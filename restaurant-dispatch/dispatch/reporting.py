"""Shift report: what happened during real service, derived from Syncora's
own task timestamps and audit events. Read-only.

Attribution rule: a task belongs to the shift in which it *started* (its
``ready_at``: food ready, course staged, or party departed). Every event of
that task counts toward that shift, even if it happened after the window
closed, so per-task numbers in the report and the CSV always agree.
Table overrides have no task and are attributed by when they happened.

Only completed tasks contribute to handoff times. Open and cancelled tasks
are counted separately and never appear as successful deliveries or resets.
Practice tickets from the setup wizard are excluded.
"""

from __future__ import annotations

import math
import zoneinfo
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from .models import AuditEvent, SetupSession, Task, Visit
from .states import TaskKind, TaskState

SMALL_SAMPLE = 20  # below this, percentiles are shown but flagged as directional
MAX_DAYS = 62

SHIFT_PRESETS = {
    "day": ("Whole service day (4:00 AM to 4:00 AM)", time(4, 0), time(4, 0)),
    "lunch": ("Lunch (11:00 AM to 3:00 PM)", time(11, 0), time(15, 0)),
    "dinner": ("Dinner (5:00 PM to 11:00 PM)", time(17, 0), time(23, 0)),
    "late": ("Late (9:00 PM to 2:00 AM, crosses midnight)", time(21, 0), time(2, 0)),
}

COUNT_DEFINITIONS = [
    ("missed_offers", "Missed offers",
     "Offers that expired with nobody claiming them. Counted per offer: one task can miss more than once."),
    ("declined_offers", "Declined offers", "Offers a runner or busser explicitly declined. Counted per offer."),
    ("routed_to_backup", "Routed to backup",
     "Tasks that reached a backup runner or busser after the first person missed or declined. Counted per task."),
    ("escalated", "Escalated",
     "Tasks that ran out of people to offer to and went to the floor lead (Regular Service) or back to the captain "
     "(Fine Dining). Counted per task."),
    ("interventions", "Manual interventions",
     "Actions a lead, captain or manager took outside normal routing: assigning or reassigning, taking work over, "
     "re-offering, releasing work from its owner, closing it on the owner's behalf, or seating a table before its "
     "reset was confirmed. Counted per action. A captain's normal course release is not an intervention."),
]


@dataclass
class ShiftFilter:
    date_from: date
    date_to: date
    start: time
    end: time
    label: str
    key: str = "custom"

    def windows(self, tz_name: str) -> list[tuple[datetime, datetime]]:
        tz = zoneinfo.ZoneInfo(tz_name)
        out = []
        day = self.date_from
        while day <= self.date_to:
            start = datetime.combine(day, self.start, tzinfo=tz)
            end_day = day if self.end > self.start else day + timedelta(days=1)
            out.append((start, datetime.combine(end_day, self.end, tzinfo=tz)))
            day += timedelta(days=1)
        return out

    @property
    def crosses_midnight(self) -> bool:
        return self.end <= self.start


def service_date(location, now=None) -> date:
    """The service day in the location's timezone (days roll over at 4 AM)."""
    local = timezone.localtime(now or timezone.now(), zoneinfo.ZoneInfo(location.time_zone))
    return (local - timedelta(hours=4)).date()


def parse_filter(params, location) -> ShiftFilter:
    """Build a filter from query parameters; invalid input falls back to defaults."""
    default_day = service_date(location)

    def _date(name, fallback):
        try:
            return date.fromisoformat(params.get(name, ""))
        except ValueError:
            return fallback

    def _time(name, fallback):
        try:
            return time.fromisoformat(params.get(name, ""))
        except ValueError:
            return fallback

    date_from = _date("from", default_day)
    date_to = _date("to", date_from)
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    if (date_to - date_from).days >= MAX_DAYS:
        date_to = date_from + timedelta(days=MAX_DAYS - 1)
    key = params.get("shift", "day")
    if key in SHIFT_PRESETS:
        label, start, end = SHIFT_PRESETS[key]
    else:
        key = "custom"
        start, end = _time("start", time(17, 0)), _time("end", time(23, 0))
        label = f"Custom ({start:%H:%M} to {end:%H:%M}{', crosses midnight' if end <= start else ''})"
    return ShiftFilter(date_from, date_to, start, end, label, key)


