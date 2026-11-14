from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from accounts.models import Profile
from tickets.models import Category, Comment, Ticket, TicketEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def requester():
    user = get_user_model().objects.create_user("ana", password="x")
    Profile.objects.create(user=user)
    return user


@pytest.fixture
def category():
    return Category.objects.create(name="Redes")


def make_ticket(requester, category, **kwargs):
    fields = {"subject": "Sin VPN", "description": "No conecta", **kwargs}
    return Ticket.objects.create(requester=requester, category=category, **fields)


def test_codigo_se_genera_desde_el_pk_y_se_guarda(requester, category):
    ticket = make_ticket(requester, category)

    assert ticket.code == f"TK-{1000 + ticket.pk}"
    assert Ticket.objects.get(code=ticket.code) == ticket


def test_codigos_distintos_y_estables_al_volver_a_guardar(requester, category):
    first = make_ticket(requester, category)
    second = make_ticket(requester, category)
    code = first.code

    first.subject = "Otro asunto"
    first.save()

    assert first.code != second.code
    assert Ticket.objects.get(pk=first.pk).code == code


@pytest.mark.parametrize(
    ("priority", "hours"),
    [("urgent", 2), ("high", 8), ("medium", 24), ("low", 72)],
)
def test_sla_se_calcula_al_crear_segun_prioridad(requester, category, priority, hours):
    ticket = make_ticket(requester, category, priority=priority)

    assert ticket.sla_due_at == ticket.created_at + timedelta(hours=hours)


def test_sla_no_se_recalcula_al_cambiar_prioridad(requester, category):
    ticket = make_ticket(requester, category, priority="low")
    due = ticket.sla_due_at

    ticket.priority = "urgent"
    ticket.save()
    ticket.refresh_from_db()

    assert ticket.sla_due_at == due


def test_respeta_created_at_del_pasado(requester, category):
    past = timezone.now() - timedelta(days=10)

    ticket = make_ticket(requester, category, created_at=past, priority="high")
    ticket.refresh_from_db()

    assert ticket.created_at == past
    assert ticket.sla_due_at == past + timedelta(hours=8)


def test_valores_por_defecto(requester, category):
    ticket = make_ticket(requester, category)

    assert ticket.status == Ticket.Status.OPEN
    assert ticket.priority == Ticket.Priority.MEDIUM
    assert ticket.assignee is None
    assert ticket.resolved_at is None
    assert requester.profile.role == Profile.Role.REQUESTER
    assert not requester.profile.is_agent


def test_categoria_con_tickets_no_se_puede_borrar(requester, category):
    make_ticket(requester, category)

    with pytest.raises(ProtectedError):
        category.delete()


def test_comentarios_y_eventos_se_borran_con_el_ticket(requester, category):
    ticket = make_ticket(requester, category)
    Comment.objects.create(ticket=ticket, author=requester, body="Hola", is_internal=False)
    TicketEvent.objects.create(ticket=ticket, actor=requester, type=TicketEvent.Type.CREATED)

    ticket.delete()

    assert not Comment.objects.exists()
    assert not TicketEvent.objects.exists()


def test_str(requester, category):
    ticket = make_ticket(requester, category)
    note = Comment.objects.create(ticket=ticket, author=requester, body="x", is_internal=True)

    assert str(ticket) == f"{ticket.code} · Sin VPN"
    assert str(note) == f"nota interna en {ticket.code}"
    assert str(category) == "Redes"
    assert str(requester.profile) == "ana (requester)"
