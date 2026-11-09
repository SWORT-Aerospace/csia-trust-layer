"""Role capabilities, enforced on the server for every action.

Screens use the same checks to decide what to show, but hiding a button is
never the protection: every engine call re-checks the capability and the
tenant scope of every object it touches.
"""

from __future__ import annotations

ROLE_CHOICES = [
    ("expo", "Expo"),
    ("runner", "Runner"),
    ("server", "Server"),
    ("host", "Host"),
    ("busser", "Busser"),
    ("captain", "Captain"),
    ("sommelier", "Sommelier"),
    ("lead", "Floor lead"),
    ("manager", "Manager"),
]
ROLE_LABELS = dict(ROLE_CHOICES)
ROLES = set(ROLE_LABELS)

# Capability -> roles that hold it. Profile-dependent capabilities are below.
CAPABILITIES: dict[str, set[str]] = {
    "pass.fire": {"expo", "manager"},
    "allergy.flag": {"expo", "captain", "manager"},
    "run.claim": {"runner"},
    "reset.claim": {"busser"},
    "table.view": {"host", "server", "lead", "captain", "manager"},
    "table.depart": {"server", "host", "captain", "lead", "manager"},
    "table.seat": {"host", "lead", "captain", "manager"},
    "table.override": {"lead", "captain", "manager"},
    "course.release": {"captain", "manager"},
    "course.hold": {"captain", "manager"},
    "course.no_pairing": {"captain", "manager"},
    "course.team_ready": {"captain", "manager"},
    "pairing.confirm": {"sommelier"},
    "manage.config": {"manager"},
    "staff.pair": {"manager"},
    "audit.view": {"manager", "lead", "captain"},
}


def roles_of(staff) -> set[str]:
    return staff.role_set


def can(staff, capability: str) -> bool:
    if staff is None or not staff.is_active:
        return False
    roles = roles_of(staff)
    if capability == "escalation.handle":
        # Regular Service: the floor lead. Fine Dining: the captain. Managers always.
        return bool(roles & {staff.location.profile.escalation_role, "manager"})
    if capability == "pairing.confirm" and not staff.location.profile.requires_pairing:
        return False
    return bool(roles & CAPABILITIES.get(capability, set()))


def claim_capability_for(kind: str) -> str:
    return "reset.claim" if kind == "reset" else "run.claim"


def worker_role_for(kind: str) -> str:
    return "busser" if kind == "reset" else "runner"


# Screens a staff member sees, in priority order, gated by role and profile.
SCREENS = [
    ("pass", "Pass", lambda s, p: can(s, "pass.fire")),
    ("runs", "My runs", lambda s, p: "runner" in s.role_set),
    ("resets", "Resets", lambda s, p: "busser" in s.role_set),
    ("captain", "Captain", lambda s, p: p.is_fine and bool(s.role_set & {"captain", "manager"})),
    ("sommelier", "Pairing", lambda s, p: p.requires_pairing and "sommelier" in s.role_set),
    ("lead", "Floor lead", lambda s, p: (not p.is_fine) and bool(s.role_set & {"lead", "manager"})),
    ("tables", "Tables", lambda s, p: can(s, "table.view")),
    ("manage", "Manage", lambda s, p: can(s, "manage.config")),
]


def screens_for(staff) -> list[tuple[str, str]]:
    profile = staff.location.profile
    return [(key, label) for key, label, rule in SCREENS if rule(staff, profile)]
