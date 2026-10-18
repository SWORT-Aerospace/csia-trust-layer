"""Mechanism B -- history-dominated threshold crossing, on the current stack.

THE PHASE-I CLAIM UNDER TEST. `docs/v1/V1_FINAL_RESEARCH_VERDICT.md` W-4: the
trust recursion carries banked evidence `S` in front of new evidence `e`, so a
node whose evidence collapses does not drop to the new level -- it WALKS there
over a number of ticks set by `S` and `rho`:

    S(k) = rho(k)*S(k-1) + 1
    T(k) = ( rho(k)*S(k-1)*T(k-1) + e(k) ) / S(k)

`MECHANISM_A_MODERN_REPLICATION.md` section 6 says why fix loss cannot test
this: self-occlusion removes the evidence, the node never moves, and there is
no crossing to time. So Mechanism B uses an EVIDENCE-PRESERVING injection -- a
constant hard-iron magnetometer offset -- preregistered in
`research/v1_1/MECHANISM_B_MAG_EMI_PREREGISTRATION.md` before any trial ran.

WHAT MAKES THE RECONSTRUCTION INDEPENDENT. T_hat is integrated forward from the
FIRST tick of the flight using only:

    * EngineConfig constants alpha0=8, beta0=2 -> S_hat(0)=10, T_hat(0)=0.8,
      read out of the trace header written by the engine that produced the run;
    * the observed per-tick evidence e(k);
    * rho(k) RE-DERIVED here from the component scores by the source formula
      (engine.py:141-143), never read from the runtime;
    * the update gate `avail AND fresh`.

No runtime trust value enters the integration. No parameter is fitted. The
runtime trust is used for one thing only: to be compared against.

E1 (primary)   max_k |T_hat(k) - T_runtime(k)| <= 0.02
E2 (secondary) |N* - N_obs| <= 25 ticks, N* from the W-4 closed form
E3             the matched CLEAN arm must not cross

  python tools/simulation/mechanism_b_report.py --platform ardupilot \\
      --arm CROSS research/v1_1/results/mechanism_b/ap_CROSS_0.json ...
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

NODE = "mag"
# csia/runtime/failsafe.py: heading_caution. The value the FROZEN failsafe
# compares mag trust against. Crossing it is the endpoint; escalating is not,
# because escalation additionally needs 1.0 s of continuous dwell and node
# freshness -- and PX4_CLEAN_ESCALATION_DIAGNOSIS.md showed the dwell, not the
# trust value, is what decides the outcome there.
THRESHOLD = 0.60
E1_TOL = 0.02          # preregistered
E2_TOL_TICKS = 25      # preregistered (1.0 s at 25 Hz)
# Preregistered fixed window for the closed form's constants: ticks
# k_inject+2 .. k_inject+26. Fixed in advance so it cannot be slid onto a
# flattering stretch of the trajectory after the fact.
EF_WINDOW = (2, 27)


# ---------------------------------------------------------------- loading
def _open_trace(path: str):
    if path.endswith(".gz"):
        import gzip
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def read_trace(path: str):
    header, steps = None, []
    with _open_trace(path) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("record") == "trace_header":
                header = rec
            elif rec.get("record") == "step":
                steps.append(rec)
    return header, steps


def read_field(result: dict):
    """`mag.field_ut` per tick from the flight log -- the RULE B observable."""
    log_dir = os.path.join(ROOT, result.get("log_dir", ""))
    fid = result.get("flight_id", "")
    out = []
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
                    .get("mag.field_ut") or {}
                if cv.get("usable") and isinstance(cv.get("value"), list) \
                        and len(cv["value"]) == 3:
                    out.append((float(rec["t_mono"]),
                                [float(x) for x in cv["value"]]))
    return out


# ------------------------------------------------------- the source formula
def rho_of(components: dict, rho_max: float, rho_min: float):
    """Re-derive rho from the component scores. engine.py:141-143.

    Returns (rho, n_available). n_available == 0 means the node had NO
    evidence this tick: the engine holds the Beta belief and does not update.
    """
    scores = [v for v in components.values() if v is not None]
    if not scores:
        return rho_max, 0
    d = (max(scores) - min(scores)) if len(scores) > 1 else 0.0
    return rho_max - (rho_max - rho_min) * d, len(scores)


def reconstruct(steps, node, cfg):
    """Integrate S_hat/T_hat forward. No runtime trust enters this loop."""
    S = cfg["alpha0"] + cfg["beta0"]
    T = cfg["alpha0"] / S
    rows = []
    for st in steps:
        comps = (st.get("components") or {}).get(node)
        if comps is None:
            continue
        rho, navail = rho_of(comps, cfg["rho_max"], cfg["rho_min"])
        e = float((st.get("evidence") or {}).get(node, 0.5))
        fresh = bool((st.get("fresh") or {}).get(node, True))
        updated = bool(navail) and fresh
        if updated:
            S_prev, T_prev = S, T
            S = rho * S_prev + 1.0
            T = (rho * S_prev * T_prev + e) / S
        rows.append({
            "t": st["t"],
            "T_hat": T,
            "S_hat": S,
            "rho": rho,
            "e": e,
            "fresh": fresh,
            "n_available": navail,
            "updated": updated,
            "T_runtime": float((st.get("trust") or {}).get(node, float("nan"))),
            "S_runtime": (None if st.get("S") is None
                          else float(st["S"].get(node, float("nan")))),
        })
    return rows


def closed_form_N(S0, T0, e_f, rho, thr=THRESHOLD):
    """Smallest N with T_N <= thr, from the W-4 constant-coefficient form.

        x = rho^N, M = 1/(1-rho)
        T_N = ( x*S0*T0 + (1-x)*M*e_f ) / ( x*S0 + (1-x)*M )

    Solving T_N = thr for x:

        x = M*(thr - e_f) / ( S0*(T0 - thr) + M*(thr - e_f) )

    Returns (N, note). N is None when no crossing is predicted, and the note
    says why rather than leaving a bare None to be read as a failure.
    """
    if T0 <= thr:
        return 0.0, "already at or below the threshold at injection"
    if e_f >= thr:
        return None, (f"steady evidence e_f={e_f:.4f} is at or above the "
                      f"threshold {thr}: T tends to e_f, so no crossing is "
                      f"predicted at any N")
    if not (0.0 < rho < 1.0):
        return None, f"rho={rho} outside (0,1)"
    M = 1.0 / (1.0 - rho)
    num = M * (thr - e_f)
    den = S0 * (T0 - thr) + num
    if den <= 0 or num <= 0:
        return None, "closed form has no admissible root"
    x = num / den
    if not (0.0 < x < 1.0):
        return None, f"root x={x:.6g} outside (0,1)"
    return math.log(x) / math.log(rho), ""


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


# ------------------------------------------------------------------ one arm
def analyse_arm(result_path: str, arm: str) -> dict:
    with open(result_path, encoding="utf-8") as fh:
        res = json.load(fh)
    trace_path = os.path.join(ROOT, res.get("trust_trace") or "")
    out = {
        "arm": arm,
        "result_file": os.path.relpath(result_path, ROOT),
        "flight_id": res.get("flight_id"),
        "platform": res.get("platform"),
        "injection": res.get("injection"),
        "command_authority": (res.get("command_authority")
                              or {}).get("result"),
    }
    if not res.get("trust_trace") or not os.path.exists(trace_path):
        out["valid"] = False
        out["invalid_reason"] = "no trust trace: nothing to reconstruct"
        return out

    header, steps = read_trace(trace_path)
    if header is None or not steps:
        out["valid"] = False
        out["invalid_reason"] = "trace unreadable or empty"
        return out
    cfg = header["engine_config"]
    out["engine_config"] = cfg
    out["steps"] = len(steps)

    inj = res.get("injection") or {}
    u = float(inj.get("micro_tesla_per_axis", 0.0) or 0.0)
    # `wrote_at_rel_s` is when the write burst actually went out; `at_s` is
    # only when it was scheduled. Prefer the former.
    at = float(inj.get("wrote_at_rel_s", inj.get("at_s", 0.0)) or 0.0)
    out["u_ut"] = u
    expected = abs(u) * math.sqrt(3.0)

    # ---- RULE B: did the field actually move, and WHEN?
    #
    # The injection instant is taken from the FIELD, not from the clock. N_obs
    # is counted from it, so a second of timing skew would enter E2 as 25
    # ticks of "mechanism". The commanded time is the fallback, used only when
    # there is nothing to detect (the null arm) or the field is unreadable.
    field = read_field(res)
    pre = [v for t, v in field if at - 2.5 <= t < at]
    mp = ([sum(v[i] for v in pre) / len(pre) for i in range(3)]
          if pre else None)
    onset = None
    if mp is not None and u > 0.0:
        for t, v in field:
            if t < at - 0.5:
                continue
            if math.sqrt(sum((v[i] - mp[i]) ** 2
                             for i in range(3))) > 0.5 * expected:
                onset = t
                break
    at_eff = onset if onset is not None else at
    post = [v for t, v in field if at_eff + 0.4 < t <= at_eff + 2.4]
    shift = None
    if mp is not None and post:
        mq = [sum(v[i] for v in post) / len(post) for i in range(3)]
        shift = math.sqrt(sum((mq[i] - mp[i]) ** 2 for i in range(3)))
    out["downstream_observable"] = {
        "name": "mag.field_ut mean vector shift across the injection instant",
        "expected_ut": round(expected, 4),
        "observed_ut": None if shift is None else round(shift, 4),
        "pre_samples": len(pre), "post_samples": len(post),
        "commanded_at_s": round(at, 3),
        "detected_onset_s": None if onset is None else round(onset, 3),
        "injection_instant_source": ("observed field onset" if onset is not None
                                     else "commanded time (no onset detected)"),
        "rule": "RULE B -- the parameter write is not the measurement",
    }
    at = at_eff

    # ---- the preregistered validity condition (section 2.5)
    reasons = []
    if out["command_authority"] != "NO_COMMAND_PATH_REACHABLE":
        reasons.append(f"command authority {out['command_authority']}")
    if inj.get("kind") == "mag_emi" and not inj.get("confirmed"):
        reasons.append("parameter readback NOT CONFIRMED")
    if shift is None:
        reasons.append("mag.field_ut not observable around the injection")
    elif u == 0.0:
        if shift >= 1.0:
            reasons.append(f"null arm field moved {shift:.3f} uT (>= 1.0)")
    elif not (0.6 * expected <= shift <= 1.4 * expected):
        reasons.append(f"field shift {shift:.3f} uT outside +/-40% of "
                       f"{expected:.3f} uT")

    # ---- the reconstruction
    rows = reconstruct(steps, NODE, cfg)
    out["reconstructed_ticks"] = len(rows)
    if not rows:
        out["valid"] = False
        out["invalid_reason"] = "; ".join(reasons + [f"no {NODE} rows"])
        return out

    deltas = [abs(r["T_hat"] - r["T_runtime"]) for r in rows
              if not math.isnan(r["T_runtime"])]
    worst = max(deltas) if deltas else float("nan")
    worst_i = deltas.index(worst) if deltas else None
    e1 = bool(deltas) and worst <= E1_TOL
    out["E1_recursion_fidelity"] = {
        "compared": len(deltas),
        # NOT rounded to 6 places: at 6 places a real 5.2e-10
        # round-off (the trace stores 9 decimals) prints as "0.0",
        # and "exactly zero" is a stronger claim than the data
        # supports. Report the magnitude actually measured.
        "max_abs_delta": float(f"{worst:.3g}"),
        "at_t": rows[worst_i]["t"] if worst_i is not None else None,
        "tolerance": E1_TOL,
        "pass": e1,
        "rule": "T_hat is integrated from alpha0/beta0 using only observed "
                "e(k), re-derived rho(k) and the update gate; no runtime "
                "trust enters the integration and no parameter is fitted",
    }
    # S is a cross-check, not an endpoint: the runtime value is only
    # attributable for the last engine step of each shadow tick.
    sd = [abs(r["S_hat"] - r["S_runtime"]) for r in rows
          if r["S_runtime"] is not None and not math.isnan(r["S_runtime"])]
    out["S_cross_check"] = {"compared": len(sd),
                            "max_abs_delta": (float(f"{max(sd):.3g}")
                                             if sd else None)}

    if not e1:
        reasons.append(f"E1 failed: max|T_hat-T| = {worst:.4f} > {E1_TOL}")
    out["valid"] = not reasons
    out["invalid_reason"] = "; ".join(reasons) if reasons else None

    # ---- crossing, observed
    k_inj = next((i for i, r in enumerate(rows) if r["t"] >= at), None)
    out["k_inject"] = k_inj
    cross_i = next((i for i, r in enumerate(rows)
                    if (k_inj is None or i >= k_inj)
                    and r["T_runtime"] <= THRESHOLD), None)
    out["crossing"] = {
        "threshold": THRESHOLD,
        "definition": "first tick at or after injection with T_runtime <= "
                      "0.60 (heading_caution); NOT escalation, which also "
                      "needs 1.0 s of continuous dwell",
        "crossed": cross_i is not None,
        "N_obs_ticks": None if (cross_i is None or k_inj is None)
                       else cross_i - k_inj,
        "at_t": rows[cross_i]["t"] if cross_i is not None else None,
        "T_at_injection": (None if k_inj is None
                           else round(rows[k_inj]["T_runtime"], 6)),
        "T_min_after_injection": (
            None if k_inj is None else
            round(min(r["T_runtime"] for r in rows[k_inj:]), 6)),
    }

    # ---- E2: the closed form, from the preregistered fixed window
    out["E2_closed_form"] = {"applicable": False}
    if k_inj is not None:
        lo, hi = k_inj + EF_WINDOW[0], k_inj + EF_WINDOW[1]
        win = rows[lo:hi]
        if win:
            e_f = median([r["e"] for r in win])
            rho_f = median([r["rho"] for r in win])
            S0 = rows[k_inj]["S_hat"]
            T0 = rows[k_inj]["T_runtime"]
            N, note = closed_form_N(S0, T0, e_f, rho_f)
            n_obs = out["crossing"]["N_obs_ticks"]
            err = (None if (N is None or n_obs is None)
                   else abs(math.ceil(N) - n_obs))
            out["E2_closed_form"] = {
                "applicable": True,
                "window_ticks": [EF_WINDOW[0], EF_WINDOW[1]],
                "S0": round(S0, 4), "T0": round(T0, 6),
                "e_f": round(e_f, 6), "rho_f": round(rho_f, 6),
                "N_predicted": None if N is None else round(N, 2),
                "N_predicted_ceil": None if N is None else math.ceil(N),
                "N_observed": n_obs,
                "error_ticks": err,
                "tolerance_ticks": E2_TOL_TICKS,
                "pass": bool(err is not None and err <= E2_TOL_TICKS),
                "note": note,
            }

    # a compact trajectory for the document, not the whole 1000 ticks
    if k_inj is not None:
        marks = {}
        for label, off in (("pre", -25), ("inject", 0), ("+1s", 25),
                           ("+2s", 50), ("+4s", 100), ("+10s", 250)):
            i = k_inj + off
            if 0 <= i < len(rows):
                r = rows[i]
                marks[label] = {
                    "t": r["t"], "T_runtime": round(r["T_runtime"], 5),
                    "T_hat": round(r["T_hat"], 5), "S_hat": round(r["S_hat"], 2),
                    "e": round(r["e"], 5), "rho": round(r["rho"], 5),
                    "fresh": r["fresh"], "updated": r["updated"],
                }
        out["trajectory"] = marks
    return out


# ------------------------------------------------------------------- verdict
def classify(platform: str, arms: list) -> dict:
    """Section 6 of the preregistration, applied mechanically."""
    valid = [a for a in arms if a.get("valid")]
    cross_arms = [a for a in valid if a["arm"] == "CROSS"]
    clean_arms = [a for a in valid if a["arm"] == "CLEAN"]
    crossed = [a for a in cross_arms if a["crossing"]["crossed"]]
    e1_all = all(a["E1_recursion_fidelity"]["pass"] for a in valid) \
        if valid else False
    e2_ok = [a for a in crossed if a.get("E2_closed_form", {}).get("pass")]
    e3_confounded = [a for a in clean_arms if a["crossing"]["crossed"]]

    if not cross_arms:
        verdict, why = "INCONCLUSIVE", (
            "no valid CROSS arm: the intervention was not verified downstream "
            "on any repetition, so neither a replication nor a failure can be "
            "claimed")
    elif not e1_all:
        verdict, why = "INCONCLUSIVE", (
            "E1 failed on at least one valid arm: the reconstruction does not "
            "describe the runtime, so no crossing claim is admissible")
    elif e3_confounded:
        verdict, why = "INCONCLUSIVE", (
            f"E3 confounded: {len(e3_confounded)} of {len(clean_arms)} CLEAN "
            "arms crossed the threshold with no injected fault, so a crossing "
            "in the injected arm cannot be attributed to the intervention")
    elif not crossed:
        verdict, why = "DOES_NOT_REPLICATE", (
            "valid CROSS arms with a verified downstream field shift did not "
            "cross the threshold")
    elif not e2_ok:
        verdict, why = "DOES_NOT_REPLICATE", (
            "the threshold was crossed, but the closed form did not predict "
            "when on any repetition")
    else:
        verdict, why = "REPLICATES", (
            f"{len(crossed)}/{len(cross_arms)} valid CROSS arms crossed; E1 "
            f"holds on all {len(valid)} valid arms; the closed form predicted "
            f"the crossing on {len(e2_ok)}; no CLEAN arm crossed")
    return {"platform": platform, "verdict": verdict, "reason": why,
            "arms_total": len(arms), "arms_valid": len(valid),
            "cross_arms_valid": len(cross_arms),
            "cross_arms_crossed": len(crossed),
            "clean_arms_valid": len(clean_arms),
            "clean_arms_crossed": len(e3_confounded),
            "e1_pass_on_all_valid": e1_all,
            "e2_pass_count": len(e2_ok)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", required=True)
    ap.add_argument("--arm", action="append", nargs=2, metavar=("ARM", "FILE"),
                    required=True, help="arm label and its result JSON")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    arms = [analyse_arm(os.path.join(ROOT, path), label)
            for label, path in args.arm]

    print(f"=== Mechanism B, {args.platform}")
    hdr = (f"  {'arm':7s} {'u uT':>6s} {'shift uT':>9s} {'valid':>6s} "
           f"{'maxdT':>8s} {'crossed':>8s} {'N_obs':>6s} {'N*':>7s} "
           f"{'err':>5s}")
    print(hdr)
    for a in arms:
        d = a.get("downstream_observable") or {}
        e1 = a.get("E1_recursion_fidelity") or {}
        cr = a.get("crossing") or {}
        e2 = a.get("E2_closed_form") or {}
        print(f"  {a['arm']:7s} {a.get('u_ut', 0):6.1f} "
              f"{str(d.get('observed_ut')):>9s} {str(a.get('valid')):>6s} "
              f"{str(e1.get('max_abs_delta')):>8s} "
              f"{str(cr.get('crossed')):>8s} "
              f"{str(cr.get('N_obs_ticks')):>6s} "
              f"{str(e2.get('N_predicted_ceil')):>7s} "
              f"{str(e2.get('error_ticks')):>5s}")
        if not a.get("valid"):
            print(f"          INVALID: {a.get('invalid_reason')}")

    verdict = classify(args.platform, arms)
    print(f"  -> {verdict['verdict']}: {verdict['reason']}")

    out = {"platform": args.platform, "arms": arms, "verdict": verdict,
           "preregistration": "research/v1_1/MECHANISM_B_MAG_EMI_PREREGISTRATION.md",
           "claim_under_test": "W-4: banked evidence S delays a trust node's "
                               "threshold crossing, and the recursion predicts "
                               "by how much"}
    path = args.out or os.path.join(ROOT, "research", "v1_1", "results",
                                    f"mechanism_b_{args.platform}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(path, ROOT)}")
    # An unusable measurement must not exit 0. INCONCLUSIVE is a real outcome
    # of the preregistered rule, not an error, so it exits 0 as well -- what
    # exits non-zero is an arm nobody could evaluate.
    return 0 if any(a.get("valid") for a in arms) else 2


if __name__ == "__main__":
    sys.exit(main())
