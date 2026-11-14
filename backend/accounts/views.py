from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from .serializers import MeSerializer


@api_view(["GET"])
def me(request):
    """Usuario autenticado y su rol."""
    return Response(MeSerializer(request.user).data)


class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"


class RefreshView(TokenRefreshView):
    """Devuelve access y un refresh nuevo (rotación); el refresh usado queda en la blacklist."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"


class LogoutView(TokenBlacklistView):
    """Invalida en servidor el refresh recibido. Responde 200 `{}`; con un refresh inválido, 401."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"
