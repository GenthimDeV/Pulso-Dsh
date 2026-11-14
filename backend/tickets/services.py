"""Reglas de negocio de los tickets. Las vistas llaman aquí; no repiten la lógica."""

from django.db import transaction
from django.utils import timezone

from .models import Comment, Ticket, TicketEvent

Status = Ticket.Status

# Máquina de estados (brief §4): desde -> destinos permitidos.
TRANSITIONS = {
    Status.OPEN: {Status.ASSIGNED},
    Status.ASSIGNED: {Status.IN_PROGRESS, Status.OPEN},
    Status.IN_PROGRESS: {Status.RESOLVED, Status.ASSIGNED},
    Status.RESOLVED: {Status.IN_PROGRESS},
}


class TransitionError(Exception):
    """Base de los errores de transición. `code` es el código estable para la API."""

    code = "transition_error"

    def __init__(self, message=""):
        super().__init__(message or self.code)


class InvalidTransition(TransitionError):
    """La tabla no permite ir de `from_status` a `to_status` (la API responde 409)."""

    code = "invalid_transition"

    def __init__(self, from_status, to_status):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"No se puede pasar de {from_status} a {to_status}.")


class AssigneeRequired(TransitionError):
    """Pasar a `assigned` exige un agente asignado."""

    code = "assignee_required"


class NotAnAgent(TransitionError):
    """El actor no es agente: solo los agentes cambian estados (la API responde 403)."""

    code = "not_an_agent"


class InvalidAssignee(TransitionError):
    """El asignado no es válido: no es agente, o se pasó en una transición que no asigna.

    Es un error de validación de los datos (la API responde 400/422), no de permisos.
    """

    code = "invalid_assignee"


@transaction.atomic
def create_ticket(requester, subject, description, category, priority=Ticket.Priority.MEDIUM):
    """Crea un ticket `open` a nombre de `requester` y registra el evento `created`."""
    ticket = Ticket.objects.create(
        subject=subject,
        description=description,
        category=category,
        priority=priority,
        requester=requester,
    )
    TicketEvent.objects.create(
        ticket=ticket,
        actor=requester,
        type=TicketEvent.Type.CREATED,
        created_at=ticket.created_at,
    )
    return ticket


def allowed_transitions(status):
    """Destinos válidos desde `status` (la UI los usa para habilitar los botones)."""
    return set(TRANSITIONS.get(status, ()))


def _is_agent(user):
    profile = getattr(user, "profile", None)
    return bool(user and profile and profile.is_agent)


@transaction.atomic
def transition(ticket, to_status, actor, assignee=None):
    """Mueve `ticket` a `to_status` y registra un TicketEvent.

    - Solo un agente puede ejecutarla.
    - `assigned` exige un asignado: `assignee` o el que ya tenga el ticket; debe ser agente.
    - `assignee` solo se admite al pasar a `assigned`; en otro destino es `InvalidAssignee`.
    - `assigned -> open` desasigna; `resolved` rellena `resolved_at`; reabrir lo limpia.
    """
    if not _is_agent(actor):
        raise NotAnAgent("Solo los agentes pueden cambiar el estado de un ticket.")

    # Relee el estado con bloqueo de fila para no transicionar sobre datos obsoletos.
    current = Ticket.objects.select_for_update().get(pk=ticket.pk)
    from_status = current.status

    if to_status not in TRANSITIONS.get(from_status, ()):
        raise InvalidTransition(from_status, to_status)

    if assignee is not None and to_status != Status.ASSIGNED:
        raise InvalidAssignee("Solo se puede indicar un asignado al pasar a 'assigned'.")

    event_type = TicketEvent.Type.STATUS_CHANGED
    now = timezone.now()

    if to_status == Status.ASSIGNED:
        new_assignee = assignee or current.assignee
        if new_assignee is None:
            raise AssigneeRequired("Pasar a 'assigned' exige un agente asignado.")
        if not _is_agent(new_assignee):
            raise InvalidAssignee("Solo un agente puede ser asignado a un ticket.")
        if from_status == Status.OPEN or new_assignee != current.assignee:
            event_type = TicketEvent.Type.ASSIGNED
        current.assignee = new_assignee
    elif to_status == Status.OPEN:
        current.assignee = None

    if to_status == Status.RESOLVED:
        current.resolved_at = now
    elif from_status == Status.RESOLVED:
        current.resolved_at = None

    current.status = to_status
    current.save(update_fields=["status", "assignee", "resolved_at", "updated_at"])
    TicketEvent.objects.create(
        ticket=current,
        actor=actor,
        type=event_type,
        from_status=from_status,
        to_status=to_status,
        created_at=now,
    )

    _sync(ticket, current)
    return ticket


def _sync(ticket, current):
    """Deja el objeto del llamador sincronizado con lo guardado."""
    ticket.status = current.status
    ticket.assignee = current.assignee
    ticket.resolved_at = current.resolved_at
    ticket.updated_at = current.updated_at


@transaction.atomic
def assign(ticket, assignee, actor):
    """Asigna `ticket` a `assignee` (agente) sin cambiar su estado salvo en `open`.

    - `open` -> `assigned` (misma regla que `transition`).
    - `assigned` / `in_progress`: reasigna y registra un evento `assigned` con el mismo estado.
    - `resolved`: no se reasigna (hay que reabrirlo antes): `InvalidTransition`.
    """
    if not _is_agent(actor):
        raise NotAnAgent("Solo los agentes pueden asignar un ticket.")

    current = Ticket.objects.select_for_update().get(pk=ticket.pk)

    if current.status == Status.OPEN:
        return transition(ticket, Status.ASSIGNED, actor, assignee=assignee)
    if current.status == Status.RESOLVED:
        raise InvalidTransition(current.status, current.status)
    if not _is_agent(assignee):
        raise InvalidAssignee("Solo un agente puede ser asignado a un ticket.")
    if assignee == current.assignee:
        return ticket  # sin cambios: no se ensucia el historial

    now = timezone.now()
    current.assignee = assignee
    current.save(update_fields=["assignee", "updated_at"])
    TicketEvent.objects.create(
        ticket=current,
        actor=actor,
        type=TicketEvent.Type.ASSIGNED,
        from_status=current.status,
        to_status=current.status,
        created_at=now,
    )
    _sync(ticket, current)
    return ticket


@transaction.atomic
def add_comment(ticket, author, body, is_internal=False):
    """Añade un comentario (o nota interna) y su evento. Las notas internas son solo de agentes."""
    if is_internal and not _is_agent(author):
        raise NotAnAgent("Solo los agentes pueden escribir notas internas.")

    comment = Comment.objects.create(
        ticket=ticket, author=author, body=body, is_internal=is_internal
    )
    TicketEvent.objects.create(
        ticket=ticket,
        actor=author,
        type=TicketEvent.Type.INTERNAL_NOTE if is_internal else TicketEvent.Type.COMMENTED,
        created_at=comment.created_at,
    )
    return comment
