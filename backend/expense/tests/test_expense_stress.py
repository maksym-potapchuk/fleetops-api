"""
Expense stress test — create 10000 expenses via API with varied edge-case data.
Reports which patterns fail validation and which pass.
"""

import time
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from expense.models import Expense, ExpenseCategory
from expense.tests.helpers import authenticate, make_user, make_vehicle

# ── Test data generators ─────────────────────────────────────────────────────

EDGE_AMOUNTS = [
    "0", "0.00", "0.01", "0.10", "1", "9.99", "10", "99.99",
    "100", "999.99", "1000", "9999.99", "10000", "99999.99",
    "12345.67", "0.001",  # 3 decimals — may fail
    "-1",  # negative — must fail
    "-0.01",  # negative — must fail
    "99999999.99",  # max 10 digits
    "100000000",  # 9 digits integer — may hit max_digits=10
    "",  # empty — must fail for COMPANY
    "abc",  # non-numeric — must fail
    "1e5",  # scientific notation
    "1,50",  # comma decimal — may fail
    "  100  ",  # whitespace
    "100.123456",  # many decimals
    ".50",  # no leading zero
    "00100",  # leading zeros
]

EDGE_DATES = [
    "2026-01-01T00:00:00Z",
    "2026-12-31T23:59:59Z",
    "2020-01-01T12:00:00Z",
    "2099-12-31T23:59:59Z",
    "2026-06-15T14:30:00+02:00",  # timezone offset
    "2026-03-15",  # date only — no time
    "",  # empty — must fail
    "not-a-date",  # invalid — must fail
    "2026-13-01T00:00:00Z",  # month 13 — must fail
    "2026-02-30T00:00:00Z",  # feb 30 — must fail
]

EDGE_PAYMENT_METHODS = ["CASH", "CASHLESS", "CRYPTO", "", "cash", None]
EDGE_PAYER_TYPES = ["COMPANY", "CLIENT", "BOTH", "", None]
EDGE_EXPENSE_FOR = [
    "", "a" * 500, "a" * 501,  # max_length=500
    "Normal expense", "Витрата на ремонт",  # unicode
    "<script>alert('xss')</script>",  # XSS attempt
    "DROP TABLE expense;",  # SQL injection attempt
    "\n\r\t",  # whitespace chars
]


