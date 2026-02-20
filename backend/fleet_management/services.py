import logging

from .models import EquipmentDefaultItem, EquipmentList

logger = logging.getLogger(__name__)


def grant_equipment_to_vehicle(vehicle_id):
    """Bulk-create EquipmentList entries from all EquipmentDefaultItem for a vehicle.
    Skips items that already exist for the vehicle (ignore_conflicts)."""
    logger.info(
        "Granting default equipment to vehicle",
        extra={
            "status_code": 100,
            "status_message": "Continue",
            "operation_type": "EQUIPMENT_GRANT_REQUEST",
            "service": "DJANGO",
            "vehicle_id": str(vehicle_id),
        },
    )
    try:
        defaults = EquipmentDefaultItem.objects.all()
        items = [
            EquipmentList(vehicle_id=vehicle_id, equipment=d.equipment)
            for d in defaults
        ]
        result = EquipmentList.objects.bulk_create(items, ignore_conflicts=True)
        logger.info(
            "Default equipment granted to vehicle successfully",
            extra={
                "status_code": 201,
                "status_message": "Created",
                "operation_type": "EQUIPMENT_GRANT_SUCCESS",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_id),
                "granted_count": len(result),
            },
        )
        return result
    except Exception:
        logger.error(
            "Failed to grant default equipment to vehicle",
            extra={
                "status_code": 500,
                "status_message": "Internal Server Error",
                "operation_type": "EQUIPMENT_GRANT_FAILED",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_id),
            },
            exc_info=True,
        )
        raise
