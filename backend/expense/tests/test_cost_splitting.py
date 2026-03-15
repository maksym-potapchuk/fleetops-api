"""
Cost Splitting & Approval Workflow Tests
=========================================
Covers the CLIENT payer type feature:
- company_amount + client_amount validation
- Approval status state machine transitions
- Payer type switching (COMPANY <-> CLIENT) side effects

VULNERABILITY FOCUS:
- Can a user bypass approval by switching payer type?
- Can negative amounts be injected?
- Can split amounts mismatch the total?
- Can APPROVED status be reverted?
"""

from decimal import Decimal
import json

from django.test import TestCase
from rest_framework.test import APIClient

from expense.models import Expense, ExpenseCategory

from .helpers import authenticate, make_user, make_vehicle

FMT = "multipart"


class CostSplittingTest(TestCase):
    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.fuel_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )
        self.other_cat, _ = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )

    def _fuel_payload(self, **overrides):
        base = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.fuel_cat.id),
            "amount": "200.00",
            "expense_date": "2026-03-01",
            "fuel_types": json.dumps(["GASOLINE"]),
            "payer_type": "COMPANY",
        }
        base.update(overrides)
        return base

    def _other_payload(self, **overrides):
        """OTHER category has no required detail fields — safe for PATCH tests."""
        base = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.other_cat.id),
            "amount": "200.00",
            "expense_date": "2026-03-01",
            "payer_type": "COMPANY",
        }
        base.update(overrides)
        return base

    # --- CLIENT payer requires split amounts ---

    def test_client_payer_without_split_amounts_returns_400(self):
        payload = self._fuel_payload(payer_type="CLIENT")
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 400)
        self.assertIn("company_amount", str(response.data))

    def test_client_payer_with_valid_split_returns_201(self):
        payload = self._fuel_payload(
            payer_type="CLIENT",
            company_amount="120.00",
            client_amount="80.00",
        )
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 201)
        expense = Expense.objects.get(id=response.data["id"])
        self.assertEqual(expense.company_amount, Decimal("120.00"))
        self.assertEqual(expense.client_amount, Decimal("80.00"))

    def test_negative_company_amount_returns_400(self):
        """VULNERABILITY: negative amounts must be rejected."""
        payload = self._fuel_payload(
            payer_type="CLIENT",
            company_amount="-50.00",
            client_amount="250.00",
        )
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 400)
        self.assertIn("company_amount", str(response.data))

    def test_negative_client_amount_returns_400(self):
        payload = self._fuel_payload(
            payer_type="CLIENT",
            company_amount="250.00",
            client_amount="-50.00",
        )
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 400)
        self.assertIn("client_amount", str(response.data))

    # --- Default approval status ---

    def test_default_approval_status_draft_on_client_create(self):
        payload = self._fuel_payload(
            payer_type="CLIENT",
            company_amount="120.00",
            client_amount="80.00",
        )
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 201)
        expense = Expense.objects.get(id=response.data["id"])
        self.assertEqual(expense.approval_status, "DRAFT")

    def test_company_payer_has_no_approval_status(self):
        payload = self._fuel_payload(payer_type="COMPANY")
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 201)
        expense = Expense.objects.get(id=response.data["id"])
        self.assertIsNone(expense.approval_status)
        self.assertEqual(expense.amount, Decimal("200.00"))
        self.assertIsNone(expense.company_amount)
        self.assertIsNone(expense.client_amount)

    # --- Payer type switching clears fields (using OTHER to avoid detail validation) ---

    def test_switch_from_client_to_company_clears_client_fields(self):
        """VULNERABILITY: switching payer type must clear approval status to prevent bypass."""
        payload = self._other_payload(
            payer_type="CLIENT",
            company_amount="120.00",
            client_amount="80.00",
        )
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 201)
        expense_id = response.data["id"]

        patch = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"payer_type": "COMPANY"},
            format=FMT,
        )
        self.assertEqual(patch.status_code, 200)
        expense = Expense.objects.get(id=expense_id)
        # amount preserved, split fields cleared
        self.assertEqual(expense.amount, Decimal("200.00"))
        self.assertIsNone(expense.company_amount)
        self.assertIsNone(expense.client_amount)
        self.assertIsNone(expense.client_driver)
        self.assertIsNone(expense.approval_status)


class ApprovalWorkflowTest(TestCase):
    """Uses OTHER category to avoid detail field validation on PATCH."""

    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.other_cat, _ = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )

    def _create_client_expense(self, approval_status="DRAFT"):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.other_cat.id),
            "expense_date": "2026-03-01",
            "payer_type": "CLIENT",
            "company_amount": "60.00",
            "client_amount": "40.00",
        }
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 201)
        expense_id = response.data["id"]
        if approval_status != "DRAFT":
            transitions = {
                "SENT": ["SENT"],
                "REVIEW": ["SENT", "REVIEW"],
                "APPROVED": ["SENT", "REVIEW", "APPROVED"],
            }
            for status in transitions.get(approval_status, []):
                r = self.client.patch(
                    f"{self.BASE_URL}{expense_id}/",
                    {"approval_status": status},
                    format=FMT,
                )
                self.assertEqual(r.status_code, 200, f"Transition to {status} failed")
        return expense_id

    # --- Valid transitions ---

    def test_draft_to_sent_succeeds(self):
        expense_id = self._create_client_expense("DRAFT")
        response = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"approval_status": "SENT"},
            format=FMT,
        )
        self.assertEqual(response.status_code, 200)

    def test_sent_to_review_succeeds(self):
        expense_id = self._create_client_expense("SENT")
        response = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"approval_status": "REVIEW"},
            format=FMT,
        )
        self.assertEqual(response.status_code, 200)

    def test_sent_to_draft_succeeds(self):
        """Rejecting a sent expense back to draft."""
        expense_id = self._create_client_expense("SENT")
        response = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"approval_status": "DRAFT"},
            format=FMT,
        )
        self.assertEqual(response.status_code, 200)

    def test_review_to_approved_succeeds(self):
        expense_id = self._create_client_expense("REVIEW")
        response = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"approval_status": "APPROVED"},
            format=FMT,
        )
        self.assertEqual(response.status_code, 200)

    # --- Invalid transitions ---

    def test_draft_to_review_returns_400(self):
        """VULNERABILITY: skipping SENT step should not be allowed."""
        expense_id = self._create_client_expense("DRAFT")
        response = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"approval_status": "REVIEW"},
            format=FMT,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("approval_status", str(response.data))

    def test_draft_to_approved_returns_400(self):
        """VULNERABILITY: direct jump to APPROVED should be blocked."""
        expense_id = self._create_client_expense("DRAFT")
        response = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"approval_status": "APPROVED"},
            format=FMT,
        )
        self.assertEqual(response.status_code, 400)

    def test_approved_cannot_transition_to_any_status(self):
        """VULNERABILITY: once approved, no further state changes allowed."""
        expense_id = self._create_client_expense("APPROVED")
        for target in ["DRAFT", "SENT", "REVIEW"]:
            response = self.client.patch(
                f"{self.BASE_URL}{expense_id}/",
                {"approval_status": target},
                format=FMT,
            )
            self.assertEqual(
                response.status_code,
                400,
                f"APPROVED -> {target} should be blocked",
            )

    def test_review_to_draft_returns_400(self):
        """Cannot go from REVIEW back to DRAFT (must go through SENT first)."""
        expense_id = self._create_client_expense("REVIEW")
        response = self.client.patch(
            f"{self.BASE_URL}{expense_id}/",
            {"approval_status": "DRAFT"},
            format=FMT,
        )
        self.assertEqual(response.status_code, 400)
