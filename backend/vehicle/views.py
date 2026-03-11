import logging

from django.db import models, transaction
from django.db.models import Case, Count, DecimalField, F, Prefetch, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config import cache_utils

from .models import (
    MileageLog,
    OwnerHistory,
    TechnicalInspection,
    Vehicle,
    VehicleOwner,
    VehiclePhoto,
)
from .serializers import (
    MileageLogSerializer,
    OwnerHistorySerializer,
    TechnicalInspectionSerializer,
    VehicleOwnerSerializer,
    VehiclePhotoSerializer,
    VehicleSerializer,
)
from .services import assign_owner, create_vehicle, unassign_owner

logger = logging.getLogger(__name__)

_VEHICLE_ANNOTATIONS = {
    "expenses_total": Coalesce(
        Sum("expenses__amount"),
        Value(0),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    ),
    "equipment_total_count": Count(
        "equipment_list",
        distinct=True,
    ),
    "equipment_equipped_count": Count(
        "equipment_list",
        filter=Q(equipment_list__is_equipped=True),
        distinct=True,
    ),
    "regulation_overdue_count": Count(
        "regulations__entries",
        filter=Q(
            initial_km__gte=F("regulations__entries__last_done_km")
            + F("regulations__entries__item__every_km"),
        ),
        distinct=True,
    ),
    "has_regulation_flag": Case(
        When(regulations__isnull=False, then=Value(True)),
        default=Value(False),
        output_field=models.BooleanField(),
    ),
}


class VehiclePagination(PageNumberPagination):
    page_size = 200
    page_size_query_param = "page_size"
    max_page_size = 500


class VehicleListCreateView(generics.ListCreateAPIView):
    pagination_class = VehiclePagination
    queryset = (
        Vehicle.objects.select_related("current_owner__driver")
        .prefetch_related(
            "photos",
            "inspections",
            "equipment_list",
            Prefetch(
                "regulations__entries__item",
            ),
        )
        .filter(is_archived=False)
        .annotate(**_VEHICLE_ANNOTATIONS)
        .order_by("status_position", "-updated_at")
    )
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["model", "manufacturer", "year", "status"]
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
            instance = create_vehicle(serializer.validated_data, user=self.request.user)
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
        Vehicle.objects.select_related("current_owner__driver")
        .prefetch_related(
            "photos",
            "inspections",
            "equipment_list",
            Prefetch(
                "regulations__entries__item",
            ),
        )
        .filter(is_archived=False)
        .annotate(**_VEHICLE_ANNOTATIONS)
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
            old_status = serializer.instance.status
            instance = serializer.save()
            if (
                instance.status != old_status
                and "status_position" not in self.request.data
            ):
                max_pos = (
                    Vehicle.objects.filter(status=instance.status, is_archived=False)
                    .exclude(pk=instance.pk)
                    .aggregate(m=models.Max("status_position"))["m"]
                    or 0
                )
                instance.status_position = max_pos + 1000
                instance.save(update_fields=["status_position"])
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

        unassign_owner(instance)

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


