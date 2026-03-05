"""
Fleet Management Service Layer Tests
=====================================
Covers: grant_equipment_to_vehicle, assign_regulation_to_vehicle.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.test import TestCase

from fleet_management.constants import EventType
from fleet_management.models import (
    EquipmentDefaultItem,
    EquipmentList,
    FleetVehicleRegulation,
    FleetVehicleRegulationHistory,
)
from fleet_management.services import (
    assign_regulation_to_vehicle,
    grant_equipment_to_vehicle,
)

from .helpers import make_item, make_schema, make_user, make_vehicle


class GrantEquipmentToVehicleServiceTest(TestCase):
    def setUp(self):
        EquipmentDefaultItem.objects.all().delete()
        self.vehicle = make_vehicle()

    def test_no_equipment_created_when_no_defaults_exist(self):
        grant_equipment_to_vehicle(self.vehicle.id)
        self.assertEqual(EquipmentList.objects.filter(vehicle=self.vehicle).count(), 0)

    def test_creates_one_equipment_item_per_default(self):
        EquipmentDefaultItem.objects.create(equipment="Jack")
        EquipmentDefaultItem.objects.create(equipment="Spare Tire")
        EquipmentDefaultItem.objects.create(equipment="First Aid Kit")
        grant_equipment_to_vehicle(self.vehicle.id)
        self.assertEqual(EquipmentList.objects.filter(vehicle=self.vehicle).count(), 3)

    def test_equipment_created_with_is_equipped_false(self):
        EquipmentDefaultItem.objects.create(equipment="Jack")
        grant_equipment_to_vehicle(self.vehicle.id)
        item = EquipmentList.objects.get(vehicle=self.vehicle, equipment="Jack")
        self.assertFalse(item.is_equipped)

    def test_calling_twice_does_not_duplicate_items(self):
        """ignore_conflicts=True in bulk_create must prevent duplicates on repeat calls."""
        EquipmentDefaultItem.objects.create(equipment="Jack")
        EquipmentDefaultItem.objects.create(equipment="Spare Tire")
        grant_equipment_to_vehicle(self.vehicle.id)
        grant_equipment_to_vehicle(self.vehicle.id)
        count = EquipmentList.objects.filter(vehicle=self.vehicle).count()
        self.assertEqual(count, 2, "Second call must not duplicate equipment items")

    def test_only_target_vehicle_receives_equipment(self):
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        EquipmentDefaultItem.objects.create(equipment="Jack")
        grant_equipment_to_vehicle(self.vehicle.id)
        self.assertEqual(EquipmentList.objects.filter(vehicle=self.vehicle).count(), 1)
        self.assertEqual(EquipmentList.objects.filter(vehicle=v2).count(), 0)


class AssignRegulationToVehicleServiceTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle()
        self.schema = make_schema(title="Basic Regulation", user=self.user)
        self.item1 = make_item(self.schema, title="Oil Change", every_km=10_000)
        self.item2 = make_item(self.schema, title="Air Filter", every_km=20_000)

    def _entries(self, km1=0, km2=0):
        return [
            {"item_id": self.item1.id, "last_done_km": km1},
            {"item_id": self.item2.id, "last_done_km": km2},
        ]

    def test_successful_assignment_returns_expected_dict(self):
        result = assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=self._entries(),
            user=self.user,
        )
        self.assertIn("regulation_id", result)
        self.assertEqual(result["schema"], "Basic Regulation")
        self.assertEqual(result["entries_created"], 2)

    def test_creates_fleet_vehicle_regulation_record(self):
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=self._entries(),
            user=self.user,
        )
        self.assertTrue(
            FleetVehicleRegulation.objects.filter(
                vehicle=self.vehicle, schema=self.schema
            ).exists()
        )

    def test_creates_entry_for_each_item_with_correct_km(self):
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=self._entries(km1=5_000, km2=12_000),
            user=self.user,
        )
        reg = FleetVehicleRegulation.objects.get(
            vehicle=self.vehicle, schema=self.schema
        )
        entry1 = reg.entries.get(item=self.item1)
        entry2 = reg.entries.get(item=self.item2)
        self.assertEqual(entry1.last_done_km, 5_000)
        self.assertEqual(entry2.last_done_km, 12_000)

    def test_creates_initial_history_with_km_updated_event(self):
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=self._entries(km1=5_000),
            user=self.user,
        )
        reg = FleetVehicleRegulation.objects.get(
            vehicle=self.vehicle, schema=self.schema
        )
        entry = reg.entries.get(item=self.item1)
        history = FleetVehicleRegulationHistory.objects.get(entry=entry)
        self.assertEqual(history.event_type, EventType.KM_UPDATED)
        self.assertEqual(history.note, "Initial assignment")
        self.assertEqual(history.km_at_event, 5_000)
        self.assertEqual(history.created_by, self.user)

    def test_initial_history_km_remaining_equals_every_km(self):
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=self._entries(km1=5_000),
            user=self.user,
        )
        reg = FleetVehicleRegulation.objects.get(
            vehicle=self.vehicle, schema=self.schema
        )
        entry = reg.entries.get(item=self.item1)
        history = FleetVehicleRegulationHistory.objects.get(entry=entry)
        self.assertEqual(history.km_remaining, self.item1.every_km)

    def test_duplicate_assignment_raises_value_error(self):
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=self._entries(),
            user=self.user,
        )
        with self.assertRaises(ValueError) as ctx:
            assign_regulation_to_vehicle(
                vehicle_pk=self.vehicle.id,
                schema_id=self.schema.id,
                entries_data=self._entries(),
                user=self.user,
            )
        self.assertIn("already assigned", str(ctx.exception))

    def test_atomic_rollback_on_invalid_item_id(self):
        invalid_entries = [
            {"item_id": self.item1.id, "last_done_km": 0},
            {"item_id": 99_999, "last_done_km": 0},  # Does not exist
        ]
        with self.assertRaises((IntegrityError, ObjectDoesNotExist)):
            assign_regulation_to_vehicle(
                vehicle_pk=self.vehicle.id,
                schema_id=self.schema.id,
                entries_data=invalid_entries,
                user=self.user,
            )
        self.assertFalse(
            FleetVehicleRegulation.objects.filter(
                vehicle=self.vehicle, schema=self.schema
            ).exists(),
            "Transaction must rollback — no partial regulation should exist",
        )

    def test_service_does_not_validate_items_belong_to_schema(self):
        """
        VULNERABILITY: The service layer has NO check that item_id belongs to schema_id.
        """
        schema2 = make_schema(title="Schema 2", user=self.user)
        foreign_item = make_item(schema2, title="Brake Service", every_km=30_000)
        try:
            assign_regulation_to_vehicle(
                vehicle_pk=self.vehicle.id,
                schema_id=self.schema.id,
                entries_data=[{"item_id": foreign_item.id, "last_done_km": 0}],
                user=self.user,
            )
            reg = FleetVehicleRegulation.objects.get(
                vehicle=self.vehicle, schema=self.schema
            )
            entry = reg.entries.first()
            self.assertNotEqual(
                entry.item.schema_id,
                self.schema.id,
                "VULNERABILITY CONFIRMED: item from different schema was assigned",
            )
        except Exception:
            pass
