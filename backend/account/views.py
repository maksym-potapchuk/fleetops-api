import logging

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import UserSerializer

logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        logger.info(
            "Login attempt",
            extra={
                "status_code": 100,
                "status_message": "Continue",
                "operation_type": "USER_LOGIN_REQUEST",
                "service": "DJANGO",
                "email": request.data.get("email", ""),
            },
        )
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            logger.error(
                "Login failed",
                extra={
                    "status_code": 401,
                    "status_message": "Unauthorized",
                    "operation_type": "USER_LOGIN_FAILED",
                    "service": "DJANGO",
                    "email": request.data.get("email", ""),
                },
                exc_info=True,
            )
            raise

        if response.status_code == 200:
            response.set_cookie(
                "access_token",
                response.data["access"],
                httponly=True,
                secure=settings.SECURE_COOKIES,
                samesite="Lax",
            )
            response.set_cookie(
                "refresh_token",
                response.data["refresh"],
                httponly=True,
                secure=settings.SECURE_COOKIES,
                samesite="Lax",
            )
            response.data = {"detail": "ok"}
            logger.info(
                "Login successful",
                extra={
                    "status_code": 200,
                    "status_message": "OK",
                    "operation_type": "USER_LOGIN_SUCCESS",
                    "service": "DJANGO",
                    "email": request.data.get("email", ""),
                },
            )

        return response


class RefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        logger.info(
            "Token refresh attempt",
            extra={
                "status_code": 100,
                "status_message": "Continue",
                "operation_type": "USER_TOKEN_REFRESH_REQUEST",
                "service": "DJANGO",
            },
        )
        refresh = request.COOKIES.get("refresh_token")
        request.data["refresh"] = refresh

        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            logger.error(
                "Token refresh failed",
                extra={
                    "status_code": 401,
                    "status_message": "Unauthorized",
                    "operation_type": "USER_TOKEN_REFRESH_FAILED",
                    "service": "DJANGO",
                },
                exc_info=True,
            )
            raise

        if response.status_code == 200:
            response.set_cookie(
                "access_token",
                response.data["access"],
                httponly=True,
                secure=settings.SECURE_COOKIES,
                samesite="Lax",
            )
            response.data = {"detail": "refreshed"}
            logger.info(
                "Token refresh successful",
                extra={
                    "status_code": 200,
                    "status_message": "OK",
                    "operation_type": "USER_TOKEN_REFRESH_SUCCESS",
                    "service": "DJANGO",
                },
            )

        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(
            "Logout attempt",
            extra={
                "status_code": 100,
                "status_message": "Continue",
                "operation_type": "USER_LOGOUT_REQUEST",
                "service": "DJANGO",
                "user_id": str(request.user.id),
            },
        )
        refresh = request.COOKIES.get("refresh_token")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                logger.warning(
                    "Logout: refresh token already invalid or expired",
                    extra={
                        "status_code": 400,
                        "status_message": "Bad Request",
                        "operation_type": "USER_LOGOUT_TOKEN_ERROR",
                        "service": "DJANGO",
                        "user_id": str(request.user.id),
                    },
                )

        response = Response({"detail": "logout"})
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        logger.info(
            "Logout successful",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "USER_LOGOUT_SUCCESS",
                "service": "DJANGO",
                "user_id": str(request.user.id),
            },
        )
        return response


class UserMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info(
            "User profile requested",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "USER_PROFILE_VIEW",
                "service": "DJANGO",
                "user_id": str(request.user.id),
            },
        )
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        logger.info(
            "User profile update attempt",
            extra={
                "status_code": 100,
                "status_message": "Continue",
                "operation_type": "USER_PROFILE_UPDATE_REQUEST",
                "service": "DJANGO",
                "user_id": str(request.user.id),
            },
        )
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except Exception:
            logger.error(
                "User profile update failed",
                extra={
                    "status_code": 500,
                    "status_message": "Internal Server Error",
                    "operation_type": "USER_PROFILE_UPDATE_FAILED",
                    "service": "DJANGO",
                    "user_id": str(request.user.id),
                },
                exc_info=True,
            )
            raise

        logger.info(
            "User profile updated successfully",
            extra={
                "status_code": 200,
                "status_message": "OK",
                "operation_type": "USER_PROFILE_UPDATE_SUCCESS",
                "service": "DJANGO",
                "user_id": str(request.user.id),
            },
        )
        return Response(serializer.data)
