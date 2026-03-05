from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User


def make_user(
    email="test@example.com",
    password="pass123!",
    username="testuser",
    **extra,
):
    return User.objects.create_user(
        email=email, password=password, username=username, **extra
    )


def authenticate(client: APIClient, user: User) -> None:
    """Injects a valid cookie-based JWT into an APIClient."""
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
