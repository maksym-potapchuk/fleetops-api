"""
Vehicle Photos API Tests
========================
Covers: upload, delete, list, cascade.
"""

import io

from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from vehicle.models import VehiclePhoto

from .helpers import authenticate, make_user, make_vehicle


def _make_image():
    """Create a minimal valid image file for upload."""
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    buf.name = "test.jpg"
    return buf


class VehiclePhotoAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="photo@example.com", username="photouser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/photos/"

    def test_upload_photo_returns_201(self):
        response = self.client.post(
            self.url, {"image": _make_image()}, format="multipart"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(VehiclePhoto.objects.filter(vehicle=self.vehicle).count(), 1)

    def test_upload_returns_path_only_url(self):
        """Image URL in response must be a path-only string (no domain), for Next.js proxy."""
        response = self.client.post(
            self.url, {"image": _make_image()}, format="multipart"
        )
        self.assertEqual(response.status_code, 201)
        image_url = response.data["image"]
        self.assertTrue(
            image_url.startswith("/media/"),
            f"Expected path-only URL, got: {image_url}",
        )

    def test_list_returns_all_photos(self):
        VehiclePhoto.objects.create(vehicle=self.vehicle, image="vehicles/photos/a.jpg")
        VehiclePhoto.objects.create(vehicle=self.vehicle, image="vehicles/photos/b.jpg")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 2)

    def test_delete_photo_returns_204(self):
        photo = VehiclePhoto.objects.create(
            vehicle=self.vehicle, image="vehicles/photos/del.jpg"
        )
        url = f"{self.url}{photo.pk}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(VehiclePhoto.objects.filter(pk=photo.pk).exists())

    def test_cascade_delete_removes_photos(self):
        VehiclePhoto.objects.create(vehicle=self.vehicle, image="vehicles/photos/c.jpg")
        self.vehicle.delete()
        self.assertEqual(VehiclePhoto.objects.count(), 0)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)
