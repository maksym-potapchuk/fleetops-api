"""
Fleet Management Model Tests
=============================
Covers: FleetVehicleRegulationSchema, FleetVehicleRegulationItem,
FleetVehicleRegulationEntry, FleetVehicleRegulation, ServicePlan,
EquipmentList, FleetService.
"""

from datetime import date

from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from fleet_management.models import (
    EquipmentList,
    FleetService,
    FleetVehicleRegulation,
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationSchema,
    ServicePlan,
)

from .helpers import make_item, make_schema, make_vehicle


class FleetVehicleRegulationSchemaModelTest(TestCase):
    """Tests for FleetVehicleRegulationSchema — default schema uniqueness & save() logic."""

    def test_single_default_schema_can_be_created(self):
        schema = make_schema(title="Schema A", is_default=True)
        self.assertTrue(schema.is_default)

    def test_setting_second_default_unsets_first(self):
        """When a new schema is saved with is_default=True, the previous default must be unset."""
        schema_a = make_schema(title="Schema A", is_default=True)
        schema_b = make_schema(title="Schema B", is_default=True)

        schema_a.refresh_from_db()
        schema_b.refresh_from_db()

        self.assertFalse(
            schema_a.is_default,
            "Schema A must lose is_default after Schema B is saved with is_default=True",
        )
        self.assertTrue(schema_b.is_default)

    def test_only_one_default_after_multiple_saves(self):
        for i in range(5):
            make_schema(title=f"Schema {i}", is_default=True)

        count = FleetVehicleRegulationSchema.objects.filter(is_default=True).count()
        self.assertEqual(count, 1, "Only one schema may be default at any time")

    def test_saving_non_default_does_not_disturb_existing_default(self):
        default_schema = make_schema(title="Default Schema", is_default=True)
        make_schema(title="Non-Default Schema", is_default=False)

        default_schema.refresh_from_db()
        self.assertTrue(
            default_schema.is_default,
            "Saving a non-default schema must not clear an existing default",
        )

    def test_updating_existing_default_keeps_it_default(self):
        """Updating fields on an already-default schema must not strip its default status."""
        schema = make_schema(title="Schema A", is_default=True)
        schema.title = "Schema A — Updated"
        schema.save()

        schema.refresh_from_db()
        self.assertTrue(schema.is_default)
        self.assertEqual(schema.title, "Schema A — Updated")

    def test_direct_queryset_update_bypasses_save_logic(self):
        """
        VULNERABILITY: FleetVehicleRegulationSchema.objects.filter(...).update(is_default=True)
        bypasses save(), skipping the "unset all others" step.
        """
        make_schema(title="Schema A", is_default=True)
        schema_b = make_schema(title="Schema B", is_default=False)

        with self.assertRaises(IntegrityError):
            FleetVehicleRegulationSchema.objects.filter(pk=schema_b.pk).update(
                is_default=True
            )

    def test_schema_created_by_is_nullable(self):
        schema = FleetVehicleRegulationSchema.objects.create(title="Orphan Schema")
        self.assertIsNone(schema.created_by)

    def test_schema_title_unique_at_db_level(self):
        """Title has a database-level unique constraint (migration 0007)."""
        make_schema(title="Duplicate Title")
        with self.assertRaises(IntegrityError):
            make_schema(title="Duplicate Title")


class FleetVehicleRegulationItemModelTest(TestCase):
    def setUp(self):
        self.schema = make_schema(title="Test Schema")

    def test_unique_together_schema_and_title(self):
        make_item(self.schema, title="Oil Change")
        with self.assertRaises(IntegrityError):
            make_item(self.schema, title="Oil Change")

    def test_same_title_allowed_across_different_schemas(self):
        schema2 = make_schema(title="Second Schema")
        make_item(self.schema, title="Oil Change")
        item2 = make_item(schema2, title="Oil Change")
        self.assertIsNotNone(item2.pk)

    def test_str_representation(self):
        item = make_item(self.schema, title="Oil Change", every_km=10_000)
        self.assertIn("Oil Change", str(item))
        self.assertIn("10000", str(item))


