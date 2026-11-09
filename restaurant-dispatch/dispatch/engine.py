"""The dispatch engine. Every state change in the product goes through here.

Rules that hold for every function:

* The actor's capability is checked here, not only in the view.
* Every object is looked up inside the actor's location (tenant scope).
* Every write is a conditional UPDATE guarded by the row's ``version`` and
  expected state, inside a transaction. Two people racing for the same task
  produce exactly one winner; the loser gets a plain-language conflict.
* Creation requests carry a client token; replaying one returns the original
  task instead of creating a duplicate.
"""

from __future__ import annotations

import functools
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import AuditEvent, StaffMember, Table, Task, Visit
from .permissions import can, claim_capability_for, worker_role_for
from .states import OfferStage, PairingStatus, TableState, TaskKind, TaskState, VisitState

log = logging.getLogger("dispatch")


# --------------------------------------------------------------------------- errors


class DispatchError(Exception):
    status = 409
    code = "conflict"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class Conflict(DispatchError):
    status = 409


class Forbidden(DispatchError):
    status = 403
    code = "forbidden"


class NotFound(DispatchError):
    status = 404
    code = "not_found"


class Invalid(DispatchError):
    status = 400
    code = "invalid"


class _Stale(Exception):
    """A guarded UPDATE matched no row: someone else changed it first."""

    def __init__(self, model, pk):
        self.model, self.pk = model, pk


@dataclass
class Result:
    message: str
    task: Task | None = None
    table: Table | None = None
    visit: Visit | None = None
    created: bool = False


