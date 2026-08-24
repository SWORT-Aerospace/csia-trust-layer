"""Canonical aircraft state: the one shape the diagnostic core consumes.

No ArduPilot field name, no PX4 field name and no MAVLink message name appears
below this module. An adapter converts its platform's dialect into these
types; the core never learns which platform it was.

Design decisions worth stating, because each one is a defect we have already
paid for:

**Every value carries its own quality.** `ChannelValue` is not a float, it is
a float *plus* whether that float means anything. v1 passed bare numbers and a
separate `valid` flag, and the ESC stub (W-5) slipped through as a perfectly
valid 0.8 A. A quality of `INFORMATIVE` is the only one that may drive a
relation.

**Missing is a reason, not a sentinel.** `fix_type < 3` does not become a
position of (0, 0, 0). It becomes `MISSING(NO_3D_FIX)`. Encoding "absent" as a
number is how a dropout turns into a fictitious kilometre-scale jump.

**Timestamps are monotonic and explicit.** `t_mono` is the deployment clock and
never goes backwards. `t_source` is whatever the vehicle said, kept for
forensics, allowed to jump when a flight controller reboots.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class Quality(enum.Enum):
    """Whether a present value may be used as diagnostic evidence.

    The ladder is deliberately not a confidence score. It is a statement about
    what has been *established* about the channel, and only the top rung is
    admissible. See docs/simulation/CHANNEL_SEMANTICS.yaml.
    """

    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE_UNVALIDATED = "AVAILABLE_UNVALIDATED"
    VALIDATED_SEMANTICS = "VALIDATED_SEMANTICS"
    INFORMATIVE = "INFORMATIVE"
    STUB_OR_NONINFORMATIVE = "STUB_OR_NONINFORMATIVE"

    @property
    def admissible(self) -> bool:
        """May a relation consume this? Only one rung says yes."""
        return self is Quality.INFORMATIVE


class MissingReason(enum.Enum):
    """Why a channel carries no usable value. Never collapse these to None."""

    NOT_RECEIVED = "NOT_RECEIVED"          # no message has arrived yet
    STALE = "STALE"                        # older than the channel's max age
    NO_3D_FIX = "NO_3D_FIX"                # GNSS fix_type < 3
    SENTINEL = "SENTINEL"                  # in-band "not measured" value
    FIELD_ABSENT = "FIELD_ABSENT"          # message lacks the field entirely
    NOT_QUALIFIED = "NOT_QUALIFIED"        # semantics not established
    STUB = "STUB"                          # present, well-formed, meaningless

    # OUT_OF_RANGE was here and is deliberately GONE. Nothing produced it, and
    # nothing should: a plausibility gate that drops "physically impossible"
    # sensor values would discard exactly the evidence a fault-detection layer
    # exists to notice. An IMU reading 400 m/s^2 is not noise to be filtered,
    # it is the finding. Values that cannot be arithmetic at all (NaN, inf)
    # are handled where they arise, and the reason a channel is unusable is
    # always one of the reasons above -- each of which some code path actually
    # emits. A vocabulary member with no producer is a promise the system does
    # not keep; SENTINEL sat here unproduced for weeks and a real distinction
    # was being lost the whole time.


class SensorFrame(enum.Enum):
    """Coordinate convention of a vector value, stated rather than assumed."""

    BODY_Z_UP = "BODY_Z_UP"
    WORLD_Z_UP = "WORLD_Z_UP"
    NONE = "NONE"


@dataclass(frozen=True)
class ChannelValue:
    """One measured quantity, with everything needed to decide whether to
    believe it.

    `value` is None exactly when `missing` is set. The two are never both set
    and never both absent -- `__post_init__` enforces that, because a
    half-populated ChannelValue is the bug this class exists to prevent.
    """

    channel: str
    value: Any = None
    unit: str = ""
    quality: Quality = Quality.UNAVAILABLE
    frame: SensorFrame = SensorFrame.NONE
    missing: Optional[MissingReason] = None
    t_source: Optional[float] = None
    age_s: Optional[float] = None
    note: str = ""

    def __post_init__(self):
        if (self.value is None) != (self.missing is not None):
            raise ValueError(
                f"{self.channel}: exactly one of value/missing must be set "
                f"(value={self.value!r}, missing={self.missing!r})")
        if self.missing is not None and self.quality.admissible:
            raise ValueError(
                f"{self.channel}: missing value cannot be INFORMATIVE")

    @property
    def usable(self) -> bool:
        """True only if present AND semantically admissible."""
        return self.missing is None and self.quality.admissible

    @classmethod
    def absent(cls, channel: str, reason: MissingReason,
               quality: Quality = Quality.UNAVAILABLE,
               note: str = "") -> "ChannelValue":
        return cls(channel=channel, value=None, missing=reason,
                   quality=quality, note=note)


@dataclass
class AircraftSample:
    """One tick of canonical vehicle state.

    Field groups mirror the interface named in the v1.1 work package. Each
    group is a dict of channel-name -> ChannelValue so that a channel can be
    individually missing without nulling its whole sensor.
    """

    t_mono: float                              # monotonic deployment clock, s
    t_source: Optional[float] = None           # vehicle-reported time, s
    imu: dict = field(default_factory=dict)    # imu0.accel, imu0.gyro, imu1.*
    gnss: dict = field(default_factory=dict)
    magnetometer: dict = field(default_factory=dict)
    barometer: dict = field(default_factory=dict)
    air_data: dict = field(default_factory=dict)
    battery: dict = field(default_factory=dict)
    esc: dict = field(default_factory=dict)
    navigation_state: dict = field(default_factory=dict)
    estimator_health: dict = field(default_factory=dict)
    flight_mode: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    GROUPS = ("imu", "gnss", "magnetometer", "barometer", "air_data",
              "battery", "esc", "navigation_state", "estimator_health")

    def channels(self):
        """Every ChannelValue in the sample, group-agnostic."""
        for g in self.GROUPS:
            for cv in getattr(self, g).values():
                yield cv

    def usable_channels(self):
        return [cv for cv in self.channels() if cv.usable]

    def blocked_channels(self):
        """Channels present in the stream but refused as evidence.

        This is the list a post-flight reader needs in order to tell
        "CSIA saw nothing" apart from "CSIA had nothing to see with"
        (W-1 self-occlusion presents exactly that way).
        """
        return [cv for cv in self.channels()
                if cv.missing in (MissingReason.STUB,
                                  MissingReason.NOT_QUALIFIED)
                or cv.quality is Quality.STUB_OR_NONINFORMATIVE]

    def get(self, channel: str) -> Optional[ChannelValue]:
        for g in self.GROUPS:
            cv = getattr(self, g).get(channel)
            if cv is not None:
                return cv
        return None

    def quality_summary(self) -> dict:
        out = {q.value: 0 for q in Quality}
        for cv in self.channels():
            out[cv.quality.value] += 1
        return out

    def to_log_dict(self) -> dict:
        """Flat, JSON-safe rendering for the S9 flight log."""
        def enc(v):
            if hasattr(v, "tolist"):
                return v.tolist()
            return v

        chans = {}
        for g in self.GROUPS:
            for name, cv in getattr(self, g).items():
                chans[name] = {
                    "value": enc(cv.value),
                    "unit": cv.unit,
                    "quality": cv.quality.value,
                    "frame": cv.frame.value,
                    "missing": cv.missing.value if cv.missing else None,
                    "age_s": cv.age_s,
                    "usable": cv.usable,
                }
        return {
            "t_mono": self.t_mono,
            "t_source": self.t_source,
            "flight_mode": self.flight_mode,
            "channels": chans,
            "quality_summary": self.quality_summary(),
            "metadata": self.metadata,
        }
