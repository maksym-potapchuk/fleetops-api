from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from account.models import User


class Command(BaseCommand):
    help = "Change a user's password by email (password entered interactively)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="User email.")

    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"])

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as err:
            raise CommandError(f"No user found with email {email}") from err

        password = getpass("New password: ")
        if not password:
            raise CommandError("Password cannot be empty")
        if getpass("Confirm password: ") != password:
            raise CommandError("Passwords do not match")

        user.set_password(password)
        user.save(update_fields=["password"])

        self.stdout.write(self.style.SUCCESS(f"Password updated for {user.email}"))
