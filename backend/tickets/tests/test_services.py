import itertools

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Profile
from tickets.models import Category, Ticket, TicketEvent
from tickets.services import (
    TRANSITIONS,
    AssigneeRequired,
    InvalidTransition,
    NotAnAgent,
    allowed_transitions,
    transition,
)

pytestmark = pytest.mark.django_db

S = Ticket.Status
ALL_STATUSES = [S.OPEN, S.ASSIGNED, S.IN_PROGRESS, S.RESOLVED]


def make_user(username, role):
    user = get_user_model().objects.create_user(username, password="x")
    Profile.objects.create(user=user, role=role)
    return user


@pytest.fixture
def agent():
    return make_user("marta", Profile.Role.AGENT)


@pytest.fixture
def other_agent():
    return make_user("luis", Profile.Role.AGENT)


@pytest.fixture
def requester():
    return make_user("ana", Profile.Role.REQUESTER)


@pytest.fixture
def make_ticket(requester):
    category = Category.objects.create(name="Redes")

    def _make(status=S.OPEN, assignee=None, **kwargs):
        return Ticket.objects.create(
            subject="Sin VPN",
            description="No conecta",
            category=category,
            requester=requester,
            status=status,
            assignee=assignee,
            **kwargs,
        )

    return _make


# --- Transiciones válidas -------------------------------------------------------------


def test_open_a_assigned_con_assignee_explicito(make_ticket, agent):
    ticket = make_ticket()

    transition(ticket, S.ASSIGNED, agent, assignee=agent)

    ticket.refresh_from_db()
    assert ticket.status == S.ASSIGNED
    assert ticket.assignee == agent


def test_open_a_assigned_usa_el_assignee_que_ya_tiene(make_ticket, agent):
    ticket = make_ticket(assignee=agent)

    transition(ticket, S.ASSIGNED, agent)

    assert Ticket.objects.get(pk=ticket.pk).assignee == agent


def test_assigned_a_in_progress(make_ticket, agent):
    ticket = make_ticket(S.ASSIGNED, assignee=agent)

    transition(ticket, S.IN_PROGRESS, agent)

    assert Ticket.objects.get(pk=ticket.pk).status == S.IN_PROGRESS


def test_assigned_a_open_desasigna(make_ticket, agent):
    ticket = make_ticket(S.ASSIGNED, assignee=agent)

    transition(ticket, S.OPEN, agent)

    ticket.refresh_from_db()
    assert ticket.status == S.OPEN
    assert ticket.assignee is None


def test_in_progress_a_resolved_rellena_resolved_at(make_ticket, agent):
    ticket = make_ticket(S.IN_PROGRESS, assignee=agent)
    assert ticket.resolved_at is None

    transition(ticket, S.RESOLVED, agent)

    ticket.refresh_from_db()
    assert ticket.status == S.RESOLVED
    assert ticket.resolved_at is not None
    assert ticket.assignee == agent


def test_in_progress_a_assigned_devuelve_y_conserva_assignee(make_ticket, agent):
    ticket = make_ticket(S.IN_PROGRESS, assignee=agent)

    transition(ticket, S.ASSIGNED, agent)

    ticket.refresh_from_db()
    assert ticket.status == S.ASSIGNED
    assert ticket.assignee == agent


def test_resolved_a_in_progress_reabre_y_limpia_resolved_at(make_ticket, agent):
    ticket = make_ticket(S.IN_PROGRESS, assignee=agent)
    transition(ticket, S.RESOLVED, agent)

    transition(ticket, S.IN_PROGRESS, agent)

    ticket.refresh_from_db()
    assert ticket.status == S.IN_PROGRESS
    assert ticket.resolved_at is None


def test_ciclo_completo_deja_un_evento_por_transicion(make_ticket, agent):
    ticket = make_ticket()
    steps = [S.ASSIGNED, S.IN_PROGRESS, S.RESOLVED, S.IN_PROGRESS]

    for step in steps:
        transition(ticket, step, agent, assignee=agent)

    events = list(ticket.events.all())
    assert [(e.from_status, e.to_status) for e in events] == [
        (S.OPEN, S.ASSIGNED),
        (S.ASSIGNED, S.IN_PROGRESS),
        (S.IN_PROGRESS, S.RESOLVED),
        (S.RESOLVED, S.IN_PROGRESS),
    ]
    assert all(e.actor == agent for e in events)


def test_el_evento_de_asignacion_es_assigned_y_el_resto_status_changed(make_ticket, agent):
    ticket = make_ticket()

    transition(ticket, S.ASSIGNED, agent, assignee=agent)
    transition(ticket, S.IN_PROGRESS, agent)

    first, second = ticket.events.all()
    assert first.type == TicketEvent.Type.ASSIGNED
    assert second.type == TicketEvent.Type.STATUS_CHANGED


