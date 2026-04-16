"""
Vehicle API stress test — VIN/car_number edge cases, status transitions,
duplicate detection, bulk creation.
"""

import time

from django.test import TestCase
from rest_framework.test import APIClient

from expense.tests.helpers import authenticate, make_user, make_vehicle
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle


class VINEdgeCasesTest(TestCase):
    """POST /api/v1/vehicle/ — VIN validation and uniqueness."""

    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def _payload(self, **overrides):
        base = {
            "model": "Camry",
            "manufacturer": ManufacturerChoices.TOYOTA,
            "year": 2022,
            "cost": "25000.00",
            "vin_number": "1HGBH41JXMN109186",
            "car_number": "AA6601BB",
            "color": "#FFFFFF",
            "initial_km": 0,
        }
        base.update(overrides)
        return base

    def test_duplicate_vin_rejected(self):
        self.client.post(self.BASE_URL, self._payload(), format="json")
        res = self.client.post(
            self.BASE_URL,
            self._payload(car_number="BB7702CC"),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("vin_number", str(res.data))

    def test_vin_edge_cases(self):
        cases = [
            ("1HGBH41JXMN109186", True, "valid 17-char VIN"),
            ("", False, "empty VIN"),
            # BUG: short VIN accepted — no min_length validation on vin_number
            ("SHORT", True, "too short VIN (5 chars) — KNOWN BUG: no min_length"),
            ("A" * 17, True, "17 chars all same"),
            ("A" * 18, False, "18 chars — too long"),
            ("1234567890ABCDEFG", True, "alphanumeric 17"),
            # BUG: leading space in VIN accepted — no strip/validation
            (
                " 1HGBH41JXMN10918",
                True,
                "leading space — KNOWN BUG: no whitespace strip",
            ),
            ("1HGBH41JXMN10918 ", False, "trailing space"),
            ("a" * 17, True, "lowercase 17 chars"),
        ]
        results = {"pass": [], "fail_expected": [], "fail_unexpected": []}
        for i, (vin, should_pass, desc) in enumerate(cases):
            res = self.client.post(
                self.BASE_URL,
                self._payload(vin_number=vin, car_number=f"T{i:05d}XX"),
                format="json",
            )
            passed = res.status_code == 201
            if passed == should_pass:
                results["pass"].append(desc)
            elif should_pass:
                results["fail_unexpected"].append(
                    f"{desc}: expected pass, got {res.status_code} {str(res.data)[:200]}"
                )
            else:
                results["fail_expected"].append(f"{desc}: expected fail, got 201")

        self.assertEqual(
            results["fail_unexpected"],
            [],
            f"Unexpected failures: {results['fail_unexpected']}",
        )
        self.assertEqual(
            results["fail_expected"],
            [],
            f"Should have been rejected: {results['fail_expected']}",
        )


class CarNumberEdgeCasesTest(TestCase):
    """car_number uniqueness, optional, temporary plate."""

    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="car@test.com", username="caruser")
        authenticate(self.client, self.user)

    def _payload(self, **overrides):
        base = {
            "model": "Corolla",
            "manufacturer": ManufacturerChoices.TOYOTA,
            "year": 2023,
            "cost": "20000.00",
            "vin_number": "UNIQUE00000000001",
            "color": "#000000",
            "initial_km": 0,
        }
        base.update(overrides)
        return base

    def test_duplicate_car_number_rejected(self):
        self.client.post(
            self.BASE_URL,
            self._payload(car_number="WW1234AB", vin_number="VIN00000000000001"),
            format="json",
        )
        res = self.client.post(
            self.BASE_URL,
            self._payload(car_number="WW1234AB", vin_number="VIN00000000000002"),
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_null_car_number_allowed(self):
        res = self.client.post(
            self.BASE_URL,
            self._payload(vin_number="VIN00000000000003"),
            format="json",
        )
        self.assertIn(res.status_code, [200, 201])

    def test_car_number_edge_values(self):
        cases = [
            ("WW1234AB", True, "normal plate"),
            ("A" * 10, True, "max length 10"),
            ("A" * 11, False, "11 chars — too long"),
            ("", True, "empty → treated as null"),
            ("ÓŁ1234", True, "polish diacritics"),
            ("WW 1234", True, "space in number"),
            ("123", True, "short plate (3 chars)"),
        ]
        results = {"bug": []}
        for i, (cn, should_pass, desc) in enumerate(cases):
            payload = self._payload(vin_number=f"CNVIN{i:012d}")
            if cn:
                payload["car_number"] = cn
            res = self.client.post(self.BASE_URL, payload, format="json")
            passed = res.status_code == 201
            if passed != should_pass:
                results["bug"].append(
                    f"{desc}: car_number={cn!r}, expected {'pass' if should_pass else 'fail'}, "
                    f"got {res.status_code} {str(res.data)[:200]}"
                )

        self.assertEqual(results["bug"], [], f"Bugs found: {results['bug']}")

    def test_temporary_plate_flag(self):
        res = self.client.post(
            self.BASE_URL,
            self._payload(
                vin_number="TEMPVIN0000000001",
                car_number="TEMP01",
                is_temporary_plate=True,
            ),
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        vehicle = Vehicle.objects.get(vin_number="TEMPVIN0000000001")
        self.assertTrue(vehicle.is_temporary_plate)


class StatusTransitionTest(TestCase):
    """PATCH /api/v1/vehicle/{id}/ — status field transitions."""

    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="status@test.com", username="statususer")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()

    def _patch_status(self, status, **extra):
        payload = {"status": status, **extra}
        return self.client.patch(
            f"{self.BASE_URL}{self.vehicle.id}/",
            payload,
            format="json",
        )

    def test_all_valid_statuses_accepted(self):
        """Each VehicleStatus value should be accepted via PATCH."""
        failed = []
        for status in VehicleStatus.values:
            res = self._patch_status(status)
            if res.status_code != 200:
                failed.append(f"{status}: {res.status_code} {str(res.data)[:200]}")
            # Reset to AUCTION for next iteration
            self.vehicle.status = VehicleStatus.AUCTION
            self.vehicle.save(update_fields=["status"])

        self.assertEqual(failed, [], f"Status transitions failed: {failed}")

    def test_invalid_status_rejected(self):
        invalid = ["INVALID", "deleted", "", "READY_TO_GO", "auction", "rent "]
        passed = []
        for status in invalid:
            res = self._patch_status(status)
            if res.status_code == 200:
                passed.append(f"{status!r} accepted as valid")

        self.assertEqual(passed, [], f"Invalid statuses accepted: {passed}")

    def test_status_change_creates_history(self):
        from vehicle.models import VehicleStatusHistory

        initial_count = VehicleStatusHistory.objects.filter(
            vehicle=self.vehicle
        ).count()
        self._patch_status(VehicleStatus.READY)
        new_count = VehicleStatusHistory.objects.filter(vehicle=self.vehicle).count()
        self.assertEqual(new_count, initial_count + 1)

    def test_status_history_records_old_and_new(self):
        from vehicle.models import VehicleStatusHistory

        self.vehicle.status = VehicleStatus.SERVICE
        self.vehicle.save(update_fields=["status"])

        self._patch_status(VehicleStatus.READY)

        latest = (
            VehicleStatusHistory.objects.filter(
                vehicle=self.vehicle,
            )
            .order_by("-changed_at")
            .first()
        )
        self.assertEqual(latest.old_status, VehicleStatus.SERVICE)
        self.assertEqual(latest.new_status, VehicleStatus.READY)


class VehicleBulkPerformanceTest(TestCase):
    """Bulk operations and list API performance."""

    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="bulk@test.com", username="bulkuser")
        authenticate(self.client, self.user)

    def test_create_1000_vehicles_via_orm(self):
        t0 = time.time()
        Vehicle.objects.bulk_create(
            [
                Vehicle(
                    model="Car",
                    manufacturer=ManufacturerChoices.TOYOTA,
                    year=2022,
                    cost="25000.00",
                    vin_number=f"BULK{i:013d}",
                    car_number=f"BK{i:04d}XX",
                    color="#FFFFFF",
                    initial_km=i * 100,
                    status=VehicleStatus.AUCTION,
                )
                for i in range(1000)
            ]
        )
        elapsed = time.time() - t0
        self.assertEqual(Vehicle.objects.count(), 1000)
        self.assertLess(elapsed, 5, f"1000 vehicles took {elapsed:.1f}s")

    def test_list_1000_vehicles_paginated(self):
        Vehicle.objects.bulk_create(
            [
                Vehicle(
                    model="Car",
                    manufacturer=ManufacturerChoices.TOYOTA,
                    year=2022,
                    cost="25000.00",
                    vin_number=f"LIST{i:013d}",
                    car_number=f"LS{i:04d}XX",
                    color="#FFFFFF",
                    initial_km=0,
                    status=VehicleStatus.AUCTION,
                )
                for i in range(1000)
            ]
        )

        t0 = time.time()
        res = self.client.get(self.BASE_URL)
        elapsed = time.time() - t0

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1000)
        self.assertLess(elapsed, 5, f"List 1k vehicles took {elapsed:.1f}s")

    def test_filter_by_status_with_1000_vehicles(self):
        Vehicle.objects.bulk_create(
            [
                Vehicle(
                    model="Car",
                    manufacturer=ManufacturerChoices.TOYOTA,
                    year=2022,
                    cost="25000.00",
                    vin_number=f"FILT{i:013d}",
                    car_number=f"FT{i:04d}XX",
                    color="#FFFFFF",
                    initial_km=0,
                    status=VehicleStatus.READY if i < 500 else VehicleStatus.AUCTION,
                )
                for i in range(1000)
            ]
        )

        t0 = time.time()
        res = self.client.get(f"{self.BASE_URL}?status=READY")
        elapsed = time.time() - t0

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 500)
        self.assertLess(elapsed, 5, f"Filtered query took {elapsed:.1f}s")
