"""Mechanism B on the current stack: reconstruct, classify, and say what the
paper is permitted to claim.

Preregistered in `research/v1_1/CURRENT_STACK_REPLICATION.md`, blob
0e186117e2dcc014862872934768e06e0a195592, committed before the first trial.

SECTION 5, THE PART THAT MATTERS. From the MEASURED S0 and T0 at onset and the
MEASURED per-tick e_k and rho_k, step the source recursion tick by tick:

    S(k) = rho(k)*S(k-1) + 1
    T(k) = ( rho(k)*S(k-1)*T(k-1) + e(k) ) / S(k)

**The closed form with a constant rho is NOT used.** The preregistration is
explicit: assuming constant forgetting is the error that invalidated the first
Phase-I derivation and is recorded as correction 9. rho is re-derived here per
tick from the observed component scores by the source formula
(engine.py:141-143) and never read from the runtime, so the reconstruction
depends on the runtime only through the observed evidence, the update gate, and
the single measured initial condition section 5 grants it.

SECTION 1, THE CRITICAL DESIGN POINT. Do not test against 93.31 ticks. That
number is specific to the Phase-I banked state S0 = 475.6775. A different
platform banks a different S0 and must cross at a different tick. What is
tested is whether the recursion, given THIS platform's measured S0 and its own
measured e_k and rho_k, predicts THIS platform's observed crossing.

  python tools/simulation/current_stack_replication.py --platform ardupilot
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "simulation"))

from mechanism_b_report import read_trace, rho_of        # noqa: E402

NODE = "gps"
THRESHOLD = 0.75                    # T*, preregistration section 1
TRAJ_TOL = 1e-6                     # section 5
CROSS_TOL_TICKS = 2                 # section 5
PREREG = "research/v1_1/CURRENT_STACK_REPLICATION.md"
PREREG_BLOB = "0e186117e2dcc014862872934768e06e0a195592"
# The GPS gate IS gvalid (online.py:518, 536). If it closes, the evidence is
# gone and the trial has become a Mechanism A trial -- section 2 voids it.
GATE_EDGE = "altitude_baro"

CONDITIONS = ("CLEAN", "STEP_SMALL", "STEP_LARGE", "RAMP_20S")
REPETITIONS = 5                     # preregistration section 3
EXPECT_CROSS = {"CLEAN": False, "STEP_SMALL": False,
                "STEP_LARGE": False, "RAMP_20S": True}


# ------------------------------------------------------------------ helpers
def gate_of(step):
    e = (step.get("edges") or {}).get(GATE_EDGE)
    return None if not e else float(e[1])


def lambda_from_c(c):
    """Invert c = exp(-0.5*max(0, lam-1)) (engine.py `consistency`).

    Returns None when c == 1.0: the map saturates there, so every lam <= 1
    gives the same c and no single value can be recovered. Reporting a number
    would be inventing precision the data does not have.
    """
    if c is None or c >= 1.0:
        return None
    if c <= 0.0:
        return float("inf")
    return 1.0 - 2.0 * math.log(c)


def reconstruct_from(steps, i0, cfg, rho_fixed=None, ignore_gate=False):
    """Section 5: step the recursion from the MEASURED S0, T0 at index i0.

    `rho_fixed` and `ignore_gate` exist only for the null controls below. The
    preregistered reconstruction uses neither.
    """
    S = steps[i0]["S_runtime"]
    T = steps[i0]["T_runtime"]
    out = []
    for i in range(i0, len(steps)):
        st = steps[i]
        if i > i0 and (ignore_gate or st["updated"]):
            rho = st["rho"] if rho_fixed is None else rho_fixed
            S_prev, T_prev = S, T
            S = rho * S_prev + 1.0
            T = (rho * S_prev * T_prev + st["e"]) / S
        row = dict(st)
        row["S_hat"], row["T_hat"] = S, T
        out.append(row)
    return out


def reconstruction_null_controls(rows, i0, cfg):
    """RULE A, turned on the reconstruction itself.

    A reconstruction fed the runtime's own measured per-tick e_k and rho_k
    SHOULD reproduce the runtime -- so agreement, on its own, could be
    tautology rather than evidence. These controls show it is not, by breaking
    one input at a time and measuring how far the trajectory then moves:

      rho_assumed_max   rho held at rho_max instead of measured per tick
      rho_assumed_min   rho held at rho_min = 0.95, the value a constant-rho
                        derivation would assume -- this is correction 9,
                        quantified on real data rather than asserted
      gate_ignored      the `avail AND fresh` update gate skipped

    If these stay near zero the controls are themselves uninformative on this
    flight, and that is reported rather than hidden: it means the flight never
    exercised the input in question.
    """
    def worst(**kw):
        rec = reconstruct_from(rows, i0, cfg, **kw)
        d = [abs(r["T_hat"] - r["T_runtime"]) for r in rec
             if not math.isnan(r["T_runtime"])]
        return float(f"{max(d):.6g}") if d else None

    gated_ticks = sum(1 for r in rows[i0:] if not r["updated"])
    return {
        "rho_assumed_max": worst(rho_fixed=cfg["rho_max"]),
        "rho_assumed_min": worst(rho_fixed=cfg["rho_min"]),
        "gate_ignored": worst(ignore_gate=True),
        "gate_closed_ticks_in_window": gated_ticks,
        "rule": "RULE A on the instrument: agreement is only evidence if "
                "breaking an input breaks the agreement",
    }


def prepare(steps, cfg):
    """Flatten the trace into per-tick rows with rho re-derived from source."""
    rows = []
    for st in steps:
        comps = (st.get("components") or {}).get(NODE)
        if comps is None:
            continue
        rho, navail = rho_of(comps, cfg["rho_max"], cfg["rho_min"])
        fresh = bool((st.get("fresh") or {}).get(NODE, True))
        S = st.get("S")
        rows.append({
            "t": st["t"],
            "e": float((st.get("evidence") or {}).get(NODE, 0.5)),
            "rho": rho,
            "fresh": fresh,
            "n_available": navail,
            "updated": bool(navail) and fresh,
            "T_runtime": float((st.get("trust") or {}).get(NODE, float("nan"))),
            "S_runtime": (None if S is None else float(S.get(NODE, float("nan")))),
            "c_phys": comps.get("phys"),
            "c_nbr": comps.get("nbr"),
            "gate_applicable": gate_of(st),
            "policy": st.get("policy"),
        })
    # S is attributable only to the last engine step of a shadow tick; carry
    # the last known value forward so the onset index always has one.
    last = None
    for r in rows:
        if r["S_runtime"] is not None and not math.isnan(r["S_runtime"]):
            last = r["S_runtime"]
        else:
            r["S_runtime"] = last
    return rows


def first_index_at_or_after(rows, t):
    return next((i for i, r in enumerate(rows) if r["t"] >= t), None)


def crossing_index(rows, i0, key):
    return next((i for i in range(i0, len(rows))
                 if rows[i][key] is not None
                 and not math.isnan(rows[i][key])
                 and rows[i][key] <= THRESHOLD), None)


def reported_offset(result):
    """RULE B: the reported GNSS position, north, and the fix-loss count.

    THERE IS NO `gnss.fix_type` CHANNEL, and it is not needed. The adapter
    refuses to publish `gnss.position` at all when `GPS_RAW_INT.fix_type < 3`,
    recording it MISSING with `NO_3D_FIX` (ardupilot.py:227). So "fix type
    unchanged from the control" is observable exactly, as the count of ticks
    where the position went missing for that reason -- and that is a stronger
    check than reading a field, because it is the quantity the trust layer
    actually gates on.
    """
    log_dir = os.path.join(ROOT, result.get("log_dir", ""))
    fid = result.get("flight_id", "")
    pts, no_fix = [], 0
    for p in sorted(glob.glob(os.path.join(log_dir, "*.jsonl"))):
        if not fid or fid not in os.path.basename(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("record") != "tick":
                    continue
                cv = ((rec.get("canonical") or {}).get("channels") or {}) \
                    .get("gnss.position") or {}
                if cv.get("usable") and isinstance(cv.get("value"), list):
                    pts.append((float(rec["t_mono"]), float(cv["value"][0])))
                elif cv.get("missing") == "NO_3D_FIX":
                    no_fix += 1
    return pts, no_fix


# ------------------------------------------------------------------ a trial
def analyse_trial(path: str, condition: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        res = json.load(fh)
    inj = res.get("injection") or {}
    out = {
        "trial": os.path.basename(path).replace(".json", ""),
        "condition": condition,
        "expectation": ("crossing" if EXPECT_CROSS[condition]
                        else "no crossing"),
        "flight_id": res.get("flight_id"),
        "command_authority": (res.get("command_authority") or {}).get("result"),
        "hold_mode": (res.get("rig_flight") or {}).get("hold_mode"),
        "hold_mode_confirmed": (res.get("rig_flight") or {}).get(
            "hold_mode_confirmed"),
        "validity_evidence": {
            "parameter": inj.get("param"),
            "readback": inj.get("readback"),
            "commanded_final": inj.get("commanded_final"),
            "readback_confirmed": inj.get("confirmed"),
            "writes": len(inj.get("schedule") or []),
            "fault_truth_source": "the injection schedule executed by the rig",
        },
    }
    trace_path = os.path.join(ROOT, res.get("trust_trace") or "")
    if not os.path.exists(trace_path):
        out["valid"] = False
        out["invalid_reason"] = "no trust trace"
        return out
    header, steps = read_trace(trace_path)
    if header is None or not steps:
        out["valid"] = False
        out["invalid_reason"] = "trace unreadable"
        return out
    cfg = header["engine_config"]
    rows = prepare(steps, cfg)
    onset_t = float(inj.get("wrote_at_rel_s") or inj.get("at_s") or 0.0)
    i0 = first_index_at_or_after(rows, onset_t)
    if i0 is None or i0 >= len(rows) - 2:
        out["valid"] = False
        out["invalid_reason"] = "onset outside the trace"
        return out
    out["onset_s"] = onset_t
    out["onset_tick"] = i0
    out["ticks"] = len(rows)

    # --- section 3 precondition: the banked state at onset
    out["S0_measured"] = rows[i0]["S_runtime"]
    out["T0_measured"] = rows[i0]["T_runtime"]

    # --- validity: gvalid must stay 1 for the WHOLE scored window
    gates = [r["gate_applicable"] for r in rows[i0:]]
    closed = sum(1 for g in gates if g is not None and g < 1.0)
    out["validity_evidence"]["gate_applicable_min"] = (
        min((g for g in gates if g is not None), default=None))
    out["validity_evidence"]["gate_closed_ticks"] = closed

    reasons = []
    if out["command_authority"] != "NO_COMMAND_PATH_REACHABLE":
        reasons.append(f"command authority {out['command_authority']}")
    if out["hold_mode_confirmed"] is not True:
        reasons.append("hold mode not confirmed")
    if closed:
        reasons.append(f"gvalid closed on {closed} ticks: the intervention "
                       f"became a Mechanism A trial")
    if condition != "CLEAN" and not inj.get("confirmed"):
        reasons.append("parameter readback NOT CONFIRMED")

    # --- RULE B: the reported position actually moved (and fix type held)
    pts, no_fix = reported_offset(res)
    base = [n for t, n in pts if onset_t - 3.0 <= t < onset_t]
    after = [n for t, n in pts if onset_t + 15.0 <= t <= onset_t + 25.0]
    shift = (None if not base or not after
             else (sum(after) / len(after) - sum(base) / len(base)))
    want = float(inj.get("metres") or 0.0)
    out["downstream_observable"] = {
        "name": "reported gnss.position north offset, 15-25 s after onset",
        "expected_m": want,
        "observed_m": None if shift is None else round(shift, 3),
        "no_3d_fix_ticks": no_fix,
        "fix_type_note": "no gnss.fix_type channel exists; a fix-type drop "
                         "would show as gnss.position MISSING/NO_3D_FIX, so 0 "
                         "such ticks IS 'fix type unchanged from the control'",
    }
    if no_fix:
        reasons.append(f"{no_fix} ticks with NO_3D_FIX: the fix did not hold, "
                       f"so this is not a fix-preserving trial")
    if want == 0.0:
        # THE CONTROL IS NOT GATED ON DISPLACEMENT. The preregistration
        # defines the null control as "identical flight, same window, no
        # parameter applied" and declares no drift tolerance. Inventing one
        # here could void a perfectly good control because ALT_HOLD let the
        # airframe wander a few metres, which is not what the control is for.
        # The number is recorded; it does not gate validity.
        pass
    elif shift is None:
        reasons.append("gnss.position not observable around onset")
    elif not (0.6 * want <= shift <= 1.4 * want):
        reasons.append(f"reported offset {shift:.2f} m outside +/-40% of "
                       f"{want:.1f} m")

    # --- section 5: reconstruct tick by tick from the MEASURED S0, T0
    rec = reconstruct_from(rows, i0, cfg)
    deltas = [abs(r["T_hat"] - r["T_runtime"]) for r in rec
              if not math.isnan(r["T_runtime"])]
    worst = max(deltas) if deltas else float("nan")
    out["reconstruction"] = {
        "from": "measured S0, T0 at onset; measured e_k; rho_k re-derived "
                "from component scores by the source formula",
        "closed_form_used": False,
        "closed_form_note": "constant-rho closed form deliberately NOT used "
                            "-- preregistration section 5, correction 9",
        "fitted_parameters": 0,
        "ticks_compared": len(deltas),
        "max_abs_delta": float(f"{worst:.6g}"),
        "tolerance": TRAJ_TOL,
        "within_tolerance": bool(deltas) and worst <= TRAJ_TOL,
        "null_controls": reconstruction_null_controls(rows, i0, cfg),
    }
    if not out["reconstruction"]["within_tolerance"]:
        reasons.append(f"reconstruction error {worst:.3g} > {TRAJ_TOL}")

    # --- crossings
    obs = crossing_index(rec, 0, "T_runtime")
    pred = crossing_index(rec, 0, "T_hat")
    out["crossing"] = {
        "threshold": THRESHOLD,
        "observed_tick": None if obs is None else obs,
        "predicted_tick": None if pred is None else pred,
        "error_ticks": (None if (obs is None or pred is None)
                        else abs(pred - obs)),
        "observed": obs is not None,
        "predicted": pred is not None,
        "agree_on_occurrence": (obs is None) == (pred is None),
        "T_min_after_onset": round(min(
            r["T_runtime"] for r in rec if not math.isnan(r["T_runtime"])), 6),
    }
    out["valid"] = not reasons
    out["invalid_reason"] = "; ".join(reasons) if reasons else None
    out["_rows"] = rec          # stripped before serialising
    return out


def write_ticks(trial, out_dir):
    """Section 4: the per-tick schema, exactly as preregistered."""
    rows = trial.get("_rows") or []
    if not rows:
        return None
    i0, onset = 0, trial["onset_s"]
    cross = trial["crossing"]["observed_tick"]
    lo = max(0, i0 - 20)
    hi = len(rows) if cross is None else min(len(rows), cross + 61)
    path = os.path.join(out_dir, f"{trial['trial']}.ticks.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["tick", "t_s", "fault_truth", "raw_residual",
                    "gate_applicable", "e_k", "rho_k", "S_k", "T_k",
                    "T_le_0_75", "failsafe_condition", "dwell_state",
                    "assurance_level"])
        for k in range(lo, hi):
            r = rows[k]
            pol = r.get("policy") or {}
            w.writerow([
                k, f"{r['t']:.4f}",
                "1" if r["t"] >= onset and trial["condition"] != "CLEAN"
                else "0",
                ("" if lambda_from_c(r["c_phys"]) is None
                 else f"{lambda_from_c(r['c_phys']):.6g}"),
                "" if r["gate_applicable"] is None
                else f"{r['gate_applicable']:.3f}",
                f"{r['e']:.9g}", f"{r['rho']:.9g}",
                "" if r["S_runtime"] is None else f"{r['S_runtime']:.9g}",
                f"{r['T_runtime']:.9g}",
                "1" if r["T_runtime"] <= THRESHOLD else "0",
                "|".join(pol.get("conditions") or []),
                "|".join(sorted((pol.get("dwell_since") or {}))),
                pol.get("level") or "",
            ])
    return os.path.relpath(path, ROOT)


# ------------------------------------------------------------- section 6
def classify(platform, trials):
    valid = [t for t in trials if t.get("valid")]
    by = {c: [t for t in valid if t["condition"] == c] for c in CONDITIONS}
    invalid = [t for t in trials if not t.get("valid")]

    traj_ok = all(t["reconstruction"]["within_tolerance"] for t in valid) \
        if valid else False
    crossed = {c: sum(1 for t in by[c] if t["crossing"]["observed"])
               for c in CONDITIONS}
    counts = {c: len(by[c]) for c in CONDITIONS}
    cross_err = [t["crossing"]["error_ticks"] for t in valid
                 if t["crossing"]["error_ticks"] is not None]
    cross_err_ok = all(e <= CROSS_TOL_TICKS for e in cross_err) if cross_err \
        else False
    occurrence_ok = all(t["crossing"]["agree_on_occurrence"] for t in valid) \
        if valid else False

    expectations = {
        c: (crossed[c] == counts[c] if EXPECT_CROSS[c] else crossed[c] == 0)
        for c in CONDITIONS if counts[c]
    }
    expectations_met = all(expectations.values()) and len(expectations) == 4

    # AN INCOMPLETE CAMPAIGN IS NOT A VERDICT. Section 6 says `NOT RUN` is not
    # in the list and must not be recorded as INCONCLUSIVE -- and a campaign
    # missing a whole condition is exactly that for the missing rows. Without
    # this guard a run with the ramp condition absent classified itself
    # PARTIALLY_REPLICATED, which reads as a finding and is not one.
    short = {c: counts[c] for c in CONDITIONS if counts[c] != REPETITIONS}
    if short:
        return {
            "platform": platform,
            "verdict": "CAMPAIGN_INCOMPLETE",
            "reason": ("not one of the five section 6 classifications: the "
                       "campaign has not run to the preregistered "
                       f"{REPETITIONS} repetitions for every condition "
                       f"({short}), so no verdict is issued"),
            "trials_total": len(trials),
            "trials_valid": len(valid),
            "trials_by_condition": counts,
        }

    if not valid:
        verdict = "INCONCLUSIVE"
        why = ("no trial passed the validity controls, so nothing can be "
               "concluded in either direction")
    elif len(valid) < len(trials):
        # A campaign with a whole condition missing cannot be REPLICATED.
        if not traj_ok:
            verdict, why = "NOT_REPLICATED", (
                "the recursion did not reproduce the runtime trajectory "
                "within tolerance on every valid trial")
        else:
            verdict, why = "PARTIALLY_REPLICATED", (
                f"{len(invalid)} of {len(trials)} trials failed the validity "
                f"controls; the recursion reproduced the trajectory on every "
                f"valid trial")
    elif not traj_ok:
        verdict, why = "NOT_REPLICATED", (
            "valid campaign, but the recursion did not reproduce the runtime "
            "trajectory within tolerance")
    elif not (expectations_met and occurrence_ok and cross_err_ok):
        verdict, why = "PARTIALLY_REPLICATED", (
            "the recursion reproduces the trajectory, but crossing outcomes "
            "differ from the predeclared expectation")
    else:
        verdict, why = "REPLICATED", (
            "valid injection with readback, matched control, gate open for "
            "the whole window, recursion reproduced the trajectory within "
            "tolerance, and predicted and observed crossings agree")

    return {
        "platform": platform,
        "verdict": verdict,
        "reason": why,
        "trials_total": len(trials),
        "trials_valid": len(valid),
        "trajectory_within_tolerance_on_all_valid": traj_ok,
        "max_reconstruction_error": (
            max((t["reconstruction"]["max_abs_delta"] for t in valid),
                default=None)),
        "crossings": {c: f"{crossed[c]} of {counts[c]}" for c in CONDITIONS},
        "expectations_met": expectations,
        "crossing_errors_ticks": cross_err,
        "crossing_error_tolerance": CROSS_TOL_TICKS,
        "S0_measured_by_condition": {
            c: [t["S0_measured"] for t in by[c]] for c in CONDITIONS},
    }


# The exact sentences Systems Paper I is permitted to use. Section 8 requires
# these for EACH outcome, so the permitted claim is fixed by the rule rather
# than written to fit whatever happened.
PERMITTED = {
    "REPLICATED": [
        "The history-dominated threshold-crossing mechanism replicates on "
        "ArduPilot 4.8: given the platform's own measured banked state and its "
        "measured per-tick evidence and forgetting factor, the source "
        "recursion reproduces the runtime trust trajectory and predicts the "
        "observed threshold crossing.",
        "The crossing tick differs from the 2015 ArduCopter 3.3 figure because "
        "the banked state differs; the mechanism, not the number, is what "
        "replicates.",
    ],
    "PARTIALLY_REPLICATED": [
        "On ArduPilot 4.8 the source recursion reproduces the runtime trust "
        "trajectory to within the preregistered tolerance, but the crossing "
        "outcomes do not match the predeclared expectation for every "
        "condition.",
        "The recursion is therefore confirmed as the mechanism governing the "
        "trajectory; the conditions under which it reaches a threshold are not "
        "fully characterised on this platform.",
    ],
    "NOT_REPLICATED": [
        "On ArduPilot 4.8 the source recursion does not reproduce the runtime "
        "trust trajectory within the preregistered tolerance, so the "
        "history-dominated threshold-crossing mechanism does not replicate on "
        "the current stack.",
        "This is an external-validity finding about a mechanism derived from a "
        "single 2015-era autopilot.",
    ],
    "INAPPLICABLE": [
        "The fix-preserving GNSS position offset required to exercise the "
        "history-dominated threshold-crossing mechanism cannot be applied on "
        "this platform, so the mechanism was not tested there.",
        "No substitute intervention was run, because substituting one would "
        "test a different fault.",
    ],
    "INCONCLUSIVE": [
        "The Mechanism B campaign ran on this platform but its validity "
        "controls failed, so no claim is made about the "
        "history-dominated threshold-crossing mechanism there.",
    ],
    # Not one of section 6's five. An unfinished campaign permits NO sentence,
    # and saying so explicitly is the point -- section 6 warns that `NOT RUN`
    # must not be laundered into INCONCLUSIVE.
    "CAMPAIGN_INCOMPLETE": [
        "NO SENTENCE IS PERMITTED. The campaign has not run to the "
        "preregistered repetitions, which is not one of the five section 6 "
        "classifications and must not be reported as any of them.",
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", default="ardupilot")
    ap.add_argument("--results", default=os.path.join(
        ROOT, "research", "v1_1", "results", "mechanism_b_gps"))
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "current_stack_replication.json"))
    args = ap.parse_args()

    trials = []
    for cond in CONDITIONS:
        for p in sorted(glob.glob(os.path.join(
                args.results, f"{args.platform}_{cond}_*.json"))):
            trials.append(analyse_trial(p, cond))

    if not trials:
        print(f"no trials found under {args.results}")
        return 2

    tick_dir = os.path.join(args.results, "ticks")
    os.makedirs(tick_dir, exist_ok=True)
    for t in trials:
        if t.get("_rows"):
            t["tick_log"] = write_ticks(t, tick_dir)
        t.pop("_rows", None)

    ap_verdict = classify(args.platform, trials)

    print(f"=== Mechanism B, {args.platform}")
    print(f"  {'trial':26s} {'valid':>5s} {'S0':>8s} {'T0':>7s} "
          f"{'maxdT':>10s} {'obs':>5s} {'pred':>5s} {'err':>4s} {'Tmin':>7s}")
    for t in trials:
        c = t.get("crossing") or {}
        r = t.get("reconstruction") or {}
        print(f"  {t['trial']:26s} {str(t.get('valid')):>5s} "
              f"{(t.get('S0_measured') or 0):8.2f} "
              f"{(t.get('T0_measured') or 0):7.4f} "
              f"{str(r.get('max_abs_delta')):>10s} "
              f"{str(c.get('observed_tick')):>5s} "
              f"{str(c.get('predicted_tick')):>5s} "
              f"{str(c.get('error_ticks')):>4s} "
              f"{str(c.get('T_min_after_onset')):>7s}")
        if not t.get("valid"):
            print(f"        INVALID: {t.get('invalid_reason')}")
    print(f"  -> {ap_verdict['verdict']}: {ap_verdict['reason']}")

    out = {
        "preregistration": PREREG,
        "preregistration_blob_sha1": PREREG_BLOB,
        "threshold": THRESHOLD,
        "node": NODE,
        "trials": trials,
        "platforms": {
            args.platform: ap_verdict,
            "px4": {
                "platform": "px4",
                "verdict": "INAPPLICABLE",
                "reason": "no fix-preserving GNSS position offset exists on "
                          "PX4 SIH; four candidate routes were read out of "
                          "source at 547e2ca and all four fail (section 2.1). "
                          "Section 3 forbids substituting another "
                          "intervention, so no trials were run.",
                "trials_total": 0,
                "evidence": {
                    "SIM_GPS_USED": "satellite count -- fix loss, which is "
                                    "Mechanism A (SensorGpsSim.cpp:155-167)",
                    "SENS_GPS1_OFFX/OFFY": "publishes a SECOND offset receiver "
                                           "instance; the primary is published "
                                           "unmodified (SensorGpsSim.cpp:"
                                           "201-217)",
                    "SENS_GPS0_OFF{X,Y,Z}": "antenna lever arm passed through "
                                            "as antenna_offset_* metadata; "
                                            "lat/lon never modified "
                                            "(VehicleGPSPosition.cpp:173,"
                                            "197-200)",
                    "failure_injection GNSS": "Off and Wrong close the "
                                              "validity gate; Stuck is a "
                                              "frozen-position fault, a "
                                              "different family",
                },
            },
        },
        "permitted_sentences_by_outcome": PERMITTED,
        "permitted_sentences_in_force": {
            args.platform: PERMITTED[ap_verdict["verdict"]],
            "px4": PERMITTED["INAPPLICABLE"],
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 0 if any(t.get("valid") for t in trials) else 2


if __name__ == "__main__":
    sys.exit(main())
