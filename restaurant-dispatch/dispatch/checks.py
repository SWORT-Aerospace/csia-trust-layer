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
