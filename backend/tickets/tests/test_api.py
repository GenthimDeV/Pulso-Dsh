from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Profile
from tickets.models import Category, Comment, RejectedTransition, Ticket, TicketEvent

pytestmark = pytest.mark.django_db

URL = "/api/v1/tickets/"
S = Ticket.Status
P = Ticket.Priority


def make_user(username, role=None, **extra):
    user = get_user_model().objects.create_user(username, password="x", **extra)
    if role:
        Profile.objects.create(user=user, role=role)
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def agent():
    return make_user("marta", Profile.Role.AGENT, first_name="Marta", last_name="Gil")


@pytest.fixture
def other_agent():
    return make_user("luis", Profile.Role.AGENT)


@pytest.fixture
def ana():
    return make_user("ana", Profile.Role.REQUESTER, first_name="Ana", last_name="Pérez")


@pytest.fixture
def beto():
    return make_user("beto", Profile.Role.REQUESTER)


@pytest.fixture
def category():
    return Category.objects.create(name="Redes")


def make_ticket(requester, category, **kwargs):
    kwargs.setdefault("subject", "Sin red")
    kwargs.setdefault("description", "No hay conexión")
    return Ticket.objects.create(requester=requester, category=category, **kwargs)


def codes(response):
    return [t["code"] for t in response.json()["results"]]


# --- Autenticación y permisos -------------------------------------------------


def test_sin_token_devuelve_401(category):
    assert APIClient().get(URL).status_code == 401
    assert APIClient().post(URL, {}).status_code == 401


def test_usuario_sin_perfil_devuelve_403(category):
    user = make_user("sinperfil")

    assert client_for(user).get(URL).status_code == 403
    assert client_for(user).post(URL, {}, format="json").status_code == 403


def test_metodos_no_soportados(agent, ana, category):
    ticket = make_ticket(ana, category)

    assert client_for(agent).delete(f"{URL}{ticket.code}/").status_code == 405
    assert client_for(agent).put(f"{URL}{ticket.code}/", {}, format="json").status_code == 405


# --- Lista: visibilidad por rol ----------------------------------------------


def test_solicitante_solo_ve_sus_tickets(ana, beto, category):
    mine = make_ticket(ana, category)
    make_ticket(beto, category)

    response = client_for(ana).get(URL)

    assert response.status_code == 200
    assert codes(response) == [mine.code]
    assert response.json()["count"] == 1


def test_agente_ve_todos_los_tickets(agent, ana, beto, category):
    make_ticket(ana, category)
    make_ticket(beto, category)

    assert client_for(agent).get(URL).json()["count"] == 2


def test_lista_expone_codigos_y_relaciones(agent, ana, category):
    ticket = make_ticket(ana, category, priority=P.HIGH)
    ticket.assignee = agent
    ticket.status = S.ASSIGNED
    ticket.save()

    item = client_for(agent).get(URL).json()["results"][0]

    assert item["code"] == ticket.code
    assert item["priority"] == "high"
    assert item["status"] == "assigned"
    assert item["category"] == {"id": category.id, "name": "Redes"}
    assert item["requester"]["username"] == "ana"
    assert item["assignee"]["username"] == "marta"
    assert "description" not in item and "comments" not in item


# --- Lista: filtros, búsqueda, orden y paginación ----------------------------


def test_filtra_por_status_y_priority(agent, ana, category):
    a = make_ticket(ana, category, priority=P.URGENT)
    make_ticket(ana, category, priority=P.LOW)
    Ticket.objects.filter(pk=a.pk).update(status=S.RESOLVED)
    client = client_for(agent)

    assert codes(client.get(URL, {"status": "resolved"})) == [a.code]
    assert codes(client.get(URL, {"priority": "urgent"})) == [a.code]
    assert client.get(URL, {"status": "resolved", "priority": "low"}).json()["count"] == 0


