"""Vehicle profile: the plumbing declaration, and nothing else.

A profile says what a particular airframe provides, over what transport, at
what rate. It is the file a user writes to plug CSIA into a new vehicle, and
it is the ONLY thing they should have to write.

WHAT A PROFILE MAY NOT DO
-------------------------
A profile may not change diagnostic mathematics. Not a threshold, not a
weight, not a prior, not a signature, not a gate definition, not a smoothing
constant. `validate()` rejects any key that would, by name, and a test
asserts the rejection list covers every frozen-core tuning constant.

This is not defensive style; it is the load-bearing property of the whole
pluggable architecture. The moment a profile can move a threshold, "the same
frozen core ran on both vehicles" stops being true, and every cross-platform
comparison in the paper becomes a comparison of two differently-tuned
systems.

FRESHNESS IS THE ONE THING A PROFILE LEGITIMATELY SETS
------------------------------------------------------
Per-channel max age is genuinely platform-dependent -- PX4's ESC_STATUS
publishes near 1 Hz where ArduPilot's is faster, and a shared constant made
PX4 report STALE for half of every publish period. The adapter already
derives max-age from the declared rate; the profile supplies the rate. That
is plumbing, and it is why `nominal_rate_hz` is allowed while
`smoothing_alpha` is not.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml

#: Keys that would move diagnostic mathematics. Rejected by name, at any depth.
#: Every entry corresponds to a real constant in the frozen core; the list is
#: not speculative and `tests/test_vehicle_profile.py` pins it against source.
FORBIDDEN_KEYS = frozenset({
    "threshold", "thresholds", "nav_caution", "nav_critical",
    "weight", "weights", "w_phys", "w_stat", "w_temp", "w_nbr",
    "prior", "priors", "prior_nominal",
    "signature", "signatures", "low", "hypothesis_signature",
    "gate_expression", "gate_definition", "speed_gate", "gate_lo", "gate_hi",
    # `gate` bare, and GATE_SPEED_LO by name. Found by
    # test_the_forbidden_list_covers_the_frozen_cores_real_constants on its
    # first run: the list had "speed_gate" and "gate_lo" and neither token
    # matches the constant the comparator actually defines, so a profile could
    # have set the horizontal-speed gate threshold and nothing would have
    # objected. Exactly the drift that test exists to catch.
    "gate", "gate_speed_lo", "gate_speed_hi",
    "smoothing", "smoothing_alpha", "alpha", "smooth_alpha",
    "evidence_mult", "eps", "rho", "rho_min", "rho_max",
    "forgetting", "forgetting_factor", "decay",
    "cusum_k", "cusum_h", "reference_value", "decision_interval",
})

#: Canonical channel names a profile may declare. Anything else is a typo and
#: a typo that silently means "not configured" is worse than an error.
KNOWN_CHANNELS = frozenset({
    "imu0.accel", "imu0.gyro", "imu1.accel", "imu1.gyro",
    "mag.field_ut",
    "baro.altitude", "baro.temp_c",
    "gnss.position", "gnss.velocity", "gnss.velocity_z",
    "battery.voltage", "battery.current",
    "esc.rpm", "esc.current",
    "vibration.rms",
    "vehicle_status.armed",
    "estimator.variances", "estimator.flight_mode",
})

KNOWN_AUTOPILOTS = frozenset({"ardupilot", "px4", "replay", "synthetic"})


class ProfileError(ValueError):
    """A profile that would change the science, or that cannot be trusted."""


@dataclass
class VehicleProfile:
    profile_id: str
    autopilot: str
    airframe: str = "unspecified"
    transport: dict = field(default_factory=dict)
    streams: dict = field(default_factory=dict)
    functions: dict = field(default_factory=dict)
    experiment: dict = field(default_factory=dict)
    safety: dict = field(default_factory=dict)
    source_path: Optional[str] = None
    raw: dict = field(default_factory=dict)

    @property
    def declared_channels(self) -> tuple:
        """Channels this vehicle is expected to provide."""
        return tuple(sorted(
            ch for ch, spec in self.streams.items()
            if (spec or {}).get("status", "declared") != "inapplicable"))

    @property
    def inapplicable_channels(self) -> tuple:
        """Channels this airframe structurally cannot provide.

        Distinct from simply omitting them: omission means "not wired here",
        `inapplicable` means "this board has one IMU". Both are non-faults and
        they are different non-faults.
        """
        return tuple(sorted(
            ch for ch, spec in self.streams.items()
            if (spec or {}).get("status") == "inapplicable"))

    @property
    def rates_hz(self) -> dict:
        return {ch: (spec or {}).get("nominal_rate_hz")
                for ch, spec in self.streams.items()
                if (spec or {}).get("nominal_rate_hz") is not None}

    @property
    def fault_injection_enabled(self) -> bool:
        return bool((self.experiment.get("fault_injector") or {})
                    .get("enabled", False))

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "autopilot": self.autopilot,
            "airframe": self.airframe,
            "declared_channels": list(self.declared_channels),
            "inapplicable_channels": list(self.inapplicable_channels),
            "rates_hz": self.rates_hz,
            "fault_injection_enabled": self.fault_injection_enabled,
            "source_path": self.source_path,
        }


def _walk_keys(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield f"{path}.{k}".lstrip("."), k
            yield from _walk_keys(v, f"{path}.{k}".lstrip("."))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_keys(v, f"{path}[{i}]")


def validate(doc: dict, source_path: Optional[str] = None) -> VehicleProfile:
    """Parse and check a profile. Raises ProfileError with a reason.

    Every check below rejects something that would otherwise fail silently at
    runtime or, worse, succeed while meaning something else.
    """
    where = source_path or "<dict>"
    if not isinstance(doc, dict):
        raise ProfileError(f"{where}: profile is not a mapping")

    # -- the load-bearing check --------------------------------------------
    offenders = sorted({
        f"{p} (key {k!r})" for p, k in _walk_keys(doc)
        if k.lower() in FORBIDDEN_KEYS})
    if offenders:
        raise ProfileError(
            f"{where}: a vehicle profile may not set diagnostic parameters. "
            f"Offending keys:\n  " + "\n  ".join(offenders) +
            "\n\nA profile declares PLUMBING -- transport, streams, rates, "
            "which channels exist. Thresholds, weights, priors, signatures, "
            "gates and smoothing belong to the frozen core, and a profile "
            "that could move them would make 'the same core ran on both "
            "vehicles' false.")

    vp = doc.get("vehicle_profile") or {}
    profile_id = vp.get("id") or doc.get("profile_id")
    if not profile_id:
        raise ProfileError(f"{where}: no vehicle_profile.id")

    autopilot = ((doc.get("autopilot") or {}).get("family")
                 or doc.get("autopilot_family"))
    if autopilot not in KNOWN_AUTOPILOTS:
        raise ProfileError(
            f"{where}: autopilot.family {autopilot!r} is not one of "
            f"{sorted(KNOWN_AUTOPILOTS)}. An unrecognised family would select "
            f"no adapter and the failure would surface as silence.")

    streams = doc.get("streams") or {}
    unknown = sorted(set(streams) - KNOWN_CHANNELS)
    if unknown:
        raise ProfileError(
            f"{where}: unknown channel name(s) {unknown}. A misspelled "
            f"channel is indistinguishable from a channel the vehicle does "
            f"not have, and would be silently reported NOT_CONFIGURED.")

    for ch, spec in streams.items():
        spec = spec or {}
        status = spec.get("status", "declared")
        if status not in ("declared", "inapplicable"):
            raise ProfileError(
                f"{where}: channel {ch} has status {status!r}; expected "
                f"'declared' or 'inapplicable'")
        rate = spec.get("nominal_rate_hz")
        if rate is not None and (not isinstance(rate, (int, float))
                                 or rate <= 0):
            raise ProfileError(
                f"{where}: channel {ch} nominal_rate_hz must be a positive "
                f"number, got {rate!r}")

    return VehicleProfile(
        profile_id=profile_id,
        autopilot=autopilot,
        airframe=vp.get("airframe", "unspecified"),
        transport=doc.get("transport") or {},
        streams=streams,
        functions=doc.get("functions") or {},
        experiment=doc.get("experiment") or {},
        safety=doc.get("safety") or {},
        source_path=source_path,
        raw=doc,
    )


def load(path: str) -> VehicleProfile:
    if not os.path.exists(path):
        raise ProfileError(f"{path}: no such profile")
    with open(path, encoding="utf-8") as fh:
        return validate(yaml.safe_load(fh), source_path=path)
