"""
Regulation Entry Calculation Tests
===================================
Covers: next_due_km precision with non-standard numbers, effective overrides,
interval edit recalculation, override behavior, mark-done cycles,
and integer storage fidelity through the API.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from fleet_management.constants import EventType
from fleet_management.models import (
    FleetVehicleRegulation,
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationHistory,
)
from fleet_management.services import assign_regulation_to_vehicle

from .helpers import authenticate, make_item, make_schema, make_user, make_vehicle


class RegulationCalcBaseTest(TestCase):
    """Shared setup: vehicle + schema + item + assigned regulation."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.schema = make_schema(title="Test Schema", user=self.user)
        self.item = make_item(self.schema, title="Oil Change", every_km=10_000)

    def _assign(self, last_done_km=0, **entry_kwargs):
        entry_data = {"item_id": self.item.id, "last_done_km": last_done_km}
        entry_data.update(entry_kwargs)
        assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=[entry_data],
            user=self.user,
        )
        self.regulation = FleetVehicleRegulation.objects.get(vehicle=self.vehicle)
        self.entry = self.regulation.entries.first()
        self.url = (
            f"/api/v1/fleet/vehicles/{self.vehicle.id}"
            f"/regulation/entries/{self.entry.id}/"
        )
        return self.entry


# ---------------------------------------------------------------------------
# next_due_km with non-standard numbers
# ---------------------------------------------------------------------------


class NextDueKmNonStandardTest(RegulationCalcBaseTest):
    """Exact integer arithmetic: last_done + every_km, no rounding."""

    def test_256980_plus_10000_equals_266980(self):
        """The exact reported bug scenario."""
        entry = self._assign(last_done_km=256_980)
        self.assertEqual(entry.next_due_km, 266_980)

    def test_13579_plus_10000(self):
        entry = self._assign(last_done_km=13_579)
        self.assertEqual(entry.next_due_km, 23_579)

    def test_77777_plus_10000(self):
        entry = self._assign(last_done_km=77_777)
        self.assertEqual(entry.next_due_km, 87_777)

    def test_100001_plus_10000(self):
        entry = self._assign(last_done_km=100_001)
        self.assertEqual(entry.next_due_km, 110_001)

    def test_999999_plus_10000(self):
        entry = self._assign(last_done_km=999_999)
        self.assertEqual(entry.next_due_km, 1_009_999)

    def test_314159_plus_10000(self):
        entry = self._assign(last_done_km=314_159)
        self.assertEqual(entry.next_due_km, 324_159)

    def test_1_plus_10000(self):
        entry = self._assign(last_done_km=1)
        self.assertEqual(entry.next_due_km, 10_001)

    def test_500001_plus_10000(self):
        entry = self._assign(last_done_km=500_001)
        self.assertEqual(entry.next_due_km, 510_001)


# ---------------------------------------------------------------------------
# Interval edit with non-standard numbers
# ---------------------------------------------------------------------------


class IntervalEditNonStandardTest(RegulationCalcBaseTest):
    """Changing every_km must recalculate next_due_km exactly."""

    def test_256980_interval_changed_to_7500(self):
        self._assign(last_done_km=256_980)
        response = self.client.patch(self.url, {"every_km": 7_500}, format="json")
        self.assertEqual(response.data["next_due_km"], 264_480)

    def test_256980_interval_changed_to_13579(self):
        self._assign(last_done_km=256_980)
        response = self.client.patch(self.url, {"every_km": 13_579}, format="json")
        self.assertEqual(response.data["next_due_km"], 270_559)

    def test_77777_interval_changed_to_33333(self):
        self._assign(last_done_km=77_777)
        response = self.client.patch(self.url, {"every_km": 33_333}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 111_110)
        self.assertEqual(response.data["next_due_km"], 111_110)

    def test_edit_interval_preserves_last_done_exactly(self):
        """Changing interval must NOT touch last_done_km."""
        self._assign(last_done_km=256_980)
        self.client.patch(self.url, {"every_km": 15_000}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 256_980)
        self.assertEqual(self.entry.next_due_km, 271_980)

    def test_edit_interval_from_10k_to_1(self):
        self._assign(last_done_km=50_000)
        self.client.patch(self.url, {"every_km": 1}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 50_001)

    def test_edit_interval_to_99999(self):
        self._assign(last_done_km=100_000)
        self.client.patch(self.url, {"every_km": 99_999}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 199_999)

    def test_edit_interval_twice_recalculates(self):
        self._assign(last_done_km=256_980)
        self.client.patch(self.url, {"every_km": 15_000}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 271_980)

        self.client.patch(self.url, {"every_km": 8_000}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 264_980)

    def test_edit_creates_history_with_correct_km_remaining(self):
        self._assign(last_done_km=256_980)
        self.client.patch(self.url, {"every_km": 15_000}, format="json")
        history = (
            FleetVehicleRegulationHistory.objects.filter(
                entry=self.entry, event_type=EventType.KM_UPDATED
            )
            .exclude(note="Initial assignment")
            .last()
        )
        self.assertIsNotNone(history)
        # km_remaining = 271980 - 256980 = 15000
        self.assertEqual(history.km_remaining, 15_000)