def test_filtro_con_valor_invalido_devuelve_400(agent, category):
    client = client_for(agent)

    assert client.get(URL, {"status": "nope"}).status_code == 400
    assert client.get(URL, {"priority": "nope"}).status_code == 400
    assert client.get(URL, {"assignee": "abc"}).status_code == 400
    assert client.get(URL, {"ordering": "subject"}).status_code == 400


@pytest.mark.parametrize(
    "value", ["²", "٣", "99999999999999999999", "9223372036854775808", "-1", "1.5"]
)
def test_assignee_numerico_no_valido_devuelve_400_y_no_500(agent, category, value):
    assert client_for(agent).get(URL, {"assignee": value}).status_code == 400


@pytest.mark.parametrize("value", ["--created_at", "---priority", "-"])
def test_ordering_con_guiones_de_mas_devuelve_400(agent, category, value):
    assert client_for(agent).get(URL, {"ordering": value}).status_code == 400


def test_filtra_por_asignado(agent, other_agent, ana, category):
    mine = make_ticket(ana, category, assignee=agent)
    theirs = make_ticket(ana, category, assignee=other_agent)
    free = make_ticket(ana, category)
    client = client_for(agent)

    assert codes(client.get(URL, {"assignee": agent.id})) == [mine.code]
    assert codes(client.get(URL, {"assignee": "me"})) == [mine.code]
    assert codes(client.get(URL, {"assignee": "none"})) == [free.code]
    assert codes(client.get(URL, {"assignee": other_agent.id})) == [theirs.code]


def test_busca_por_asunto_codigo_y_solicitante(agent, ana, beto, category):
    by_subject = make_ticket(ana, category, subject="Impresora atascada")
    by_requester = make_ticket(beto, category, subject="Otra cosa")
    client = client_for(agent)

    assert codes(client.get(URL, {"search": "impresora"})) == [by_subject.code]
    assert codes(client.get(URL, {"search": by_requester.code})) == [by_requester.code]
    assert codes(client.get(URL, {"search": "pérez"})) == [by_subject.code]
    assert codes(client.get(URL, {"search": "beto"})) == [by_requester.code]
    assert client.get(URL, {"search": "inexistente"}).json()["count"] == 0


def test_la_busqueda_ignora_el_caracter_nul(agent, ana, category):
    ticket = make_ticket(ana, category, subject="Impresora atascada")
    client = client_for(agent)

    assert codes(client.get(URL, {"search": "impre\x00sora"})) == [ticket.code]
    assert client.get(URL, {"search": "\x00"}).status_code == 200


def test_los_filtros_respetan_la_visibilidad_del_solicitante(ana, beto, category):
    make_ticket(beto, category, subject="Impresora de Beto")

    response = client_for(ana).get(URL, {"search": "impresora"})

    assert response.json()["count"] == 0
    # Filtrar por un asignado tampoco amplía lo que ve.
    assert client_for(ana).get(URL, {"assignee": "none"}).json()["count"] == 0


def test_orden_por_defecto_y_explicito(agent, ana, category):
    now = timezone.now()
    old = make_ticket(ana, category, created_at=now - timedelta(days=2))
    new = make_ticket(ana, category, created_at=now)
    client = client_for(agent)

    assert codes(client.get(URL)) == [new.code, old.code]
    assert codes(client.get(URL, {"ordering": "created_at"})) == [old.code, new.code]


def test_orden_por_prioridad_es_por_gravedad(agent, ana, category):
    low = make_ticket(ana, category, priority=P.LOW)
    urgent = make_ticket(ana, category, priority=P.URGENT)
    medium = make_ticket(ana, category, priority=P.MEDIUM)
    high = make_ticket(ana, category, priority=P.HIGH)
    client = client_for(agent)

    assert codes(client.get(URL, {"ordering": "priority"})) == [
        urgent.code,
        high.code,
        medium.code,
        low.code,
    ]
    assert codes(client.get(URL, {"ordering": "-priority"})) == [
        low.code,
        medium.code,
        high.code,
        urgent.code,
    ]


