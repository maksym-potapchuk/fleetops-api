from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    FleetService,
    FleetVehicleRegulationSchema,
    FleetVehicleRegulation,
    FleetVehicleRegulationNotification,
    ServicePlan,
    EquipmentDefaultItem,
    EquipmentList,
)
from .serializers import (
    FleetServiceSerializer,
    FleetVehicleRegulationSchemaSerializer,
    ServicePlanSerializer,
    EquipmentDefaultItemSerializer,
    EquipmentListSerializer,
)
from .filters import FleetVehicleRegulationSchemaFilter
from .services import grant_equipment_to_vehicle


class FleetServiceViewSet(viewsets.ModelViewSet):
    queryset = FleetService.objects.all()
    serializer_class = FleetServiceSerializer
    permission_classes = [IsAuthenticated]


class FleetVehicleRegulationSchemaListAPIView(generics.ListCreateAPIView):
    queryset = FleetVehicleRegulationSchema.objects.prefetch_related("items").all()
    serializer_class = FleetVehicleRegulationSchemaSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = FleetVehicleRegulationSchemaFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title"]
    ordering_fields = ["created_at", "title"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ServicePlanListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ServicePlanSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["vehicle", "is_done"]
    search_fields = ["title"]
    ordering_fields = ["planned_at", "created_at"]

    def get_queryset(self):
        return ServicePlan.objects.filter(
            vehicle_id=self.kwargs["vehicle_pk"]
        ).order_by("planned_at")

    def perform_create(self, serializer):
        serializer.save(vehicle_id=self.kwargs["vehicle_pk"])


class ServicePlanDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ServicePlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ServicePlan.objects.filter(vehicle_id=self.kwargs["vehicle_pk"])


class ServicePlanMarkDoneAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, vehicle_pk, pk):
        plan = generics.get_object_or_404(
            ServicePlan, pk=pk, vehicle_id=vehicle_pk
        )
        plan.is_done = True
        plan.save(update_fields=["is_done"])
        return Response(ServicePlanSerializer(plan).data)


class EquipmentDefaultItemViewSet(viewsets.ModelViewSet):
    queryset = EquipmentDefaultItem.objects.all().order_by("equipment")
    serializer_class = EquipmentDefaultItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["equipment"]


class EquipmentListListCreateAPIView(generics.ListAPIView):
    serializer_class = EquipmentListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_equipped"]
    search_fields = ["equipment"]

    def get_queryset(self):
        return EquipmentList.objects.filter(
            vehicle_id=self.kwargs["vehicle_pk"]
        ).order_by("equipment")


class GrantDefaultEquipmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_pk):
        created = grant_equipment_to_vehicle(vehicle_pk)
        return Response({"granted": len(created)}, status=status.HTTP_201_CREATED)


class EquipmentListDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EquipmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EquipmentList.objects.filter(vehicle_id=self.kwargs["vehicle_pk"])
