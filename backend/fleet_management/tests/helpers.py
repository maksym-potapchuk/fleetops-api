from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from fleet_management.models import (
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
)
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


def make_schema(title="Basic", is_default=False, user=None):
    return FleetVehicleRegulationSchema.objects.create(
        title=title,
        is_default=is_default,
        created_by=user,
    )


def make_item(schema, title="Oil Change", every_km=10_000, notify_before_km=500):
    return FleetVehicleRegulationItem.objects.create(
        schema=schema,
        title=title,
        every_km=every_km,
        notify_before_km=notify_before_km,
    )


def authenticate(client: APIClient, user: User) -> None:
    """Injects a valid cookie-based JWT into an APIClient."""
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
