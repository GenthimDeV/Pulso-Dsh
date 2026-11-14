import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Profile
from tickets.models import Category, Ticket, TicketEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def ticket(admin_user):
    category = Category.objects.create(name="Redes")
    ticket = Ticket.objects.create(
        subject="Sin VPN", description="No conecta", category=category, requester=admin_user
    )
    TicketEvent.objects.create(ticket=ticket, actor=admin_user, type=TicketEvent.Type.CREATED)
    return ticket


@pytest.mark.parametrize(
    "model", ["tickets_ticket", "tickets_category", "tickets_comment", "tickets_ticketevent"]
)
def test_changelists_responden(admin_client, ticket, model):
    response = admin_client.get(reverse(f"admin:{model}_changelist"))

    assert response.status_code == 200


def test_formulario_de_ticket_y_alta_desde_el_admin(admin_client, admin_user, ticket):
    assert (
        admin_client.get(reverse("admin:tickets_ticket_change", args=[ticket.pk])).status_code
        == 200
    )
    assert admin_client.get(reverse("admin:tickets_ticket_add")).status_code == 200

    data = {
        "subject": "Impresora",
        "description": "Atasco",
        "priority": "high",
        "category": ticket.category.pk,
        "requester": admin_user.pk,
        "assignee": "",
        "created_at_0": "2026-11-14",
        "created_at_1": "10:00:00",
        # Formularios de gestión de los inlines (comentarios editables, eventos de solo lectura).
        "comments-TOTAL_FORMS": "0",
        "comments-INITIAL_FORMS": "0",
        "events-TOTAL_FORMS": "0",
        "events-INITIAL_FORMS": "0",
    }
    response = admin_client.post(reverse("admin:tickets_ticket_add"), data)

    assert response.status_code == 302, response.context["adminform"].form.errors
    created = Ticket.objects.get(subject="Impresora")
    assert created.code.startswith("TK-")
    assert created.status == Ticket.Status.OPEN
    assert created.sla_due_at is not None


def test_estado_no_editable_desde_el_admin(admin_client, ticket):
    response = admin_client.get(reverse("admin:tickets_ticket_change", args=[ticket.pk]))

    assert "status" not in response.context["adminform"].form.fields


def test_usuario_con_inline_de_perfil(admin_client):
    user = get_user_model().objects.create_user("luis", password="x")
    Profile.objects.create(user=user, role=Profile.Role.AGENT, team="Redes")

    assert admin_client.get(reverse("admin:auth_user_changelist")).status_code == 200
    response = admin_client.get(reverse("admin:auth_user_change", args=[user.pk]))
    assert response.status_code == 200
    assert b"Redes" in response.content
