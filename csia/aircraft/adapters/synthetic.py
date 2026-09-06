"""Synthetic adapter: constructed evidence, indelibly marked as constructed.

For unit tests, property-based testing, conformance testing and deliberately
bad-system testing. Never for a paper number.

THE ONE THING THIS MODULE MUST GUARANTEE
----------------------------------------
Synthetic evidence must be impossible to mistake for measured evidence, even
after it has been serialised, copied, and read by somebody who was not here.
A convention would not survive that. So the marker is structural:

  * every sample carries `metadata["synthetic"] = True`;
  * every sample carries `metadata["synthetic_warning"]`, a sentence that
    survives into any JSON dump;
  * the platform string is literally `"synthetic"`, so a trial manifest that
    recorded the adapter name already records the disqualification;
  * `tests/test_synthetic_evidence_is_quarantined.py` greps the research and
    publication trees and fails if the marker appears anywhere near a paper
    artifact.

The fourth is the one that actually holds the line. The first three are
labels; the test is the enforcement.

WHY A SYNTHETIC ADAPTER IS WORTH HAVING AT ALL
-----------------------------------------------
Three jobs that no recorded trace can do:

  1. construct states a real vehicle rarely reaches -- every channel stale at
     once, a gate closing on the single discriminator, a hypothesis-dependent
     gate that is provably non-informative;
  2. generate structures for property testing at volume;
  3. build systems that are DELIBERATELY WRONG, so a conformance suite can be
     shown to reject them. A test method that has never rejected anything has
     not been tested.
"""

from __future__ import annotations

import time
from typing import Iterable, Optional

from ..sample import (AircraftSample, ChannelValue, MissingReason, Quality,
                      SensorFrame)
from .base import GROUP_OF, PlatformAdapter

SYNTHETIC_WARNING = (
    "SYNTHETIC EVIDENCE -- constructed for testing. This sample was not "
    "measured on any vehicle, simulated or physical, and may never appear in "
    "a paper result, a trial manifest scored as evidence, or a public "
    "evidence capsule."
)

#: Default units per channel, so a hand-written test state does not have to
#: restate them and cannot drift from the live adapters.
DEFAULT_UNITS = {
    "imu0.accel": "m/s^2", "imu0.gyro": "rad/s",
    "imu1.accel": "m/s^2", "imu1.gyro": "rad/s",
    "mag.field_ut": "uT",
    "baro.altitude": "m", "baro.temp_c": "degC",
    "gnss.position": "m", "gnss.velocity": "m/s", "gnss.velocity_z": "m/s",
    "battery.voltage": "V", "battery.current": "A",
    "esc.rpm": "rpm", "esc.current": "A",
    "vibration.rms": "m/s^2",
    "vehicle_status.armed": "bool",
    "estimator.variances": "", "estimator.flight_mode": "",
}


class SyntheticAdapter(PlatformAdapter):
    """Build canonical samples directly, from a declared state.

    `set_channel` and `set_missing` are the whole API. There is deliberately
    no physics: this adapter does not simulate a vehicle, it asserts a
    canonical state. Anything that needs a vehicle should use a real
    simulator and a real platform adapter.
    """

    platform = "synthetic"
    adapter_version = "1.0.0"

    def __init__(self, *, contract=None, clock=time.monotonic,
                 label: str = "unlabelled"):
        super().__init__(contract=contract, clock=clock)
        self.label = label
        self._state: dict = {}
        self._t_mono = 0.0
        self._flight_mode: Optional[str] = None

    # -- state construction ------------------------------------------------

    def set_channel(self, channel: str, value, *, unit: Optional[str] = None,
                    quality: Quality = Quality.INFORMATIVE,
                    frame: SensorFrame = SensorFrame.NONE,
                    age_s: Optional[float] = 0.0,
                    note: str = "") -> "SyntheticAdapter":
        if channel not in GROUP_OF:
            raise ValueError(
                f"{channel!r} is not a canonical channel. Synthetic states "
                f"must use the same vocabulary as live adapters, or a test "
                f"passes against a channel the core has never seen.")
        if value is None:
            raise ValueError(
                f"{channel}: use set_missing() to declare absence. A None "
                f"value with no reason is exactly the half-populated state "
                f"ChannelValue rejects.")
        self._state[channel] = ChannelValue(
            channel=channel, value=value,
            unit=unit if unit is not None else DEFAULT_UNITS.get(channel, ""),
            quality=quality, frame=frame, age_s=age_s, note=note)
        return self

    def set_missing(self, channel: str, reason: MissingReason, *,
                    quality: Quality = Quality.UNAVAILABLE,
                    note: str = "") -> "SyntheticAdapter":
        if channel not in GROUP_OF:
            raise ValueError(f"{channel!r} is not a canonical channel")
        self._state[channel] = ChannelValue.absent(
            channel, reason, quality=quality, note=note)
        return self

    def clear(self, channel: str) -> "SyntheticAdapter":
        """Remove a channel entirely -- the vehicle never sent it.

        Distinct from set_missing: a cleared channel is ABSENT FROM THE
        SAMPLE, where a missing one is present-and-unusable-for-a-reason. The
        two reach the core differently and conflating them would hide the
        difference the whole canonical record exists to preserve.
        """
        self._state.pop(channel, None)
        return self

    def advance(self, dt: float = 0.04) -> "SyntheticAdapter":
        self._t_mono += dt
        return self

    def set_flight_mode(self, mode: Optional[str]) -> "SyntheticAdapter":
        self._flight_mode = mode
        return self

    # -- adapter surface ---------------------------------------------------

    def ingest(self, msg) -> None:
        raise NotImplementedError(
            "SyntheticAdapter has no wire format. Build state with "
            "set_channel/set_missing.")

    def sample(self, t_mono: Optional[float] = None) -> AircraftSample:
        s = AircraftSample(
            t_mono=self._t_mono if t_mono is None else t_mono,
            t_source=None, flight_mode=self._flight_mode)
        for channel, cv in self._state.items():
            getattr(s, GROUP_OF[channel])[channel] = cv
        s.metadata = {
            "platform": self.platform,
            "adapter_version": self.adapter_version,
            "label": self.label,
            # The three structural markers. Removing any of them is a
            # deliberate act that a reviewer can see in a diff.
            "synthetic": True,
            "synthetic_warning": SYNTHETIC_WARNING,
            "admissible_as_evidence": False,
        }
        return s

    def status(self) -> dict:
        d = super().status()
        d["synthetic"] = True
        d["synthetic_warning"] = SYNTHETIC_WARNING
        return d


def from_states(states: Iterable[dict], *, label: str = "sequence"):
    """Build a sequence of samples from declarative dicts.

    Each state is `{"channels": {name: value_or_(reason)}, "dt": float}`.
    Intended for property tests and conformance vectors, where the state
    matters and the construction should be one line.
    """
    adapter = SyntheticAdapter(label=label)
    out = []
    for st in states:
        for name, spec in (st.get("channels") or {}).items():
            if isinstance(spec, MissingReason):
                adapter.set_missing(name, spec)
            elif spec is None:
                adapter.clear(name)
            else:
                adapter.set_channel(name, spec)
        out.append(adapter.sample())
        adapter.advance(st.get("dt", 0.04))
    return out
