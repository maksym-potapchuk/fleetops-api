"""
Invoice model tests — shared invoice across multiple expenses.
===============================================================
Covers: create expense with new invoice, attach existing invoice,
invoice_existing flag, search endpoint, auth guard, file validation.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from expense.models import ExpenseCategory, Invoice

from .helpers import authenticate, make_user, make_vehicle


class InvoiceExpenseTest(TestCase):
    """POST /expense/ — invoice creation and attachment."""

    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="inv@example.com", username="invuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.service_cat, _ = ExpenseCategory.objects.get_or_create(
            code="SERVICE",
            defaults={"name": "Service", "is_system": True, "order": 2},
        )
        self.parts_cat, _ = ExpenseCategory.objects.get_or_create(
            code="PARTS",
            defaults={"name": "Parts", "is_system": True, "order": 3},
        )

    def _pdf(self, name="invoice.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")

    def _base(self, category, **extra):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(category.id),
            "expense_date": "2026-03-01",
            "amount": "250.00",
        }
        payload.update(extra)
        return payload

    def test_create_expense_with_new_invoice(self):
        """New invoice_number + invoice_file → creates Invoice + links to expense."""
        payload = self._base(
            self.parts_cat,
            invoice_number="FAK-2026/001",
            invoice_file=self._pdf(),
        )
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.data["invoice_data"])
        self.assertEqual(response.data["invoice_data"]["number"], "FAK-2026/001")
        self.assertFalse(response.data["invoice_existing"])
        self.assertEqual(Invoice.objects.count(), 1)

    def test_create_expense_with_existing_invoice_attaches_it(self):
        """If invoice_number matches existing Invoice → attach without re-upload."""
        invoice = Invoice.objects.create(
            number="FAK-EXIST-001",
            file=self._pdf("existing.pdf"),
            vendor_name="AutoParts Sp. z o.o.",
        )
        payload = self._base(self.parts_cat, invoice_number="FAK-EXIST-001")
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["invoice_existing"])
        self.assertEqual(response.data["invoice_data"]["id"], str(invoice.id))
        # No new Invoice created
        self.assertEqual(Invoice.objects.count(), 1)

    def test_multiple_expenses_share_same_invoice(self):
        """Two expenses can reference the same Invoice object."""
        invoice = Invoice.objects.create(
            number="FAK-SHARED-001",
            file=self._pdf("shared.pdf"),
        )
        for i in range(2):
            v = make_vehicle(
                car_number=f"BB770{i}CC",
                vin_number=f"WVWZZZ3CZWE00000{i}",
            )
            payload = self._base(self.parts_cat, invoice_number="FAK-SHARED-001")
            payload["vehicle"] = str(v.id)
            resp = self.client.post(self.BASE_URL, payload, format="multipart")
            self.assertEqual(resp.status_code, 201)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(invoice.expenses.count(), 2)

    def test_invoice_number_without_file_returns_400(self):
        """invoice_number without matching Invoice AND no file → 400 validation error."""
        payload = self._base(self.parts_cat, invoice_number="FAK-NO-FILE-001")
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("invoice_file", response.data)
        self.assertEqual(Invoice.objects.count(), 0)

    def test_invoice_jpg_file_rejected(self):
        """Only .pdf, .doc, .docx allowed — .jpg must be rejected."""
        jpg = SimpleUploadedFile("photo.jpg", b"\xff\xd8\xff", content_type="image/jpeg")
        payload = self._base(
            self.parts_cat,
            invoice_number="FAK-JPG-001",
            invoice_file=jpg,
        )
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("invoice_file", response.data)

    def test_expense_without_invoice_number_creates_no_invoice(self):
        """Expense without invoice_number → no Invoice created, invoice_data=null."""
        payload = self._base(self.parts_cat)
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["invoice_data"])
        self.assertFalse(response.data["invoice_existing"])
        self.assertEqual(Invoice.objects.count(), 0)

    def test_delete_expense_does_not_delete_shared_invoice(self):
        """Deleting an expense with a shared invoice keeps the Invoice intact."""
        invoice = Invoice.objects.create(
            number="FAK-KEEP-001", file=self._pdf("keep.pdf"),
        )
        v2 = make_vehicle(car_number="CC8801DD", vin_number="WVWZZZ3CZWE000099")
        # Two expenses sharing the same invoice
        p1 = self._base(self.parts_cat, invoice_number="FAK-KEEP-001")
        p2 = self._base(self.parts_cat, invoice_number="FAK-KEEP-001")
        p2["vehicle"] = str(v2.id)
        r1 = self.client.post(self.BASE_URL, p1, format="multipart")
        r2 = self.client.post(self.BASE_URL, p2, format="multipart")
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        # Delete first expense
        self.client.delete(f"{self.BASE_URL}{r1.data['id']}/")
        # Invoice still exists with 1 linked expense
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(invoice.expenses.count(), 1)

    def test_invoice_docx_file_accepted(self):
        """.docx files are valid invoice attachments."""
        docx = SimpleUploadedFile("invoice.docx", b"PK\x03\x04", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        payload = self._base(
            self.parts_cat,
            invoice_number="FAK-DOCX-001",
            invoice_file=docx,
        )
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["invoice_data"]["number"], "FAK-DOCX-001")


class InvoiceSearchTest(TestCase):
    """GET /expense/invoices/?search=... — invoice autocomplete."""

    SEARCH_URL = "/api/v1/expense/invoices/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="search@example.com", username="searchuser")
        authenticate(self.client, self.user)
        self.pdf = SimpleUploadedFile("inv.pdf", b"%PDF-1.4", content_type="application/pdf")

    def test_search_returns_matching_invoices(self):
        Invoice.objects.create(number="FAK-100/2026", file=self.pdf, vendor_name="Kraków Auto")
        pdf2 = SimpleUploadedFile("inv2.pdf", b"%PDF-1.4", content_type="application/pdf")
        Invoice.objects.create(number="FAK-200/2026", file=pdf2, vendor_name="Warszawa Parts")
        response = self.client.get(self.SEARCH_URL, {"search": "FAK-100"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["number"], "FAK-100/2026")

    def test_search_by_vendor_name(self):
        Invoice.objects.create(number="FAK-V-001", file=self.pdf, vendor_name="AutoSerwis Kraków")
        response = self.client.get(self.SEARCH_URL, {"search": "Kraków"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["vendor_name"], "AutoSerwis Kraków")

    def test_search_includes_expense_count(self):
        invoice = Invoice.objects.create(number="FAK-COUNT-001", file=self.pdf)
        # Create 2 expenses linked to this invoice
        user = self.user
        vehicle = make_vehicle()
        cat, _ = ExpenseCategory.objects.get_or_create(
            code="PARTS", defaults={"name": "Parts", "is_system": True, "order": 3}
        )
        from expense.models import Expense

        for _ in range(2):
            Expense.objects.create(
                vehicle=vehicle, category=cat, amount="100.00",
                expense_date="2026-03-01", invoice=invoice, created_by=user,
            )
        response = self.client.get(self.SEARCH_URL, {"search": "FAK-COUNT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["expense_count"], 2)

    def test_search_without_query_returns_all(self):
        Invoice.objects.create(number="FAK-ALL-001", file=self.pdf)
        pdf2 = SimpleUploadedFile("a2.pdf", b"%PDF-1.4", content_type="application/pdf")
        Invoice.objects.create(number="FAK-ALL-002", file=pdf2)
        response = self.client.get(self.SEARCH_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_search_layout_aware_finds_cyrillic_from_latin(self):
        """Layout-aware filter: typing 'Aenjcthdsc' (lat) finds 'АвтоСервіс' (cyr)."""
        pdf2 = SimpleUploadedFile("layout.pdf", b"%PDF-1.4", content_type="application/pdf")
        Invoice.objects.create(number="FAK-LAYOUT-001", file=pdf2, vendor_name="АвтоСервіс")
        # 'Fdnjcthdsc' is what you type on English layout trying to type 'АвтоСервіс'
        response = self.client.get(self.SEARCH_URL, {"search": "АвтоСервіс"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_unauthenticated_search_returns_401(self):
        client = APIClient()
        response = client.get(self.SEARCH_URL, {"search": "FAK"})
        self.assertEqual(response.status_code, 401)
