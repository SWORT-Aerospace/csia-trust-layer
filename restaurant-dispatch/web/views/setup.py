"""Browser-only setup wizard. Design target: a working floor in under 10 minutes.

Order: create a location -> edition and preset -> paste table labels ->
roles and sections -> pair staff -> complete a sample run and reset.
Start and finish are instrumented on SetupSession and in the activity log.
"""

from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from dispatch import config_ops, engine
from dispatch.models import Location, Restaurant, Section, SetupSession, StaffMember, Table, Task
from dispatch.permissions import ROLE_CHOICES
from dispatch.profiles import FINE_PRESETS, PROFILES
from dispatch.seeding import parse_staff_lines
from dispatch.states import TableState, TaskKind, TaskState

STEPS = [
    ("location", "Location"),
    ("edition", "Edition"),
    ("tables", "Tables"),
    ("staff", "Roles & sections"),
    ("pair", "Pair devices"),
    ("practice", "Practice run"),
]
SESSION_START_KEY = "setup_started_at"


def _shared(setup=None, step="location", **extra):
    elapsed = None
    if setup is not None:
        elapsed = int(((setup.finished_at or timezone.now()) - setup.started_at).total_seconds())
    return {"steps": STEPS, "step": step, "setup": setup, "elapsed": elapsed, **extra}


@never_cache
def start(request):
    signed_in = request.user.is_authenticated and not request.user.username.startswith("demo_")
    if not settings.DISPATCH_SETUP_OPEN and not signed_in:
        return render(request, "setup/closed.html", status=403)
    request.session.setdefault(SESSION_START_KEY, timezone.now().isoformat())
    errors, values = [], request.POST
    if request.method == "POST":
        restaurant_name = values.get("restaurant", "").strip()[:120]
        location_name = values.get("location", "").strip()[:120] or "Main"
        your_name = values.get("your_name", "").strip()[:60]
        if not restaurant_name:
            errors.append("Enter the restaurant's name.")
        if not your_name:
            errors.append("Enter your name as staff will see it.")
        User = get_user_model()
        username = values.get("username", "").strip()
        password = values.get("password", "")
        if not signed_in:
            if not username:
                errors.append("Choose a username for signing in.")
            elif User.objects.filter(username__iexact=username).exists():
                errors.append("That username is taken.")
            if password != values.get("password2", ""):
                errors.append("The two passwords don't match.")
            else:
                try:
                    password_validation.validate_password(password, User(username=username))
                except ValidationError as error:
                    errors.extend(error.messages)
        if not errors:
            with transaction.atomic():
                user = request.user if signed_in else User.objects.create_user(username=username, password=password)
                restaurant = Restaurant.objects.create(name=restaurant_name)
                location = Location.objects.create(restaurant=restaurant, name=location_name)
                manager = StaffMember.objects.create(location=location, user=user, display_name=your_name)
                manager.set_roles(["manager"])
                started = request.session.get(SESSION_START_KEY)
                setup = SetupSession.objects.create(
                    user=user,
                    location=location,
                    started_at=datetime.fromisoformat(started) if started else timezone.now(),
                )
                setup.mark("location")
                engine.audit(location, manager, "setup.started", f"{manager} started setup for {location.display_name}")
            if not signed_in:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.pop(SESSION_START_KEY, None)
            return redirect("web:setup_step", setup_id=setup.pk, step="edition")
    return render(request, "setup/location.html", _shared(errors=errors, values=values, signed_in=signed_in))


def _load(request, setup_id):
    if not request.user.is_authenticated:
        raise Http404
    setup = SetupSession.objects.select_related("location__restaurant").filter(pk=setup_id, user=request.user).first()
    if setup is None or setup.location is None:
        raise Http404
    manager = (
        StaffMember.objects.filter(location=setup.location, user=request.user, role_grants__role="manager")
        .select_related("location__restaurant")
        .first()
    )
    if manager is None:
        raise Http404
    timezone.activate(setup.location.time_zone)
    return setup, manager


def _run(request, fn, *args, **kwargs):
    try:
        return True, fn(*args, **kwargs)
    except engine.DispatchError as error:
        messages.error(request, error.message)
        return False, None


def _next(setup, step):
    keys = [k for k, _ in STEPS]
    setup.mark(step)
    return redirect("web:setup_step", setup_id=setup.pk, step=keys[keys.index(step) + 1])