def test_paginacion(agent, ana, category):
    for _ in range(25):
        make_ticket(ana, category)
    client = client_for(agent)

    first = client.get(URL).json()
    second = client.get(URL, {"page": 2}).json()

    assert first["count"] == 25
    assert len(first["results"]) == 20
    assert first["next"] is not None
    assert len(second["results"]) == 5
    assert len(client.get(URL, {"page_size": 5}).json()["results"]) == 5
    assert len(client.get(URL, {"page_size": 1000}).json()["results"]) == 25


def test_lista_no_hace_consultas_por_ticket(agent, ana, beto, category):
    def count_queries(n):
        for _ in range(n):
            make_ticket(ana, category, assignee=agent)
        with CaptureQueriesContext(connection) as ctx:
            client_for(agent).get(URL)
        return len(ctx)

    assert count_queries(2) == count_queries(10)


# --- Detalle -----------------------------------------------------------------


def _ticket_con_conversacion(agent, ana, category):
    ticket = make_ticket(ana, category)
    TicketEvent.objects.create(ticket=ticket, actor=ana, type=TicketEvent.Type.CREATED)
    Comment.objects.create(ticket=ticket, author=ana, body="Hola")
    Comment.objects.create(ticket=ticket, author=agent, body="Nota privada", is_internal=True)
    TicketEvent.objects.create(ticket=ticket, actor=agent, type=TicketEvent.Type.INTERNAL_NOTE)
    Comment.objects.create(ticket=ticket, author=agent, body="Lo miramos")
    TicketEvent.objects.create(ticket=ticket, actor=agent, type=TicketEvent.Type.COMMENTED)
    return ticket


def test_agente_ve_detalle_con_notas_internas_y_transiciones(agent, ana, category):
    ticket = _ticket_con_conversacion(agent, ana, category)

    data = client_for(agent).get(f"{URL}{ticket.code}/").json()

    assert data["code"] == ticket.code
    assert data["description"] == "No hay conexión"
    assert [c["body"] for c in data["comments"]] == ["Hola", "Nota privada", "Lo miramos"]
    assert [c["is_internal"] for c in data["comments"]] == [False, True, False]
    assert [e["type"] for e in data["events"]] == ["created", "internal_note", "commented"]
    assert data["allowed_transitions"] == ["assigned"]


def test_solicitante_no_ve_notas_internas_ni_su_evento(agent, ana, category):
    ticket = _ticket_con_conversacion(agent, ana, category)

    data = client_for(ana).get(f"{URL}{ticket.code}/").json()

    assert [c["body"] for c in data["comments"]] == ["Hola", "Lo miramos"]
    assert all(not c["is_internal"] for c in data["comments"])
    assert [e["type"] for e in data["events"]] == ["created", "commented"]
    assert "Nota privada" not in str(data)
    assert data["allowed_transitions"] == []


def test_solicitante_recibe_404_ante_un_ticket_ajeno(ana, beto, category):
    ticket = make_ticket(beto, category)

    assert client_for(ana).get(f"{URL}{ticket.code}/").status_code == 404


def test_detalle_de_codigo_inexistente_devuelve_404(agent):
    assert client_for(agent).get(f"{URL}TK-9999/").status_code == 404


def test_detalle_no_hace_consultas_por_comentario(agent, ana, category):
    def count_queries(n):
        ticket = make_ticket(ana, category)
        for _ in range(n):
            Comment.objects.create(ticket=ticket, author=agent, body="x")
            TicketEvent.objects.create(ticket=ticket, actor=agent, type=TicketEvent.Type.COMMENTED)
        with CaptureQueriesContext(connection) as ctx:
            client_for(agent).get(f"{URL}{ticket.code}/")
        return len(ctx)

    assert count_queries(1) == count_queries(8)


