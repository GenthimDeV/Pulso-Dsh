from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

CODE_PREFIX = "TK-"
CODE_OFFSET = 1000  # el primer ticket es TK-1001: los códigos parecen de un sistema en uso


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    class Priority(models.TextChoices):
        URGENT = "urgent", "Urgent"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    # Horas de SLA por prioridad (brief §4).
    SLA_HOURS = {
        Priority.URGENT: 2,
        Priority.HIGH: 8,
        Priority.MEDIUM: 24,
        Priority.LOW: 72,
    }

    # Se rellena en save() a partir del pk; vacío solo entre el INSERT y el UPDATE.
    code = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="tickets")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_tickets"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    # default (y no auto_now_add) para que el seed pueda crear tickets con fechas pasadas.
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    sla_due_at = models.DateTimeField(editable=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assignee", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.code} · {self.subject}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if is_new and self.sla_due_at is None:
            self.sla_due_at = self.sla_due_for(self.priority, self.created_at)
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new and not self.code:
                # El código se deriva del pk: único y sin condiciones de carrera.
                # Dentro de la transacción: si el UPDATE falla, el INSERT se revierte.
                self.code = f"{CODE_PREFIX}{CODE_OFFSET + self.pk}"
                type(self).objects.filter(pk=self.pk).update(code=self.code)

    @classmethod
    def sla_due_for(cls, priority, created_at):
        try:
            hours = cls.SLA_HOURS[priority]
        except KeyError:
            raise ValueError(f"Prioridad inválida: {priority!r}") from None
        return created_at + timedelta(hours=hours)


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comments"
    )
    body = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Nota interna: solo la ven agentes.")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        kind = "nota interna" if self.is_internal else "comentario"
        return f"{kind} en {self.ticket.code}"


class TicketEvent(models.Model):
    """Historial del ticket. Lo escribe la capa de servicios (2.2), no las vistas."""

    class Type(models.TextChoices):
        CREATED = "created", "Created"
        ASSIGNED = "assigned", "Assigned"
        STATUS_CHANGED = "status_changed", "Status changed"
        COMMENTED = "commented", "Commented"
        INTERNAL_NOTE = "internal_note", "Internal note"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_events",
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    from_status = models.CharField(max_length=20, choices=Ticket.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Ticket.Status.choices, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["ticket", "created_at"])]

    def __str__(self):
        return f"{self.ticket.code} · {self.type}"
