from .views import DriverModelViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"", DriverModelViewSet, basename="drivers")

urlpatterns = router.urls
