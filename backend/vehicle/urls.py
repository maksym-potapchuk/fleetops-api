from django.urls import path

from expense.views import VehicleExpenseListCreateView

from . import views

urlpatterns = [
    path("", views.VehicleListCreateView.as_view(), name="vehicle-list-create"),
    path(
        "reorder/",
        views.VehicleReorderView.as_view(),
        name="vehicle-reorder",
    ),
    path(
        "archive/",
        views.VehicleArchiveListView.as_view(),
        name="vehicle-archive-list",
    ),
    path(
        "<uuid:pk>/",
        views.VehicleRetrieveUpdateDestroyView.as_view(),
        name="vehicle-detail",
    ),
    path(
        "<uuid:pk>/restore/",
        views.VehicleRestoreView.as_view(),
        name="vehicle-restore",
    ),
    path(
        "<uuid:pk>/delete-check/",
        views.VehicleDeleteCheckView.as_view(),
        name="vehicle-delete-check",
    ),
    path(
        "<uuid:pk>/permanent-delete/",
        views.VehiclePermanentDeleteView.as_view(),
        name="vehicle-permanent-delete",
    ),
    path(
        "<uuid:pk>/photos/",
        views.VehiclePhotoListCreateView.as_view(),
        name="vehicle-photos",
    ),
    path(
        "<uuid:pk>/photos/<int:photo_pk>/",
        views.VehiclePhotoDestroyView.as_view(),
        name="vehicle-photo-delete",
    ),
    path(
        "<uuid:pk>/owner-history/",
        views.VehicleOwnerHistoryListCreateView.as_view(),
        name="vehicle-owner-history",
    ),
    path(
        "<uuid:pk>/owner-history/<int:history_pk>/",
        views.VehicleOwnerHistoryUpdateView.as_view(),
        name="vehicle-owner-history-update",
    ),
    path(
        "<uuid:pk>/inspections/",
        views.TechnicalInspectionListCreateView.as_view(),
        name="vehicle-inspections",
    ),
    path(
        "<uuid:pk>/inspections/<int:inspection_pk>/",
        views.TechnicalInspectionUpdateDestroyView.as_view(),
        name="vehicle-inspection-detail",
    ),
    path(
        "<uuid:pk>/mileage/",
        views.MileageLogListCreateView.as_view(),
        name="vehicle-mileage",
    ),
    path(
        "<uuid:pk>/expenses/",
        VehicleExpenseListCreateView.as_view(),
        name="vehicle-expenses",
    ),
]