def engine_action(fn):
    """Run in a transaction; turn a lost race into a Conflict describing the winner."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            with transaction.atomic():
                return fn(*args, **kwargs)
        except _Stale as stale:
            raise Conflict(_describe_current(stale.model, stale.pk), code="stale") from None

    return wrapper


def _describe_current(model, pk) -> str:
    if model is Table:
        table = Table.objects.filter(pk=pk).first()
        if table is None:
            return "That table no longer exists."
        return f"Table {table.label} just changed — it's now “{table.get_state_display()}”."
    task = Task.objects.select_related("owner", "offered_to", "table", "completed_by").filter(pk=pk).first()
    if task is None:
        return "That task no longer exists."
    if task.state == TaskState.CLAIMED:
        return f"{task.owner} already has {task.title}."
    if task.state == TaskState.OFFERED:
        return f"{task.title} is now offered to {task.offered_to}."
    if task.state == TaskState.COMPLETED:
        return f"{task.title} was already marked done by {task.completed_by or 'someone else'}."
    if task.state == TaskState.CANCELLED:
        return f"{task.title} was cancelled."
    return f"{task.title} just changed — it's now “{task.get_state_display()}”."


# --------------------------------------------------------------------------- helpers


def audit(location, actor, verb: str, summary: str, task=None, table=None, system="Dispatch", **data) -> AuditEvent:
    return AuditEvent.objects.create(
        location=location,
        actor=actor,
        actor_name=actor.display_name if actor else system,
        verb=verb,
        summary=summary[:240],
        task=task,
        table=table or (task.table if task is not None else None),
        data=data,
    )


def _require(actor: StaffMember, capability: str, message: str = "Your role can't do that.") -> None:
    if not can(actor, capability):
        raise Forbidden(message)


def _token(value) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise Invalid("The request token is malformed. Refresh the screen and try again.") from None


def _can_see_staged(actor) -> bool:
    return can(actor, "course.release") or can(actor, "pairing.confirm") or can(actor, "pass.fire")


def _lock(model, **filters):
    """Row-lock a single row (no joins), then return its pk.

    Locking the bare row and reading related objects in a *new* statement
    matters on PostgreSQL: after waiting on a lock, joined rows from the
    original statement can be stale, so the loser of a race would describe
    the wrong winner."""
    return model.objects.select_for_update().filter(**filters).values_list("pk", flat=True).first()


def _get_task(actor: StaffMember, task_id) -> Task:
    try:
        pk = _lock(Task, pk=int(task_id), location_id=actor.location_id)
    except (ValueError, TypeError):
        pk = None
    if pk is None:
        raise NotFound("That task isn't on this floor.")
    task = Task.objects.select_related(
        "table__section", "visit", "location", "offered_to", "owner", "completed_by"
    ).get(pk=pk)
    if task.state == TaskState.STAGED and not _can_see_staged(actor):
        # Staged courses stay invisible to runners until the captain releases them.
        raise NotFound("That task isn't on this floor.")
    return task


def _get_table(actor: StaffMember, table_id) -> Table:
    try:
        pk = _lock(Table, pk=int(table_id), location_id=actor.location_id, is_active=True)
    except (ValueError, TypeError):
        pk = None
    if pk is None:
        raise NotFound("That table isn't on this floor.")
    return Table.objects.select_related("current_visit", "section", "location").get(pk=pk)


def _get_worker(actor: StaffMember, staff_id, kind: str) -> StaffMember:
    role = worker_role_for(kind)
    try:
        staff = StaffMember.objects.get(pk=int(staff_id), location_id=actor.location_id, is_active=True)
    except (StaffMember.DoesNotExist, ValueError, TypeError):
        raise NotFound("That person isn't on this location's staff.") from None
    if role not in staff.role_set:
        raise Invalid(f"{staff} isn't set up as a {role}.")
    if not staff.on_shift:
        raise Invalid(f"{staff} isn't on shift.")
    return staff


def _apply(obj, expected_states, **changes) -> None:
    """Version-guarded conditional UPDATE; raises _Stale if anyone got there first."""
    model = type(obj)
    changes["version"] = obj.version + 1
    updated = model.objects.filter(pk=obj.pk, version=obj.version, state__in=expected_states).update(**changes)
    if updated != 1:
        raise _Stale(model, obj.pk)
    for key, value in changes.items():
        setattr(obj, key, value)


def _set_table(table_id, visit_id, expected_states, now, **changes) -> bool:
    """Change a table only if it still belongs to the given visit. Returns False
    (and changes nothing) when the table has moved on to a newer visit."""
    changes.setdefault("state_changed_at", now)
    return bool(
        Table.objects.filter(pk=table_id, current_visit_id=visit_id, state__in=expected_states).update(
            version=F("version") + 1, **changes
        )
    )


# --------------------------------------------------------------------------- offer chain


def eligible_workers(location, kind: str, exclude_ids=()):
    return (
        StaffMember.objects.filter(
            location=location, is_active=True, on_shift=True, role_grants__role=worker_role_for(kind)
        )
        .exclude(pk__in=list(exclude_ids))
        .annotate(load=Count("owned_tasks", filter=Q(owned_tasks__state=TaskState.CLAIMED), distinct=True))
        .order_by("load", "display_name", "id")
    )


def _coverage(task: Task, stage: str):
    section = task.table.section
    if section is None:
        return None
    if task.kind == TaskKind.RESET:
        return section.primary_busser if stage == OfferStage.PRIMARY else section.backup_busser
    return section.primary_runner if stage == OfferStage.PRIMARY else section.backup_runner


def _pick_candidate(task: Task, stage: str):
    """Section coverage first, then the least-busy eligible person not yet offered."""
    eligible = eligible_workers(task.location, task.kind, task.offered_history or [])
    preferred = _coverage(task, stage)
    if preferred is not None:
        match = eligible.filter(pk=preferred.pk).first()
        if match:
            return match
    return eligible.first()


def _offer_fields(task: Task, staff: StaffMember, stage: str, now) -> dict:
    loc = task.location
    timeout = loc.backup_timeout_seconds if stage == OfferStage.BACKUP else loc.offer_timeout_seconds
    history = list(task.offered_history or [])
    if staff.pk not in history:
        history.append(staff.pk)
    return {
        "state": TaskState.OFFERED,
        "offered_to": staff,
        "offer_stage": stage,
        "offered_at": now,
        "offer_expires_at": now + timedelta(seconds=timeout),
        "offered_history": history,
        "owner": None,
    }


def _escalation_fields(task: Task, now) -> dict:
    return {
        "state": TaskState.ESCALATED,
        "offered_to": None,
        "offer_stage": OfferStage.NONE,
        "offer_expires_at": None,
        "escalated_at": now,
        "escalated_to_role": task.location.profile.escalation_role,
        "offered_history": list(task.offered_history or []),
        "owner": None,
    }


def _next_fields(task: Task, now, restart: bool = False) -> dict:
    """Where an unclaimed task goes next, per the location's profile."""
    profile = task.location.profile
    if profile.task_offer_chain_uses_backup(task):
        current = OfferStage.NONE if restart else task.offer_stage
        next_stage = {OfferStage.NONE: OfferStage.PRIMARY, OfferStage.PRIMARY: OfferStage.BACKUP}.get(current)
        if next_stage:
            candidate = _pick_candidate(task, next_stage)
            if candidate is not None:
                return _offer_fields(task, candidate, next_stage, now)
    return _escalation_fields(task, now)


