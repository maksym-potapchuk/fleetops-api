import django_filters

from .models import Expense


class ExpenseFilter(django_filters.FilterSet):
    category = django_filters.UUIDFilter(field_name="category_id")
    category_code = django_filters.CharFilter(field_name="category__code")
    vehicle = django_filters.UUIDFilter(field_name="vehicle_id")
    date_from = django_filters.DateFilter(
        field_name="expense_date", lookup_expr="date__gte"
    )
    date_to = django_filters.DateFilter(
        field_name="expense_date", lookup_expr="date__lte"
    )
    min_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    payment_method = django_filters.CharFilter(field_name="payment_method")
    payer_type = django_filters.CharFilter(field_name="payer_type")
    approval_status = django_filters.CharFilter(field_name="approval_status")

    class Meta:
        model = Expense
        fields = [
            "category",
            "category_code",
            "vehicle",
            "date_from",
            "date_to",
            "min_amount",
            "max_amount",
            "payment_method",
            "payer_type",
            "approval_status",
        ]
