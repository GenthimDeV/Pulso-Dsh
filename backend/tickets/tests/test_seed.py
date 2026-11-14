from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import Profile
from tickets import seed, seed_data
from tickets.models import Category, Comment, Ticket, TicketEvent
from tickets.services import TRANSITIONS

pytestmark = pytest.mark.django_db

NOW = timezone.now().replace(microsecond=0)
TOTAL_TICKETS = 56
AGENT_CAPACITY = 10  # brief §4


@pytest.fixture
def seeded():
    seed.seed(now=NOW)


def snapshot():
    """Todo lo que el seed decide, sin ids, para comparar dos ejecuciones."""
    tickets = [
        (
            t.code,
            t.subject,
            t.priority,
            t.status,
            t.requester.username,
            t.assignee and t.assignee.username,
            t.created_at,
            t.resolved_at,
            [(e.type, e.actor and e.actor.username, e.created_at) for e in t.events.all()],
            [(c.author.username, c.body, c.is_internal, c.created_at) for c in t.comments.all()],
        )
        for t in Ticket.objects.order_by("code").select_related("requester", "assignee")
    ]
    return tickets


def test_crea_los_datos_esperados(seeded):
    assert Ticket.objects.count() == TOTAL_TICKETS
    assert Profile.objects.filter(role=Profile.Role.AGENT).count() == len(seed_data.AGENTS)
    assert Profile.objects.filter(role=Profile.Role.REQUESTER).count() == len(seed_data.REQUESTERS)
    assert Category.objects.count() == len(seed_data.CATEGORY_TEAM)
    assert Comment.objects.filter(is_internal=True).exists()
    assert Comment.objects.filter(is_internal=False).exists()
    # Todos los estados y prioridades salen representados.
    assert set(Ticket.objects.values_list("status", flat=True)) == set(Ticket.Status.values)
    assert set(Ticket.objects.values_list("priority", flat=True)) == set(Ticket.Priority.values)
    # El solicitante de demo tiene tickets propios que ver.
    assert Ticket.objects.filter(requester__username=seed_data.DEMO_REQUESTER_USERNAME).count() >= 5


def test_cuentas_de_demo(seeded):
    password = seed.DEFAULT_PASSWORD
    agent = authenticate(username=seed_data.DEMO_AGENT_USERNAME, password=password)
    requester = authenticate(username=seed_data.DEMO_REQUESTER_USERNAME, password=password)
    assert agent and agent.profile.is_agent
    assert requester and not requester.profile.is_agent
    for user in get_user_model().objects.all():
        assert not user.is_staff and not user.is_superuser


def test_historial_coherente_con_la_maquina_de_estados(seeded):
    for ticket in Ticket.objects.prefetch_related("events", "comments"):
        events = list(ticket.events.all())  # ordenados por fecha
        assert events[0].type == TicketEvent.Type.CREATED
        assert events[0].created_at == ticket.created_at

        status = Ticket.Status.OPEN
        for event in events:
            if event.type in (TicketEvent.Type.ASSIGNED, TicketEvent.Type.STATUS_CHANGED):
                assert event.from_status == status
                assert event.to_status in TRANSITIONS[status]
                status = event.to_status
        assert status == ticket.status

        # Ningún evento fuera de la vida del ticket.
        assert all(ticket.created_at <= e.created_at <= NOW for e in events)
        assert ticket.updated_at == max(e.created_at for e in events)
        # Un evento por comentario.
        notes = [c for c in ticket.comments.all()]
        comment_events = [
            e
            for e in events
            if e.type in (TicketEvent.Type.COMMENTED, TicketEvent.Type.INTERNAL_NOTE)
        ]
        assert len(notes) == len(comment_events)

        # Campos derivados.
        assert ticket.code and ticket.code.startswith("TK-")
        assert ticket.sla_due_at == Ticket.sla_due_for(ticket.priority, ticket.created_at)
        if ticket.status == Ticket.Status.OPEN:
            assert ticket.assignee is None
        else:
            assert ticket.assignee and ticket.assignee.profile.is_agent
        if ticket.status == Ticket.Status.RESOLVED:
            assert ticket.resolved_at == events[-1].created_at
        else:
            assert ticket.resolved_at is None