class ExpenseStressTest(TestCase):
    """Create expenses via API with edge-case data, report failures."""

    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.fuel_cat = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )[0]
        self.other_cat = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )[0]

    def _post(self, **overrides):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.other_cat.id),
            "expense_date": "2026-04-01T12:00:00Z",
            "amount": "100.00",
            "payment_method": "CASHLESS",
            "payer_type": "COMPANY",
        }
        payload.update(overrides)
        return self.client.post(self.BASE_URL, payload, format="multipart")

    # ── Amount edge cases ────────────────────────────────────────────────────

    def test_amount_edge_cases(self):
        """Test all edge-case amounts, collect pass/fail."""
        results = {"pass": [], "fail": []}
        for amt in EDGE_AMOUNTS:
            res = self._post(amount=amt)
            bucket = "pass" if res.status_code == 201 else "fail"
            results[bucket].append((amt, res.status_code, str(res.data)[:200]))

        # Negative amounts MUST be rejected
        neg_results = [r for r in results["pass"] if r[0].lstrip().startswith("-")]
        self.assertEqual(
            neg_results, [],
            f"Negative amounts should be rejected but passed: {neg_results}",
        )

        # Non-numeric MUST be rejected
        non_numeric_passed = [
            r for r in results["pass"]
            if r[0] in ("abc", "not-a-date", "")
        ]
        self.assertEqual(
            non_numeric_passed, [],
            f"Non-numeric amounts should be rejected: {non_numeric_passed}",
        )

    # ── Date edge cases ──────────────────────────────────────────────────────

    def test_date_edge_cases(self):
        """Test all edge-case dates."""
        results = {"pass": [], "fail": []}
        for dt in EDGE_DATES:
            res = self._post(expense_date=dt)
            bucket = "pass" if res.status_code == 201 else "fail"
            results[bucket].append((dt, res.status_code, str(res.data)[:200]))

        # Invalid dates MUST be rejected
        must_fail = ["", "not-a-date", "2026-13-01T00:00:00Z", "2026-02-30T00:00:00Z"]
        invalid_passed = [r for r in results["pass"] if r[0] in must_fail]
        self.assertEqual(
            invalid_passed, [],
            f"Invalid dates should be rejected: {invalid_passed}",
        )

    # ── Payment method edge cases ────────────────────────────────────────────

    def test_payment_method_edge_cases(self):
        """Test valid and invalid payment methods."""
        results = {"pass": [], "fail": []}
        for pm in EDGE_PAYMENT_METHODS:
            kwargs = {"payment_method": pm} if pm is not None else {}
            res = self._post(**kwargs)
            bucket = "pass" if res.status_code == 201 else "fail"
            results[bucket].append((pm, res.status_code))

        # Invalid methods MUST be rejected
        invalid_passed = [r for r in results["pass"] if r[0] not in ("CASH", "CASHLESS", None)]
        self.assertEqual(
            invalid_passed, [],
            f"Invalid payment methods should be rejected: {invalid_passed}",
        )

    # ── Payer type edge cases ────────────────────────────────────────────────

    def test_payer_type_edge_cases(self):
        """Test valid and invalid payer types."""
        results = {"pass": [], "fail": []}
        for pt in EDGE_PAYER_TYPES:
            kwargs = {"payer_type": pt} if pt is not None else {}
            if pt == "CLIENT":
                kwargs.update({
                    "company_amount": "50.00",
                    "client_amount": "50.00",
                })
                kwargs.pop("amount", None)
            res = self._post(**kwargs)
            bucket = "pass" if res.status_code == 201 else "fail"
            results[bucket].append((pt, res.status_code))

        # Invalid payer types MUST be rejected
        invalid_passed = [r for r in results["pass"] if r[0] not in ("COMPANY", "CLIENT", None)]
        self.assertEqual(
            invalid_passed, [],
            f"Invalid payer types should be rejected: {invalid_passed}",
        )

    # ── expense_for edge cases ───────────────────────────────────────────────

    def test_expense_for_edge_cases(self):
        """Test long strings, XSS, SQL injection, unicode."""
        results = {"pass": [], "fail": []}
        for ef in EDGE_EXPENSE_FOR:
            res = self._post(expense_for=ef)
            bucket = "pass" if res.status_code == 201 else "fail"
            results[bucket].append((ef[:50], res.status_code))

        # 501 chars MUST be rejected (max_length=500)
        over_500_passed = [r for r in results["pass"] if len(r[0]) > 50 and "a" * 50 in r[0]]
        # Check in DB that XSS is stored as-is (not executed)
        xss_expenses = Expense.objects.filter(expense_for__contains="<script>")
        if xss_expenses.exists():
            self.assertEqual(
                xss_expenses.first().expense_for,
                "<script>alert('xss')</script>",
                "XSS should be stored as plain text",
            )

    # ── CLIENT payer edge cases ──────────────────────────────────────────────

    def test_client_payer_split_amounts(self):
        """Test CLIENT payer with various split amounts."""
        cases = [
            ({"company_amount": "0.00", "client_amount": "100.00"}, True),
            ({"company_amount": "100.00", "client_amount": "0.00"}, True),
            ({"company_amount": "50.50", "client_amount": "49.50"}, True),
            ({"company_amount": "-1", "client_amount": "101"}, False),
            ({"company_amount": "50", "client_amount": "-50"}, False),
            ({}, False),  # missing amounts for CLIENT
        ]
        for split, should_pass in cases:
            payload = {
                "payer_type": "CLIENT",
                **split,
            }
            payload.pop("amount", None)
            res = self._post(**payload)
            passed = res.status_code == 201
            self.assertEqual(
                passed, should_pass,
                f"CLIENT split {split}: expected {'pass' if should_pass else 'fail'}, "
                f"got {res.status_code} {str(res.data)[:200]}",
            )

    # ── Bulk creation performance ────────────────────────────────────────────

    def test_bulk_create_10000_expenses_via_orm(self):
        """Create 10000 expenses directly via ORM, verify count and time."""
        t0 = time.time()
        expenses = []
        for i in range(10000):
            expenses.append(Expense(
                vehicle=self.vehicle,
                category=self.fuel_cat if i % 2 == 0 else self.other_cat,
                expense_date=f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T12:00:00Z",
                amount=Decimal(str(round(i * 1.37, 2))),
                payment_method="CASH" if i % 3 == 0 else "CASHLESS",
                payer_type="COMPANY",
                created_by=self.user,
            ))
        Expense.objects.bulk_create(expenses)
        elapsed = time.time() - t0

        self.assertEqual(Expense.objects.count(), 10000)
        self.assertLess(elapsed, 15, f"10000 expenses took {elapsed:.1f}s")

    # ── Read performance ─────────────────────────────────────────────────────

    def test_list_expenses_with_10000_records(self):
        """GET /expense/ with 10000 records — must paginate and respond fast."""
        Expense.objects.bulk_create([
            Expense(
                vehicle=self.vehicle,
                category=self.other_cat,
                expense_date=f"2026-01-{(i % 28) + 1:02d}T12:00:00Z",
                amount=Decimal("100.00"),
                payer_type="COMPANY",
                created_by=self.user,
            )
            for i in range(10000)
        ])

        t0 = time.time()
        res = self.client.get(self.BASE_URL)
        elapsed = time.time() - t0

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 10000)
        self.assertLess(elapsed, 5, f"List 10k expenses took {elapsed:.1f}s")

    def test_vehicle_expense_summary_with_10000_records(self):
        """GET /vehicle/{id}/expenses/summary/ with 10000 records."""
        cats = [self.fuel_cat, self.other_cat]
        Expense.objects.bulk_create([
            Expense(
                vehicle=self.vehicle,
                category=cats[i % 2],
                expense_date=f"2026-01-{(i % 28) + 1:02d}T12:00:00Z",
                amount=Decimal(str(round(50 + i * 0.01, 2))),
                payer_type="COMPANY",
                created_by=self.user,
            )
            for i in range(10000)
        ])

        t0 = time.time()
        res = self.client.get(f"/api/v1/vehicle/{self.vehicle.id}/expenses/summary/")
        elapsed = time.time() - t0

        self.assertEqual(res.status_code, 200)
        self.assertLess(elapsed, 5, f"Summary took {elapsed:.1f}s")
