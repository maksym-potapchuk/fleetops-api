from django.core.management.base import BaseCommand

from notification.constants import NotificationType
from notification.services import create_notification
from vehicle.models import Vehicle


class Command(BaseCommand):
    help = "Send a test notification for the first active vehicle."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            default="inspection_expiring",
            choices=[c.value for c in NotificationType],
            help="Notification type to send",
        )

    def handle(self, *args, **options):
        vehicle = (
            Vehicle.objects.filter(is_archived=False).exclude(status="SOLD").first()
        )
        if not vehicle:
            self.stderr.write(self.style.ERROR("No active vehicles found."))
            return

        n_type = options["type"]

        payload_map = {
            "inspection_expiring": {
                "days_remaining": 3,
                "next_inspection_date": "2026-03-28",
            },
            "inspection_expired": {
                "overdue_days": 5,
                "next_inspection_date": "2026-03-20",
            },
            "regulation_approaching": {
                "item_title": "Oil change",
                "km_remaining": 450,
                "next_due_km": 50000,
                "current_km": 49550,
            },
            "regulation_overdue": {
                "item_title": "Oil change",
                "overdue_by_km": 200,
                "next_due_km": 50000,
                "current_km": 50200,
            },
            "regulation_performed": {"item_title": "Oil change"},
            "service_plan_due": {
                "plan_title": "Brake pad replacement",
                "planned_at": "2026-03-28",
                "days_remaining": 3,
            },
            "service_plan_overdue": {
                "plan_title": "Brake pad replacement",
                "planned_at": "2026-03-20",
                "overdue_days": 5,
            },
            "mileage_submitted": {
                "submitted_km": 51000,
                "current_km": 50000,
                "delta_km": 1000,
                "unit": "km",
            },
            "service_report": {"report": "Test service report"},
        }

        notification = create_notification(
            notification_type=n_type,
            vehicle=vehicle,
            payload=payload_map.get(n_type, {}),
        )

        if notification:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sent [{n_type}] for {vehicle} (id: {notification.id})"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Notification skipped (dedup)."))
