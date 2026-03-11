from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    vehicle_display = serializers.SerializerMethodField()
    driver_display = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "status",
            "vehicle",
            "driver",
            "vehicle_display",
            "driver_display",
            "payload",
            "is_read",
            "created_at",
            "read_at",
            "resolved_at",
            "resolved_by",
            "sent_at",
            "sent_to",
            "retry_at",
        ]
        read_only_fields = fields

    def get_vehicle_display(self, obj) -> str | None:
        if obj.vehicle:
            return str(obj.vehicle)
        return None

    def get_driver_display(self, obj) -> str | None:
        if obj.driver:
            return str(obj.driver)
        return None


class MileageSubmitSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField()
    km = serializers.IntegerField(min_value=1)
    unit = serializers.ChoiceField(choices=["km", "miles"], default="km")
    driver_telegram_id = serializers.IntegerField()


class ResolveNotificationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    reason = serializers.CharField(required=False, allow_blank=True, default="")
