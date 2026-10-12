"""Validate the component relations against the component simulator.

WHAT "VALIDATE" MEANS HERE, AND WHAT IT DOES NOT
-------------------------------------------------
Four questions per relation, each measurable:

    RESPONDS      at what magnitude does the fault it claims to catch rise
                  above this platform's own clean-run noise? That is a
                  DETECTION FLOOR, not a yes/no.
    QUIET         on clean runs, how far does the residual wander? A
                  relation whose clean spread overlaps its fault response
                  has no usable threshold and is reported as such.
    GATES         outside its declared gate, does it contribute ZERO? A gate
                  that merely down-weights is not a gate.
    BLIND         the fault it declared itself blind to -- does it in fact
                  miss it? THIS IS THE PREDICTION TEST.

THE PREDICTIONS WERE COMMITTED BEFORE THE SIMULATOR EXISTED. Every
`gate`, `blames` and `blind_to` in `csia_components/catalog.py` was written
on 2026-09-11 with no component simulator in the repository (MX-035). Running
them against a simulator written afterwards is a test of statements made in
advance, which is the one thing that keeps this from being a detector finding
what its own author generated.

IT DOES NOT REMOVE THE CIRCULARITY, IT BOUNDS IT. The simulator and the
residuals were written by the same author in the same week. A relation
passing here has been shown consistent with a model of the physics, not with
any vehicle. `csia_components/simulate.py` states the same thing at greater
length and it is the first thing to read before quoting a floor from here.

THE CROSS-RELATION MATRIX IS THE PART THAT IS HARDEST TO FAKE
--------------------------------------------------------------
Every fault is run against EVERY relation, not only the one it was meant to
exercise. A relation that lights up on a fault it has no physical business
seeing is a false-positive source, and one that stays dark on a fault two
other relations catch is a coverage gap. Neither is visible when each
relation is tested only against its own fault.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_components import RELATIONS, relation                   # noqa: E402
from csia_components import residuals as R                        # noqa: E402
from csia_components import simulate as S                         # noqa: E402

INSTRUMENT = "tools.research.component_validation"

SEEDS = (0, 100, 200, 300, 400)
#: HELD OUT. `effort_drift` needs the effort this platform requires when
#: healthy, and taking it from the run being scored makes the clean residual
#: identically zero -- so every fault "detects" and the floor is meaningless.
#: That is the same train-on-test error MX-030 had to fix on the predictor
#: side, and it appeared here on the first run. The reference now comes from
#: a seed that appears in no scored run.
REFERENCE_SEED = 999
DURATION = 60.0
ONSET, FAULT_LEN = 20.0, 30.0
#: Scored window: after the fault has taken hold and before it clears. The
#: thermal time constant is 25 s, so a window starting 5 s after onset is
#: INSIDE the settling time for the thermal relation -- which is exactly
#: what that relation's gate is for, and the gate is tested rather than
#: worked around by moving the window.
WIN_LO, WIN_HI = ONSET + 5.0, ONSET + FAULT_LEN

#: Magnitude grids, in each fault kind's own physical units. Spanning well
#: below and well above, so a floor is bracketed rather than assumed.
GRIDS = {
    "esc_efficiency_loss": (0.005, 0.01, 0.03, 0.08, 0.20, 0.40),
    "bearing_friction": (0.02, 0.05, 0.15, 0.40, 1.00, 2.50),
    "pack_impedance_rise": (0.002, 0.005, 0.015, 0.040, 0.100, 0.250),
    "shunt_bias": (0.002, 0.005, 0.015, 0.040, 0.100, 0.250),
    "thermal_path_loss": (0.02, 0.05, 0.15, 0.40, 1.00, 2.50),
    "cpu_overrun": (0.00005, 0.0002, 0.0008, 0.003, 0.010, 0.030),
    "bus_drops": (0.002, 0.005, 0.02, 0.06, 0.15, 0.40),
}


def _config(clean_reference):
    """Nominals each relation needs, from the platform's own specification.

    On a real vehicle these come from a datasheet or a commissioning run.
    `reference_effort` is the one that MUST come from a clean run -- it is
    the effort this platform needs when healthy, and there is no way to
    derive it from the run being checked.
    """
    return {
        "power_balance": {"quiescent_a": S.QUIESCENT_A},
        "source_impedance": {"r_nominal": S.PACK_R_NOMINAL},
        "charge_accounting": {"capacity_ah": S.PACK_CAPACITY_AH},
        "actuator_response": {"k_thrust": S.K_THRUST, "mass_kg": S.MASS_KG},
        "actuator_agreement": {},
        "effort_drift": {"reference_effort": clean_reference},
        "loop_rate": {"nominal_period": 1.0 / S.LOOP_HZ},
        "bus_rate": {"nominal_hz": S.LOOP_HZ},
        "clock_agreement": {"specified_drift_rate": 1.5e-6},
        "thermal_rise": {"thermal_k": S.THERMAL_K, "esc_r": S.ESC_R,
                         "motor": 1, "settle_s": S.THERMAL_TAU,
                         "fault_free_change_at": None},
        "sequence_continuity": {},
        "error_rate": {"baseline_rate": 0.0},
    }


def _residual(key, tel, cfg):
    fn = R.RESIDUALS[key]
    return fn(tel, WIN_LO, WIN_HI, **cfg[key])


def _clean_reference(seed=REFERENCE_SEED):
    """Effort on a HELD-OUT clean run. See REFERENCE_SEED."""
    tel = S.Platform(seed=seed, duration=DURATION).run()
    duty = np.asarray(tel.duty, dtype=float)
    win = (tel.array("t") >= WIN_LO) & (tel.array("t") <= WIN_HI)
    return float(np.mean(duty[win]))


def run() -> dict:
    keys = sorted(R.RESIDUALS)

    # ---- clean baseline: what does each residual do with NO fault? --------
    clean = {k: [] for k in keys}
    for seed in SEEDS:
        ref = _clean_reference()
        cfg = _config(ref)
        tel = S.Platform(seed=seed, duration=DURATION).run()
        for k in keys:
            value, gate = _residual(k, tel, cfg)
            if gate > 0:
                clean[k].append(abs(value))
    baseline = {
        k: {"n": len(v),
            "clean_abs_mean": statistics.fmean(v) if v else None,
            "clean_abs_max": max(v) if v else None,
            "gated_out_on_clean": len(v) == 0,
            # A RESIDUAL THAT IS EXACTLY ZERO ON EVERY CLEAN RUN HAS NO
            # NOISE FLOOR, so "exceeds the clean maximum" degenerates to
            # "is not zero" and the ratio is undefined. Sometimes that is
            # honest -- a link with no dropped frames really does have zero
            # gaps -- and sometimes it means the reference was fitted to the
            # run being scored, which is what happened to `effort_drift`
            # before REFERENCE_SEED existed. Either way a reader must see it.
            "clean_is_identically_zero": bool(v) and max(v) == 0.0}
        for k, v in clean.items()}

    # ---- every fault, every magnitude, against EVERY relation -------------
    grid_rows = []
    for node, kind in S.applicable_faults():
        for magnitude in GRIDS[kind]:
            per_relation = {k: [] for k in keys}
            gates = {k: [] for k in keys}
            for seed in SEEDS:
                ref = _clean_reference()
                cfg = _config(ref)
                fault = S.Fault(kind, node, ONSET, FAULT_LEN, magnitude)
                tel = S.Platform(seed=seed, duration=DURATION).run((fault,))
                for k in keys:
                    value, gate = _residual(k, tel, cfg)
                    gates[k].append(gate)
                    if gate > 0:
                        per_relation[k].append(abs(value))
            row = {"node": node, "kind": kind, "magnitude": magnitude,
                   "relations": {}}
            for k in keys:
                vals = per_relation[k]
                base = baseline[k]["clean_abs_max"]
                mean = statistics.fmean(vals) if vals else None
                zero_clean = baseline[k]["clean_is_identically_zero"]
                row["relations"][k] = {
                    "gate_mean": statistics.fmean(gates[k]),
                    "abs_mean": mean,
                    "against_zero_clean_baseline": zero_clean,
                    # DETECTED means the fault response clears the WORST
                    # clean excursion, not the average one. A threshold
                    # placed at the mean would fire on clean flights.
                    "detected": bool(vals and base is not None
                                     and mean > base),
                    "ratio_to_clean_max": (mean / base if (mean is not None
                                                           and base)
                                           else None),
                }
            grid_rows.append(row)

    floors = _floors(grid_rows, keys)
    return {
        "schema": "csia.components.validation/1",
        "platform": "four-rotor electric, closed-loop vertical velocity",
        "seeds": list(SEEDS),
        "scored_window_s": [WIN_LO, WIN_HI],
        "relations_with_a_residual": len(keys),
        "relations_without_one": R.NOT_IMPLEMENTED,
        "clean_baseline": baseline,
        "relations_with_zero_clean_baseline": sorted(
            k for k, v in baseline.items()
            if v["clean_is_identically_zero"]),
        "zero_clean_note": (
            "For these, 'exceeds the clean maximum' degenerates to 'is not "
            "zero' and the ratio is undefined. A detection against a zero "
            "baseline is a weaker statement than one against a measured "
            "noise floor and is flagged per row."),
        "detection_floors": floors,
        "grid": grid_rows,
        "cross_relation": _cross(grid_rows, keys),
        "predictions": _predictions(grid_rows, floors),
        "what_this_is_not": (
            "A simulator written by the same author as the residuals, in the "
            "same week. A relation passing here is consistent with a model "
            "of the physics, not with any vehicle. Every floor is a floor "
            "against SIMULATED noise, and the phenomena this simulator "
            "cannot produce are exactly the ones it cannot warn about."),
    }


def _floors(grid_rows, keys) -> dict:
    """The smallest magnitude at which each (fault, relation) pair detects."""
    out = {}
    for row in grid_rows:
        for k in keys:
            if not row["relations"][k]["detected"]:
                continue
            tag = f"{row['node']}|{row['kind']}|{k}"
            prev = out.get(tag)
            if prev is None or row["magnitude"] < prev["magnitude"]:
                out[tag] = {"magnitude": row["magnitude"],
                            "ratio_to_clean_max":
                                row["relations"][k]["ratio_to_clean_max"]}
    return out


def _cross(grid_rows, keys) -> dict:
    """Which relations respond to which faults, at ANY magnitude."""
    matrix = {}
    for row in grid_rows:
        tag = f"{row['node']}|{row['kind']}"
        hit = sorted(k for k in keys if row["relations"][k]["detected"])
        matrix.setdefault(tag, set()).update(hit)
    return {
        "responders_by_fault": {k: sorted(v) for k, v in
                                sorted(matrix.items())},
        "faults_with_no_responder": sorted(k for k, v in matrix.items()
                                           if not v),
        "note": ("a relation responding to a fault it has no physical "
                 "business seeing is a false-positive source; a fault with "
                 "no responder is a coverage gap. Neither is visible when "
                 "each relation is tested only against its own fault."),
    }


#: The catalogue's blind-spot claims, restated as testable pairs.
#: EACH WAS WRITTEN BEFORE THE SIMULATOR EXISTED (MX-035).
BLINDNESS_PREDICTIONS = (
    ("actuator_response", "esc_efficiency_loss",
     "the controller compensates, so the plant output carries no error even "
     "while the plant degrades"),
    ("power_balance", "esc_efficiency_loss",
     "the branch currents still sum to the pack current; a collective "
     "efficiency loss raises both sides together"),
    ("power_balance", "thermal_path_loss",
     "a cooling fault changes no current anywhere"),
    ("actuator_agreement", "pack_impedance_rise",
     "a pack fault is common-mode across a symmetric actuator group"),
    ("thermal_rise", "cpu_overrun",
     "a scheduling fault has no thermal signature in the ESCs"),
    ("loop_rate", "bearing_friction",
     "a mechanical fault does not stretch the control period"),
)


def _predictions(grid_rows, floors) -> dict:
    """Test the blind-spot claims. A violation is a real falsification."""
    results = []
    for rel_key, kind, why in BLINDNESS_PREDICTIONS:
        detected_at = [row["magnitude"] for row in grid_rows
                       if row["kind"] == kind
                       and row["relations"][rel_key]["detected"]]
        results.append({
            "relation": rel_key, "fault": kind,
            "predicted": "BLIND", "why_predicted": why,
            "detected_at_magnitudes": sorted(detected_at),
            "holds": not detected_at,
        })
    violated = [r for r in results if not r["holds"]]
    return {
        "checked": len(results),
        "held": len(results) - len(violated),
        "violated": len(violated),
        "violations": violated,
        "reading": ("a violated blindness prediction is a FALSIFICATION of "
                    "something written down before the simulator existed, "
                    "and the catalogue is wrong rather than the test"),
        "results": results,
    }


def _controls():
    """The campaign is worthless if the residuals cannot fail.

    POSITIVE: a large fault must move its own relation far past the clean
    spread. A residual wired to a constant would report every fault
    undetected and look like a clean null.

    NEGATIVE: a gated-out relation must return exactly zero gate. If a gate
    were a soft weight, an inapplicable check would contribute a little
    agreement and absence of evidence would become evidence of health.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _responds():
        ref = _clean_reference()
        cfg = _config(ref)
        clean = S.Platform(seed=0, duration=DURATION).run()
        fault = S.Fault("bearing_friction", "esc1", ONSET, FAULT_LEN, 2.5)
        bad = S.Platform(seed=0, duration=DURATION).run((fault,))
        c, _ = _residual("actuator_agreement", clean, cfg)
        b, _ = _residual("actuator_agreement", bad, cfg)
        return {"clean": abs(c), "faulted": abs(b)}

    def _gates_hard():
        # A manoeuvring setpoint violates `effort_drift`'s stationarity gate
        # and a constant current violates `source_impedance`'s variation
        # gate. Both must return a gate of exactly zero.
        ref = _clean_reference()
        cfg = _config(ref)
        moving = S.Platform(seed=0, duration=DURATION,
                            setpoint=lambda t: 0.4 * np.sin(t)).run()
        _, g_effort = _residual("effort_drift", moving, cfg)
        steady = S.Platform(seed=0, duration=DURATION).run()
        _, g_imp = _residual("source_impedance", steady, cfg)
        return {"effort_drift_gate_when_manoeuvring": g_effort,
                "source_impedance_gate_at_constant_load": g_imp}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a large mechanical fault moves its own relation far past "
                 "the clean spread",
            kind=POSITIVE, run=_responds,
            expect=lambda d: d["faulted"] > 10 * max(d["clean"], 1e-9),
            basis=("2.5 A of extra draw on one motor of four against a "
                   "0.05 A per-branch measurement sigma is a 50-sigma "
                   "asymmetry; arithmetic, not a property of this tool"),
        ),
        negative=Control(
            name="a relation outside its declared gate returns exactly zero",
            kind=NEGATIVE, run=_gates_hard,
            expect=lambda d: all(v == 0.0 for v in d.values()),
            basis=("catalog.py declares effort_drift gated on a stationary "
                   "operating point and source_impedance on current "
                   "variation; a sinusoidal setpoint and a constant load "
                   "violate them by construction"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    report = guard(INSTRUMENT)

    doc = stamp(run(), report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
        p = doc["predictions"]
        print(f"\nBLINDNESS PREDICTIONS: {p['held']}/{p['checked']} held, "
              f"{p['violated']} violated")
        for r in p["results"]:
            mark = "held" if r["holds"] else "VIOLATED"
            print(f"  {r['relation']:22s} vs {r['fault']:22s} {mark}"
                  + ("" if r["holds"]
                     else f"  detected at {r['detected_at_magnitudes']}"))
        print("\nDETECTION FLOORS (smallest magnitude clearing the worst "
              "clean excursion)")
        for tag, v in sorted(doc["detection_floors"].items()):
            ratio = v["ratio_to_clean_max"]
            shown = "n/a" if ratio is None else f"{ratio:.1f}x clean max"
            print(f"  {tag:52s} {v['magnitude']:>8} ({shown})")
        cross = doc["cross_relation"]
        print(f"\nFAULTS WITH NO RESPONDER: "
              f"{cross['faults_with_no_responder'] or 'none'}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