def test_devolver_con_otro_assignee_registra_reasignacion(make_ticket, agent, other_agent):
    ticket = make_ticket(S.IN_PROGRESS, assignee=agent)

    transition(ticket, S.ASSIGNED, agent, assignee=other_agent)

    ticket.refresh_from_db()
    assert ticket.assignee == other_agent
    assert ticket.events.get().type == TicketEvent.Type.ASSIGNED


def test_transition_sincroniza_el_objeto_del_llamador(make_ticket, agent):
    ticket = make_ticket()

    returned = transition(ticket, S.ASSIGNED, agent, assignee=agent)

    assert returned is ticket
    assert ticket.status == S.ASSIGNED
    assert ticket.assignee == agent


# --- Transiciones inválidas -----------------------------------------------------------

INVALID_PAIRS = [
    (a, b) for a, b in itertools.product(ALL_STATUSES, repeat=2) if b not in TRANSITIONS[a]
]


def test_la_tabla_cubre_todos_los_pares():
    valid = sum(len(targets) for targets in TRANSITIONS.values())
    assert valid + len(INVALID_PAIRS) == len(ALL_STATUSES) ** 2
    assert len(INVALID_PAIRS) == 10  # 16 pares - 6 válidos (incluye las 4 identidades)


@pytest.mark.parametrize(("from_status", "to_status"), INVALID_PAIRS)
def test_transicion_invalida_se_rechaza_sin_efectos(make_ticket, agent, from_status, to_status):
    assignee = None if from_status == S.OPEN else agent
    ticket = make_ticket(from_status, assignee=assignee)
    before = Ticket.objects.get(pk=ticket.pk)

    with pytest.raises(InvalidTransition) as exc:
        transition(ticket, to_status, agent, assignee=agent)

    assert exc.value.code == "invalid_transition"
    assert (exc.value.from_status, exc.value.to_status) == (from_status, to_status)
    after = Ticket.objects.get(pk=ticket.pk)
    assert (after.status, after.assignee, after.resolved_at) == (
        before.status,
        before.assignee,
        before.resolved_at,
    )
    assert not ticket.events.exists()


def test_estado_desconocido_es_transicion_invalida(make_ticket, agent):
    ticket = make_ticket()

    with pytest.raises(InvalidTransition):
        transition(ticket, "archived", agent)


def test_se_valida_contra_el_estado_guardado_y_no_el_del_objeto(make_ticket, agent):
    ticket = make_ticket()
    stale = Ticket.objects.get(pk=ticket.pk)
    transition(ticket, S.ASSIGNED, agent, assignee=agent)

    # `stale` aún cree que está open: open -> assigned ya no vale, la BD manda.
    with pytest.raises(InvalidTransition):
        transition(stale, S.ASSIGNED, agent, assignee=agent)
    assert ticket.events.count() == 1


# --- Asignado, permisos ----------------------------------------------------------------


def test_assigned_sin_assignee_falla(make_ticket, agent):
    ticket = make_ticket()

    with pytest.raises(AssigneeRequired) as exc:
        transition(ticket, S.ASSIGNED, agent)

    assert exc.value.code == "assignee_required"
    assert Ticket.objects.get(pk=ticket.pk).status == S.OPEN
    assert not ticket.events.exists()


def test_no_se_puede_asignar_a_un_solicitante(make_ticket, agent, requester):
    ticket = make_ticket()

    with pytest.raises(NotAnAgent):
        transition(ticket, S.ASSIGNED, agent, assignee=requester)

    assert Ticket.objects.get(pk=ticket.pk).status == S.OPEN


def test_un_solicitante_no_puede_cambiar_estados(make_ticket, requester, agent):
    ticket = make_ticket(assignee=agent)

    with pytest.raises(NotAnAgent) as exc:
        transition(ticket, S.ASSIGNED, requester)

    assert exc.value.code == "not_an_agent"
    assert Ticket.objects.get(pk=ticket.pk).status == S.OPEN
    assert not ticket.events.exists()


def test_actor_sin_perfil_o_nulo_no_puede_cambiar_estados(make_ticket, agent):
    ticket = make_ticket(assignee=agent)
    sin_perfil = get_user_model().objects.create_user("sinperfil", password="x")

    for actor in (sin_perfil, None):
        with pytest.raises(NotAnAgent):
            transition(ticket, S.ASSIGNED, actor)


def test_allowed_transitions_refleja_la_tabla():
    assert allowed_transitions(S.OPEN) == {S.ASSIGNED}
    assert allowed_transitions(S.ASSIGNED) == {S.IN_PROGRESS, S.OPEN}
    assert allowed_transitions(S.IN_PROGRESS) == {S.RESOLVED, S.ASSIGNED}
    assert allowed_transitions(S.RESOLVED) == {S.IN_PROGRESS}
    assert allowed_transitions("archived") == set()
