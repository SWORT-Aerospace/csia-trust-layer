"""The gate inventory, read off `csia/runtime/online.py` by hand and pinned.

WHY THIS IS HAND-WRITTEN AND WHY THAT IS NOT A SHORTCUT
-------------------------------------------------------
The gates are expressions inside one method, not a declarative table. Parsing
them automatically would be guessing at intent from syntax; naming them from
their dictionary keys would be inferring behaviour from names, which the brief
forbids and which is how `degraded` came to mean the wrong thing in
`FL-017`'s neighbourhood.

So each row below was read from the source expression and records that
expression verbatim in `gate_expression`. A test re-reads the source and
asserts every recorded expression still occurs in it, so the inventory cannot
drift from the code without the suite failing.

THE DISTINCTION THE WHOLE PHASE TURNS ON
-----------------------------------------
`online.py` multiplies every edge and every physics check by its own gate AND
by the freshness of the sensors involved:

    E = {key: (lam, gate * fresh[a] * fresh[b]) ...}
    P = {n:   (lam, gate * fresh[n]) ...}

So there are two ways evidence disappears, and they are not the same:

    FRESHNESS_COUPLED   the gate closes only when the sensor is also stale or
                        invalid, so a freshness monitor sees it too.
    FRESHNESS_INDEPENDENT
                        the gate closes while the sensor's own data is fresh
                        and valid. Nothing in the freshness path reacts, and
                        the relation silently stops contributing.

The second class is what H1 is about. This module classifies every gate into
one of them and says, per gate, why.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

ONLINE = pathlib.Path(__file__).resolve().parents[1] / "csia/runtime/online.py"

FRESHNESS_COUPLED = "FRESHNESS_COUPLED"
FRESHNESS_INDEPENDENT = "FRESHNESS_INDEPENDENT"
ALWAYS_OPEN = "ALWAYS_OPEN"

IDENTIFIABLE = "IDENTIFIABLE"
AMBIGUOUS = "AMBIGUOUS"
NON_IDENTIFIABLE = "NON_IDENTIFIABLE"


@dataclass(frozen=True)
class Gate:
    """One gated evidence term, as the source actually computes it."""

    gate_id: str
    kind: str                     # "edge" or "physics"
    protects: str                 # the signal or relation
    gate_expression: str          # verbatim from online.py
    open_condition: str
    closed_condition: str
    data_fresh_when_closed: bool
    fault_can_close: bool
    independent_freshness_reacts: bool
    coupling: str
    endpoints: Tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        if self.coupling not in (FRESHNESS_COUPLED, FRESHNESS_INDEPENDENT,
                                 ALWAYS_OPEN):
            raise ValueError(f"{self.gate_id}: bad coupling {self.coupling!r}")

    @property
    def uncovered_candidate(self) -> bool:
        """H1's shape: closes, data still fresh, nothing else warns."""
        return (self.coupling == FRESHNESS_INDEPENDENT
                and self.data_fresh_when_closed
                and not self.independent_freshness_reacts)