# --- Creación ----------------------------------------------------------------


def payload(category, **extra):
    return {
        "subject": "VPN caída",
        "description": "No conecta desde casa",
        "category": category.id,
        **extra,
    }


def test_solicitante_crea_un_ticket(ana, category):
    response = client_for(ana).post(URL, payload(category, priority="urgent"), format="json")

    assert response.status_code == 201
    data = response.json()
    ticket = Ticket.objects.get(code=data["code"])
    assert data["code"].startswith("TK-")
    assert data["status"] == "open"
    assert data["priority"] == "urgent"
    assert data["requester"]["username"] == "ana"
    assert data["assignee"] is None
    assert ticket.requester == ana
    assert ticket.sla_due_at == ticket.created_at + timedelta(hours=2)
    assert [e["type"] for e in data["events"]] == ["created"]
    event = ticket.events.get()
    assert event.type == TicketEvent.Type.CREATED
    assert event.actor == ana


def test_prioridad_por_defecto_es_media(ana, category):
    response = client_for(ana).post(URL, payload(category), format="json")

    assert response.json()["priority"] == "medium"


def test_agente_tambien_puede_crear_a_su_nombre(agent, category):
    response = client_for(agent).post(URL, payload(category), format="json")

    assert response.status_code == 201
    assert response.json()["requester"]["username"] == "marta"
    assert response.json()["allowed_transitions"] == ["assigned"]


def test_crear_ignora_requester_status_y_assignee_del_cuerpo(ana, beto, agent, category):
    body = payload(category, requester=beto.id, status="resolved", assignee=agent.id, code="TK-1")

    response = client_for(ana).post(URL, body, format="json")

    assert response.status_code == 201
    ticket = Ticket.objects.get(code=response.json()["code"])
    assert ticket.requester == ana
    assert ticket.status == S.OPEN
    assert ticket.assignee is None
    assert ticket.code != "TK-1"


@pytest.mark.parametrize(
    "change",
    [
        {"subject": ""},
        {"subject": "x" * 201},
        {"description": ""},
        {"category": 99999},
        {"priority": "critical"},
    ],
)
def test_crear_con_datos_invalidos_devuelve_400_y_no_crea(ana, category, change):
    response = client_for(ana).post(URL, {**payload(category), **change}, format="json")

    assert response.status_code == 400
    assert not Ticket.objects.exists()
    assert not TicketEvent.objects.exists()


@pytest.mark.parametrize(
    ("change", "errors"),
    [
        ({"subject": ""}, {"subject": "blank"}),
        ({"subject": "x" * 201}, {"subject": "max_length"}),
        ({"description": ""}, {"description": "blank"}),
        ({"category": 99999}, {"category": "does_not_exist"}),
        ({"priority": "critical"}, {"priority": "invalid_choice"}),
    ],
)
def test_crear_con_datos_invalidos_devuelve_codigos(ana, category, change, errors):
    response = client_for(ana).post(URL, {**payload(category), **change}, format="json")

    assert response.status_code == 400
    assert response.json() == errors


def test_crear_sin_campos_devuelve_required_por_campo(ana, category):
    response = client_for(ana).post(URL, {}, format="json")

    assert response.json() == {
        "subject": "required",
        "description": "required",
        "category": "required",
    }


def test_categorias_para_agentes_y_solicitantes(agent, ana, category):
    Category.objects.create(name="Accesos")

    for user in (agent, ana):
        response = client_for(user).get("/api/v1/categories/")
        assert response.status_code == 200
        assert [c["name"] for c in response.json()] == ["Accesos", "Redes"]
        assert set(response.json()[0]) == {"id", "name"}


def test_categorias_exigen_sesion_y_perfil():
    assert APIClient().get("/api/v1/categories/").status_code == 401
    sin_perfil = make_user("sinperfil")
    assert client_for(sin_perfil).get("/api/v1/categories/").status_code == 403


