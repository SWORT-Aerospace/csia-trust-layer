"""Read-side queries for each role's board. Always scoped to one location."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils import timezone

from .models import AuditEvent, StaffMember, Table, Task, WorkerHeartbeat
from .permissions import can
from .states import PairingStatus, TableState, TaskKind, TaskState

WORKER_NAME = "dispatch-timer"
RECENT = timedelta(minutes=20)

_TASK_RELATED = ("table", "table__section", "owner", "offered_to", "assigned_by", "completed_by", "pairing_resolved_by", "team_ready_by", "visit")


def tasks(location):
    return Task.objects.filter(location=location).select_related(*_TASK_RELATED)


def _recent_done(qs, now):
    return qs.filter(state=TaskState.COMPLETED, completed_at__gte=now - RECENT).order_by("-completed_at")


def runner_board(staff):
    now = timezone.now()
    base = tasks(staff.location).filter(kind__in=[TaskKind.RUN, TaskKind.COURSE])
    open_pool = base.none()
    if staff.location.profile.open_claim_when_escalated:
        open_pool = base.filter(state=TaskState.ESCALATED)
    return {
        "offers": base.filter(state=TaskState.OFFERED, offered_to=staff).order_by("offer_expires_at"),
        "mine": base.filter(state=TaskState.CLAIMED, owner=staff).order_by("claimed_at"),
        "open_pool": open_pool.order_by("escalated_at"),
        "done": _recent_done(base.filter(completed_by=staff), now)[:5],
    }


def busser_board(staff):
    now = timezone.now()
    base = tasks(staff.location).filter(kind=TaskKind.RESET)
    open_pool = base.none()
    if staff.location.profile.open_claim_when_escalated:
        open_pool = base.filter(state=TaskState.ESCALATED)
    return {
        "offers": base.filter(state=TaskState.OFFERED, offered_to=staff).order_by("offer_expires_at"),
        "mine": base.filter(state=TaskState.CLAIMED, owner=staff).order_by("claimed_at"),
        "open_pool": open_pool.order_by("escalated_at"),
        "done": _recent_done(base.filter(completed_by=staff), now)[:5],
    }


def pass_board(staff):
    now = timezone.now()
    base = tasks(staff.location).filter(kind__in=[TaskKind.RUN, TaskKind.COURSE])
    seated = (
        Table.objects.filter(location=staff.location, is_active=True, state=TableState.OCCUPIED)
        .select_related("current_visit", "section")
        .order_by("sort", "label")
    )
    return {
        "open": base.filter(state__in=TaskState.OPEN).order_by("created_at"),
        "done": _recent_done(base, now)[:8],
        "seated_tables": seated,
    }


def captain_board(staff):
    now = timezone.now()
    base = tasks(staff.location)
    courses = base.filter(kind=TaskKind.COURSE)
    return {
        "staged": courses.filter(state=TaskState.STAGED).order_by("staged_at"),
        "returned": base.filter(state=TaskState.ESCALATED).order_by("escalated_at"),
        "in_flight": courses.filter(state__in=[TaskState.OFFERED, TaskState.CLAIMED]).order_by("released_at"),
        "done": _recent_done(courses, now)[:6],
        "runners": on_shift_workers(staff.location, "runner"),
        "bussers": on_shift_workers(staff.location, "busser"),
    }


def sommelier_board(staff):
    now = timezone.now()
    courses = tasks(staff.location).filter(kind=TaskKind.COURSE)
    return {
        "pending": courses.filter(
            pairing_status=PairingStatus.PENDING, state__in=[TaskState.STAGED, TaskState.ESCALATED]
        ).order_by("staged_at"),
        "resolved": courses.filter(
            pairing_status__in=[PairingStatus.READY, PairingStatus.NOT_NEEDED], pairing_resolved_at__gte=now - RECENT
        ).order_by("-pairing_resolved_at")[:8],
    }


def lead_board(staff):
    base = tasks(staff.location)
    return {
        "escalated": base.filter(state=TaskState.ESCALATED).order_by("escalated_at"),
        "offered": base.filter(state=TaskState.OFFERED).order_by("offer_expires_at"),
        "claimed": base.filter(state=TaskState.CLAIMED).order_by("claimed_at"),
        "runners": on_shift_workers(staff.location, "runner"),
        "bussers": on_shift_workers(staff.location, "busser"),
    }


def tables_board(staff):
    open_resets = Task.objects.filter(kind=TaskKind.RESET, state__in=TaskState.OPEN).select_related("owner", "offered_to")
    tables = (
        Table.objects.filter(location=staff.location, is_active=True)
        .select_related("current_visit", "section")
        .prefetch_related(Prefetch("tasks", queryset=open_resets, to_attr="open_resets"))
        .order_by("section__sort", "section__name", "sort", "label")
    )
    if "server" in staff.role_set and not (staff.role_set & {"host", "lead", "captain", "manager"}):
        mine = list(staff.sections.values_list("pk", flat=True))
        if mine:
            tables = tables.filter(section_id__in=mine)
    counts = {state: 0 for state, _ in TableState.CHOICES}
    rows = list(tables)
    for table in rows:
        counts[table.state] += 1
        table.reset_task = table.open_resets[0] if table.open_resets else None
    return {"tables": rows, "counts": counts}


def on_shift_workers(location, role):
    return StaffMember.objects.filter(location=location, is_active=True, on_shift=True, role_grants__role=role).order_by(
        "display_name"
    )


def stalled(location):
    """Work that needs a manager's attention right now."""
    now = timezone.now()
    base = tasks(location)
    claimed_cutoff = now - timedelta(minutes=location.stall_minutes)
    items = []
    for task in base.filter(state=TaskState.ESCALATED).order_by("escalated_at"):
        items.append(("Nobody owns it", task))
    for task in base.filter(state=TaskState.OFFERED, offer_expires_at__lt=now - timedelta(seconds=10)):
        items.append(("Offer overdue — is the timer worker running?", task))
    for task in base.filter(state=TaskState.CLAIMED, claimed_at__lt=claimed_cutoff).order_by("claimed_at"):
        items.append((f"Claimed over {location.stall_minutes} min ago, not done", task))
    for task in base.filter(state=TaskState.STAGED, staged_at__lt=now - timedelta(minutes=15)).order_by("staged_at"):
        items.append(("Held at the pass over 15 min", task))
    return items


def recent_activity(location, limit=100, verb=None):
    qs = AuditEvent.objects.filter(location=location).select_related("task", "table")
    if verb:
        qs = qs.filter(verb__startswith=verb)
    return qs[:limit]


def worker_status():
    beat = WorkerHeartbeat.objects.filter(name=WORKER_NAME).first()
    if beat is None:
        return {"online": False, "beat": None, "age": None}
    age = (timezone.now() - beat.beat_at).total_seconds()
    return {"online": age <= settings.DISPATCH_WORKER_STALE_SECONDS, "beat": beat, "age": int(age)}


def attention_count(staff) -> int:
    """Badge count for the most urgent item on this person's plate."""
    loc = staff.location
    q = Q(state=TaskState.OFFERED, offered_to=staff)
    if can(staff, "escalation.handle"):
        q |= Q(state=TaskState.ESCALATED)
    return Task.objects.filter(location=loc).filter(q).count()
