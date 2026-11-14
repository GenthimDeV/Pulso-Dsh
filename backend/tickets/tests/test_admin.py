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
    events = list(created.events.all())
    assert [e.type for e in events] == [TicketEvent.Type.CREATED]
    assert events[0].actor == admin_user


def test_comentario_desde_el_admin_genera_evento(admin_client, admin_user, ticket):
    url = reverse("admin:tickets_comment_add")
    base = {"ticket": ticket.pk, "author": admin_user.pk, "body": "Hola"}
    when = {"created_at_0": "2026-11-14", "created_at_1": "10:00:00"}

    assert admin_client.post(url, {**base, **when}).status_code == 302
    assert admin_client.post(url, {**base, **when, "is_internal": "on"}).status_code == 302

    types = list(ticket.events.order_by("pk").values_list("type", flat=True))
    assert types == [
        TicketEvent.Type.CREATED,
        TicketEvent.Type.COMMENTED,
        TicketEvent.Type.INTERNAL_NOTE,
    ]


def test_comentario_inline_genera_evento_solo_al_crearse(admin_client, admin_user, ticket):
    def post(**extra):
        return admin_client.post(
            reverse("admin:tickets_ticket_change", args=[ticket.pk]),
            {
                "subject": ticket.subject,
                "description": ticket.description,
                "priority": ticket.priority,
                "category": ticket.category.pk,
                "requester": ticket.requester.pk,
                "created_at_0": "2026-11-14",
                "created_at_1": "10:00:00",
                "events-TOTAL_FORMS": "0",
                "events-INITIAL_FORMS": "0",
                **extra,
            },
        )

    new = {
        "comments-TOTAL_FORMS": "1",
        "comments-INITIAL_FORMS": "0",
        "comments-0-author": admin_user.pk,
        "comments-0-body": "Nota",
        "comments-0-created_at_0": "2026-11-14",
        "comments-0-created_at_1": "11:00:00",
    }
    assert post(**new).status_code == 302
    comment = ticket.comments.get()
    assert ticket.events.filter(type=TicketEvent.Type.COMMENTED).count() == 1

    edit = {
        "comments-TOTAL_FORMS": "1",
        "comments-INITIAL_FORMS": "1",
        "comments-0-id": comment.pk,
        "comments-0-ticket": ticket.pk,
        "comments-0-author": admin_user.pk,
        "comments-0-body": "Nota editada",
        "comments-0-created_at_0": "2026-11-14",
        "comments-0-created_at_1": "11:00:00",
    }
    assert post(**edit).status_code == 302
    comment.refresh_from_db()
    assert comment.body == "Nota editada"
    assert ticket.events.filter(type=TicketEvent.Type.COMMENTED).count() == 1


def test_asignado_no_editable_desde_el_admin(admin_client, ticket):
    response = admin_client.get(reverse("admin:tickets_ticket_change", args=[ticket.pk]))

    assert "assignee" not in response.context["adminform"].form.fields


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