def test_crear_sin_campos_obligatorios_devuelve_400(ana, category):
    response = client_for(ana).post(URL, {}, format="json")

    assert response.status_code == 400
    assert {"subject", "description", "category"} <= set(response.json())


def test_el_ticket_creado_aparece_en_la_lista_del_solicitante(ana, category):
    created = client_for(ana).post(URL, payload(category), format="json").json()

    assert codes(client_for(ana).get(URL)) == [created["code"]]


# --- Transiciones, asignación y comentarios ----------------------------------


def act(ticket, action):
    return f"{URL}{ticket.code}/{action}/"


def post(user, ticket, action, body):
    return client_for(user).post(act(ticket, action), body, format="json")


def test_acciones_sin_token_devuelven_401(ana, category):
    ticket = make_ticket(ana, category)

    for action in ("transition", "assign", "comments"):
        assert APIClient().post(act(ticket, action), {}, format="json").status_code == 401


def test_agente_asigna_un_ticket_abierto(agent, other_agent, ana, category):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "assign", {"assignee": other_agent.pk})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == S.ASSIGNED
    assert data["assignee"]["id"] == other_agent.pk
    assert data["allowed_transitions"] == ["in_progress", "open"]
    assert data["events"][-1]["type"] == "assigned"
    assert data["events"][-1]["actor"]["id"] == agent.pk


def test_agente_reasigna_sin_cambiar_el_estado(agent, other_agent, ana, category):
    ticket = make_ticket(ana, category, status=S.IN_PROGRESS, assignee=agent)

    response = post(agent, ticket, "assign", {"assignee": other_agent.pk})

    assert response.status_code == 200
    assert response.json()["status"] == S.IN_PROGRESS
    ticket.refresh_from_db()
    assert ticket.assignee == other_agent
    event = ticket.events.get()
    assert (event.type, event.from_status, event.to_status) == (
        "assigned",
        S.IN_PROGRESS,
        S.IN_PROGRESS,
    )


def test_reasignar_al_mismo_agente_no_crea_evento(agent, ana, category):
    ticket = make_ticket(ana, category, status=S.ASSIGNED, assignee=agent)

    response = post(agent, ticket, "assign", {"assignee": agent.pk})

    assert response.status_code == 200
    assert not ticket.events.exists()


def test_asignar_un_ticket_resuelto_devuelve_409(agent, other_agent, ana, category):
    ticket = make_ticket(ana, category, status=S.RESOLVED, assignee=agent)

    response = post(agent, ticket, "assign", {"assignee": other_agent.pk})

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


@pytest.mark.parametrize("status_", [S.OPEN, S.ASSIGNED])
def test_asignar_a_alguien_que_no_es_agente_devuelve_400(agent, ana, beto, category, status_):
    current = None if status_ == S.OPEN else agent
    ticket = make_ticket(ana, category, status=status_, assignee=current)

    response = post(agent, ticket, "assign", {"assignee": beto.pk})

    assert response.status_code == 400
    assert response.json() == {"code": "invalid_assignee"}
    ticket.refresh_from_db()
    assert (ticket.status, ticket.assignee) == (status_, current)


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({}, "required"),
        ({"assignee": 999999}, "does_not_exist"),
        ({"assignee": "x"}, "incorrect_type"),
        ({"assignee": None}, "null"),
    ],
)
def test_asignar_con_datos_invalidos_devuelve_400_con_codigo(agent, ana, category, body, code):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "assign", body)

    assert response.status_code == 400
    assert response.json() == {"assignee": code}


@pytest.mark.parametrize("action_", ["assign", "transition"])
def test_asignar_a_un_agente_inactivo_devuelve_400(agent, ana, category, action_):
    inactive = make_user("baja", Profile.Role.AGENT, is_active=False)
    ticket = make_ticket(ana, category)
    body = {"assignee": inactive.pk}
    if action_ == "transition":
        body["to"] = "assigned"

    response = post(agent, ticket, action_, body)

    assert response.status_code == 400
    assert response.json() == {"code": "invalid_assignee"}
    ticket.refresh_from_db()
    assert (ticket.status, ticket.assignee) == (S.OPEN, None)


