from .models import EquipmentDefaultItem, EquipmentList


def grant_equipment_to_vehicle(vehicle_id):
    """Bulk-create EquipmentList entries from all EquipmentDefaultItem for a vehicle.
    Skips items that already exist for the vehicle (ignore_conflicts)."""
    defaults = EquipmentDefaultItem.objects.all()
    items = [
        EquipmentList(vehicle_id=vehicle_id, equipment=d.equipment)
        for d in defaults
    ]
    return EquipmentList.objects.bulk_create(items, ignore_conflicts=True)
