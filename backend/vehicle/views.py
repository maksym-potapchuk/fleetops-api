import logging

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config import cache_utils

from .models import (
    MileageLog,
    TechnicalInspection,
    Vehicle,
    VehicleOwnerHistory,
    VehiclePhoto,
)
from .serializers import (
    MileageLogSerializer,
    TechnicalInspectionSerializer,
    VehicleOwnerHistorySerializer,
    VehiclePhotoSerializer,
    VehicleSerializer,
)
from .services import create_vehicle

logger = logging.getLogger(__name__)

_EXPENSES_TOTAL_ANNOTATION = {
    "expenses_total": Coalesce(
        Sum("expenses__amount"),
        Value(0),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
}


class VehicleListCreateView(generics.ListCreateAPIView):
    queryset = (
        Vehicle.objects.select_related("driver")
        .prefetch_related(
            "photos",
            "inspections",
            "equipment_list",
            "regulations__entries__item",
        )
        .filter(is_archived=False)
        .annotate(**_EXPENSES_TOTAL_ANNOTATION)
        .order_by("-updated_at")
    )
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["model", "manufacturer", "year", "status"]
    pagination_class = None
    http_method_names = ["get", "post"]

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_vehicle_list(request.query_params)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_vehicle_list(request.query_params, response.data)
        return response

    def perform_create(self, serializer):
        try:
            instance = create_vehicle(serializer.validated_data)
            serializer.instance = (
                instance  # allow DRF to serialize the response correctly
            )
            cache_utils.invalidate_vehicle()
            logger.info(
                "Vehicle created successfully",
                extra={
                    "status_code": 201,
                    "status_message": "Created",
                    "operation_type": "VEHICLE_CREATE",
                    "service": "DJANGO",
                    "vehicle_id": str(instance.id),
                    "car_number": instance.car_number,
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Vehicle creation failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "VEHICLE_CREATE_FAILED",
                    "service": "DJANGO",
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise


class VehicleRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = (
        Vehicle.objects.select_related("driver")
        .prefetch_related(
            "photos",
            "inspections",
            "equipment_list",
            "regulations__entries__item",
        )
        .filter(is_archived=False)
        .annotate(**_EXPENSES_TOTAL_ANNOTATION)
    )
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch", "delete"]

    def retrieve(self, request, *args, **kwargs):
        vehicle_id = self.kwargs["pk"]
        cached = cache_utils.get_vehicle_detail(vehicle_id)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        cache_utils.set_vehicle_detail(vehicle_id, response.data)
        return response

    def perform_update(self, serializer):
        try:
            instance = serializer.save()
            cache_utils.invalidate_vehicle(instance.id)
            logger.info(
                "Vehicle updated successfully",
                extra={
                    "status_code": 200,
                    "status_message": "OK",
                    "operation_type": "VEHICLE_UPDATE",
                    "service": "DJANGO",
                    "vehicle_id": str(instance.id),
                    "car_number": instance.car_number,
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Vehicle update failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "VEHICLE_UPDATE_FAILED",
                    "service": "DJANGO",
                    "vehicle_id": str(self.kwargs.get("pk", "")),
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise

    def perform_destroy(self, instance):
        vehicle_id = instance.id
        car_number = instance.car_number

        # Unassign driver before archiving (triggers signals for driver history)
        if instance.driver_id:
            instance.driver = None

        instance.is_archived = True
        instance.archived_at = timezone.now()
        instance.save()

        cache_utils.invalidate_vehicle(vehicle_id)
        logger.info(
            "Vehicle archived",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "VEHICLE_ARCHIVE",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_id),
                "car_number": car_number,
                "user_id": str(self.request.user.id),
            },
        )


class VehicleArchiveListView(generics.ListAPIView):
    """GET /vehicle/archive/ — list archived vehicles."""

    queryset = (
        Vehicle.objects.select_related("driver")
        .prefetch_related("photos", "inspections")
        .filter(is_archived=True)
        .annotate(**_EXPENSES_TOTAL_ANNOTATION)
        .order_by("-archived_at")
    )
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ["get"]


class VehicleRestoreView(generics.GenericAPIView):
    """POST /vehicle/<pk>/restore/ — restore vehicle from archive."""

    queryset = Vehicle.objects.filter(is_archived=True)
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["post"]

    def post(self, request, pk):
        vehicle = self.get_object()
        vehicle.is_archived = False
        vehicle.archived_at = None
        vehicle.save(update_fields=["is_archived", "archived_at", "updated_at"])
        cache_utils.invalidate_vehicle(vehicle.id)
        logger.info(
            "Vehicle restored from archive",
            extra={
                "operation_type": "VEHICLE_RESTORE",
                "service": "DJANGO",
                "vehicle_id": str(vehicle.id),
                "car_number": vehicle.car_number,
                "user_id": str(request.user.id),
            },
        )
        serializer = self.get_serializer(vehicle)
        return Response(serializer.data)


class VehicleDeleteCheckView(generics.GenericAPIView):
    """GET /vehicle/<pk>/delete-check/ — check related data before permanent delete."""

    queryset = Vehicle.objects.filter(is_archived=True)
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]

    def get(self, request, pk):
        vehicle = self.get_object()
        return Response(
            {
                "has_related_data": vehicle.has_related_data(),
                "related_counts": {
                    "owner_history": vehicle.owner_history.count(),
                    "driver_history": vehicle.vehicle_drivers.count(),
                    "photos": vehicle.photos.count(),
                    "inspections": vehicle.inspections.count(),
                    "service_history": vehicle.service_history.count(),
                    "regulations": vehicle.regulations.count(),
                    "service_plans": vehicle.service_plans.count(),
                    "equipment": vehicle.equipment_list.count(),
                    "mileage_logs": vehicle.mileage_logs.count(),
                    "expenses": vehicle.expenses.count(),
                },
            }
        )


class VehiclePermanentDeleteView(generics.GenericAPIView):
    """DELETE /vehicle/<pk>/permanent-delete/ — permanently delete archived vehicle."""

    queryset = Vehicle.objects.filter(is_archived=True)
    permission_classes = [IsAuthenticated]
    http_method_names = ["delete"]

    def delete(self, request, pk):
        vehicle = self.get_object()
        vehicle_id = vehicle.id
        car_number = vehicle.car_number
        has_data = vehicle.has_related_data()

        if has_data and request.query_params.get("confirm") != "true":
            return Response(
                {
                    "has_related_data": True,
                    "message": "Vehicle has related data. Pass ?confirm=true to permanently delete.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vehicle.delete()
        cache_utils.invalidate_vehicle(vehicle_id)
        logger.info(
            "Vehicle permanently deleted",
            extra={
                "operation_type": "VEHICLE_PERMANENT_DELETE",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_id),
                "car_number": car_number,
                "user_id": str(request.user.id),
                "had_related_data": has_data,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehiclePhotoListCreateView(generics.ListCreateAPIView):
    """
    GET  /vehicle/<pk>/photos/  — list all photos for a vehicle.
    POST /vehicle/<pk>/photos/  — upload a new photo (multipart/form-data, field: image).
                                  Max 10 photos per vehicle.
    """

    serializer_class = VehiclePhotoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return VehiclePhoto.objects.filter(vehicle_id=self.kwargs["pk"])

    def perform_create(self, serializer):
        serializer.save(vehicle_id=self.kwargs["pk"])
        cache_utils.invalidate_vehicle(self.kwargs["pk"])


class VehiclePhotoDestroyView(generics.DestroyAPIView):
    """DELETE /vehicle/<pk>/photos/<photo_pk>/ — remove a photo."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VehiclePhoto.objects.filter(vehicle_id=self.kwargs["pk"])

    def get_object(self):
        return generics.get_object_or_404(
            self.get_queryset(), pk=self.kwargs["photo_pk"]
        )

    def perform_destroy(self, instance):
        instance.delete()
        cache_utils.invalidate_vehicle(self.kwargs["pk"])


class VehicleOwnerHistoryListCreateView(generics.ListCreateAPIView):
    """
    GET  /vehicle/<pk>/owner-history/  — list all ownership records for a vehicle.
    POST /vehicle/<pk>/owner-history/  — assign a new owner (driver) to the vehicle.
    """

    serializer_class = VehicleOwnerHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VehicleOwnerHistory.objects.filter(
            vehicle_id=self.kwargs["pk"]
        ).select_related("driver")

    def perform_create(self, serializer):
        serializer.save(vehicle_id=self.kwargs["pk"])


class VehicleOwnerHistoryUpdateView(generics.UpdateAPIView):
    """
    PATCH /vehicle/<pk>/owner-history/<history_pk>/
    Allows updating agreement_number or closing ownership (released_at).
    """

    serializer_class = VehicleOwnerHistorySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_queryset(self):
        return VehicleOwnerHistory.objects.filter(vehicle_id=self.kwargs["pk"])

    def get_object(self):
        return generics.get_object_or_404(
            self.get_queryset(), pk=self.kwargs["history_pk"]
        )


class TechnicalInspectionListCreateView(generics.ListCreateAPIView):
    serializer_class = TechnicalInspectionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return TechnicalInspection.objects.filter(vehicle_id=self.kwargs["pk"])

    def perform_create(self, serializer):
        serializer.save(vehicle_id=self.kwargs["pk"])
        cache_utils.invalidate_vehicle(self.kwargs["pk"])


class TechnicalInspectionUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TechnicalInspectionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        return TechnicalInspection.objects.filter(vehicle_id=self.kwargs["pk"])

    def get_object(self):
        return generics.get_object_or_404(
            self.get_queryset(), pk=self.kwargs["inspection_pk"]
        )

    def perform_update(self, serializer):
        serializer.save()
        cache_utils.invalidate_vehicle(self.kwargs["pk"])

    def perform_destroy(self, instance):
        instance.delete()
        cache_utils.invalidate_vehicle(self.kwargs["pk"])


class MileageLogListCreateView(generics.ListCreateAPIView):
    serializer_class = MileageLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return MileageLog.objects.filter(vehicle_id=self.kwargs["pk"])

    def perform_create(self, serializer):
        vehicle_id = self.kwargs["pk"]
        instance = serializer.save(
            vehicle_id=vehicle_id,
            created_by=self.request.user,
        )
        Vehicle.objects.filter(pk=vehicle_id).update(initial_km=instance.km)
        cache_utils.invalidate_vehicle(vehicle_id)
