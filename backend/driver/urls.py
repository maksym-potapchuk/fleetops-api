from rest_framework.routers import DefaultRouter

from .views import DriverModelViewSet

router = DefaultRouter()
router.register(r"", DriverModelViewSet, basename="drivers")

urlpatterns = router.urls