def _audit_routing(task: Task, actor, system="Dispatch") -> None:
    if task.state == TaskState.OFFERED:
        window = int((task.offer_expires_at - task.offered_at).total_seconds())
        audit(
            task.location,
            actor,
            "offer.sent",
            f"{task.title} offered to {task.offered_to} ({task.get_offer_stage_display().lower()}), "
            f"{window}s to claim",
            task=task,
            system=system,
            stage=task.offer_stage,
            to=task.offered_to_id,
        )
    elif task.state == TaskState.ESCALATED:
        audit(
            task.location,
            actor,
            "task.escalated",
            f"{task.title}: nobody claimed it — {task.location.profile.escalation_label.lower()}",
            task=task,
            system=system,
            to_role=task.escalated_to_role,
        )


# --------------------------------------------------------------------------- creation


def _existing_by_token(actor, token) -> Task | None:
    if token is None:
        return None
    return Task.objects.select_related("table", "location").filter(location_id=actor.location_id, client_token=token).first()


def _seated_table(actor, table_id) -> Table:
    table = _get_table(actor, table_id)
    if table.state != TableState.OCCUPIED or table.current_visit is None:
        raise Conflict(f"Table {table.label} isn't seated, so there's nobody to send food to.")
    return table


@engine_action
def food_ready(actor, table_id, item_count=1, note="", allergy_alert=False, client_token=None, practice=False) -> Result:
    """Regular Service: plates are up. Creates a run and offers it to one runner."""
    _require(actor, "pass.fire", "Only expo can send food from the pass.")
    profile = actor.location.profile
    if profile.holds_at_pass:
        raise Invalid("This location holds courses at the pass. Use “Stage course”.")
    token = _token(client_token)
    if existing := _existing_by_token(actor, token):
        return Result(f"Already sent: {existing.title}.", task=existing)
    if allergy_alert:
        _require(actor, "allergy.flag")
    try:
        item_count = max(1, min(int(item_count or 1), 30))
    except (TypeError, ValueError):
        raise Invalid("Plate count must be a number.") from None
    table = _seated_table(actor, table_id)
    now = timezone.now()
    task = Task(
        location=actor.location,
        kind=TaskKind.RUN,
        table=table,
        visit=table.current_visit,
        item_count=item_count,
        note=(note or "").strip()[:140],
        allergy_alert=bool(allergy_alert),
        is_practice=practice,
        client_token=token,
        created_by=actor,
        created_at=now,
        ready_at=now,
        offered_history=[],
    )
    for key, value in _next_fields(task, now).items():
        setattr(task, key, value)
    try:
        with transaction.atomic():
            task.save()
    except IntegrityError:
        if existing := _existing_by_token(actor, token):
            return Result(f"Already sent: {existing.title}.", task=existing)
        raise
    audit(actor.location, actor, "run.ready", f"Food ready: {task.title}", task=task, allergy=task.allergy_alert)
    _audit_routing(task, None)
    return Result(f"Food ready: {task.title}.", task=task, created=True)


@engine_action
def stage_course(actor, table_id, course_number=None, note="", allergy_alert=False, client_token=None) -> Result:
    """Fine Dining: the course is plated and held at the pass. Runners can't see it."""
    _require(actor, "pass.fire", "Only expo can stage courses.")
    profile = actor.location.profile
    if not profile.holds_at_pass:
        raise Invalid("This location sends food straight to runners. Use “Food ready”.")
    token = _token(client_token)
    if existing := _existing_by_token(actor, token):
        return Result(f"Already staged: {existing.title}.", task=existing)
    if allergy_alert:
        _require(actor, "allergy.flag")
    table = _seated_table(actor, table_id)
    visit = Visit.objects.select_for_update().get(pk=table.current_visit_id)
    if course_number in (None, ""):
        number = visit.next_course
    else:
        try:
            number = max(1, min(int(course_number), 30))
        except (TypeError, ValueError):
            raise Invalid("Course number must be a number.") from None
    if Task.objects.filter(visit=visit, kind=TaskKind.COURSE, course_number=number).exclude(
        state=TaskState.CANCELLED
    ).exists():
        raise Conflict(f"Course {number} for table {table.label} is already on the pass.")
    now = timezone.now()
    task = Task.objects.create(
        location=actor.location,
        kind=TaskKind.COURSE,
        table=table,
        visit=visit,
        course_number=number,
        note=(note or "").strip()[:140],
        allergy_alert=bool(allergy_alert),
        state=TaskState.STAGED,
        pairing_status=PairingStatus.PENDING if profile.requires_pairing else PairingStatus.NOT_REQUIRED,
        client_token=token,
        created_by=actor,
        created_at=now,
        ready_at=now,
        staged_at=now,
    )
    Visit.objects.filter(pk=visit.pk).update(next_course=max(visit.next_course, number + 1))
    audit(actor.location, actor, "course.staged", f"Staged {task.title} — held for the captain", task=task)
    return Result(f"Staged {task.title}. Held until the captain releases it.", task=task, created=True)


