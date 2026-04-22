"""
Tests for the VehicleDocument backfill migration logic.

Exercises the pure function directly (no migration runner) to keep the test
fast and independent from Django's migration executor.
"""

import importlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from expense.tests.helpers import make_user, make_vehicle
from vehicle.models import TechnicalInspection, VehicleDocument

backfill_module = importlib.import_module(
    "vehicle.migrations.0018_backfill_vehicle_documents"
)


class FakeAppsRegistry:
    """Minimal apps stub for apps.get_model used by the migration."""

    def __init__(self):
        self._models = {
            ("vehicle", "TechnicalInspection"): TechnicalInspection,
            ("vehicle", "VehicleDocument"): VehicleDocument,
        }

    def get_model(self, app_label, model_name):
        return self._models[(app_label, model_name)]


class BackfillMigrationTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle()

    def _inspection(self, file_name, content=b"x"):
        inspection = TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date="2026-01-01",
            created_by=self.user,
        )
        inspection.report = SimpleUploadedFile(file_name, content)
        inspection.save(update_fields=["report"])
        return inspection

    def _run(self):
        backfill_module.backfill_documents(FakeAppsRegistry(), schema_editor=None)

    def test_existing_pdf_report_copied_as_pdf_document(self):
        self._inspection("cert.pdf", b"%PDF-1.4")
        self._run()
        doc = VehicleDocument.objects.get(vehicle=self.vehicle)
        self.assertEqual(doc.document_type, "pdf")

    def test_existing_image_report_copied_as_photo_document(self):
        self._inspection("cert.jpg", b"\xff\xd8")
        self._run()
        doc = VehicleDocument.objects.get(vehicle=self.vehicle)
        self.assertEqual(doc.document_type, "photo")

    def test_idempotent_rerun(self):
        self._inspection("cert.pdf")
        self._run()
        self._run()
        self.assertEqual(VehicleDocument.objects.count(), 1)

    def test_respects_per_type_cap(self):
        for i in range(3):
            insp = TechnicalInspection.objects.create(
                vehicle=self.vehicle,
                inspection_date=f"2026-01-0{i + 1}",
                created_by=self.user,
            )
            insp.report = SimpleUploadedFile(f"cert{i}.pdf", b"%PDF")
            insp.save(update_fields=["report"])
        self._run()
        self.assertEqual(
            VehicleDocument.objects.filter(
                vehicle=self.vehicle, document_type="pdf"
            ).count(),
            2,
        )

    def test_empty_report_skipped(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date="2026-01-01",
            created_by=self.user,
        )
        self._run()
        self.assertEqual(VehicleDocument.objects.count(), 0)
