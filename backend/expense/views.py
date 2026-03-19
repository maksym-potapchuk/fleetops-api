import logging

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config import cache_utils
from config.filters import LayoutAwareSearchFilter as SearchFilter

from .filters import ExpenseFilter
from .models import Expense, ExpenseCategory, Invoice
from .serializers import (
    ExpenseCategorySerializer,
    ExpenseSerializer,
    InvoiceSearchSerializer,
)

logger = logging.getLogger(__name__)


def _expense_queryset():
    return Expense.objects.select_related(
        "vehicle",
        "created_by",
        "edited_by",
        "category",
        "client_driver",
        "service_detail__service",
        "inspection_detail",
        "inspection_detail__linked_inspection",
        "parts_detail",
        "invoice",
    ).prefetch_related("parts", "service_items")


class ExpenseCategoryListView(generics.ListAPIView):
    """GET /expense/categories/ — active categories for UI dropdown."""

    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return ExpenseCategory.objects.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_category_list()
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_category_list(response.data)
        return response


class ExpenseListCreateView(generics.ListCreateAPIView):
    """GET /expense/ — list all expenses (paginated, filtered).
    POST /expense/ — create a new expense (vehicle + category in body)."""

    queryset = _expense_queryset()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ExpenseFilter
    search_fields = ["vehicle__car_number", "vehicle__manufacturer", "vehicle__model"]
    ordering_fields = ["expense_date", "amount", "created_at"]
    ordering = ["-created_at"]

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_expense_list(request.query_params)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_expense_list(request.query_params, response.data)
        return response

    def perform_create(self, serializer):
        instance = serializer.save(
            created_by=self.request.user,
            edited_by=self.request.user,
        )
        cache_utils.invalidate_expense()
        cache_utils.invalidate_vehicle(instance.vehicle_id)
        logger.info(
            "Expense created",
            extra={
                "status_code": 201,
                "operation_type": "EXPENSE_CREATE",
                "service": "DJANGO",
                "expense_id": str(instance.id),
                "category": instance.category.code or instance.category.name,
                "vehicle_id": str(instance.vehicle_id),
                "user_id": str(self.request.user.id),
            },
        )


class ExpenseRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /expense/{id}/"""

    queryset = _expense_queryset()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "patch", "delete"]

    def retrieve(self, request, *args, **kwargs):
        expense_id = self.kwargs["pk"]
        cached = cache_utils.get_expense_detail(expense_id)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        cache_utils.set_expense_detail(expense_id, response.data)
        return response

    def perform_update(self, serializer):
        instance = serializer.save(edited_by=self.request.user)
        cache_utils.invalidate_expense(instance.id)
        cache_utils.invalidate_vehicle(instance.vehicle_id)
        logger.info(
            "Expense updated",
            extra={
                "operation_type": "EXPENSE_UPDATE",
                "service": "DJANGO",
                "expense_id": str(instance.id),
                "user_id": str(self.request.user.id),
            },
        )

    def perform_destroy(self, instance):
        expense_id = instance.id
        vehicle_id = instance.vehicle_id
        # Delete linked TechnicalInspection for INSPECTION expenses
        if instance.category.code == "INSPECTION":
            detail = getattr(instance, "inspection_detail", None)
            if detail and detail.linked_inspection_id:
                detail.linked_inspection.delete()
        instance.delete()
        cache_utils.invalidate_expense(expense_id)
        cache_utils.invalidate_vehicle(vehicle_id)
        logger.info(
            "Expense deleted",
            extra={
                "operation_type": "EXPENSE_DELETE",
                "service": "DJANGO",
                "expense_id": str(expense_id),
                "user_id": str(self.request.user.id),
            },
        )


class InvoiceSearchView(generics.ListAPIView):
    """GET /expense/invoices/?search=FAK-123 — search invoices by number."""

    serializer_class = InvoiceSearchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    filter_backends = [SearchFilter]
    search_fields = ["number", "vendor_name"]

    def get_queryset(self):
        from django.db.models import Count

        return Invoice.objects.annotate(_expense_count=Count("expenses")).order_by(
            "-created_at"
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())[:20]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class VehicleExpenseListCreateView(generics.ListCreateAPIView):
    """GET /vehicle/{pk}/expenses/ — expenses for one vehicle.
    POST /vehicle/{pk}/expenses/ — create expense scoped to this vehicle."""

    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ExpenseFilter
    ordering_fields = ["expense_date", "amount", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return _expense_queryset().filter(vehicle_id=self.kwargs["pk"])

    def get_serializer(self, *args, **kwargs):
        if self.request.method == "POST":
            data = kwargs.get("data")
            if data is not None:
                if hasattr(data, "_mutable"):
                    data._mutable = True
                    data["vehicle"] = self.kwargs["pk"]
                    data._mutable = False
                else:
                    data["vehicle"] = self.kwargs["pk"]
                kwargs["data"] = data
        return super().get_serializer(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_expense_list(
            {**request.query_params.dict(), "_v": str(self.kwargs["pk"])}
        )
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_expense_list(
            {**request.query_params.dict(), "_v": str(self.kwargs["pk"])},
            response.data,
        )
        return response

    def perform_create(self, serializer):
        instance = serializer.save(
            vehicle_id=self.kwargs["pk"],
            created_by=self.request.user,
            edited_by=self.request.user,
        )
        cache_utils.invalidate_expense()
        cache_utils.invalidate_vehicle(self.kwargs["pk"])
        logger.info(
            "Vehicle expense created",
            extra={
                "operation_type": "VEHICLE_EXPENSE_CREATE",
                "service": "DJANGO",
                "expense_id": str(instance.id),
                "vehicle_id": str(self.kwargs["pk"]),
                "user_id": str(self.request.user.id),
            },
        )


class VehicleExpenseSummaryView(APIView):
    """GET /vehicle/{pk}/expenses/summary/ — per-category totals."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        qs = Expense.objects.filter(vehicle_id=pk)

        # Main summary — only expenses that count toward vehicle cost
        rows = (
            qs.filter(exclude_from_cost=False)
            .values(
                "category__code", "category__name", "category__icon", "category__color"
            )
            .annotate(
                total=Coalesce(Sum("amount"), Value(0, output_field=DecimalField()))
            )
            .order_by("-total")
        )
        categories = []
        grand_total = 0
        for row in rows:
            total = float(row["total"])
            grand_total += total
            categories.append(
                {
                    "code": row["category__code"],
                    "name": row["category__name"],
                    "icon": row["category__icon"],
                    "color": row["category__color"],
                    "total": f"{total:.2f}",
                }
            )

        # Excluded expenses total (client-only, not in vehicle cost)
        excluded = qs.filter(exclude_from_cost=True).aggregate(
            total=Coalesce(Sum("amount"), Value(0, output_field=DecimalField()))
        )
        excluded_total = float(excluded["total"])

        return Response(
            {
                "total": f"{grand_total:.2f}",
                "excluded_total": f"{excluded_total:.2f}",
                "categories": categories,
            }
        )
