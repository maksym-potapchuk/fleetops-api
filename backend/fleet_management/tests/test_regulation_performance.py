"""
Performance / bulk operation tests.
Verifies no O(n^2) regressions with large datasets.
"""

import time

from django.test import TestCase
from rest_framework.test import APIClient

from fleet_management.models import (
    FleetVehicleRegulation,
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationHistory,
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
)
from fleet_management.services import assign_regulation_to_vehicle
from fleet_management.tests.helpers import authenticate, make_user
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle


def _bulk_vehicles(n, prefix="PERF"):
    return Vehicle.objects.bulk_create([
        Vehicle(
            model="Car",
            manufacturer=ManufacturerChoices.TOYOTA,
            year=2022,
            cost="25000.00",
            vin_number=f"{prefix}{i:013d}",
            car_number=f"{prefix[:2]}{i:04d}BB",
            color="#FFFFFF",
            initial_km=i * 100,
            status=VehicleStatus.AUCTION,
        )
        for i in range(n)
    ])


class BulkCreationPerformanceTest(TestCase):
    """Bulk create operations with wall-clock assertions."""

    def test_bulk_create_1000_vehicles(self):
        t0 = time.time()
        _bulk_vehicles(1000)
        elapsed = time.time() - t0
        self.assertEqual(Vehicle.objects.count(), 1000)
        self.assertLess(elapsed, 5, f"1000 vehicles took {elapsed:.1f}s")

    def test_bulk_create_1000_schemas_with_items(self):
        t0 = time.time()
        schemas = FleetVehicleRegulationSchema.objects.bulk_create([
            FleetVehicleRegulationSchema(title=f"Schema-{i}")
            for i in range(1000)
        ])
        FleetVehicleRegulationItem.objects.bulk_create([
            FleetVehicleRegulationItem(
                schema=s, title=f"Item-{s.id}", every_km=10000,
            )
            for s in schemas
        ])
        elapsed = time.time() - t0
        self.assertEqual(FleetVehicleRegulationSchema.objects.count(), 1000)
        self.assertEqual(FleetVehicleRegulationItem.objects.count(), 1000)
        self.assertLess(elapsed, 10, f"1000 schemas+items took {elapsed:.1f}s")

    def test_bulk_create_1000_entries_directly(self):
        vehicles = _bulk_vehicles(1, prefix="ENTRY")
        schema = FleetVehicleRegulationSchema.objects.create(title="Bulk-Entry-Schema")
        items = FleetVehicleRegulationItem.objects.bulk_create([
            FleetVehicleRegulationItem(
                schema=schema, title=f"Item-{i}", every_km=5000 + i,
            )
            for i in range(1000)
        ])
        reg = FleetVehicleRegulation.objects.create(
            vehicle=vehicles[0], schema=schema,
        )
        t0 = time.time()
        FleetVehicleRegulationEntry.objects.bulk_create([
            FleetVehicleRegulationEntry(
                regulation=reg, item=item, last_done_km=i * 100,
            )
            for i, item in enumerate(items)
        ])
        elapsed = time.time() - t0
        self.assertEqual(FleetVehicleRegulationEntry.objects.count(), 1000)
        self.assertLess(elapsed, 5, f"1000 entries took {elapsed:.1f}s")

    def test_bulk_history_creation_1000_records(self):
        vehicles = _bulk_vehicles(1, prefix="HIST")
        schema = FleetVehicleRegulationSchema.objects.create(title="Hist-Schema")
        item = FleetVehicleRegulationItem.objects.create(
            schema=schema, title="Hist-Item", every_km=10000,
        )
        reg = FleetVehicleRegulation.objects.create(
            vehicle=vehicles[0], schema=schema,
        )
        entry = FleetVehicleRegulationEntry.objects.create(
            regulation=reg, item=item, last_done_km=0,
        )
        t0 = time.time()
        FleetVehicleRegulationHistory.objects.bulk_create([
            FleetVehicleRegulationHistory(
                entry=entry, event_type="KM_UPDATED",
                km_at_event=i * 100, km_remaining=10000 - i * 100,
            )
            for i in range(1000)
        ])
        elapsed = time.time() - t0
        self.assertEqual(FleetVehicleRegulationHistory.objects.count(), 1000)
        self.assertLess(elapsed, 5, f"1000 history records took {elapsed:.1f}s")


