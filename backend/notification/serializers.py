from rest_framework import serializers

from .models import Notification, NotificationPreferences


class NotificationSerializer(serializers.ModelSerializer):
    vehicle_display = serializers.SerializerMethodField()
    driver_display = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "status",
            "source",
            "vehicle",
            "driver",
            "vehicle_display",
            "driver_display",
            "payload",
            "dedup_key",
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


class NotificationPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreferences
        fields = [
            "inspection_enabled",
            "regulation_enabled",
            "service_plan_enabled",
            "mileage_enabled",
            "certificate_enabled",
            "inspection_notify_days",
            "service_plan_notify_days",
            "certificate_notify_days",
            "regulation_notify_before_km",
            "overdue_reminder_interval",
            "overdue_reminder_max",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_inspection_notify_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of integers.")
        if not all(isinstance(d, int) and 1 <= d <= 90 for d in value):
            raise serializers.ValidationError(
                "Each value must be an integer between 1 and 90."
            )
        return sorted(set(value), reverse=True)

    def validate_service_plan_notify_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of integers.")
        if not all(isinstance(d, int) and 1 <= d <= 90 for d in value):
            raise serializers.ValidationError(
                "Each value must be an integer between 1 and 90."
            )
        return sorted(set(value), reverse=True)

    def validate_certificate_notify_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of integers.")
        if not all(isinstance(d, int) and 1 <= d <= 90 for d in value):
            raise serializers.ValidationError(
                "Each value must be an integer between 1 and 90."
            )
        return sorted(set(value), reverse=True)
