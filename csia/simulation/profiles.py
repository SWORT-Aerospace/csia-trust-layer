"""Operating profiles (S4). Every simulated result must name one.

The measurement that forced this to exist: IMU-bias detection is present in
the `sim` configuration and **absent** in `field` (min trust 0.99, no
detection at all). The detection was a property of the noise model, not of the
fault. A result that does not name its profile is therefore uninterpretable.

    IDEAL_SIM            simulator defaults. Useful for determinism checks and
                         for nothing else. NOT evidence about an aircraft.
    REALISTIC_SIM        hand-set noise in the range airframes plausibly show.
                         Engineering judgement, explicitly labelled as such.
    FIELD_DERIVED_NOISE  parameters estimated from the real-log corpus.

**What FIELD_DERIVED_NOISE is not.** The corpus is unannotated. Only
quantities legitimately estimable without labels are taken from it -- marginal
noise, update-rate jitter, dropout frequency, dispersion. No fault-conditioned
quantity is estimated from it, ever, because you cannot condition on a label
that does not exist. And it is NOT claimed to be statistically representative
of any fleet: 26 logs are 26 logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class NoiseProfile:
    name: str
    description: str
    basis: str
    representative: bool
    sitl_params: dict = field(default_factory=dict)
    csia_field_mode: bool = False
    estimable_from_unlabelled: tuple = ()
    not_estimable: tuple = ()

    def to_dict(self) -> dict:
        return asdict(self)


IDEAL_SIM = NoiseProfile(
    name="IDEAL_SIM",
    description="simulator defaults; sensor noise near zero",
    basis="ArduPilot/PX4 SITL default parameter set",
    representative=False,
    sitl_params={},
    csia_field_mode=False,
    not_estimable=("anything about a real aircraft",),
)

REALISTIC_SIM = NoiseProfile(
    name="REALISTIC_SIM",
    description=("hand-set sensor noise in a range small multirotors "
                 "plausibly exhibit"),
    basis=("engineering judgement, NOT measurement. Chosen to sit between "
           "IDEAL_SIM and the corpus-derived figures so that a result which "
           "survives only at IDEAL_SIM is visibly fragile."),
    representative=False,
    sitl_params={
        "SIM_ACC1_RND": 0.5,
        "SIM_ACC2_RND": 0.5,
        "SIM_GYR1_RND": 0.05,
        "SIM_GYR2_RND": 0.05,
        "SIM_MAG1_RND": 2.0,
        "SIM_BARO_RND": 0.1,
        "SIM_GPS1_NOISE": 0.3,
    },
    csia_field_mode=True,
)

FIELD_DERIVED_NOISE = NoiseProfile(
    name="FIELD_DERIVED_NOISE",
    description="noise and timing estimated from the 26-log public corpus",
    basis=("datasets/reports/exposure_v2.json and the content-addressed "
           "manifest datasets/manifests/px4_public_v1.json. The corpus is "
           "UNANNOTATED."),
    representative=False,          # 26 logs are not a fleet
    sitl_params={
        "SIM_ACC1_RND": 1.2,
        "SIM_ACC2_RND": 1.2,
        "SIM_GYR1_RND": 0.12,
        "SIM_GYR2_RND": 0.12,
        "SIM_MAG1_RND": 5.0,
        "SIM_BARO_RND": 0.25,
        "SIM_GPS1_NOISE": 0.6,
    },
    csia_field_mode=True,
    estimable_from_unlabelled=(
        "marginal sensor noise distribution",
        "update-rate jitter",
        "dropout frequency and duration",
        "covariance / dispersion under observed operating conditions",
        "regime occupancy where a regime is inferable without labels",
    ),
    not_estimable=(
        "false-alarm rate",
        "recall / detection probability",
        "P(gate closed | fault present)",
        "any fault-conditioned quantity whatsoever",
    ),
)

PROFILES = {p.name: p for p in (IDEAL_SIM, REALISTIC_SIM,
                                FIELD_DERIVED_NOISE)}


def get_profile(name: str) -> NoiseProfile:
    key = (name or "").strip().upper()
    if key not in PROFILES:
        raise KeyError(f"unknown profile {name!r}; available: "
                       f"{sorted(PROFILES)}")
    return PROFILES[key]
