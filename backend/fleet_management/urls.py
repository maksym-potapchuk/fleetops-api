from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FleetServiceViewSet

router = DefaultRouter()
router.register(r'services', FleetServiceViewSet, basename='service')

urlpatterns = [
    path('', include(router.urls)),
]