@never_cache
def step(request, setup_id, step):
    setup, manager = _load(request, setup_id)
    handler = {
        "edition": _edition,
        "tables": _tables,
        "staff": _staff,
        "pair": _pair,
        "practice": _practice,
        "done": _done,
    }.get(step)
    if handler is None:
        raise Http404
    return handler(request, setup, manager)


def _edition(request, setup, manager):
    if request.method == "POST":
        ok, _ = _run(request, config_ops.update_rules, manager, profile_key=request.POST.get("profile"))
        if ok:
            return _next(setup, "edition")
    return render(
        request,
        "setup/edition.html",
        _shared(setup, "edition", regular=PROFILES["regular"], presets=FINE_PRESETS, current=manager.location.profile_key),
    )


def _tables(request, setup, manager):
    location = manager.location
    if request.method == "POST":
        if request.POST.get("op") == "continue":
            if not Table.objects.filter(location=location).exists():
                messages.error(request, "Add at least one table first.")
            else:
                return _next(setup, "tables")
        else:
            ok, created = _run(request, config_ops.add_tables, manager, request.POST.get("labels", ""))
            if ok:
                messages.success(request, f"Added {created} table(s).")
        return redirect("web:setup_step", setup_id=setup.pk, step="tables")
    sections = Section.objects.filter(location=location).prefetch_related("tables")
    return render(request, "setup/tables.html", _shared(setup, "tables", sections=sections))


def _staff(request, setup, manager):
    location = manager.location
    if request.method == "POST":
        op = request.POST.get("op")
        if op == "people":
            people = parse_staff_lines(request.POST.get("people", ""))
            added = 0
            for name, roles in people:
                ok, _ = _run(request, config_ops.save_staff, manager, name=name, roles=roles)
                added += ok
            messages.success(request, f"Added {added} staff member(s).")
        elif op == "coverage":
            for section in Section.objects.filter(location=location):
                coverage = {
                    f: request.POST.get(f"{section.pk}-{f}")
                    for f in ("primary_runner", "backup_runner", "primary_busser", "backup_busser")
                }
                _run(request, config_ops.save_section, manager, name=section.name, section_id=section.pk, coverage=coverage)
            if StaffMember.objects.filter(location=location, role_grants__role="runner").exists():
                return _next(setup, "staff")
            messages.error(request, "Add at least one runner so food has somewhere to go.")
        return redirect("web:setup_step", setup_id=setup.pk, step="staff")
    staff = StaffMember.objects.filter(location=location).prefetch_related("role_grants")
    return render(
        request,
        "setup/staff.html",
        _shared(
            setup,
            "staff",
            staff=staff,
            sections=Section.objects.filter(location=location),
            runners=[s for s in staff if "runner" in s.role_set],
            bussers=[s for s in staff if "busser" in s.role_set],
            roles=ROLE_CHOICES,
        ),
    )


def _pair(request, setup, manager):
    location = manager.location
    codes = {}
    if request.method == "POST":
        if request.POST.get("op") == "continue":
            return _next(setup, "pair")
        ok, result = _run(request, config_ops.create_pairing_code, manager, request.POST.get("staff"))
        if ok:
            code, record = result
            codes[record.staff_id] = {"code": code, "expires": record.expires_at}
    staff = StaffMember.objects.filter(location=location).exclude(pk=manager.pk).prefetch_related("role_grants")
    return render(request, "setup/pair.html", _shared(setup, "pair", staff=staff, codes=codes, pair_url=request.build_absolute_uri("/pair/")))


# --------------------------------------------------------------------------- practice run


