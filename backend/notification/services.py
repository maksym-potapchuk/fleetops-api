from datetime import date
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from .constants import NotificationSource, NotificationStatus, NotificationType
from .models import Notification

logger = logging.getLogger(__name__)

MANAGERS_GROUP = "notifications_managers"

# ── Default thresholds (used when no preferences exist) ──────────────────────
DEFAULT_INSPECTION_DAYS = [7, 3, 1]
DEFAULT_SERVICE_PLAN_DAYS = [3, 1]
# Temporary certificate reminders: weekly cadence, up to 5 reminders.
CERTIFICATE_REMINDER_WINDOW_DAYS = 30
CERTIFICATE_REMINDER_INTERVAL_DAYS = 7
CERTIFICATE_REMINDER_MAX = 5
DEFAULT_OVERDUE_INTERVAL = 7
DEFAULT_OVERDUE_MAX = 3
DEFAULT_REGULATION_NOTIFY_BEFORE_KM = 500


def _get_global_preferences():
    """Load notification preferences. Uses first manager's prefs or defaults."""
    from .models import NotificationPreferences

    prefs = NotificationPreferences.objects.first()
    if prefs:
        return prefs
    return None


def _should_send_overdue_reminder(
    dedup_prefix: str,
    overdue_days: int,
    interval: int,
    max_reminders: int,
) -> tuple[bool, int]:
    """Determine if an overdue reminder should be sent.

    Returns (should_send, reminder_number).
    Reminder #0 = first overdue notification (day 0).
    Reminder #1 = first repeat (after `interval` days), etc.
    """
    if overdue_days < 0:
        return False, 0

    # Count existing overdue notifications for this item
    existing_count = Notification.objects.filter(
        dedup_key__startswith=dedup_prefix,
    ).count()

    if existing_count >= max_reminders:
        return False, 0

    if existing_count == 0:
        # First overdue — always send
        return True, 0

    # Check if enough days passed since last reminder
    last = (
        Notification.objects.filter(dedup_key__startswith=dedup_prefix)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    if last:
        days_since_last = (timezone.now() - last).days
        if days_since_last >= interval:
            return True, existing_count
    return False, 0


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
    source: str = NotificationSource.SYSTEM,
    push: bool = True,
    retry_at=None,
    dedup_key: str | None = None,
) -> Notification:
    """Create a notification and optionally push it to connected managers.

    If dedup_key is provided, skips creation when an unread notification
    with the same dedup_key already exists.
    """
    if dedup_key:
        already_exists = Notification.objects.filter(
            dedup_key=dedup_key,
            is_read=False,
        ).exists()
        if already_exists:
            return None

    notification = Notification.objects.create(
        type=notification_type,
        status=status,
        source=source,
        vehicle=vehicle,
        driver=driver,
        payload=payload or {},
        retry_at=retry_at,
        dedup_key=dedup_key,
    )
    if push:
        transaction.on_commit(lambda: _push_to_managers(notification))
    return notification


# ── Regulation checks (km-based) ────────────────────────────────────────────


def check_regulation_notifications(vehicle) -> list[Notification]:
    """Check all regulation entries for a vehicle and create notifications if needed.

    Called after vehicle.initial_km is updated.
    """
    from fleet_management.models import FleetVehicleRegulationEntry

    prefs = _get_global_preferences()
    if prefs and not prefs.regulation_enabled:
        return []
    # Skip sold/archived vehicles — they shouldn't generate any reminders.
    if vehicle.status == "SOLD" or vehicle.is_archived:
        return []

    # Global threshold overrides per-item settings
    global_notify_before = (
        prefs.regulation_notify_before_km
        if prefs
        else DEFAULT_REGULATION_NOTIFY_BEFORE_KM
    )

    current_km = vehicle.initial_km
    entries = FleetVehicleRegulationEntry.objects.filter(
        regulation__vehicle=vehicle,
    ).select_related("item", "regulation")

    created = []
    for entry in entries:
        remaining = entry.km_remaining(current_km)
        notify_before = global_notify_before

        if remaining <= 0:
            n_type = NotificationType.REGULATION_OVERDUE
            payload = {
                "entry_id": entry.id,
                "item_title": entry.item.title,
                "every_km": entry.effective_every_km,
                "overdue_by_km": abs(remaining),
                "next_due_km": entry.next_due_km,
                "current_km": current_km,
            }
        elif remaining <= notify_before:
            n_type = NotificationType.REGULATION_APPROACHING
            payload = {
                "entry_id": entry.id,
                "item_title": entry.item.title,
                "every_km": entry.effective_every_km,
                "km_remaining": remaining,
                "next_due_km": entry.next_due_km,
                "current_km": current_km,
            }
        else:
            continue

        dedup = f"{n_type}:{vehicle.pk}:{entry.id}"
        notification = create_notification(
            notification_type=n_type,
            vehicle=vehicle,
            payload=payload,
            dedup_key=dedup,
        )
        if notification:
            created.append(notification)

    return created


