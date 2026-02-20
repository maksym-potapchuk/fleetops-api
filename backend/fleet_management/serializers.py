from django.utils import timezone
from rest_framework import serializers

from .models import (
    EquipmentDefaultItem,
    EquipmentList,
    FleetService,
    FleetVehicleRegulation,
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
    ServicePlan,
)


class FleetServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetService
        fields = [
            "id",
            "name",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class FleetVehicleRegulationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetVehicleRegulation
        fields = [
            "vehicle",
            "schema",
            "assigned_at",
        ]


class FleetVehicleRegulationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetVehicleRegulationItem
        fields = [
            "id",
            "title",
            "every_km",
            "notify_before_km",
        ]


class FleetVehicleRegulationSchemaSerializer(serializers.ModelSerializer):
    items = FleetVehicleRegulationItemSerializer(many=True)

    class Meta:
        model = FleetVehicleRegulationSchema
        fields = [
            "id",
            "title",
            "items",
            "is_default",
            "created_by",
        ]

    def validate_is_default(self, value):
        """Only one schema can be default"""
        return value

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        schema = FleetVehicleRegulationSchema.objects.create(**validated_data)

        for item_data in items_data:
            FleetVehicleRegulationItem.objects.create(schema=schema, **item_data)
        return schema


class ServicePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePlan
        fields = [
            "id",
            "vehicle",
            "title",
            "description",
            "planned_at",
            "is_done",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


class EquipmentDefaultItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDefaultItem
        fields = [
            "id",
            "equipment",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


class EquipmentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentList
        fields = [
            "id",
            "vehicle",
            "equipment",
            "is_equipped",
            "approved_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "approved_at",
            "created_at",
        ]

    def update(self, instance, validated_data):
        if validated_data.get("is_equipped") and not instance.is_equipped:
            validated_data["approved_at"] = timezone.now()
        return super().update(instance, validated_data)
