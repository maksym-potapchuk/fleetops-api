import logging

from django.db import transaction

from config import cache_utils
from .models import (
    EventType,
    EquipmentDefaultItem, 
    EquipmentList, 
    FleetVehicleRegulation, 
    FleetVehicleRegulationHistory,
    FleetVehicleRegulationEntry
    )

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
        cache_utils.invalidate_equipment(vehicle_id)
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

@transaction.atomic
def assign_regulation_to_vehicle(vehicle_pk, schema_id, entries_data, user):
    if FleetVehicleRegulation.objects.filter(
        vehicle_id=vehicle_pk,
        schema_id=schema_id
    ).exists():
        raise ValueError("Schema already assigned to this vehicle")

    regulation=FleetVehicleRegulation.objects.create(
        vehicle_id=vehicle_pk,
        schema_id=schema_id
    )

    created_entries=[]
    for entry_data in entries_data:
        entry=FleetVehicleRegulationEntry.objects.create(
            regulation=regulation,
            item_id=entry_data["item_id"],
            last_done_km=entry_data["last_done_km"]
        )
        FleetVehicleRegulationHistory.objects.create(
                entry=entry,
                event_type=EventType.KM_UPDATED,
                km_at_event=entry_data["last_done_km"],
                km_remaining=entry.next_due_km - entry_data["last_done_km"],
                note="Initial assignment",
                created_by=user,
            )
        created_entries.append(entry)
    transaction.on_commit(lambda: cache_utils.invalidate_regulation_plan(vehicle_pk))
    return {
        "regulation_id": regulation.id,
        "schema": regulation.schema.title,
        "entries_created": len(created_entries),
    }