# --------------------------------------------------------------------------- claiming


@engine_action
def claim(actor, task_id) -> Result:
    task = _get_task(actor, task_id)
    if task.state == TaskState.CLAIMED and task.owner_id == actor.pk:
        return Result(f"{task.title} is already yours.", task=task)
    handler = can(actor, "escalation.handle")
    worker = can(actor, claim_capability_for(task.kind))
    if not (worker or handler):
        raise Forbidden("Your role can't claim this kind of work.")
    took_over_from = None
    if task.state == TaskState.OFFERED:
        if task.offered_to_id == actor.pk:
            pass
        elif handler:
            took_over_from = task.offered_to
        else:
            raise Conflict(f"{task.title} is offered to {task.offered_to} right now.")
    elif task.state == TaskState.ESCALATED:
        if not handler and not task.location.profile.open_claim_when_escalated:
            raise Conflict("This went back to the captain. They'll assign it.")
    elif task.state == TaskState.STAGED:
        raise Conflict(f"{task.title} is held at the pass until the captain releases it.")
    elif task.state == TaskState.CLAIMED:
        raise Conflict(f"{task.owner} already has {task.title}.")
    elif task.state == TaskState.COMPLETED:
        raise Conflict(f"{task.title} is already done.")
    else:
        raise Conflict(f"{task.title} was cancelled.")

    now = timezone.now()
    history = list(task.offered_history or [])
    if actor.pk not in history:
        history.append(actor.pk)
    _apply(
        task,
        (task.state,),
        state=TaskState.CLAIMED,
        owner=actor,
        claimed_at=now,
        offered_to=None,
        offer_expires_at=None,
        offered_history=history,
    )
    if task.kind == TaskKind.RESET:
        _set_table(task.table_id, task.visit_id, (TableState.NEEDS_RESET,), now, state=TableState.RESETTING)
    extra = f" (took over from {took_over_from})" if took_over_from else ""
    audit(task.location, actor, "task.claimed", f"{actor} claimed {task.title}{extra}", task=task)
    return Result(f"Claimed: {task.title}.", task=task)


@engine_action
def decline(actor, task_id) -> Result:
    task = _get_task(actor, task_id)
    if task.state != TaskState.OFFERED or task.offered_to_id != actor.pk:
        raise Conflict("That offer isn't yours any more.")
    now = timezone.now()
    audit(task.location, actor, "offer.declined", f"{actor} declined {task.title}", task=task)
    _apply(task, (TaskState.OFFERED,), **_next_fields(task, now))
    _audit_routing(task, None)
    return Result(f"Declined {task.title}. It's moved on.", task=task)


@engine_action
def complete(actor, task_id) -> Result:
    """Physically done: food is on the table, or the table is reset."""
    task = _get_task(actor, task_id)
    if task.state == TaskState.COMPLETED:
        if task.completed_by_id == actor.pk:
            return Result(f"{task.title} is already marked done.", task=task)
        raise Conflict(f"{task.completed_by} already marked {task.title} done.")
    if task.state == TaskState.CANCELLED:
        reason = f": {task.cancel_reason}" if task.cancel_reason else "."
        raise Conflict(f"{task.title} was cancelled{reason}")
    if task.state != TaskState.CLAIMED:
        raise Conflict(f"Claim {task.title} before marking it done.")
    on_behalf = task.owner_id != actor.pk
    if on_behalf and not can(actor, "escalation.handle"):
        raise Forbidden(f"{task.owner} owns {task.title}. Only they or a lead can close it.")
    now = timezone.now()
    owner = task.owner
    _apply(task, (TaskState.CLAIMED,), state=TaskState.COMPLETED, completed_at=now, completed_by=actor)
    verb = "Reset done" if task.kind == TaskKind.RESET else "Delivered"
    note = f" on behalf of {owner}" if on_behalf else ""
    audit(task.location, actor, "task.completed", f"{verb}: {task.title}{note}", task=task)
    if task.kind == TaskKind.RESET:
        freed = _set_table(
            task.table_id,
            task.visit_id,
            (TableState.NEEDS_RESET, TableState.RESETTING),
            now,
            state=TableState.READY,
            current_visit=None,
        )
        if freed:
            Visit.objects.filter(pk=task.visit_id).update(state=VisitState.CLOSED, closed_at=now)
            audit(task.location, actor, "table.ready", f"Table {task.table.label} is ready to seat", task=task)
        else:
            # A reset from an earlier visit must never release an occupied table.
            audit(
                task.location,
                actor,
                "reset.stale",
                f"Late reset for an earlier party at table {task.table.label}; table left unchanged",
                task=task,
            )
            return Result(f"Recorded. Table {task.table.label} already has a new party, so it stays seated.", task=task)
    return Result(f"{verb}: {task.title}.", task=task)


