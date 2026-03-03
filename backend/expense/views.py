import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config import cache_utils

from .filters import ExpenseFilter
from .models import Expense, ExpenseCategory
from .serializers import ExpenseCategorySerializer, ExpenseSerializer

logger = logging.getLogger(__name__)


def _expense_queryset():
    return Expense.objects.select_related(
        "vehicle",
        "created_by",
        "category",
        "service_detail__service",
        "inspection_detail",
        "inspection_detail__linked_inspection",
        "parts_detail",
    ).prefetch_related("parts", "invoices", "service_items")


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
    ordering = ["-expense_date"]

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_expense_list(request.query_params)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_expense_list(request.query_params, response.data)
        return response

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        cache_utils.invalidate_expense()
        cache_utils.invalidate_vehicle()
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
        instance = serializer.save()
        cache_utils.invalidate_expense(instance.id)
        cache_utils.invalidate_vehicle()
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


class VehicleExpenseListCreateView(generics.ListCreateAPIView):
    """GET /vehicle/{pk}/expenses/ — expenses for one vehicle.
    POST /vehicle/{pk}/expenses/ — create expense scoped to this vehicle."""

    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ExpenseFilter
    ordering_fields = ["expense_date", "amount", "created_at"]
    ordering = ["-expense_date"]

    def get_queryset(self):
        return _expense_queryset().filter(vehicle_id=self.kwargs["pk"])

    def get_serializer(self, *args, **kwargs):
        if self.request.method == "POST":
            data = kwargs.get("data")
            if data is not None:
                mutable = data.copy() if hasattr(data, "copy") else dict(data)
                mutable["vehicle"] = self.kwargs["pk"]
                kwargs["data"] = mutable
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
