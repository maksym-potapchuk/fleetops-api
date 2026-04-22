"""
VehicleDocument API tests — upload, delete, per-type limits, type detection.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from expense.tests.helpers import authenticate, make_user, make_vehicle
from vehicle.models import VehicleDocument


class VehicleDocumentUploadTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/documents/"

    def _jpg(self, name="photo.jpg"):
        return SimpleUploadedFile(
            name, b"\xff\xd8\xff\xe0fake", content_type="image/jpeg"
        )

    def _pdf(self, name="cert.pdf"):
        return SimpleUploadedFile(
            name, b"%PDF-1.4 fake", content_type="application/pdf"
        )

    def test_upload_photo_detected_as_photo(self):
        resp = self.client.post(self.url, {"file": self._jpg()}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["document_type"], "photo")

    def test_upload_pdf_detected_as_pdf(self):
        resp = self.client.post(self.url, {"file": self._pdf()}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["document_type"], "pdf")

    def test_two_photos_allowed(self):
        self.client.post(self.url, {"file": self._jpg("a.jpg")}, format="multipart")
        resp = self.client.post(
            self.url, {"file": self._jpg("b.jpg")}, format="multipart"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            VehicleDocument.objects.filter(
                vehicle=self.vehicle, document_type="photo"
            ).count(),
            2,
        )

    def test_third_photo_rejected(self):
        self.client.post(self.url, {"file": self._jpg("a.jpg")}, format="multipart")
        self.client.post(self.url, {"file": self._jpg("b.jpg")}, format="multipart")
        resp = self.client.post(
            self.url, {"file": self._jpg("c.jpg")}, format="multipart"
        )
        self.assertEqual(resp.status_code, 400)

    def test_third_pdf_rejected(self):
        self.client.post(self.url, {"file": self._pdf("a.pdf")}, format="multipart")
        self.client.post(self.url, {"file": self._pdf("b.pdf")}, format="multipart")
        resp = self.client.post(
            self.url, {"file": self._pdf("c.pdf")}, format="multipart"
        )
        self.assertEqual(resp.status_code, 400)

    def test_pdf_limit_independent_from_photo_limit(self):
        self.client.post(self.url, {"file": self._jpg("a.jpg")}, format="multipart")
        self.client.post(self.url, {"file": self._jpg("b.jpg")}, format="multipart")
        resp = self.client.post(
            self.url, {"file": self._pdf("a.pdf")}, format="multipart"
        )
        self.assertEqual(resp.status_code, 201)

    def test_non_image_non_pdf_rejected(self):
        bad = SimpleUploadedFile(
            "malware.exe", b"MZ", content_type="application/octet-stream"
        )
        resp = self.client.post(self.url, {"file": bad}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_upload_rejected(self):
        self.client.cookies.clear()
        resp = self.client.post(self.url, {"file": self._jpg()}, format="multipart")
        self.assertIn(resp.status_code, (401, 403))


class VehicleDocumentDeleteTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.list_url = f"/api/v1/vehicle/{self.vehicle.id}/documents/"
        resp = self.client.post(
            self.list_url,
            {
                "file": SimpleUploadedFile(
                    "a.jpg", b"\xff\xd8\xff", content_type="image/jpeg"
                )
            },
            format="multipart",
        )
        self.doc_id = resp.data["id"]

    def test_delete_removes_document(self):
        url = f"/api/v1/vehicle/{self.vehicle.id}/documents/{self.doc_id}/"
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(VehicleDocument.objects.filter(pk=self.doc_id).exists())

    def test_delete_allows_re_upload_past_limit(self):
        # Fill to limit, delete one, upload new
        self.client.post(
            self.list_url,
            {
                "file": SimpleUploadedFile(
                    "b.jpg", b"\xff\xd8", content_type="image/jpeg"
                )
            },
            format="multipart",
        )
        # 2 photos now — next would fail
        reject = self.client.post(
            self.list_url,
            {
                "file": SimpleUploadedFile(
                    "c.jpg", b"\xff\xd8", content_type="image/jpeg"
                )
            },
            format="multipart",
        )
        self.assertEqual(reject.status_code, 400)

        self.client.delete(
            f"/api/v1/vehicle/{self.vehicle.id}/documents/{self.doc_id}/"
        )

        accept = self.client.post(
            self.list_url,
            {
                "file": SimpleUploadedFile(
                    "c.jpg", b"\xff\xd8", content_type="image/jpeg"
                )
            },
            format="multipart",
        )
        self.assertEqual(accept.status_code, 201)
