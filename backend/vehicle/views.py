import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Vehicle
from .serializers import VehicleSerializer

logger = logging.getLogger(__name__)


class VehicleListCreateView(generics.ListCreateAPIView):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["model", "manufacturer", "year", "status"]
    pagination_class = None
    http_method_names = ["get", "post"]

    def perform_create(self, serializer):
        try:
            instance = serializer.save()
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
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch", "delete"]

    def perform_update(self, serializer):
        try:
            instance = serializer.save()
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
        logger.info(
            "Vehicle deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "VEHICLE_DELETE",
                "service": "DJANGO",
                "vehicle_id": str(instance.id),
                "car_number": instance.car_number,
                "user_id": str(self.request.user.id),
            },
        )
        instance.delete()
