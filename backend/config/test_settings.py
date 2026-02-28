"""
Test-specific Django settings.

Overrides:
- Cache: LocMemCache instead of Redis (redis package not required)
- Throttling: disabled to prevent rate-limit failures during automated tests
"""
from config.settings import *  # noqa: F401, F403

# Use in-memory cache — no Redis required for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Keep throttle rates very high so tests never hit the limit.
# ScopedRateThrottle on LoginView/RefreshView requires 'auth' scope to exist.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/minute",
    "user": "10000/minute",
    "auth": "10000/minute",
}
