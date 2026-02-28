"""
Vehicle signals.

Responsibilities:
1. Track driver assignment changes on Vehicle saves / deletes.
2. Keep Driver.has_vehicle in sync.
3. Maintain VehicleDriverHistory records (open / close entries).
4. Invalidate driver-related caches whenever has_vehicle changes.

Note: VehicleOwnerHistory is managed directly via API (no signal needed).
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Vehicle, VehicleDriverHistory

logger = logging.getLogger(__name__)

_SENTINEL = object()  # marker for "signal data not stored"


# ── pre_save — capture previous driver before the row is changed ──────────────

@receiver(pre_save, sender=Vehicle)
def vehicle_capture_prev_driver(sender, instance, **kwargs):
    """Store the current (old) driver_id on the instance before it changes."""
    if not instance.pk:
        instance._prev_driver_id = _SENTINEL
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._prev_driver_id = old.driver_id
    except sender.DoesNotExist:
        instance._prev_driver_id = _SENTINEL


# ── post_save — react to the change ──────────────────────────────────────────

@receiver(post_save, sender=Vehicle)
def vehicle_post_save(sender, instance, created, **kwargs):
    """
    On create   → assign initial driver (if any).
    On update   → detect driver change and reconcile.
    """
    prev = getattr(instance, "_prev_driver_id", _SENTINEL)

    if created:
        if instance.driver_id:
            _assign_driver(instance, old_driver_id=None, new_driver_id=instance.driver_id)
        return

    if prev is _SENTINEL:
        # pre_save didn't capture anything (e.g. bulk_create with update_fields
        # that bypasses pre_save logic). Skip to avoid inconsistent state.
        return

    if prev == instance.driver_id:
        return  # driver unchanged — nothing to do

    _assign_driver(instance, old_driver_id=prev, new_driver_id=instance.driver_id)


# ── pre_delete — close history and clear has_vehicle before row disappears ────

@receiver(pre_delete, sender=Vehicle)
def vehicle_pre_delete(sender, instance, **kwargs):
    """
    When a vehicle is deleted, close its open driver-history entry
    and update the driver's has_vehicle flag if needed.
    """
    if not instance.driver_id:
        return
    try:
        _assign_driver(instance, old_driver_id=instance.driver_id, new_driver_id=None)
    except Exception:
        logger.error(
            "Error handling driver state on vehicle deletion",
            extra={"vehicle_id": str(instance.pk)},
            exc_info=True,
        )


# ── Core logic ────────────────────────────────────────────────────────────────

def _assign_driver(vehicle: Vehicle, old_driver_id, new_driver_id) -> None:
    """
    Reconcile driver assignment:
    • Close the open VehicleDriverHistory entry for old_driver_id.
    • Update old driver's has_vehicle (False if no other vehicles).
    • Create a new VehicleDriverHistory entry for new_driver_id.
    • Update new driver's has_vehicle = True.
    • Invalidate affected driver caches.
    """
    from driver.models import Driver  # local import avoids circular dependency at module level

    try:
        if old_driver_id:
            VehicleDriverHistory.objects.filter(
                vehicle=vehicle,
                driver_id=old_driver_id,
                unassigned_at__isnull=True,
            ).update(unassigned_at=timezone.now())

            # Only mark has_vehicle=False if this driver has no other active vehicles.
            still_has = (
                Vehicle.objects.filter(driver_id=old_driver_id)
                .exclude(pk=vehicle.pk)
                .exists()
            )
            if not still_has:
                Driver.objects.filter(pk=old_driver_id).update(has_vehicle=False)
                logger.info(
                    "Driver has_vehicle set to False",
                    extra={"driver_id": str(old_driver_id)},
                )

        if new_driver_id:
            VehicleDriverHistory.objects.create(
                vehicle=vehicle,
                driver_id=new_driver_id,
            )
            Driver.objects.filter(pk=new_driver_id).update(has_vehicle=True)
            logger.info(
                "Driver has_vehicle set to True",
                extra={"driver_id": str(new_driver_id)},
            )

        # Invalidate driver caches after the transaction commits so we never
        # clear the cache for a write that ultimately rolled back.
        transaction.on_commit(
            lambda: _invalidate_driver_caches(old_driver_id, new_driver_id)
        )

    except Exception:
        logger.error(
            "Error in _assign_driver signal handler",
            extra={
                "vehicle_id": str(vehicle.pk),
                "old_driver_id": str(old_driver_id),
                "new_driver_id": str(new_driver_id),
            },
            exc_info=True,
        )


def _invalidate_driver_caches(*driver_ids) -> None:
    """Clear driver list cache + detail caches for each affected driver."""
    try:
        from config.cache_utils import invalidate_driver  # local to avoid import cycle

        invalidate_driver()  # always clear the full list
        for driver_id in driver_ids:
            if driver_id:
                invalidate_driver(driver_id)
        logger.debug(
            "Driver cache invalidated (post-commit)",
            extra={"driver_ids": [str(d) for d in driver_ids if d]},
        )
    except Exception:
        logger.warning("Could not invalidate driver cache from signal", exc_info=True)
