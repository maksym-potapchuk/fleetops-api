from rest_framework import serializers
from .models import Driver

class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = (
            "id",
            "first_name",
            "last_name",
            "phone_number",
            "has_vehicle",
            "is_active_driver",
            "last_active_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "has_vehicle",
            "is_active_driver",
            "created_at",
            "updated_at",
        )

    def validate_phone_number(self, values):
        if not values.isdigit():
            raise serializers.ValidationError("Phone number must contain only digits.")
        if len(values) < 10 or len(values) > 15:
            raise serializers.ValidationError("Phone number must be between 10 and 15 digits long.")
        if not values.startswith('+48'):
            raise serializers.ValidationError("Phone number must  start with +48, for example 4123456789.")