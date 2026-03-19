import json
import logging
import os

from django.db import transaction
from rest_framework import serializers

from config.storage_utils import media_url

from .constants import ALLOWED_INVOICE_EXTENSIONS, ApprovalStatus, FuelType, PayerType
from .models import (
    Expense,
    ExpenseCategory,
    ExpensePart,
    FineExpenseDetail,
    FuelExpenseDetail,
    InspectionExpenseDetail,
    Invoice,
    PartsExpenseDetail,
    ServiceExpenseDetail,
    ServiceItem,
    WashingExpenseDetail,
)

logger = logging.getLogger(__name__)

# ── Detail map: category code → (model, fields, required) ──

DETAIL_MAP = {
    "FUEL": {
        "model": FuelExpenseDetail,
        "fields": ["fuel_types"],
        "required": ["fuel_types"],
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
            "registration_certificate",
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


class InvoiceSerializer(serializers.ModelSerializer):
    expense_count = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "file",
            "vendor_name",
            "invoice_date",
            "total_amount",
            "expense_count",
            "created_at",
        ]
        read_only_fields = ["id", "expense_count", "created_at"]

    def get_expense_count(self, obj):
        return obj.expenses.count()

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        file_url = rep.get("file") or ""
        if file_url:
            rep["file"] = media_url(file_url)
        return rep


class InvoiceSearchSerializer(serializers.ModelSerializer):
    expense_count = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "vendor_name",
            "invoice_date",
            "total_amount",
            "expense_count",
        ]

    def get_expense_count(self, obj):
        if hasattr(obj, "_expense_count"):
            return obj._expense_count
        return obj.expenses.count()


class ServiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceItem
        fields = ["id", "name", "price"]
        read_only_fields = ["id"]


# ── Main expense serializer ──


