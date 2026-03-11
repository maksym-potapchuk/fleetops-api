from django.contrib import admin

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

# ── Category admin ──


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_system", "is_active", "order"]
    list_filter = ["is_system", "is_active"]
    list_editable = ["is_active", "order"]

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


# ── Detail inlines ──


class FuelExpenseInline(admin.StackedInline):
    model = FuelExpenseDetail
    extra = 0
    max_num = 1


class ServiceExpenseInline(admin.StackedInline):
    model = ServiceExpenseDetail
    extra = 0
    max_num = 1
    raw_id_fields = ["service"]


class WashingExpenseInline(admin.StackedInline):
    model = WashingExpenseDetail
    extra = 0
    max_num = 1


class FineExpenseInline(admin.StackedInline):
    model = FineExpenseDetail
    extra = 0
    max_num = 1
    raw_id_fields = ["driver_at_time"]


class ExpensePartInline(admin.TabularInline):
    model = ExpensePart
    extra = 1


class InspectionExpenseInline(admin.StackedInline):
    model = InspectionExpenseDetail
    extra = 0
    max_num = 1


class ServiceItemInline(admin.TabularInline):
    model = ServiceItem
    extra = 1


class PartsExpenseDetailInline(admin.StackedInline):
    model = PartsExpenseDetail
    extra = 0
    max_num = 1


_CODE_INLINES = {
    "FUEL": [FuelExpenseInline],
    "SERVICE": [ServiceExpenseInline, ServiceItemInline],
    "PARTS": [PartsExpenseDetailInline, ExpensePartInline],
    "WASHING": [WashingExpenseInline],
    "FINES": [FineExpenseInline],
    "INSPECTION": [InspectionExpenseInline],
}


# ── Invoice admin ──


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "vendor_name",
        "invoice_date",
        "total_amount",
        "created_at",
    ]
    search_fields = ["number", "vendor_name"]
    list_filter = ["invoice_date"]


# ── Expense admin ──


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "vehicle",
        "category",
        "amount",
        "expense_date",
        "payment_method",
        "payer_type",
        "created_by",
    ]
    list_filter = ["category", "expense_date", "payment_method", "payer_type"]
    search_fields = ["vehicle__car_number"]
    raw_id_fields = ["vehicle", "created_by", "invoice"]

    def get_inlines(self, request, obj=None):
        if obj is None:
            return []
        code = obj.category.code if obj.category_id else None
        return _CODE_INLINES.get(code, [])
