"""Staff screens: each role's board, its live partial, and the action endpoint."""

from __future__ import annotations

import time

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from dispatch import engine, selectors
from dispatch.models import StaffMember
from dispatch.permissions import can, screens_for
from dispatch.states import TableState

from ..access import staff_view, wants_json

BOARDS = {
    "pass": selectors.pass_board,
    "runs": selectors.runner_board,
    "resets": selectors.busser_board,
    "captain": selectors.captain_board,
    "sommelier": selectors.sommelier_board,
    "lead": selectors.lead_board,
    "tables": selectors.tables_board,
}

SCREEN_TITLES = {
    "pass": "Pass",
    "runs": "My runs",
    "resets": "Table resets",
    "captain": "Captain",
    "sommelier": "Pairings",
    "lead": "Floor lead",
    "tables": "Tables",
}


def _post_bool(post, key) -> bool:
    return post.get(key) in {"on", "true", "1", "yes"}


# Each action maps POST fields onto one engine call. The engine re-checks the
# actor's capability and tenant scope; nothing here grants permission.
ACTIONS = {
    "food_ready": lambda s, p: engine.food_ready(
        s, p.get("table"), p.get("items"), p.get("note", ""), _post_bool(p, "allergy"), p.get("client_token")
    ),
    "stage_course": lambda s, p: engine.stage_course(
        s, p.get("table"), p.get("course") or None, p.get("note", ""), _post_bool(p, "allergy"), p.get("client_token")
    ),
    "claim": lambda s, p: engine.claim(s, p.get("task")),
    "decline": lambda s, p: engine.decline(s, p.get("task")),
    "complete": lambda s, p: engine.complete(s, p.get("task")),
    "release": lambda s, p: engine.release_claim(s, p.get("task")),
    "assign": lambda s, p: engine.assign(s, p.get("task"), p.get("staff")),
    "offer_to": lambda s, p: engine.offer_to(s, p.get("task"), p.get("staff")),
    "release_course": lambda s, p: engine.release_course(s, p.get("task"), p.get("staff") or None),
    "hold": lambda s, p: engine.hold_course(s, p.get("task")),
    "pairing_ready": lambda s, p: engine.confirm_pairing(s, p.get("task")),
    "no_pairing": lambda s, p: engine.mark_no_pairing(s, p.get("task")),
    "team_ready": lambda s, p: engine.confirm_team_ready(s, p.get("task")),
    "depart": lambda s, p: engine.mark_departed(s, p.get("table"), p.get("client_token")),
    "seat": lambda s, p: engine.seat_party(s, p.get("table"), p.get("party"), p.get("client_token")),
    "seat_override": lambda s, p: engine.seat_override(s, p.get("table"), p.get("party"), p.get("client_token")),
    "shift": lambda s, p: engine.set_on_shift(s, p.get("staff") or s.pk, _post_bool(p, "on")),
    "waitlist": lambda s, p: engine.set_waitlist(s, _post_bool(p, "on")),
}


def _screen_context(request, staff, screen):
    allowed = dict(screens_for(staff))
    if screen not in allowed or screen not in BOARDS:
        return None
    board = BOARDS[screen](staff)
    profile = staff.location.profile
    return {
        "staff": staff,
        "location": staff.location,
        "profile": profile,
        "screen": screen,
        "screen_title": SCREEN_TITLES[screen],
        "board": board,
        "can": _CapView(staff),
        "TableState": TableState,
        "worker": selectors.worker_status() if can(staff, "escalation.handle") else None,
        "embed": request.GET.get("embed") == "1",
        "next_url": reverse("web:screen", args=[staff.pk, screen])
        + ("?embed=1" if request.GET.get("embed") == "1" else ""),
    }


# Screens with a separately refreshed part (kept stable while someone is typing).
PARTS = {"pass": {"composer"}}


class _CapView:
    """Template helper: {% if can.course_release %}."""

    def __init__(self, staff):
        self._staff = staff

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return can(self._staff, name.replace("_", ".", 1))


def shell_context(request, staff, active):
    embed = request.GET.get("embed") == "1"
    personas = []
    restaurant = staff.location.restaurant
    if restaurant.demo_owner_id == request.user.pk:
        personas = list(
            StaffMember.objects.filter(location=staff.location, user=request.user)
            .prefetch_related("role_grants")
            .order_by("id")
        )
    return {
        "staff": staff,
        "location": staff.location,
        "profile": staff.location.profile,
        "nav": screens_for(staff),
        "active": active,
        "embed": embed,
        "embed_qs": "?embed=1" if embed else "",
        "personas": personas,
        "is_sandbox": bool(personas),
        "other_memberships": StaffMember.objects.filter(user=request.user, is_active=True)
        .exclude(location=staff.location)
        .select_related("location__restaurant")
        .exists()
        and not personas,
    }


@staff_view()
def home(request, staff):
    screens = screens_for(staff)
    if not screens:
        return render(request, "403.html", {"staff": staff, "reason": "No role assigned yet. Ask your manager."}, status=403)
    suffix = "?embed=1" if request.GET.get("embed") == "1" else ""
    return redirect(reverse("web:screen", args=[staff.pk, screens[0][0]]) + suffix)


@never_cache
@staff_view()
def screen(request, staff, name):
    if name == "manage":
        return redirect("web:manage_now", sid=staff.pk)
    context = _screen_context(request, staff, name)
    if context is None:
        if name in BOARDS:
            return render(request, "403.html", {"staff": staff}, status=403)
        raise Http404
    context.update(shell_context(request, staff, name))
    context["body_template"] = f"app/screens/{name}.html"
    if "composer" in PARTS.get(name, ()):
        context["composer_template"] = f"app/screens/{name}_composer.html"
    context["live_url"] = reverse("web:live", args=[staff.pk, name])
    return render(request, "app/screen.html", context)


@never_cache
@staff_view()
def live(request, staff, name):
    context = _screen_context(request, staff, name)
    if context is None:
        return render(request, "403.html", {"staff": staff}, status=403)
    part = request.GET.get("part")
    template = f"app/screens/{name}_{part}.html" if part in PARTS.get(name, ()) else f"app/screens/{name}.html"
    response = render(request, template, context)
    response["X-Server-Time"] = str(int(time.time() * 1000))
    return response


def _safe_next(request, staff):
    nxt = request.POST.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return reverse("web:staff_home", args=[staff.pk])


@require_POST
@staff_view()
def act(request, staff, action):
    handler = ACTIONS.get(action)
    if handler is None:
        raise Http404
    try:
        result = handler(staff, request.POST)
        payload = {"ok": True, "message": result.message, "created": result.created}
        status = 200
    except engine.DispatchError as error:
        payload = {"ok": False, "message": error.message, "code": error.code}
        status = error.status
    if wants_json(request):
        response = JsonResponse(payload, status=status)
        response["X-Server-Time"] = str(int(time.time() * 1000))
        return response
    (messages.success if payload["ok"] else messages.error)(request, payload["message"])
    return redirect(_safe_next(request, staff))
