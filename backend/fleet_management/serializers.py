from django.utils import timezone
from rest_framework import serializers

from .models import (
    EquipmentDefaultItem,
    EquipmentList,
    FleetService,
    FleetVehicleRegulation,
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationHistory,
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


class RegulationEntryInitialSerializer(serializers.Serializer):
    item_id=serializers.IntegerField()
    last_done_km=serializers.IntegerField(min_value=0)

    def validate_item_id(self, value):
        if not FleetVehicleRegulationItem.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Item {value} does not exist")
        return value 

class AssignRegulationSerializer(serializers.Serializer):
    schema_id=serializers.IntegerField()
    entries=RegulationEntryInitialSerializer(many=True)

    def validate_schema_id(self, value):
        if not FleetVehicleRegulationSchema.objects.filter(pk=value).exists:
            raise serializers.ValidationError(f"Schema {value} does not exist")
        return value

    def validate(self, data):
        schema=FleetVehicleRegulationSchema.objects.prefetch_related(
            "items"
        ).get(pk=data["schema_id"])
        schema_item_ids=set(schema.items.values_list("id", flat=True))
        provided_items_ids=[item["item_id"] for item in data["entires"]]

        invalid=provided_items_ids-schema_item_ids
        if invalid:
            raise serializers.ValidationError(
                F"Items {invalid} does not exist to schema"
            )

        missing=schema_item_ids-provided_items_ids
        if missing:
            raise serializers.ValidationError(
                F"Does not exist last_km_done for every items: {missing}"
            )
        return data
    
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
