from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from driver.models import Driver
from fleet_management.models import (
    FleetVehicleRegulation,
    FleetVehicleRegulationEntry,
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


def make_driver(**kwargs):
    defaults = {
        "first_name": "Jan",
        "last_name": "Kowalski",
        "phone_number": "48123456789",
    }
    defaults.update(kwargs)
    return Driver.objects.create(**defaults)


def make_regulation(vehicle, user=None, every_km=10_000, notify_before_km=500):
    """Create a full regulation chain: schema → item → regulation → entry."""
    schema = FleetVehicleRegulationSchema.objects.create(
        title=f"Schema-{vehicle.pk}",
        created_by=user,
    )
    item = FleetVehicleRegulationItem.objects.create(
        schema=schema,
        title="Oil Change",
        every_km=every_km,
        notify_before_km=notify_before_km,
    )
    regulation = FleetVehicleRegulation.objects.create(
        vehicle=vehicle,
        schema=schema,
        created_by=user,
    )
    entry = FleetVehicleRegulationEntry.objects.create(
        regulation=regulation,
        item=item,
        last_done_km=0,
    )
    return schema, item, regulation, entry


def authenticate(client: APIClient, user: User) -> None:
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
