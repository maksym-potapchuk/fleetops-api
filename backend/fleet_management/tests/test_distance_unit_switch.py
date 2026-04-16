"""
Switch vehicle distance_unit (KM↔MI) after regulation assigned.
Verifies km fields (source of truth) never change on switch.
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


class KmToMiSwitchTest(TestCase):
    """Start with KM vehicle, switch to MI after assign."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(distance_unit="KM")
        self.schema = make_schema(title="Switch Schema", user=self.user)
        self.item = make_item(
            self.schema, title="Oil Change", every_km=10000,
            every_mi=6000, notify_before_mi=300,
        )
        self.client.post(
            f"/api/v1/fleet/regulation/{self.vehicle.id}/assign/",
            {"schema_id": self.schema.id, "entries": [
                {"item_id": self.item.id, "last_done_km": 50000},
            ]},
            format="json",
        )
        self.entry = FleetVehicleRegulationEntry.objects.first()

    def _switch(self, unit):
        self.vehicle.distance_unit = unit
        self.vehicle.save(update_fields=["distance_unit"])
        return self.vehicle

    def test_switch_km_to_mi_km_fields_unchanged(self):
        self._switch("MI")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 50000)
        self.assertEqual(self.entry.next_due_km, 60000)

    def test_switch_km_to_mi_mi_fields_still_null(self):
        self._switch("MI")
        self.entry.refresh_from_db()
        self.assertIsNone(self.entry.last_done_mi)

    def test_switch_km_to_mi_then_mark_done_with_mi(self):
        self._switch("MI")
        self.client.patch(
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/entries/{self.entry.id}/",
            {"last_done_km": 60000, "last_done_mi": 37282},
            format="json",
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 60000)
        self.assertEqual(self.entry.last_done_mi, 37282)
        self.assertEqual(self.entry.next_due_mi, 43282)

    def test_switch_km_to_mi_then_set_every_mi(self):
        self._switch("MI")
        self.client.patch(
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/entries/{self.entry.id}/",
            {"every_mi": 7000},
            format="json",
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.effective_every_mi, 7000)

    def test_switch_persists_to_db(self):
        self._switch("MI")
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.distance_unit, "MI")


class MiToKmSwitchTest(TestCase):
    """Start with MI vehicle, switch to KM after assign."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="mi@test.com", username="miuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(
            distance_unit="MI", vin_number="MIVIN00000000001", car_number="MI0001AA",
        )
        self.schema = make_schema(title="MI→KM Schema", user=self.user)
        self.item = make_item(
            self.schema, title="Brake Pads", every_km=16000,
            every_mi=10000,
        )
        self.client.post(
            f"/api/v1/fleet/regulation/{self.vehicle.id}/assign/",
            {"schema_id": self.schema.id, "entries": [
                {"item_id": self.item.id, "last_done_km": 161000, "last_done_mi": 100000},
            ]},
            format="json",
        )
        self.entry = FleetVehicleRegulationEntry.objects.first()

    def _switch(self, unit):
        self.vehicle.distance_unit = unit
        self.vehicle.save(update_fields=["distance_unit"])

    def test_switch_mi_to_km_km_fields_unchanged(self):
        self._switch("KM")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 161000)
        self.assertEqual(self.entry.next_due_km, 177000)

    def test_switch_mi_to_km_mi_fields_preserved(self):
        self._switch("KM")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_mi, 100000)

    def test_switch_mi_to_km_mark_done_without_mi_clears_mi(self):
        self._switch("KM")
        self.client.patch(
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/entries/{self.entry.id}/",
            {"last_done_km": 177000},
            format="json",
        )
        self.entry.refresh_from_db()
        self.assertIsNone(self.entry.last_done_mi)

    def test_double_switch_km_mi_km_preserves_data(self):
        self._switch("KM")
        self._switch("MI")
        self._switch("KM")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 161000)
        self.assertEqual(self.entry.last_done_mi, 100000)

    def test_switch_does_not_affect_other_vehicle(self):
        v2 = make_vehicle(
            distance_unit="MI", vin_number="OTHER0000000001", car_number="OT0001AA",
        )
        schema2 = make_schema(title="Other Schema", user=self.user)
        item2 = make_item(schema2, title="Other Item", every_km=5000)
        self.client.post(
            f"/api/v1/fleet/regulation/{v2.id}/assign/",
            {"schema_id": schema2.id, "entries": [
                {"item_id": item2.id, "last_done_km": 80000, "last_done_mi": 49710},
            ]},
            format="json",
        )
        self._switch("KM")
        other_entry = FleetVehicleRegulationEntry.objects.filter(
            regulation__vehicle=v2,
        ).first()
        self.assertEqual(other_entry.last_done_mi, 49710)
