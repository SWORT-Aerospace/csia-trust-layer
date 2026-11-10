"""The one-minute guided tour inside an isolated demo sandbox.

Every step runs a real engine action as the sandbox persona who would do it on
a shift, and the "offer expires" step waits for the real timer worker. Step
status is derived from the database, so taps made directly on a staff screen
advance the tour too. The session only remembers which tasks the tour created.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from django.urls import reverse

from dispatch import engine
from dispatch.models import AuditEvent, StaffMember, Table, Task
from dispatch.states import OfferStage, PairingStatus, TableState, TaskKind, TaskState

SESSION_KEY = "demo_tour"


@dataclass
class Step:
    key: str
    title: str
    who: str = ""
    who_sid: int | None = None
    action: str | None = None  # button label when the visitor can trigger it
    status: str = "todo"  # done | current | todo
    waiting: bool = False  # current step that the timer worker will complete
    expires_at_ms: int | None = None
    note: str = ""
    done: bool = field(default=False, repr=False)


class Tour:
    def __init__(self, request, location):
        self.request = request
        self.location = location
        self.profile = location.profile
        self.people = {
            p.display_name: p
            for p in StaffMember.objects.filter(location=location, user=request.user).prefetch_related("role_grants")
        }
        data = request.session.get(SESSION_KEY) or {}
        if data.get("loc") != location.pk:
            data = {"loc": location.pk}
        self.data = data
        self.run = self._task("run")
        self.reset = self._task("reset")
        self.course = self._task("course")

    # ------------------------------------------------------------------ helpers
    def _task(self, name):
        pk = self.data.get(name)
        if not pk:
            return None
        return (
            Task.objects.select_related("table", "offered_to", "owner", "location")
            .filter(pk=pk, location=self.location)
            .first()
        )

    def _save(self):
        self.request.session[SESSION_KEY] = self.data
        self.request.session.modified = True

    def person(self, name):
        return self.people.get(name)

    def _step(self, key, title, who=None, **kwargs):
        member = self.person(who) if isinstance(who, str) else who
        return Step(
            key=key,
            title=title,
            who=f"{member.display_name} ({member.roles_display})" if member else "",
            who_sid=member.pk if member else None,
            **kwargs,
        )

    def _seated_table(self, prefer, avoid=()):
        tables = Table.objects.filter(location=self.location, is_active=True, state=TableState.OCCUPIED).exclude(
            pk__in=[t for t in avoid if t]
        )
        busy = set(
            Task.objects.filter(location=self.location, state__in=TaskState.OPEN).values_list("table_id", flat=True)
        )
        candidates = [t for t in tables.order_by("sort", "label") if t.pk not in busy]
        for label in prefer:
            for t in candidates:
                if t.label == label:
                    return t
        return candidates[0] if candidates else None

    # ------------------------------------------------------------------ steps
    def steps(self) -> list[Step]:
        steps = self._fine_steps() if self.profile.is_fine else self._regular_steps()
        current = next((s for s in steps if not s.done), None)
        for s in steps:
            s.status = "done" if s.done else ("current" if s is current else "todo")
            if s is not current or s.waiting:
                s.action = None  # only the next step can be triggered
        return steps

    def _regular_steps(self):
        run, reset = self.run, self.reset
        steps = []
        steps.append(self._step("fire", "Expo marks food ready. Syncora offers it to the section runner.", "Sam",
                                action="Mark food ready", done=run is not None))
        expired = run is not None and AuditEvent.objects.filter(task=run, verb="offer.expired").exists()
        waiting = run is not None and run.state == TaskState.OFFERED and run.offer_stage == OfferStage.PRIMARY
        skipped = run is not None and not expired and not waiting
        s = self._step(
            "expire",
            f"Maria doesn't claim it. After {self.location.offer_timeout_seconds}s the timer worker offers it to Dev, her backup.",
            "Maria",
            done=expired or skipped,
            waiting=waiting,
        )
        if waiting:
            s.expires_at_ms = int(run.offer_expires_at.timestamp() * 1000)
            s.note = "Nothing to tap: the server's timer does this, not your browser."
        if skipped:
            s.note = "Someone acted before the offer expired, so there was nothing to route."
        steps.append(s)
        # Until the first offer expires, the person who will claim is the backup (Dev).
        moved_on = run is not None and run.state == TaskState.OFFERED and run.offer_stage != OfferStage.PRIMARY
        claimer = (run.offered_to if moved_on else None) or self.person("Dev")
        steps.append(self._step("backup_claim", f"{claimer.display_name} claims the run.", claimer, action=f"Claim as {claimer.display_name}",
                                done=run is not None and run.state in (TaskState.CLAIMED, TaskState.COMPLETED)))
        owner = (run.owner if run and run.owner else None) or claimer
        steps.append(self._step("deliver", f"{owner.display_name} puts the plates on the table and taps Delivered.", owner,
                                action="Mark delivered", done=run is not None and run.state == TaskState.COMPLETED))
        steps.append(self._step("depart", "The party at a table leaves. The host confirms they've physically gone.", "Ana",
                                action="Confirm party left", done=reset is not None))
        busser = (reset.offered_to if reset and reset.state == TaskState.OFFERED else None) or self.person("Lee")
        steps.append(self._step("reset_claim", f"{busser.display_name} claims the reset.", busser, action=f"Claim as {busser.display_name}",
                                done=reset is not None and reset.state in (TaskState.CLAIMED, TaskState.COMPLETED)))
        cleaner = (reset.owner if reset and reset.owner else None) or busser
        steps.append(self._step("reset_done", f"{cleaner.display_name} finishes the reset.", cleaner, action="Mark reset done",
                                done=reset is not None and reset.state == TaskState.COMPLETED))
        reset_done = reset is not None and reset.state == TaskState.COMPLETED
        where = f"table {reset.table.label}" if reset else "the table"
        steps.append(self._step("host_sees", f"Ana's board shows {where} ready to seat. Open her screen to see it.", "Ana",
                                action="Got it", done=reset_done and bool(self.data.get("seen"))))
        return steps

    def _fine_steps(self):
        course, p = self.course, self.profile
        steps = [
            self._step("stage", "Expo stages the next course. It's held at the pass, and runners can't see it.", "Noor",
                       action="Stage course", done=course is not None)
        ]
        released = course is not None and course.state in (TaskState.OFFERED, TaskState.CLAIMED, TaskState.COMPLETED)
        if p.requires_pairing:
            refusal = self.data.get("refusal", "")
            s = self._step("try_release", "The captain tries to release it early.", "Elise", action="Try to release",
                           done=bool(refusal) or released or (course is not None and course.pairing_status != PairingStatus.PENDING))
            if refusal:
                s.note = f"Refused by the server: {refusal}"
            steps.append(s)
            steps.append(self._step("pairing", "The sommelier confirms the pairing.", "Jordan", action="Confirm pairing",
                                    done=course is not None and course.pairing_status in (PairingStatus.READY, PairingStatus.NOT_NEEDED)))
        if p.requires_team_ready:
            steps.append(self._step("team", "The captain confirms the service team is ready.", "Elise", action="Confirm team ready",
                                    done=course is not None and course.team_ready_at is not None))
        returned = course is not None and course.state == TaskState.ESCALATED
        steps.append(self._step(
            "release",
            "Mateo missed it, so it came back to the captain. Offer it again." if returned
            else "The captain releases it to one runner.",
            "Elise", action="Offer to Mateo" if returned else "Release to Mateo", done=released,
        ))
        steps.append(self._step("claim", "Mateo claims the course.", "Mateo", action="Claim as Mateo",
                                done=course is not None and course.state in (TaskState.CLAIMED, TaskState.COMPLETED)))
        s = self._step("deliver", "Mateo serves it and taps Delivered.", "Mateo", action="Mark delivered",
                       done=course is not None and course.state == TaskState.COMPLETED)
        if course is not None and course.state == TaskState.COMPLETED and course.released_at and course.staged_at:
            held = int((course.released_at - course.staged_at).total_seconds())
            served = int((course.completed_at - course.released_at).total_seconds())
            s.note = f"Held at the pass {held}s by choice, then {served}s from release to the table."
        steps.append(s)
        return steps

    # ------------------------------------------------------------------ actions
    def act(self, key):
        steps = self.steps()
        current = next((s for s in steps if s.status == "current"), None)
        if current is None or current.key != key or not current.action:
            raise engine.Conflict("That step isn't next. The tour has moved on; refresh to see where it is.")
        handler = getattr(self, f"_do_{key}")
        message = handler()
        self._save()
        return message

    def _do_fire(self):
        table = self._seated_table(["4", "5", "6", "2"])
        if table is None:
            raise engine.Conflict("No seated table is free for a run. Seat a party from Ana's screen first.")
        result = engine.food_ready(self.person("Sam"), table.pk, 2)
        self.data["run"] = result.task.pk
        return result.message

    def _do_backup_claim(self):
        run = self.run
        actor = run.offered_to if run.state == TaskState.OFFERED else self.person("Dev")
        return engine.claim(actor, run.pk).message

    def _do_deliver(self):
        if self.profile.is_fine:
            return engine.complete(self.course.owner, self.course.pk).message
        return engine.complete(self.run.owner, self.run.pk).message

    def _do_depart(self):
        avoid = [self.run.table_id] if self.run else []
        table = self._seated_table(["1", "2", "5", "P1"], avoid=avoid)
        if table is None:
            raise engine.Conflict("No seated table is free. Seat a party from Ana's screen first.")
        result = engine.mark_departed(self.person("Ana"), table.pk)
        self.data["reset"] = result.task.pk
        return result.message

    def _do_reset_claim(self):
        reset = self.reset
        actor = reset.offered_to if reset.state == TaskState.OFFERED else self.person("Lee")
        return engine.claim(actor, reset.pk).message

    def _do_reset_done(self):
        return engine.complete(self.reset.owner, self.reset.pk).message

    def _do_host_sees(self):
        self.data["seen"] = True
        return f"Table {self.reset.table.label} is back with the host."

    def _do_stage(self):
        table = self._seated_table(["3", "5", "1", "6"])
        if table is None:
            raise engine.Conflict("No seated table is free. Seat a party from Ana's screen first.")
        result = engine.stage_course(self.person("Noor"), table.pk)
        self.data["course"] = result.task.pk
        return result.message

    def _do_try_release(self):
        try:
            engine.release_course(self.person("Elise"), self.course.pk, self.person("Mateo").pk)
        except engine.Conflict as refused:
            self.data["refusal"] = refused.message
            return f"Refused by the server: {refused.message}"
        return "Released."

    def _do_pairing(self):
        return engine.confirm_pairing(self.person("Jordan"), self.course.pk).message

    def _do_team(self):
        return engine.confirm_team_ready(self.person("Elise"), self.course.pk).message

    def _do_release(self):
        if self.course.state == TaskState.ESCALATED:
            return engine.offer_to(self.person("Elise"), self.course.pk, self.person("Mateo").pk).message
        return engine.release_course(self.person("Elise"), self.course.pk, self.person("Mateo").pk).message

    def _do_claim(self):
        return engine.claim(self.person("Mateo"), self.course.pk).message

    def restart(self):
        self.data = {"loc": self.location.pk}
        self._save()

    # ------------------------------------------------------------------ json
    def state(self):
        steps = self.steps()
        current = next((i for i, s in enumerate(steps) if s.status == "current"), None)
        rows = []
        for s in steps:
            row = asdict(s)
            row.pop("done")
            row["who_url"] = reverse("web:staff_home", args=[s.who_sid]) if s.who_sid else None
            rows.append(row)
        return {
            "now_ms": int(time.time() * 1000),
            "edition": self.profile.edition_name,
            "preset": self.profile.name,
            "steps": rows,
            "current": current,
            "complete": current is None,
        }