def percentile(values, q: float):
    """Linear interpolation between closest ranks (same as NumPy's default)."""
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


@dataclass
class Stat:
    n: int
    median: float | None
    p90: float | None

    @property
    def small(self) -> bool:
        return 0 < self.n < SMALL_SAMPLE

    @classmethod
    def of(cls, values):
        values = [v for v in values if v is not None]
        return cls(len(values), percentile(values, 0.5), percentile(values, 0.9))


@dataclass
class Row:
    task: Task
    outcome: str  # completed | open | cancelled
    ready_to_done: float | None = None
    held_at_pass: float | None = None
    release_to_delivery: float | None = None
    missed_offers: int = 0
    declined_offers: int = 0
    routed_to_backup: bool = False
    escalated: bool = False
    interventions: int = 0
    stale_reset: bool = False
    notes: list = field(default_factory=list)


def _window_q(field_name, windows) -> Q:
    q = Q(pk__in=[])
    for start, end in windows:
        q |= Q(**{f"{field_name}__gte": start, f"{field_name}__lt": end})
    return q


def _seconds(a, b):
    if a is None or b is None:
        return None
    return max(0.0, (b - a).total_seconds())


def _held_seconds(task, events):
    """Time the course sat at the pass by choice: from staging (or a re-hold)
    until each release. Time an offer spent unclaimed is not 'held'."""
    held, start = 0.0, task.staged_at
    for e in events:
        if e.verb == "course.released" and start is not None:
            held += _seconds(start, e.at)
            start = None
        elif e.verb == "course.held":
            start = e.at
    return held


