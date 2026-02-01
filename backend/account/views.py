from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer

class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            response.set_cookie(
                "access_token",
                response.data["access"],
                httponly=True,
                samesite="Lax",
            )
            response.set_cookie(
                "refresh_token",
                response.data["refresh"],
                httponly=True,
                samesite="Lax",
            )
            response.data = {"detail": "ok"}

        return response


class RefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh = request.COOKIES.get("refresh_token")
        request.data["refresh"] = refresh

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            response.set_cookie(
                "access_token",
                response.data["access"],
                httponly=True,
                samesite="Lax",
            )
            response.data = {"detail": "refreshed"}

        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.COOKIES.get("refresh_token")
        if refresh:
            RefreshToken(refresh).blacklist()

        response = Response({"detail": "logout"})
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response


class UserMeAPIView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self, request):
        serializer=UserSerializer(request.user)
        return Response(serializer.data)
    
    def patch(self, request):
        serializer=UserSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)