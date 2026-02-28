from django.core.management.base import BaseCommand

from vehicle.models import Vehicle


class Command(BaseCommand):
    help = "Delete all vehicles (and their related data) from the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt.",
        )

    def handle(self, *args, **options):
        count = Vehicle.objects.count()

        if count == 0:
            self.stdout.write("No vehicles found — nothing to delete.")
            return

        if not options["force"]:
            confirm = input(
                f"This will permanently delete all {count} vehicle(s) and their related data. "
                "Type 'yes' to confirm: "
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write("Aborted.")
                return

        Vehicle.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} vehicle(s)."))
