from rest_framework import serializers

from .models import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
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
            "is_selected",
            "status",
            "driver",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
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