def build(location, shift: ShiftFilter, waitlist: str = "all") -> dict:
    windows = shift.windows(location.time_zone)
    tasks = list(
        Task.objects.filter(location=location, is_practice=False)
        .filter(_window_q("ready_at", windows))
        .select_related("table__section")
        .order_by("ready_at", "id")
    )
    by_task = defaultdict(list)
    for e in AuditEvent.objects.filter(task__in=[t.pk for t in tasks]).order_by("at", "id"):
        by_task[e.task_id].append(e)

    rows = []
    for task in tasks:
        events = by_task.get(task.pk, [])
        outcome = {TaskState.COMPLETED: "completed", TaskState.CANCELLED: "cancelled"}.get(task.state, "open")
        row = Row(task=task, outcome=outcome)
        row.missed_offers = sum(e.verb == "offer.expired" for e in events)
        row.declined_offers = sum(e.verb == "offer.declined" for e in events)
        row.routed_to_backup = any(e.verb == "offer.sent" and e.data.get("stage") == "backup" for e in events)
        row.escalated = any(e.verb == "task.escalated" for e in events)
        row.interventions = sum(1 for e in events if e.data.get("intervention"))
        row.stale_reset = any(e.verb == "reset.stale" for e in events)
        if outcome == "completed" and not row.stale_reset:
            row.ready_to_done = _seconds(task.ready_at, task.completed_at)
            if task.kind == TaskKind.COURSE:
                row.held_at_pass = _held_seconds(task, events)
                row.release_to_delivery = _seconds(task.released_at, task.completed_at)
        if row.stale_reset:
            row.notes.append("late reset for an earlier party; table was not freed")
        rows.append(row)

    def done(kind, extra=None):
        return [r for r in rows if r.task.kind == kind and r.ready_to_done is not None and (extra is None or extra(r))]

    waitlist_filter = {
        "waiting": lambda r: r.task.waitlist_active is True,
        "no_wait": lambda r: r.task.waitlist_active is False,
    }.get(waitlist)
    resets_done = done(TaskKind.RESET, waitlist_filter)

    def outcomes(kind):
        subset = [r for r in rows if r.task.kind == kind]
        return {o: sum(r.outcome == o for r in subset) for o in ("completed", "open", "cancelled")}

    # Interventions with no task (seating a table before its reset) count by when they happened.
    overrides = (
        AuditEvent.objects.filter(location=location, task__isnull=True, data__has_key="intervention")
        .filter(_window_q("at", windows))
        .count()
    )
    counts = {
        "missed_offers": sum(r.missed_offers for r in rows),
        "declined_offers": sum(r.declined_offers for r in rows),
        "routed_to_backup": sum(r.routed_to_backup for r in rows),
        "escalated": sum(r.escalated for r in rows),
        "interventions": sum(r.interventions for r in rows) + overrides,
    }
    visits = Visit.objects.filter(location=location).filter(_window_q("seated_at", windows)).exclude(
        tasks__is_practice=True
    )
    covers = visits.aggregate(total=Sum("party_size"))["total"] or 0
    setup = SetupSession.objects.filter(location=location, finished_at__isnull=False).order_by("-finished_at").first()
    profile = location.profile
    report = {
        "location": location,
        "profile": profile,
        "shift": shift,
        "windows": windows,
        "waitlist": waitlist,
        "is_demo": location.restaurant.is_demo,
        "rows": rows,
        "runs": Stat.of([r.ready_to_done for r in done(TaskKind.RUN)]),
        "courses_total": Stat.of([r.ready_to_done for r in done(TaskKind.COURSE)]),
        "courses_held": Stat.of([r.held_at_pass for r in done(TaskKind.COURSE)]),
        "courses_release": Stat.of([r.release_to_delivery for r in done(TaskKind.COURSE)]),
        "resets": Stat.of([r.ready_to_done for r in resets_done]),
        "reset_waitlist_known": sum(1 for r in rows if r.task.kind == TaskKind.RESET and r.task.waitlist_active is not None),
        "outcomes": {k: outcomes(k) for k in (TaskKind.RUN, TaskKind.COURSE, TaskKind.RESET)},
        "stale_resets": sum(r.stale_reset for r in rows),
        "counts": counts,
        "definitions": COUNT_DEFINITIONS,
        "covers": covers,
        "parties": visits.count(),
        "interventions_per_100": round(counts["interventions"] * 100 / covers, 1) if covers else None,
        "setup_seconds": setup.duration_seconds if setup else None,
        "setup": setup,
        "small_sample": SMALL_SAMPLE,
    }
    return report


# --------------------------------------------------------------------------- CSV

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")

CSV_HEADER = [
    "data_source", "location", "task_id", "kind", "table", "section", "outcome", "waitlist_active",
    "ready_local", "released_local", "completed_local",
    "ready_to_complete_s", "held_at_pass_s", "release_to_delivery_s",
    "missed_offers", "declined_offers", "routed_to_backup", "escalated", "interventions", "note",
]


def safe_cell(value):
    """Neutralise spreadsheet formula injection in text cells."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.0f}"
    if isinstance(value, int):
        return value
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def csv_rows(report):
    tz = zoneinfo.ZoneInfo(report["location"].time_zone)

    def local(dt):
        return timezone.localtime(dt, tz).strftime("%Y-%m-%d %H:%M:%S") if dt else ""

    source = "demo" if report["is_demo"] else "syncora_events"
    yield CSV_HEADER
    for r in report["rows"]:
        t = r.task
        yield [
            safe_cell(v)
            for v in (
                source, report["location"].display_name, t.pk, t.kind, t.table.label,
                t.table.section.name if t.table.section else "", r.outcome,
                "" if t.waitlist_active is None else t.waitlist_active,
                local(t.ready_at), local(t.released_at), local(t.completed_at),
                r.ready_to_done, r.held_at_pass, r.release_to_delivery,
                r.missed_offers, r.declined_offers, r.routed_to_backup, r.escalated, r.interventions,
                "; ".join(r.notes),
            )
        ]
