"""Sample restaurants: used by `manage.py seed_demo` and by the isolated
per-visitor demo sandboxes. All names are fictional sample data."""

from __future__ import annotations

import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from . import engine
from .models import Location, Restaurant, Section, StaffMember, Table
from .profiles import get_profile

DEMO_OFFER_SECONDS = 15
DEMO_BACKUP_SECONDS = 25

REGULAR_SAMPLE = {
    "restaurant": "Juniper & Pine",
    "location": "Main Street",
    "sections": [("Main room", ["1", "2", "3", "4", "5", "6", "7", "8"]), ("Patio", ["P1", "P2", "P3", "P4"])],
    "staff": [
        ("sam", "Sam", ["expo"]),
        ("maria", "Maria", ["runner"]),
        ("dev", "Dev", ["runner"]),
        ("lee", "Lee", ["busser"]),
        ("jo", "Jo", ["busser"]),
        ("ana", "Ana", ["host"]),
        ("theo", "Theo", ["server"]),
        ("rae", "Rae", ["lead"]),
        ("kim", "Kim", ["manager"]),
    ],
    "coverage": {
        "Main room": {"primary_runner": "maria", "backup_runner": "dev", "primary_busser": "lee", "backup_busser": "jo"},
        "Patio": {"primary_runner": "dev", "backup_runner": "maria", "primary_busser": "jo", "backup_busser": "lee"},
    },
    "server_sections": {"theo": ["Main room", "Patio"]},
    "seated": {"1": 2, "2": 4, "4": 3, "5": 2, "6": 6, "P1": 2, "P3": 4},
    "departed": ["3"],
}

FINE_SAMPLE = {
    "restaurant": "Marrow Room",
    "location": "Dining room",
    "sections": [("Dining room", ["1", "2", "3", "4", "5", "6", "7", "8"]), ("Salon", ["S1", "S2"])],
    "staff": [
        ("noor", "Noor", ["expo"]),
        ("elise", "Elise", ["captain"]),
        ("jordan", "Jordan", ["sommelier"]),
        ("mateo", "Mateo", ["runner"]),
        ("priya", "Priya", ["runner"]),
        ("lee", "Lee", ["busser"]),
        ("ana", "Ana", ["host"]),
        ("kim", "Kim", ["manager"]),
    ],
    "coverage": {
        "Dining room": {"primary_runner": "mateo", "backup_runner": "priya", "primary_busser": "lee"},
        "Salon": {"primary_runner": "priya", "backup_runner": "mateo", "primary_busser": "lee"},
    },
    "server_sections": {},
    "seated": {"1": 2, "2": 4, "3": 2, "5": 6, "6": 2, "S1": 8},
    "departed": [],
    "staged": [("2", 3)],  # table 2 is on course 3
}


def sample_for(profile_key: str) -> dict:
    return FINE_SAMPLE if get_profile(profile_key).is_fine else REGULAR_SAMPLE


@transaction.atomic
def build_sample(
    profile_key: str,
    *,
    demo_user=None,
    username_prefix: str | None = None,
    password: str | None = None,
    demo_ttl_hours: int | None = None,
    restaurant_name: str | None = None,
    offer_timeout: int | None = None,
):
    """Create a complete sample restaurant.

    * ``demo_user``: an isolated sandbox; every persona belongs to this one user.
    * ``username_prefix`` + ``password``: seeded local accounts, one per person.
    """
    spec = sample_for(profile_key)
    profile = get_profile(profile_key)
    restaurant = Restaurant.objects.create(
        name=restaurant_name or spec["restaurant"],
        is_demo=demo_user is not None or username_prefix is not None,
        demo_owner=demo_user,
        demo_expires_at=timezone.now() + timedelta(hours=demo_ttl_hours) if demo_ttl_hours else None,
    )
    if demo_user is not None:
        # Sandbox only: short windows so a visitor sees backup routing within the
        # one-minute tour. Real locations keep their own configured windows.
        primary, backup = DEMO_OFFER_SECONDS, DEMO_BACKUP_SECONDS
    else:
        primary = backup = 60 if profile.is_fine else 45
    if offer_timeout:
        primary = backup = offer_timeout
    location = Location.objects.create(
        restaurant=restaurant,
        name=spec["location"],
        profile_key=profile_key,
        offer_timeout_seconds=primary,
        backup_timeout_seconds=backup,
    )
    sections, tables = {}, {}
    for s_index, (section_name, labels) in enumerate(spec["sections"]):
        section = Section.objects.create(location=location, name=section_name, sort=s_index)
        sections[section_name] = section
        for t_index, label in enumerate(labels):
            tables[label] = Table.objects.create(location=location, section=section, label=label, sort=s_index * 100 + t_index)

    User = get_user_model()
    staff = {}
    for key, name, roles in spec["staff"]:
        user = demo_user
        if username_prefix is not None:
            user, _ = User.objects.get_or_create(username=f"{username_prefix}{key}")
            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()
            user.save()
        member = StaffMember.objects.create(
            location=location, user=user, display_name=name, is_demo_account=True
        )
        member.set_roles(roles)
        staff[key] = member
    for section_name, cover in spec["coverage"].items():
        section = sections[section_name]
        for field, key in cover.items():
            setattr(section, field, staff[key])
        section.save()
    for key, section_names in spec["server_sections"].items():
        staff[key].sections.set([sections[n] for n in section_names])

    host = next(m for m in staff.values() if "host" in m.role_set or "manager" in m.role_set)
    for label, size in spec["seated"].items():
        engine.seat_party(host, tables[label].pk, size)
    for label in spec["departed"]:
        engine.seat_party(host, tables[label].pk, 2)
        engine.mark_departed(host, tables[label].pk)
    expo = next(m for m in staff.values() if "expo" in m.role_set)
    for label, course in spec.get("staged", []):
        engine.stage_course(expo, tables[label].pk, course_number=course)
    return location, staff


