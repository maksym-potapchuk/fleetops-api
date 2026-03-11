from rest_framework import serializers

from .models import (
    EquipmentDefaultItem,
    EquipmentList,
    FleetService,
    FleetVehicleRegulation,
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationHistory,
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
            "address",
            "description",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "updated_at",
        ]


class FleetVehicleRegulationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetVehicleRegulation
        fields = [
            "vehicle",
            "schema",
            "created_by",
            "assigned_at",
        ]
        read_only_fields = ["created_by"]


class FleetVehicleRegulationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetVehicleRegulationItem
        fields = [
            "id",
            "title",
            "title_pl",
            "title_uk",
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
            "title_pl",
            "title_uk",
            "items",
            "is_default",
            "created_by",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        schema = FleetVehicleRegulationSchema.objects.create(**validated_data)

        for item_data in items_data:
            FleetVehicleRegulationItem.objects.create(schema=schema, **item_data)
        return schema


class RegulationEntryInitialSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    last_done_km = serializers.IntegerField(min_value=0)

    def validate_item_id(self, value):
        if not FleetVehicleRegulationItem.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Item {value} does not exist")
        return value


class AssignRegulationSerializer(serializers.Serializer):
    schema_id = serializers.IntegerField()
    entries = RegulationEntryInitialSerializer(many=True)

    def validate_schema_id(self, value):
        if not FleetVehicleRegulationSchema.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Schema {value} does not exist")
        return value

    def validate(self, data):
        schema = FleetVehicleRegulationSchema.objects.prefetch_related("items").get(
            pk=data["schema_id"]
        )
        schema_item_ids = set(schema.items.values_list("id", flat=True))
        provided_items_ids = set(item["item_id"] for item in data["entries"])

        invalid = provided_items_ids - schema_item_ids
        if invalid:
            raise serializers.ValidationError(
                f"Items {invalid} do not belong to schema"
            )

        if not provided_items_ids:
            raise serializers.ValidationError("At least one entry is required")
        return data


class AddRegulationEntrySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=155)
    title_pl = serializers.CharField(max_length=155, required=False, default="")
    title_uk = serializers.CharField(max_length=155, required=False, default="")
    every_km = serializers.IntegerField(min_value=1)
    notify_before_km = serializers.IntegerField(min_value=0, default=500)
    last_done_km = serializers.IntegerField(min_value=0, default=0)


class FleetVehicleRegulationSchemaUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH/PUT on an existing schema — no nested items."""

    class Meta:
        model = FleetVehicleRegulationSchema
        fields = ["id", "title", "title_pl", "title_uk", "is_default"]
        read_only_fields = ["id"]


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
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "vehicle",
            "created_by",
            "created_at",
        ]


class ServicePlanWithVehicleSerializer(serializers.ModelSerializer):
    vehicle_car_number = serializers.CharField(
        source="vehicle.car_number", read_only=True
    )

    class Meta:
        model = ServicePlan
        fields = [
            "id",
            "vehicle",
            "vehicle_car_number",
            "title",
            "description",
            "planned_at",
            "is_done",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "vehicle",
            "vehicle_car_number",
            "created_by",
            "created_at",
        ]


class EquipmentDefaultItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDefaultItem
        fields = [
            "id",
            "equipment",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
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
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "vehicle",
            "created_by",
            "created_at",
        ]


class VehicleRegulationPlanEntrySerializer(serializers.ModelSerializer):
    item = FleetVehicleRegulationItemSerializer(read_only=True)
    next_due_km = serializers.IntegerField(read_only=True)

    class Meta:
        model = FleetVehicleRegulationEntry
        fields = ["id", "item", "last_done_km", "next_due_km", "updated_at"]


class _RegulationSchemaShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetVehicleRegulationSchema
        fields = ["id", "title", "title_pl", "title_uk"]


class VehicleRegulationPlanSerializer(serializers.ModelSerializer):
    schema = _RegulationSchemaShortSerializer(read_only=True)
    entries = VehicleRegulationPlanEntrySerializer(many=True, read_only=True)

    class Meta:
        model = FleetVehicleRegulation
        fields = ["id", "schema", "assigned_at", "entries"]


class VehicleRegulationHistorySerializer(serializers.ModelSerializer):
    item_title = serializers.CharField(source="entry.item.title", read_only=True)
    item_title_pl = serializers.CharField(source="entry.item.title_pl", read_only=True)
    item_title_uk = serializers.CharField(source="entry.item.title_uk", read_only=True)

    class Meta:
        model = FleetVehicleRegulationHistory
        fields = [
            "id",
            "item_title",
            "item_title_pl",
            "item_title_uk",
            "event_type",
            "km_at_event",
            "km_remaining",
            "note",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
