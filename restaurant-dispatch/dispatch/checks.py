"""Deployment safety checks (run by `manage.py check --deploy` and at startup)."""

from django.conf import settings
from django.core.checks import Error, Warning, register


@register(deploy=True)
def demo_logins_off_in_public(app_configs, **kwargs):
    problems = []
    if not settings.DEBUG and settings.DISPATCH_ALLOW_DEMO_LOGINS:
        problems.append(
            Error(
                "Seeded demo accounts can sign in on a non-debug deployment.",
                hint="Set DISPATCH_ALLOW_DEMO_LOGINS=false for any public or hosted deployment.",
                id="dispatch.E001",
            )
        )
    if not settings.DEBUG and settings.DISPATCH_DEMO_STAFF_PASSWORD:
        problems.append(
            Warning(
                "DISPATCH_DEMO_STAFF_PASSWORD is set on a non-debug deployment.",
                hint="Unset it; seed_demo refuses to create password accounts outside DEBUG.",
                id="dispatch.W001",
            )
        )
    return problems


@register()
def shared_rate_limits(app_configs, **kwargs):
    """Hosted deployments must count pairing and demo-start limits in a shared cache."""
    if getattr(settings, "DISPATCH_CONFIGURED_DEBUG", settings.DEBUG):
        return []
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    process_local = ("locmem", "dummy", "filebased", "db.DatabaseCache")
    if not getattr(settings, "DISPATCH_REDIS_URL", "") or any(word in backend for word in process_local):
        return [
            Error(
                "Rate limits would be process-local: no shared Redis is configured.",
                hint="Set DISPATCH_REDIS_URL to a Redis reachable from every web process.",
                id="dispatch.E002",
            )
        ]
    return []


@register(deploy=True)
def shared_rate_limits_reachable(app_configs, **kwargs):
    if getattr(settings, "DISPATCH_CONFIGURED_DEBUG", settings.DEBUG) or not getattr(settings, "DISPATCH_REDIS_URL", ""):
        return []
    from web.ratelimit import get_limiter

    if not get_limiter().ping():
        return [
            Error(
                "DISPATCH_REDIS_URL is set but Redis didn't answer.",
                hint="Pairing and demo starts fail closed until Redis is reachable; staff boards keep working.",
                id="dispatch.E003",
            )
        ]
    return []
