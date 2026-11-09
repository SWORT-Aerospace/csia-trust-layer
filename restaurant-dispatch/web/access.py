"""Resolve the acting staff membership for a request and enforce scope.

Every staff URL names a membership id. It must belong to the signed-in user;
otherwise the response is 404 (never revealing another tenant's data)."""

from __future__ import annotations

import functools

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from dispatch.models import StaffMember
from dispatch.permissions import can


def membership_for(request, sid):
    try:
        staff = (
            StaffMember.objects.select_related("location__restaurant")
            .prefetch_related("role_grants")
            .get(pk=int(sid), user=request.user, is_active=True)
        )
    except (StaffMember.DoesNotExist, ValueError, TypeError):
        raise Http404("Not found") from None
    return staff


def staff_view(capability: str | None = None):
    def decorator(view):
        @login_required
        @functools.wraps(view)
        def wrapper(request, sid, *args, **kwargs):
            staff = membership_for(request, sid)
            restaurant = staff.location.restaurant
            if restaurant.demo_owner_id and restaurant.demo_expires_at and restaurant.demo_expires_at < timezone.now():
                return redirect("web:demo")
            if capability and not can(staff, capability):
                return render(request, "403.html", {"staff": staff}, status=403)
            request.staff = staff
            timezone.activate(staff.location.time_zone)
            return view(request, staff, *args, **kwargs)

        return wrapper

    return decorator


def wants_json(request) -> bool:
    return request.headers.get("X-Dispatch-Fetch") == "1"
