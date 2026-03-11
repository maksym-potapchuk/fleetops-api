from django.urls import path

from .consumers import NotificationSSEConsumer

urlpatterns = [
    path("api/v1/notifications/stream/", NotificationSSEConsumer.as_asgi()),
]
