from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from driver.models import Driver
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle


def make_user(email="test@example.com", password="pass123!", username="testuser"):
    return User.objects.create_user(email=email, password=password, username=username)


def make_vehicle(**kwargs):
    defaults = {
        "model": "Camry",
        "manufacturer": ManufacturerChoices.TOYOTA,
        "year": 2022,
        "cost": "25000.00",
        "vin_number": "1HGBH41JXMN109186",
        "car_number": "AA6601BB",
        "color": "#FFFFFF",
        "initial_km": 0,
        "status": VehicleStatus.AUCTION,
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(**defaults)


def make_driver(**kwargs):
    defaults = {
        "first_name": "Jan",
        "last_name": "Kowalski",
        "phone_number": "48123456789",
    }
    defaults.update(kwargs)
    return Driver.objects.create(**defaults)


def authenticate(client: APIClient, user: User) -> None:
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
