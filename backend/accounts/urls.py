from django.urls import path

from .views import LoginView, LogoutView, RefreshView, me

urlpatterns = [
    path("auth/token/", LoginView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", me, name="me"),
]
