#!/usr/bin/env python3
"""PRIME-1 Phase 8: the RPM-telemetry perturbation matrix. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/telemetry_matrix.py [--bases dev|heldout]

**What it does.** A nominal SITL flight with a healthy motor_2; its logged ESC
telemetry is changed offline from `T_ON` s after log start, one kind at a time;
the unchanged product path (`runs.stock_flight`, both releases) analyses it.
OFFLINE CORRUPTION OF SITL LOGS: no claim about real ESCs follows from it.

**Bases:**
- `dev` (in-sample; development only): RB-001 CAL1 (hover) and 2.3 V5
  (maneuvering);
- `heldout`: the PRIME-1 held-out nominal flights HN1 (hover) and HN4
  (maneuvering), used only by the frozen evaluation (`heldout_eval.py`).

**The expected outcome of every kind is written down here, before any run, from
the signal's physics, not from the product** (`EXPECTED`). Not every kind is
expected to open an event: a change the telemetry statistic cannot see is a
stated blind spot, not a failure, as long as nothing false is concluded.

Writes TELEMETRY_MATRIX_<bases>.json.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import common_prime1 as C

from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs
from csia_evidence_assurance.stock_log import StockLog

MOTOR = 2
T_ON = 80.0
WINDOW = (-1.0, 2.0)
KINDS = ("x0.1", "x0.5", "x0.78", "x0.95", "x1.05", "x1.2", "x2", "x10", "offset_static_plus_1000rpm",
         "drift_0.5pct_per_s", "step_up_500rpm", "step_down_500rpm", "dropout_10s", "stuck",
         "zero_while_offline")
#: Expected outcome per kind (fixed before running). event: the telemetry event the
#: discovery must open within WINDOW of T_ON ("deficit", "excess", "offline", None = no
#: requirement, "none" = must not be required and any is allowed); state: the telemetry
#: output expected at that event. Every kind: no motor symptom (the motor is healthy).
EXPECTED = {
    "x0.1": ("deficit", "DEGRADED"), "x0.5": ("deficit", "DEGRADED"), "x0.78": ("deficit", "DEGRADED"),
    "x0.95": ("deficit", "DEGRADED"),
    "x1.05": ("excess", "DEGRADED"), "x1.2": ("excess", "DEGRADED"), "x2": ("excess", "DEGRADED"),
    "x10": ("excess", "DEGRADED"),
    "offset_static_plus_1000rpm": (None, None),      # no change after the start: a blind spot of a change detector
    "drift_0.5pct_per_s": (None, None),               # slower than the trailing reference: may or may not open
    "step_up_500rpm": ("excess", "DEGRADED"), "step_down_500rpm": ("deficit", "DEGRADED"),
    "dropout_10s": (None, None),                      # no samples: a log gap, never a measurement
    "stuck": (None, None),                            # frozen value: visible only if the command moves
    "zero_while_offline": ("offline", "UNAVAILABLE"),  # PX4 reports the ESC offline
}
KIND_OF_TRIGGER = {"deficit": {"propulsion.rpm_deficit"}, "excess": {"propulsion.rpm_excess"},
                   "offline": {"px4.esc_offline"}}


def perturb(log: StockLog, kind: str) -> StockLog:
    log = copy.deepcopy(log)
    es = log.topics["esc_status"]
    t = es["t"]
    f = f"esc[{MOTOR}].esc_rpm"
    rpm = es[f].astype(float)
    on = t >= T_ON
    if kind.startswith("x"):
        rpm[on] *= float(kind[1:])
    elif kind == "offset_static_plus_1000rpm":
        rpm = rpm + 1000.0 * (rpm > 0)
    elif kind == "drift_0.5pct_per_s":
        rpm[on] *= 1.0 + 0.005 * (t[on] - T_ON)
    elif kind == "step_up_500rpm":
        rpm[on] += 500.0
    elif kind == "step_down_500rpm":
        rpm[on] -= 500.0
    elif kind == "stuck":
        i = int(np.searchsorted(t, T_ON)) - 1
        rpm[on] = rpm[max(i, 0)]
    elif kind == "zero_while_offline":
        rpm[on] = 0.0
        flags = es["esc_online_flags"].astype(np.int64)
        flags[on] &= ~(1 << MOTOR)
        es["esc_online_flags"] = flags.astype(float)
    elif kind == "dropout_10s":
        keep = ~((t >= T_ON) & (t < T_ON + 10.0))
        log.topics["esc_status"] = {k: v[keep] for k, v in es.items()}
        return log
    else:
        raise ValueError(kind)
    es[f] = rpm
    return log


def analyse(log, release):
    run = runs.stock_flight(stock_log=log, est_log=None, release=release)
    return RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)


def score(m, kind) -> dict:
    exp_event, exp_state = EXPECTED[kind]
    syms = sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]})
    near = [e for e in m["events"] if T_ON + WINDOW[0] <= e["t0"] <= T_ON + WINDOW[1]]
    kinds_near = sorted({k for e in near for k in e["trigger_kinds"]})
    tel = sorted({(v["window"], v["state"], ",".join(v["reason_codes"]))
                  for v in m["evidence_values"]
                  if v["record"] == f"ACTUATION/motor_{MOTOR}:esc.telemetry_response"
                  and near and abs(v["t"] - (near[0]["t0"] + 15.0)) < 1e-6})
    event_ok = (True if exp_event is None else bool(set(kinds_near) & KIND_OF_TRIGGER[exp_event]))
    state_ok = (True if exp_state is None or not near else any(s == exp_state for _w, s, _c in tel))
    return {"events": [{"t0": e["t0"], "kinds": e["trigger_kinds"]} for e in m["events"]],
            "kinds_near_onset": kinds_near, "telemetry_after_at_event": [list(x) for x in tel],
            "symptoms": syms, "attribution": m["summary"]["attribution"]["verdict"],
            "expected_event": exp_event, "expected_state": exp_state,
            "event_as_expected": event_ok, "state_as_expected": state_ok,
            "no_motor_symptom": not syms, "pass": event_ok and state_ok and not syms}


def one(args):
    base, kind, release = args
    log = StockLog.from_ulog(base)
    return {"base": base.stem, "kind": kind, "release": release, **score(analyse(perturb(log, kind), release), kind)}


def bases(which):
    if which == "dev":
        return [C.SITL_RB001 / "CAL1.ulg", C.SITL_2_3 / "V5.ulg"]
    return [C.OUT_RAW / "heldout" / "HN1.ulg", C.OUT_RAW / "heldout" / "HN4.ulg"]


def run_matrix(which: str, releases=("2.3", "prime1"), workers: int = 4) -> dict:
    jobs = [(b, k, r) for b in bases(which) for k in KINDS for r in releases]
    with ProcessPoolExecutor(workers) as ex:
        rows = list(ex.map(one, jobs))
    summary = {}
    for r in releases:
        sel = [x for x in rows if x["release"] == r]
        summary[r] = {"cases": len(sel), "pass": sum(x["pass"] for x in sel),
                      "failed": [f"{x['base']}:{x['kind']}" for x in sel if not x["pass"]],
                      "motor_symptoms": [f"{x['base']}:{x['kind']}" for x in sel if x["symptoms"]]}
    return {"label": f"PRIME-1 telemetry matrix, {which} bases; SITL + OFFLINE CORRUPTION",
            "motor": MOTOR, "t_on_s": T_ON, "window_s": list(WINDOW),
            "expected": {k: list(v) for k, v in EXPECTED.items()}, "rows": rows, "summary": summary}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", choices=("dev", "heldout"), default="dev")
    a = ap.parse_args()
    out = run_matrix(a.bases)
    C.write_json(C.HERE / f"TELEMETRY_MATRIX_{a.bases.upper()}.json", out)
    print(json.dumps(out["summary"], indent=1))
    for x in out["rows"]:
        if x["release"] == "prime1":
            print(x["base"], x["kind"], x["kinds_near_onset"], x["telemetry_after_at_event"][:2], x["symptoms"], x["pass"])


if __name__ == "__main__":
    sys.exit(main())
