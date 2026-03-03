import json
from urllib.parse import urlparse

from django.db import transaction
from rest_framework import serializers

from .models import (
    Expense,
    ExpenseCategory,
    ExpenseInvoice,
    ExpensePart,
    FineExpenseDetail,
    FuelExpenseDetail,
    InspectionExpenseDetail,
    PartsExpenseDetail,
    ServiceExpenseDetail,
    ServiceItem,
    WashingExpenseDetail,
)

# ── Detail map: category code → (model, fields, required) ──

DETAIL_MAP = {
    "FUEL": {
        "model": FuelExpenseDetail,
        "fields": ["liters", "fuel_type"],
        "required": ["liters", "fuel_type"],
    },
    "SERVICE": {
        "model": ServiceExpenseDetail,
        "fields": ["service"],
        "required": [],
    },
    "WASHING": {
        "model": WashingExpenseDetail,
        "fields": ["wash_type"],
        "required": ["wash_type"],
    },
    "FINES": {
        "model": FineExpenseDetail,
        "fields": [
            "fine_number",
            "violation_type",
            "fine_date",
            "driver_at_time",
        ],
        "required": ["violation_type"],
    },
    "INSPECTION": {
        "model": InspectionExpenseDetail,
        "fields": [
            "inspection_date",
            "official_cost",
            "additional_cost",
            "next_inspection_date",
        ],
        "required": ["inspection_date", "official_cost"],
    },
    "PARTS": {
        "model": PartsExpenseDetail,
        "fields": ["source_name", "supplier_type"],
        "required": [],
    },
}

ALL_DETAIL_FIELDS = {f for cfg in DETAIL_MAP.values() for f in cfg["fields"]}


# ── Lightweight serializers ──


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = [
            "id",
            "code",
            "name",
            "icon",
            "color",
            "is_system",
            "is_active",
            "order",
        ]
        read_only_fields = ["id", "is_system"]


class ExpensePartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpensePart
        fields = ["id", "name", "quantity", "unit_price"]
        read_only_fields = ["id"]


class ExpenseInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseInvoice
        fields = ["id", "file", "name", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        file_url = rep.get("file") or ""
        if file_url:
            rep["file"] = urlparse(file_url).path
        return rep


class ServiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceItem
        fields = ["id", "name", "price"]
        read_only_fields = ["id"]


# ── Main expense serializer ──


class ExpenseSerializer(serializers.ModelSerializer):
    # Category read-only fields
    category_code = serializers.CharField(source="category.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_icon = serializers.CharField(source="category.icon", read_only=True)
    category_color = serializers.CharField(source="category.color", read_only=True)
    vehicle_car_number = serializers.CharField(
        source="vehicle.car_number", read_only=True
    )
    vehicle_vin_number = serializers.CharField(
        source="vehicle.vin_number", read_only=True
    )

    # Amount: not required — auto-computed for SERVICE / PARTS / INSPECTION
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    # FUEL detail fields
    liters = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )
    fuel_type = serializers.CharField(required=False, allow_blank=True)

    # SERVICE detail fields
    service = serializers.PrimaryKeyRelatedField(
        read_only=True, required=False, allow_null=True
    )
    service_name = serializers.CharField(
        source="service_detail.service.name", read_only=True, default=""
    )

    # WASHING detail fields
    wash_type = serializers.CharField(required=False, allow_blank=True)

    # FINES detail fields
    fine_number = serializers.CharField(required=False, allow_blank=True)
    violation_type = serializers.CharField(required=False, allow_blank=True)
    fine_date = serializers.DateField(required=False, allow_null=True)
    driver_at_time = serializers.PrimaryKeyRelatedField(
        read_only=True, required=False, allow_null=True
    )

    # INSPECTION detail fields
    inspection_date = serializers.DateField(required=False, allow_null=True)
    official_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    additional_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    next_inspection_date = serializers.DateField(required=False, allow_null=True)

    # PARTS detail fields
    source_name = serializers.CharField(required=False, allow_blank=True)
    supplier_type = serializers.CharField(required=False, allow_blank=True)

    # PARTS — read-only nested output
    parts = ExpensePartSerializer(many=True, read_only=True)
    invoices = ExpenseInvoiceSerializer(many=True, read_only=True)

    # SERVICE items — read-only nested output
    service_items = ServiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "vehicle",
            "vehicle_car_number",
            "vehicle_vin_number",
            "category",
            "category_code",
            "category_name",
            "category_icon",
            "category_color",
            "amount",
            "expense_date",
            "receipt",
            "payment_method",
            "payer_type",
            "expense_for",
            # FUEL
            "liters",
            "fuel_type",
            # SERVICE
            "service",
            "service_name",
            "service_items",
            # WASHING
            "wash_type",
            # FINES
            "fine_number",
            "violation_type",
            "fine_date",
            "driver_at_time",
            # INSPECTION
            "inspection_date",
            "official_cost",
            "additional_cost",
            "next_inspection_date",
            # PARTS
            "source_name",
            "supplier_type",
            "parts",
            "invoices",
            # Meta
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vehicle_car_number",
            "vehicle_vin_number",
            "category_code",
            "category_name",
            "category_icon",
            "category_color",
            "service_name",
            "service_items",
            "parts",
            "invoices",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from driver.models import Driver
        from fleet_management.models import FleetService

        self.fields["driver_at_time"] = serializers.PrimaryKeyRelatedField(
            queryset=Driver.objects.all(), required=False, allow_null=True
        )
        self.fields["service"] = serializers.PrimaryKeyRelatedField(
            queryset=FleetService.objects.all(), required=False, allow_null=True
        )

    # ── Helpers ──

    def _get_category_code(self, data):
        category = data.get("category")
        if category:
            if hasattr(category, "code"):
                return category.code
            return (
                ExpenseCategory.objects.filter(pk=category)
                .values_list("code", flat=True)
                .first()
            )
        if self.instance:
            return self.instance.category.code
        return None

    # ── Validation ──

    def validate(self, data):
        code = self._get_category_code(data)

        # Auto-computed categories: amount derived from line items
        if (
            code in ("SERVICE", "PARTS", "INSPECTION", "ACCESSORIES", "DOCUMENTS")
            and "amount" not in data
        ):
            data["amount"] = 0

        # Type-specific required fields
        cfg = DETAIL_MAP.get(code)
        if cfg:
            for field in cfg["required"]:
                val = data.get(field)
                if val is None or val == "":
                    raise serializers.ValidationError(
                        {field: f"Required for {code} expenses."}
                    )

        # Parts: parse JSON string from FormData (PARTS, ACCESSORIES, DOCUMENTS)
        if code in ("PARTS", "ACCESSORIES", "DOCUMENTS"):
            parts_raw = self.initial_data.get("parts_json")
            if parts_raw and isinstance(parts_raw, str):
                try:
                    data["_parts"] = json.loads(parts_raw)
                except (json.JSONDecodeError, TypeError):
                    raise serializers.ValidationError(
                        {"parts_json": "Invalid JSON."}
                    ) from None

        # Service items: parse JSON string from FormData
        if code == "SERVICE":
            items_raw = self.initial_data.get("service_items_json")
            if items_raw and isinstance(items_raw, str):
                try:
                    data["_service_items"] = json.loads(items_raw)
                except (json.JSONDecodeError, TypeError):
                    raise serializers.ValidationError(
                        {"service_items_json": "Invalid JSON."}
                    ) from None

        return data

    # ── Create / Update ──

    def _extract_detail_data(self, validated_data):
        detail_data = {}
        for field_name in ALL_DETAIL_FIELDS:
            if field_name in validated_data:
                detail_data[field_name] = validated_data.pop(field_name)
        return detail_data

    def _save_detail(self, expense, detail_data):
        code = expense.category.code
        cfg = DETAIL_MAP.get(code)
        if cfg is None:
            return
        model_cls = cfg["model"]
        model_fields = {k: v for k, v in detail_data.items() if k in cfg["fields"]}
        model_cls.objects.update_or_create(expense=expense, defaults=model_fields)

    def _save_parts(self, expense, validated_data):
        parts_data = validated_data.pop("_parts", None)
        if parts_data is None:
            return
        expense.parts.all().delete()
        for part in parts_data:
            ExpensePart.objects.create(
                expense=expense,
                name=part.get("name", ""),
                quantity=part.get("quantity", 1),
                unit_price=part.get("unit_price", 0),
            )

    def _save_service_items(self, expense, validated_data):
        items_data = validated_data.pop("_service_items", None)
        if items_data is None:
            return
        expense.service_items.all().delete()
        for item in items_data:
            ServiceItem.objects.create(
                expense=expense,
                name=item.get("name", ""),
                price=item.get("price", 0),
            )

    def _create_linked_inspection(self, expense, detail_data):
        from vehicle.models import TechnicalInspection

        inspection_date = detail_data.get("inspection_date")
        if not inspection_date:
            return

        next_date = detail_data.get("next_inspection_date")
        if not next_date:
            try:
                next_date = inspection_date.replace(year=inspection_date.year + 1)
            except ValueError:
                next_date = inspection_date.replace(
                    year=inspection_date.year + 1, day=28
                )

        inspection = TechnicalInspection.objects.create(
            vehicle=expense.vehicle,
            inspection_date=inspection_date,
            next_inspection_date=next_date,
            notes=f"Auto-created from expense #{expense.id}",
        )

        detail = getattr(expense, "inspection_detail", None)
        if detail:
            detail.linked_inspection = inspection
            detail.save(update_fields=["linked_inspection"])

    def _update_linked_inspection(self, expense, detail_data):
        detail = getattr(expense, "inspection_detail", None)
        if not detail or not detail.linked_inspection_id:
            return

        inspection = detail.linked_inspection
        changed = False
        if "inspection_date" in detail_data and detail_data["inspection_date"]:
            inspection.inspection_date = detail_data["inspection_date"]
            changed = True
        if (
            "next_inspection_date" in detail_data
            and detail_data["next_inspection_date"]
        ):
            inspection.next_inspection_date = detail_data["next_inspection_date"]
            changed = True
        if changed:
            inspection.save()

    def _save_invoices(self, expense, request):
        files = request.FILES.getlist("invoice_files")
        if not files:
            return
        for f in files:
            ExpenseInvoice.objects.create(expense=expense, file=f, name=f.name)

    @transaction.atomic
    def create(self, validated_data):
        detail_data = self._extract_detail_data(validated_data)
        parts_data = validated_data.pop("_parts", None)
        service_items_data = validated_data.pop("_service_items", None)

        # Auto-computed categories: placeholder amount — will be recomputed from items
        code = self._get_category_code(validated_data)
        auto_amount_codes = (
            "SERVICE",
            "PARTS",
            "INSPECTION",
            "ACCESSORIES",
            "DOCUMENTS",
        )
        if code in auto_amount_codes:
            validated_data.setdefault("amount", 0)

        expense = Expense.objects.create(**validated_data)
        self._save_detail(expense, detail_data)
        if parts_data is not None:
            self._save_parts(expense, {"_parts": parts_data})
        if service_items_data is not None:
            self._save_service_items(expense, {"_service_items": service_items_data})

        # Recompute amount from line items
        if code in auto_amount_codes:
            expense.amount = expense.computed_amount
            expense.save(update_fields=["amount"])

        # Auto-create TechnicalInspection for INSPECTION expenses
        if code == "INSPECTION":
            self._create_linked_inspection(expense, detail_data)

        request = self.context.get("request")
        if request:
            self._save_invoices(expense, request)
        return expense

    @transaction.atomic
    def update(self, instance, validated_data):
        detail_data = self._extract_detail_data(validated_data)
        parts_data = validated_data.pop("_parts", None)
        service_items_data = validated_data.pop("_service_items", None)

        old_code = instance.category.code
        new_category = validated_data.get("category")
        new_code = new_category.code if new_category else old_code

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # If category changed, delete old detail
        if old_code != new_code and old_code:
            old_cfg = DETAIL_MAP.get(old_code)
            if old_cfg:
                old_cfg["model"].objects.filter(expense=instance).delete()

        self._save_detail(instance, detail_data)
        if parts_data is not None:
            self._save_parts(instance, {"_parts": parts_data})
        if service_items_data is not None:
            self._save_service_items(instance, {"_service_items": service_items_data})

        # Recompute amount from line items
        if new_code in ("SERVICE", "PARTS", "INSPECTION", "ACCESSORIES", "DOCUMENTS"):
            instance.amount = instance.computed_amount
            instance.save(update_fields=["amount"])

        # Sync linked TechnicalInspection for INSPECTION expenses
        if new_code == "INSPECTION":
            self._update_linked_inspection(instance, detail_data)

        request = self.context.get("request")
        if request and request.FILES.getlist("invoice_files"):
            self._save_invoices(instance, request)
        return instance

    # ── Representation (flatten detail fields) ──

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Receipt: path-only
        receipt_url = rep.get("receipt") or ""
        if receipt_url:
            rep["receipt"] = urlparse(receipt_url).path

        code = instance.category.code if instance.category_id else None

        # Flatten detail fields
        cfg = DETAIL_MAP.get(code)
        if cfg:
            related_name = cfg["model"]._meta.get_field("expense").related_query_name()
            detail_obj = getattr(instance, related_name, None)
            if detail_obj:
                for field_name in cfg["fields"]:
                    val = getattr(detail_obj, field_name, None)
                    if field_name == "driver_at_time":
                        rep[field_name] = str(val.pk) if val else None
                    elif field_name == "service":
                        rep[field_name] = val.pk if val else None
                        rep["service_name"] = val.name if val else ""
                    else:
                        rep[field_name] = val
            else:
                for field_name in cfg["fields"]:
                    rep[field_name] = None
                if code == "SERVICE":
                    rep["service_name"] = ""
        else:
            for field_name in ALL_DETAIL_FIELDS:
                rep[field_name] = None
            rep["service_name"] = ""

        return rep
