"""Public website, sign-in, device pairing and the isolated demo."""

from __future__ import annotations

import hmac
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from dispatch import config_ops, engine, selectors
from dispatch.models import Location, StaffMember
from dispatch.profiles import FINE_PRESETS, PROFILES
from dispatch.seeding import create_demo_sandbox

from .. import demo_tour, ratelimit

log = logging.getLogger("dispatch")

# Pairing: attempts per client address per window. A successful pairing gives
# its attempt back, so a restaurant pairing many phones behind one Wi-Fi
# address is only limited by mistakes.
# Demo sandboxes: per client address, plus a global ceiling to cap hosting cost.
# Limits come from settings (DISPATCH_PAIR_ATTEMPT_LIMIT, DISPATCH_DEMO_*_LIMIT).
PAIR_WINDOW = 600
DEMO_WINDOW = 3600


def home(request):
    from ..showcase import context as showcase_context

    return render(request, "site/home.html", {"presets": FINE_PRESETS, "regular": PROFILES["regular"], **showcase_context()})


def healthz(request):
    """Public liveness: no tenant data, versions or internal diagnostics."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"ok": True})
    except Exception:  # database unreachable: say so without details
        return JsonResponse({"ok": False}, status=503)


@never_cache
def healthz_worker(request):
    """Operator check for a stalled timer worker. Requires the bearer token in
    DISPATCH_HEALTH_TOKEN; 404 when no token is configured."""
    token = settings.DISPATCH_HEALTH_TOKEN
    if not token:
        raise Http404
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), token.encode()):
        return JsonResponse({"ok": False}, status=401)
    online = selectors.worker_status()["online"]
    return JsonResponse({"worker": "ok" if online else "stalled"}, status=200 if online else 503)


# --------------------------------------------------------------------------- sign in


@never_cache
def signin(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        memberships = StaffMember.objects.filter(user=user, is_active=True)
        if not memberships.exists() and not user.is_superuser:
            form.add_error(None, "This account isn't linked to a restaurant yet. Ask your manager.")
        elif not settings.DISPATCH_ALLOW_DEMO_LOGINS and not memberships.filter(is_demo_account=False).exists():
            form.add_error(None, "Demo accounts are switched off on this deployment.")
        else:
            login(request, user)
            return redirect("web:app_home")
    return render(request, "auth/signin.html", {"form": form, "demo_logins": settings.DISPATCH_ALLOW_DEMO_LOGINS and settings.DEBUG})


@require_POST
def signout(request):
    logout(request)
    return redirect("web:home")


@never_cache
def pair(request):
    error = None
    status = 200
    if request.method == "POST":
        ip = ratelimit.client_ip(request)
        try:
            decision = ratelimit.hit("pair", ip, settings.DISPATCH_PAIR_ATTEMPT_LIMIT, PAIR_WINDOW)
        except ratelimit.LimiterUnavailable:
            log.error("pairing refused: shared rate limiter unavailable")
            return render(
                request,
                "auth/pair.html",
                {"error": "Pairing is temporarily unavailable. Staff already signed in aren't affected. Try again in a minute."},
                status=503,
            )
        if not decision.allowed:
            error, status = "Too many attempts from this network. Wait ten minutes, then ask your manager for a new code.", 429
        else:
            staff = config_ops.redeem_pairing_code(request.POST.get("code", ""))
            if staff is None:
                error = "That code didn't work. Codes are single-use and expire after 15 minutes."
            else:
                ratelimit.refund("pair", ip, PAIR_WINDOW)
                login(request, staff.user, backend="django.contrib.auth.backends.ModelBackend")
                return redirect("web:staff_home", sid=staff.pk)
    return render(request, "auth/pair.html", {"error": error}, status=status)


@never_cache
@login_required
def app_home(request):
    memberships = list(
        StaffMember.objects.filter(user=request.user, is_active=True)
        .select_related("location__restaurant")
        .prefetch_related("role_grants")
    )
    sandbox = [m for m in memberships if m.location.restaurant.demo_owner_id == request.user.pk]
    if sandbox:
        return redirect("web:demo_floor")
    if len(memberships) == 1:
        return redirect("web:staff_home", sid=memberships[0].pk)
    return render(request, "auth/choose.html", {"memberships": memberships})


# --------------------------------------------------------------------------- demo


def _demo_enabled():
    if not settings.DISPATCH_DEMO_ENABLED:
        raise Http404("The demo is switched off on this deployment.")


def demo(request):
    _demo_enabled()
    return render(request, "site/demo.html", {"presets": FINE_PRESETS, "regular": PROFILES["regular"]})


@require_POST
def demo_start(request):
    _demo_enabled()
    profile_key = request.POST.get("profile", "regular")
    if profile_key not in PROFILES:
        profile_key = "regular"
    # Shared, atomic throttles keep the demo cheap to host across all web processes.
    try:
        per_client = ratelimit.hit("demo", ratelimit.client_ip(request), settings.DISPATCH_DEMO_PER_CLIENT_LIMIT, DEMO_WINDOW)
        overall = ratelimit.hit("demo-all", "all", settings.DISPATCH_DEMO_GLOBAL_LIMIT, DEMO_WINDOW)
    except ratelimit.LimiterUnavailable:
        log.error("demo start refused: shared rate limiter unavailable")
        return render(request, "site/demo_unavailable.html", status=503)
    if not (per_client.allowed and overall.allowed):
        messages.error(request, "Too many demo sessions right now. Try again in an hour.")
        return redirect("web:demo")
    user, location, _ = create_demo_sandbox(profile_key)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.pop(demo_tour.SESSION_KEY, None)
    return redirect("web:demo_floor")


def _sandbox_location(request):
    if not request.user.is_authenticated:
        return None
    return (
        Location.objects.filter(restaurant__demo_owner=request.user, restaurant__is_demo=True)
        .select_related("restaurant")
        .order_by("-id")
        .first()
    )


DEMO_PANES = {
    False: ["Sam", "Maria", "Dev", "Ana", "Lee", "Rae"],
    True: ["Noor", "Elise", "Jordan", "Mateo", "Ana", "Lee"],
}


@never_cache
def demo_floor(request):
    _demo_enabled()
    location = _sandbox_location(request)
    if location is None:
        return redirect("web:demo")
    personas = list(
        StaffMember.objects.filter(location=location, user=request.user).prefetch_related("role_grants").order_by("id")
    )
    by_name = {p.display_name: p for p in personas}
    profile = location.profile
    panes = [by_name[n] for n in DEMO_PANES[profile.is_fine] if n in by_name]
    manager = next((p for p in personas if "manager" in p.role_set), None)
    return render(
        request,
        "demo/floor.html",
        {
            "location": location,
            "profile": profile,
            "personas": personas,
            "panes": panes,
            "manager": manager,
            "presets": FINE_PRESETS,
            "expires": location.restaurant.demo_expires_at,
        },
    )


@require_POST
def demo_preset(request):
    _demo_enabled()
    location = _sandbox_location(request)
    if location is None:
        return redirect("web:demo")
    manager = StaffMember.objects.filter(location=location, user=request.user, role_grants__role="manager").first()
    try:
        config_ops.update_rules(manager, profile_key=request.POST.get("profile"))
        messages.success(request, f"Preset switched to {location.__class__.objects.get(pk=location.pk).profile.name}.")
    except engine.DispatchError as error:
        messages.error(request, error.message)
    return redirect(reverse("web:demo_floor"))


# --------------------------------------------------------------------------- guided tour


def _tour(request):
    _demo_enabled()
    location = _sandbox_location(request)
    if location is None:
        raise Http404("No demo sandbox in this session.")
    return demo_tour.Tour(request, location)


@never_cache
def tour_state(request):
    return JsonResponse(_tour(request).state())


@require_POST
def tour_do(request):
    tour = _tour(request)
    try:
        message = tour.act(request.POST.get("step", ""))
        tone = "refused" if message.startswith("Refused") else "ok"
        return JsonResponse({"ok": True, "tone": tone, "message": message, "state": tour.state()})
    except engine.DispatchError as error:
        return JsonResponse({"ok": False, "message": error.message, "state": tour.state()}, status=error.status)


@require_POST
def tour_restart(request):
    tour = _tour(request)
    tour.restart()
    return JsonResponse({"ok": True, "state": tour.state()})