# ---------------------------------------------------------------------------
# Mark-done with non-standard numbers
# ---------------------------------------------------------------------------


class MarkDoneNonStandardTest(RegulationCalcBaseTest):
    def test_mark_done_at_256980(self):
        self._assign(last_done_km=246_980)
        self.client.patch(self.url, {"last_done_km": 256_980}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 256_980)
        self.assertEqual(self.entry.next_due_km, 266_980)

    def test_mark_done_at_13579(self):
        self._assign(last_done_km=0)
        self.client.patch(self.url, {"last_done_km": 13_579}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 13_579)
        self.assertEqual(self.entry.next_due_km, 23_579)

    def test_mark_done_at_77777_with_interval_change(self):
        self._assign(last_done_km=0)
        self.client.patch(
            self.url, {"last_done_km": 77_777, "every_km": 33_333}, format="json"
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 111_110)

    def test_mark_done_at_999999(self):
        self._assign(last_done_km=0)
        self.client.patch(self.url, {"last_done_km": 999_999}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 999_999)
        self.assertEqual(self.entry.next_due_km, 1_009_999)

    def test_consecutive_mark_done_no_drift(self):
        """Simulate 5 mark-dones — values must stay exact."""
        self._assign(last_done_km=0)
        steps = [13_579, 23_579, 33_579, 43_579, 53_579]
        for km in steps:
            self.client.patch(self.url, {"last_done_km": km}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 53_579)
        self.assertEqual(self.entry.next_due_km, 63_579)


# ---------------------------------------------------------------------------
# Override with non-standard numbers
# ---------------------------------------------------------------------------


class OverrideNonStandardTest(RegulationCalcBaseTest):
    def test_override_256980_stored_exactly(self):
        self._assign(last_done_km=250_000)
        self.client.patch(self.url, {"next_due_km_override": 256_980}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 256_980)

    def test_override_13579_stored_exactly(self):
        self._assign(last_done_km=10_000)
        self.client.patch(self.url, {"next_due_km_override": 13_579}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 13_579)

    def test_override_cleared_after_mark_done_recalculates(self):
        self._assign(last_done_km=250_000, next_due_km_override=256_980)
        self.assertEqual(self.entry.next_due_km, 256_980)

        self.client.patch(self.url, {"last_done_km": 256_980}, format="json")
        self.entry.refresh_from_db()
        self.assertIsNone(self.entry.next_due_km_override)
        self.assertEqual(self.entry.next_due_km, 266_980)

    def test_override_777777(self):
        self._assign(last_done_km=0)
        self.client.patch(self.url, {"next_due_km_override": 777_777}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_km, 777_777)


# ---------------------------------------------------------------------------
# Vehicle-level effective overrides
# ---------------------------------------------------------------------------


class EffectiveOverrideNonStandardTest(RegulationCalcBaseTest):
    def test_every_km_override_13579(self):
        entry = self._assign(last_done_km=100_000, every_km=13_579)
        self.assertEqual(entry.effective_every_km, 13_579)
        self.assertEqual(entry.next_due_km, 113_579)

    def test_notify_override_1234(self):
        entry = self._assign(last_done_km=0, notify_before_km=1_234)
        self.assertEqual(entry.effective_notify_before_km, 1_234)

    def test_no_override_falls_back_to_item(self):
        entry = self._assign(last_done_km=0)
        self.assertEqual(entry.effective_every_km, 10_000)
        self.assertEqual(entry.effective_notify_before_km, 500)


# ---------------------------------------------------------------------------
# API response precision
# ---------------------------------------------------------------------------


class APIPrecisionNonStandardTest(RegulationCalcBaseTest):
    def test_plan_response_256980(self):
        self._assign(last_done_km=256_980)
        url = f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/"
        response = self.client.get(url)
        entry = response.data["entries"][0]
        self.assertEqual(entry["last_done_km"], 256_980)
        self.assertEqual(entry["next_due_km"], 266_980)

    def test_plan_response_after_edit_13579_interval(self):
        self._assign(last_done_km=256_980)
        self.client.patch(self.url, {"every_km": 13_579}, format="json")
        url = f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/"
        response = self.client.get(url)
        entry = response.data["entries"][0]
        self.assertEqual(entry["next_due_km"], 270_559)
        self.assertEqual(entry["effective_every_km"], 13_579)

    def test_entry_update_response_matches_db(self):
        self._assign(last_done_km=77_777)
        response = self.client.patch(self.url, {"every_km": 33_333}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(response.data["next_due_km"], self.entry.next_due_km)
        self.assertEqual(response.data["next_due_km"], 111_110)

    def test_integer_stored_exactly_not_rounded(self):
        """PositiveIntegerField stores exact values — no float rounding."""
        self._assign(last_done_km=0)
        self.client.patch(self.url, {"last_done_km": 314_159}, format="json")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 314_159)
        self.assertEqual(self.entry.next_due_km, 324_159)


