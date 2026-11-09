"""Public website, sign-in, device pairing and the isolated demo."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from dispatch import config_ops, engine, selectors
from dispatch.models import Location, StaffMember
from dispatch.profiles import FINE_PRESETS, PROFILES
from dispatch.seeding import create_demo_sandbox

PAIR_FAIL_LIMIT = 10
PAIR_FAIL_WINDOW = 600


def home(request):
    return render(request, "site/home.html", {"presets": FINE_PRESETS, "regular": PROFILES["regular"]})


def healthz(request):
    worker = selectors.worker_status()
    return JsonResponse({"ok": True, "worker_online": worker["online"], "worker_age_seconds": worker["age"]})


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


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


@never_cache
def pair(request):
    error = None
    if request.method == "POST":
        key = f"pair-fail:{_client_ip(request)}"
        if cache.get(key, 0) >= PAIR_FAIL_LIMIT:
            error = "Too many attempts. Wait ten minutes, then ask your manager for a new code."
        else:
            staff = config_ops.redeem_pairing_code(request.POST.get("code", ""))
            if staff is None:
                cache.set(key, cache.get(key, 0) + 1, PAIR_FAIL_WINDOW)
                error = "That code didn't work. Codes are single-use and expire after 15 minutes."
            else:
                login(request, staff.user, backend="django.contrib.auth.backends.ModelBackend")
                return redirect("web:staff_home", sid=staff.pk)
    return render(request, "auth/pair.html", {"error": error})


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
    # Throttle sandbox creation per client to keep the demo cheap to host.
    key = f"demo-start:{_client_ip(request)}"
    if cache.get(key, 0) >= 30:
        messages.error(request, "Too many demo sessions from this network. Try again in an hour.")
        return redirect("web:demo")
    cache.set(key, cache.get(key, 0) + 1, 3600)
    user, location, _ = create_demo_sandbox(profile_key)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
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
