"""Phase 3.1 — the fault families Phase 3 could not reach, and nothing else.

WHY THIS IS A SEPARATE MODULE
------------------------------
`consequence_model.py` is listed in Phase 3's SHA-256 manifest, and that
manifest's job is to say what Phase 3 was committed at. Editing the file to
add two fault families would change its hash, and the manifest would then
describe a state Phase 3 never ran in. So Phase 3.1 extends rather than edits.
Every Phase-3 constant is imported, not restated, and none is re-tuned.

WHAT IS AND IS NOT PHYSICALLY MEANINGFUL, DECLARED BEFORE THE RUN
------------------------------------------------------------------
A power sag and a rotor-vibration anomaly do not cause an attitude error, so
a horizontal drift rate for them would be invented rather than modelled. Both
are declared 0.0. What IS meaningful for them is **time to safe state**: they
reach `CRITICAL` and issue `LAND_NOW` / `LAND_SOON`, which the model turns
into a descent. That is the field Phase 3 recorded as undefined in all 216 of
its scenarios and named as its first removal action.

The energy margin is declared NOT meaningful for any family here.
`ENERGY_FULL_S` is a fixed endurance and no modelled fault consumes energy
differently, so the column measures airborne time. It is still recorded, and
it is labelled, rather than quietly dropped.
"""
from __future__ import annotations

from typing import Optional

from .action_adapter import (R_CAUTION_GENERIC, R_CONTROLLED_DESCENT, R_NONE,
                             R_PREPARE_LANDING, R_SELECT_IMU0, R_SELECT_IMU1)
from .consequence_model import (CONSTANTS, DRIFT_IMU_MPS, FAULT_DRIFT,
                                Outcome, correct_response, response_factor,
                                simulate)

#: Neither family moves the vehicle. Declared, not derived, and declared as
#: zero precisely so that no drift number is invented for them.
DRIFT_POWER_MPS = 0.0
DRIFT_STRUCT_MPS = 0.0

FAULT_DRIFT_31 = dict(FAULT_DRIFT)
FAULT_DRIFT_31["power_sag"] = DRIFT_POWER_MPS
FAULT_DRIFT_31["vibration_anomaly"] = DRIFT_STRUCT_MPS

#: family -> which recorded consequence columns mean anything for it.
MEANINGFUL = {
    "imu_bias": ("position_error_m", "altitude_error_m",
                 "min_geofence_margin_m"),
    "power_sag": ("time_to_safe_state_s",),
    "vibration_anomaly": ("time_to_safe_state_s",),
    "none": (),
}

#: Recorded for every family and meaningful for none of them. Kept visible.
NOT_MEANINGFUL_ANY_FAMILY = ("energy_margin_frac",)

CONSTANTS_31 = dict(CONSTANTS)
CONSTANTS_31["DRIFT_POWER_MPS"] = DRIFT_POWER_MPS
CONSTANTS_31["DRIFT_STRUCT_MPS"] = DRIFT_STRUCT_MPS


def correct_response_31(fault_family: str,
                        faulty_source: Optional[str]) -> str:
    """Ground truth for the Phase-3.1 families, Phase 3's for the rest."""
    if fault_family == "power_sag":
        # The pack is sagging. The right answer is to end the flight on our
        # terms; it is not to reconfigure a sensor, and it is not to keep
        # flying. PREPARE_LANDING and LAND_NOW are the same response class.
        return R_PREPARE_LANDING
    if fault_family == "vibration_anomaly":
        # Rotor damage propagates. Same class, same reasoning.
        return R_PREPARE_LANDING
    return correct_response(fault_family, faulty_source)


def simulate_31(ticks, *, fault_family: str, faulty_source: Optional[str],
                correct: str) -> Outcome:
    """Phase 3's integrator, with the two new families' drift rates in scope.

    The integrator itself is not reimplemented. `FAULT_DRIFT` is a module-level
    table in `consequence_model`, so the extended table is installed for the
    call and restored afterwards -- a patch with a visible beginning and end
    beats a second copy of the arithmetic that could drift from the first.
    """
    from . import consequence_model as base
    original = base.FAULT_DRIFT
    base.FAULT_DRIFT = FAULT_DRIFT_31
    try:
        return simulate(ticks, fault_family=fault_family,
                        faulty_source=faulty_source, correct=correct)
    finally:
        base.FAULT_DRIFT = original
