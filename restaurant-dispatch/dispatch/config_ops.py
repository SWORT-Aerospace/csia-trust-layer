"""Manager configuration: tables, sections, staff roles, coverage, rules and
device pairing. Same guarantees as the engine: capability check, tenant scope,
audit event."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import zoneinfo
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .engine import Conflict, Forbidden, Invalid, NotFound, _require, audit
from .models import PairingCode, Section, StaffMember, Table, Task
from .permissions import ROLES
from .profiles import PROFILES
from .seeding import parse_table_labels
from .states import PairingStatus, TableState, TaskKind, TaskState

PAIR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
PAIR_TTL = timedelta(minutes=15)


def _section(actor, section_id) -> Section | None:
    if section_id in (None, "", "none"):
        return None
    try:
        return Section.objects.get(pk=int(section_id), location_id=actor.location_id)
    except (Section.DoesNotExist, ValueError, TypeError):
        raise NotFound("That section isn't at this location.") from None


def _staff(actor, staff_id) -> StaffMember:
    try:
        return StaffMember.objects.get(pk=int(staff_id), location_id=actor.location_id)
    except (StaffMember.DoesNotExist, ValueError, TypeError):
        raise NotFound("That person isn't on this location's staff.") from None


@transaction.atomic
def update_rules(actor, *, profile_key=None, offer_timeout=None, backup_timeout=None, stall_minutes=None, time_zone=None):
    _require(actor, "manage.config", "Only a manager can change service rules.")
    loc = type(actor.location).objects.select_for_update().get(pk=actor.location_id)
    changes = []
    if profile_key and profile_key != loc.profile_key:
        if profile_key not in PROFILES:
            raise Invalid("Unknown edition or preset.")
        new, old = PROFILES[profile_key], loc.profile
        if new.edition != old.edition and Task.objects.filter(
            location=loc, kind__in=[TaskKind.RUN, TaskKind.COURSE], state__in=TaskState.OPEN
        ).exists():
            raise Conflict("Finish or cancel open runs and courses before switching edition. Presets can change any time.")
        loc.profile_key = profile_key
        changes.append(f"preset → {new.name}")
        if new.requires_pairing and not old.requires_pairing:
            # Courses already at the pass join the sommelier's queue.
            Task.objects.filter(
                location=loc,
                kind=TaskKind.COURSE,
                state__in=[TaskState.STAGED, TaskState.ESCALATED],
                pairing_status=PairingStatus.NOT_REQUIRED,
            ).update(pairing_status=PairingStatus.PENDING)
    for field, value, low, high, label in (
        ("offer_timeout_seconds", offer_timeout, 10, 600, "first offer timeout"),
        ("backup_timeout_seconds", backup_timeout, 10, 600, "backup timeout"),
        ("stall_minutes", stall_minutes, 1, 120, "stall threshold"),
    ):
        if value in (None, ""):
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise Invalid(f"The {label} must be a whole number.") from None
        if not low <= value <= high:
            raise Invalid(f"The {label} must be between {low} and {high}.")
        if getattr(loc, field) != value:
            setattr(loc, field, value)
            changes.append(f"{label} → {value}")
    if time_zone and time_zone != loc.time_zone:
        if time_zone not in zoneinfo.available_timezones():
            raise Invalid("Unknown time zone.")
        loc.time_zone = time_zone
        changes.append(f"time zone → {time_zone}")
    if changes:
        loc.save()
        actor.location = loc
        audit(loc, actor, "config.rules", "Rules changed: " + "; ".join(changes))
    return changes


@transaction.atomic
def add_tables(actor, text: str) -> int:
    _require(actor, "manage.config", "Only a manager can change the floor plan.")
    parsed = parse_table_labels(text)
    if not parsed:
        raise Invalid("Paste at least one table label.")
    existing = {t.lower() for t in Table.objects.filter(location_id=actor.location_id).values_list("label", flat=True)}
    created = 0
    base_sort = Table.objects.filter(location_id=actor.location_id).count()
    for section_name, labels in parsed:
        section, _ = Section.objects.get_or_create(
            location_id=actor.location_id,
            name=section_name,
            defaults={"sort": Section.objects.filter(location_id=actor.location_id).count()},
        )
        for label in labels:
            if label.lower() in existing:
                continue
            Table.objects.create(location_id=actor.location_id, section=section, label=label, sort=base_sort + created)
            existing.add(label.lower())
            created += 1
    audit(actor.location, actor, "config.tables", f"Added {created} table(s)")
    return created


@transaction.atomic
def update_table(actor, table_id, *, section_id=None, active=None):
    _require(actor, "manage.config", "Only a manager can change the floor plan.")
    try:
        table = Table.objects.select_for_update().get(pk=int(table_id), location_id=actor.location_id)
    except (Table.DoesNotExist, ValueError, TypeError):
        raise NotFound("That table isn't at this location.") from None
    if active is False and table.state != TableState.READY:
        raise Conflict(f"Table {table.label} is in use. Remove it once it's ready to seat.")
    if section_id is not None:
        table.section = _section(actor, section_id)
    if active is not None:
        table.is_active = active
    table.save(update_fields=["section", "is_active"])
    audit(actor.location, actor, "config.table", f"Updated table {table.label}", table=table)
    return table


@transaction.atomic
def save_section(actor, *, name, section_id=None, coverage=None):
    _require(actor, "manage.config", "Only a manager can change sections.")
    name = (name or "").strip()[:40]
    if not name:
        raise Invalid("Give the section a name.")
    section = _section(actor, section_id) if section_id else Section(location_id=actor.location_id)
    if Section.objects.filter(location_id=actor.location_id, name__iexact=name).exclude(pk=section.pk).exists():
        raise Conflict(f"There's already a section called {name}.")
    section.name = name
    for field, staff_id in (coverage or {}).items():
        if field not in {"primary_runner", "backup_runner", "primary_busser", "backup_busser"}:
            continue
        member = _staff(actor, staff_id) if staff_id else None
        role = "busser" if "busser" in field else "runner"
        if member is not None and role not in member.role_set:
            raise Invalid(f"{member} isn't set up as a {role}.")
        setattr(section, field, member)
    section.save()
    audit(actor.location, actor, "config.section", f"Saved section {section.name} and its coverage")
    return section


@transaction.atomic
def save_staff(actor, *, name, roles, staff_id=None, section_ids=None, active=True):
    _require(actor, "manage.config", "Only a manager can change staff roles.")
    name = (name or "").strip()[:60]
    if not name:
        raise Invalid("Enter the person's name.")
    roles = [r for r in roles if r in ROLES]
    member = _staff(actor, staff_id) if staff_id else StaffMember(location_id=actor.location_id)
    if member.pk == actor.pk and "manager" not in roles:
        raise Conflict("You can't remove your own manager role.")
    member.display_name = name
    member.is_active = bool(active) or member.pk == actor.pk
    member.save()
    member.set_roles(roles)
    if section_ids is not None:
        member.sections.set([s for s in (_section(actor, sid) for sid in section_ids) if s])
    audit(actor.location, actor, "config.staff", f"Saved {member}: {member.roles_display}")
    return member


def _hash_code(code: str) -> str:
    normalized = "".join(ch for ch in code.upper() if ch.isalnum())
    return hmac.new(settings.SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def create_pairing_code(actor, staff_id) -> tuple[str, PairingCode]:
    _require(actor, "staff.pair", "Only a manager can pair devices.")
    member = _staff(actor, staff_id)
    if member.is_demo_account and member.location.restaurant.demo_owner_id:
        raise Forbidden("Demo sandbox personas can't be paired to devices.")
    if member.user is None:
        User = get_user_model()
        user = User.objects.create(username=f"staff_{secrets.token_hex(6)}")
        user.set_unusable_password()
        user.save()
        member.user = user
        member.save(update_fields=["user"])
    PairingCode.objects.filter(staff=member, used_at__isnull=True).update(expires_at=timezone.now())
    raw = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(8))
    code = PairingCode.objects.create(
        staff=member, code_hash=_hash_code(raw), expires_at=timezone.now() + PAIR_TTL, created_by=actor
    )
    audit(actor.location, actor, "staff.pair_code", f"Created a device pairing code for {member}")
    return f"{raw[:4]}-{raw[4:]}", code


@transaction.atomic
def redeem_pairing_code(raw: str) -> StaffMember | None:
    pk = (
        PairingCode.objects.select_for_update()
        .filter(code_hash=_hash_code(raw or ""), used_at__isnull=True, expires_at__gt=timezone.now())
        .values_list("pk", flat=True)
        .first()
    )
    code = PairingCode.objects.select_related("staff__location", "staff__user").filter(pk=pk).first() if pk else None
    if code is None or not code.staff.is_active or code.staff.user is None:
        return None
    code.used_at = timezone.now()
    code.save(update_fields=["used_at"])
    audit(code.staff.location, code.staff, "staff.paired", f"{code.staff} paired a device")
    return code.staff
