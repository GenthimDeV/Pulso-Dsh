"""Permisos por rol. Se combinan con `get_queryset` en las vistas de tickets (3.2+)."""

from rest_framework.permissions import BasePermission

from .models import Profile


def user_role(user):
    """Rol del usuario ('agent' o 'requester'), o None si no está autenticado o no tiene perfil."""
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)  # RelatedObjectDoesNotExist es un AttributeError
    return profile.role if profile else None


class IsAgent(BasePermission):
    """Solo agentes."""

    def has_permission(self, request, view):
        return user_role(request.user) == Profile.Role.AGENT


class IsRequester(BasePermission):
    """Solo solicitantes."""

    def has_permission(self, request, view):
        return user_role(request.user) == Profile.Role.REQUESTER