def test_solicitante_no_puede_asignar_ni_transicionar(ana, agent, category):
    ticket = make_ticket(ana, category)

    assert post(ana, ticket, "assign", {"assignee": agent.pk}).status_code == 403
    assert post(ana, ticket, "transition", {"to": "assigned"}).status_code == 403
    ticket.refresh_from_db()
    assert ticket.status == S.OPEN


def test_usuario_sin_perfil_no_puede_actuar(ana, category):
    ticket = make_ticket(ana, category)
    user = make_user("sinperfil")

    for action in ("transition", "assign", "comments"):
        assert post(user, ticket, action, {}).status_code == 403


def test_transicion_valida_devuelve_el_detalle(agent, ana, category):
    ticket = make_ticket(ana, category, status=S.ASSIGNED, assignee=agent)

    response = post(agent, ticket, "transition", {"to": "in_progress"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == S.IN_PROGRESS
    assert data["allowed_transitions"] == ["assigned", "resolved"]
    last = data["events"][-1]
    assert (last["type"], last["from_status"], last["to_status"]) == (
        "status_changed",
        "assigned",
        "in_progress",
    )


def test_transicion_a_assigned_con_assignee_en_el_cuerpo(agent, other_agent, ana, category):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "transition", {"to": "assigned", "assignee": other_agent.pk})

    assert response.status_code == 200
    assert response.json()["assignee"]["id"] == other_agent.pk


def test_resolver_rellena_resolved_at(agent, ana, category):
    ticket = make_ticket(ana, category, status=S.IN_PROGRESS, assignee=agent)

    data = post(agent, ticket, "transition", {"to": "resolved"}).json()

    assert data["resolved_at"] is not None


def test_transicion_invalida_devuelve_409_con_codigo(agent, ana, category):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "transition", {"to": "resolved"})

    assert response.status_code == 409
    assert response.json() == {"code": "invalid_transition", "from": "open", "to": "resolved"}
    ticket.refresh_from_db()
    assert ticket.status == S.OPEN
    assert not ticket.events.exists()


def test_pasar_a_assigned_sin_asignado_devuelve_400(agent, ana, category):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "transition", {"to": "assigned"})

    assert response.status_code == 400
    assert response.json() == {"code": "assignee_required"}


def test_assignee_en_una_transicion_que_no_asigna_devuelve_400(agent, other_agent, ana, category):
    ticket = make_ticket(ana, category, status=S.ASSIGNED, assignee=agent)

    response = post(agent, ticket, "transition", {"to": "in_progress", "assignee": other_agent.pk})

    assert response.status_code == 400
    assert response.json() == {"code": "invalid_assignee"}


@pytest.mark.parametrize(
    ("body", "errors"),
    [
        ({}, {"to": "required"}),
        ({"to": "nope"}, {"to": "invalid_choice"}),
        ({"to": "assigned", "assignee": 999999}, {"assignee": "does_not_exist"}),
    ],
)
def test_transicion_con_datos_invalidos_devuelve_400_con_codigos(
    agent, ana, category, body, errors
):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "transition", body)

    assert response.status_code == 400
    assert response.json() == errors


def test_transicion_de_un_codigo_inexistente_devuelve_404(agent):
    response = client_for(agent).post(f"{URL}TK-0/transition/", {"to": "assigned"}, format="json")

    assert response.status_code == 404


def test_solicitante_comenta_su_ticket(ana, agent, category):
    ticket = make_ticket(ana, category)

    response = post(ana, ticket, "comments", {"body": "Sigue igual"})

    assert response.status_code == 201
    data = response.json()
    assert (data["body"], data["is_internal"], data["author"]["id"]) == (
        "Sigue igual",
        False,
        ana.pk,
    )
    assert ticket.events.get().type == "commented"
    detail = client_for(agent).get(f"{URL}{ticket.code}/").json()
    assert [c["body"] for c in detail["comments"]] == ["Sigue igual"]