def test_comentarios_coherentes(seeded):
    for comment in Comment.objects.select_related("author__profile", "ticket"):
        assert comment.created_at >= comment.ticket.created_at
        assert comment.created_at <= NOW
        if comment.is_internal:  # las notas internas solo las escriben agentes
            assert comment.author.profile.is_agent
        if comment.author == comment.ticket.requester:
            assert not comment.is_internal


def test_la_carga_por_agente_cabe_en_la_capacidad(seeded):
    loads = (
        Ticket.objects.filter(status__in=[Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS])
        .values("assignee")
        .annotate(n=Count("pk"))
    )
    assert loads
    assert max(row["n"] for row in loads) <= AGENT_CAPACITY


def test_hay_tickets_para_el_panel(seeded):
    """El panel necesita ver: sin asignar, SLA vencido y resueltos recientes y antiguos."""
    assert Ticket.objects.filter(status=Ticket.Status.OPEN).exists()
    vencidos = Ticket.objects.exclude(status=Ticket.Status.RESOLVED).filter(sla_due_at__lt=NOW)
    assert vencidos.exists()
    recientes = Ticket.objects.filter(resolved_at__gte=NOW - timedelta(days=7))
    assert recientes.exists()
    assert Ticket.objects.filter(resolved_at__lt=NOW - timedelta(weeks=8)).exists()


def test_reproducible_con_la_misma_semilla():
    seed.seed(now=NOW)
    first = snapshot()
    seed.wipe()
    seed.seed(now=NOW)
    assert snapshot() == first


def test_otra_semilla_da_otros_datos():
    seed.seed(now=NOW)
    first = snapshot()
    seed.wipe()
    seed.seed(now=NOW, rng_seed=7)
    assert snapshot() != first


def test_las_fechas_son_relativas_a_ahora():
    seed.seed(now=NOW)
    first = snapshot()
    seed.wipe()
    shift = timedelta(days=30)
    seed.seed(now=NOW + shift)
    shifted = snapshot()

    def minus_shift(rows):
        return [
            (*r[:6], r[6] - shift, r[7] and r[7] - shift,
             [(t, a, d - shift) for t, a, d in r[8]],
             [(a, b, i, d - shift) for a, b, i, d in r[9]])
            for r in rows
        ]  # fmt: skip

    assert minus_shift(shifted) == first


def test_seed_demo_no_duplica():
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert Ticket.objects.count() == TOTAL_TICKETS
    call_command("seed_demo", stdout=out)
    assert Ticket.objects.count() == TOTAL_TICKETS
    assert "Ya hay datos" in out.getvalue()


def test_reset_demo_restaura_y_respeta_otros_usuarios(seeded):
    other = get_user_model().objects.create_user("ajeno", password="x")
    ticket = Ticket.objects.first()
    ticket.status = Ticket.Status.RESOLVED
    ticket.save()
    Ticket.objects.filter(pk__in=Ticket.objects.values("pk")[:10]).delete()
    Comment.objects.all().delete()

    call_command("reset_demo", "--yes", stdout=StringIO())

    assert Ticket.objects.count() == TOTAL_TICKETS
    assert Comment.objects.exists()
    assert get_user_model().objects.filter(pk=other.pk).exists()
    assert get_user_model().objects.count() == len(seed.demo_usernames()) + 1


def test_reset_demo_sin_confirmacion_no_borra(seeded, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    out = StringIO()
    call_command("reset_demo", stdout=out)
    assert "Cancelado" in out.getvalue()
    assert Ticket.objects.count() == TOTAL_TICKETS

    def no_tty(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_tty)
    with pytest.raises(CommandError):
        call_command("reset_demo")


def test_password_de_demo_configurable(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "otra-clave")
    seed.seed(now=NOW)
    assert authenticate(username=seed_data.DEMO_AGENT_USERNAME, password="otra-clave")
    assert not authenticate(username=seed_data.DEMO_AGENT_USERNAME, password=seed.DEFAULT_PASSWORD)


def test_no_quedan_tickets_sin_codigo(seeded):
    assert not Ticket.objects.filter(Q(code__isnull=True) | Q(code="")).exists()
