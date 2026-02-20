from django.urls import path

from . import views

urlpatterns = [
    path("", views.VehicleListCreateView.as_view(), name="vehicle-list-create"),
    path(
        "<uuid:pk>/",
        views.VehicleRetrieveUpdateDestroyView.as_view(),
        name="vehicle-detail",
    ),
]
