import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config import cache_utils
from config.filters import LayoutAwareSearchFilter as SearchFilter

from .constants import EventType
from .filters import FleetVehicleRegulationSchemaFilter, RegulationHistoryFilter
from .models import (
    EquipmentDefaultItem,
    EquipmentList,
    FleetService,
    FleetVehicleRegulation,
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationHistory,
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
    ServicePlan,
)
from .serializers import (
    AssignRegulationSerializer,
    EquipmentDefaultItemSerializer,
    EquipmentListSerializer,
    FleetServiceSerializer,
    FleetVehicleRegulationItemSerializer,
    FleetVehicleRegulationSchemaSerializer,
    FleetVehicleRegulationSchemaUpdateSerializer,
    ServicePlanSerializer,
    ServicePlanWithVehicleSerializer,
    VehicleRegulationHistorySerializer,
    VehicleRegulationPlanEntrySerializer,
    VehicleRegulationPlanSerializer,
)
from .services import assign_regulation_to_vehicle

logger = logging.getLogger(__name__)


class FleetServiceViewSet(viewsets.ModelViewSet):
    queryset = FleetService.objects.all()
    serializer_class = FleetServiceSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            instance = serializer.save(created_by=self.request.user)
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


class FleetVehicleRegulationSchemaListCreateAPIView(generics.ListCreateAPIView):
    queryset = FleetVehicleRegulationSchema.objects.prefetch_related("items").all()
    serializer_class = FleetVehicleRegulationSchemaSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = FleetVehicleRegulationSchemaFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title"]
    ordering_fields = ["created_at", "title"]

    def list(self, request, *args, **kwargs):
        cached = cache_utils.get_schema_list(request.query_params)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_schema_list(request.query_params, response.data)
        return response

    def perform_create(self, serializer):
        try:
            instance = serializer.save(created_by=self.request.user)
            cache_utils.invalidate_schema()
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


class FleetVehicleRegulationSchemaDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE a single regulation schema."""

    queryset = FleetVehicleRegulationSchema.objects.prefetch_related("items")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return FleetVehicleRegulationSchemaUpdateSerializer
        return FleetVehicleRegulationSchemaSerializer

    def retrieve(self, request, *args, **kwargs):
        schema_id = self.kwargs["pk"]
        cached = cache_utils.get_schema_detail(schema_id)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        cache_utils.set_schema_detail(schema_id, response.data)
        return response

    def perform_update(self, serializer):
        try:
            instance = serializer.save()
            cache_utils.invalidate_schema(instance.id)
            logger.info(
                "Regulation schema updated successfully",
                extra={
                    "status_code": 200,
                    "status_message": "OK",
                    "operation_type": "REGULATION_SCHEMA_UPDATE",
                    "service": "DJANGO",
                    "schema_id": instance.id,
                    "schema_title": instance.title,
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Regulation schema update failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "REGULATION_SCHEMA_UPDATE_FAILED",
                    "service": "DJANGO",
                    "schema_id": str(self.kwargs.get("pk", "")),
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise

    def perform_destroy(self, instance):
        schema_id = instance.id
        schema_title = instance.title
        instance.delete()
        cache_utils.invalidate_schema(schema_id)
        logger.info(
            "Regulation schema deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "REGULATION_SCHEMA_DELETE",
                "service": "DJANGO",
                "schema_id": schema_id,
                "schema_title": schema_title,
                "user_id": str(self.request.user.id),
            },
        )


class FleetVehicleRegulationItemDetailAPIView(generics.RetrieveUpdateAPIView):
    """GET / PATCH a single regulation item (title_pl, title_uk, etc.)."""

    queryset = FleetVehicleRegulationItem.objects.all()
    serializer_class = FleetVehicleRegulationItemSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        instance = serializer.save()
        # Item belongs to a schema — bust the schema caches so detail reflects change.
        cache_utils.invalidate_schema(instance.schema_id)


class AssignRegulationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_pk):
        serializer = AssignRegulationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = assign_regulation_to_vehicle(
                vehicle_pk=vehicle_pk,
                schema_id=serializer.validated_data["schema_id"],
                entries_data=serializer.validated_data["entries"],
                user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        cache_utils.invalidate_regulation_plan(vehicle_pk)
        logger.info(
            "Regulation assigned to vehicle",
            extra={
                "vehicle_id": str(vehicle_pk),
                "schema_id": serializer.validated_data["schema_id"],
                "user_id": str(request.user.id),
            },
        )
        return Response(result, status=status.HTTP_201_CREATED)


class VehicleRegulationEntryUpdate(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, vehicle_pk, entry_pk):
        entry = generics.get_object_or_404(
            FleetVehicleRegulationEntry,
            pk=entry_pk,
            regulation__vehicle_id=vehicle_pk,
        )
        km = request.data.get("last_done_km")
        if km is None or not str(km).isdigit():
            return Response(
                {
                    "detail": "last_done_km is required and must be a non-negative integer."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        km = int(km)
        entry.last_done_km = km
        entry.save(update_fields=["last_done_km", "updated_at"])

        FleetVehicleRegulationHistory.objects.create(
            entry=entry,
            event_type=EventType.PERFORMED,
            km_at_event=km,
            km_remaining=entry.next_due_km - km,
            note=request.data.get("note", ""),
            created_by=request.user,
        )

        cache_utils.invalidate_regulation_plan(vehicle_pk)
        logger.info(
            "Regulation entry updated",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "REGULATION_ENTRY_UPDATE",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_pk),
                "entry_id": entry_pk,
                "km": km,
                "user_id": str(request.user.id),
            },
        )
        return Response(VehicleRegulationPlanEntrySerializer(entry).data)


class VehicleRegulationPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_pk):
        cached = cache_utils.get_regulation_plan(vehicle_pk)
        if cached is not None:
            return Response(cached)

        regulation = (
            FleetVehicleRegulation.objects.filter(vehicle_id=vehicle_pk)
            .prefetch_related("entries__item", "schema")
            .first()
        )
        if not regulation:
            data = {"assigned": False}
        else:
            data = {
                "assigned": True,
                **VehicleRegulationPlanSerializer(regulation).data,
            }

        cache_utils.set_regulation_plan(vehicle_pk, data)
        return Response(data)


class VehicleRegulationHistoryView(generics.ListAPIView):
    serializer_class = VehicleRegulationHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = RegulationHistoryFilter
    ordering_fields = ["created_at"]
    ordering = ["created_at"]

    def get_queryset(self):
        return FleetVehicleRegulationHistory.objects.filter(
            entry__regulation__vehicle_id=self.kwargs["vehicle_pk"]
        ).select_related("entry__item", "created_by")


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
            instance = serializer.save(
                vehicle_id=self.kwargs["vehicle_pk"], created_by=self.request.user
            )
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


class AllServicePlansAPIView(generics.ListAPIView):
    """GET /fleet/service-plans/ — all plans across all vehicles, with car_number."""

    serializer_class = ServicePlanWithVehicleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["is_done"]
    ordering_fields = ["planned_at", "created_at"]
    ordering = ["planned_at"]

    def get_queryset(self):
        return ServicePlan.objects.select_related("vehicle").all()


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
            instance = serializer.save(created_by=self.request.user)
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


class EquipmentListAPIView(generics.ListCreateAPIView):
    serializer_class = EquipmentListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return EquipmentList.objects.filter(
            vehicle_id=self.kwargs["vehicle_pk"],
        ).order_by("equipment")

    def list(self, request, *args, **kwargs):
        vehicle_pk = self.kwargs["vehicle_pk"]
        cached = cache_utils.get_equipment_list(vehicle_pk)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache_utils.set_equipment_list(vehicle_pk, response.data)
        return response

    def perform_create(self, serializer):
        try:
            instance = serializer.save(
                vehicle_id=self.kwargs["vehicle_pk"], created_by=self.request.user
            )
            cache_utils.invalidate_equipment(self.kwargs["vehicle_pk"])
            cache_utils.invalidate_vehicle(self.kwargs["vehicle_pk"])
            logger.info(
                "Equipment item created for vehicle",
                extra={
                    "status_code": 201,
                    "status_message": "Created",
                    "operation_type": "EQUIPMENT_ITEM_CREATE",
                    "service": "DJANGO",
                    "vehicle_id": str(self.kwargs["vehicle_pk"]),
                    "equipment": instance.equipment,
                    "user_id": str(self.request.user.id),
                },
            )
        except Exception:
            logger.error(
                "Equipment item creation failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "EQUIPMENT_ITEM_CREATE_FAILED",
                    "service": "DJANGO",
                    "vehicle_id": str(self.kwargs["vehicle_pk"]),
                    "user_id": str(self.request.user.id),
                },
                exc_info=True,
            )
            raise


class EquipmentItemDestroyAPIView(generics.DestroyAPIView):
    serializer_class = EquipmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EquipmentList.objects.filter(vehicle_id=self.kwargs["vehicle_pk"])

    def perform_destroy(self, instance):
        vehicle_pk = self.kwargs["vehicle_pk"]
        instance.delete()
        cache_utils.invalidate_equipment(vehicle_pk)
        cache_utils.invalidate_vehicle(vehicle_pk)
        logger.info(
            "Equipment item deleted",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "EQUIPMENT_ITEM_DELETE",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_pk),
                "user_id": str(self.request.user.id),
            },
        )


class EquipmentItemToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, vehicle_pk, pk):
        item = generics.get_object_or_404(EquipmentList, pk=pk, vehicle_id=vehicle_pk)
        item.is_equipped = not item.is_equipped
        item.save(update_fields=["is_equipped"])
        cache_utils.invalidate_equipment(vehicle_pk)
        cache_utils.invalidate_vehicle(vehicle_pk)
        logger.info(
            "Equipment item toggled",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "EQUIPMENT_ITEM_TOGGLE",
                "service": "DJANGO",
                "vehicle_id": str(vehicle_pk),
                "item_id": pk,
                "is_equipped": item.is_equipped,
                "user_id": str(request.user.id),
            },
        )
        return Response(EquipmentListSerializer(item).data)