# ── Technical inspection checks (date-based) ────────────────────────────────


def check_inspection_notifications() -> list[Notification]:
    """Check all active vehicles for upcoming/expired technical inspections.

    For each vehicle, considers only the latest inspection with next_inspection_date set.
    Uses manager's configured thresholds from NotificationPreferences.
    """
    from vehicle.models import TechnicalInspection

    prefs = _get_global_preferences()
    if prefs and not prefs.inspection_enabled:
        return []

    threshold_days = (
        prefs.inspection_notify_days
        if prefs and prefs.inspection_notify_days
        else DEFAULT_INSPECTION_DAYS
    )
    overdue_interval = (
        prefs.overdue_reminder_interval if prefs else DEFAULT_OVERDUE_INTERVAL
    )
    overdue_max = prefs.overdue_reminder_max if prefs else DEFAULT_OVERDUE_MAX
    today = date.today()

    # Subquery: latest inspection per vehicle that has a next_inspection_date
    latest_per_vehicle = (
        TechnicalInspection.objects.filter(
            vehicle=OuterRef("vehicle"),
            next_inspection_date__isnull=False,
        )
        .order_by("-inspection_date")
        .values("id")[:1]
    )

    inspections = (
        TechnicalInspection.objects.filter(
            id__in=Subquery(latest_per_vehicle),
            vehicle__is_archived=False,
        )
        .exclude(vehicle__status="SOLD")
        .select_related("vehicle")
    )

    created = []
    for insp in inspections:
        days_remaining = (insp.next_inspection_date - today).days

        if days_remaining <= 0:
            overdue_days = abs(days_remaining)
            dedup_prefix = f"inspection_expired:{insp.vehicle_id}:{insp.id}"
            should_send, reminder_num = _should_send_overdue_reminder(
                dedup_prefix,
                overdue_days,
                overdue_interval,
                overdue_max,
            )
            if not should_send:
                continue

            n_type = NotificationType.INSPECTION_EXPIRED
            dedup = f"{dedup_prefix}:r{reminder_num}"
            payload = {
                "inspection_id": insp.id,
                "next_inspection_date": str(insp.next_inspection_date),
                "overdue_days": overdue_days,
                "reminder_number": reminder_num,
            }
        elif days_remaining in threshold_days:
            n_type = NotificationType.INSPECTION_EXPIRING
            dedup = f"inspection_expiring:{insp.vehicle_id}:{insp.id}:{days_remaining}d"
            payload = {
                "inspection_id": insp.id,
                "next_inspection_date": str(insp.next_inspection_date),
                "days_remaining": days_remaining,
            }
        else:
            continue

        notification = create_notification(
            notification_type=n_type,
            vehicle=insp.vehicle,
            payload=payload,
            dedup_key=dedup,
        )
        if notification:
            created.append(notification)

    return created


# ── Service plan checks (date-based) ────────────────────────────────────────


def check_service_plan_notifications() -> list[Notification]:
    """Check incomplete service plans for approaching/overdue dates."""
    from fleet_management.models import ServicePlan

    prefs = _get_global_preferences()
    if prefs and not prefs.service_plan_enabled:
        return []

    notify_days = (
        prefs.service_plan_notify_days
        if prefs and prefs.service_plan_notify_days
        else DEFAULT_SERVICE_PLAN_DAYS
    )
    overdue_interval = (
        prefs.overdue_reminder_interval if prefs else DEFAULT_OVERDUE_INTERVAL
    )
    overdue_max = prefs.overdue_reminder_max if prefs else DEFAULT_OVERDUE_MAX
    today = date.today()

    plans = (
        ServicePlan.objects.filter(
            is_done=False,
            vehicle__is_archived=False,
        )
        .exclude(vehicle__status="SOLD")
        .select_related("vehicle")
    )

    created = []
    for plan in plans:
        days_remaining = (plan.planned_at - today).days

        if days_remaining <= 0:
            overdue_days = abs(days_remaining)
            dedup_prefix = f"service_plan_overdue:{plan.vehicle_id}:{plan.id}"
            should_send, reminder_num = _should_send_overdue_reminder(
                dedup_prefix,
                overdue_days,
                overdue_interval,
                overdue_max,
            )
            if not should_send:
                continue

            n_type = NotificationType.SERVICE_PLAN_OVERDUE
            dedup = f"{dedup_prefix}:r{reminder_num}"
            payload = {
                "plan_id": plan.id,
                "plan_title": plan.title,
                "planned_at": str(plan.planned_at),
                "overdue_days": overdue_days,
                "reminder_number": reminder_num,
            }
        elif days_remaining in notify_days:
            n_type = NotificationType.SERVICE_PLAN_DUE
            dedup = f"service_plan_due:{plan.vehicle_id}:{plan.id}:{days_remaining}d"
            payload = {
                "plan_id": plan.id,
                "plan_title": plan.title,
                "planned_at": str(plan.planned_at),
                "days_remaining": days_remaining,
            }
        else:
            continue

        notification = create_notification(
            notification_type=n_type,
            vehicle=plan.vehicle,
            payload=payload,
            dedup_key=dedup,
        )
        if notification:
            created.append(notification)

    return created


