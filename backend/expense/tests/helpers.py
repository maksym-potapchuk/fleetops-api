from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle


def make_user(email="expense@example.com", password="pass123!", username="expuser"):
    return User.objects.create_user(email=email, password=password, username=username)


def make_vehicle(**kwargs):
    defaults = {
        "model": "Camry",
        "manufacturer": ManufacturerChoices.TOYOTA,
        "year": 2022,
        "cost": "25000.00",
        "vin_number": "1HGBH41JXMN109186",
        "car_number": "AA6601BB",
        "initial_km": 0,
        "status": VehicleStatus.AUCTION,
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(**defaults)


def authenticate(client: APIClient, user: User) -> None:
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
