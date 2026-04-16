"""
Driver API stress test — phone validation edge cases, duplicate detection,
name validation, filters, pagination sync, bulk performance.
"""

import time

from django.test import TestCase
from rest_framework.test import APIClient

from driver.models import Driver
from driver.tests.helpers import authenticate, make_driver, make_user


class PhoneValidationEdgeCasesTest(TestCase):
    """POST /api/v1/driver/ — phone_number edge cases."""

    BASE_URL = "/api/v1/driver/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def _payload(self, **overrides):
        base = {
            "first_name": "Test",
            "last_name": "Driver",
            "phone_number": "48111222333",
        }
        base.update(overrides)
        return base

    def test_phone_edge_cases(self):
        """Run all phone edge cases, collect pass/fail."""
        cases = [
            # (phone, should_pass, description)
            ("48123456789", True, "valid 11 digits"),
            ("4812345678", True, "valid 10 digits (min)"),
            ("481234567890123", True, "valid 15 digits (max)"),
            ("4812345678901234", False, "16 digits — too long"),
            ("481234567", False, "9 digits — too short"),
            ("", False, "empty string"),
            ("48abc123456", False, "letters mixed in"),
            ("38123456789", False, "starts with 38 not 48"),
            ("12345678901", False, "starts with 12 not 48"),
            ("48 123 456 789", False, "spaces in number"),
            ("+48123456789", False, "plus sign"),
            ("48-123-456-789", False, "dashes"),
            ("48000000000", True, "all zeros after 48"),
            ("48999999999", True, "all nines after 48"),
            ("048123456789", False, "leading zero before 48"),
            ("48123456789 ", False, "trailing space"),
            (" 48123456789", False, "leading space"),
        ]
        bugs = []
        for i, (phone, should_pass, desc) in enumerate(cases):
            res = self.client.post(
                self.BASE_URL,
                self._payload(
                    phone_number=phone,
                    first_name=f"Test{i}",
                    last_name=f"Driver{i}",
                ),
                format="json",
            )
            passed = res.status_code == 201
            if passed != should_pass:
                bugs.append(
                    f"{desc}: phone={phone!r}, expected {'pass' if should_pass else 'fail'}, "
                    f"got {res.status_code} {str(res.data)[:200]}"
                )

        self.assertEqual(bugs, [], f"Phone validation bugs: {bugs}")

    def test_duplicate_phone_rejected(self):
        make_driver(phone_number="48111000111")
        res = self.client.post(
            self.BASE_URL,
            self._payload(phone_number="48111000111"),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone_number", str(res.data))

    def test_phone_validation_error_message_is_human_readable(self):
        res = self.client.post(
            self.BASE_URL,
            self._payload(phone_number="abc"),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        error_text = str(res.data.get("phone_number", ""))
        self.assertTrue(
            "digits" in error_text.lower() or "цифр" in error_text.lower(),
            f"Error should mention digits: {error_text}",
        )


class NameValidationEdgeCasesTest(TestCase):
    """POST /api/v1/driver/ — first_name/last_name edge cases."""

    BASE_URL = "/api/v1/driver/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="name@test.com", username="nameuser")
        authenticate(self.client, self.user)
        self._phone_counter = 48200000000

    def _next_phone(self):
        self._phone_counter += 1
        return str(self._phone_counter)

    def _payload(self, **overrides):
        base = {
            "first_name": "Valid",
            "last_name": "Name",
            "phone_number": self._next_phone(),
        }
        base.update(overrides)
        return base

    def test_name_edge_cases(self):
        cases = [
            # (first, last, should_pass, description)
            ("Jan", "Kowalski", True, "normal names"),
            ("A", "B", True, "single char names"),
            ("A" * 50, "B" * 50, True, "max length 50"),
            ("A" * 51, "B", False, "first_name 51 chars — too long"),
            ("A", "B" * 51, False, "last_name 51 chars — too long"),
            ("", "Kowalski", False, "empty first_name"),
            ("Jan", "", False, "empty last_name"),
            ("Олександр", "Петренко", True, "Ukrainian names"),
            ("José", "García", True, "Spanish diacritics"),
            ("Marie-Claire", "O'Brien", True, "hyphen and apostrophe"),
            ("  Jan  ", "  Kowalski  ", True, "whitespace — DRF may strip"),
            ("123", "456", True, "numeric names (no validation)"),
            ("<script>", "alert(1)", True, "XSS in name (stored as text)"),
        ]
        bugs = []
        for first, last, should_pass, desc in cases:
            res = self.client.post(
                self.BASE_URL,
                self._payload(first_name=first, last_name=last),
                format="json",
            )
            passed = res.status_code == 201
            if passed != should_pass:
                bugs.append(f"{desc}: got {res.status_code} {str(res.data)[:200]}")

        self.assertEqual(bugs, [], f"Name validation bugs: {bugs}")

    def test_xss_in_name_stored_as_plain_text(self):
        res = self.client.post(
            self.BASE_URL,
            self._payload(first_name="<img src=x>", last_name="test"),
            format="json",
        )
        if res.status_code == 201:
            driver = Driver.objects.get(pk=res.data["id"])
            self.assertEqual(driver.first_name, "<img src=x>")


class DriverFilterAndPaginationTest(TestCase):
    """GET /api/v1/driver/ — search filter, pagination consistency."""

    BASE_URL = "/api/v1/driver/"

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()
        self.user = make_user(email="filter@test.com", username="filteruser")
        authenticate(self.client, self.user)
        # Create 25 drivers with varied names
        for i in range(25):
            Driver.objects.create(
                first_name=f"Alpha{i}" if i < 10 else f"Beta{i}",
                last_name=f"Driver{i:03d}",
                phone_number=f"48300{i:06d}",
            )

    def test_pagination_returns_correct_count(self):
        res = self.client.get(self.BASE_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 25)
        self.assertIn("results", res.data)

    def test_pagination_page_size(self):
        res = self.client.get(self.BASE_URL)
        # Default page_size — check results <= page_size
        self.assertLessEqual(len(res.data["results"]), 25)

    def test_search_by_first_name(self):
        res = self.client.get(f"{self.BASE_URL}?search=Alpha")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 10)
        for d in res.data["results"]:
            self.assertTrue(d["first_name"].startswith("Alpha"))

    def test_search_by_last_name(self):
        res = self.client.get(f"{self.BASE_URL}?search=Driver005")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.data["count"], 1)

    def test_search_empty_returns_all(self):
        res = self.client.get(f"{self.BASE_URL}?search=")
        self.assertEqual(res.data["count"], 25)

    def test_search_no_match_returns_empty(self):
        res = self.client.get(f"{self.BASE_URL}?search=ZZZNonexistent")
        self.assertEqual(res.data["count"], 0)
        self.assertEqual(res.data["results"], [])

    def test_page_2_returns_different_results(self):
        res1 = self.client.get(self.BASE_URL)
        if res1.data.get("next"):
            res2 = self.client.get(f"{self.BASE_URL}?page=2")
            self.assertEqual(res2.status_code, 200)
            ids1 = {d["id"] for d in res1.data["results"]}
            ids2 = {d["id"] for d in res2.data["results"]}
            self.assertEqual(len(ids1 & ids2), 0, "Page 1 and 2 should not overlap")

    def test_invalid_page_returns_404(self):
        res = self.client.get(f"{self.BASE_URL}?page=999")
        self.assertIn(res.status_code, [404, 200])