# ---------------------------------------------------------------------------
# last_done_mi display-only field (vehicle in miles)
# ---------------------------------------------------------------------------


class LastDoneMiDisplayTest(RegulationCalcBaseTest):
    """last_done_mi stores user's mi input to avoid km↔mi rounding drift."""

    def test_mark_done_with_mi_stores_both(self):
        self._assign(last_done_km=0)
        self.client.patch(
            self.url,
            {"last_done_km": 413_247, "last_done_mi": 256_780},
            format="json",
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.last_done_km, 413_247)
        self.assertEqual(self.entry.last_done_mi, 256_780)

    def test_mark_done_without_mi_clears_it(self):
        """When km-unit vehicle marks done, last_done_mi should be null."""
        self._assign(last_done_km=0)
        self.client.patch(self.url, {"last_done_km": 256_980}, format="json")
        self.entry.refresh_from_db()
        self.assertIsNone(self.entry.last_done_mi)

    def test_mi_value_256780_survives_round_trip(self):
        """User enters 256780 mi → API returns last_done_mi=256780 (no drift)."""
        self._assign(last_done_km=0)
        response = self.client.patch(
            self.url,
            {"last_done_km": 413_247, "last_done_mi": 256_780},
            format="json",
        )
        self.assertEqual(response.data["last_done_mi"], 256_780)

    def test_next_due_mi_computed_from_mi_fields(self):
        """next_due_mi = last_done_mi + effective_every_mi."""
        self._assign(last_done_km=0)
        # Set every_mi on the entry
        self.client.patch(
            self.url,
            {
                "last_done_km": 413_247,
                "last_done_mi": 256_780,
                "every_km": 20_000,
                "every_mi": 12_427,
            },
            format="json",
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_mi, 256_780 + 12_427)

    def test_next_due_mi_is_none_without_every_mi(self):
        """When every_mi is not set, next_due_mi falls back to None."""
        self._assign(last_done_km=0)
        self.client.patch(
            self.url,
            {"last_done_km": 100_000, "last_done_mi": 62_137},
            format="json",
        )
        self.entry.refresh_from_db()
        self.assertIsNone(self.entry.next_due_mi)

    def test_plan_response_includes_mi_fields(self):
        self._assign(last_done_km=0)
        self.client.patch(
            self.url,
            {
                "last_done_km": 413_247,
                "last_done_mi": 256_780,
                "every_km": 20_000,
                "every_mi": 12_427,
            },
            format="json",
        )
        url = f"/api/v1/fleet/vehicles/{self.vehicle.id}/regulation/"
        response = self.client.get(url)
        entry = response.data["entries"][0]
        self.assertEqual(entry["last_done_mi"], 256_780)
        self.assertEqual(entry["next_due_mi"], 256_780 + 12_427)

    def test_assign_with_last_done_mi(self):
        """assign_regulation_to_vehicle stores last_done_mi."""
        result = assign_regulation_to_vehicle(
            vehicle_pk=self.vehicle.id,
            schema_id=self.schema.id,
            entries_data=[
                {
                    "item_id": self.item.id,
                    "last_done_km": 413_247,
                    "last_done_mi": 256_780,
                }
            ],
            user=self.user,
        )
        self.assertEqual(result["entries_created"], 1)
        entry = FleetVehicleRegulationEntry.objects.get(
            regulation__vehicle=self.vehicle
        )
        self.assertEqual(entry.last_done_mi, 256_780)

    def test_non_standard_mi_values_stored_exactly(self):
        """Various non-standard mi values stored without drift."""
        self._assign(last_done_km=0)
        test_cases = [
            (16_093, 9_999),
            (80_467, 49_999),
            (160_934, 100_000),
            (321_868, 199_999),
            (804_670, 500_000),
        ]
        for km, mi in test_cases:
            self.client.patch(
                self.url,
                {"last_done_km": km, "last_done_mi": mi},
                format="json",
            )
            self.entry.refresh_from_db()
            self.assertEqual(
                self.entry.last_done_mi, mi, f"last_done_mi={mi} not stored correctly"
            )
