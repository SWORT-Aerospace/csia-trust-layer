"""Edition and preset rules.

Both editions run the same task engine. Everything that differs between
Regular Service and the three Fine Dining presets is expressed here as data,
so the engine asks the profile instead of branching on edition names.

Internal keys never reference any third-party rating scheme; operators only
ever see the public names below.
"""

from __future__ import annotations

from dataclasses import dataclass

from .states import PairingStatus

REGULAR = "regular"
FINE = "fine"


@dataclass(frozen=True)
class ServiceProfile:
    key: str
    edition: str
    edition_name: str
    name: str  # public preset name
    summary: str
    holds_at_pass: bool  # expo stages courses; nothing moves until the captain releases
    requires_pairing: bool  # sommelier readiness (or captain's "no pairing")
    requires_team_ready: bool  # captain confirms the service team is ready
    escalation_role: str  # who missed offers go to: "lead" or "captain"
    uses_backup_offer: bool  # primary -> backup -> escalate, vs. assigned -> escalate
    open_claim_when_escalated: bool  # may any eligible worker grab an escalated task?

    @property
    def is_fine(self) -> bool:
        return self.edition == FINE

    @property
    def escalation_label(self) -> str:
        return "Returned to captain" if self.escalation_role == "captain" else "With floor lead"

    @property
    def pass_action_label(self) -> str:
        return "Stage course" if self.holds_at_pass else "Food ready"

    def release_blockers(self, task) -> list[str]:
        """Plain-language reasons a staged course cannot be released yet."""
        blockers: list[str] = []
        if self.requires_pairing and task.pairing_status not in PairingStatus.RESOLVED:
            blockers.append("Waiting for the sommelier's pairing check (or mark “No pairing”).")
        if self.requires_pairing and task.pairing_status == PairingStatus.NOT_REQUIRED:
            # Preset switched mid-service: the course was staged before checks existed.
            blockers.append("Pairing check not recorded for this course yet.")
        if self.requires_team_ready and not task.team_ready_at:
            blockers.append("Captain hasn't confirmed the service team is ready.")
        return blockers

    def task_offer_chain_uses_backup(self, task) -> bool:
        # Resets always use primary -> backup coverage; courses follow the preset.
        if task.kind == "reset":
            return True
        return self.uses_backup_offer


PROFILES: dict[str, ServiceProfile] = {
    "regular": ServiceProfile(
        key="regular",
        edition=REGULAR,
        edition_name="Regular Service",
        name="Regular Service",
        summary="Food moves from expo to a runner right away. Missed offers go to backup, then the floor lead.",
        holds_at_pass=False,
        requires_pairing=False,
        requires_team_ready=False,
        escalation_role="lead",
        uses_backup_offer=True,
        open_claim_when_escalated=True,
    ),
    "captain_release": ServiceProfile(
        key="captain_release",
        edition=FINE,
        edition_name="Fine Dining",
        name="Captain Release",
        summary="Expo stages each course. The captain controls release and picks the runner.",
        holds_at_pass=True,
        requires_pairing=False,
        requires_team_ready=False,
        escalation_role="captain",
        uses_backup_offer=False,
        open_claim_when_escalated=False,
    ),
    "pairing_coordination": ServiceProfile(
        key="pairing_coordination",
        edition=FINE,
        edition_name="Fine Dining",
        name="Pairing Coordination",
        summary="Adds a sommelier readiness check. The captain can mark a course as needing no pairing.",
        holds_at_pass=True,
        requires_pairing=True,
        requires_team_ready=False,
        escalation_role="captain",
        uses_backup_offer=False,
        open_claim_when_escalated=False,
    ),
    "coordinated_service": ServiceProfile(
        key="coordinated_service",
        edition=FINE,
        edition_name="Fine Dining",
        name="Coordinated Service",
        summary="Adds the captain's confirmation that the service team is ready before release.",
        holds_at_pass=True,
        requires_pairing=True,
        requires_team_ready=True,
        escalation_role="captain",
        uses_backup_offer=False,
        open_claim_when_escalated=False,
    ),
}

PROFILE_CHOICES = [(p.key, f"{p.edition_name} — {p.name}" if p.is_fine else p.name) for p in PROFILES.values()]
FINE_PRESETS = [p for p in PROFILES.values() if p.is_fine]


def get_profile(key: str) -> ServiceProfile:
    return PROFILES.get(key, PROFILES["regular"])
