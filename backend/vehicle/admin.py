from django.contrib import admin

from .models import MileageLog, OwnerHistory, TechnicalInspection, Vehicle, VehicleOwner


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["car_number", "manufacturer", "model", "year", "status"]
    list_filter = ["status", "manufacturer"]
    search_fields = ["car_number", "vin_number", "model"]


@admin.register(TechnicalInspection)
class TechnicalInspectionAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "inspection_date", "created_at"]
    list_filter = ["inspection_date"]
    search_fields = ["vehicle__car_number"]
    raw_id_fields = ["vehicle"]


@admin.register(MileageLog)
class MileageLogAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "km", "recorded_at", "created_by"]
    list_filter = ["recorded_at"]
    search_fields = ["vehicle__car_number"]
    raw_id_fields = ["vehicle"]


@admin.register(VehicleOwner)
class VehicleOwnerAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "driver", "agreement_number", "assigned_at"]
    raw_id_fields = ["vehicle", "driver"]


@admin.register(OwnerHistory)
class OwnerHistoryAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "driver", "assigned_at", "unassigned_at"]
    raw_id_fields = ["vehicle", "driver"]
