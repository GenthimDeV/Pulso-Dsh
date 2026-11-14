from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "team"]
    list_filter = ["role", "team"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email"]
    list_select_related = ["user"]


admin.site.unregister(User)


@admin.register(User)
class PulsoUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = ["username", "first_name", "last_name", "email", "role", "is_staff"]
    list_filter = ["profile__role", *UserAdmin.list_filter]
    list_select_related = ["profile"]

    @admin.display(description="role", ordering="profile__role")
    def role(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.role if profile else "—"
