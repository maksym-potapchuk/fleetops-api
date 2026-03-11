from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# All v1 app routes — grouped so v2 can be added alongside without touching each app
v1_patterns = [
    path("auth/", include("account.urls")),
    path("driver/", include("driver.urls")),
    path("vehicle/", include("vehicle.urls")),
    path("fleet/", include("fleet_management.urls")),
    path("expense/", include("expense.urls")),
    path("notifications/", include("notification.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(v1_patterns)),
    # path("api/v2/", include("v2.urls")),  # future
    path("", include("django_prometheus.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
