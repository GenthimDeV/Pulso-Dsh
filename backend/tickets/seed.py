"""Datos de demostración reproducibles.

Con la misma semilla y el mismo `now` salen exactamente los mismos datos; con otro `now`
todas las fechas se desplazan igual, así el panel siempre parece vivo. Las transiciones se
hacen con `services.transition` (la máquina de estados no se reescribe aquí) y luego se
retocan las fechas de sus eventos para colocarlos en el pasado.
"""

import os
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import Profile

from . import seed_data as data
from .models import Category, Comment, Ticket, TicketEvent
from .services import transition

DEFAULT_SEED = 42
DEFAULT_PASSWORD = "pulso-demo"  # cuentas públicas de un demo con datos ficticios

Status = Ticket.Status
EventType = TicketEvent.Type

# Reparto de los 56 tickets por estado final.
STATUS_COUNTS = {Status.OPEN: 10, Status.ASSIGNED: 8, Status.IN_PROGRESS: 12, Status.RESOLVED: 26}
# Prioridad -> peso.
PRIORITY_WEIGHTS = {"urgent": 12, "high": 28, "medium": 40, "low": 20}
# Edad máxima y mínima (horas) del ticket según su estado final.
AGE_HOURS = {
    Status.OPEN: (0.5, 120),
    Status.ASSIGNED: (1, 96),
    Status.IN_PROGRESS: (3, 150),
    Status.RESOLVED: (24, 84 * 24),  # 12 semanas: las que enseña la gráfica de resolución
}
# Horas que tarda cada paso (según el estado al que se pasa).
STEP_HOURS = {
    Status.ASSIGNED: (0.2, 6),
    Status.OPEN: (0.5, 8),
    Status.IN_PROGRESS: (0.2, 4),
    Status.RESOLVED: (1, 14),
}


def demo_usernames():
    return [a[0] for a in data.AGENTS] + [r[0] for r in data.REQUESTERS]


def is_seeded():
    User = get_user_model()
    return Ticket.objects.exists() or User.objects.filter(username__in=demo_usernames()).exists()


def demo_password():
    return os.environ.get("DEMO_PASSWORD") or DEFAULT_PASSWORD


@transaction.atomic
def wipe():
    """Borra los tickets (con comentarios e historial), las categorías y las cuentas del seed.

    Las cuentas de demo se identifican solo por su nombre de usuario (`demo_usernames`): un
    usuario real con uno de esos nombres también se borraría, y `is_seeded` lo tomaría por
    datos de demo. Los nombres están reservados para el seed. Los demás usuarios no se tocan.
    """
    counts = {"tickets": Ticket.objects.count()}
    Ticket.objects.all().delete()
    Category.objects.filter(name__in=data.CATEGORY_TEAM).delete()
    get_user_model().objects.filter(username__in=demo_usernames()).delete()
    _reset_sequences(Ticket, Comment, TicketEvent)
    return counts


def _reset_sequences(*models):
    """Vuelve a numerar desde 1 las tablas vaciadas: el código TK- sale del pk del ticket."""
    sequences = [{"table": m._meta.db_table, "column": m._meta.pk.column} for m in models]
    for sql in connection.ops.sequence_reset_by_name_sql(no_style(), sequences):
        with connection.cursor() as cursor:
            cursor.execute(sql)


@transaction.atomic
def seed(now=None, rng_seed=DEFAULT_SEED, password=None):
    """Crea los datos de demostración. Parte de una base sin datos de demo (ver `is_seeded`)."""
    now = (now or timezone.now()).replace(microsecond=0)
    rng = random.Random(rng_seed)

    agents, requesters = _create_users(password or demo_password())
    categories = {name: Category.objects.create(name=name) for name in data.CATEGORY_TEAM}
    team_agent = {a.profile.team: a for a in agents}

    for status, template_index, repeated in _plan(rng):
        _create_ticket(
            rng, now, status, data.TICKET_TEMPLATES[template_index], repeated,
            categories, agents, requesters, team_agent,
        )  # fmt: skip

    return {
        "agents": len(agents),
        "requesters": len(requesters),
        "tickets": Ticket.objects.count(),
        "comments": Comment.objects.count(),
        "events": TicketEvent.objects.count(),
    }


def _create_users(password):
    User = get_user_model()
    hashed = make_password(password)  # un solo hash: PBKDF2 es lento a propósito

    def build(username, first, last, role, team=""):
        user = User.objects.create(
            username=username,
            first_name=first,
            last_name=last,
            email=f"{username}@example.com",
            password=hashed,
        )
        Profile.objects.create(user=user, role=role, team=team)
        return user

    agents = [build(u, f, ln, Profile.Role.AGENT, team) for u, f, ln, team in data.AGENTS]
    requesters = [build(u, f, ln, Profile.Role.REQUESTER) for u, f, ln in data.REQUESTERS]
    return agents, requesters


def _plan(rng):
    """Una entrada por ticket: (estado final, plantilla, ¿plantilla repetida?)."""
    statuses = [s for s, n in STATUS_COUNTS.items() for _ in range(n)]
    rng.shuffle(statuses)
    n_templates = len(data.TICKET_TEMPLATES)
    templates = list(range(n_templates)) * 2
    rng.shuffle(templates)
    seen = set()
    plan = []
    for status, template in zip(statuses, templates, strict=False):
        plan.append((status, template, template in seen))
        seen.add(template)
    return plan


