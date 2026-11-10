"""UI helpers. Every status carries a glyph *and* words, so nothing depends on color."""

import uuid

from django import template
from django.urls import reverse
from django.utils import timezone

from dispatch.states import PairingStatus, TableState, TaskKind, TaskState

register = template.Library()


def _chip(glyph, text, mod):
    return {"glyph": glyph, "text": text, "mod": mod}


@register.inclusion_tag("components/chip.html")
def task_chip(task, viewer=None):
    profile = task.location.profile
    if task.state == TaskState.STAGED:
        return _chip("‖", "Held at pass", "held")
    if task.state == TaskState.OFFERED:
        who = "you" if viewer is not None and task.offered_to_id == viewer.pk else str(task.offered_to)
        stage = " (backup)" if task.offer_stage == "backup" else ""
        return _chip("→", f"Offered to {who}{stage}", "offered")
    if task.state == TaskState.ESCALATED:
        return _chip("▲", profile.escalation_label, "alert")
    if task.state == TaskState.CLAIMED:
        who = "You have it" if viewer is not None and task.owner_id == viewer.pk else f"{task.owner} has it"
        return _chip("●", who, "claimed")
    if task.state == TaskState.COMPLETED:
        return _chip("✓", "Reset done" if task.kind == TaskKind.RESET else "Delivered", "done")
    return _chip("✕", "Cancelled", "muted")


@register.inclusion_tag("components/chip.html")
def table_chip(table):
    return {
        TableState.READY: _chip("✓", "Ready to seat", "ready"),
        TableState.OCCUPIED: _chip("●", "Seated", "seated"),
        TableState.NEEDS_RESET: _chip("▲", "Needs reset", "alert"),
        TableState.RESETTING: _chip("↻", "Being reset", "working"),
    }[table.state]


@register.inclusion_tag("components/chip.html")
def pairing_chip(task):
    status = task.pairing_status
    when = timezone.localtime(task.pairing_resolved_at).strftime("%-I:%M %p") if task.pairing_resolved_at else ""
    if status == PairingStatus.PENDING:
        return _chip("○", "Pairing: waiting for sommelier", "waiting")
    if status == PairingStatus.READY:
        return _chip("✓", f"Pairing ready · {task.pairing_resolved_by} {when}", "ready")
    if status == PairingStatus.NOT_NEEDED:
        return _chip("—", f"No pairing · marked by {task.pairing_resolved_by} {when}", "ready")
    return _chip("·", "No pairing check", "muted")


@register.inclusion_tag("components/chip.html")
def team_chip(task):
    if task.team_ready_at:
        when = timezone.localtime(task.team_ready_at).strftime("%-I:%M %p")
        return _chip("✓", f"Team ready · {task.team_ready_by} {when}", "ready")
    return _chip("○", "Team readiness: not confirmed", "waiting")


@register.simple_tag
def token():
    """Fresh idempotency token for a creation form. A double tap resends the
    same token, so the server returns the original instead of a duplicate."""
    return str(uuid.uuid4())


@register.simple_tag(takes_context=True)
def act_url(context, action):
    return reverse("web:act", args=[context["staff"].pk, action])


@register.filter
def epoch_ms(value):
    if not value:
        return ""
    return int(value.timestamp() * 1000)


@register.filter
def mmss(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


@register.filter
def since(value):
    if not value:
        return ""
    seconds = int((timezone.now() - value).total_seconds())
    if seconds < 60:
        return f"{max(seconds, 0)}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60}h {minutes % 60:02d}m"


@register.filter
def clock(value):
    if not value:
        return ""
    return timezone.localtime(value).strftime("%-I:%M:%S %p")


@register.filter
def duration(seconds):
    if seconds is None:
        return "—"
    seconds = int(seconds)
    return f"{seconds // 60}m {seconds % 60:02d}s"


@register.filter
def get(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def release_blockers(task, profile):
    return profile.release_blockers(task)


@register.simple_tag
def coverage_rows(section, runners, bussers):
    """(field, label, choices, current) for a section's backup-coverage form."""
    return [
        ("primary_runner", "First runner", runners, section.primary_runner),
        ("backup_runner", "Backup runner", runners, section.backup_runner),
        ("primary_busser", "First busser", bussers, section.primary_busser),
        ("backup_busser", "Backup busser", bussers, section.backup_busser),
    ]


@register.filter
def secs(value):
    """Seconds as a short duration: 48s, 2m 05s, 1h 04m."""
    if value is None:
        return "—"
    value = int(round(value))
    if value < 60:
        return f"{value}s"
    if value < 3600:
        return f"{value // 60}m {value % 60:02d}s"
    return f"{value // 3600}h {value % 3600 // 60:02d}m"


@register.filter
def signed(value):
    if value is None:
        return "—"
    return f"{value:+.1f}%"