def create_demo_sandbox(profile_key: str):
    """A fresh, isolated sandbox for one visitor: its own restaurant, its own
    random user (no password), deleted by the worker after the TTL."""
    User = get_user_model()
    user = User.objects.create(username=f"demo_{secrets.token_hex(8)}")
    user.set_unusable_password()
    user.save()
    location, staff = build_sample(
        profile_key, demo_user=user, demo_ttl_hours=settings.DISPATCH_DEMO_TTL_HOURS
    )
    return user, location, staff


def cleanup_expired_demos(now=None) -> int:
    now = now or timezone.now()
    expired = Restaurant.objects.filter(is_demo=True, demo_owner__isnull=False, demo_expires_at__lt=now)
    count = 0
    for restaurant in expired:
        owner = restaurant.demo_owner
        restaurant.delete()
        if owner and owner.username.startswith("demo_"):
            owner.delete()
        count += 1
    return count


# --------------------------------------------------------------------------- setup parsing

_RANGE = re.compile(r"^([A-Za-z]*)(\d+)\s*[-–]\s*([A-Za-z]*)(\d+)$")


def parse_table_labels(text: str) -> list[tuple[str, list[str]]]:
    """Parse pasted table labels into sections.

    Accepts lines like ``Main: 1-12, 14`` or ``Patio: P1-P6`` or bare
    ``20, 21, Bar 1``. Lines without a section name go to "Main".
    """
    sections: dict[str, list[str]] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        name = "Main"
        if ":" in line:
            name, _, line = line.partition(":")
            name = name.strip()[:40] or "Main"
        labels = sections.setdefault(name, [])
        for token in re.split(r"[,\t;]+", line):
            token = token.strip()
            if not token:
                continue
            match = _RANGE.match(token.replace(" ", ""))
            if match and (not match.group(3) or match.group(3) == match.group(1)):
                prefix, start, end = match.group(1), int(match.group(2)), int(match.group(4))
                if start <= end and end - start <= 200:
                    labels.extend(f"{prefix}{n}" for n in range(start, end + 1))
                    continue
            labels.append(token[:20])
    seen: set[str] = set()
    result = []
    for name, labels in sections.items():
        unique = []
        for label in labels:
            if label.lower() not in seen:
                seen.add(label.lower())
                unique.append(label)
        if unique:
            result.append((name, unique))
    return result


def parse_staff_lines(text: str) -> list[tuple[str, list[str]]]:
    """``Maria: runner, busser`` -> ("Maria", ["runner", "busser"])."""
    from .permissions import ROLE_CHOICES

    aliases = {label.lower(): key for key, label in ROLE_CHOICES}
    aliases.update({key: key for key, _ in ROLE_CHOICES})
    aliases.update({"lead": "lead", "floor lead": "lead", "som": "sommelier", "somm": "sommelier", "back": "busser"})
    people = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        name, _, roles_text = line.partition(":")
        if not roles_text and " - " in line:
            name, _, roles_text = line.partition(" - ")
        roles = []
        for token in re.split(r"[,/;]+", roles_text):
            role = aliases.get(token.strip().lower().rstrip("s"))
            if role is None:
                role = aliases.get(token.strip().lower())
            if role and role not in roles:
                roles.append(role)
        if name.strip():
            people.append((name.strip()[:60], roles))
    return people
