from django.core.management.base import BaseCommand

from fleet_management.models import FleetVehicleRegulationSchema


class Command(BaseCommand):
    help = "Delete the default regulation schema and ALL related vehicle data (regulations, entries, history, notifications)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        schema = FleetVehicleRegulationSchema.objects.filter(is_default=True).first()
        if not schema:
            self.stderr.write(self.style.WARNING("No default regulation schema found."))
            return

        # Count related objects
        reg_count = schema.regulations.count()
        item_count = schema.items.count()

        self.stdout.write(
            f'Default schema: "{schema.title}" (id={schema.id})\n'
            f"  {item_count} item(s)\n"
            f"  {reg_count} vehicle regulation(s) (with entries, history, notifications)"
        )

        if not options["force"]:
            confirm = input(
                "\nThis will CASCADE-delete everything above. Continue? [y/N] "
            )
            if confirm.lower() != "y":
                self.stdout.write("Aborted.")
                return

        # Delete vehicle regulations first (PROTECT on schema FK)
        deleted_regs, _ = schema.regulations.all().delete()
        # Now delete the schema (cascades to items)
        schema.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted default schema + {item_count} items + {deleted_regs} vehicle regulation(s) with all entries/history."
            )
        )
