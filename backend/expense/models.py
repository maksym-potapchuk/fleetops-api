import os
import uuid

from django.core.exceptions import ValidationError
from django.db import models

from .constants import (
    ALLOWED_INVOICE_EXTENSIONS,
    ApprovalStatus,
    PayerType,
    PaymentMethod,
    SupplierType,
    WashType,
)

# ── Dynamic expense category ──


class ExpenseCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        help_text="System slug (FUEL, SERVICE …). Null for custom categories.",
    )
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(
        max_length=7, blank=True, help_text="Hex color, e.g. #F59E0B"
    )
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Expense Category"
        verbose_name_plural = "Expense Categories"

    def __str__(self) -> str:
        return f"{self.name} ({self.code or 'custom'})"


# ── Base expense ──


class Expense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    invoice = models.ForeignKey(
        "Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    expense_date = models.DateTimeField()
    receipt = models.FileField(upload_to="expenses/receipts/", blank=True, null=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASHLESS,
    )
    payer_type = models.CharField(
        max_length=20,
        choices=PayerType.choices,
        default=PayerType.COMPANY,
    )
    expense_for = models.CharField(max_length=200, blank=True)
    # ── Amounts ──
    # COMPANY: amount = full cost, company_amount / client_amount = NULL
    # CLIENT:  amount = company_amount + client_amount (both required)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    company_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    client_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    client_driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_expenses",
    )
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["vehicle", "category"]),
            models.Index(fields=["expense_date"]),
            models.Index(fields=["approval_status"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.vehicle} — {self.category.name} {self.amount} ({self.expense_date})"
        )

    @property
    def computed_amount(self):
        """Auto-computed amount for SERVICE, PARTS, ACCESSORIES, DOCUMENTS, and INSPECTION."""
        if not self.category_id:
            return self.amount
        code = self.category.code
        if code == "SERVICE":
            return sum(item.price for item in self.service_items.all())
        if code in ("PARTS", "ACCESSORIES", "DOCUMENTS"):
            return sum(p.unit_price * p.quantity for p in self.parts.all())
        if code == "INSPECTION":
            detail = getattr(self, "inspection_detail", None)
            if detail:
                return (detail.official_cost or 0) + (detail.additional_cost or 0)
        return self.amount


class FuelExpenseDetail(models.Model):
    expense = models.OneToOneField(
        Expense, on_delete=models.CASCADE, related_name="fuel_detail"
    )
    liters = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    fuel_types = models.JSONField(
        default=list, help_text="List of fuel types, e.g. ['DIESEL', 'LPG']"
    )

    class Meta:
        verbose_name = "Fuel detail"

    def __str__(self) -> str:
        return f"Fuel: {', '.join(self.fuel_types)}"


class ServiceExpenseDetail(models.Model):
    expense = models.OneToOneField(
        Expense, on_delete=models.CASCADE, related_name="service_detail"
    )
    service = models.ForeignKey(
        "fleet_management.FleetService",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expense_details",
    )

    class Meta:
        verbose_name = "Service detail"

    def __str__(self) -> str:
        return f"Service: {self.service}"


class WashingExpenseDetail(models.Model):
    expense = models.OneToOneField(
        Expense, on_delete=models.CASCADE, related_name="washing_detail"
    )
    wash_type = models.CharField(max_length=20, choices=WashType.choices)

    class Meta:
        verbose_name = "Washing detail"

    def __str__(self) -> str:
        return f"Washing: {self.wash_type}"


class FineExpenseDetail(models.Model):
    expense = models.OneToOneField(
        Expense, on_delete=models.CASCADE, related_name="fine_detail"
    )
    fine_number = models.CharField(max_length=50, blank=True)
    violation_type = models.CharField(max_length=100)
    fine_date = models.DateField(null=True, blank=True)
    driver_at_time = models.ForeignKey(
        "driver.Driver",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fines",
    )

    class Meta:
        verbose_name = "Fine detail"

    def __str__(self) -> str:
        return f"Fine: {self.violation_type}"


class InspectionExpenseDetail(models.Model):
    expense = models.OneToOneField(
        Expense, on_delete=models.CASCADE, related_name="inspection_detail"
    )
    inspection_date = models.DateField()
    official_cost = models.DecimalField(max_digits=10, decimal_places=2)
    additional_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    next_inspection_date = models.DateField(null=True, blank=True)
    registration_certificate = models.FileField(
        upload_to="expenses/certificates/", blank=True, null=True
    )
    linked_inspection = models.OneToOneField(
        "vehicle.TechnicalInspection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_detail",
    )

    class Meta:
        verbose_name = "Inspection detail"

    def __str__(self) -> str:
        return f"Inspection: {self.inspection_date}"


class PartsExpenseDetail(models.Model):
    expense = models.OneToOneField(
        Expense, on_delete=models.CASCADE, related_name="parts_detail"
    )
    source_name = models.CharField(max_length=200, blank=True)
    supplier_type = models.CharField(
        max_length=20,
        choices=SupplierType.choices,
        default=SupplierType.DISASSEMBLY,
    )

    class Meta:
        verbose_name = "Parts detail"

    def __str__(self) -> str:
        return f"Parts: {self.source_name} ({self.supplier_type})"


# ── Parts & Invoices (for PARTS category) ──


class ExpensePart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="parts")
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} x{self.quantity} @ {self.unit_price}"


def validate_invoice_file(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_INVOICE_EXTENSIONS:
        allowed = ", ".join(ALLOWED_INVOICE_EXTENSIONS)
        raise ValidationError(f"Unsupported file format. Allowed: {allowed}")


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=100, unique=True, db_index=True)
    file = models.FileField(
        upload_to="expenses/invoices/",
        validators=[validate_invoice_file],
        blank=True,
    )
    vendor_name = models.CharField(max_length=200, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invoice {self.number}"


class ServiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="service_items"
    )
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} — {self.price}"
