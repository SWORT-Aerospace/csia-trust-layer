"""Semantic qualification: deciding whether a present field means anything.

Loads `docs/simulation/CHANNEL_SEMANTICS.yaml` and answers one question per
channel: **may this drive a CSIA relation?**

Where this lives matters. It runs at the ADAPTER boundary, not inside the
diagnostic core. Nothing here changes a v1 threshold, weight, gate or
relation -- the core still does exactly what it did at
`csia-v1.0-research-final`. The only difference is what reaches it.

That placement is deliberate and was specified: "implement the concept at the
adapter/qualification layer, not by falsifying the scientific baseline."
Blocking a stub inside the core would have meant a tuned threshold and a
changed algorithm. Blocking it at the adapter means the algorithm is
unchanged and simply receives MISSING, which it already knows how to handle by
abstaining.

Qualification is per PLATFORM INSTANCE, not global. The ArduPilot *simulator*
publishes a constant ESC current; a real ArduPilot vehicle with real ESC
telemetry does not. A bench with real hardware re-runs the probe rather than
inheriting the simulator's row.
"""

from __future__ import annotations

import os
from typing import Optional

import yaml

from .sample import ChannelValue, MissingReason, Quality

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTRACT_PATH = os.path.join(ROOT, "docs", "simulation",
                             "CHANNEL_SEMANTICS.yaml")

# Qualification depends on where the data comes from, not only on the channel.
# A simulator row does not transfer to hardware and vice versa.
CONTEXT_SIMULATOR = "SIMULATOR"
CONTEXT_HARDWARE = "HARDWARE"
CONTEXT_REPLAY = "REPLAY"


class ChannelContract:
    """One row of CHANNEL_SEMANTICS.yaml, with its admissibility decision."""

    __slots__ = ("channel", "node", "unit", "quantity", "quality",
                 "may_use", "reason", "simulator_implementation",
                 "missing_semantics", "aggregation", "criterion", "raw")

    def __init__(self, row: dict):
        self.raw = row
        self.channel = row["channel"]
        self.node = row.get("node", "")
        self.unit = row.get("unit", "")
        self.quantity = row.get("quantity", "")
        self.quality = Quality(row["qualification"])
        self.may_use = bool(row.get("csia_may_use", False))
        self.reason = row.get("csia_may_use_reason", "")
        self.simulator_implementation = row.get("simulator_implementation", "")
        self.missing_semantics = row.get("missing_semantics", "")
        self.aggregation = row.get("aggregation", "")
        # VARIATION (default) or DECODE. See the header of
        # CHANNEL_SEMANTICS.yaml: a latched enum is constant by nature and
        # cannot be qualified by variation.
        self.criterion = row.get("qualification_criterion", "VARIATION")

    @property
    def admissible(self) -> bool:
        """Both gates must agree.

        `qualification: INFORMATIVE` says the channel carries information.
        `csia_may_use` says we have decided to consume it. They are separate
        because `estimator.variances` is genuinely INFORMATIVE and still must
        never enter diagnosis -- CSIA cannot be independent of an estimator it
        consumes. Requiring both keeps that distinction expressible.
        """
        return self.quality.admissible and self.may_use

    def block_reason(self) -> MissingReason:
        if self.quality is Quality.STUB_OR_NONINFORMATIVE:
            return MissingReason.STUB
        if self.quality is Quality.UNAVAILABLE:
            return MissingReason.FIELD_ABSENT
        return MissingReason.NOT_QUALIFIED

    def __repr__(self):
        return (f"<ChannelContract {self.channel} {self.quality.value} "
                f"may_use={self.may_use}>")


