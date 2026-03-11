import glob
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load database from a JSON fixture dump (works with any DB backend including RDS)."

    BACKUP_DIR = Path(settings.BASE_DIR).parent / "backups"

    def add_arguments(self, parser):
        parser.add_argument(
            "fixture",
            nargs="?",
            default="",
            help="Path to fixture file. Default: latest file in backups/",
        )
        parser.add_argument(
            "--no-flush",
            action="store_true",
            help="Skip flushing database before loading (may cause unique constraint errors)",
        )

    def _find_latest(self):
        pattern = str(self.BACKUP_DIR / "fleet_db_*.json")
        files = sorted(glob.glob(pattern), reverse=True)
        return Path(files[0]) if files else None

    def handle(self, *args, **options):
        fixture = options["fixture"]

        if fixture:
            path = Path(fixture)
        else:
            path = self._find_latest()

        if not path or not path.exists():
            self.stderr.write(
                self.style.ERROR(
                    f"Fixture not found: {path or 'no files in backups/'}\n"
                    f"Usage: python manage.py db_load backups/fleet_db_20260305.json"
                )
            )
            return

        size_kb = path.stat().st_size / 1024
        self.stdout.write(f"Loading fixture ({size_kb:.0f} KB): {path}")

        if not options["no_flush"]:
            self.stdout.write("Flushing database before loading...")
            call_command("flush", "--no-input", verbosity=0)

        call_command("loaddata", str(path), verbosity=1)

        self.stdout.write(self.style.SUCCESS(f"Done — database loaded from {path}"))
