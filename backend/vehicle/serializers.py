from datetime import date
from decimal import Decimal

from rest_framework import serializers

from config.storage_utils import media_url

from .models import (
    MileageLog,
    OwnerHistory,
    TechnicalInspection,
    Vehicle,
    VehicleOwner,
    VehiclePhoto,
)


class VehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePhoto
        fields = ["id", "image", "uploaded_at", "created_by"]
        read_only_fields = ["id", "uploaded_at", "created_by"]

    def validate(self, attrs):
        vehicle_id = self.context["view"].kwargs["pk"]
        if VehiclePhoto.objects.filter(vehicle_id=vehicle_id).count() >= 10:
            raise serializers.ValidationError("Maximum 10 photos per vehicle.")
        return attrs

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Return path-only URL so the frontend can proxy via Next.js /media/ rewrite
        # regardless of whether the API is accessed from browser or server-side.
        image_url = rep.get("image") or ""
        if image_url:
            rep["image"] = media_url(image_url)
        return rep


class TechnicalInspectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicalInspection
        fields = [
            "id",
            "inspection_date",
            "next_inspection_date",
            "report",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def validate_inspection_date(self, value):
        if value > date.today():
            raise serializers.ValidationError(
                "Inspection date cannot be in the future."
            )
        return value

    @staticmethod
    def _compute_default_next(inspection_date):
        try:
            return inspection_date.replace(year=inspection_date.year + 1)
        except ValueError:
            return inspection_date.replace(year=inspection_date.year + 1, day=28)

    def validate(self, data):
        if not data.get("next_inspection_date"):
            inspection_date = data.get("inspection_date")
            if inspection_date:
                data["next_inspection_date"] = self._compute_default_next(
                    inspection_date
                )
        return data

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Backward compat: frontend reads expiry_date
        rep["expiry_date"] = rep.get("next_inspection_date")
        report_url = rep.get("report") or ""
        if report_url:
            rep["report"] = media_url(report_url)
        return rep


class VehicleSerializer(serializers.ModelSerializer):
    photos = VehiclePhotoSerializer(many=True, read_only=True)
    last_inspection_date = serializers.DateField(read_only=True, default=None)
    next_inspection_date = serializers.DateField(read_only=True, default=None)
    days_until_inspection = serializers.IntegerField(read_only=True, default=None)
    equipment_total = serializers.IntegerField(read_only=True, default=0)
    equipment_equipped = serializers.IntegerField(read_only=True, default=0)
    regulation_overdue = serializers.IntegerField(read_only=True, default=0)
    has_regulation = serializers.BooleanField(read_only=True, default=False)
    expenses_total = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, default=0
    )

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "model",
            "manufacturer",
            "year",
            "cost",
            "vin_number",
            "car_number",
            "is_temporary_plate",
            "color",
            "fuel_type",
            "initial_km",
            "is_selected",
            "status",
            "photos",
            "last_inspection_date",
            "next_inspection_date",
            "days_until_inspection",
            "equipment_total",
            "equipment_equipped",
            "regulation_overdue",
            "has_regulation",
            "expenses_total",
            "status_position",
            "is_archived",
            "archived_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "photos",
            "last_inspection_date",
            "next_inspection_date",
            "days_until_inspection",
            "equipment_total",
            "equipment_equipped",
            "regulation_overdue",
            "has_regulation",
            "expenses_total",
            "is_archived",
            "archived_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    @staticmethod
    def _compute_expiry(inspection_date):
        try:
            return inspection_date.replace(year=inspection_date.year + 1)
        except ValueError:
            return inspection_date.replace(year=inspection_date.year + 1, day=28)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Driver from current_owner (select_related in queryset)
        current_owner = getattr(instance, "_prefetched_current_owner", None)
        if current_owner is None:
            try:
                current_owner = instance.current_owner
            except VehicleOwner.DoesNotExist:
                current_owner = None

        if current_owner:
            representation["driver"] = {
                "id": str(current_owner.driver.id),
                "first_name": current_owner.driver.first_name,
                "last_name": current_owner.driver.last_name,
            }
        else:
            representation["driver"] = None

        inspections = list(instance.inspections.all())
        latest = inspections[0] if inspections else None
        if latest:
            next_date = latest.next_inspection_date or self._compute_expiry(
                latest.inspection_date
            )
            representation["last_inspection_date"] = latest.inspection_date.isoformat()
            representation["next_inspection_date"] = next_date.isoformat()
            representation["days_until_inspection"] = (next_date - date.today()).days
        else:
            representation["last_inspection_date"] = None
            representation["next_inspection_date"] = None
            representation["days_until_inspection"] = None

        # Equipment counts (uses prefetched equipment_list if available)
        eq_list = list(instance.equipment_list.all())
        representation["equipment_total"] = len(eq_list)
        representation["equipment_equipped"] = sum(1 for e in eq_list if e.is_equipped)

        # Regulation
        regs = list(instance.regulations.all())
        representation["has_regulation"] = len(regs) > 0
        overdue = 0
        current_km = instance.initial_km
        for reg in regs:
            for entry in reg.entries.all():
                if current_km >= entry.last_done_km + entry.item.every_km:
                    overdue += 1
        representation["regulation_overdue"] = overdue

        # Total cost = purchase price + all expenses
        expenses_total = getattr(instance, "expenses_total", None) or Decimal("0")
        representation["expenses_total"] = str(expenses_total)
        representation["total_cost"] = str(instance.cost + expenses_total)

        return representation


class VehicleOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleOwner
        fields = ["id", "driver", "agreement_number", "assigned_at", "created_by"]
        read_only_fields = ["id", "assigned_at", "created_by"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["driver"] = {
            "id": str(instance.driver.id),
            "first_name": instance.driver.first_name,
            "last_name": instance.driver.last_name,
        }
        return rep


class OwnerHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnerHistory
        fields = [
            "id",
            "driver",
            "agreement_number",
            "assigned_at",
            "unassigned_at",
            "created_by",
        ]
        read_only_fields = [
            "id",
            "driver",
            "agreement_number",
            "assigned_at",
            "unassigned_at",
            "created_by",
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["driver"] = {
            "id": str(instance.driver.id),
            "first_name": instance.driver.first_name,
            "last_name": instance.driver.last_name,
        }
        return rep


class MileageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MileageLog
        fields = ["id", "km", "recorded_at", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]

    def validate_km(self, value):
        vehicle_id = self.context["view"].kwargs["pk"]
        current_km = (
            Vehicle.objects.filter(pk=vehicle_id)
            .values_list("initial_km", flat=True)
            .first()
        )
        if current_km is not None and value <= current_km:
            raise serializers.ValidationError(
                f"Mileage must be greater than current value ({current_km} km)."
            )
        return value
