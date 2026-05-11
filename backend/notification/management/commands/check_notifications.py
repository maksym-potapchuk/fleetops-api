from django.core.management.base import BaseCommand

from notification.services import check_all_scheduled_notifications


class Command(BaseCommand):
    help = "Run daily notification checks (inspections, service plans, certificates)."

    def handle(self, *args, **options):
        results = check_all_scheduled_notifications()

        self.stdout.write(f"Inspections: {results['inspections']} new notifications")
        self.stdout.write(
            f"Service plans: {results['service_plans']} new notifications"
        )
        self.stdout.write(f"Certificates: {results['certificates']} new notifications")

        total = (
            results["inspections"] + results["service_plans"] + results["certificates"]
        )
        if total:
            self.stdout.write(self.style.SUCCESS(f"Created {total} notifications."))
        else:
            self.stdout.write(self.style.SUCCESS("No new notifications."))
