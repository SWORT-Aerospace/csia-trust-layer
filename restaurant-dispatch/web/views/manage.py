"""Manager screens: stalled work, floor plan, staff and coverage, rules,
activity log and integrations. Every write goes through dispatch.config_ops."""

from __future__ import annotations

import zoneinfo

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from dispatch import config_ops, engine, selectors
from dispatch.integrations import pos
from dispatch.models import IntegrationEvent, Section, SetupSession, StaffMember, Table, Task
from dispatch.permissions import ROLE_CHOICES
from dispatch.profiles import PROFILES
from dispatch.states import TaskState

from ..access import staff_view
from .staff import shell_context

TABS = [
    ("manage_now", "Now"),
    ("manage_floor", "Floor"),
    ("manage_staff", "Staff & coverage"),
    ("manage_rules", "Rules"),
    ("manage_activity", "Activity log"),
    ("manage_integrations", "Integrations"),
]


def _render(request, staff, template, tab, **context):
    context.update(shell_context(request, staff, "manage"))
    context.update({"tabs": TABS, "tab": tab})
    return render(request, template, context)


def _run(request, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        return True, result
    except engine.DispatchError as error:
        messages.error(request, error.message)
        return False, None


@never_cache
@staff_view("manage.config")
def now(request, staff):
    loc = staff.location
    counts = dict(
        Task.objects.filter(location=loc, state__in=TaskState.OPEN, is_practice=False)
        .values_list("state")
        .annotate(n=Count("id"))
    )
    setup = SetupSession.objects.filter(location=loc, finished_at__isnull=False).order_by("-finished_at").first()
    return _render(
        request,
        staff,
        "app/manage/now.html",
        "manage_now",
        stalled=selectors.stalled(loc),
        worker=selectors.worker_status(),
        counts=counts,
        states=TaskState.CHOICES,
        on_shift=StaffMember.objects.filter(location=loc, is_active=True, on_shift=True).prefetch_related("role_grants"),
        setup=setup,
        recent=selectors.recent_activity(loc, limit=12),
    )


@never_cache
@staff_view("manage.config")
def floor(request, staff):
    if request.method == "POST":
        op = request.POST.get("op")
        if op == "add_tables":
            ok, created = _run(request, config_ops.add_tables, staff, request.POST.get("labels", ""))
            if ok:
                messages.success(request, f"Added {created} table(s).")
        elif op == "table":
            active = None
            if "active" in request.POST:
                active = request.POST.get("active") == "1"
            ok, _ = _run(
                request,
                config_ops.update_table,
                staff,
                request.POST.get("table"),
                section_id=request.POST.get("section"),
                active=active,
            )
            if ok:
                messages.success(request, "Table updated.")
        elif op == "section":
            ok, _ = _run(
                request, config_ops.save_section, staff, name=request.POST.get("name"), section_id=request.POST.get("section")
            )
            if ok:
                messages.success(request, "Section saved.")
        return redirect("web:manage_floor", sid=staff.pk)
    loc = staff.location
    return _render(
        request,
        staff,
        "app/manage/floor.html",
        "manage_floor",
        sections=Section.objects.filter(location=loc).annotate(n=Count("tables")),
        tables=Table.objects.filter(location=loc).select_related("section").order_by("-is_active", "section__sort", "sort", "label"),
    )


@never_cache
@staff_view("manage.config")
def staff_page(request, staff):
    pairing = None
    if request.method == "POST":
        op = request.POST.get("op")
        if op == "staff":
            ok, member = _run(
                request,
                config_ops.save_staff,
                staff,
                name=request.POST.get("name"),
                roles=request.POST.getlist("roles"),
                staff_id=request.POST.get("staff") or None,
                section_ids=request.POST.getlist("sections"),
                active=request.POST.get("active", "1") == "1",
            )
            if ok:
                messages.success(request, f"Saved {member}.")
        elif op == "coverage":
            coverage = {f: request.POST.get(f) for f in ("primary_runner", "backup_runner", "primary_busser", "backup_busser")}
            section = Section.objects.filter(pk=request.POST.get("section") or 0, location=staff.location).first()
            ok, _ = _run(
                request,
                config_ops.save_section,
                staff,
                name=section.name if section else "",
                section_id=request.POST.get("section"),
                coverage=coverage,
            )
            if ok:
                messages.success(request, "Coverage saved.")
        elif op == "shift":
            ok, result = _run(request, engine.set_on_shift, staff, request.POST.get("staff"), request.POST.get("on") == "1")
            if ok:
                messages.success(request, result.message)
        elif op == "pair":
            ok, result = _run(request, config_ops.create_pairing_code, staff, request.POST.get("staff"))
            if ok:
                code, record = result
                pairing = {"code": code, "staff": record.staff, "expires": record.expires_at}
        if pairing is None:
            return redirect("web:manage_staff", sid=staff.pk)
    loc = staff.location
    return _render(
        request,
        staff,
        "app/manage/staff.html",
        "manage_staff",
        members=StaffMember.objects.filter(location=loc).prefetch_related("role_grants", "sections").order_by("-is_active", "display_name"),
        sections=Section.objects.filter(location=loc).select_related(
            "primary_runner", "backup_runner", "primary_busser", "backup_busser"
        ),
        bussers=StaffMember.objects.filter(location=loc, role_grants__role="busser").order_by("display_name"),
        all_runners=StaffMember.objects.filter(location=loc, role_grants__role="runner").order_by("display_name"),
        roles=ROLE_CHOICES,
        pairing=pairing,
    )


@never_cache
@staff_view("manage.config")
def rules(request, staff):
    if request.method == "POST":
        ok, changes = _run(
            request,
            config_ops.update_rules,
            staff,
            profile_key=request.POST.get("profile"),
            offer_timeout=request.POST.get("offer_timeout"),
            backup_timeout=request.POST.get("backup_timeout"),
            stall_minutes=request.POST.get("stall_minutes"),
            time_zone=request.POST.get("time_zone"),
        )
        if ok:
            messages.success(request, ("Saved: " + "; ".join(changes)) if changes else "Nothing changed.")
        return redirect("web:manage_rules", sid=staff.pk)
    zones = sorted(z for z in zoneinfo.available_timezones() if z.startswith(("America/", "Europe/", "Asia/", "Australia/", "Pacific/", "Africa/")))
    return _render(
        request, staff, "app/manage/rules.html", "manage_rules", profiles=list(PROFILES.values()), zones=zones
    )


@never_cache
@staff_view("audit.view")
def activity(request, staff):
    verb = request.GET.get("type") or None
    return _render(
        request,
        staff,
        "app/manage/activity.html",
        "manage_activity",
        events=selectors.recent_activity(staff.location, limit=300, verb=verb),
        verb=verb or "",
        filters=[("", "Everything"), ("offer", "Offers"), ("task", "Claims & completions"), ("course", "Courses"), ("pairing", "Pairings"), ("table", "Tables"), ("config", "Configuration"), ("staff", "Staff"), ("setup", "Setup")],
    )


@never_cache
@staff_view("manage.config")
def integrations(request, staff):
    return _render(
        request,
        staff,
        "app/manage/integrations.html",
        "manage_integrations",
        planned=pos.PLANNED_ADAPTERS,
        events=IntegrationEvent.objects.filter(location=staff.location).order_by("-received_at")[:50],
        tables=Table.objects.filter(location=staff.location, is_active=True).order_by("sort", "label"),
    )


@require_POST
@staff_view("manage.config")
def integrations_test_event(request, staff):
    """Feed one event through the *fake* adapter to show shadow-mode handling."""
    kind = request.POST.get("kind")
    if kind not in {"item_ready", "check_closed", "course_fired"}:
        messages.error(request, "Pick an event type.")
        return redirect("web:manage_integrations", sid=staff.pk)
    table = Table.objects.filter(location=staff.location, pk=request.POST.get("table") or 0).first()
    if table is None:
        messages.error(request, "Pick a table.")
        return redirect("web:manage_integrations", sid=staff.pk)
    recorded = pos.ingest(staff.location, pos.FakePOSAdapter(), {"events": [{"kind": kind, "table": table.label, "ref": "test"}]})
    engine.audit(staff.location, staff, "integration.shadow", f"Test adapter event recorded in shadow mode: {recorded[0].would_do}")
    messages.success(request, "Recorded in shadow mode. Nothing on the floor changed.")
    return redirect("web:manage_integrations", sid=staff.pk)
