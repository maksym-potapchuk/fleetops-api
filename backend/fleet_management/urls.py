from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FleetServiceViewSet,
    FleetVehicleRegulationSchemaListAPIView,
    ServicePlanListCreateAPIView,
    ServicePlanDetailAPIView,
    ServicePlanMarkDoneAPIView,
    EquipmentDefaultItemViewSet,
    EquipmentListListCreateAPIView,
    EquipmentListDetailAPIView,
    GrantDefaultEquipmentAPIView,
)

router = DefaultRouter()
router.register(r"services", FleetServiceViewSet, basename="service")
router.register(r"equipment/defaults", EquipmentDefaultItemViewSet, basename="equipment-default")

urlpatterns = [
    path("", include(router.urls)),

    # Regulation schemas
    path(
        "regulation/schemas/",
        FleetVehicleRegulationSchemaListAPIView.as_view(),
        name="regulation-schema-list",
    ),

    # Service plans  (scoped to a vehicle)
    path(
        "vehicles/<uuid:vehicle_pk>/service-plans/",
        ServicePlanListCreateAPIView.as_view(),
        name="service-plan-list",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/service-plans/<int:pk>/",
        ServicePlanDetailAPIView.as_view(),
        name="service-plan-detail",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/service-plans/<int:pk>/done/",
        ServicePlanMarkDoneAPIView.as_view(),
        name="service-plan-mark-done",
    ),

    # Equipment lists (scoped to a vehicle)
    path(
        "vehicles/<uuid:vehicle_pk>/equipment/",
        EquipmentListListCreateAPIView.as_view(),
        name="equipment-list",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/equipment/<int:pk>/",
        EquipmentListDetailAPIView.as_view(),
        name="equipment-detail",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/equipment/grant-defaults/",
        GrantDefaultEquipmentAPIView.as_view(),
        name="equipment-grant-defaults",
    ),
]