#: Read from csia/runtime/online.py. `gate_expression` is verbatim; a test
#: asserts each one still appears in the source.
GATES: Tuple[Gate, ...] = (
    Gate("redundant_imu", "edge", "imu0 vs imu1 acceleration agreement",
         'E["redundant_imu"] = self._lam_upd(', "always", "never",
         False, False, False, ALWAYS_OPEN, ("imu0", "imu1"),
         "gate literal 1.0; disappears only when an endpoint goes stale"),
    Gate("accel_motor_current", "edge", "accel vs current-derived thrust",
         '"accel_motor_current", acc0[2] - f_from_cur, 0.45), armed_gate',
         "armed, after a 1 s spin-up ramp", "disarmed, or within the ramp",
         True, False, False, FRESHNESS_INDEPENDENT, ("imu0", "motor_esc"),
         "armed_gate is vehicle state, not data health. Disarmed on the "
         "ground with perfectly fresh IMU and ESC telemetry, this relation "
         "contributes nothing and no freshness signal changes."),
    Gate("accel_esc_rpm", "edge", "accel vs rpm-derived thrust",
         '"accel_esc_rpm", acc1[2] - f_from_rpm, 0.45), armed_gate',
         "armed, after ramp", "disarmed, or within the ramp",
         True, False, False, FRESHNESS_INDEPENDENT, ("imu1", "motor_esc"),
         "same as accel_motor_current, on the other IMU"),
    Gate("altitude_baro", "edge", "baro altitude vs GPS altitude",
         '"altitude_baro", alt - pos[2], 2.2), gvalid',
         "GPS valid and seen", "GPS invalid or unseen",
         False, True, True, FRESHNESS_COUPLED, ("baro", "gps"),
         "gvalid is gps.valid AND gps.seen, so the GPS freshness path "
         "reacts to the same condition"),
    Gate("velocity_gps_doppler_0", "edge", "IMU0 integration vs GPS doppler",
         'key, np.linalg.norm(d), 1.6, df=3 if vz_ok else 2), gvalid',
         "GPS valid and seen", "GPS invalid or unseen",
         False, True, True, FRESHNESS_COUPLED, ("imu0", "gps")),
    Gate("velocity_gps_doppler_1", "edge", "IMU1 integration vs GPS doppler",
         'key, np.linalg.norm(d), 1.6, df=3 if vz_ok else 2), gvalid',
         "GPS valid and seen", "GPS invalid or unseen",
         False, True, True, FRESHNESS_COUPLED, ("imu1", "gps")),
    Gate("attitude_gravity_mag", "edge", "mag heading vs IMU0 yaw",
         'wrap_angle(np.array([self._mag_heading - att0[2]]))[0],',
         "always", "never", False, False, False, ALWAYS_OPEN,
         ("mag", "imu0")),
    Gate("heading_course", "edge", "mag heading vs GPS ground course",
         'np.deg2rad(10.0)), speed_gate * gvalid',
         "horizontal speed above GATE_SPEED_HI and GPS valid",
         "horizontal speed below GATE_SPEED_LO, or GPS invalid",
         True, False, False, FRESHNESS_INDEPENDENT, ("mag", "gps"),
         "the speed_gate half closes on a hovering or slow vehicle with "
         "fully fresh mag and GPS. Ground course is undefined at low speed, "
         "so closing is CORRECT -- and the relation still vanishes with no "
         "freshness signal marking its absence."),
    Gate("power_thrust", "edge", "battery current vs ESC current sum",
         '"power_thrust", batt_i - float(esc_i.sum()) - AVIONICS_CURRENT,',
         "always", "never", False, False, False, ALWAYS_OPEN,
         ("battery", "motor_esc")),
    Gate("vibration_prop_freq", "edge", "vibration RMS vs rpm envelope",
         '"vibration_prop_freq", vib_rms - rms_pred, 0.035), 1.0',
         "always", "never", False, False, False, ALWAYS_OPEN,
         ("vibration", "motor_esc")),
    Gate("temp_bias_drift", "edge", "baro temperature rate of change",
         '"temp_bias_drift", dtemp, 0.5), 0.2',
         "never fully open", "never fully closed",
         True, False, False, FRESHNESS_INDEPENDENT, ("baro", "imu0"),
         "constant 0.2 weight. Permanently attenuated to a fifth regardless "
         "of data health; no condition opens it and none closes it."),
    Gate("phys_gps", "physics", "GPS position/velocity self-consistency",
         'gvalid * (1.0 if tau > 3.0 else 0.0))',
         "GPS valid and seen, and more than 3 s since start",
         "GPS invalid, or within the first 3 s",
         True, True, False, FRESHNESS_INDEPENDENT, ("gps",),
         "the tau > 3.0 warm-up half closes with fresh valid GPS for the "
         "first three seconds. A fault in that window is unattributable and "
         "no freshness signal says so."),
    Gate("phys_battery", "physics", "terminal voltage vs OCV model",
         '"phys_battery", batt_v - (ocv - batt_i * PACK_R_INTERNAL),',
         "always", "never", False, False, False, ALWAYS_OPEN, ("battery",)),
    Gate("phys_motor_esc", "physics", "ESC current vs rpm cube law",
         '"phys_motor_esc", float(np.abs(esc_i - i_pred).mean()), 0.2), 1.0',
         "always", "never", False, False, False, ALWAYS_OPEN,
         ("motor_esc",)),
    Gate("phys_mag", "physics", "magnetic field norm vs reference",
         '0.6), 1.0 if mag_ref_ready else 0.0)',
         "a magnetic reference has been established",
         "no reference yet",
         True, False, False, FRESHNESS_INDEPENDENT, ("mag",),
         "closed until _mag_ref is set, with the magnetometer fresh and "
         "valid throughout"),
    Gate("phys_baro", "physics", "barometric altitude rate sanity",
         '"phys_baro", max(abs(alt_rate) - 8.0, 0.0), 3.0), 1.0',
         "always", "never", False, False, False, ALWAYS_OPEN, ("baro",)),
    Gate("phys_vibration", "physics", "vibration RMS vs rpm envelope",
         'P["vibration"][1] * float(fresh["motor_esc"]))',
         "ESC telemetry fresh", "ESC telemetry stale or absent",
         True, True, False, FRESHNESS_INDEPENDENT, ("vibration",),
         "CROSS-SENSOR. The vibration check is gated by the freshness of a "
         "DIFFERENT sensor. The vibration channel can be perfectly fresh "
         "while its check is switched off by the ESC going quiet, and the "
         "vibration node's own freshness signal stays green."),
    Gate("hist_vr_withdrawal", "withdrawal",
         "temporal-predictor evidence (hist and vr) for any sensor",
         "return not (self._field and s[n].adapt_level > 25.0)",
         "adaptive level at or below 25 (residuals within ~5 sigma)",
         "adaptive level above 25 in field mode",
         True, True, False, FRESHNESS_INDEPENDENT, (),
         "A JUDGEMENT, RECORDED SO IT CAN BE DISAGREED WITH. This is not a "
         "multiplicative gate on E or P; it sets hist and vr to None, "
         "withdrawing the temporal-predictor evidence for that sensor. It "
         "is listed because it has H1's exact shape -- evidence disappears, "
         "the data stay fresh and valid, and no freshness signal marks the "
         "absence -- and excluding it on a technicality about WHERE the "
         "multiplication happens would hide the most self-referential case: "
         "the channel withdraws its own evidence because its residuals are "
         "chronically large, which is also when a fault is most likely. "
         "Counting it gives eight uncovered candidates; excluding it gives "
         "seven. Both numbers are in the inventory."),
)


