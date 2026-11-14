from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Datos de Pulso asociados a un usuario de Django: su rol y, si es agente, su equipo."""

    class Role(models.TextChoices):
        REQUESTER = "requester", "Requester"
        AGENT = "agent", "Agent"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.REQUESTER)
    team = models.CharField(max_length=100, blank=True, help_text="Equipo o especialidad.")

    def __str__(self):
        return f"{self.user.get_username()} ({self.role})"

    @property
    def is_agent(self):
        return self.role == self.Role.AGENT