def test_solicitante_no_comenta_un_ticket_ajeno(ana, beto, category):
    ticket = make_ticket(beto, category)

    response = post(ana, ticket, "comments", {"body": "Hola"})

    assert response.status_code == 404
    assert not Comment.objects.exists()


def test_solicitante_no_puede_escribir_notas_internas(ana, category):
    ticket = make_ticket(ana, category)

    response = post(ana, ticket, "comments", {"body": "Hola", "is_internal": True})

    assert response.status_code == 403
    assert response.json() == {"code": "not_an_agent"}
    assert not Comment.objects.exists()
    assert not ticket.events.exists()


def test_agente_escribe_nota_interna_y_el_solicitante_no_la_ve(agent, ana, category):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "comments", {"body": "Secreto", "is_internal": True})

    assert response.status_code == 201
    assert response.json()["is_internal"] is True
    assert ticket.events.get().type == "internal_note"
    detail = client_for(ana).get(f"{URL}{ticket.code}/").json()
    assert "Secreto" not in str(detail)
    assert detail["events"] == []


def test_agente_comenta_cualquier_ticket(agent, ana, category):
    ticket = make_ticket(ana, category)

    response = post(agent, ticket, "comments", {"body": "En ello"})

    assert response.status_code == 201
    assert response.json()["author"]["id"] == agent.pk


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({}, "required"),
        ({"body": ""}, "blank"),
        ({"body": "   "}, "blank"),
        ({"body": "x" * 5001}, "max_length"),
    ],
)
def test_comentario_invalido_devuelve_400_con_codigo(ana, category, body, code):
    ticket = make_ticket(ana, category)

    response = post(ana, ticket, "comments", body)

    assert response.status_code == 400
    assert response.json() == {"body": code}
    assert not Comment.objects.exists()


def test_las_acciones_no_aceptan_get(agent, ana, category):
    ticket = make_ticket(ana, category)

    for action in ("transition", "assign", "comments"):
        assert client_for(agent).get(act(ticket, action)).status_code == 405


def test_transicion_invalida_registra_el_rechazo(agent, ana, category):
    ticket = make_ticket(ana, category)

    post(agent, ticket, "transition", {"to": "resolved"})

    rejected = RejectedTransition.objects.get()
    assert (rejected.ticket, rejected.actor) == (ticket, agent)
    assert (rejected.from_status, rejected.to_status) == ("open", "resolved")


def test_rechazos_identicos_seguidos_se_registran_una_vez(agent, ana, category):
    ticket = make_ticket(ana, category)

    for _ in range(3):
        post(agent, ticket, "transition", {"to": "resolved"})

    assert RejectedTransition.objects.count() == 1


def test_los_rechazos_por_ticket_tienen_tope(agent, ana, category, monkeypatch):
    from tickets import services

    monkeypatch.setattr(services, "REJECTIONS_PER_TICKET", 2)
    monkeypatch.setattr(services, "REJECTION_THROTTLE", timedelta(0))
    ticket = make_ticket(ana, category)

    for _ in range(4):
        post(agent, ticket, "transition", {"to": "resolved"})

    assert RejectedTransition.objects.filter(ticket=ticket).count() == 2


def test_otros_errores_y_transiciones_validas_no_registran_rechazo(agent, ana, category):
    ticket = make_ticket(ana, category)

    post(agent, ticket, "transition", {"to": "assigned"})  # falta asignado: 400
    post(agent, ticket, "transition", {"to": "nope"})  # datos inválidos: 400
    post(agent, ticket, "transition", {"to": "assigned", "assignee": agent.pk})  # válida

    assert not RejectedTransition.objects.exists()