class ServiceLayerPerformanceTest(TestCase):
    """Service-layer calls with sequential assignment."""

    def setUp(self):
        self.user = make_user()

    def test_assign_regulation_to_100_vehicles(self):
        vehicles = _bulk_vehicles(100, prefix="ASGN")
        schema = FleetVehicleRegulationSchema.objects.create(title="Assign-Schema")
        item = FleetVehicleRegulationItem.objects.create(
            schema=schema, title="Oil", every_km=10000,
        )
        t0 = time.time()
        for v in vehicles:
            assign_regulation_to_vehicle(
                vehicle_pk=v.pk, schema_id=schema.id,
                entries_data=[{"item_id": item.id, "last_done_km": 0}],
                user=self.user,
            )
        elapsed = time.time() - t0
        self.assertEqual(FleetVehicleRegulation.objects.count(), 100)
        self.assertLess(elapsed, 30, f"100 assigns took {elapsed:.1f}s")


class QueryPerformanceTest(TestCase):
    """Query efficiency with large datasets."""

    def test_filter_1000_vehicles_by_regulation(self):
        vehicles = _bulk_vehicles(1000, prefix="FILT")
        schema = FleetVehicleRegulationSchema.objects.create(title="Filter-Schema")
        FleetVehicleRegulation.objects.bulk_create([
            FleetVehicleRegulation(vehicle=v, schema=schema)
            for v in vehicles[:500]
        ])
        t0 = time.time()
        count = Vehicle.objects.filter(regulations__isnull=False).distinct().count()
        elapsed = time.time() - t0
        self.assertEqual(count, 500)
        self.assertLess(elapsed, 2, f"Filter query took {elapsed:.1f}s")

    def test_next_due_km_property_on_1000_entries(self):
        vehicles = _bulk_vehicles(1, prefix="PROP")
        schema = FleetVehicleRegulationSchema.objects.create(title="Prop-Schema")
        items = FleetVehicleRegulationItem.objects.bulk_create([
            FleetVehicleRegulationItem(
                schema=schema, title=f"P-{i}", every_km=10000,
            )
            for i in range(1000)
        ])
        reg = FleetVehicleRegulation.objects.create(
            vehicle=vehicles[0], schema=schema,
        )
        entries = FleetVehicleRegulationEntry.objects.bulk_create([
            FleetVehicleRegulationEntry(
                regulation=reg, item=item, last_done_km=i * 1000,
            )
            for i, item in enumerate(items)
        ])
        t0 = time.time()
        values = [e.next_due_km for e in entries]
        elapsed = time.time() - t0
        self.assertEqual(len(values), 1000)
        self.assertTrue(all(isinstance(v, int) for v in values))
        self.assertLess(elapsed, 2, f"1000 property accesses took {elapsed:.1f}s")


class PlanAPIPerformanceTest(TestCase):
    """Plan API response time with many entries."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def test_plan_api_with_50_entries(self):
        vehicle = _bulk_vehicles(1, prefix="PLAN")[0]
        schema = FleetVehicleRegulationSchema.objects.create(title="Plan-Schema")
        items = FleetVehicleRegulationItem.objects.bulk_create([
            FleetVehicleRegulationItem(
                schema=schema, title=f"Plan-{i}", every_km=10000,
            )
            for i in range(50)
        ])
        assign_regulation_to_vehicle(
            vehicle_pk=vehicle.pk, schema_id=schema.id,
            entries_data=[{"item_id": item.id, "last_done_km": 0} for item in items],
            user=self.user,
        )
        t0 = time.time()
        res = self.client.get(f"/api/v1/fleet/vehicles/{vehicle.id}/regulation/")
        elapsed = time.time() - t0
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["entries"]), 50)
        self.assertLess(elapsed, 2, f"Plan API took {elapsed:.1f}s")
