from rest_framework import serializers
from .models import Vehicle

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        models=Vehicle
        fields=[
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

        read_only_fields=[
            "id",
            "created_at",
            "updated_at",
        ]