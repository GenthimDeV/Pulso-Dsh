from rest_framework import serializers

from .permissions import user_role


class MeSerializer(serializers.Serializer):
    """Usuario actual. El rol es un código (`agent`/`requester`); el frontend lo traduce."""

    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()

    def get_role(self, user):
        return user_role(user)

    def get_team(self, user):
        profile = getattr(user, "profile", None)
        return profile.team if profile else ""