class SemanticContract:
    """The loaded contract, plus per-instance overrides."""

    def __init__(self, path: str = CONTRACT_PATH,
                 context: str = CONTEXT_SIMULATOR):
        with open(path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        self.path = path
        self.context = context
        self.version = doc.get("contract_version")
        self.frozen_core = doc.get("frozen_core")
        self.platforms = doc.get("platforms", {})
        self.channels = {}
        for row in doc.get("channels", []):
            c = ChannelContract(row)
            if c.channel in self.channels:
                raise ValueError(f"duplicate channel row: {c.channel}")
            self.channels[c.channel] = c
        self._overrides = {}

    # -- overrides ---------------------------------------------------------

    def override(self, channel: str, quality: Quality, may_use: bool,
                 reason: str):
        """Re-qualify a channel for THIS deployment.

        Used when hardware differs from the simulator the contract was written
        against. An override is recorded in the flight log so a reader can see
        that a channel was admitted on local authority rather than on the
        committed contract.
        """
        if channel not in self.channels:
            raise KeyError(f"cannot override unknown channel {channel!r}")
        if not reason:
            raise ValueError("an override without a stated reason is not "
                             "permitted; that is how stubs get re-admitted")
        self._overrides[channel] = (quality, may_use, reason)

    def effective(self, channel: str):
        """(quality, may_use, reason, overridden)."""
        c = self.channels.get(channel)
        if c is None:
            return (Quality.UNAVAILABLE, False,
                    "channel is not in the semantic contract", False)
        if channel in self._overrides:
            q, u, r = self._overrides[channel]
            return (q, u, r, True)
        return (c.quality, c.may_use, c.reason, False)

    # -- the operation everything else calls -------------------------------

    def qualify(self, channel: str, value, *, unit: str = "",
                frame=None, t_source: Optional[float] = None,
                age_s: Optional[float] = None) -> ChannelValue:
        """Wrap a raw value in a ChannelValue with its admissibility decided.

        A blocked channel returns MISSING with the reason, never the value.
        The value is dropped on purpose: keeping it invites a later caller to
        use it "just for logging" and then for a decision.
        """
        from .sample import SensorFrame
        frame = frame or SensorFrame.NONE
        c = self.channels.get(channel)
        quality, may_use, reason, overridden = self.effective(channel)

        if c is None:
            return ChannelValue.absent(
                channel, MissingReason.NOT_QUALIFIED,
                note="not in CHANNEL_SEMANTICS.yaml; refused by default")

        if value is None:
            return ChannelValue.absent(
                channel, MissingReason.NOT_RECEIVED,
                quality=(Quality.UNAVAILABLE if quality.admissible
                         else quality),
                note=c.missing_semantics)

        if not (quality.admissible and may_use):
            note = reason or "not admissible under the semantic contract"
            if overridden:
                note = f"[OVERRIDE] {note}"
            # `Quality` on the CONTRACT describes the channel; `Quality` on a
            # ChannelValue describes *this value's admissibility*. They differ
            # for a channel that is genuinely INFORMATIVE but excluded by
            # policy -- estimator.variances is real, useful data that CSIA
            # must not consume, because a layer cannot be independent of an
            # estimator it reads. Reporting the value as INFORMATIVE while
            # withholding it would advertise it as usable, so the value is
            # graded VALIDATED_SEMANTICS (understood, not admitted) and the
            # contract grade is preserved in the note.
            vq = quality
            if quality.admissible and not may_use:
                vq = Quality.VALIDATED_SEMANTICS
                note = f"INFORMATIVE but excluded by policy: {note}"
            return ChannelValue.absent(channel, c.block_reason(),
                                       quality=vq, note=note)

        return ChannelValue(
            channel=channel, value=value, unit=unit or c.unit,
            quality=quality, frame=frame, t_source=t_source, age_s=age_s,
            note="[OVERRIDE] admitted locally" if overridden else "")

    # -- reporting ---------------------------------------------------------

    def admissible_channels(self):
        return sorted(k for k in self.channels if self.effective(k)[0:2] ==
                      (Quality.INFORMATIVE, True))

    def blocked_channels(self):
        out = []
        for k, c in sorted(self.channels.items()):
            q, u, r, _ = self.effective(k)
            if not (q.admissible and u):
                out.append((k, q.value, r))
        return out

    def report(self) -> str:
        lines = [f"semantic contract v{self.version} "
                 f"({os.path.relpath(self.path, ROOT)}) "
                 f"context={self.context}",
                 f"  frozen core: {self.frozen_core}",
                 f"  channels:    {len(self.channels)}"]
        adm = self.admissible_channels()
        lines.append(f"  ADMISSIBLE ({len(adm)}):")
        for k in adm:
            lines.append(f"      {k}")
        blocked = self.blocked_channels()
        lines.append(f"  BLOCKED ({len(blocked)}):")
        for k, q, r in blocked:
            lines.append(f"      {k:26s} {q}")
            if r:
                lines.append(f"          {r.strip().splitlines()[0]}")
        return "\n".join(lines)


_DEFAULT: Optional[SemanticContract] = None


def default_contract() -> SemanticContract:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = SemanticContract()
    return _DEFAULT