class FleetVehicleRegulationEntryModelTest(TestCase):
    """Tests for FleetVehicleRegulationEntry business properties."""

    def setUp(self):
        self.vehicle = make_vehicle()
        self.schema = make_schema(title="Test Schema")
        self.item = make_item(self.schema, every_km=10_000)
        self.regulation = FleetVehicleRegulation.objects.create(
            vehicle=self.vehicle, schema=self.schema
        )
        self.entry = FleetVehicleRegulationEntry.objects.create(
            regulation=self.regulation,
            item=self.item,
            last_done_km=5_000,
        )

    # --- next_due_km property ---

    def test_next_due_km_is_last_done_plus_every_km(self):
        self.assertEqual(self.entry.next_due_km, 15_000)  # 5000 + 10000

    def test_next_due_km_at_zero_baseline(self):
        item2 = make_item(self.schema, title="Tires", every_km=5_000)
        entry = FleetVehicleRegulationEntry.objects.create(
            regulation=self.regulation, item=item2, last_done_km=0
        )
        self.assertEqual(entry.next_due_km, 5_000)

    # --- is_due() ---

    def test_is_due_at_exact_threshold(self):
        self.assertTrue(self.entry.is_due(15_000))

    def test_is_due_above_threshold(self):
        self.assertTrue(self.entry.is_due(20_000))

    def test_not_due_below_threshold(self):
        self.assertFalse(self.entry.is_due(14_999))

    # --- km_remaining() ---

    def test_km_remaining_positive_when_not_due(self):
        self.assertEqual(self.entry.km_remaining(10_000), 5_000)

    def test_km_remaining_zero_at_exact_threshold(self):
        self.assertEqual(self.entry.km_remaining(15_000), 0)

    def test_km_remaining_negative_when_overdue(self):
        remaining = self.entry.km_remaining(20_000)
        self.assertEqual(remaining, -5_000)  # 15000 - 20000

    # --- constraints ---

    def test_unique_together_regulation_and_item(self):
        with self.assertRaises(IntegrityError):
            FleetVehicleRegulationEntry.objects.create(
                regulation=self.regulation, item=self.item, last_done_km=0
            )

    def test_last_done_km_defaults_to_zero(self):
        item2 = make_item(self.schema, title="Brake Fluid")
        entry = FleetVehicleRegulationEntry.objects.create(
            regulation=self.regulation, item=item2
        )
        self.assertEqual(entry.last_done_km, 0)


class FleetVehicleRegulationModelTest(TestCase):
    def setUp(self):
        self.vehicle = make_vehicle()
        self.schema = make_schema(title="Basic")

    def test_unique_together_schema_and_vehicle(self):
        FleetVehicleRegulation.objects.create(vehicle=self.vehicle, schema=self.schema)
        with self.assertRaises(IntegrityError):
            FleetVehicleRegulation.objects.create(
                vehicle=self.vehicle, schema=self.schema
            )

    def test_different_schemas_same_vehicle_allowed(self):
        schema2 = make_schema(title="Advanced")
        FleetVehicleRegulation.objects.create(vehicle=self.vehicle, schema=self.schema)
        reg2 = FleetVehicleRegulation.objects.create(
            vehicle=self.vehicle, schema=schema2
        )
        self.assertIsNotNone(reg2.pk)

    def test_schema_delete_blocked_by_protect_when_regulation_exists(self):
        FleetVehicleRegulation.objects.create(vehicle=self.vehicle, schema=self.schema)
        with self.assertRaises(ProtectedError):
            self.schema.delete()

    def test_regulation_deleted_when_vehicle_deleted(self):
        """FleetVehicleRegulation uses on_delete=CASCADE from Vehicle."""
        FleetVehicleRegulation.objects.create(vehicle=self.vehicle, schema=self.schema)
        self.vehicle.delete()
        self.assertEqual(
            FleetVehicleRegulation.objects.filter(schema=self.schema).count(), 0
        )


class ServicePlanModelTest(TestCase):
    def setUp(self):
        self.vehicle = make_vehicle()

    def test_unique_together_vehicle_and_title(self):
        ServicePlan.objects.create(
            vehicle=self.vehicle, title="Annual Service", planned_at=date.today()
        )
        with self.assertRaises(IntegrityError):
            ServicePlan.objects.create(
                vehicle=self.vehicle, title="Annual Service", planned_at=date.today()
            )

    def test_same_title_allowed_for_different_vehicles(self):
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        ServicePlan.objects.create(
            vehicle=self.vehicle, title="Annual Service", planned_at=date.today()
        )
        plan2 = ServicePlan.objects.create(
            vehicle=v2, title="Annual Service", planned_at=date.today()
        )
        self.assertIsNotNone(plan2.pk)

    def test_is_done_defaults_to_false(self):
        plan = ServicePlan.objects.create(
            vehicle=self.vehicle, title="Test", planned_at=date.today()
        )
        self.assertFalse(plan.is_done)

    def test_description_is_optional(self):
        plan = ServicePlan.objects.create(
            vehicle=self.vehicle, title="No Desc", planned_at=date.today()
        )
        self.assertIsNone(plan.description)


class EquipmentListModelTest(TestCase):
    def setUp(self):
        self.vehicle = make_vehicle()

    def test_unique_together_vehicle_and_equipment(self):
        EquipmentList.objects.create(vehicle=self.vehicle, equipment="Tire Iron")
        with self.assertRaises(IntegrityError):
            EquipmentList.objects.create(vehicle=self.vehicle, equipment="Tire Iron")

    def test_is_equipped_defaults_to_false(self):
        item = EquipmentList.objects.create(vehicle=self.vehicle, equipment="Jack")
        self.assertFalse(item.is_equipped)

    def test_approved_at_is_nullable(self):
        item = EquipmentList.objects.create(vehicle=self.vehicle, equipment="Reflector")
        self.assertIsNone(item.approved_at)

    def test_str_includes_vehicle_and_equipment(self):
        item = EquipmentList.objects.create(vehicle=self.vehicle, equipment="Jack")
        self.assertIn("Jack", str(item))


class FleetServiceModelTest(TestCase):
    def test_create_fleet_service(self):
        svc = FleetService.objects.create(name="Midas", description="General repair")
        self.assertEqual(str(svc), "Midas")

    def test_description_optional(self):
        svc = FleetService.objects.create(name="TyreFit")
        self.assertIsNone(svc.description)
