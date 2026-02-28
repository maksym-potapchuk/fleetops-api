import logging

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config import cache_utils

from .models import Driver
from .serializers import DriverSerializer

logger = logging.getLogger(__name__)


class DriverModelViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_driver_list()
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_driver_list(response.data)
        return response

    def retrieve(self, request, *args, **kwargs):
        driver_id = self.kwargs["pk"]
        cached = cache_utils.get_driver_detail(driver_id)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        cache_utils.set_driver_detail(driver_id, response.data)
        return response

    def perform_create(self, serializer):
        try:
            instance = serializer.save()
            cache_utils.invalidate_driver()
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
            cache_utils.invalidate_driver(instance.id)
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
        driver_id = instance.id
        driver_name = str(instance)
        instance.delete()
        cache_utils.invalidate_driver(driver_id)
        logger.info(
            "Driver deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "DRIVER_DELETE",
                "service": "DJANGO",
                "driver_id": str(driver_id),
                "driver_name": driver_name,
                "user_id": str(self.request.user.id),
            },
        )
