import logging
import math

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from driver.models import Driver
from vehicle.models import Vehicle

from .constants import NotificationStatus, NotificationType
from .models import Notification
from .serializers import (
    MileageSubmitSerializer,
    NotificationSerializer,
    ResolveNotificationSerializer,
)
from .services import create_notification, resolve_notification

logger = logging.getLogger(__name__)

MILES_TO_KM = 1.60934


class NotificationListView(generics.ListAPIView):
    """List notifications with optional filters: type, status, is_read."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.select_related("vehicle", "driver").all()
        n_type = self.request.query_params.get("type")
        n_status = self.request.query_params.get("status")
        is_read = self.request.query_params.get("is_read")

        if n_type:
            qs = qs.filter(type=n_type)
        if n_status:
            qs = qs.filter(status=n_status)
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == "true")
        return qs


class UnreadCountView(APIView):
    """Return count of unread notifications."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(is_read=False).count()
        return Response({"unread_count": count})


class MarkReadView(APIView):
    """Mark a single notification as read."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        if not notification.is_read:
            from django.utils import timezone

            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    """Mark all unread notifications as read."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.utils import timezone

        updated = Notification.objects.filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response({"updated": updated})


class ResolveNotificationView(APIView):
    """Approve or reject a pending notification."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        serializer = ResolveNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resolved = resolve_notification(
                notification,
                action=serializer.validated_data["action"],
                user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(NotificationSerializer(resolved).data)


class MileageSubmitView(APIView):
    """Bot-facing endpoint: driver submits mileage for manager approval.

    Creates a PENDING notification that the manager must approve/reject.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MileageSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        vehicle = get_object_or_404(Vehicle, pk=data["vehicle_id"])
        driver = Driver.objects.filter(telegram_id=data["driver_telegram_id"]).first()
        if not driver:
            return Response(
                {"detail": "Driver not found by telegram_id."},
                status=status.HTTP_404_NOT_FOUND,
            )

        km = data["km"]
        if data["unit"] == "miles":
            km = math.ceil(km * MILES_TO_KM)

        current_km = vehicle.initial_km
        if km <= current_km:
            return Response(
                {"detail": f"Mileage must be greater than current ({current_km} km)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification = create_notification(
            notification_type=NotificationType.MILEAGE_SUBMITTED,
            vehicle=vehicle,
            driver=driver,
            status=NotificationStatus.PENDING,
            payload={
                "submitted_km": km,
                "current_km": current_km,
                "delta_km": km - current_km,
                "unit": data["unit"],
                "source": "telegram_bot",
            },
        )
        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED,
        )
