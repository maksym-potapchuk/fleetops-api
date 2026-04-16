"""
Regulation assignment for KM-distance vehicles (default).
Verifies km fields correct, mi fields null.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from fleet_management.models import (
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationHistory,
)
from fleet_management.tests.helpers import (
    authenticate,
    make_item,
    make_schema,
    make_user,
    make_vehicle,
)


class KmVehicleRegulationTest(TestCase):
    """POST /fleet/regulation/{id}/assign/ with default KM vehicle."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.schema = make_schema(title="KM Schema", user=self.user)
        self.item = make_item(self.schema, title="Oil Change", every_km=10000)

    def _assign(self, entries=None):
        entries = entries or [
            {"item_id": self.item.id, "last_done_km": 50000},
        ]
        return self.client.post(
            f"/api/v1/fleet/regulation/{self.vehicle.id}/assign/",
            {"schema_id": self.schema.id, "entries": entries},
            format="json",
        )

    def _entry(self):
        return FleetVehicleRegulationEntry.objects.first()

    def test_assign_stores_last_done_km(self):
        self._assign()
        self.assertEqual(self._entry().last_done_km, 50000)

    def test_assign_computes_next_due_km(self):
        self._assign()
        self.assertEqual(self._entry().next_due_km, 60000)

    def test_assign_mi_fields_are_null(self):
        self._assign()
        entry = self._entry()
        self.assertIsNone(entry.last_done_mi)
        self.assertIsNone(entry.next_due_mi)

    def test_mark_done_without_mi_leaves_mi_null(self):
        self._assign()
        entry = self._entry()
        self.client.patch(
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/entries/{entry.id}/",
            {"last_done_km": 60000},
            format="json",
        )
        entry.refresh_from_db()
        self.assertIsNone(entry.last_done_mi)

    def test_effective_every_km_from_item(self):
        self._assign()
        self.assertEqual(self._entry().effective_every_km, 10000)

    def test_entry_override_every_km(self):
        self._assign(
            entries=[
                {"item_id": self.item.id, "last_done_km": 50000, "every_km": 15000},
            ]
        )
        entry = self._entry()
        self.assertEqual(entry.effective_every_km, 15000)
        self.assertEqual(entry.next_due_km, 65000)

    def test_assign_multiple_entries(self):
        item2 = make_item(self.schema, title="Brake Fluid", every_km=20000)
        item3 = make_item(self.schema, title="Air Filter", every_km=30000)
        self._assign(
            entries=[
                {"item_id": self.item.id, "last_done_km": 50000},
                {"item_id": item2.id, "last_done_km": 40000},
                {"item_id": item3.id, "last_done_km": 30000},
            ]
        )
        entries = FleetVehicleRegulationEntry.objects.all()
        self.assertEqual(entries.count(), 3)
        due_values = sorted(e.next_due_km for e in entries)
        self.assertEqual(due_values, [60000, 60000, 60000])

    def test_history_created_for_each_entry(self):
        item2 = make_item(self.schema, title="Coolant", every_km=15000)
        self._assign(
            entries=[
                {"item_id": self.item.id, "last_done_km": 50000},
                {"item_id": item2.id, "last_done_km": 45000},
            ]
        )
        history_count = FleetVehicleRegulationHistory.objects.filter(
            event_type="km_updated"
        ).count()
        self.assertEqual(history_count, 2)