class VehicleReorderView(generics.GenericAPIView):
    """POST /vehicle/reorder/ -- batch update positions (and optionally status)."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["post"]

    def post(self, request):
        items = request.data
        if not isinstance(items, list) or len(items) == 0:
            return Response(
                {"detail": "Expected non-empty array."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(items) > 100:
            return Response(
                {"detail": "Too many items."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vehicle_ids = [item["id"] for item in items]
        vehicles_qs = Vehicle.objects.filter(id__in=vehicle_ids, is_archived=False)
        vehicles_map = {str(v.id): v for v in vehicles_qs}

        with transaction.atomic():
            to_update = []
            for item in items:
                v = vehicles_map.get(item["id"])
                if not v:
                    continue
                v.status = item.get("status", v.status)
                v.status_position = item["status_position"]
                to_update.append(v)
            if to_update:
                Vehicle.objects.bulk_update(to_update, ["status", "status_position"])

        cache_utils.invalidate_vehicle()
        return Response({"updated": len(to_update)})


class VehicleArchiveListView(generics.ListAPIView):
    """GET /vehicle/archive/ -- list archived vehicles."""

    queryset = (
        Vehicle.objects.select_related("current_owner__driver")
        .prefetch_related("photos", "inspections")
        .filter(is_archived=True)
        .annotate(**_VEHICLE_ANNOTATIONS)
        .order_by("-archived_at")
    )
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_archive_list()
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_archive_list(response.data)
        return response


class VehicleRestoreView(generics.GenericAPIView):
    """POST /vehicle/<pk>/restore/ -- restore vehicle from archive."""

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
    """GET /vehicle/<pk>/delete-check/ -- check related data before permanent delete."""

    queryset = Vehicle.objects.filter(is_archived=True)
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]

    def get(self, request, pk):
        cached = cache_utils.get_delete_check(pk)
        if cached is not None:
            return Response(cached)

        vehicle = (
            Vehicle.objects.filter(pk=pk, is_archived=True)
            .annotate(
                _current_owner=Count("current_owner", distinct=True),
                _ownership_history=Count("ownership_history", distinct=True),
                _photos=Count("photos", distinct=True),
                _inspections=Count("inspections", distinct=True),
                _service_history=Count("service_history", distinct=True),
                _regulations=Count("regulations", distinct=True),
                _service_plans=Count("service_plans", distinct=True),
                _equipment=Count("equipment_list", distinct=True),
                _mileage_logs=Count("mileage_logs", distinct=True),
                _expenses=Count("expenses", distinct=True),
            )
            .first()
        )
        if not vehicle:
            return Response(status=status.HTTP_404_NOT_FOUND)

        counts = {
            "current_owner": vehicle._current_owner,
            "ownership_history": vehicle._ownership_history,
            "photos": vehicle._photos,
            "inspections": vehicle._inspections,
            "service_history": vehicle._service_history,
            "regulations": vehicle._regulations,
            "service_plans": vehicle._service_plans,
            "equipment": vehicle._equipment,
            "mileage_logs": vehicle._mileage_logs,
            "expenses": vehicle._expenses,
        }
        data = {
            "has_related_data": any(v > 0 for v in counts.values()),
            "related_counts": counts,
        }
        cache_utils.set_delete_check(pk, data)
        return Response(data)


class VehiclePermanentDeleteView(generics.GenericAPIView):
    """DELETE /vehicle/<pk>/permanent-delete/ -- permanently delete archived vehicle."""

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
    GET  /vehicle/<pk>/photos/  -- list all photos for a vehicle.
    POST /vehicle/<pk>/photos/  -- upload a new photo (multipart/form-data, field: image).
    """

    serializer_class = VehiclePhotoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return VehiclePhoto.objects.filter(vehicle_id=self.kwargs["pk"])

    def perform_create(self, serializer):
        serializer.save(vehicle_id=self.kwargs["pk"], created_by=self.request.user)
        cache_utils.invalidate_vehicle(self.kwargs["pk"])


class VehiclePhotoDestroyView(generics.DestroyAPIView):
    """DELETE /vehicle/<pk>/photos/<photo_pk>/ -- remove a photo."""

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


class VehicleOwnerView(generics.GenericAPIView):
    """
    GET    /vehicle/<pk>/owner/  -- current owner (or 404)
    POST   /vehicle/<pk>/owner/  -- assign new owner (archives old one)
    PATCH  /vehicle/<pk>/owner/  -- update agreement_number
    DELETE /vehicle/<pk>/owner/  -- unassign current owner
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete"]

    def get(self, request, pk):
        vehicle = generics.get_object_or_404(Vehicle, pk=pk)
        try:
            owner = VehicleOwner.objects.select_related("driver").get(vehicle=vehicle)
        except VehicleOwner.DoesNotExist:
            return Response(None)
        serializer = VehicleOwnerSerializer(owner)
        return Response(serializer.data)

    def post(self, request, pk):
        vehicle = generics.get_object_or_404(Vehicle, pk=pk)
        serializer = VehicleOwnerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        driver = serializer.validated_data["driver"]
        agreement_number = serializer.validated_data.get("agreement_number", "")

        assign_owner(
            vehicle, driver, agreement_number=agreement_number, user=request.user
        )
        cache_utils.invalidate_vehicle(pk)

        owner = VehicleOwner.objects.select_related("driver").get(vehicle=vehicle)
        return Response(
            VehicleOwnerSerializer(owner).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request, pk):
        vehicle = generics.get_object_or_404(Vehicle, pk=pk)
        try:
            owner = VehicleOwner.objects.select_related("driver").get(vehicle=vehicle)
        except VehicleOwner.DoesNotExist:
            return Response(
                {"detail": "No current owner to update."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = VehicleOwnerSerializer(owner, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        cache_utils.invalidate_vehicle(pk)
        return Response(serializer.data)

    def delete(self, request, pk):
        vehicle = generics.get_object_or_404(Vehicle, pk=pk)
        unassign_owner(vehicle)
        cache_utils.invalidate_vehicle(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerHistoryListView(generics.ListAPIView):
    """GET /vehicle/<pk>/owner/history/ -- archived ownership records."""

    serializer_class = OwnerHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OwnerHistory.objects.filter(vehicle_id=self.kwargs["pk"]).select_related(
            "driver"
        )


class TechnicalInspectionListCreateView(generics.ListCreateAPIView):
    serializer_class = TechnicalInspectionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return TechnicalInspection.objects.filter(vehicle_id=self.kwargs["pk"])

    def perform_create(self, serializer):
        serializer.save(vehicle_id=self.kwargs["pk"], created_by=self.request.user)
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

        instance.vehicle.initial_km = instance.km
        from notification.services import check_regulation_notifications

        check_regulation_notifications(instance.vehicle)
