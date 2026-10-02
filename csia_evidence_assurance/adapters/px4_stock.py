"""Stock PX4 evidence producers (CSIA 2.3). OFFBOARD ONLY.

Each producer turns stock topics (`stock_log.py`) into evidence envelopes,
following its claim in the claim register
(`research/csia_2_3_stock_bridge/CLAIMS.json`). Every one is event-relative:
it compares a window after a discovered event (`events.py`) with the window
before it (`stock_stats.WINDOWS`). The event is the analysis context named
`stock.event`.

| producer | claim | record | profile? | validity (relative to the event) |
|---|---|---|---|---|
| `px4:allocator.compensation` | PHYSICAL_EFFECT | ACTUATION/motor_m `actuation.physical_response` | yes (quad r1) | [10, 15] s: XSYS-001's validated T3 |
| `px4:esc.telemetry_response` | TELEMETRY_RESPONSE | ACTUATION/motor_m `esc.telemetry_response` | no: context (finding SB-1) | [0.5, 15] s |
| `px4:vehicle.rate_transient` | RATE_TRANSIENT | ACTUATION/motor_m `vehicle.rate_transient` | no: context | [0, 0.2] s: XSYS-001's validated T1 |
| `px4:allocator.status` | AUTHORITY | COMPUTE/control_allocator `allocation.authority` | no: context | [0.5, 15] s |
| `px4:battery.status` | SOURCE_TELEMETRY | POWER/battery `power.source_health` | yes | content age 1 s |
| `px4:battery.status` | WARNING | POWER/battery `power.battery_warning` | no: context | content age 1 s |

**SB-1.** The ESC telemetry claim is NOT placed on
`actuation.mechanical_response`. That relation is read by 2.1.1's
STALL_SIGNATURE, which takes the absence of ACT_STALLED as "stall checked
and absent". Without ESC current, a stall cannot be checked, so an RPM-only
deficit there would refute ACTUATION/mechanical. The claim is context: the
report shows it, no symptom reads it.

**The power gate on PHYSICAL_EFFECT NOMINAL** (XSYS-001's
`compensation_witness`). "No compensation" is affirmed only where the motor's
telemetry reports a deficit L large enough that a genuine loss would have
produced a compensation of at least 2 theta: 1 / (1 - L) - 1 >= 2 theta.
Without such a deficit there is nothing to test, and the record is
NOT_APPLICABLE.

**Thresholds** come from `stock_calibration.json`: apparatus data only,
frozen before any XSYS-001 evaluation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState

from .. import stock_stats as SS
from ..envelope import EvidenceEnvelope
from ..health import ProducerHealth
from ..lineage import Lineage
from ..profiles import multirotor_quad as Q

EVENT = "stock.event"
PRODUCER_VERSION = "csia-2.3-stock-r1"
CONTRACT_VERSION = "stock-1"
CALIBRATION = Path(__file__).resolve().parents[1] / "stock_calibration.json"
CHECKPOINTS = {"T1": 0.2, "EARLY": 2.0, "AFTER": 15.0}

COMP, TEL, DYN, ALLOC, BAT = ("px4:allocator.compensation", "px4:esc.telemetry_response",
                              "px4:vehicle.rate_transient", "px4:allocator.status",
                              "px4:battery.status")
CONTRACT_FILES = ("stock_allocator_compensation", "stock_esc_telemetry_response",
                  "stock_vehicle_rate_transient", "stock_allocator_status",
                  "stock_battery_status")

MOTOR_DEPS = ("POWER/battery", "COMPUTE/control_allocator")
MOTOR_FNS = ("PROPULSION", "AUTONOMOUS_MISSION")
ALL_FNS = tuple(f.name for f in Q.FUNCTIONS)


def load_calibration(path=CALIBRATION) -> dict:
    return json.loads(Path(path).read_text())


def _rec(domain, component, relation, source, state, app, *, codes=(), measured=None,
         expected=None, expected_relation=None, deps=(), fns=(), attributable=True,
         detail=None, t=None):
    return EvidenceRecord(
        domain=domain, component=component, relation=relation, source=source,
        observation_state=state, applicability=app, affected_functions=tuple(fns),
        reason_codes=tuple(codes), measured_value=measured, expected_value=expected,
        expected_relation=expected_relation, dependencies=tuple(deps),
        attributable=attributable, detail=detail or {}, timestamp_processed=t)


def _num(x):
    return float(x) if x is not None and math.isfinite(x) else None


class StockProducers:
    """Event-relative stock evidence for one log (already decimated to the
    stock rates), and one IMU lineage root."""

    def __init__(self, log, imu_root: str = "sensor:imu.unknown", calibration=None):
        self.log = log
        self.cal = (calibration or load_calibration())["calibration"]
        self.imu = imu_root
        self.ms = SS.motor_series(log)
        self.n = log.n_motors

    # ------------------------------------------------------------ coverage
    def coverage_notices(self) -> list:
        out = []
        if self.ms is None:
            out.append({"producer_id": COMP, "source": "ACTUATION/motor_*", "available": False,
                        "why": "actuator_motors or esc_status missing, or CA_ROTOR_COUNT < 2"})
        es = self.log.topics.get("esc_status", {})
        if not any(np.any(es.get(f"esc[{m}].esc_current", np.zeros(1)) != 0) for m in range(self.n)):
            out.append({"producer_id": TEL, "source": "ACTUATION/motor_*:actuation.electrical_response",
                        "available": False,
                        "why": "esc_status carries no ESC current: the electrical response and "
                               "the stall signature cannot be judged (SB-1)"})
        b = self.log.topics.get("battery_status")
        if b is None or not np.any(np.asarray(b.get("current_a", [-1])) >= 0):
            out.append({"producer_id": BAT, "source": "POWER/battery:power.droop_vs_current",
                        "available": False,
                        "why": "battery current not measured (battery_status.current_a = -1)"})
        return out

    # ------------------------------------------------------------ envelopes
    def at(self, t0: float, checkpoint: str) -> list:
        """The outputs whose content ends by event + CHECKPOINTS[checkpoint]."""
        tc = t0 + CHECKPOINTS[checkpoint]
        out = []
        if checkpoint == "T1":
            out += self._rate(t0, tc)
        if checkpoint in ("EARLY", "AFTER") and self.ms is not None:
            ch = SS.event_changes(self.ms, t0)
            w = checkpoint
            out += self._telemetry(ch, w, tc)
            if w == "AFTER":
                out += self._compensation(ch, tc)
            out += self._allocation(t0, w, tc)
        out += self._battery(tc)
        return out

    def _env(self, pid, claim, rec, lineage, content_t, produced_t, health=ProducerHealth.VALID,
             detail=None):
        return EvidenceEnvelope(producer_id=pid, producer_version=PRODUCER_VERSION,
                                contract_version=CONTRACT_VERSION, claim=claim, record=rec,
                                lineage=lineage, content_time=round(content_t, 6),
                                producer_health=health, produced_time=round(produced_t, 6),
                                detail=detail or {})

    def _cmd_roots(self):
        return [f"channel:motor_command.motor_{j}" for j in range(self.n)]

    def _telemetry(self, ch, w, tc):
        th = self.cal["theta_tel"]
        lin = Lineage.of(*[f"channel:esc_rpm.motor_{j}" for j in range(self.n)], *self._cmd_roots())
        out = []
        for m in range(self.n):
            L, n = ch[f"L_tel_{w}"][m], min(ch["n_before"][m], ch[f"n_{w}"][m])
            if n < 10 or not math.isfinite(L):
                st, app, codes = (ObservationState.UNAVAILABLE, Applicability.INPUTS_MISSING,
                                  ("NOT_MEASURABLE_IN_FLIGHT_WINDOWS",))
            elif L >= th:
                st, app, codes = ObservationState.DEGRADED, Applicability.APPLICABLE, ("ESC_TELEMETRY_DEFICIT",)
            elif L <= -th:
                st, app, codes = ObservationState.DEGRADED, Applicability.APPLICABLE, ("ESC_TELEMETRY_EXCESS",)
            else:
                st, app, codes = ObservationState.NOMINAL, Applicability.APPLICABLE, ()
            rec = _rec("ACTUATION", f"motor_{m}", "esc.telemetry_response", TEL, st, app,
                       codes=codes, measured=_num(L), expected=0.0,
                       expected_relation=f"implied thrust deficit from ESC RPM within +/-{th:.4g}",
                       deps=MOTOR_DEPS, fns=MOTOR_FNS, attributable=False, t=tc,
                       detail={"unit": "fraction of commanded thrust", "window": w, "samples": n,
                               "threshold": th})
            out.append(self._env(TEL, "TELEMETRY_RESPONSE", rec, lin, tc, tc))
        return out

    def _compensation(self, ch, tc):
        th, tht = self.cal["theta_ctrl"], self.cal["theta_tel"]
        lin = Lineage.of(*self._cmd_roots(), self.imu, "model:ekf2", "model:px4_rate_controller",
                         "model:px4_control_allocator")
        sat = self._saturated(tc - 5.0, tc) if self.log.has("control_allocator_status") else False
        out = []
        for m in range(self.n):
            C, n = ch["C_AFTER"][m], min(ch["n_before"][m], ch["n_AFTER"][m])
            L = ch["L_tel_AFTER"][m]
            gate = (1.0 / (1.0 - L) - 1.0) if math.isfinite(L) and L < 1.0 else float("nan")
            detail = {"unit": "compensation ratio change (1/eta - 1 for a compensated loss)",
                      "window": "AFTER", "samples": n, "threshold": th,
                      "telemetry_deficit_L": _num(L), "expected_if_genuine": _num(gate)}
            if n < 10 or not math.isfinite(C) or sat:
                st, app = ObservationState.UNAVAILABLE, Applicability.INPUTS_MISSING
                codes = ("ALLOCATOR_SATURATED",) if sat else ("NOT_MEASURABLE_IN_FLIGHT_WINDOWS",)
            elif C >= th:
                st, app, codes = ObservationState.VIOLATED, Applicability.APPLICABLE, ("ACT_NO_PHYSICAL_RESPONSE",)
            elif C <= -th or not (math.isfinite(L) and L >= tht):
                # the opposite direction is explained by no single-motor loss;
                # no local deficit means nothing to test
                st, app = ObservationState.NOT_APPLICABLE, Applicability.NOT_APPLICABLE
                codes = ("NO_LOCAL_DEFICIT_TO_TEST",) if C > -th else ("COMPENSATION_OPPOSITE",)
            elif gate >= 2.0 * th:
                st, app, codes = ObservationState.NOMINAL, Applicability.APPLICABLE, ()
            else:
                st, app, codes = (ObservationState.UNAVAILABLE, Applicability.INPUTS_MISSING,
                                  ("REPORTED_DEFICIT_TOO_SMALL_TO_TEST",))
            rec = _rec("ACTUATION", f"motor_{m}", "actuation.physical_response", COMP, st, app,
                       codes=codes, measured=_num(C), expected=0.0,
                       expected_relation=f"compensation change below {th:.4g}",
                       deps=MOTOR_DEPS, fns=MOTOR_FNS, attributable=True, t=tc, detail=detail)
            out.append(self._env(COMP, "PHYSICAL_EFFECT", rec, lin, tc, tc))
        return out

    def _saturated(self, a, b):
        ca = self.log.topics["control_allocator_status"]
        msk = (ca["t"] >= a) & (ca["t"] < b)
        if not msk.any():
            return False
        sat = np.stack([ca.get(f"actuator_saturation[{m}]", np.zeros(len(ca["t"])))
                        for m in range(self.n)], 1)[msk]
        return bool((sat != 0).mean() > 0.5)

    def _allocation(self, t0, w, tc):
        if not self.log.has("control_allocator_status"):
            return []
        ca = self.log.topics["control_allocator_status"]
        a, b = SS.WINDOWS[w]
        msk = (ca["t"] >= t0 + a) & (ca["t"] < t0 + b)
        if not msk.any():
            st, app, codes, frac = (ObservationState.UNAVAILABLE, Applicability.INPUTS_MISSING,
                                    ("NO_SAMPLES",), None)
        else:
            not_ach = float(np.mean((ca["torque_setpoint_achieved"][msk] == 0)
                                    | (ca["thrust_setpoint_achieved"][msk] == 0)))
            sat = np.stack([ca.get(f"actuator_saturation[{m}]", np.zeros(len(ca["t"])))
                            for m in range(self.n)], 1)[msk]
            frac = max(not_ach, float((sat != 0).any(axis=1).mean()))
            bad = frac > 0.5
            st = ObservationState.DEGRADED if bad else ObservationState.NOMINAL
            app, codes = Applicability.APPLICABLE, (("ALLOCATION_NOT_ACHIEVED",) if bad else ())
        rec = _rec("COMPUTE", "control_allocator", "allocation.authority", ALLOC, st, app,
                   codes=codes, measured=frac, expected=0.0,
                   expected_relation="torque and thrust setpoints achieved, no actuator saturated, "
                                     "for most of the window",
                   attributable=False, t=tc,
                   detail={"unit": "fraction of window samples not achieved or saturated",
                           "window": w})
        lin = Lineage.of("model:px4_control_allocator", *self._cmd_roots())
        return [self._env(ALLOC, "AUTHORITY", rec, lin, tc, tc)]

    def _rate(self, t0, tc):
        th = self.cal["theta_dyn"]
        out = []
        lin = Lineage.of(self.imu, "calibration:rotor_geometry")
        for m in range(self.n):
            D, n = SS.rate_transient(self.log, t0, m)
            if not n or not math.isfinite(D):
                st, app, codes = (ObservationState.UNAVAILABLE, Applicability.INPUTS_MISSING,
                                  ("NOT_MEASURABLE",))
            elif D >= th:
                st, app, codes = ObservationState.DEGRADED, Applicability.APPLICABLE, ("RATE_RESPONSE_ON_LOSS_AXIS",)
            elif D <= -th:
                # a response OPPOSITE to this motor's loss axis is explained by no
                # loss on this motor (XSYS-001's dynamics_witness: None)
                st, app, codes = (ObservationState.NOT_APPLICABLE, Applicability.NOT_APPLICABLE,
                                  ("RESPONSE_OPPOSITE_TO_LOSS_AXIS",))
            else:
                st, app, codes = ObservationState.NOMINAL, Applicability.APPLICABLE, ()
            rec = _rec("ACTUATION", f"motor_{m}", "vehicle.rate_transient", DYN, st, app,
                       codes=codes, measured=_num(D), expected=0.0,
                       expected_relation=f"body-rate change on the loss axis below {th:.4g} rad/s",
                       deps=MOTOR_DEPS, fns=MOTOR_FNS, attributable=False, t=tc,
                       detail={"unit": "rad/s", "window": "event + [0, 0.2] s", "samples": n,
                               "threshold": th})
            out.append(self._env(DYN, "RATE_TRANSIENT", rec, lin, tc, tc))
        return out

    def _battery(self, tc):
        if not self.log.has("battery_status"):
            return []
        b = self.log.topics["battery_status"]
        i = int(np.searchsorted(b["t"], tc, side="right")) - 1
        if i < 0:
            return []
        ts = float(b["t"][i])
        v, cur = float(b["voltage_v"][i]), float(b["current_a"][i])
        warn, conn = int(b["warning"][i]), float(b["connected"][i]) > 0.5
        lin = Lineage.of("sensor:battery.0")
        if not conn or not math.isfinite(v):
            st, app, codes = (ObservationState.UNAVAILABLE, Applicability.INPUTS_MISSING,
                              ("POWER_TELEMETRY_MISSING",))
        elif cur < 0:
            st, app, codes = (ObservationState.UNAVAILABLE, Applicability.INPUTS_MISSING,
                              ("BATTERY_CURRENT_NOT_MEASURED",))
        else:
            st, app, codes = ObservationState.NOMINAL, Applicability.APPLICABLE, ()
        health = _rec("POWER", "battery", "power.source_health", BAT, st, app, codes=codes,
                      measured=v, expected_relation="battery voltage and current present and readable "
                                                    "(v2 power.source_health)",
                      fns=ALL_FNS, attributable=True, t=ts,
                      detail={"unit": "V", "current_a": cur if cur >= 0 else None})
        n_cells = self.log.params.get("BAT1_N_CELLS")
        v_empty = self.log.params.get("BAT1_V_EMPTY")
        floor = (float(n_cells) * float(v_empty)) if n_cells and v_empty else None
        low = warn >= 1 or (floor is not None and v < floor)
        wst = ObservationState.DEGRADED if low else ObservationState.NOMINAL
        wrec = _rec("POWER", "battery", "power.battery_warning", BAT, wst, Applicability.APPLICABLE,
                    codes=(("BATTERY_WARNING",) if low else ()), measured=v, expected=floor,
                    expected_relation="no PX4 battery warning and voltage above cells x BAT1_V_EMPTY",
                    attributable=False, t=ts,
                    detail={"unit": "V", "px4_warning": warn, "floor_v": floor})
        return [self._env(BAT, "SOURCE_TELEMETRY", health, lin, ts, tc),
                self._env(BAT, "WARNING", wrec, lin, ts, tc)]


# ------------------------------------------------------------------ contracts
def contracts_dict() -> dict:
    """The five stock contracts, as written to `contracts/`."""
    base = {"schema": "csia.evidence_contract/1", "producer_version": PRODUCER_VERSION,
            "contract_version": CONTRACT_VERSION, "health_reporting": "IN_PROCESS",
            "lineage": "PER_OUTPUT", "profile_compatibility": [Q.BASE],
            "update": {"mode": "SAMPLE_AND_HOLD", "period_s": None},
            "expected_inputs": ["a PX4 ULog with the stock topics (stock_log.py)",
                                "a discovered event (events.py)"],
            "fault_behavior": "a statistic that cannot be computed is UNAVAILABLE "
                              "(INPUTS_MISSING), never NOMINAL"}
    claims_ref = "research/csia_2_3_stock_bridge/CLAIMS.json"
    out = {
        "stock_allocator_compensation": dict(base, producer_id=COMP, claims={
            "PHYSICAL_EFFECT": {
                "domain": "ACTUATION", "relation": "actuation.physical_response",
                "attributable": True,
                "meaning": "the closed loop commands motor m more than the other motors after the "
                           "event than before it (VIOLATED: the motor lost physical effect), or, "
                           "where the motor's telemetry reports a deficit large enough to be tested, "
                           "does not (NOMINAL). NOT_APPLICABLE with nothing to test; UNAVAILABLE "
                           "when not measurable or saturated. Cannot say which stage of the "
                           "propulsion chain failed"}},
            validity={"event_window_s": [10.0, 15.0], "relative_to": EVENT},
            validity_rule="XSYS-001's validated T3 window for the same statistic (CTRL_T3)",
            lineage_rule=["channel:motor_command.motor_<all>", "sensor:imu.<device>",
                          "model:ekf2", "model:px4_rate_controller", "model:px4_control_allocator"],
            configuration_assumptions=["IMU_GYRO_DNF_EN without the ESC-RPM bit",
                                       "constant payload", "no saturation"],
            claim_register=claims_ref + "#ALLOCATOR_COMPENSATION"),
        "stock_esc_telemetry_response": dict(base, producer_id=TEL, claims={
            "TELEMETRY_RESPONSE": {
                "domain": "ACTUATION", "relation": "esc.telemetry_response", "attributable": False,
                "meaning": "the ESC-reported rotor speed per unit commanded thrust of motor m, "
                           "against the other motors, changed after the event (DEGRADED) or not "
                           "(NOMINAL). Context: no symptom reads it (finding SB-1)"}},
            validity={"event_window_s": [0.5, 15.0], "relative_to": EVENT},
            validity_rule="the EARLY and AFTER windows",
            lineage_rule=["channel:esc_rpm.motor_<all>", "channel:motor_command.motor_<all>"],
            configuration_assumptions=["identical rotors", "THR_MDL_FAC matches the propulsion"],
            claim_register=claims_ref + "#ESC_TELEMETRY_RESPONSE"),
        "stock_vehicle_rate_transient": dict(base, producer_id=DYN, claims={
            "RATE_TRANSIENT": {
                "domain": "ACTUATION", "relation": "vehicle.rate_transient", "attributable": False,
                "meaning": "roll and pitch rate in the first 0.2 s after the event, projected on "
                           "motor m's thrust-loss axis, against before. Context; valid only when "
                           "the event time is accurate to a fraction of 0.2 s"}},
            validity={"event_window_s": [0.0, 0.2], "relative_to": EVENT},
            validity_rule="XSYS-001's validated T1 window (W_DYN)",
            lineage_rule=["sensor:imu.<device>", "calibration:rotor_geometry"],
            claim_register=claims_ref + "#VEHICLE_RATE_TRANSIENT"),
        "stock_allocator_status": dict(base, producer_id=ALLOC, claims={
            "AUTHORITY": {
                "domain": "COMPUTE", "relation": "allocation.authority", "attributable": False,
                "nominal_means": "NO_ANOMALY",
                "meaning": "PX4's control allocator reported its torque or thrust setpoint not "
                           "achieved, or an actuator saturated, for most of the window "
                           "(DEGRADED); otherwise silent (NO_ANOMALY). Context"}},
            validity={"event_window_s": [0.5, 15.0], "relative_to": EVENT},
            validity_rule="the EARLY and AFTER windows",
            lineage_rule=["model:px4_control_allocator", "channel:motor_command.motor_<all>"],
            claim_register=claims_ref + "#ALLOCATION_STATUS"),
        "stock_battery_status": dict(base, producer_id=BAT, claims={
            "SOURCE_TELEMETRY": {
                "domain": "POWER", "relation": "power.source_health", "attributable": True,
                "meaning": "v2's power.source_health: battery voltage AND current present and "
                           "readable (NOMINAL); UNAVAILABLE when current is not measured "
                           "(current_a = -1), because v2 does not exonerate what it cannot see"},
            "WARNING": {
                "domain": "POWER", "relation": "power.battery_warning", "attributable": False,
                "nominal_means": "NO_ANOMALY",
                "meaning": "PX4's battery warning level, or voltage below cells x BAT1_V_EMPTY "
                           "(DEGRADED); otherwise silent (NO_ANOMALY). Context"}},
            validity={"max_content_age_s": 1.0},
            validity_rule="battery_status is logged at 5 Hz by default",
            lineage_rule=["sensor:battery.<instance>"],
            claim_register=claims_ref + "#BATTERY_SOURCE_STATUS"),
    }
    return out
