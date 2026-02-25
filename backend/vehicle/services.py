import logging

from django.db import transaction

from .models import Vehicle
from fleet_management.services import grant_equipment_to_vehicle

logger = logging.getLogger(__name__)


@transaction.atomic
def create_vehicle(validated_data: dict) -> Vehicle:
    vehicle = Vehicle.objects.create(**validated_data)
    grant_equipment_to_vehicle(vehicle.id)
    logger.info(
        "Vehicle created with default equipment",
        extra={
            "status_code": 201,
            "status_message": "Created",
            "operation_type": "VEHICLE_CREATE_WITH_EQUIPMENT",
            "service": "DJANGO",
            "vehicle_id": str(vehicle.id),
            "car_number": vehicle.car_number,
        },
    )
    return vehicle
