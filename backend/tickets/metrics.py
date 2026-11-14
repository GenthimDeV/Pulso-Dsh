"""Métricas del panel (brief §4). Todo con consultas agregadas: nunca se recorren tickets en Python.

Devuelven solo códigos y números; el frontend pone los textos.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Min, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from accounts.models import Profile

from .models import RejectedTransition, Ticket

Status = Ticket.Status
Priority = Ticket.Priority

RANGES = ("today", "7d", "30d")
DEFAULT_RANGE = "7d"
AGENT_CAPACITY = 10  # brief §4
RESOLUTION_TARGET_HOURS = 8  # brief §4
WEEKS = 12
SLA_AT_RISK_WINDOW = timedelta(hours=1)  # "en riesgo" = vence en menos de 1 h

_UNRESOLVED = ~Q(status=Status.RESOLVED)


def _range_start(range_code, now):
    if range_code == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=7 if range_code == "7d" else 30)


def _week_start(moment):
    """Lunes 00:00 UTC de la semana de `moment` (coincide con TruncWeek)."""
    return (moment - timedelta(days=moment.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _open_at(moment):
    """Tickets que estaban abiertos (no resueltos) en `moment`.

    El estado manda: un ticket `resolved` sin `resolved_at` (dato incoherente) no cuenta como
    abierto en ningún momento, igual que en `open`.
    """
    still_open = Q(resolved_at__gt=moment) | (Q(resolved_at__isnull=True) & _UNRESOLVED)
    return Q(created_at__lte=moment) & still_open


def _counts_by(field, codes):
    """Conteo de abiertos por `field`, con todos los códigos presentes aunque valgan 0."""
    rows = Ticket.objects.filter(_UNRESOLVED).values(field).annotate(n=Count("pk"))
    found = {row[field]: row["n"] for row in rows}
    return {code: found.get(code, 0) for code in codes}


def _weekly_resolution(now):
    first_week = _week_start(now) - timedelta(weeks=WEEKS - 1)
    duration = ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())
    rows = (
        Ticket.objects.filter(resolved_at__gte=first_week)
        .annotate(week=TruncWeek("resolved_at"))
        .values("week")
        .annotate(avg=Avg(duration), n=Count("pk"))
    )
    found = {row["week"]: row for row in rows}
    weeks = []
    for i in range(WEEKS):
        start = first_week + timedelta(weeks=i)
        row = found.get(start)
        hours = round(row["avg"].total_seconds() / 3600, 2) if row else None
        weeks.append({"week_start": start, "avg_hours": hours, "resolved": row["n"] if row else 0})
    return weeks


def _series_days(range_code):
    return 30 if range_code == "30d" else 7


def _day_end(day, now):
    """Fin del día `day` (o `now` si es hoy)."""
    end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
    return min(end, now)


def _daily_series(range_code, now):
    """Series diarias: abiertos al cierre de cada día y resueltos por día (un agregado cada una)."""
    days = [
        (now - timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        for offset in range(_series_days(range_code) - 1, -1, -1)
    ]
    open_counts = Ticket.objects.aggregate(
        **{f"d{i}": Count("pk", filter=_open_at(_day_end(day, now))) for i, day in enumerate(days)}
    )
    resolved_rows = (
        Ticket.objects.filter(resolved_at__gte=days[0], resolved_at__lte=now)
        .annotate(day=TruncDate("resolved_at"))
        .values("day")
        .annotate(n=Count("pk"))
    )
    resolved_by_day = {row["day"]: row["n"] for row in resolved_rows}
    return {
        "open": [{"date": day.date(), "count": open_counts[f"d{i}"]} for i, day in enumerate(days)],
        "resolved": [
            {"date": day.date(), "count": resolved_by_day.get(day.date(), 0)} for day in days
        ],
    }


def _rejected(start, now):
    """Transiciones rechazadas en el periodo y la última (solo códigos)."""
    rows = RejectedTransition.objects.filter(created_at__gte=start, created_at__lte=now)
    latest = rows.first()  # Meta.ordering = -created_at
    return {
        "count": rows.count(),
        "latest": {"from": latest.from_status, "to": latest.to_status} if latest else None,
    }


def summary(range_code=DEFAULT_RANGE, now=None):
    now = now or timezone.now()
    start = _range_start(range_code, now)
    # Periodo anterior: "hoy" se compara con el día de ayer completo; 7d/30d, con la ventana previa.
    previous_start = start - (timedelta(days=1) if range_code == "today" else now - start)
    week_ago = now - timedelta(days=7)

    totals = Ticket.objects.aggregate(
        open=Count("pk", filter=_UNRESOLVED),
        open_week_ago=Count("pk", filter=_open_at(week_ago)),
        unassigned=Count("pk", filter=_UNRESOLVED & Q(assignee__isnull=True)),
        unassigned_urgent=Count(
            "pk", filter=_UNRESOLVED & Q(assignee__isnull=True, priority=Priority.URGENT)
        ),
        oldest_unassigned=Min("created_at", filter=_UNRESOLVED & Q(assignee__isnull=True)),
        resolved=Count("pk", filter=Q(resolved_at__gte=start, resolved_at__lte=now)),
        resolved_previous=Count(
            "pk", filter=Q(resolved_at__gte=previous_start, resolved_at__lt=start)
        ),
        sla_breached=Count("pk", filter=_UNRESOLVED & Q(sla_due_at__lt=now)),
        sla_at_risk=Count(
            "pk",
            filter=_UNRESOLVED & Q(sla_due_at__gte=now, sla_due_at__lt=now + SLA_AT_RISK_WINDOW),
        ),
    )

    return {
        "range": range_code,
        "generated_at": now,
        "open": {"count": totals["open"], "week_ago": totals["open_week_ago"]},
        "unassigned": {
            "count": totals["unassigned"],
            "urgent": totals["unassigned_urgent"],
            "oldest_created_at": totals["oldest_unassigned"],
        },
        "by_priority": _counts_by("priority", Priority.values),
        "by_status": _counts_by_status(),
        "resolved": {"count": totals["resolved"], "previous": totals["resolved_previous"]},
        "sla": {"breached": totals["sla_breached"], "at_risk": totals["sla_at_risk"]},
        "resolution": {
            "target_hours": RESOLUTION_TARGET_HOURS,
            "weekly": _weekly_resolution(now),
        },
        "rejected": _rejected(start, now),
        "series": _daily_series(range_code, now),
    }


def _counts_by_status():
    """Conteo de TODOS los tickets por estado (incluye resueltos)."""
    rows = Ticket.objects.values("status").annotate(n=Count("pk"))
    found = {row["status"]: row["n"] for row in rows}
    return {code: found.get(code, 0) for code in Status.values}


def agent_loads():
    """Agentes activos (también con carga 0) con sus tickets asignados y en curso."""
    agents = (
        get_user_model()
        .objects.filter(profile__role=Profile.Role.AGENT, is_active=True)
        .annotate(
            assigned=Count("assigned_tickets", filter=Q(assigned_tickets__status=Status.ASSIGNED)),
            in_progress=Count(
                "assigned_tickets", filter=Q(assigned_tickets__status=Status.IN_PROGRESS)
            ),
        )
        .select_related("profile")
        .order_by("first_name", "username")
    )
    return [
        {
            "id": agent.pk,
            "username": agent.username,
            "first_name": agent.first_name,
            "last_name": agent.last_name,
            "team": agent.profile.team,
            "assigned": agent.assigned,
            "in_progress": agent.in_progress,
            "capacity": AGENT_CAPACITY,
        }
        for agent in agents
    ]
