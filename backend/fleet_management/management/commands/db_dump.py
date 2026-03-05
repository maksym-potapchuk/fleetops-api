import datetime
import os
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export full database dump as JSON fixture (works with any DB backend including RDS)."

    BACKUP_DIR = Path(settings.BASE_DIR).parent / "backups"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            default="",
            help="Output file path. Default: backups/fleet_db_<date>.json",
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="JSON indent level (default: 2)",
        )

    def handle(self, *args, **options):
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        if options["output"]:
            out_path = Path(options["output"])
        else:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = self.BACKUP_DIR / f"fleet_db_{stamp}.json"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        exclude = [
            "contenttypes",
            "auth.permission",
            "admin.logentry",
            "sessions.session",
            "token_blacklist",
        ]

        self.stdout.write(f"Dumping database → {out_path}")

        with open(out_path, "w", encoding="utf-8") as f:
            call_command(
                "dumpdata",
                "--natural-foreign",
                "--natural-primary",
                f"--indent={options['indent']}",
                *[f"--exclude={e}" for e in exclude],
                stdout=f,
            )

        size_kb = os.path.getsize(out_path) / 1024
        self.stdout.write(self.style.SUCCESS(f"Done — {size_kb:.0f} KB → {out_path}"))
