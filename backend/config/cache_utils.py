"""
Cache key management and invalidation utilities.

Strategy
--------
* List caches   → version-based keys.  Any write bumps the entity version;
                  all old list entries become unreachable and expire on their TTL.
* Detail caches → per-PK key.  Explicitly deleted on update / delete.
* All cache ops  → wrapped in try/except so a Redis outage never breaks a request.

Key anatomy:
    fleet:<entity>:list:v<N>:<params_hash8>
    fleet:<entity>:detail:<pk>
    fleet:<entity>:version                    (never expires)
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── TTLs pulled from settings ────────────────────────────────────────────────
_VEHICLE_LIST_TTL = getattr(settings, "CACHE_TTL_VEHICLE_LIST", 30)
_VEHICLE_DETAIL_TTL = getattr(settings, "CACHE_TTL_VEHICLE_DETAIL", 60)
_DRIVER_LIST_TTL = getattr(settings, "CACHE_TTL_DRIVER_LIST", 300)
_SCHEMA_LIST_TTL = getattr(settings, "CACHE_TTL_SCHEMA_LIST", 600)
_SCHEMA_DETAIL_TTL = getattr(settings, "CACHE_TTL_SCHEMA_DETAIL", 600)
_REG_PLAN_TTL = getattr(settings, "CACHE_TTL_REGULATION_PLAN", 300)
_EQUIPMENT_TTL = getattr(settings, "CACHE_TTL_EQUIPMENT", 300)

# ── Version-key names ────────────────────────────────────────────────────────
_VK_VEHICLE = "v:vehicle"
_VK_SCHEMA = "v:schema"


# ── Internal helpers ─────────────────────────────────────────────────────────


def _safe_get(key: str):
    try:
        return cache.get(key)
    except Exception:
        logger.warning("cache GET failed", extra={"key": key}, exc_info=True)
        return None


def _safe_set(key: str, value, timeout: int) -> None:
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        logger.warning("cache SET failed", extra={"key": key}, exc_info=True)


def _safe_delete(*keys: str) -> None:
    try:
        cache.delete_many(list(keys))
    except Exception:
        logger.warning("cache DELETE failed", extra={"keys": keys}, exc_info=True)


def _get_version(version_key: str) -> int:
    """Return current version, defaulting to 0 if key absent."""
    try:
        val = cache.get(version_key)
        return val if val is not None else 0
    except Exception:
        return 0


def _bump_version(version_key: str) -> None:
    """
    Atomically increment the version counter.
    • cache.add()  → atomic "set if not exists".  Returns True when it creates the key.
    • cache.incr() → used when key already exists.
    If incr fails (race: key deleted between add/incr), fall back to set(1).
    """
    try:
        created = cache.add(version_key, 1, timeout=None)
        if not created:
            try:
                cache.incr(version_key)
            except Exception:
                cache.set(version_key, 1, timeout=None)
    except Exception:
        logger.warning(
            "cache version bump failed",
            extra={"version_key": version_key},
            exc_info=True,
        )


def _params_hash(query_params) -> str:
    """8-char MD5 of sorted query params → stable, short cache-key segment."""
    items = sorted((k, v) for k, v in query_params.items())
    raw = "&".join(f"{k}={v}" for k, v in items)
    return hashlib.md5(raw.encode()).hexdigest()[:8]


# ── Vehicle ───────────────────────────────────────────────────────────────────


def get_vehicle_list(query_params) -> list | None:
    v = _get_version(_VK_VEHICLE)
    return _safe_get(f"vehicle:list:v{v}:{_params_hash(query_params)}")


def set_vehicle_list(query_params, data) -> None:
    v = _get_version(_VK_VEHICLE)
    _safe_set(
        f"vehicle:list:v{v}:{_params_hash(query_params)}", data, _VEHICLE_LIST_TTL
    )


def get_vehicle_detail(vehicle_id) -> dict | None:
    return _safe_get(f"vehicle:detail:{vehicle_id}")


def set_vehicle_detail(vehicle_id, data) -> None:
    _safe_set(f"vehicle:detail:{vehicle_id}", data, _VEHICLE_DETAIL_TTL)


def invalidate_vehicle(vehicle_id=None) -> None:
    """
    Bump the vehicle version → all existing list caches become unreachable.
    Optionally also delete the specific vehicle's detail cache.
    """
    _bump_version(_VK_VEHICLE)
    if vehicle_id is not None:
        _safe_delete(f"vehicle:detail:{vehicle_id}")


# ── Driver ────────────────────────────────────────────────────────────────────

_DRIVER_LIST_KEY = "driver:list"
_DRIVER_DETAIL_FMT = "driver:detail:{}"


def get_driver_list() -> list | None:
    return _safe_get(_DRIVER_LIST_KEY)


def set_driver_list(data) -> None:
    _safe_set(_DRIVER_LIST_KEY, data, _DRIVER_LIST_TTL)


def get_driver_detail(driver_id) -> dict | None:
    return _safe_get(_DRIVER_DETAIL_FMT.format(driver_id))


def set_driver_detail(driver_id, data) -> None:
    _safe_set(_DRIVER_DETAIL_FMT.format(driver_id), data, _DRIVER_LIST_TTL)


def invalidate_driver(driver_id=None) -> None:
    """
    Always clears the full driver list (has_vehicle may have changed).
    Optionally clears a specific driver's detail cache.
    """
    keys = [_DRIVER_LIST_KEY]
    if driver_id is not None:
        keys.append(_DRIVER_DETAIL_FMT.format(driver_id))
    _safe_delete(*keys)


# ── Regulation Schema ─────────────────────────────────────────────────────────


def get_schema_list(query_params) -> list | None:
    v = _get_version(_VK_SCHEMA)
    return _safe_get(f"schema:list:v{v}:{_params_hash(query_params)}")


def set_schema_list(query_params, data) -> None:
    v = _get_version(_VK_SCHEMA)
    _safe_set(f"schema:list:v{v}:{_params_hash(query_params)}", data, _SCHEMA_LIST_TTL)


def get_schema_detail(schema_id) -> dict | None:
    return _safe_get(f"schema:detail:{schema_id}")


def set_schema_detail(schema_id, data) -> None:
    _safe_set(f"schema:detail:{schema_id}", data, _SCHEMA_DETAIL_TTL)


def invalidate_schema(schema_id=None) -> None:
    _bump_version(_VK_SCHEMA)
    if schema_id is not None:
        _safe_delete(f"schema:detail:{schema_id}")


# ── Vehicle Regulation Plan ───────────────────────────────────────────────────


def get_regulation_plan(vehicle_id) -> dict | None:
    return _safe_get(f"regulation:plan:{vehicle_id}")


def set_regulation_plan(vehicle_id, data) -> None:
    _safe_set(f"regulation:plan:{vehicle_id}", data, _REG_PLAN_TTL)


def invalidate_regulation_plan(vehicle_id) -> None:
    _safe_delete(f"regulation:plan:{vehicle_id}")


# ── Equipment List ────────────────────────────────────────────────────────────


def get_equipment_list(vehicle_id) -> list | None:
    return _safe_get(f"equipment:{vehicle_id}")


def set_equipment_list(vehicle_id, data) -> None:
    _safe_set(f"equipment:{vehicle_id}", data, _EQUIPMENT_TTL)


def invalidate_equipment(vehicle_id) -> None:
    _safe_delete(f"equipment:{vehicle_id}")