class ExpenseUserSerializer(serializers.ModelSerializer):
    class Meta:
        from account.models import User

        model = User
        fields = ["id", "username", "email", "color"]


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
    created_by = ExpenseUserSerializer(read_only=True)
    edited_by = ExpenseUserSerializer(read_only=True)

    # Amount: writable primary field
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    # FUEL detail fields
    fuel_types = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )

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
    registration_certificate = serializers.FileField(required=False, allow_null=True)

    # PARTS detail fields
    source_name = serializers.CharField(required=False, allow_blank=True)
    supplier_type = serializers.CharField(required=False, allow_blank=True)

    # PARTS — read-only nested output
    parts = ExpensePartSerializer(many=True, read_only=True)

    # SERVICE items — read-only nested output
    service_items = ServiceItemSerializer(many=True, read_only=True)

    # Cost splitting (CLIENT payer only)
    company_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    client_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    client_driver = serializers.PrimaryKeyRelatedField(
        read_only=True, required=False, allow_null=True
    )
    client_driver_name = serializers.SerializerMethodField()
    approval_status = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    # Exclude from vehicle cost (CLIENT payer only)
    exclude_from_cost = serializers.BooleanField(required=False, default=False)

    # Invoice
    invoice_number = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )
    invoice_data = InvoiceSerializer(source="invoice", read_only=True)
    invoice_existing = serializers.SerializerMethodField()

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
            # Cost splitting
            "company_amount",
            "client_amount",
            "client_driver",
            "client_driver_name",
            "approval_status",
            "exclude_from_cost",
            # FUEL
            "fuel_types",
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
            "registration_certificate",
            # PARTS
            "source_name",
            "supplier_type",
            "parts",
            # Invoice
            "invoice",
            "invoice_number",
            "invoice_data",
            "invoice_existing",
            # Meta
            "created_by",
            "edited_by",
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
            "invoice_data",
            "invoice_existing",
            "client_driver_name",
            "created_by",
            "edited_by",
            "created_at",
            "updated_at",
        ]

    def get_invoice_existing(self, obj):
        return getattr(obj, "_invoice_existing", False)

    def get_client_driver_name(self, obj):
        driver = obj.client_driver
        if driver:
            return f"{driver.first_name} {driver.last_name}".strip()
        return None

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
        self.fields["client_driver"] = serializers.PrimaryKeyRelatedField(
            queryset=Driver.objects.all(), required=False, allow_null=True
        )

    # DRF run_validators() calls copy.deepcopy(value) which fails on
    # TemporaryUploadedFile (large uploads stored on disk as BufferedRandom).
    # We pop file fields before deepcopy and restore them after.
    _FILE_FIELDS = ("receipt", "invoice_file", "registration_certificate")

    def run_validators(self, value):
        files = {k: value.pop(k) for k in self._FILE_FIELDS if k in value}
        super().run_validators(value)
        value.update(files)

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

        # Type-specific required fields
        cfg = DETAIL_MAP.get(code)
        if cfg:
            for field in cfg["required"]:
                val = data.get(field)
                if val is None or val == "" or val == []:
                    raise serializers.ValidationError(
                        {field: f"Required for {code} expenses."}
                    )

        # Fuel types: parse JSON string from FormData & validate values
        if code == "FUEL":
            ft = data.get("fuel_types")
            if isinstance(ft, str):
                try:
                    data["fuel_types"] = json.loads(ft)
                except (json.JSONDecodeError, TypeError):
                    data["fuel_types"] = [ft] if ft else []
            elif isinstance(ft, list) and len(ft) == 1 and isinstance(ft[0], str):
                try:
                    parsed = json.loads(ft[0])
                    if isinstance(parsed, list):
                        data["fuel_types"] = parsed
                except (json.JSONDecodeError, TypeError):
                    pass
            ft_list = data.get("fuel_types") or []
            if not ft_list:
                raise serializers.ValidationError(
                    {"fuel_types": "Required for FUEL expenses."}
                )
            valid_values = {c.value for c in FuelType}
            invalid = [v for v in ft_list if v not in valid_values]
            if invalid:
                raise serializers.ValidationError(
                    {"fuel_types": f"Invalid fuel types: {', '.join(invalid)}"}
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

        # ── Amount & cost splitting validation ──
        payer_type = data.get("payer_type")
        if payer_type is None and self.instance:
            payer_type = self.instance.payer_type

        auto_amount_codes = (
            "SERVICE",
            "PARTS",
            "INSPECTION",
            "ACCESSORIES",
            "DOCUMENTS",
        )

        if payer_type == PayerType.COMPANY:
            # COMPANY: amount is the primary field, clear split fields
            data["company_amount"] = None
            data["client_amount"] = None
            data["client_driver"] = None
            data["approval_status"] = None
            data["exclude_from_cost"] = False
            # amount required on create (except auto-computed)
            if (
                self.instance is None
                and data.get("amount") is None
                and code not in auto_amount_codes
            ):
                raise serializers.ValidationError({"amount": "Required."})
            amt = data.get("amount")
            if amt is not None and amt < 0:
                raise serializers.ValidationError({"amount": "Must be >= 0."})
        elif payer_type == PayerType.CLIENT:
            company_amt = data.get("company_amount")
            client_amt = data.get("client_amount")
            if self.instance is None:
                if company_amt is None or client_amt is None:
                    raise serializers.ValidationError(
                        {"company_amount": "Required when payer_type is CLIENT."}
                    )
            if company_amt is not None and company_amt < 0:
                raise serializers.ValidationError({"company_amount": "Must be >= 0."})
            if client_amt is not None and client_amt < 0:
                raise serializers.ValidationError({"client_amount": "Must be >= 0."})
            # Compute amount = company_amount + client_amount
            if company_amt is not None and client_amt is not None:
                data["amount"] = company_amt + client_amt
            # Default approval_status to DRAFT on create
            if self.instance is None and not data.get("approval_status"):
                data["approval_status"] = ApprovalStatus.DRAFT

        # ── Approval status transition validation ──
        new_status = data.get("approval_status")
        if self.instance and new_status and new_status != self.instance.approval_status:
            allowed_transitions = {
                ApprovalStatus.DRAFT: [ApprovalStatus.SENT],
                ApprovalStatus.SENT: [ApprovalStatus.REVIEW, ApprovalStatus.DRAFT],
                ApprovalStatus.REVIEW: [ApprovalStatus.APPROVED],
            }
            old_status = self.instance.approval_status
            allowed = allowed_transitions.get(old_status, [])
            if new_status not in allowed:
                raise serializers.ValidationError(
                    {
                        "approval_status": f"Cannot transition from {old_status} to {new_status}."
                    }
                )

        # Invoice: look up by number
        invoice_number = self.initial_data.get("invoice_number", "").strip()
        if invoice_number:
            existing = Invoice.objects.filter(number=invoice_number).first()
            if existing:
                data["_invoice_obj"] = existing
                data["_invoice_existing"] = True
            else:
                data["_invoice_number"] = invoice_number
                data["_invoice_existing"] = False

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

        # Try to find an existing unlinked inspection with the same date
        existing = TechnicalInspection.objects.filter(
            vehicle=expense.vehicle,
            inspection_date=inspection_date,
            expense_detail__isnull=True,
        ).first()

        if existing:
            inspection = existing
        else:
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
                created_by=expense.created_by,
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

    def _save_invoice(self, expense, invoice_obj, invoice_number, request):
        # Existing invoice found by number
        if invoice_obj:
            expense.invoice = invoice_obj
            expense._invoice_existing = True
            expense.save(update_fields=["invoice"])
            logger.info(
                "Existing invoice attached",
                extra={
                    "operation_type": "INVOICE_ATTACH",
                    "invoice_number": invoice_obj.number,
                    "expense_id": str(expense.id),
                },
            )
            return

        # New invoice: need at least a number
        if not invoice_number or not request:
            return

        file = request.FILES.get("invoice_file")
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ALLOWED_INVOICE_EXTENSIONS:
                allowed = ", ".join(ALLOWED_INVOICE_EXTENSIONS)
                raise serializers.ValidationError(
                    {"invoice_file": f"Unsupported file format. Allowed: {allowed}"}
                )

        invoice = Invoice.objects.create(
            number=invoice_number,
            file=file or "",
            vendor_name=request.data.get("vendor_name", ""),
            invoice_date=request.data.get("invoice_date") or None,
            total_amount=request.data.get("invoice_total_amount") or None,
        )
        expense.invoice = invoice
        expense._invoice_existing = False
        expense.save(update_fields=["invoice"])
        logger.info(
            "New invoice created",
            extra={
                "operation_type": "INVOICE_CREATE",
                "invoice_number": invoice_number,
                "invoice_id": str(invoice.id),
                "expense_id": str(expense.id),
            },
        )

    @transaction.atomic
    def create(self, validated_data):
        detail_data = self._extract_detail_data(validated_data)
        parts_data = validated_data.pop("_parts", None)
        service_items_data = validated_data.pop("_service_items", None)

        # Pop invoice-related keys before Expense.objects.create()
        validated_data.pop("_invoice_existing", None)
        validated_data.pop("invoice_number", None)
        invoice_obj = validated_data.pop("_invoice_obj", None)
        invoice_number = validated_data.pop("_invoice_number", None)

        # Auto-computed categories: placeholder amount — will be recomputed
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

        # Recompute amount from line items for auto-computed categories
        if code in auto_amount_codes:
            computed = expense.computed_amount
            if expense.payer_type == PayerType.CLIENT:
                # CLIENT: validate split sum matches computed total
                split_sum = (expense.company_amount or 0) + (expense.client_amount or 0)
                if split_sum != computed:
                    raise serializers.ValidationError(
                        {
                            "company_amount": f"company_amount + client_amount must equal {computed}."
                        }
                    )
                expense.amount = computed
                expense.save(update_fields=["amount"])
            else:
                # COMPANY: set amount to computed total
                expense.amount = computed
                expense.save(update_fields=["amount"])

        # Auto-create TechnicalInspection for INSPECTION expenses
        if code == "INSPECTION":
            self._create_linked_inspection(expense, detail_data)

        request = self.context.get("request")
        self._save_invoice(expense, invoice_obj, invoice_number, request)
        return expense

    @transaction.atomic
    def update(self, instance, validated_data):
        detail_data = self._extract_detail_data(validated_data)
        parts_data = validated_data.pop("_parts", None)
        service_items_data = validated_data.pop("_service_items", None)

        # Pop invoice-related keys before setattr loop
        validated_data.pop("_invoice_existing", None)
        validated_data.pop("invoice_number", None)
        invoice_obj = validated_data.pop("_invoice_obj", None)
        invoice_number = validated_data.pop("_invoice_number", None)

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

        # Recompute amount from line items for auto-computed categories
        auto_codes = ("SERVICE", "PARTS", "INSPECTION", "ACCESSORIES", "DOCUMENTS")
        if new_code in auto_codes:
            computed = instance.computed_amount
            if instance.payer_type == PayerType.CLIENT:
                split_sum = (instance.company_amount or 0) + (
                    instance.client_amount or 0
                )
                if split_sum != computed:
                    raise serializers.ValidationError(
                        {
                            "company_amount": f"company_amount + client_amount must equal {computed}."
                        }
                    )
                instance.amount = computed
                instance.save(update_fields=["amount"])
            else:
                instance.amount = computed
                instance.save(update_fields=["amount"])

        # Sync linked TechnicalInspection for INSPECTION expenses
        if new_code == "INSPECTION":
            self._update_linked_inspection(instance, detail_data)

        request = self.context.get("request")
        self._save_invoice(instance, invoice_obj, invoice_number, request)
        return instance

    # ── Representation (flatten detail fields) ──

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        receipt_url = rep.get("receipt") or ""
        if receipt_url:
            rep["receipt"] = media_url(receipt_url)

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
                    elif field_name == "registration_certificate":
                        rep[field_name] = media_url(val.url) if val else None
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
