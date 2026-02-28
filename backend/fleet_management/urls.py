from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AllServicePlansAPIView,
    AssignRegulationView,
    EquipmentDefaultItemViewSet,
    EquipmentItemDestroyAPIView,
    EquipmentItemToggleAPIView,
    EquipmentListAPIView,
    FleetServiceViewSet,
    FleetVehicleRegulationItemDetailAPIView,
    FleetVehicleRegulationSchemaDetailAPIView,
    FleetVehicleRegulationSchemaListCreateAPIView,
    ServicePlanDetailAPIView,
    ServicePlanListCreateAPIView,
    ServicePlanMarkDoneAPIView,
    VehicleRegulationEntryUpdate,
    VehicleRegulationHistoryView,
    VehicleRegulationPlanView,
)

router = DefaultRouter()
router.register(r"services", FleetServiceViewSet, basename="service")
router.register(
    r"equipment/defaults",
    EquipmentDefaultItemViewSet,
    basename="equipment-default",
)

urlpatterns = [
    path("", include(router.urls)),
    path("service-plans/", AllServicePlansAPIView.as_view(), name="all-service-plans"),
    # Regulation schemas
    path(
        "regulation/schemas/",
        FleetVehicleRegulationSchemaListCreateAPIView.as_view(),
        name="regulation-schema-list",
    ),
    path(
        "regulation/schemas/<int:pk>/",
        FleetVehicleRegulationSchemaDetailAPIView.as_view(),
        name="regulation-schema-detail",
    ),
    path(
        "regulation/items/<int:pk>/",
        FleetVehicleRegulationItemDetailAPIView.as_view(),
        name="regulation-item-detail",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/regulation/",
        VehicleRegulationPlanView.as_view(),
        name="vehicle-regulation-plan",
    ),
    path(
        "regulation/<uuid:vehicle_pk>/assign/",
        AssignRegulationView.as_view(),
        name="regulation-assign-entry",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/regulation/history/",
        VehicleRegulationHistoryView.as_view(),
        name="vehicle-regulation-history",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/regulation/entries/<int:entry_pk>/",
        VehicleRegulationEntryUpdate.as_view(),
        name="regulation-entry-update",
    ),
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
    path(
        "vehicles/<uuid:vehicle_pk>/equipment/",
        EquipmentListAPIView.as_view(),
        name="equipment-list",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/equipment/<int:pk>/",
        EquipmentItemDestroyAPIView.as_view(),
        name="equipment-detail",
    ),
    path(
        "vehicles/<uuid:vehicle_pk>/equipment/<int:pk>/toggle/",
        EquipmentItemToggleAPIView.as_view(),
        name="equipment-toggle",
    ),
]