# ── Registration certificate checks (date-based, temporary only) ───────────


def check_certificate_notifications() -> list[Notification]:
    """Notify about temporary registration certificates approaching/past expiry.

    Only active temporary certificates with valid_until set are checked.
    """
    from vehicle.models import CertificateType, RegistrationCertificate

    prefs = _get_global_preferences()
    if prefs and not prefs.certificate_enabled:
        return []

    overdue_interval = (
        prefs.overdue_reminder_interval if prefs else DEFAULT_OVERDUE_INTERVAL
    )
    overdue_max = prefs.overdue_reminder_max if prefs else DEFAULT_OVERDUE_MAX
    today = date.today()

    certificates = (
        RegistrationCertificate.objects.filter(
            is_active=True,
            certificate_type=CertificateType.TEMPORARY,
            valid_until__isnull=False,
            vehicle__is_archived=False,
        )
        .exclude(vehicle__status="SOLD")
        .select_related("vehicle")
    )

    created = []
    for cert in certificates:
        days_remaining = (cert.valid_until - today).days

        if days_remaining <= 0:
            overdue_days = abs(days_remaining)
            dedup_prefix = f"certificate_expired:{cert.vehicle_id}:{cert.id}"
            should_send, reminder_num = _should_send_overdue_reminder(
                dedup_prefix,
                overdue_days,
                overdue_interval,
                overdue_max,
            )
            if not should_send:
                continue
            n_type = NotificationType.CERTIFICATE_EXPIRED
            dedup = f"{dedup_prefix}:r{reminder_num}"
            payload = {
                "certificate_id": str(cert.id),
                "valid_until": str(cert.valid_until),
                "overdue_days": overdue_days,
                "reminder_number": reminder_num,
            }
        elif days_remaining <= CERTIFICATE_REMINDER_WINDOW_DAYS:
            # Weekly reminders: send up to N notifications, one per week,
            # while the temporary certificate is in the reminder window.
            reminder_prefix = f"certificate_expiring:{cert.vehicle_id}:{cert.id}"
            should_send, reminder_num = _should_send_overdue_reminder(
                reminder_prefix,
                # `overdue_days` arg in helper is repurposed: any non-negative
                # value enables the "first reminder always sends" path.
                days_remaining,
                CERTIFICATE_REMINDER_INTERVAL_DAYS,
                CERTIFICATE_REMINDER_MAX,
            )
            if not should_send:
                continue
            n_type = NotificationType.CERTIFICATE_EXPIRING
            dedup = f"{reminder_prefix}:r{reminder_num}"
            payload = {
                "certificate_id": str(cert.id),
                "valid_until": str(cert.valid_until),
                "days_remaining": days_remaining,
                "reminder_number": reminder_num,
            }
        else:
            continue

        notification = create_notification(
            notification_type=n_type,
            vehicle=cert.vehicle,
            payload=payload,
            dedup_key=dedup,
        )
        if notification:
            created.append(notification)
    return created


# ── Run all scheduled checks ────────────────────────────────────────────────


def check_all_scheduled_notifications() -> dict:
    """Run all date-based notification checks. Called by management command."""
    inspections = check_inspection_notifications()
    plans = check_service_plan_notifications()
    certificates = check_certificate_notifications()
    return {
        "inspections": len(inspections),
        "service_plans": len(plans),
        "certificates": len(certificates),
    }


# ── Resolve (approve / reject) ──────────────────────────────────────────────


@transaction.atomic
def resolve_notification(notification: Notification, action: str, user) -> Notification:
    """Approve or reject a pending notification.

    For MILEAGE_SUBMITTED:
      - approve → create MileageLog, update vehicle.initial_km, check regulations
      - reject → just mark as rejected
    """
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
