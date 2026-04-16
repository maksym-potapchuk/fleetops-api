"""
Regulation assignment for MI-distance vehicles.
Verifies mi fields are stored, computed, and returned correctly.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from fleet_management.models import FleetVehicleRegulationEntry
from fleet_management.tests.helpers import (
    authenticate,
    make_item,
    make_schema,
    make_user,
    make_vehicle,
)


class MiVehicleRegulationTest(TestCase):
    """POST /fleet/regulation/{id}/assign/ with distance_unit=MI vehicle."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(distance_unit="MI")
        self.schema = make_schema(title="MI Schema", user=self.user)
        self.item = make_item(
            self.schema, title="Oil Change", every_km=16000,
            every_mi=10000, notify_before_km=800, notify_before_mi=500,
        )

    def _assign(self, last_done_km=161000, last_done_mi=100000, **entry_kw):
        entry = {"item_id": self.item.id, "last_done_km": last_done_km}
        if last_done_mi is not None:
            entry["last_done_mi"] = last_done_mi
        entry.update(entry_kw)
        return self.client.post(
            f"/api/v1/fleet/regulation/{self.vehicle.id}/assign/",
            {"schema_id": self.schema.id, "entries": [entry]},
            format="json",
        )

    def _entry(self):
        return FleetVehicleRegulationEntry.objects.first()

    def test_assign_stores_last_done_mi(self):
        self._assign(last_done_km=161000, last_done_mi=100000)
        self.assertEqual(self._entry().last_done_mi, 100000)

    def test_assign_computes_next_due_mi(self):
        self._assign(last_done_km=161000, last_done_mi=100000)
        self.assertEqual(self._entry().next_due_mi, 110000)

    def test_effective_every_mi_falls_back_to_item(self):
        self._assign()
        self.assertEqual(self._entry().effective_every_mi, 10000)

    def test_effective_every_mi_entry_override_via_patch(self):
        self._assign()
        entry = self._entry()
        self.client.patch(
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/entries/{entry.id}/",
            {"every_mi": 7000},
            format="json",
        )
        entry.refresh_from_db()
        self.assertEqual(entry.effective_every_mi, 7000)
        self.assertEqual(entry.next_due_mi, 107000)

    def test_effective_notify_before_mi_falls_back_to_item(self):
        self._assign()
        self.assertEqual(self._entry().effective_notify_before_mi, 500)

    def test_mark_done_updates_both_km_and_mi(self):
        self._assign()
        entry = self._entry()
        self.client.patch(
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/entries/{entry.id}/",
            {"last_done_km": 200000, "last_done_mi": 124274},
            format="json",
        )
        entry.refresh_from_db()
        self.assertEqual(entry.last_done_km, 200000)
        self.assertEqual(entry.last_done_mi, 124274)

    def test_mark_done_recalculates_next_due_mi(self):
        self._assign()
        entry = self._entry()
        self.client.patch(
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/entries/{entry.id}/",
            {"last_done_km": 200000, "last_done_mi": 124274},
            format="json",
        )
        entry.refresh_from_db()
        self.assertEqual(entry.next_due_mi, 134274)

    def test_plan_api_returns_mi_fields(self):
        self._assign()
        res = self.client.get(f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/")
        e = res.data["entries"][0]
        self.assertEqual(e["last_done_mi"], 100000)
        self.assertEqual(e["next_due_mi"], 110000)
        self.assertEqual(e["effective_every_mi"], 10000)
        self.assertEqual(e["effective_notify_before_mi"], 500)

    def test_assign_without_mi_data_leaves_mi_null(self):
        self._assign(last_done_mi=None)
        entry = self._entry()
        self.assertIsNone(entry.last_done_mi)
        self.assertIsNone(entry.next_due_mi)

    def test_non_standard_mi_98876_plus_6213(self):
        item2 = make_item(
            self.schema, title="Brake Fluid", every_km=10000, every_mi=6213,
        )
        self.client.post(
            f"/api/v1/fleet/regulation/{self.vehicle.id}/assign/",
            {"schema_id": self.schema.id, "entries": [
                {"item_id": item2.id, "last_done_km": 159100, "last_done_mi": 98876},
            ]},
            format="json",
        )
        entry = FleetVehicleRegulationEntry.objects.get(item=item2)
        self.assertEqual(entry.next_due_mi, 105089)
