from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import Profile
from tickets import metrics
from tickets.models import Category, Ticket

pytestmark = pytest.mark.django_db

# Miércoles 2026-11-11 12:00 UTC: la semana empieza el lunes 2026-11-09.
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
S = Ticket.Status
P = Ticket.Priority


def hours_ago(h):
    return NOW - timedelta(hours=h)


def make_user(username, role, **extra):
    user = get_user_model().objects.create_user(username, password="x", **extra)
    Profile.objects.create(user=user, role=role, team=extra.pop("team", ""))
    return user


@pytest.fixture
def agent():
    return make_user("marta", Profile.Role.AGENT, first_name="Marta")


@pytest.fixture
def other_agent():
    return make_user("luis", Profile.Role.AGENT, first_name="Luis")


@pytest.fixture
def requester():
    return make_user("ana", Profile.Role.REQUESTER)


@pytest.fixture
def category():
    return Category.objects.create(name="Redes")


@pytest.fixture
def make_ticket(requester, category):
    def _make(created_hours_ago=1, resolved_hours_ago=None, **kwargs):
        kwargs.setdefault("subject", "Sin red")
        kwargs.setdefault("description", "x")
        created = hours_ago(created_hours_ago)
        resolved = hours_ago(resolved_hours_ago) if resolved_hours_ago is not None else None
        if resolved is not None:
            kwargs["status"] = S.RESOLVED
        return Ticket.objects.create(
            requester=requester,
            category=category,
            created_at=created,
            resolved_at=resolved,
            **kwargs,
        )

    return _make


def test_resumen_vacio_devuelve_ceros_y_todas_las_claves():
    data = metrics.summary("7d", now=NOW)
    assert data["open"] == {"count": 0, "week_ago": 0}
    assert data["unassigned"] == {"count": 0, "urgent": 0, "oldest_created_at": None}
    assert data["by_priority"] == {"urgent": 0, "high": 0, "medium": 0, "low": 0}
    assert data["by_status"] == {"open": 0, "assigned": 0, "in_progress": 0, "resolved": 0}
    assert data["resolved"] == {"count": 0, "previous": 0}
    assert data["sla"] == {"breached": 0, "at_risk": 0}
    assert len(data["resolution"]["weekly"]) == 12
    assert all(w["avg_hours"] is None and w["resolved"] == 0 for w in data["resolution"]["weekly"])


def test_abiertos_sin_asignar_prioridad_y_estado(make_ticket, agent):
    make_ticket(created_hours_ago=5, priority=P.URGENT)  # sin asignar, el más antiguo
    make_ticket(created_hours_ago=2, priority=P.LOW)  # sin asignar
    make_ticket(created_hours_ago=3, priority=P.HIGH, status=S.ASSIGNED, assignee=agent)
    make_ticket(created_hours_ago=4, priority=P.HIGH, status=S.IN_PROGRESS, assignee=agent)
    make_ticket(created_hours_ago=6, resolved_hours_ago=1, priority=P.MEDIUM, assignee=agent)

    data = metrics.summary("7d", now=NOW)

    assert data["open"]["count"] == 4
    assert data["unassigned"] == {"count": 2, "urgent": 1, "oldest_created_at": hours_ago(5)}
    assert data["by_priority"] == {"urgent": 1, "high": 2, "medium": 0, "low": 1}  # sin resueltos
    assert data["by_status"] == {"open": 2, "assigned": 1, "in_progress": 1, "resolved": 1}


def test_variacion_frente_a_la_semana_anterior(make_ticket):
    week = 24 * 7
    make_ticket(created_hours_ago=week + 10)  # abierto hoy y hace una semana
    make_ticket(created_hours_ago=week + 10, resolved_hours_ago=week + 2)  # resuelto antes
    make_ticket(created_hours_ago=week + 10, resolved_hours_ago=5)  # abierto hace 1 sem.
    make_ticket(created_hours_ago=3)  # nuevo: no existía hace una semana

    data = metrics.summary("7d", now=NOW)

    assert data["open"] == {"count": 2, "week_ago": 2}


@pytest.mark.parametrize(
    ("range_code", "inside", "previous"),
    [
        ("today", 12, 30),  # hoy desde las 00:00 (hace 12 h); ayer = de hace 36 h a hace 12 h
        ("7d", 24 * 3, 24 * 10),
        ("30d", 24 * 20, 24 * 40),
    ],
)
def test_resueltos_en_el_rango_y_en_el_anterior(make_ticket, range_code, inside, previous):
    make_ticket(created_hours_ago=500, resolved_hours_ago=inside - 1 if inside > 1 else 0)
    make_ticket(created_hours_ago=900, resolved_hours_ago=previous - 1)
    make_ticket(created_hours_ago=2000, resolved_hours_ago=1500)  # fuera de ambos

    data = metrics.summary(range_code, now=NOW)

    assert data["resolved"] == {"count": 1, "previous": 1}