def uncovered_candidates() -> Tuple[Gate, ...]:
    return tuple(g for g in GATES if g.uncovered_candidate)


def by_coupling() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for gate in GATES:
        out.setdefault(gate.coupling, []).append(gate.gate_id)
    return out


def source_expressions_present() -> Dict[str, bool]:
    """Every recorded expression must still occur in online.py."""
    text = ONLINE.read_text(encoding="utf-8")
    return {g.gate_id: (g.gate_expression in text) for g in GATES}


def inventory() -> dict:
    return {
        "schema": "csia.consequence.gate_inventory/1",
        "source": "csia/runtime/online.py",
        "evidence_level": "SOURCE_ANALYSIS",
        "gate_count": len(GATES),
        "by_coupling": by_coupling(),
        "uncovered_candidate_count": len(uncovered_candidates()),
        "uncovered_candidate_count_excluding_withdrawal": len(
            [g for g in uncovered_candidates() if g.kind != "withdrawal"]),
        "count_note": (
            "Eight with the hist/vr withdrawal path counted, seven without. "
            "The withdrawal is not a multiplicative gate on E or P but has "
            "H1's exact shape. The judgement is recorded in that gate's note "
            "so a reader can recount either way; no count is asserted as the "
            "only correct one."),
        "uncovered_candidates": [g.gate_id for g in uncovered_candidates()],
        "gates": [
            {"gate_id": g.gate_id, "kind": g.kind, "protects": g.protects,
             "gate_expression": g.gate_expression,
             "open_condition": g.open_condition,
             "closed_condition": g.closed_condition,
             "data_fresh_when_closed": g.data_fresh_when_closed,
             "fault_can_close": g.fault_can_close,
             "independent_freshness_reacts": g.independent_freshness_reacts,
             "coupling": g.coupling, "endpoints": list(g.endpoints),
             "uncovered_candidate": g.uncovered_candidate, "note": g.note}
            for g in GATES],
        "what_this_is_not": (
            "not a runtime measurement. This is what the source says the "
            "gates do. Whether a closure actually occurs, and with what "
            "consequence, is a separate question at a higher evidence "
            "level."),
    }
