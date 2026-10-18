"""Phase 3 — the deterministic action-consequence model.

THIS IS THE MODEL, AND IT IS THE ONLY MODELLED PART
----------------------------------------------------
`MODEL_BASED_ACTION_CONSEQUENCE` is an honest label for exactly this file.
The diagnosis is not modelled: `TrustState` comes from the frozen
`OnlineTrustLayer`, the fault comes from the frozen `csia.sensors` injector,
and P0's response comes from the frozen `FailsafePolicy`. What is modelled
here is the *vehicle's response to the response* -- how far it drifts, when it
gets down, how much fence and energy margin is left.

**No vehicle behaved in any way described by this file.** Nothing flew,
nothing was armed, nothing was commanded. Every number it produces is the
output of the arithmetic below.

EVERY CONSTANT IS DECLARED IN THE PREREGISTRATION
--------------------------------------------------
`research/consequence/phase3/PREREGISTRATION_PHASE3.md` §9 fixes all of them
before the locked partition is opened, and `tests/test_consequence_phase3.py`
asserts that this file and that document still agree. They are assumptions,
not measurements.

THE ONE ASSUMPTION THAT DECIDES WHETHER H2 CAN BE SUPPORTED AT ALL
-------------------------------------------------------------------
`WRONG_SOURCE_FACTOR = 1.60`. It says that selecting the FAULTY inertial unit
is worse than selecting neither -- that a confident wrong attribution costs
more than silence. Without it, an incorrect actionable decision would be
indistinguishable from doing nothing and H2 could not be falsified in either
direction. It is declared, it is not measured, and any H2 result is
conditional on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .action_adapter import (R_ABSTAIN, R_CAUTION_GENERIC,
                             R_CONTROLLED_DESCENT, R_NONE,
                             R_PREPARE_LANDING, R_SELECT_IMU0, R_SELECT_IMU1)

# --- preregistered constants (PREREGISTRATION_PHASE3.md section 9) --------
H_HOVER_M = 30.0
DESCENT_RATE_MPS = 1.5
REACT_DELAY_S = 0.5
GEOFENCE_R_M = 120.0
ENERGY_FULL_S = 900.0
DRIFT_IMU_MPS = 1.20
DRIFT_MAG_MPS = 0.65
DRIFT_ALT_MPS = 0.25
MITIGATED_FRACTION = 0.25
WRONG_SOURCE_FACTOR = 1.60
CAUTION_FRACTION = 0.60
SAFE_STATE_ALT_M = 0.5

CONSTANTS = {
    "H_HOVER_M": H_HOVER_M, "DESCENT_RATE_MPS": DESCENT_RATE_MPS,
    "REACT_DELAY_S": REACT_DELAY_S, "GEOFENCE_R_M": GEOFENCE_R_M,
    "ENERGY_FULL_S": ENERGY_FULL_S, "DRIFT_IMU_MPS": DRIFT_IMU_MPS,
    "DRIFT_MAG_MPS": DRIFT_MAG_MPS, "DRIFT_ALT_MPS": DRIFT_ALT_MPS,
    "MITIGATED_FRACTION": MITIGATED_FRACTION,
    "WRONG_SOURCE_FACTOR": WRONG_SOURCE_FACTOR,
    "CAUTION_FRACTION": CAUTION_FRACTION,
    "SAFE_STATE_ALT_M": SAFE_STATE_ALT_M,
}

#: Fault family -> the horizontal drift rate it causes while undetected.
FAULT_DRIFT = {
    "imu_bias": DRIFT_IMU_MPS,
    "dual_imu_bias": DRIFT_IMU_MPS,
    "mag_emi": DRIFT_MAG_MPS,
    "none": 0.0,
}

#: Responses that begin a descent.
DESCENDING = frozenset({R_PREPARE_LANDING, R_CONTROLLED_DESCENT})


def response_factor(response: str, *, faulty_source: Optional[str]) -> float:
    """Drift multiplier for a response, given which unit is actually bad.

    `SELECT_IMU*` is the only response whose value depends on the latent
    truth, which is the point: it is the only one that asserts an attribution
    and can therefore assert the wrong one.
    """
    if response in (R_SELECT_IMU0, R_SELECT_IMU1):
        chosen = "imu0" if response == R_SELECT_IMU0 else "imu1"
        if faulty_source is None:
            # nothing is wrong, so selecting a unit is a needless
            # reconfiguration, not a hazard
            return CAUTION_FRACTION
        return (WRONG_SOURCE_FACTOR if chosen == faulty_source
                else MITIGATED_FRACTION)
    if response == R_CONTROLLED_DESCENT:
        return MITIGATED_FRACTION
    if response in (R_PREPARE_LANDING, R_CAUTION_GENERIC, R_ABSTAIN):
        return CAUTION_FRACTION
    return 1.0


def correct_response(fault_family: str, faulty_source: Optional[str]) -> str:
    """The response the latent truth calls for. Ground truth, not a policy."""
    if fault_family == "none":
        return R_NONE
    if fault_family == "dual_imu_bias":
        return R_CONTROLLED_DESCENT
    if fault_family == "imu_bias":
        return R_SELECT_IMU1 if faulty_source == "imu0" else R_SELECT_IMU0
    if fault_family == "mag_emi":
        return R_CAUTION_GENERIC
    raise ValueError(f"no declared correct response for {fault_family!r}")


@dataclass
class Outcome:
    """What the model says happened. Every field is derived, none assumed."""
    time_to_first_response_s: Optional[float] = None
    time_to_correct_response_s: Optional[float] = None
    time_to_safe_state_s: Optional[float] = None
    position_error_m: float = 0.0
    max_position_error_m: float = 0.0
    altitude_error_m: float = 0.0
    geofence_margin_m: float = GEOFENCE_R_M
    min_geofence_margin_m: float = GEOFENCE_R_M
    energy_margin_frac: float = 1.0
    geofence_breached: bool = False
    airborne_s: float = 0.0
    final_altitude_m: float = 0.0
    reached_safe_state: bool = False
    responses_seen: List[str] = field(default_factory=list)


def simulate(ticks, *, fault_family: str, faulty_source: Optional[str],
             correct: str) -> Outcome:
    """Integrate the model over a scenario's ticks.

    `ticks` is a sequence of dicts with keys `t`, `airborne`, `response`.
    Airborne is a fact of the scenario schedule -- the vehicle is on the
    ground before it arms -- and drift accrues only while airborne, because a
    grounded vehicle does not fly away from an undetected bias.
    """
    out = Outcome()
    base_rate = FAULT_DRIFT[fault_family]
    alt = 0.0
    e_h = 0.0
    e_alt = 0.0
    airborne_s = 0.0
    pending: List[tuple] = []          # (effective_time, response)
    active = R_NONE
    seen = []
    prev_t = None
    for tick in ticks:
        t = float(tick["t"])
        dt = 0.0 if prev_t is None else t - prev_t
        prev_t = t
        response = tick["response"]
        if response != (seen[-1] if seen else R_NONE):
            pending.append((t + REACT_DELAY_S, response))
        seen.append(response)
        while pending and pending[0][0] <= t:
            active = pending.pop(0)[1]
        if response != R_NONE and out.time_to_first_response_s is None:
            out.time_to_first_response_s = t
        if response == correct and out.time_to_correct_response_s is None:
            out.time_to_correct_response_s = t

        if tick["airborne"]:
            if alt <= 0.0:
                alt = H_HOVER_M
            airborne_s += dt
            factor = response_factor(active, faulty_source=faulty_source)
            e_h += base_rate * factor * dt
            if fault_family in ("imu_bias", "dual_imu_bias"):
                e_alt += DRIFT_ALT_MPS * factor * dt
            if active in DESCENDING:
                alt = max(0.0, alt - DESCENT_RATE_MPS * dt)
            if alt <= SAFE_STATE_ALT_M and not out.reached_safe_state:
                out.reached_safe_state = True
                out.time_to_safe_state_s = t
        out.max_position_error_m = max(out.max_position_error_m, e_h)
        out.min_geofence_margin_m = min(out.min_geofence_margin_m,
                                        GEOFENCE_R_M - e_h)

    out.position_error_m = e_h
    out.altitude_error_m = e_alt
    out.geofence_margin_m = GEOFENCE_R_M - e_h
    out.geofence_breached = out.min_geofence_margin_m < 0.0
    out.energy_margin_frac = max(0.0, 1.0 - airborne_s / ENERGY_FULL_S)
    out.airborne_s = airborne_s
    out.final_altitude_m = alt
    out.responses_seen = sorted(set(seen))
    return out
