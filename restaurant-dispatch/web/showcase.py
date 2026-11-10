"""Homepage storyboards rendered with the real staff-screen templates.

Every object here is an unsaved, in-memory sample (labelled "Demo data" on
the page). Nothing is written to the database and nothing on the homepage can
act on real service: the screens are rendered inside an `inert` container.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from dispatch.models import AuditEvent, Location, Restaurant, Section, StaffMember, Table, Task, Visit
from dispatch.profiles import FINE_PRESETS, get_profile
from dispatch.states import OfferStage, PairingStatus, TableState, TaskKind, TaskState


class ShowCaps:
    """Template `can` stand-in that shows a role's controls. The homepage
    renders them inside an `inert` container, so they can't be used."""

    def __init__(self, *allowed):
        self._allowed = set(allowed)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return name in self._allowed


def _person(pk, name, location):
    member = StaffMember(id=pk, display_name=name, location=location)
    return member


def _event(when, actor, verb, summary):
    return AuditEvent(at=when, actor_name=actor, verb=verb, summary=summary)


def _location(profile_key, name):
    return Location(id=0, name="Sample", profile_key=profile_key, restaurant=Restaurant(name=name), offer_timeout_seconds=30)


def regular_story():
    now = timezone.now()
    loc = _location("regular", "Sample bistro")
    main = Section(name="Main room")
    maria, dev, ana, lee = (_person(i, n, loc) for i, n in ((1, "Maria"), (2, "Dev"), (3, "Ana"), (4, "Lee")))
    t4 = Table(label="4", section=main, state=TableState.OCCUPIED)
    run = Task(
        id=1, location=loc, kind=TaskKind.RUN, table=t4, item_count=2, state=TaskState.OFFERED,
        offered_to=dev, offer_stage=OfferStage.BACKUP, ready_at=now - timedelta(seconds=34),
        offered_at=now - timedelta(seconds=4), offer_expires_at=now + timedelta(seconds=26),
    )
    t3 = Table(label="3", section=main, state=TableState.READY, state_changed_at=now - timedelta(seconds=5))
    t3.reset_task = None
    t5 = Table(label="5", section=main, state=TableState.OCCUPIED, current_visit=Visit(party_size=4, seated_at=now - timedelta(minutes=41)))
    t5.reset_task = None
    t6 = Table(label="6", section=main, state=TableState.NEEDS_RESET)
    t6.reset_task = Task(state=TaskState.OFFERED, offered_to=lee, offer_expires_at=now + timedelta(seconds=19))
    return {
        "profile": loc.profile,
        "runner": {
            "who": "Dev · Runner (backup)",
            "staff": dev,
            "task": run,
            "events": [
                _event(now - timedelta(seconds=4), "Timer", "offer.expired", "Maria didn't claim Table 4 · 2 plates in time (primary)"),
                _event(now - timedelta(seconds=4), "Timer", "offer.sent", "Table 4 · 2 plates offered to Dev (backup), 30s to claim"),
            ],
        },
        "host": {
            "who": "Ana · Host",
            "staff": ana,
            "tables": [t3, t5, t6],
            "events": [
                _event(now - timedelta(seconds=5), "Lee", "task.completed", "Reset done: Reset table 3"),
                _event(now - timedelta(seconds=5), "Lee", "table.ready", "Table 3 is ready to seat"),
            ],
        },
    }


def fine_stories():
    now = timezone.now()
    stories = []
    for preset in FINE_PRESETS:
        loc = _location(preset.key, "Sample tasting room")
        room = Section(name="Dining room")
        elise, jordan, mateo = (_person(i, n, loc) for i, n in ((11, "Elise"), (12, "Jordan"), (13, "Mateo")))
        t2 = Table(label="2", section=room, state=TableState.OCCUPIED)
        held = Task(
            id=2, location=loc, kind=TaskKind.COURSE, table=t2, course_number=3, state=TaskState.STAGED,
            ready_at=now - timedelta(seconds=48), staged_at=now - timedelta(seconds=48),
            pairing_status=PairingStatus.PENDING if preset.requires_pairing else PairingStatus.NOT_REQUIRED,
        )
        cleared = Task(
            id=3, location=loc, kind=TaskKind.COURSE, table=t2, course_number=3, state=TaskState.STAGED,
            ready_at=now - timedelta(seconds=71), staged_at=now - timedelta(seconds=71),
            pairing_status=PairingStatus.READY if preset.requires_pairing else PairingStatus.NOT_REQUIRED,
            pairing_resolved_by=jordan if preset.requires_pairing else None,
            pairing_resolved_at=now - timedelta(seconds=9) if preset.requires_pairing else None,
            team_ready_by=elise if preset.requires_team_ready else None,
            team_ready_at=now - timedelta(seconds=3) if preset.requires_team_ready else None,
        )
        released = Task(
            id=4, location=loc, kind=TaskKind.COURSE, table=t2, course_number=3, state=TaskState.OFFERED,
            offered_to=mateo, offer_stage=OfferStage.ASSIGNED, ready_at=now - timedelta(seconds=74),
            staged_at=now - timedelta(seconds=74), released_at=now - timedelta(seconds=2),
            offered_at=now - timedelta(seconds=2), offer_expires_at=now + timedelta(seconds=28),
        )
        stories.append(
            {
                "preset": preset,
                "captain": {"who": "Elise · Captain", "staff": elise, "held": held, "cleared": cleared},
                "runner": {"who": "Mateo · Runner", "staff": mateo, "task": released},
                "board": SimpleNamespace(runners=[mateo], bussers=[]),
            }
        )
    return stories


def context():
    return {
        "story_regular": regular_story(),
        "story_fine": fine_stories(),
        "host_caps": ShowCaps("table_seat", "table_depart"),
        "captain_caps": ShowCaps("course_release", "course_no_pairing", "course_team_ready", "course_hold"),
        "no_caps": ShowCaps(),
        "regular_profile": get_profile("regular"),
    }