def _practice_state(setup, manager):
    p = setup.practice or {}
    location = manager.location
    profile = location.profile
    table = Table.objects.filter(pk=p.get("table"), location=location).first() if p.get("table") else None
    if table is None:
        table = Table.objects.filter(location=location, is_active=True, state=TableState.READY).order_by("sort", "label").first()
    task = Task.objects.filter(pk=p.get("task"), location=location).first() if p.get("task") else None
    reset = Task.objects.filter(pk=p.get("reset"), location=location).first() if p.get("reset") else None
    steps = []

    def add(key, label, done, hint=""):
        steps.append({"key": key, "label": label, "done": done, "hint": hint})

    add("seat", f"Seat a practice party at table {table.label if table else '—'}", bool(p.get("visit")), "As the host.")
    if profile.holds_at_pass:
        add("send", "Stage a course at the pass", task is not None, "As expo. Runners can't see it yet.")
        if profile.requires_pairing:
            add("no_pairing", "Resolve the pairing check", bool(task and task.pairing_status in ("ready", "not_needed")), "As captain: “No pairing” for practice.")
        if profile.requires_team_ready:
            add("team_ready", "Confirm the service team is ready", bool(task and task.team_ready_at), "As captain.")
        add("release", "Release the course to a runner", bool(task and task.released_at), "As captain.")
    else:
        add("send", "Tap “Food ready” at the pass", task is not None, "As expo. It's offered to one runner.")
    add("claim", "Claim the run", bool(task and task.state in (TaskState.CLAIMED, TaskState.COMPLETED)), "On a real shift the runner taps Claim on their phone. Here you take it over as manager.")
    add("deliver", "Confirm delivery", bool(task and task.state == TaskState.COMPLETED), "Physically on the table.")
    add("depart", "Confirm the party has left", reset is not None, "Payment never frees a table — only this does.")
    add("reset_claim", "Claim the table reset", bool(reset and reset.state in (TaskState.CLAIMED, TaskState.COMPLETED)), "As the busser (taken over by you).")
    add("reset_done", "Confirm the reset — table back to Ready to seat", bool(reset and reset.state == TaskState.COMPLETED), "The host view updates.")
    current = next((s for s in steps if not s["done"]), None)
    return {"table": table, "task": task, "reset": reset, "steps": steps, "current": current}


def _practice(request, setup, manager):
    state = _practice_state(setup, manager)
    if request.method == "POST":
        op = request.POST.get("op")
        p = dict(setup.practice or {})
        table, task, reset = state["table"], state["task"], state["reset"]
        ok, result = True, None
        if op == "seat" and table:
            p["table"] = table.pk
            ok, result = _run(request, engine.seat_party, manager, table.pk, 2)
            if ok:
                p["visit"] = result.visit.pk
        elif op == "send" and table:
            if manager.location.profile.holds_at_pass:
                ok, result = _run(request, engine.stage_course, manager, table.pk)
            else:
                ok, result = _run(request, engine.food_ready, manager, table.pk, 1, "Practice run", False, None, True)
            if ok:
                p["task"] = result.task.pk
                Task.objects.filter(pk=result.task.pk).update(is_practice=True)
        elif op == "no_pairing" and task:
            ok, _ = _run(request, engine.mark_no_pairing, manager, task.pk)
        elif op == "team_ready" and task:
            ok, _ = _run(request, engine.confirm_team_ready, manager, task.pk)
        elif op == "release" and task:
            ok, _ = _run(request, engine.release_course, manager, task.pk)
        elif op == "claim" and task:
            ok, _ = _run(request, engine.claim, manager, task.pk)
        elif op == "deliver" and task:
            ok, _ = _run(request, engine.complete, manager, task.pk)
        elif op == "depart" and table:
            ok, result = _run(request, engine.mark_departed, manager, table.pk)
            if ok and result.task:
                p["reset"] = result.task.pk
                Task.objects.filter(pk=result.task.pk).update(is_practice=True)
        elif op == "reset_claim" and reset:
            ok, _ = _run(request, engine.claim, manager, reset.pk)
        elif op == "reset_done" and reset:
            ok, _ = _run(request, engine.complete, manager, reset.pk)
        elif op == "finish":
            if state["current"] is not None:
                messages.error(request, "Finish the practice steps first (or skip them).")
                return redirect("web:setup_step", setup_id=setup.pk, step="practice")
            return _finish(request, setup, manager)
        elif op == "skip":
            return _finish(request, setup, manager, skipped=True)
        setup.practice = p
        setup.save(update_fields=["practice"])
        return redirect("web:setup_step", setup_id=setup.pk, step="practice")
    return render(request, "setup/practice.html", _shared(setup, "practice", state=state, profile=manager.location.profile))


def _finish(request, setup, manager, skipped=False):
    if setup.finished_at is None:
        setup.finished_at = timezone.now()
        setup.steps["practice"] = setup.finished_at.isoformat()
        if skipped:
            setup.steps["practice_skipped"] = True
        setup.save(update_fields=["finished_at", "steps"])
        engine.audit(
            manager.location,
            manager,
            "setup.finished",
            f"Setup finished in {setup.duration_seconds // 60}m {setup.duration_seconds % 60:02d}s"
            + (" (practice skipped)" if skipped else ""),
            duration_seconds=setup.duration_seconds,
            skipped_practice=skipped,
        )
    return redirect("web:setup_step", setup_id=setup.pk, step="done")


def _done(request, setup, manager):
    if setup.finished_at is None:
        return redirect("web:setup_step", setup_id=setup.pk, step="practice")
    return render(request, "setup/done.html", _shared(setup, "done", manager=manager))
