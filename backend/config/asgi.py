"""
ASGI config for config project.

Uses Django Channels to route SSE (notification stream) via channel layer,
while all other HTTP requests go through standard Django ASGI handler.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django ASGI application early to populate AppRegistry
django_asgi_app = get_asgi_application()

# Import after django setup to avoid AppRegistryNotReady
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.urls import re_path  # noqa: E402

from notification.consumers import NotificationSSEConsumer  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [
                re_path(
                    r"^api/v1/notifications/stream/$",
                    NotificationSSEConsumer.as_asgi(),
                ),
                # All other HTTP requests → standard Django ASGI
                re_path(r"", django_asgi_app),
            ]
        ),
    }
)
