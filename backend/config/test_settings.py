"""
Test-specific Django settings.

Overrides:
- Cache: LocMemCache instead of Redis (redis package not required)
- Throttling: disabled to prevent rate-limit failures during automated tests
"""

from config.settings import *  # noqa: F403

# Use in-memory SQLite — fast, no external DB required for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use in-memory cache — no Redis required for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Use in-memory channel layer — no Redis required for tests
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Keep throttle rates very high so tests never hit the limit.
# ScopedRateThrottle on LoginView/RefreshView requires 'auth' scope to exist.
# Force local file storage — tests must not depend on S3
USE_S3 = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/minute",
    "user": "10000/minute",
    "auth": "10000/minute",
}
