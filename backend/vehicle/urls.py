from django.urls import path

from . import views

urlpatterns = [
    path("", views.VehicleListCreateView.as_view(), name="vehicle-list-create"),
    path(
        "<uuid:pk>/",
        views.VehicleRetrieveUpdateDestroyView.as_view(),
        name="vehicle-detail",
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
]
