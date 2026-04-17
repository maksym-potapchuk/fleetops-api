"""
Regulation Event Type Tests
============================
Covers: mark-done creates PERFORMED event, edit creates EDITED event,
settings-only edit creates KM_UPDATED event.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from fleet_management.constants import EventType
from fleet_management.models import (
    FleetVehicleRegulation,
    FleetVehicleRegulationHistory,
)
from fleet_management.services import assign_regulation_to_vehicle

from .helpers import authenticate, make_item, make_schema, make_user, make_vehicle


class EventTypeBaseTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.schema = make_schema(title="Test Schema", user=self.user)
        self.item = make_item(self.schema, title="Oil Change", every_km=10_000)
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=[{"item_id": self.item.id, "last_done_km": 50_000}],
            user=self.user,
        )
        self.regulation = FleetVehicleRegulation.objects.get(vehicle=self.vehicle)
        self.entry = self.regulation.entries.first()
        self.url = (
            f"/api/v1/fleet/vehicles/{self.vehicle.id}"
            f"/regulation/entries/{self.entry.id}/"
        )


class MarkDoneCreatesPerformedEventTest(EventTypeBaseTest):
    def test_mark_done_creates_performed_event(self):
        resp = self.client.patch(
            self.url,
            {"last_done_km": 60000},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        event = (
            FleetVehicleRegulationHistory.objects.filter(entry=self.entry)
            .order_by("-created_at")
            .first()
        )
        self.assertEqual(event.event_type, EventType.PERFORMED)
        self.assertEqual(event.km_at_event, 60000)


class EditCreatesEditedEventTest(EventTypeBaseTest):
    def test_edit_with_action_flag_creates_edited_event(self):
        resp = self.client.patch(
            self.url,
            {"last_done_km": 55000, "action": "edit"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        event = (
            FleetVehicleRegulationHistory.objects.filter(entry=self.entry)
            .order_by("-created_at")
            .first()
        )
        self.assertEqual(event.event_type, EventType.EDITED)
        self.assertEqual(event.km_at_event, 55000)


class EditWithoutKmCreatesKmUpdatedTest(EventTypeBaseTest):
    def test_settings_only_edit_creates_km_updated_event(self):
        resp = self.client.patch(
            self.url,
            {"every_km": 15000},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        event = (
            FleetVehicleRegulationHistory.objects.filter(
                entry=self.entry,
                event_type=EventType.KM_UPDATED,
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(event)
        self.assertIn("interval", event.note)


class EditWithActionAndSettingsCreatesEditedTest(EventTypeBaseTest):
    def test_edit_km_and_interval_together_creates_edited(self):
        resp = self.client.patch(
            self.url,
            {"last_done_km": 52000, "every_km": 12000, "action": "edit"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        events = FleetVehicleRegulationHistory.objects.filter(
            entry=self.entry
        ).order_by("-created_at")
        latest = events[0]
        self.assertEqual(latest.event_type, EventType.EDITED)


class MarkDoneWithoutActionFlagStaysPerformedTest(EventTypeBaseTest):
    def test_no_action_flag_defaults_to_performed(self):
        resp = self.client.patch(
            self.url,
            {"last_done_km": 60000},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        event = (
            FleetVehicleRegulationHistory.objects.filter(entry=self.entry)
            .order_by("-created_at")
            .first()
        )
        self.assertEqual(event.event_type, EventType.PERFORMED)