@engine_action
def release_claim(actor, task_id) -> Result:
    """Owner gives work back, or a lead takes it off them. It re-enters routing."""
    task = _get_task(actor, task_id)
    if task.state != TaskState.CLAIMED:
        raise Conflict(f"{task.title} isn't claimed.")
    if task.owner_id != actor.pk and not can(actor, "escalation.handle"):
        raise Forbidden(f"Only {task.owner} or a lead can release {task.title}.")
    now = timezone.now()
    previous = task.owner
    history = list(task.offered_history or [])
    if previous and previous.pk not in history:
        history.append(previous.pk)
    task.offered_history = history
    _apply(task, (TaskState.CLAIMED,), claimed_at=None, **_next_fields(task, now, restart=True))
    if task.kind == TaskKind.RESET:
        _set_table(task.table_id, task.visit_id, (TableState.RESETTING,), now, state=TableState.NEEDS_RESET)
    who = "gave back" if previous and previous.pk == actor.pk else f"released from {previous}"
    audit(task.location, actor, "task.released", f"{task.title} {who}", task=task)
    _audit_routing(task, None)
    return Result(f"Released {task.title}.", task=task)


@engine_action
def assign(actor, task_id, staff_id) -> Result:
    """A lead (Regular) or captain (Fine Dining) hands the work to a specific person."""
    _require(actor, "escalation.handle", "Only a floor lead, captain or manager can assign work.")
    task = _get_task(actor, task_id)
    if task.state not in (TaskState.OFFERED, TaskState.ESCALATED, TaskState.CLAIMED):
        if task.state == TaskState.STAGED:
            raise Conflict("Release the course first; staged courses stay at the pass.")
        raise Conflict(f"{task.title} is already closed.")
    target = _get_worker(actor, staff_id, task.kind)
    if task.state == TaskState.CLAIMED and task.owner_id == target.pk:
        return Result(f"{target} already has {task.title}.", task=task)
    now = timezone.now()
    previous = task.owner
    history = list(task.offered_history or [])
    if target.pk not in history:
        history.append(target.pk)
    _apply(
        task,
        (task.state,),
        state=TaskState.CLAIMED,
        owner=target,
        assigned_by=actor,
        claimed_at=now,
        offered_to=None,
        offer_expires_at=None,
        offered_history=history,
    )
    if task.kind == TaskKind.RESET:
        _set_table(task.table_id, task.visit_id, (TableState.NEEDS_RESET,), now, state=TableState.RESETTING)
    from_note = f" (was {previous})" if previous and previous.pk != target.pk else ""
    audit(task.location, actor, "task.assigned", f"{actor} assigned {task.title} to {target}{from_note}", task=task)
    return Result(f"Assigned {task.title} to {target}.", task=task)


@engine_action
def offer_to(actor, task_id, staff_id) -> Result:
    """Captain re-offers a returned course (or a lead re-offers any unclaimed task)."""
    _require(actor, "escalation.handle", "Only a floor lead, captain or manager can re-offer work.")
    task = _get_task(actor, task_id)
    if task.state not in (TaskState.OFFERED, TaskState.ESCALATED):
        raise Conflict(f"{task.title} isn't waiting for an owner.")
    target = _get_worker(actor, staff_id, task.kind)
    now = timezone.now()
    _apply(task, (task.state,), **_offer_fields(task, target, OfferStage.ASSIGNED, now))
    _audit_routing(task, actor)
    return Result(f"Offered {task.title} to {target}.", task=task)


# --------------------------------------------------------------------------- fine dining


