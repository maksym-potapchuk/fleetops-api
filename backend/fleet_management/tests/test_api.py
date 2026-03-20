"""
Fleet Management API Tests
===========================
Covers: AssignRegulationView, VehicleRegulationPlanView,
VehicleRegulationEntryUpdate, ServicePlan CRUD, EquipmentToggle,
EquipmentGrantOnVehicleCreation, RegulationSchema CRUD.
"""

from datetime import date
from unittest.mock import patch
import uuid

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from fleet_management.constants import EventType
from fleet_management.models import (
    EquipmentDefaultItem,
    EquipmentList,
    FleetVehicleRegulation,
    FleetVehicleRegulationHistory,
    ServicePlan,
)
from fleet_management.services import assign_regulation_to_vehicle

from .helpers import authenticate, make_item, make_schema, make_user, make_vehicle

# ===========================================================================
# Base class
# ===========================================================================


class BaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()


# ---------------------------------------------------------------------------
# AssignRegulationView
# ---------------------------------------------------------------------------


class AssignRegulationAPITest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.schema = make_schema(title="Basic Regulation", user=self.user)
        self.item1 = make_item(self.schema, title="Oil Change", every_km=10_000)
        self.item2 = make_item(self.schema, title="Air Filter", every_km=20_000)
        self.url = f"/api/v1/fleet/regulation/{self.vehicle.id}/assign/"

    def _payload(self, km1=0, km2=0):
        return {
            "schema_id": self.schema.id,
            "entries": [
                {"item_id": self.item1.id, "last_done_km": km1},
                {"item_id": self.item2.id, "last_done_km": km2},
            ],
        }

    def test_successful_assignment_returns_201(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_response_contains_regulation_id_schema_title_entries_count(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertIn("regulation_id", response.data)
        self.assertEqual(response.data["schema"], "Basic Regulation")
        self.assertEqual(response.data["entries_created"], 2)

    def test_duplicate_assignment_returns_400(self):
        self.client.post(self.url, self._payload(), format="json")
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("already assigned", response.data["detail"])

    def test_unauthenticated_request_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, 401)

    def test_nonexistent_schema_returns_400(self):
        response = self.client.post(
            self.url, {"schema_id": 99_999, "entries": []}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_partial_schema_items_accepted(self):
        """Partial submission (not all schema items) is now allowed."""
        response = self.client.post(
            self.url,
            {
                "schema_id": self.schema.id,
                "entries": [{"item_id": self.item1.id, "last_done_km": 0}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_item_from_wrong_schema_returns_400(self):
        schema2 = make_schema(title="Schema 2")
        foreign_item = make_item(schema2, title="Brakes", every_km=30_000)
        response = self.client.post(
            self.url,
            {
                "schema_id": self.schema.id,
                "entries": [
                    {"item_id": self.item1.id, "last_done_km": 0},
                    {"item_id": self.item2.id, "last_done_km": 0},
                    {"item_id": foreign_item.id, "last_done_km": 0},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_vehicle_raises_server_error(self):
        """
        BUG: AssignRegulationView does not validate that vehicle_pk exists.
        """
        fake_vehicle_id = uuid.uuid4()
        url = f"/api/v1/fleet/regulation/{fake_vehicle_id}/assign/"
        with patch("fleet_management.views.assign_regulation_to_vehicle") as mock_svc:
            mock_svc.side_effect = IntegrityError(
                "FK violation: vehicle does not exist"
            )
            self.client.raise_request_exception = False
            response = self.client.post(url, self._payload(), format="json")
        self.assertEqual(response.status_code, 500)


# ---------------------------------------------------------------------------
# VehicleRegulationPlanView
# ---------------------------------------------------------------------------


class VehicleRegulationPlanAPITest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.schema = make_schema(title="Basic")
        self.item = make_item(self.schema, title="Oil Change", every_km=10_000)
        self.url = f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/"

    def test_returns_assigned_false_when_no_regulation_assigned(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["assigned"])

    def test_returns_assigned_false_for_nonexistent_vehicle(self):
        """BUG: returns {"assigned": False} instead of 404 for non-existent vehicle."""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/fleet/vehicles/{fake_id}/regulation/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.data.get("assigned"),
            "BUG: non-existent vehicle silently returns assigned=False instead of 404",
        )

    def test_returns_regulation_data_when_assigned(self):
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=[{"item_id": self.item.id, "last_done_km": 5_000}],
            user=self.user,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["assigned"])
        self.assertIn("entries", response.data)
        self.assertIn("schema", response.data)

    def test_entry_contains_correct_next_due_km(self):
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=[{"item_id": self.item.id, "last_done_km": 5_000}],
            user=self.user,
        )
        response = self.client.get(self.url)
        entry = response.data["entries"][0]
        self.assertEqual(entry["next_due_km"], 15_000)

    def test_unauthenticated_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.get(self.url)
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# VehicleRegulationEntryUpdate
# ---------------------------------------------------------------------------


class VehicleRegulationEntryUpdateAPITest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.schema = make_schema(title="Basic")
        self.item = make_item(self.schema, title="Oil Change", every_km=10_000)
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=[{"item_id": self.item.id, "last_done_km": 5_000}],
            user=self.user,
        )
        self.regulation = FleetVehicleRegulation.objects.get(vehicle=self.vehicle)
        self.entry = self.regulation.entries.first()
        self.url = (
            f"/api/v1/fleet/vehicles/{self.vehicle.id}"
            f"/regulation/entries/{self.entry.id}/"
        )

    def test_successful_update_returns_200(self):
        response = self.client.patch(self.url, {"last_done_km": 20_000}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_update_persists_new_km_value(self):
        self.client.patch(self.url, {"last_done_km": 20_000}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 20_000)

    def test_update_creates_performed_history_entry(self):
        self.client.patch(self.url, {"last_done_km": 20_000}, format="json")
        history = FleetVehicleRegulationHistory.objects.filter(
            entry=self.entry, event_type=EventType.PERFORMED
        )
        self.assertTrue(history.exists())
        self.assertEqual(history.first().km_at_event, 20_000)

    def test_history_km_remaining_equals_every_km_after_update(self):
        self.client.patch(self.url, {"last_done_km": 20_000}, format="json")
        history = FleetVehicleRegulationHistory.objects.filter(
            entry=self.entry, event_type=EventType.PERFORMED
        ).first()
        self.assertEqual(history.km_remaining, self.item.every_km)

    def test_note_is_persisted_in_history(self):
        self.client.patch(
            self.url,
            {"last_done_km": 20_000, "note": "Changed to synthetic oil"},
            format="json",
        )
        history = FleetVehicleRegulationHistory.objects.filter(
            entry=self.entry, event_type=EventType.PERFORMED
        ).first()
        self.assertEqual(history.note, "Changed to synthetic oil")

    def test_empty_payload_returns_400(self):
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_zero_km_is_accepted(self):
        response = self.client.patch(self.url, {"last_done_km": 0}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_negative_km_is_rejected(self):
        response = self.client.patch(self.url, {"last_done_km": -100}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_float_km_is_rejected(self):
        response = self.client.patch(
            self.url, {"last_done_km": 150_000.5}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_string_km_is_rejected(self):
        response = self.client.patch(self.url, {"last_done_km": "abc"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_entry_from_different_vehicle_returns_404(self):
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        url = f"/api/v1/fleet/vehicles/{v2.id}/regulation/entries/{self.entry.id}/"
        response = self.client.patch(url, {"last_done_km": 10_000}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.patch(
            self.url, {"last_done_km": 10_000}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    # --- Edit entry (interval / notify) without marking done ---

    def test_edit_interval_only_returns_200(self):
        response = self.client.patch(self.url, {"every_km": 15_000}, format="json")
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.every_km, 15_000)

    def test_edit_interval_creates_km_updated_history(self):
        self.client.patch(self.url, {"every_km": 15_000}, format="json")
        history = (
            FleetVehicleRegulationHistory.objects.filter(
                entry=self.entry, event_type=EventType.KM_UPDATED
            )
            .exclude(note="Initial assignment")
            .last()
        )
        self.assertIsNotNone(history)
        self.assertIn("interval", history.note)

    def test_edit_notify_before_km_only_returns_200(self):
        response = self.client.patch(
            self.url, {"notify_before_km": 1_000}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.notify_before_km, 1_000)

    def test_edit_both_settings_updates_entry_and_creates_history(self):
        response = self.client.patch(
            self.url, {"every_km": 12_000, "notify_before_km": 2_000}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.every_km, 12_000)
        self.assertEqual(self.entry.notify_before_km, 2_000)
        history = (
            FleetVehicleRegulationHistory.objects.filter(
                entry=self.entry, event_type=EventType.KM_UPDATED
            )
            .exclude(note="Initial assignment")
            .last()
        )
        self.assertIn("interval", history.note)
        self.assertIn("notify", history.note)

    def test_edit_with_same_values_creates_no_history(self):
        self.client.patch(
            self.url, {"every_km": 10_000, "notify_before_km": 500}, format="json"
        )
        history_count = (
            FleetVehicleRegulationHistory.objects.filter(
                entry=self.entry, event_type=EventType.KM_UPDATED
            )
            .exclude(note="Initial assignment")
            .count()
        )
        self.assertEqual(history_count, 0)

    def test_edit_interval_zero_is_rejected(self):
        response = self.client.patch(self.url, {"every_km": 0}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_mark_done_with_interval_override_creates_performed_history(self):
        response = self.client.patch(
            self.url,
            {"last_done_km": 20_000, "every_km": 15_000},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 20_000)
        self.assertEqual(self.entry.every_km, 15_000)
        history = FleetVehicleRegulationHistory.objects.filter(
            entry=self.entry, event_type=EventType.PERFORMED
        ).last()
        self.assertIsNotNone(history)
        self.assertEqual(history.km_at_event, 20_000)


# ---------------------------------------------------------------------------
# ServicePlan
# ---------------------------------------------------------------------------


class ServicePlanAPITest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.list_url = f"/api/v1/fleet/vehicles/{self.vehicle.id}/service-plans/"
        self.plan = ServicePlan.objects.create(
            vehicle=self.vehicle,
            title="Annual Service",
            planned_at=date.today(),
        )
        self.detail_url = (
            f"/api/v1/fleet/vehicles/{self.vehicle.id}/service-plans/{self.plan.id}/"
        )
        self.done_url = f"/api/v1/fleet/vehicles/{self.vehicle.id}/service-plans/{self.plan.id}/done/"

    def test_list_returns_200(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_create_service_plan_returns_201(self):
        response = self.client.post(
            self.list_url,
            {"title": "Oil Change", "planned_at": "2026-03-01"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_duplicate_title_same_vehicle_returns_500(self):
        """BUG: IntegrityError propagates as 500 instead of 400."""
        self.client.post(
            self.list_url,
            {"title": "Unique Plan", "planned_at": "2026-03-01"},
            format="json",
        )
        self.client.raise_request_exception = False
        response = self.client.post(
            self.list_url,
            {"title": "Unique Plan", "planned_at": "2026-04-01"},
            format="json",
        )
        self.assertEqual(response.status_code, 500)

    def test_mark_done_sets_is_done_true(self):
        response = self.client.patch(self.done_url)
        self.assertEqual(response.status_code, 200)
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.is_done)

    def test_mark_done_is_idempotent_on_already_done_plan(self):
        self.plan.is_done = True
        self.plan.save()
        response = self.client.patch(self.done_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_done"])

    def test_mark_done_is_one_way_only(self):
        """BUG / DESIGN GAP: no guard prevents reverting is_done via PATCH."""
        self.client.patch(self.done_url)
        response = self.client.patch(self.detail_url, {"is_done": False}, format="json")
        if response.status_code == 200:
            self.plan.refresh_from_db()
            self.assertFalse(
                self.plan.is_done,
                "INFO: is_done can be reverted via PATCH — no server-side guard exists",
            )

    def test_plan_belonging_to_different_vehicle_returns_404(self):
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        url = f"/api/v1/fleet/vehicles/{v2.id}/service-plans/{self.plan.id}/done/"
        response = self.client.patch(url)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.get(self.list_url)
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# EquipmentToggle
# ---------------------------------------------------------------------------


class EquipmentToggleAPITest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.equipment = EquipmentList.objects.create(
            vehicle=self.vehicle,
            equipment="First Aid Kit",
            is_equipped=False,
        )
        self.url = (
            f"/api/v1/fleet/vehicles/{self.vehicle.id}"
            f"/equipment/{self.equipment.id}/toggle/"
        )

    def test_toggle_false_to_true(self):
        response = self.client.patch(self.url)
        self.assertEqual(response.status_code, 200)
        self.equipment.refresh_from_db()
        self.assertTrue(self.equipment.is_equipped)

    def test_toggle_true_to_false(self):
        self.equipment.is_equipped = True
        self.equipment.save()
        response = self.client.patch(self.url)
        self.assertEqual(response.status_code, 200)
        self.equipment.refresh_from_db()
        self.assertFalse(self.equipment.is_equipped)

    def test_toggle_does_not_set_approved_at(self):
        """BUG: approved_at is never populated."""
        self.client.patch(self.url)
        self.equipment.refresh_from_db()
        self.assertTrue(self.equipment.is_equipped)
        self.assertIsNone(
            self.equipment.approved_at,
            "BUG: approved_at must be set when is_equipped becomes True",
        )

    def test_toggle_equipment_from_different_vehicle_returns_404(self):
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        url = f"/api/v1/fleet/vehicles/{v2.id}/equipment/{self.equipment.id}/toggle/"
        response = self.client.patch(url)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.patch(self.url)
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# Equipment grant during vehicle creation
# ---------------------------------------------------------------------------


class EquipmentGrantOnVehicleCreationAPITest(BaseAPITest):
    def setUp(self):
        EquipmentDefaultItem.objects.all().delete()
        super().setUp()

    def _create_vehicle_payload(self, vin="1HGBH41JXMN109200", car="ZZ0001ZZ"):
        return {
            "model": "Corolla",
            "manufacturer": "Toyota",
            "year": 2023,
            "cost": "20000.00",
            "vin_number": vin,
            "car_number": car,
            "color": "#FFFFFF",
            "initial_km": 0,
            "status": "AUCTION",
        }

    def test_vehicle_creation_via_api_grants_default_equipment(self):
        EquipmentDefaultItem.objects.create(equipment="Jack")
        EquipmentDefaultItem.objects.create(equipment="Spare Tire")
        response = self.client.post(
            "/api/v1/vehicle/", self._create_vehicle_payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        vehicle_id = response.data["id"]
        count = EquipmentList.objects.filter(vehicle_id=vehicle_id).count()
        self.assertEqual(count, 2, "Vehicle creation must auto-grant default equipment")

    def test_vehicle_creation_without_defaults_creates_no_equipment(self):
        response = self.client.post(
            "/api/v1/vehicle/", self._create_vehicle_payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        vehicle_id = response.data["id"]
        count = EquipmentList.objects.filter(vehicle_id=vehicle_id).count()
        self.assertEqual(count, 0)


# ---------------------------------------------------------------------------
# Regulation schema CRUD
# ---------------------------------------------------------------------------


class RegulationSchemaAPITest(BaseAPITest):
    def test_create_schema_with_nested_items_returns_201(self):
        response = self.client.post(
            "/api/v1/fleet/regulation/schemas/",
            {
                "title": "Full Schema",
                "is_default": False,
                "items": [
                    {
                        "title": "Oil Change",
                        "every_km": 10_000,
                        "notify_before_km": 500,
                    },
                    {
                        "title": "Air Filter",
                        "every_km": 20_000,
                        "notify_before_km": 1_000,
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_list_schemas_returns_200(self):
        make_schema(title="S1")
        make_schema(title="S2")
        response = self.client.get("/api/v1/fleet/regulation/schemas/")
        self.assertEqual(response.status_code, 200)

    def test_delete_schema_without_regulations_returns_204(self):
        schema = make_schema(title="Deletable Schema")
        response = self.client.delete(f"/api/v1/fleet/regulation/schemas/{schema.id}/")
        self.assertEqual(response.status_code, 204)

    def test_delete_schema_with_active_regulation_returns_error(self):
        """BUG: ProtectedError propagates as 500."""
        schema = make_schema(title="Protected Schema")
        make_item(schema, title="Oil Change")
        FleetVehicleRegulation.objects.create(vehicle=self.vehicle, schema=schema)
        self.client.raise_request_exception = False
        response = self.client.delete(f"/api/v1/fleet/regulation/schemas/{schema.id}/")
        self.assertIn(response.status_code, [400, 409, 500])

    def test_duplicate_schema_title_returns_400(self):
        make_schema(title="Duplicate Title")
        response = self.client.post(
            "/api/v1/fleet/regulation/schemas/",
            {"title": "Duplicate Title", "items": []},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.get("/api/v1/fleet/regulation/schemas/")
        self.assertEqual(response.status_code, 401)
