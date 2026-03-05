import logging

from django.db import models, transaction
from django.utils import timezone

from fleet_management.services import grant_equipment_to_vehicle

from .constants import VehicleStatus
from .models import OwnerHistory, Vehicle, VehicleOwner

logger = logging.getLogger(__name__)


@transaction.atomic
def create_vehicle(validated_data: dict, user=None) -> Vehicle:
    driver = validated_data.pop("driver", None)
    agreement_number = validated_data.pop("agreement_number", "")

    if user:
        validated_data["created_by"] = user
    if "status_position" not in validated_data:
        status = validated_data.get("status", VehicleStatus.AUCTION)
        max_pos = (
            Vehicle.objects.filter(status=status, is_archived=False).aggregate(
                m=models.Max("status_position")
            )["m"]
            or 0
        )
        validated_data["status_position"] = max_pos + 1000
    vehicle = Vehicle.objects.create(**validated_data)
    grant_equipment_to_vehicle(vehicle.id)

    if driver:
        assign_owner(vehicle, driver, agreement_number=agreement_number, user=user)

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


@transaction.atomic
def assign_owner(vehicle, driver, agreement_number="", user=None):
    try:
        current = vehicle.current_owner
        OwnerHistory.objects.create(
            vehicle=vehicle,
            driver=current.driver,
            agreement_number=current.agreement_number,
            assigned_at=current.assigned_at,
            unassigned_at=timezone.now(),
            created_by=current.created_by,
        )
        old_driver = current.driver
        current.delete()

        if not VehicleOwner.objects.filter(driver=old_driver).exists():
            old_driver.has_vehicle = False
            old_driver.save(update_fields=["has_vehicle"])

        transaction.on_commit(lambda: _invalidate_driver_caches(old_driver.id))
    except VehicleOwner.DoesNotExist:
        pass

    VehicleOwner.objects.create(
        vehicle=vehicle,
        driver=driver,
        agreement_number=agreement_number,
        created_by=user,
    )
    driver.has_vehicle = True
    driver.save(update_fields=["has_vehicle"])

    transaction.on_commit(lambda: _invalidate_caches(vehicle.id, driver.id))


@transaction.atomic
def unassign_owner(vehicle):
    try:
        current = vehicle.current_owner
    except VehicleOwner.DoesNotExist:
        return

    OwnerHistory.objects.create(
        vehicle=vehicle,
        driver=current.driver,
        agreement_number=current.agreement_number,
        assigned_at=current.assigned_at,
        unassigned_at=timezone.now(),
        created_by=current.created_by,
    )
    old_driver = current.driver
    current.delete()

    if not VehicleOwner.objects.filter(driver=old_driver).exists():
        old_driver.has_vehicle = False
        old_driver.save(update_fields=["has_vehicle"])

    transaction.on_commit(lambda: _invalidate_caches(vehicle.id, old_driver.id))


def _invalidate_caches(vehicle_id, driver_id=None):
    try:
        from config.cache_utils import invalidate_driver, invalidate_vehicle

        invalidate_vehicle(vehicle_id)
        if driver_id:
            invalidate_driver()
            invalidate_driver(driver_id)
    except Exception:
        logger.warning("Could not invalidate caches", exc_info=True)


def _invalidate_driver_caches(driver_id):
    try:
        from config.cache_utils import invalidate_driver

        invalidate_driver()
        invalidate_driver(driver_id)
    except Exception:
        logger.warning("Could not invalidate driver cache", exc_info=True)
