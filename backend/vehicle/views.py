import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config import cache_utils
from .models import Vehicle, VehicleOwnerHistory, VehiclePhoto
from .serializers import VehicleOwnerHistorySerializer, VehiclePhotoSerializer, VehicleSerializer
from .services import create_vehicle

logger = logging.getLogger(__name__)


class VehicleListCreateView(generics.ListCreateAPIView):
    queryset = Vehicle.objects.select_related("driver").prefetch_related("photos").order_by("-created_at")
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
            serializer.instance = instance  # allow DRF to serialize the response correctly
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
    queryset = Vehicle.objects.select_related("driver").prefetch_related("photos").all()
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
        instance.delete()
        cache_utils.invalidate_vehicle(vehicle_id)
        logger.info(
            "Vehicle deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "VEHICLE_DELETE",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_id),
                "car_number": car_number,
                "user_id": str(self.request.user.id),
            },
        )


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
        return generics.get_object_or_404(self.get_queryset(), pk=self.kwargs["photo_pk"])

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
        return (
            VehicleOwnerHistory.objects.filter(vehicle_id=self.kwargs["pk"])
            .select_related("driver")
        )

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
