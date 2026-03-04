"""
Vehicle Photos API Tests
========================
Covers: upload, max 10 limit, delete, list, cascade.
"""

import io

from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle, VehiclePhoto


def make_user(email="photo@example.com", password="pass123!", username="photouser"):
    return User.objects.create_user(email=email, password=password, username=username)


def make_vehicle(**kwargs):
    defaults = {
        "model": "Camry",
        "manufacturer": ManufacturerChoices.TOYOTA,
        "year": 2022,
        "cost": "25000.00",
        "vin_number": "1HGBH41JXMN109186",
        "car_number": "AA6601BB",
        "color": "#FFFFFF",
        "initial_km": 0,
        "status": VehicleStatus.PREPARATION,
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(**defaults)


def authenticate(client: APIClient, user: User) -> None:
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)


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
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/photos/"

    def test_upload_photo_returns_201(self):
        response = self.client.post(self.url, {"image": _make_image()}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(VehiclePhoto.objects.filter(vehicle=self.vehicle).count(), 1)

    def test_upload_returns_path_only_url(self):
        """Image URL in response must be a path-only string (no domain), for Next.js proxy."""
        response = self.client.post(self.url, {"image": _make_image()}, format="multipart")
        self.assertEqual(response.status_code, 201)
        image_url = response.data["image"]
        self.assertTrue(
            image_url.startswith("/media/"),
            f"Expected path-only URL, got: {image_url}",
        )

    def test_upload_11th_photo_returns_400(self):
        """Maximum 10 photos per vehicle enforced by serializer."""
        for i in range(10):
            VehiclePhoto.objects.create(
                vehicle=self.vehicle,
                image=f"vehicles/photos/test_{i}.jpg",
            )
        response = self.client.post(self.url, {"image": _make_image()}, format="multipart")
        self.assertEqual(response.status_code, 400)

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
