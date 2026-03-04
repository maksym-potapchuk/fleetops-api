import logging

from django.db import models, transaction

from fleet_management.services import grant_equipment_to_vehicle

from .constants import VehicleStatus
from .models import Vehicle

logger = logging.getLogger(__name__)


@transaction.atomic
def create_vehicle(validated_data: dict, user=None) -> Vehicle:
    if user:
        validated_data["created_by"] = user
    if "status_position" not in validated_data:
        status = validated_data.get("status", VehicleStatus.PREPARATION)
        max_pos = Vehicle.objects.filter(
            status=status, is_archived=False
        ).aggregate(m=models.Max("status_position"))["m"] or 0
        validated_data["status_position"] = max_pos + 1000
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
