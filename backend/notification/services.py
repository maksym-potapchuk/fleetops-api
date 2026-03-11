import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from .constants import NotificationStatus, NotificationType
from .models import Notification

logger = logging.getLogger(__name__)

MANAGERS_GROUP = "notifications_managers"


def _push_to_managers(notification: Notification) -> None:
    """Send notification event to all connected managers via channel layer."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        from .serializers import NotificationSerializer

        data = NotificationSerializer(notification).data
        async_to_sync(channel_layer.group_send)(
            MANAGERS_GROUP,
            {"type": "notification.event", "data": data},
        )
        # Track delivery
        Notification.objects.filter(pk=notification.pk).update(
            sent_at=timezone.now(),
            sent_to="web",
        )
    except Exception:
        logger.warning("Failed to push notification via channel layer", exc_info=True)


def create_notification(
    *,
    notification_type: str,
    vehicle=None,
    driver=None,
    payload: dict | None = None,
    status: str = NotificationStatus.INFO,
    push: bool = True,
    retry_at=None,
) -> Notification:
    """Create a notification and optionally push it to connected managers."""
    notification = Notification.objects.create(
        type=notification_type,
        status=status,
        vehicle=vehicle,
        driver=driver,
        payload=payload or {},
        retry_at=retry_at,
    )
    if push:
        transaction.on_commit(lambda: _push_to_managers(notification))
    return notification


def check_regulation_notifications(vehicle) -> list[Notification]:
    """Check all regulation entries for a vehicle and create notifications if needed.

    Called after vehicle.initial_km is updated.
    Skips creation if an unread notification for the same entry+type already exists.
    """
    from fleet_management.models import FleetVehicleRegulationEntry

    current_km = vehicle.initial_km
    entries = FleetVehicleRegulationEntry.objects.filter(
        regulation__vehicle=vehicle,
    ).select_related("item", "regulation")

    created = []
    for entry in entries:
        remaining = entry.km_remaining(current_km)
        notify_before = entry.item.notify_before_km

        if remaining <= 0:
            n_type = NotificationType.REGULATION_OVERDUE
            payload = {
                "entry_id": entry.id,
                "item_title": entry.item.title,
                "every_km": entry.item.every_km,
                "overdue_by_km": abs(remaining),
                "next_due_km": entry.next_due_km,
                "current_km": current_km,
            }
        elif remaining <= notify_before:
            n_type = NotificationType.REGULATION_APPROACHING
            payload = {
                "entry_id": entry.id,
                "item_title": entry.item.title,
                "every_km": entry.item.every_km,
                "km_remaining": remaining,
                "next_due_km": entry.next_due_km,
                "current_km": current_km,
            }
        else:
            continue

        # Deduplicate: skip if unread notification for same entry+type exists
        already_exists = Notification.objects.filter(
            type=n_type,
            vehicle=vehicle,
            is_read=False,
            payload__entry_id=entry.id,
        ).exists()
        if already_exists:
            continue

        notification = create_notification(
            notification_type=n_type,
            vehicle=vehicle,
            payload=payload,
        )
        created.append(notification)

    return created


@transaction.atomic
def resolve_notification(notification: Notification, action: str, user) -> Notification:
    """Approve or reject a pending notification.

    For MILEAGE_SUBMITTED:
      - approve → create MileageLog, update vehicle.initial_km, check regulations
      - reject → just mark as rejected
    """
    from django.utils import timezone

    if notification.status != NotificationStatus.PENDING:
        raise ValueError("Only pending notifications can be resolved.")

    if action == "approve":
        notification.status = NotificationStatus.APPROVED
        notification.resolved_at = timezone.now()
        notification.resolved_by = user

        if notification.type == NotificationType.MILEAGE_SUBMITTED:
            _approve_mileage(notification, user)

    elif action == "reject":
        notification.status = NotificationStatus.REJECTED
        notification.resolved_at = timezone.now()
        notification.resolved_by = user
    else:
        raise ValueError(f"Unknown action: {action}")

    notification.save()
    transaction.on_commit(lambda: _push_to_managers(notification))
    return notification


def _approve_mileage(notification: Notification, user) -> None:
    """Create MileageLog and update vehicle km after manager approval."""
    from django.utils import timezone

    from config.cache_utils import invalidate_vehicle
    from vehicle.models import MileageLog, Vehicle

    vehicle = notification.vehicle
    submitted_km = notification.payload.get("submitted_km")
    if not submitted_km or not vehicle:
        raise ValueError("Invalid mileage notification payload.")

    current_km = vehicle.initial_km
    if submitted_km <= current_km:
        raise ValueError(
            f"Submitted km ({submitted_km}) is not greater than current ({current_km})."
        )

    MileageLog.objects.create(
        vehicle=vehicle,
        km=submitted_km,
        recorded_at=timezone.now().date(),
        note=f"Approved from bot submission (was {current_km} km)",
        created_by=user,
    )
    Vehicle.objects.filter(pk=vehicle.pk).update(initial_km=submitted_km)
    vehicle.refresh_from_db()

    transaction.on_commit(lambda: invalidate_vehicle(vehicle.pk))
    check_regulation_notifications(vehicle)