def test_sla_vencido_y_en_riesgo(make_ticket, agent):
    # sla = created + horas de prioridad. urgent=2h, medium=24h.
    make_ticket(created_hours_ago=3, priority=P.URGENT)  # vencido hace 1 h
    make_ticket(created_hours_ago=1.5, priority=P.URGENT)  # vence en 30 min -> en riesgo
    make_ticket(created_hours_ago=1, priority=P.MEDIUM)  # vence en 23 h -> ni lo uno ni lo otro
    make_ticket(created_hours_ago=10, resolved_hours_ago=9, priority=P.URGENT)  # resuelto

    data = metrics.summary("7d", now=NOW)

    assert data["sla"] == {"breached": 1, "at_risk": 1}


def test_tiempo_medio_de_resolucion_por_semana(make_ticket):
    # Semana actual (desde el lunes 09/11 00:00): 2 tickets de 4 h y 8 h -> media 6 h.
    make_ticket(created_hours_ago=10, resolved_hours_ago=6)
    make_ticket(created_hours_ago=10, resolved_hours_ago=2)
    # Semana anterior: 1 ticket de 20 h.
    make_ticket(created_hours_ago=24 * 7 + 30, resolved_hours_ago=24 * 7 + 10)
    # Fuera de las 12 semanas.
    make_ticket(created_hours_ago=24 * 7 * 13, resolved_hours_ago=24 * 7 * 13 - 5)

    weekly = metrics.summary("7d", now=NOW)["resolution"]["weekly"]

    assert [w["week_start"] for w in weekly][-1] == datetime(2026, 11, 9, tzinfo=UTC)
    assert weekly[-1]["avg_hours"] == 6.0 and weekly[-1]["resolved"] == 2
    assert weekly[-2]["avg_hours"] == 20.0 and weekly[-2]["resolved"] == 1
    assert sum(w["resolved"] for w in weekly) == 3


def test_el_resumen_usa_un_numero_fijo_de_consultas(make_ticket, agent):
    for i in range(15):
        make_ticket(created_hours_ago=i + 1, priority=P.HIGH)
    with CaptureQueriesContext(connection) as queries:
        metrics.summary("30d", now=NOW)
    assert len(queries) == 4  # totales, por prioridad, por estado, semanas


def test_agentes_con_carga_y_capacidad(make_ticket, agent, other_agent):
    make_ticket(status=S.ASSIGNED, assignee=agent)
    make_ticket(status=S.ASSIGNED, assignee=agent)
    make_ticket(status=S.IN_PROGRESS, assignee=agent)
    make_ticket(created_hours_ago=5, resolved_hours_ago=1, assignee=agent)  # resuelto: no cuenta

    with CaptureQueriesContext(connection) as queries:
        rows = metrics.agent_loads()

    assert len(queries) == 1
    by_name = {row["username"]: row for row in rows}
    assert by_name["marta"]["assigned"] == 2
    assert by_name["marta"]["in_progress"] == 1
    assert by_name["marta"]["capacity"] == 10
    assert by_name["luis"]["assigned"] == 0 and by_name["luis"]["in_progress"] == 0
    assert len(rows) == 2  # los solicitantes no aparecen


# --- API ----------------------------------------------------------------------


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


@pytest.mark.parametrize("url", ["/api/v1/metrics/summary/", "/api/v1/agents/"])
def test_permisos_agente_si_solicitante_403_anonimo_401(url, agent, requester):
    assert client_for(agent).get(url).status_code == 200
    assert client_for(requester).get(url).status_code == 403
    assert client_for().get(url).status_code == 401


def test_resumen_por_api_y_rango_por_defecto(agent, make_ticket):
    make_ticket(priority=P.HIGH)
    response = client_for(agent).get("/api/v1/metrics/summary/")
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "7d"
    assert body["open"]["count"] == 1
    assert body["by_priority"]["high"] == 1


@pytest.mark.parametrize("value", ["today", "7d", "30d"])
def test_rangos_validos(agent, value):
    response = client_for(agent).get("/api/v1/metrics/summary/", {"range": value})
    assert response.status_code == 200
    assert response.json()["range"] == value


@pytest.mark.parametrize("value", ["90d", "zzz", "7D", "%00"])
def test_rango_invalido_da_400_con_codigo(agent, value):
    response = client_for(agent).get("/api/v1/metrics/summary/", {"range": value})
    assert response.status_code == 400
    assert response.json() == {"range": "invalid_choice"}


def test_agentes_por_api(agent, other_agent, make_ticket):
    make_ticket(status=S.ASSIGNED, assignee=agent)
    response = client_for(agent).get("/api/v1/agents/")
    assert response.status_code == 200
    rows = {row["username"]: row for row in response.json()}
    assert rows["marta"]["assigned"] == 1 and rows["marta"]["capacity"] == 10
    assert set(rows["luis"]) >= {"id", "first_name", "last_name", "team", "in_progress"}
