from rest_framework import serializers

from .models import Vehicle, VehicleOwnerHistory, VehiclePhoto


class VehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePhoto
        fields = ["id", "image", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

    def validate(self, attrs):
        vehicle_id = self.context["view"].kwargs["pk"]
        if VehiclePhoto.objects.filter(vehicle_id=vehicle_id).count() >= 10:
            raise serializers.ValidationError("Maximum 10 photos per vehicle.")
        return attrs

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Return path-only URL so the frontend can proxy via Next.js /media/ rewrite
        # regardless of whether the API is accessed from browser or server-side.
        image_url = rep.get("image") or ""
        if image_url:
            from urllib.parse import urlparse

            rep["image"] = urlparse(image_url).path
        return rep


class VehicleSerializer(serializers.ModelSerializer):
    photos = VehiclePhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "model",
            "manufacturer",
            "year",
            "cost",
            "vin_number",
            "car_number",
            "initial_km",
            "is_selected",
            "status",
            "driver",
            "photos",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "photos",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.driver:
            representation["driver"] = {
                "id": instance.driver.id,
                "first_name": instance.driver.first_name,
                "last_name": instance.driver.last_name,
            }
        else:
            representation["driver"] = None
        return representation


class VehicleOwnerHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleOwnerHistory
        fields = ["id", "driver", "agreement_number", "acquired_at", "released_at"]
        read_only_fields = ["id", "acquired_at"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["driver"] = {
            "id": instance.driver.id,
            "first_name": instance.driver.first_name,
            "last_name": instance.driver.last_name,
        }
        return rep
