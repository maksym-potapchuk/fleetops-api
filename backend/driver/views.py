import logging

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Driver
from .serializers import DriverSerializer

logger = logging.getLogger(__name__)


class DriverModelViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            instance = serializer.save()
            logger.info(
                "Driver created successfully",
                extra={
                    "status_code": 201,
                    "status_message": "Created",
                    "operation_type": "DRIVER_CREATE",
                    "service": "DJANGO",
                    "driver_id": str(instance.id),
                    "driver_name": str(instance),
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Driver creation failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "DRIVER_CREATE_FAILED",
                    "service": "DJANGO",
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise

    def perform_update(self, serializer):
        try:
            instance = serializer.save()
            logger.info(
                "Driver updated successfully",
                extra={
                    "status_code": 200,
                    "status_message": "OK",
                    "operation_type": "DRIVER_UPDATE",
                    "service": "DJANGO",
                    "driver_id": str(instance.id),
                    "driver_name": str(instance),
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Driver update failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "DRIVER_UPDATE_FAILED",
                    "service": "DJANGO",
                    "driver_id": str(self.kwargs.get("pk", "")),
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise

    def perform_destroy(self, instance):
        logger.info(
            "Driver deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "DRIVER_DELETE",
                "service": "DJANGO",
                "driver_id": str(instance.id),
                "driver_name": str(instance),
                "user_id": str(self.request.user.id),
            },
        )
        instance.delete()
