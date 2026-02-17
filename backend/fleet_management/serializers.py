from rest_framework import serializers
from .models import (
    FleetService,
    ServiceHistory,
    FleetVehicleRegulation,
    FleetVehicleRegulationNotification,
)


class FleetServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetService
        fields = [
            "id", 
            "name", 
            "description", 
            "created_at", 
            "updated_at"
        ]
        read_only_fields = (
            "id", 
            "created_at", 
            "updated_at"
        )
