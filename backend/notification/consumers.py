import json
import logging

from channels.db import database_sync_to_async
from channels.generic.http import AsyncHttpConsumer

from .services import MANAGERS_GROUP

logger = logging.getLogger(__name__)


class NotificationSSEConsumer(AsyncHttpConsumer):
    """Server-Sent Events consumer for real-time notifications.

    Managers connect to this endpoint and receive notification events
    pushed via the channel layer.
    """

    async def handle(self, body):
        user = await self._authenticate()
        if user is None:
            await self.send_response(
                401,
                b"Unauthorized",
                headers=[(b"Content-Type", b"text/plain")],
            )
            return

        await self.send_headers(
            status=200,
            headers=[
                (b"Content-Type", b"text/event-stream"),
                (b"Cache-Control", b"no-cache"),
                (b"Connection", b"keep-alive"),
                (b"X-Accel-Buffering", b"no"),
            ],
        )

        self.group_name = MANAGERS_GROUP
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Send initial unread count so the client can render badge immediately
        unread_count = await self._get_unread_count()
        await self._send_sse_event(
            "init",
            {"unread_count": unread_count},
        )

    async def disconnect(self):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_event(self, event):
        """Handler for messages sent to the group with type 'notification.event'."""
        await self._send_sse_event("notification", event["data"])

    async def _send_sse_event(self, event_type: str, data: dict) -> None:
        payload = f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
        await self.send_body(payload.encode("utf-8"), more_body=True)

    async def _authenticate(self):
        """Extract and validate JWT from cookies."""
        headers = dict(self.scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()
        if not cookie_header:
            return None

        cookies = {}
        for item in cookie_header.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()

        token = cookies.get("access_token")
        if not token:
            return None

        return await self._validate_token(token)

    @database_sync_to_async
    def _validate_token(self, raw_token: str):
        try:
            from rest_framework_simplejwt.tokens import AccessToken

            validated = AccessToken(raw_token)
            from django.contrib.auth import get_user_model

            user_model = get_user_model()
            return user_model.objects.get(id=validated["user_id"])
        except Exception:
            return None

    @database_sync_to_async
    def _get_unread_count(self) -> int:
        from .models import Notification

        return Notification.objects.filter(is_read=False).count()