@engine_action
def confirm_pairing(actor, task_id) -> Result:
    _require(actor, "pairing.confirm", "Only the sommelier can confirm a pairing.")
    task = _get_task(actor, task_id)
    if task.kind != TaskKind.COURSE:
        raise Invalid("Pairings apply to courses.")
    if task.pairing_status == PairingStatus.READY:
        return Result(f"Pairing for {task.title} is already confirmed.", task=task)
    if task.pairing_status == PairingStatus.NOT_NEEDED:
        raise Conflict(f"The captain marked {task.title} as needing no pairing.")
    if task.state not in (TaskState.STAGED, TaskState.ESCALATED):
        raise Conflict(f"{task.title} has already left the pass.")
    now = timezone.now()
    _apply(
        task,
        (task.state,),
        pairing_status=PairingStatus.READY,
        pairing_resolved_by=actor,
        pairing_resolved_at=now,
    )
    audit(task.location, actor, "pairing.ready", f"{actor} confirmed the pairing for {task.title}", task=task)
    return Result(f"Pairing ready for {task.title}.", task=task)


@engine_action
def mark_no_pairing(actor, task_id) -> Result:
    _require(actor, "course.no_pairing", "Only the captain can mark a course as needing no pairing.")
    task = _get_task(actor, task_id)
    if not task.location.profile.requires_pairing:
        raise Invalid("This preset has no pairing check.")
    if task.kind != TaskKind.COURSE or task.state not in (TaskState.STAGED, TaskState.ESCALATED):
        raise Conflict("Only courses still at the pass can be changed.")
    if task.pairing_status == PairingStatus.NOT_NEEDED:
        return Result(f"{task.title} is already marked “No pairing”.", task=task)
    if task.pairing_status == PairingStatus.READY:
        raise Conflict(f"{task.pairing_resolved_by} already confirmed a pairing for {task.title}.")
    now = timezone.now()
    _apply(
        task,
        (task.state,),
        pairing_status=PairingStatus.NOT_NEEDED,
        pairing_resolved_by=actor,
        pairing_resolved_at=now,
    )
    audit(task.location, actor, "pairing.not_needed", f"{actor} marked {task.title} as needing no pairing", task=task)
    return Result(f"{task.title}: no pairing needed.", task=task)


@engine_action
def confirm_team_ready(actor, task_id) -> Result:
    _require(actor, "course.team_ready", "Only the captain can confirm the service team is ready.")
    task = _get_task(actor, task_id)
    if not task.location.profile.requires_team_ready:
        raise Invalid("This preset has no team readiness check.")
    if task.kind != TaskKind.COURSE or task.state not in (TaskState.STAGED, TaskState.ESCALATED):
        raise Conflict("Only courses still at the pass can be confirmed.")
    if task.team_ready_at:
        return Result(f"Team readiness for {task.title} is already confirmed.", task=task)
    now = timezone.now()
    _apply(task, (task.state,), team_ready_by=actor, team_ready_at=now)
    audit(task.location, actor, "team.ready", f"{actor} confirmed the service team is ready for {task.title}", task=task)
    return Result(f"Team ready for {task.title}.", task=task)


@engine_action
def release_course(actor, task_id, runner_id=None) -> Result:
    _require(actor, "course.release", "Only the captain can release a course.")
    task = _get_task(actor, task_id)
    if task.kind != TaskKind.COURSE:
        raise Invalid("Only courses are released.")
    if task.state != TaskState.STAGED:
        if task.state in (TaskState.OFFERED, TaskState.CLAIMED):
            return Result(f"{task.title} is already released.", task=task)
        raise Conflict(f"{task.title} isn't held at the pass.")
    blockers = task.location.profile.release_blockers(task)
    if blockers:
        raise Conflict("Can't release yet. " + " ".join(blockers), code="not_ready")
    if runner_id not in (None, ""):
        runner = _get_worker(actor, runner_id, task.kind)
    else:
        task.offered_history = []
        runner = _pick_candidate(task, OfferStage.PRIMARY)
        if runner is None:
            raise Conflict("No runner is on shift. Put someone on shift, then release.")
    now = timezone.now()
    task.offered_history = []
    _apply(
        task,
        (TaskState.STAGED,),
        released_at=now,
        released_by=actor,
        **_offer_fields(task, runner, OfferStage.ASSIGNED, now),
    )
    audit(task.location, actor, "course.released", f"{actor} released {task.title} to {runner}", task=task)
    _audit_routing(task, None)
    return Result(f"Released {task.title} to {runner}.", task=task)


