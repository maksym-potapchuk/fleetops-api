from django.contrib import admin

from .models import Notification, NotificationPreferences


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "type",
        "status",
        "vehicle",
        "driver",
        "is_read",
        "dedup_key",
        "sent_to",
        "sent_at",
        "retry_at",
        "created_at",
    ]
    list_filter = ["type", "status", "is_read", "sent_to"]
    search_fields = ["vehicle__car_number", "driver__first_name", "driver__last_name"]
    readonly_fields = ["id", "created_at", "read_at", "resolved_at", "sent_at"]
    raw_id_fields = ["vehicle", "driver", "resolved_by"]


@admin.register(NotificationPreferences)
class NotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "inspection_enabled",
        "regulation_enabled",
        "service_plan_enabled",
        "mileage_enabled",
        "inspection_notify_days",
        "service_plan_notify_days",
    ]
    raw_id_fields = ["user"]
