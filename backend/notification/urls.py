from django.urls import path

from . import views

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="notification-list"),
    path(
        "unread-count/",
        views.UnreadCountView.as_view(),
        name="notification-unread-count",
    ),
    path("read-all/", views.MarkAllReadView.as_view(), name="notification-read-all"),
    path("<uuid:pk>/read/", views.MarkReadView.as_view(), name="notification-read"),
    path(
        "<uuid:pk>/resolve/",
        views.ResolveNotificationView.as_view(),
        name="notification-resolve",
    ),
    path(
        "mileage-submit/",
        views.MileageSubmitView.as_view(),
        name="notification-mileage-submit",
    ),
]
