import logging

from django.db import models, transaction

from fleet_management.services import grant_equipment_to_vehicle

from .constants import VehicleStatus
from .models import Vehicle, VehicleStatusHistory

logger = logging.getLogger(__name__)


@transaction.atomic
def create_vehicle(validated_data: dict, user=None) -> Vehicle:
    validated_data.pop("driver", None)
    validated_data.pop("agreement_number", "")

    if user:
        validated_data["created_by"] = user
    if "status_position" not in validated_data:
        status = validated_data.get("status", VehicleStatus.AUCTION)
        min_pos = (
            Vehicle.objects.filter(status=status, is_archived=False).aggregate(
                m=models.Min("status_position")
            )["m"]
            or 1000
        )
        validated_data["status_position"] = min_pos - 1000
    vehicle = Vehicle.objects.create(**validated_data)
    grant_equipment_to_vehicle(vehicle.id)

    record_status_change(
        vehicle,
        old_status=None,
        new_status=vehicle.status,
        user=user,
        source=VehicleStatusHistory.ChangeSource.CREATION,
    )

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


def record_status_change(
    vehicle,
    old_status,
    new_status,
    user=None,
    source=VehicleStatusHistory.ChangeSource.MANUAL,
):
    """Record a status transition in the history log."""
    if old_status == new_status:
        return None
    return VehicleStatusHistory.objects.create(
        vehicle=vehicle,
        old_status=old_status,
        new_status=new_status,
        source=source,
        changed_by=user,
    )