@engine_action
def hold_course(actor, task_id) -> Result:
    """Put an unclaimed course back on hold at the pass. Readiness checks are kept."""
    _require(actor, "course.hold", "Only the captain can put a course back on hold.")
    task = _get_task(actor, task_id)
    if task.kind != TaskKind.COURSE:
        raise Invalid("Only courses can be held.")
    if task.state == TaskState.STAGED:
        return Result(f"{task.title} is already on hold.", task=task)
    if task.state == TaskState.CLAIMED:
        raise Conflict(f"{task.owner} has already claimed {task.title}. Reassign it instead.")
    if task.state not in (TaskState.OFFERED, TaskState.ESCALATED):
        raise Conflict(f"{task.title} is already closed.")
    _apply(
        task,
        (task.state,),
        state=TaskState.STAGED,
        offered_to=None,
        offer_stage=OfferStage.NONE,
        offer_expires_at=None,
        released_at=None,
        escalated_to_role="",
    )
    audit(task.location, actor, "course.held", f"{actor} put {task.title} back on hold", task=task)
    return Result(f"{task.title} is back on hold at the pass.", task=task)


# --------------------------------------------------------------------------- tables


@engine_action
def mark_departed(actor, table_id, client_token=None) -> Result:
    """The party has physically left. Payment or check closure never does this."""
    _require(actor, "table.depart", "Your role can't mark a table as left.")
    token = _token(client_token)
    if existing := _existing_by_token(actor, token):
        return Result(f"Already marked as left: table {existing.table.label}.", task=existing)
    table = _get_table(actor, table_id)
    visit = table.current_visit
    if table.state != TableState.OCCUPIED or visit is None:
        if visit is not None and visit.state == VisitState.DEPARTED:
            reset = Task.objects.filter(visit=visit, kind=TaskKind.RESET).exclude(state=TaskState.CANCELLED).first()
            return Result(f"Table {table.label} is already marked as left.", task=reset, table=table)
        raise Conflict(f"Table {table.label} isn't seated (it's “{table.get_state_display()}”).")
    now = timezone.now()
    _apply(table, (TableState.OCCUPIED,), state=TableState.NEEDS_RESET, state_changed_at=now)
    Visit.objects.filter(pk=visit.pk, state=VisitState.SEATED).update(
        state=VisitState.DEPARTED, departed_at=now, departed_by=actor
    )
    # Courses still held for a party that has left will never be served.
    held = list(Task.objects.filter(visit=visit, state=TaskState.STAGED))
    for course in held:
        _apply(course, (TaskState.STAGED,), state=TaskState.CANCELLED, cancelled_at=now, cancel_reason="Party left")
        audit(actor.location, actor, "task.cancelled", f"{course.title} cancelled: party left", task=course)
    reset = Task(
        location=actor.location,
        kind=TaskKind.RESET,
        table=table,
        visit=visit,
        client_token=token,
        created_by=actor,
        created_at=now,
        ready_at=now,
        offered_history=[],
    )
    for key, value in _next_fields(reset, now).items():
        setattr(reset, key, value)
    reset.save()  # one_reset_per_visit makes a duplicate impossible
    audit(actor.location, actor, "table.departed", f"Party left table {table.label} (confirmed by {actor})", task=reset)
    _audit_routing(reset, None)
    return Result(f"Table {table.label}: party left. Reset requested.", task=reset, table=table, created=True)


def _new_visit(actor, table, party_size, token, now) -> Visit:
    try:
        party_size = max(1, min(int(party_size or 2), 40))
    except (TypeError, ValueError):
        raise Invalid("Party size must be a number.") from None
    return Visit.objects.create(
        location=actor.location,
        table=table,
        party_size=party_size,
        client_token=token,
        seated_at=now,
        seated_by=actor,
    )


@engine_action
def seat_party(actor, table_id, party_size=2, client_token=None) -> Result:
    _require(actor, "table.seat", "Only the host or a lead can seat a table.")
    token = _token(client_token)
    if token and (visit := Visit.objects.filter(location_id=actor.location_id, client_token=token).first()):
        return Result(f"Already seated at table {visit.table.label}.", visit=visit, table=visit.table)
    table = _get_table(actor, table_id)
    if table.state != TableState.READY:
        raise Conflict(f"Table {table.label} is “{table.get_state_display()}”. It can be seated once it's reset.")
    now = timezone.now()
    visit = _new_visit(actor, table, party_size, token, now)
    _apply(table, (TableState.READY,), state=TableState.OCCUPIED, current_visit=visit, state_changed_at=now)
    audit(actor.location, actor, "table.seated", f"Seated {visit.party_size} at table {table.label}", table=table)
    return Result(f"Seated {visit.party_size} at table {table.label}.", visit=visit, table=table, created=True)


