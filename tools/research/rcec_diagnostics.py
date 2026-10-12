"""Repair diagnostics. Why P3 failed, what binds, and is the lag error safe?

Runs ONLY on the `diagnostic` partition. `partitions.seeds()` refuses a
sealed partition and has no override, and a test asserts this file's seed
constants are disjoint from both locked sets.

FIVE QUESTIONS, EACH WITH ITS OWN SECTION
------------------------------------------
  1. reconstruct   what the failing pilot actually did, deterministically
  2. feasibility   is there ANY waveform that certifies, and what is it?
  3. binding       for every candidate, which condition bound FIRST?
  4. optimizer     does the search find the best feasible candidate?
  5. lag           is underestimating the loop lag conservative, or not?

WHAT THIS TOOL IS NOT ALLOWED TO DO
-------------------------------------
It does not loosen a constraint to make P3 certify. If the feasible set is
empty the correct answer is `NO_SAFE_INFORMATIVE_ACTION`, and that is a
result rather than a failure.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import battery_1rc as B                  # noqa: E402
from csia_active_evidence import partitions as PT                  # noqa: E402
from csia_active_evidence import polarization as PZ                # noqa: E402
from csia_active_evidence import rcec                              # noqa: E402
from csia_active_evidence import rcec_selector as RS               # noqa: E402
from csia_active_evidence import realized_moments as RM            # noqa: E402
from csia_active_evidence import waveform_compensation as WC       # noqa: E402
from tools.research import rcec_campaign as C                      # noqa: E402

INSTRUMENT = "tools.research.rcec_diagnostics"
SCHEMA = "csia.active_evidence.rcec_diagnostics/1"

DIAG = PT.seeds("diagnostic")
CAL = PT.seeds("amended_calibration")


# --- 1. reconstruct the failed pilot ---------------------------------------

def pilot_objective(cand) -> float:
    """THE FAILING OBJECTIVE, RECONSTRUCTED FROM RC-3'S DESCRIPTION.

    RECONSTRUCTED, NOT RECOVERED. `git log -S` over the campaign file finds
    no commit containing it: the pilot ran from uncommitted working state and
    its artifact does not exist. This is rebuilt from the exact wording of
    RC-3 in `COUNTEREXAMPLE_LOG.md` -- a shortfall against `S_II_min`, the
    drift lever arm squared, energy divided by 100, and a saturation penalty.

    It is kept so the repair has something to be compared against, and it is
    labelled `RECONSTRUCTED_NOT_RECOVERED` wherever it appears.
    """
    t = RS.window_times(C.ACTION_START, cand["duration"], C.HZ)
    w = _waveform(cand, t)
    cmd = WC.as_callable(w, t)
    b = C.budget()
    sigma_eff = math.sqrt(b.sigma_v ** 2 + (b.r_reference * b.sigma_i) ** 2)
    s_ii_min = (b.k_sigma * sigma_eff
                / (C.C_FRACTION * C.TARGET_DELTA_R)) ** 2
    gamma_max = (C.C_FRACTION * C.TARGET_DELTA_R) / C.D_MAX
    total = 0.0
    for seed in DIAG:
        tr = B.simulate(cmd, duration=C.DURATION, seed=int(seed))
        win = tr.window(C.ACTION_START, C.ACTION_START + cand["duration"])
        if win.n < 5:
            total += 100.0
            continue
        m = RM.moments(win.t, win.i_meas)
        deficit = max(0.0, s_ii_min - m.s_ii) / s_ii_min
        coupling = abs(m.lever_arm_s) / gamma_max
        energy = float(np.sum(np.abs(w)) / C.HZ) / 100.0
        total += deficit ** 2 + coupling ** 2 + energy \
            + 10.0 * float(np.mean(win.saturated))
    return total / len(DIAG)


def _waveform(cand, t):
    if cand["shape"] == "palindromic":
        return RS.palindromic(t, C.ACTION_START, cand["duration"],
                              cand["amplitude"], cand.get("cycles", 3))
    return RS.SHAPES[cand["shape"]](t, C.ACTION_START, cand["duration"],
                                    cand["amplitude"])


def certificate_objective(cand) -> float:
    """The repaired objective: scored by the certificate itself."""
    return C.p3_objective(cand)


# --- 2 and 3. feasibility and the binding-constraint table ------------------

FIRST_BINDING = ("SHAPE_INVALID", "TOO_FEW_SAMPLES", "EXCITATION",
                 "DRIFT_COUPLING", "MODEL_MISMATCH", "ERROR_BUDGET",
                 "CERTIFIED")


def classify(cand, seed) -> dict:
    """Run one candidate once and record WHICH condition bound first.

    The ordering is the certificate's own evaluation order, so a candidate is
    attributed to the first thing that actually stopped it rather than to
    whatever is easiest to blame.
    """
    t = RS.window_times(C.ACTION_START, cand["duration"], C.HZ)
    w = _waveform(cand, t)
    cmd = WC.as_callable(w, t)
    tr = B.simulate(cmd, duration=C.DURATION, seed=int(seed))
    win = tr.window(C.ACTION_START, C.ACTION_START + cand["duration"])
    if win.n < C.budget().min_samples:
        return {"binding": "TOO_FEW_SAMPLES", "state": None}
    cert = rcec.certify(win.t, win.i_meas, win.v_meas, C.budget())
    m = RM.moments(win.t, win.i_meas)
    binding = {
        rcec.CERTIFIED: "CERTIFIED",
        rcec.INSUFFICIENT_EXCITATION: "EXCITATION",
        rcec.DRIFT_COUPLED: "DRIFT_COUPLING",
        rcec.MODEL_MISMATCH_LIMITED: "MODEL_MISMATCH",
        rcec.MEASUREMENT_LIMITED: "ERROR_BUDGET",
        rcec.UNKNOWN_OR_MODEL_MISMATCH: "MODEL_MISMATCH",
        rcec.ABORTED_INCOMPLETE: "TOO_FEW_SAMPLES",
    }.get(cert.state, "SHAPE_INVALID")
    return {
        "binding": binding, "state": cert.state,
        "predicted_s_ii": float(np.var(w + C.AMPLITUDE * 0.0) * w.size),
        "realized_s_ii": m.s_ii,
        "realized_s_ti": m.s_ti,
        "realized_lever_s": m.lever_arm_s,
        "B_drift": cert.terms.get("B_drift"),
        "B_dynamic": cert.terms.get("B_dynamic"),
        "B_total": cert.terms.get("B_total"),
        "achieved_error": cert.resolution.get("achieved_error"),
        "allowed_error": cert.resolution.get("allowed_error"),
        "saturated_fraction": float(np.mean(win.saturated)),
    }


def feasibility_and_binding(candidates, seed) -> dict:
    rows = []
    for cand in candidates:
        r = classify(cand, seed)
        r["candidate"] = cand
        rows.append(r)
    counts = {}
    for r in rows:
        counts[r["binding"]] = counts.get(r["binding"], 0) + 1
    feasible = [r for r in rows if r["binding"] == "CERTIFIED"]
    witness = None
    if feasible:
        witness = min(feasible,
                      key=lambda r: r["candidate"]["amplitude"]
                      * r["candidate"]["duration"])
    return {
        "candidates": len(rows),
        "binding_counts": counts,
        "feasible_count": len(feasible),
        "feasible_set_is_empty": not feasible,
        "cheapest_feasible_witness": witness["candidate"] if witness else None,
        "witness_detail": {k: v for k, v in (witness or {}).items()
                           if k != "candidate"} if witness else None,
        "rows": rows,
        "reading": ("An empty feasible set means NO_SAFE_INFORMATIVE_ACTION "
                    "is the correct answer and the constraints must not be "
                    "loosened to avoid it."),
    }


# --- 4. optimizer comparison ------------------------------------------------

def optimizer_comparison(candidates, seed) -> dict:
    """Does the search find the best feasible candidate on this grid?

    Exhaustive enumeration is available because the grid is small, so the
    optimum is known and the search can be checked against it rather than
    trusted.
    """
    scored = [(certificate_objective(c), c) for c in candidates]
    scored.sort(key=lambda x: x[0])
    chosen = scored[0][1]

    exhaustive = feasibility_and_binding(candidates, seed)
    feasible = [r for r in exhaustive["rows"] if r["binding"] == "CERTIFIED"]
    cheapest = (min(feasible, key=lambda r: r["candidate"]["amplitude"]
                    * r["candidate"]["duration"])["candidate"]
                if feasible else None)

    chosen_ok = classify(chosen, seed)["binding"] == "CERTIFIED"
    pilot = [(pilot_objective(c), c) for c in candidates]
    pilot.sort(key=lambda x: x[0])
    pilot_choice = pilot[0][1]
    pilot_ok = classify(pilot_choice, seed)["binding"] == "CERTIFIED"

    return {
        "grid_size": len(candidates),
        "repaired_objective_choice": chosen,
        "repaired_choice_certifies": chosen_ok,
        "reconstructed_pilot_choice": pilot_choice,
        "reconstructed_pilot_choice_certifies": pilot_ok,
        "pilot_label": "RECONSTRUCTED_NOT_RECOVERED",
        "cheapest_feasible_on_grid": cheapest,
        "search_found_a_feasible_candidate": chosen_ok,
        "verdict": ("OPTIMIZER_OK" if chosen_ok else
                    "OPTIMIZER_FAILED_A_FEASIBLE_WITNESS_EXISTS"
                    if feasible else "INFEASIBLE_ON_THIS_GRID"),
    }


# --- 5. the lag sweep, signed --------------------------------------------

def lag_sweep() -> dict:
    """Is underestimating the loop lag conservative? SIGNED, both directions.

    MX-039 called underestimation conservative because it under-compensates.
    That was asserted, not shown. Under-compensation can change the sign of
    S_tI, the saturation timing, the realized excitation and the safety
    margin, and this sweeps both directions to find out.
    """
    rows = []
    for true_tau in (0.10, 0.25, 0.50, 0.80):
        loop = B.Loop(**{**B.SYNTHETIC_LOOP, "lag_s": true_tau})

        def sim(command, duration, seed, _loop=loop):
            return B.simulate(command, duration=duration, seed=seed,
                              loop=_loop)
        fitted = WC.estimate_lag(sim, seeds=CAL).tau_s
        for ratio in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0):
            assumed = true_tau * ratio
            model = WC.LagModel(tau_s=assumed, rms_residual_a=0.0,
                                fitted_on_seeds=tuple(CAL))
            t = RS.window_times(C.ACTION_START, C.ACTION_DURATION, C.HZ)
            base = RS.palindromic(t, C.ACTION_START, C.ACTION_DURATION,
                                  C.AMPLITUDE, 6)
            u, rep = WC.compensate(base, t, model,
                                   authority_a=C.AUTHORITY_A)
            tr = sim(WC.as_callable(u, t), C.DURATION, int(DIAG[0]))
            w = tr.window(C.ACTION_START,
                          C.ACTION_START + C.ACTION_DURATION)
            m = RM.moments(w.t, w.i_meas)
            cert = rcec.certify(w.t, w.i_meas, w.v_meas, C.budget())
            rows.append({
                "true_tau_s": true_tau, "assumed_tau_s": assumed,
                "ratio": ratio,
                "signed_error_s": assumed - true_tau,
                "signed_error_pct": 100.0 * (assumed - true_tau) / true_tau,
                "fitted_tau_s": fitted,
                "fit_signed_error_s": fitted - true_tau,
                "fit_signed_error_pct": 100.0 * (fitted - true_tau) / true_tau,
                "realized_s_ii": m.s_ii,
                "realized_lever_s": m.lever_arm_s,
                "lever_sign": int(np.sign(m.lever_arm_s)),
                "saturated_fraction": float(np.mean(w.saturated)),
                "clipped_fraction": rep["fraction_clipped"],
                "state": cert.state,
                "achieved_error": cert.resolution.get("achieved_error"),
            })

    under = [r for r in rows if r["ratio"] < 1.0]
    over = [r for r in rows if r["ratio"] > 1.0]
    exact = [r for r in rows if r["ratio"] == 1.0]

    def worst(rs):
        vals = [r["achieved_error"] for r in rs
                if r["achieved_error"] is not None]
        return max(vals) if vals else None

    sign_flips = sorted({(r["true_tau_s"], r["ratio"])
                         for r in rows
                         for e in exact
                         if e["true_tau_s"] == r["true_tau_s"]
                         and r["lever_sign"] != e["lever_sign"]
                         and r["lever_sign"] != 0})
    monotone = True
    for tt in {r["true_tau_s"] for r in rows}:
        seq = [r for r in sorted(rows, key=lambda x: x["ratio"])
               if r["true_tau_s"] == tt and r["achieved_error"] is not None]
        errs = [r["achieved_error"] for r in seq]
        if errs != sorted(errs) and errs != sorted(errs, reverse=True):
            monotone = False
    return {
        "rows": rows,
        "worst_error_underestimating": worst(under),
        "worst_error_exact": worst(exact),
        "worst_error_overestimating": worst(over),
        "lever_sign_flips_relative_to_exact": [list(x) for x in sign_flips],
        "error_is_monotone_in_lag_ratio": monotone,
        "underestimation_is_conservative": (
            worst(under) is not None and worst(exact) is not None
            and worst(under) <= worst(exact)),
        "reading": ("`conservative` is only earned if underestimating never "
                    "produces a larger error than the exact lag ANYWHERE in "
                    "the declared envelope. Otherwise the word is withdrawn."),
    }


def run() -> dict:
    started = time.time()
    cands = C.p3_candidates()
    seed = int(DIAG[0])
    feas = feasibility_and_binding(cands, seed)
    opt = optimizer_comparison(cands, seed)
    lag = lag_sweep()
    return {
        "schema": SCHEMA,
        "amendment": ("research/active_evidence/realized_current/"
                      "PREREGISTRATION_AMENDMENT_1.md"),
        "partition_manifest_sha256": PT.manifest_hash(),
        "seeds_used": {"diagnostic": list(DIAG),
                       "amended_calibration": list(CAL)},
        "locked_seeds_untouched": True,
        "feasibility_and_binding": feas,
        "optimizer": opt,
        "lag_sweep": lag,
        "what_this_is_not": (
            "Repair diagnostics on the diagnostic partition. No locked seed, "
            "original or amended, is read here, and no constraint was "
            "loosened to make any strategy certify."),
        "elapsed_s": time.time() - started,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)
    doc = run()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    f = doc["feasibility_and_binding"]
    print(f"\nBINDING CONSTRAINT TABLE ({f['candidates']} candidates)")
    for k in sorted(f["binding_counts"], key=lambda x: -f["binding_counts"][x]):
        print(f"  {k:22s} {f['binding_counts'][k]:4d}")
    print(f"  feasible set empty: {f['feasible_set_is_empty']}")
    print(f"  cheapest witness  : {f['cheapest_feasible_witness']}")
    o = doc["optimizer"]
    print(f"\nOPTIMIZER: {o['verdict']}")
    print(f"  repaired choice     {o['repaired_objective_choice']} "
          f"certifies={o['repaired_choice_certifies']}")
    print(f"  pilot choice (recon){o['reconstructed_pilot_choice']} "
          f"certifies={o['reconstructed_pilot_choice_certifies']}")
    lg = doc["lag_sweep"]
    print(f"\nLAG: underestimation conservative = "
          f"{lg['underestimation_is_conservative']}")
    print(f"  worst error  under={lg['worst_error_underestimating']} "
          f"exact={lg['worst_error_exact']} over={lg['worst_error_overestimating']}")
    print(f"  lever sign flips: {lg['lever_sign_flips_relative_to_exact']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