def _path(status, rng):
    """Estados por los que pasa un ticket: casi todos directos, algunos con vueltas."""
    roll = rng.random()
    A, O, I, R = Status.ASSIGNED, Status.OPEN, Status.IN_PROGRESS, Status.RESOLVED  # noqa: E741
    if status == Status.OPEN:
        return []
    if status == Status.ASSIGNED:
        return [A, O, A] if roll < 0.15 else [A]
    if status == Status.IN_PROGRESS:
        return [A, I, A, I] if roll < 0.15 else [A, I]
    if roll < 0.10:
        return [A, I, R, I, R]  # reabierto
    if roll < 0.20:
        return [A, I, A, I, R]  # devuelto a la cola del agente
    return [A, I, R]


def _hours(rng, bounds):
    return rng.uniform(*bounds)


def _create_ticket(
    rng, now, status, template, repeated, categories, agents, requesters, team_agent
):
    category_name, subject, description = template
    place = rng.choice(data.PLACES)
    priority = rng.choices(list(PRIORITY_WEIGHTS), weights=list(PRIORITY_WEIGHTS.values()))[0]
    # La cuenta de demo del solicitante abre más tickets que el resto.
    requester = rng.choices(requesters, weights=[3] + [1] * (len(requesters) - 1))[0]
    lead = agents[0]  # despachador: reparte tickets
    agent = team_agent[data.CATEGORY_TEAM[category_name]]
    if rng.random() < 0.25:
        agent = rng.choice(agents)

    path = _path(status, rng)
    delays = [_hours(rng, STEP_HOURS[step]) for step in path]
    lo, hi = AGE_HOURS[status]
    age = lo + (hi - lo) * rng.random() ** (1.5 if status == Status.RESOLVED else 1)
    age = max(age, sum(delays) + rng.uniform(0.5, 6))  # nada ocurre en el futuro
    created_at = (now - timedelta(hours=age)).replace(microsecond=0)

    ticket = Ticket.objects.create(
        subject=f"{subject} ({place})" if repeated else subject,
        description=f"{description} Ubicación: {place}.",
        priority=priority,
        category=categories[category_name],
        requester=requester,
        created_at=created_at,
    )
    TicketEvent.objects.create(
        ticket=ticket,
        actor=requester,
        type=EventType.CREATED,
        to_status=Status.OPEN,
        created_at=created_at,
    )

    # Historial: cada paso pasa por el servicio y luego se coloca en su fecha.
    moment = created_at
    times = []
    previous = Status.OPEN
    for step, delay in zip(path, delays, strict=True):
        moment = (moment + timedelta(hours=delay)).replace(microsecond=0)
        assignee = None
        if step == Status.ASSIGNED and previous == Status.OPEN:
            if times:  # tras desasignar, lo coge otra persona
                agent = rng.choice([a for a in agents if a != agent])
            assignee = agent
            actor = lead if rng.random() < 0.5 else agent
        else:
            actor = agent
        transition(ticket, step, actor, assignee)
        TicketEvent.objects.filter(pk=ticket.events.latest("pk").pk).update(created_at=moment)
        if step == Status.RESOLVED:
            Ticket.objects.filter(pk=ticket.pk).update(resolved_at=moment)
        times.append(moment)
        previous = step

    last = _add_comments(rng, now, ticket, status, agent, times)
    last_activity = max([created_at, *times, *([last] if last else [])])
    Ticket.objects.filter(pk=ticket.pk).update(updated_at=last_activity)


def _add_comments(rng, now, ticket, status, agent, times):
    """Conversación del ticket (con notas internas). Devuelve la fecha del último comentario."""
    if not times:  # sin asignar: a lo sumo, el solicitante insiste
        kinds = ["requester"] if rng.random() < 0.25 else []
        start = ticket.created_at + timedelta(minutes=5)
    else:
        kinds = ["agent"]
        if rng.random() < 0.5:
            kinds += ["requester", "agent"]
        if rng.random() < 0.45:
            kinds.insert(rng.randint(0, len(kinds)), "note")
        start = times[0]
    end = times[-1] if status == Status.RESOLVED else now - timedelta(minutes=1)
    if not kinds or end <= start + timedelta(minutes=1):
        return None

    span = (end - start).total_seconds()
    moments = sorted(start + timedelta(seconds=span * rng.random()) for _ in kinds)
    comments, events = [], []
    for kind, moment in zip(kinds, moments, strict=True):
        moment = moment.replace(microsecond=0)
        is_note = kind == "note"
        author = ticket.requester if kind == "requester" else agent
        pool = {
            "requester": data.REQUESTER_COMMENTS,
            "agent": data.AGENT_COMMENTS,
            "note": data.INTERNAL_NOTES,
        }[kind]
        comments.append(
            Comment(
                ticket=ticket,
                author=author,
                body=rng.choice(pool),
                is_internal=is_note,
                created_at=moment,
            )
        )
        events.append(
            TicketEvent(
                ticket=ticket,
                actor=author,
                type=EventType.INTERNAL_NOTE if is_note else EventType.COMMENTED,
                created_at=moment,
            )
        )
    Comment.objects.bulk_create(comments)
    TicketEvent.objects.bulk_create(events)
    return comments[-1].created_at
