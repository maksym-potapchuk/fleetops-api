from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from rest_framework import serializers

from config.storage_utils import media_url
from driver.models import DriverVehicleDeal

from .models import (
    CertificateType,
    MileageLog,
    RegistrationCertificate,
    RegistrationCertificatePhoto,
    TechnicalInspection,
    Vehicle,
    VehicleDocument,
    VehiclePhoto,
)


class VehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePhoto
        fields = ["id", "image", "is_cover", "uploaded_at", "created_by"]
        read_only_fields = ["id", "uploaded_at", "created_by"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Return path-only URL so the frontend can proxy via Next.js /media/ rewrite
        # regardless of whether the API is accessed from browser or server-side.
        image_url = rep.get("image") or ""
        if image_url:
            rep["image"] = media_url(image_url)
        return rep


class VehicleDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDocument
        fields = ["id", "doc_type", "title", "file", "created_at", "created_by"]
        read_only_fields = ["id", "created_at", "created_by"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        file_url = rep.get("file") or ""
        if file_url:
            rep["file"] = media_url(file_url)
        if not rep.get("title"):
            try:
                rep["title"] = instance.file.name.split("/")[-1]
            except Exception:
                pass
        return rep


class RegistrationCertificatePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationCertificatePhoto
        fields = ["id", "side", "image", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        image_url = rep.get("image") or ""
        if image_url:
            rep["image"] = media_url(image_url)
        return rep


class RegistrationCertificateSerializer(serializers.ModelSerializer):
    photos = RegistrationCertificatePhotoSerializer(many=True, read_only=True)
    photo_front = serializers.ImageField(write_only=True, required=False)
    photo_back = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = RegistrationCertificate
        fields = [
            "id",
            "vehicle",
            "certificate_type",
            "issued_at",
            "valid_until",
            "notes",
            "is_active",
            "photos",
            "photo_front",
            "photo_back",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vehicle",
            "is_active",
            "photos",
            "created_by",
            "created_at",
            "updated_at",
        ]

    @staticmethod
    def _default_valid_until(certificate_type, issued_at):
        if not issued_at:
            return None
        if certificate_type == CertificateType.TEMPORARY:
            return issued_at + relativedelta(months=1)
        return None

    def validate(self, data):
        cert_type = data.get(
            "certificate_type",
            getattr(self.instance, "certificate_type", CertificateType.PERMANENT),
        )
        issued_at = data.get(
            "issued_at",
            getattr(self.instance, "issued_at", None),
        )
        valid_until = data.get("valid_until")

        if cert_type == CertificateType.TEMPORARY:
            if "valid_until" not in data or valid_until is None:
                if not self.instance and issued_at:
                    data["valid_until"] = self._default_valid_until(
                        cert_type, issued_at
                    )
                elif self.instance and self.instance.valid_until is None:
                    data["valid_until"] = self._default_valid_until(
                        cert_type, issued_at
                    )

            final_valid_until = data.get(
                "valid_until", getattr(self.instance, "valid_until", None)
            )
            if final_valid_until is None:
                raise serializers.ValidationError(
                    {
                        "valid_until": "Temporary certificates require an expiry date.",
                    }
                )
            if issued_at and final_valid_until <= issued_at:
                raise serializers.ValidationError(
                    {"valid_until": "Expiry must be after the issue date."}
                )
        return data

    def _require_photos_on_create(self, attrs):
        photo_front = attrs.get("photo_front")
        photo_back = attrs.get("photo_back")
        missing = []
        if not photo_front:
            missing.append("photo_front")
        if not photo_back:
            missing.append("photo_back")
        if missing:
            raise serializers.ValidationError(
                {field: "This field is required." for field in missing}
            )

    @transaction.atomic
    def create(self, validated_data):
        photo_front = validated_data.pop("photo_front", None)
        photo_back = validated_data.pop("photo_back", None)
        self._require_photos_on_create(
            {"photo_front": photo_front, "photo_back": photo_back}
        )

        vehicle_id = validated_data.get("vehicle_id") or (
            validated_data["vehicle"].pk if validated_data.get("vehicle") else None
        )
        # Deactivate previous active certificate
        RegistrationCertificate.objects.filter(
            vehicle_id=vehicle_id, is_active=True
        ).update(is_active=False)

        certificate = RegistrationCertificate.objects.create(
            is_active=True, **validated_data
        )
        RegistrationCertificatePhoto.objects.create(
            certificate=certificate,
            side=RegistrationCertificatePhoto.Side.FRONT,
            image=photo_front,
        )
        RegistrationCertificatePhoto.objects.create(
            certificate=certificate,
            side=RegistrationCertificatePhoto.Side.BACK,
            image=photo_back,
        )
        return certificate

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("photo_front", None)
        validated_data.pop("photo_back", None)
        return super().update(instance, validated_data)


class LinkedExpenseSerializer(serializers.Serializer):
    """Read-only nested representation of expense linked to an inspection."""

    id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    official_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    additional_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.CharField()
    receipt = serializers.CharField(allow_null=True)
    registration_certificate = serializers.CharField(allow_null=True)
    invoice_number = serializers.CharField(allow_null=True)
    invoice_file = serializers.CharField(allow_null=True)
    expense_date = serializers.DateTimeField()


class TechnicalInspectionSerializer(serializers.ModelSerializer):
    linked_expense = serializers.SerializerMethodField()
    registration_certificate = RegistrationCertificateSerializer(read_only=True)

    # Inline certificate creation fields (multipart). When provided on create,
    # a new RegistrationCertificate is created and linked to this inspection.
    certificate_type = serializers.ChoiceField(
        choices=CertificateType.choices, write_only=True, required=False
    )
    certificate_issued_at = serializers.DateField(write_only=True, required=False)
    certificate_valid_until = serializers.DateField(
        write_only=True, required=False, allow_null=True
    )
    certificate_photo_front = serializers.ImageField(write_only=True, required=False)
    certificate_photo_back = serializers.ImageField(write_only=True, required=False)
    certificate_notes = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    # Alternative to creating a new certificate: link an existing one
    certificate_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = TechnicalInspection
        fields = [
            "id",
            "inspection_date",
            "next_inspection_date",
            "report",
            "notes",
            "registration_certificate",
            "certificate_type",
            "certificate_issued_at",
            "certificate_valid_until",
            "certificate_photo_front",
            "certificate_photo_back",
            "certificate_notes",
            "certificate_id",
            "created_by",
            "created_at",
            "linked_expense",
        ]
        read_only_fields = [
            "id",
            "registration_certificate",
            "created_by",
            "created_at",
            "linked_expense",
        ]

    def get_linked_expense(self, obj):
        detail = getattr(obj, "expense_detail", None)
        if not detail:
            return None
        expense = detail.expense
        invoice = expense.invoice
        return LinkedExpenseSerializer(
            {
                "id": expense.id,
                "amount": expense.amount,
                "official_cost": detail.official_cost,
                "additional_cost": detail.additional_cost,
                "payment_method": expense.payment_method,
                "receipt": media_url(expense.receipt.url) if expense.receipt else None,
                "registration_certificate": media_url(
                    detail.registration_certificate.url
                )
                if detail.registration_certificate
                else None,
                "invoice_number": invoice.number if invoice else None,
                "invoice_file": media_url(invoice.file.url)
                if invoice and invoice.file
                else None,
                "expense_date": expense.expense_date,
            }
        ).data

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

        # If any certificate field is provided on create, require both photos.
        # If certificate_id is provided, photos are not required.
        cert_fields = (
            "certificate_type",
            "certificate_issued_at",
            "certificate_photo_front",
            "certificate_photo_back",
        )
        has_any_cert_field = any(data.get(f) for f in cert_fields)
        has_cert_id = bool(data.get("certificate_id"))
        if has_any_cert_field and has_cert_id:
            raise serializers.ValidationError(
                {
                    "certificate_id": (
                        "Pass either certificate_id OR certificate_* fields, "
                        "not both."
                    )
                }
            )
        if has_any_cert_field and not self.instance:
            errors = {}
            if not data.get("certificate_photo_front"):
                errors["certificate_photo_front"] = "This field is required."
            if not data.get("certificate_photo_back"):
                errors["certificate_photo_back"] = "This field is required."
            if not data.get("certificate_issued_at"):
                errors["certificate_issued_at"] = "This field is required."
            if errors:
                raise serializers.ValidationError(errors)

            cert_type = data.get("certificate_type", CertificateType.PERMANENT)
            issued_at = data.get("certificate_issued_at")
            if cert_type == CertificateType.TEMPORARY and not data.get(
                "certificate_valid_until"
            ):
                data["certificate_valid_until"] = (
                    issued_at + relativedelta(months=1) if issued_at else None
                )
            valid_until = data.get("certificate_valid_until")
            if (
                cert_type == CertificateType.TEMPORARY
                and issued_at
                and valid_until
                and valid_until <= issued_at
            ):
                raise serializers.ValidationError(
                    {
                        "certificate_valid_until": "Expiry must be after the issue date."
                    }
                )
        return data

    @transaction.atomic
    def create(self, validated_data):
        cert_type = validated_data.pop("certificate_type", None)
        cert_issued_at = validated_data.pop("certificate_issued_at", None)
        cert_valid_until = validated_data.pop("certificate_valid_until", None)
        cert_photo_front = validated_data.pop("certificate_photo_front", None)
        cert_photo_back = validated_data.pop("certificate_photo_back", None)
        cert_notes = validated_data.pop("certificate_notes", "")
        cert_id = validated_data.pop("certificate_id", None)

        inspection = TechnicalInspection.objects.create(**validated_data)

        # Branch 1: link an existing certificate
        if cert_id:
            try:
                existing = RegistrationCertificate.objects.get(
                    pk=cert_id, vehicle=inspection.vehicle
                )
            except RegistrationCertificate.DoesNotExist as err:
                raise serializers.ValidationError(
                    {"certificate_id": "Certificate not found for this vehicle."}
                ) from err
            inspection.registration_certificate = existing
            inspection.save(update_fields=["registration_certificate"])
            return inspection

        # Branch 2: create a fresh certificate inline
        if cert_photo_front and cert_photo_back and cert_issued_at:
            vehicle = inspection.vehicle
            RegistrationCertificate.objects.filter(
                vehicle=vehicle, is_active=True
            ).update(is_active=False)
            certificate = RegistrationCertificate.objects.create(
                vehicle=vehicle,
                certificate_type=cert_type or CertificateType.PERMANENT,
                issued_at=cert_issued_at,
                valid_until=cert_valid_until,
                notes=cert_notes,
                is_active=True,
                created_by=validated_data.get("created_by"),
            )
            RegistrationCertificatePhoto.objects.create(
                certificate=certificate,
                side=RegistrationCertificatePhoto.Side.FRONT,
                image=cert_photo_front,
            )
            RegistrationCertificatePhoto.objects.create(
                certificate=certificate,
                side=RegistrationCertificatePhoto.Side.BACK,
                image=cert_photo_back,
            )
            inspection.registration_certificate = certificate
            inspection.save(update_fields=["registration_certificate"])
        return inspection

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
            "distance_unit",
            "tire_size",
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

    def validate_year(self, value):
        if value is None:
            return value
        max_year = date.today().year + 1
        if value < 1900 or value > max_year:
            raise serializers.ValidationError(
                f"Year must be between 1900 and {max_year}."
            )
        return value

    @staticmethod
    def _compute_expiry(inspection_date):
        try:
            return inspection_date.replace(year=inspection_date.year + 1)
        except ValueError:
            return inspection_date.replace(year=inspection_date.year + 1, day=28)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Driver from DriverVehicleDeal (prefetched via deals or queried)
        deals = getattr(instance, "_prefetched_objects_cache", {}).get("deals")
        if deals is not None:
            deal = deals[0] if deals else None
        else:
            deal = (
                DriverVehicleDeal.objects.filter(
                    vehicle=instance, deal__status="active"
                )
                .select_related("driver", "deal")
                .first()
            )

        if deal:
            representation["driver"] = {
                "id": str(deal.driver.id),
                "first_name": deal.driver.first_name,
                "last_name": deal.driver.last_name,
                "phone_number": deal.driver.phone_number,
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

        # Equipment counts (from DB annotations when available, fallback to Python)
        if hasattr(instance, "equipment_total_count"):
            representation["equipment_total"] = instance.equipment_total_count
            representation["equipment_equipped"] = instance.equipment_equipped_count
        else:
            eq_list = list(instance.equipment_list.all())
            representation["equipment_total"] = len(eq_list)
            representation["equipment_equipped"] = sum(
                1 for e in eq_list if e.is_equipped
            )

        # Regulation (from DB annotations when available, fallback to Python)
        if hasattr(instance, "has_regulation_flag"):
            representation["has_regulation"] = instance.has_regulation_flag
            representation["regulation_overdue"] = instance.regulation_overdue_count
        else:
            regs = list(instance.regulations.all())
            representation["has_regulation"] = len(regs) > 0
            overdue = 0
            current_km = instance.initial_km
            for reg in regs:
                for entry in reg.entries.all():
                    if current_km >= entry.last_done_km + entry.effective_every_km:
                        overdue += 1
            representation["regulation_overdue"] = overdue

        # Total cost = purchase price + all expenses
        expenses_total = getattr(instance, "expenses_total", None) or Decimal("0")
        representation["expenses_total"] = str(expenses_total)
        representation["total_cost"] = str(instance.cost + expenses_total)

        # Active registration certificate (тех паспорт)
        active_cert = next(
            (
                c
                for c in instance.registration_certificates.all()
                if c.is_active
            ),
            None,
        ) if "registration_certificates" in getattr(
            instance, "_prefetched_objects_cache", {}
        ) else (
            instance.registration_certificates.filter(is_active=True)
            .prefetch_related("photos")
            .first()
        )
        if active_cert:
            representation["active_certificate"] = (
                RegistrationCertificateSerializer(active_cert).data
            )
            if active_cert.certificate_type == CertificateType.TEMPORARY and active_cert.valid_until:
                representation["certificate_days_left"] = (
                    active_cert.valid_until - date.today()
                ).days
            else:
                representation["certificate_days_left"] = None
        else:
            representation["active_certificate"] = None
            representation["certificate_days_left"] = None

        return representation


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
