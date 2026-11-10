"""Manager screens: stalled work, floor plan, staff and coverage, rules,
activity log and integrations. Every write goes through dispatch.config_ops."""

from __future__ import annotations

import zoneinfo

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

import csv
from urllib.parse import urlencode

from django.http import HttpResponse

from dispatch import config_ops, engine, reporting, selectors
from dispatch.integrations import pos
from dispatch.models import IntegrationEvent, Section, SetupSession, ShiftObservation, StaffMember, Table, Task
from dispatch.permissions import ROLE_CHOICES
from dispatch.profiles import PROFILES
from dispatch.states import TaskState

from ..access import staff_view
from ..forms import ObservationForm
from .staff import shell_context

TABS = [
    ("manage_now", "Now"),
    ("manage_report", "Shift report"),
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


# --------------------------------------------------------------------------- shift report

WAITLIST_FILTERS = [("all", "All resets"), ("waiting", "Guests were waiting"), ("no_wait", "No one waiting")]
HANDOFF_TARGET = -20.0  # proposed: 20% faster at the 90th percentile
INTERVENTION_TARGET = -25.0  # proposed: 25% fewer interventions per 100 covers
MIN_COVERS = 100


def _change(before, after):
    if not before or after is None:
        return None
    return round((after - before) * 100.0 / before, 1)


def pilot_comparison(report, observations):
    """Baseline (manual) vs Syncora (event data) against the *proposed* targets.
    Never reports a result unless both sides were measured on real shifts."""
    baseline = [o for o in observations if o.source == ShiftObservation.BASELINE]
    syncora = [o for o in observations if o.source == ShiftObservation.SYNCORA]
    fine = report["profile"].is_fine
    rows = []

    def verdict(enough, change, target):
        if report["is_demo"]:
            return "Demo data: not pilot evidence"
        if not enough:
            return "Not enough measured data yet"
        return "Meets proposed target" if change is not None and change <= target else "Doesn't meet proposed target"

    handoff = report["courses_total"] if fine else report["runs"]
    b = next((o for o in baseline if o.food_handoff_p90_seconds), None)
    change = _change(b.food_handoff_p90_seconds, handoff.p90) if b else None
    enough = bool(b and (b.food_handoff_samples or 0) >= reporting.SMALL_SAMPLE and handoff.n >= reporting.SMALL_SAMPLE)
    rows.append({
        "metric": "Course staged → delivered, 90th percentile" if fine else "Food ready → delivered, 90th percentile",
        "baseline": f"{b.food_handoff_p90_seconds}s (n={b.food_handoff_samples or 0}, {b.service_date} {b.shift_label})" if b else "Not recorded",
        "syncora": f"{handoff.p90:.0f}s (n={handoff.n})" if handoff.p90 is not None else "No completed tasks",
        "change": change, "target": HANDOFF_TARGET, "verdict": verdict(enough, change, HANDOFF_TARGET),
    })
    resets = report["resets"]
    b = next((o for o in baseline if o.reset_p90_seconds), None)
    change = _change(b.reset_p90_seconds, resets.p90) if b else None
    enough = bool(b and (b.reset_samples or 0) >= reporting.SMALL_SAMPLE and resets.n >= reporting.SMALL_SAMPLE)
    rows.append({
        "metric": "Party left → reset done, 90th percentile",
        "baseline": f"{b.reset_p90_seconds}s (n={b.reset_samples or 0}, {b.service_date} {b.shift_label})" if b else "Not recorded",
        "syncora": f"{resets.p90:.0f}s (n={resets.n})" if resets.p90 is not None else "No completed resets",
        "change": change, "target": HANDOFF_TARGET, "verdict": verdict(enough, change, HANDOFF_TARGET),
    })
    counted = [o for o in baseline if o.manager_interventions is not None]
    b_covers = sum(o.covers for o in counted)
    b_rate = round(sum(o.manager_interventions for o in counted) * 100.0 / b_covers, 1) if b_covers else None
    s_covers = sum(o.covers for o in syncora) or report["covers"]
    s_rate = round(report["counts"]["interventions"] * 100.0 / s_covers, 1) if s_covers else None
    change = _change(b_rate, s_rate)
    enough = b_covers >= MIN_COVERS and s_covers >= MIN_COVERS
    rows.append({
        "metric": "Manager interventions per 100 covers",
        "baseline": f"{b_rate} ({b_covers} covers)" if b_rate is not None else "Not recorded",
        "syncora": f"{s_rate} ({s_covers} covers{', POS count' if syncora else ', Syncora seatings'})" if s_rate is not None else "No covers",
        "change": change, "target": INTERVENTION_TARGET, "verdict": verdict(enough, change, INTERVENTION_TARGET),
    })
    return rows


def _report_query(shift, waitlist):
    params = {"from": shift.date_from.isoformat(), "to": shift.date_to.isoformat(), "shift": shift.key, "waitlist": waitlist}
    if shift.key == "custom":
        params.update({"start": shift.start.strftime("%H:%M"), "end": shift.end.strftime("%H:%M")})
    return urlencode(params)


def _waitlist_param(request):
    value = request.GET.get("waitlist", "all")
    return value if value in dict(WAITLIST_FILTERS) else "all"


@never_cache
@staff_view("manage.config")
def report(request, staff):
    loc = staff.location
    shift = reporting.parse_filter(request.GET, loc)
    waitlist = _waitlist_param(request)
    form = ObservationForm(
        request.POST or None,
        initial={"service_date": shift.date_from, "start_time": shift.start, "end_time": shift.end, "shift_label": shift.label.split(" (")[0]},
    )
    if request.method == "POST":
        if form.is_valid():
            observation = form.save(commit=False)
            observation.location = loc
            observation.recorded_by = staff
            observation.save()
            engine.audit(loc, staff, "pilot.observation", f"Recorded a {observation.get_source_display().lower()} observation for {observation.service_date} {observation.shift_label}")
            messages.success(request, "Observation recorded. It stays separate from Syncora's event data.")
            return redirect(reverse("web:manage_report", args=[staff.pk]) + "?" + _report_query(shift, waitlist))
        messages.error(request, "Check the highlighted fields.")
    data = reporting.build(loc, shift, waitlist)
    observations = list(
        ShiftObservation.objects.filter(location=loc, service_date__range=(shift.date_from, shift.date_to))
    )
    other_locations = (
        StaffMember.objects.filter(user=request.user, is_active=True, role_grants__role="manager")
        .exclude(pk=staff.pk)
        .select_related("location__restaurant")
    )
    return _render(
        request, staff, "app/manage/report.html", "manage_report",
        manage_title="Shift report",
        r=data,
        query=_report_query(shift, waitlist),
        presets=[(k, v[0]) for k, v in reporting.SHIFT_PRESETS.items()],
        waitlist_filters=WAITLIST_FILTERS,
        observations=observations,
        comparison=pilot_comparison(data, observations),
        form=form,
        other_locations=other_locations,
        unresolved=[row for row in data["rows"] if row.outcome != "completed"],
    )


@never_cache
@staff_view("manage.config")
def report_csv(request, staff):
    """Manager-only export, scoped to this membership's location. The location
    comes from the URL membership (checked against the user), never a parameter."""
    loc = staff.location
    shift = reporting.parse_filter(request.GET, loc)
    data = reporting.build(loc, shift, _waitlist_param(request))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="syncora-shift-report-{loc.pk}-{shift.date_from}-to-{shift.date_to}.csv"'
    )
    response.write("\ufeff")  # lets spreadsheet apps detect UTF-8
    writer = csv.writer(response)
    for row in reporting.csv_rows(data):
        writer.writerow(row)
    engine.audit(loc, staff, "report.export", f"Exported the shift report CSV ({shift.date_from} to {shift.date_to}, {shift.label})")
    return response
