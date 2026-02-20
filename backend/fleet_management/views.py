import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import FleetVehicleRegulationSchemaFilter
from .models import (
    EquipmentDefaultItem,
    EquipmentList,
    FleetService,
    FleetVehicleRegulationSchema,
    ServicePlan,
)
from .serializers import (
    EquipmentDefaultItemSerializer,
    EquipmentListSerializer,
    FleetServiceSerializer,
    FleetVehicleRegulationSchemaSerializer,
    ServicePlanSerializer,
)
from .services import grant_equipment_to_vehicle

logger = logging.getLogger(__name__)


class FleetServiceViewSet(viewsets.ModelViewSet):
    queryset = FleetService.objects.all()
    serializer_class = FleetServiceSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            instance = serializer.save()
            logger.info(
                "Fleet service created successfully",
                extra={
                    "status_code": 201,
                    "status_message": "Created",
                    "operation_type": "FLEET_SERVICE_CREATE",
                    "service": "DJANGO",
                    "fleet_service_id": instance.id,
                    "fleet_service_name": instance.name,
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Fleet service creation failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "FLEET_SERVICE_CREATE_FAILED",
                    "service": "DJANGO",
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise

    def perform_destroy(self, instance):
        logger.info(
            "Fleet service deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "FLEET_SERVICE_DELETE",
                "service": "DJANGO",
                "fleet_service_id": instance.id,
                "fleet_service_name": instance.name,
                "user_id": str(self.request.user.id),
            },
        )
        instance.delete()


class FleetVehicleRegulationSchemaListAPIView(generics.ListCreateAPIView):
    queryset = FleetVehicleRegulationSchema.objects.prefetch_related("items").all()
    serializer_class = FleetVehicleRegulationSchemaSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = FleetVehicleRegulationSchemaFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title"]
    ordering_fields = ["created_at", "title"]

    def perform_create(self, serializer):
        try:
            instance = serializer.save(created_by=self.request.user)
            logger.info(
                "Regulation schema created successfully",
                extra={
                    "status_code": 201,
                    "status_message": "Created",
                    "operation_type": "REGULATION_SCHEMA_CREATE",
                    "service": "DJANGO",
                    "schema_id": instance.id,
                    "schema_title": instance.title,
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Regulation schema creation failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "REGULATION_SCHEMA_CREATE_FAILED",
                    "service": "DJANGO",
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise


class ServicePlanListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ServicePlanSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["vehicle", "is_done"]
    search_fields = ["title"]
    ordering_fields = ["planned_at", "created_at"]

    def get_queryset(self):
        return ServicePlan.objects.filter(
            vehicle_id=self.kwargs["vehicle_pk"],
        ).order_by("planned_at")

    def perform_create(self, serializer):
        try:
            instance = serializer.save(vehicle_id=self.kwargs["vehicle_pk"])
            logger.info(
                "Service plan created successfully",
                extra={
                    "status_code": 201,
                    "status_message": "Created",
                    "operation_type": "SERVICE_PLAN_CREATE",
                    "service": "DJANGO",
                    "plan_id": instance.id,
                    "plan_title": instance.title,
                    "vehicle_id": str(self.kwargs["vehicle_pk"]),
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Service plan creation failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "SERVICE_PLAN_CREATE_FAILED",
                    "service": "DJANGO",
                    "vehicle_id": str(self.kwargs["vehicle_pk"]),
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise


class ServicePlanDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ServicePlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ServicePlan.objects.filter(vehicle_id=self.kwargs["vehicle_pk"])


class ServicePlanMarkDoneAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, vehicle_pk, pk):
        logger.info(
            "Service plan mark-done attempt",
            extra={
                "status_code": 100,
                "status_message": "Continue",
                "operation_type": "SERVICE_PLAN_MARK_DONE_REQUEST",
                "service": "DJANGO",
                "plan_id": pk,
                "vehicle_id": str(vehicle_pk),
                "user_id": str(request.user.id),
            },
        )
        plan = generics.get_object_or_404(ServicePlan, pk=pk, vehicle_id=vehicle_pk)
        try:
            plan.is_done = True
            plan.save(update_fields=["is_done"])
        except Exception:
            logger.error(
                "Service plan mark-done failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "SERVICE_PLAN_MARK_DONE_FAILED",
                    "service": "DJANGO",
                    "plan_id": pk,
                    "vehicle_id": str(vehicle_pk),
                    "user_id": str(request.user.id),
                },
                exc_info=True,
            )
            raise

        logger.info(
            "Service plan marked as done",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "SERVICE_PLAN_MARK_DONE_SUCCESS",
                "service": "DJANGO",
                "plan_id": pk,
                "vehicle_id": str(vehicle_pk),
                "user_id": str(request.user.id),
            },
        )
        return Response(ServicePlanSerializer(plan).data)


class EquipmentDefaultItemViewSet(viewsets.ModelViewSet):
    queryset = EquipmentDefaultItem.objects.all().order_by("equipment")
    serializer_class = EquipmentDefaultItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["equipment"]

    def perform_create(self, serializer):
        try:
            instance = serializer.save()
            logger.info(
                "Default equipment item created",
                extra={
                    "status_code": 201,
                    "status_message": "Created",
                    "operation_type": "EQUIPMENT_DEFAULT_ITEM_CREATE",
                    "service": "DJANGO",
                    "item_id": instance.id,
                    "equipment": instance.equipment,
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Default equipment item creation failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "EQUIPMENT_DEFAULT_ITEM_CREATE_FAILED",
                    "service": "DJANGO",
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise

    def perform_destroy(self, instance):
        logger.info(
            "Default equipment item deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "EQUIPMENT_DEFAULT_ITEM_DELETE",
                "service": "DJANGO",
                "item_id": instance.id,
                "equipment": instance.equipment,
                "user_id": str(self.request.user.id),
            },
        )
        instance.delete()


class EquipmentListListAPIView(generics.ListAPIView):
    serializer_class = EquipmentListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_equipped"]
    search_fields = ["equipment"]

    def get_queryset(self):
        return EquipmentList.objects.filter(
            vehicle_id=self.kwargs["vehicle_pk"],
        ).order_by("equipment")


class GrantDefaultEquipmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_pk):
        logger.info(
            "Grant default equipment to vehicle attempt",
            extra={
                "status_code": 100,
                "status_message": "Continue",
                "operation_type": "EQUIPMENT_GRANT_REQUEST",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_pk),
                "user_id": str(request.user.id),
            },
        )
        try:
            created = grant_equipment_to_vehicle(vehicle_pk)
        except Exception:
            logger.error(
                "Grant default equipment to vehicle failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "EQUIPMENT_GRANT_FAILED",
                    "service": "DJANGO",
                    "vehicle_id": str(vehicle_pk),
                    "user_id": str(request.user.id),
                },
                exc_info=True,
            )
            raise

        logger.info(
            "Default equipment granted to vehicle",
            extra={
                "status_code": 201,
                "status_message": "Created",
                "operation_type": "EQUIPMENT_GRANT_SUCCESS",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_pk),
                "granted_count": len(created),
                "user_id": str(request.user.id),
            },
        )
        return Response({"granted": len(created)}, status=status.HTTP_201_CREATED)


class EquipmentListDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EquipmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EquipmentList.objects.filter(vehicle_id=self.kwargs["vehicle_pk"])
