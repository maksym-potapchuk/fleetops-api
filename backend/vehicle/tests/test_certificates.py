"""
Registration Certificate API Tests
==================================
Covers: CRUD, type-based validation, photo replacement, inspection linkage.
"""

import datetime
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from vehicle.models import (
    CertificateType,
    RegistrationCertificate,
    RegistrationCertificatePhoto,
    TechnicalInspection,
)

from .helpers import authenticate, make_user, make_vehicle


def _img(name="cert.jpg") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")


class RegistrationCertificateAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="cert@example.com", username="certuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/registration-certificates/"

    def _payload(self, **overrides):
        base = {
            "certificate_type": CertificateType.TEMPORARY,
            "issued_at": "2026-05-08",
            "photo_front": _img("front.jpg"),
            "photo_back": _img("back.jpg"),
        }
        base.update(overrides)
        return base

    def test_create_temporary_auto_sets_valid_until_one_month_later(self):
        response = self.client.post(self.url, self._payload(), format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["valid_until"], "2026-06-08")
        self.assertEqual(response.data["certificate_type"], "temporary")

    def test_create_temporary_with_custom_valid_until_respects_input(self):
        payload = self._payload(valid_until="2026-08-01")
        response = self.client.post(self.url, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["valid_until"], "2026-08-01")

    def test_permanent_does_not_require_valid_until(self):
        payload = self._payload(certificate_type=CertificateType.PERMANENT)
        payload.pop("valid_until", None)
        response = self.client.post(self.url, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["valid_until"])

    def test_temporary_with_valid_until_before_issue_rejected(self):
        payload = self._payload(valid_until="2026-04-01")
        response = self.client.post(self.url, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid_until", response.data)

    def test_create_without_both_photos_rejected(self):
        payload = self._payload()
        payload.pop("photo_back")
        response = self.client.post(self.url, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("photo_back", response.data)

    def test_creating_new_certificate_deactivates_previous_active(self):
        self.client.post(self.url, self._payload(), format="multipart")
        old = RegistrationCertificate.objects.get(vehicle=self.vehicle)
        self.assertTrue(old.is_active)

        self.client.post(
            self.url, self._payload(issued_at="2026-07-01"), format="multipart"
        )
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        active = RegistrationCertificate.objects.filter(
            vehicle=self.vehicle, is_active=True
        ).count()
        self.assertEqual(active, 1)

    def test_replace_photo_front_replaces_only_front(self):
        self.client.post(self.url, self._payload(), format="multipart")
        cert = RegistrationCertificate.objects.get(vehicle=self.vehicle)
        back_id_before = RegistrationCertificatePhoto.objects.get(
            certificate=cert, side="back"
        ).id

        replace_url = f"{self.url}{cert.id}/photos/front/"
        response = self.client.put(
            replace_url, {"image": _img("new_front.jpg")}, format="multipart"
        )
        self.assertEqual(response.status_code, 200)

        back_after = RegistrationCertificatePhoto.objects.get(
            certificate=cert, side="back"
        )
        self.assertEqual(back_after.id, back_id_before)
        self.assertEqual(
            RegistrationCertificatePhoto.objects.filter(
                certificate=cert
            ).count(),
            2,
        )

    def test_replace_photo_invalid_side_rejected(self):
        self.client.post(self.url, self._payload(), format="multipart")
        cert = RegistrationCertificate.objects.get(vehicle=self.vehicle)
        bad_url = f"{self.url}{cert.id}/photos/sideways/"
        response = self.client.put(
            bad_url, {"image": _img()}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)

    def test_inspection_create_with_certificate_links_them(self):
        ins_url = f"/api/v1/vehicle/{self.vehicle.id}/inspections/"
        payload = {
            "inspection_date": "2026-05-08",
            "certificate_type": CertificateType.TEMPORARY,
            "certificate_issued_at": "2026-05-08",
            "certificate_photo_front": _img("front.jpg"),
            "certificate_photo_back": _img("back.jpg"),
        }
        response = self.client.post(ins_url, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        inspection = TechnicalInspection.objects.get(pk=response.data["id"])
        self.assertIsNotNone(inspection.registration_certificate)
        self.assertEqual(
            inspection.registration_certificate.valid_until,
            datetime.date(2026, 6, 8),
        )

    def test_inspection_create_with_existing_certificate_id_links_it(self):
        # First, create a certificate
        cert_response = self.client.post(
            self.url, self._payload(), format="multipart"
        )
        cert_id = cert_response.data["id"]

        # Then create an inspection that references it
        ins_url = f"/api/v1/vehicle/{self.vehicle.id}/inspections/"
        response = self.client.post(
            ins_url,
            {"inspection_date": "2026-05-10", "certificate_id": cert_id},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        inspection = TechnicalInspection.objects.get(pk=response.data["id"])
        self.assertEqual(str(inspection.registration_certificate_id), cert_id)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)