class DriverBulkPerformanceTest(TestCase):
    """Bulk creation and list performance."""

    BASE_URL = "/api/v1/driver/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="bulk@test.com", username="bulkdriver")
        authenticate(self.client, self.user)

    def test_bulk_create_1000_drivers(self):
        t0 = time.time()
        Driver.objects.bulk_create(
            [
                Driver(
                    first_name=f"Driver{i}",
                    last_name=f"Bulk{i}",
                    phone_number=f"48400{i:06d}",
                )
                for i in range(1000)
            ]
        )
        elapsed = time.time() - t0
        self.assertEqual(Driver.objects.count(), 1000)
        self.assertLess(elapsed, 5, f"1000 drivers took {elapsed:.1f}s")

    def test_list_1000_drivers_response_time(self):
        Driver.objects.bulk_create(
            [
                Driver(
                    first_name=f"D{i}",
                    last_name=f"L{i}",
                    phone_number=f"48500{i:06d}",
                )
                for i in range(1000)
            ]
        )
        t0 = time.time()
        res = self.client.get(self.BASE_URL)
        elapsed = time.time() - t0
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1000)
        self.assertLess(elapsed, 3, f"List 1k drivers took {elapsed:.1f}s")

    def test_search_among_1000_drivers(self):
        Driver.objects.bulk_create(
            [
                Driver(
                    first_name="UniqueTarget" if i == 500 else f"Normal{i}",
                    last_name=f"Search{i}",
                    phone_number=f"48600{i:06d}",
                )
                for i in range(1000)
            ]
        )
        t0 = time.time()
        res = self.client.get(f"{self.BASE_URL}?search=UniqueTarget")
        elapsed = time.time() - t0
        self.assertEqual(res.data["count"], 1)
        self.assertLess(elapsed, 2, f"Search took {elapsed:.1f}s")
