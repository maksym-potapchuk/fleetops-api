from django.urls import path

from .views import LoginView, LogoutView, RefreshView, UnsetSessionView, UserMeAPIView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("refresh/", RefreshView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("me/", UserMeAPIView.as_view()),
    path("unset-session/", UnsetSessionView.as_view()),
]