@engine_action
def seat_override(actor, table_id, party_size=2, client_token=None) -> Result:
    """Authorized override: seat a table whose reset hasn't been confirmed.
    The open reset is cancelled so a late completion can't touch the new party."""
    _require(actor, "table.override", "Only a lead, captain or manager can seat a table before its reset is done.")
    token = _token(client_token)
    if token and (visit := Visit.objects.filter(location_id=actor.location_id, client_token=token).first()):
        return Result(f"Already seated at table {visit.table.label}.", visit=visit, table=visit.table)
    table = _get_table(actor, table_id)
    if table.state not in (TableState.NEEDS_RESET, TableState.RESETTING):
        raise Conflict(f"Table {table.label} doesn't need an override (it's “{table.get_state_display()}”).")
    now = timezone.now()
    old_visit = table.current_visit
    for reset in Task.objects.filter(visit=old_visit, kind=TaskKind.RESET, state__in=TaskState.OPEN):
        _apply(
            reset,
            (reset.state,),
            state=TaskState.CANCELLED,
            cancelled_at=now,
            offered_to=None,
            offer_expires_at=None,
            cancel_reason=f"Table reseated by {actor} before the reset was confirmed",
        )
        audit(actor.location, actor, "task.cancelled", f"{reset.title} cancelled: table reseated", task=reset)
    if old_visit:
        Visit.objects.filter(pk=old_visit.pk).update(state=VisitState.CLOSED, closed_at=now)
    visit = _new_visit(actor, table, party_size, token, now)
    _apply(
        table,
        (TableState.NEEDS_RESET, TableState.RESETTING),
        state=TableState.OCCUPIED,
        current_visit=visit,
        state_changed_at=now,
    )
    audit(
        actor.location,
        actor,
        "table.override",
        f"{actor} seated {visit.party_size} at table {table.label} before its reset was confirmed",
        table=table,
    )
    return Result(f"Seated {visit.party_size} at table {table.label} (override).", visit=visit, table=table, created=True)


# --------------------------------------------------------------------------- staff


@engine_action
def set_on_shift(actor, staff_id, on_shift: bool) -> Result:
    try:
        staff = StaffMember.objects.select_for_update().get(pk=int(staff_id), location_id=actor.location_id)
    except (StaffMember.DoesNotExist, ValueError, TypeError):
        raise NotFound("That person isn't on this location's staff.") from None
    if staff.pk != actor.pk:
        _require(actor, "manage.config", "Only a manager can change someone else's shift.")
    StaffMember.objects.filter(pk=staff.pk).update(on_shift=bool(on_shift))
    staff.on_shift = bool(on_shift)
    word = "started" if on_shift else "ended"
    audit(actor.location, actor, "staff.shift", f"{staff} {word} their shift", staff=staff.pk)
    if not on_shift:
        # Offers waiting on someone who just left move on now, not at expiry.
        now = timezone.now()
        for task in Task.objects.select_related("table__section", "location").filter(
            location_id=actor.location_id, state=TaskState.OFFERED, offered_to=staff
        ):
            _apply(task, (TaskState.OFFERED,), **_next_fields(task, now))
            _audit_routing(task, None)
    return Result(f"{staff} {word} their shift.")


# --------------------------------------------------------------------------- timer


def expire_due_offers(now=None, limit: int = 500) -> int:
    """Advance every offer past its expiry. Called by the worker process, never
    by a browser. Safe to run concurrently with claims and with other workers."""
    now = now or timezone.now()
    due = list(
        Task.objects.filter(state=TaskState.OFFERED, offer_expires_at__lte=now)
        .order_by("offer_expires_at")
        .values_list("pk", flat=True)[:limit]
    )
    advanced = 0
    for pk in due:
        try:
            with transaction.atomic():
                if _lock(Task, pk=pk) is None:
                    continue
                task = Task.objects.select_related("table__section", "location", "offered_to").filter(pk=pk).first()
                if task is None or task.state != TaskState.OFFERED or task.offer_expires_at > now:
                    continue
                missed = task.offered_to
                audit(
                    task.location,
                    None,
                    "offer.expired",
                    f"{missed} didn't claim {task.title} in time ({task.get_offer_stage_display().lower()})",
                    task=task,
                    system="Timer",
                    stage=task.offer_stage,
                )
                _apply(task, (TaskState.OFFERED,), **_next_fields(task, now))
                _audit_routing(task, None, system="Timer")
                advanced += 1
        except _Stale:
            continue  # claimed or changed between the scan and the lock: the claim wins
    return advanced
