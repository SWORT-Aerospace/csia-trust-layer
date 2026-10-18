"""Formal results, the minimal counterexample, information loss, compute cost.

Items 15, 16, 17, 23, 24, 35. Everything here is derived from the frozen
constants in csia/diagnosis/bayes.py and then CHECKED against the measured
replays, so a wrong derivation shows up as a mismatch rather than as prose.

Notation (item 15):

  X_j(t)  numerical measurement            V_j(t)  source-reported validity
  P_j(t)  provenance state                 A_j(t)  operational admissibility
  D_j(t)  diagnostic evidential admissibility

  coupled architecture   D_j = A_j
  split architecture     D_j may differ from A_j

DiagnosisCore, verbatim from source:

  ell_{j,h}(t) = log(1 - c_j + eps)   if j in LOW(h)
                 log(c_j + eps)       otherwise
  ll_h(t)      = sum_j D_j(t) * ell_{j,h}(t)
  S_h(t)       = (1-alpha) S_h(t-1) + alpha * ll_h(t)
  score_h      = log pi_h + M * S_h
  posterior    = softmax(score)
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import statistics
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
ONSET = 12.0


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", os.path.join(
    ROOT, "research", "invalidity_masking", "masking_harness.py"))
R = _load("_dual_replay", os.path.join(_HERE, "dual_replay.py"))
A = _load("_dual_arms", os.path.join(_HERE, "dual_arms.py"))
PT = _load("_pat", os.path.join(_HERE, "pattern_and_transport.py"))


def constants():
    from csia.diagnosis.bayes import (CAUSES, EPS, EVIDENCE_MULT,
                                      PRIOR_NOMINAL, SMOOTH_ALPHA)
    k = len(CAUSES)
    return {
        "EPS": EPS, "SMOOTH_ALPHA": SMOOTH_ALPHA,
        "EVIDENCE_MULT": EVIDENCE_MULT, "PRIOR_NOMINAL": PRIOR_NOMINAL,
        "n_causes": k,
        "prior_nominal": PRIOR_NOMINAL,
        "prior_fault": (1.0 - PRIOR_NOMINAL) / (k - 1),
    }


def delta(c, eps):
    """The per-feature discriminating increment.

    For a feature j in LOW(a) but not LOW(b), the pairwise contribution to
    Delta_ab is +delta(c); for j in LOW(b) only it is -delta(c); for j in both
    or neither it is exactly zero. Decreasing in c, zero at c = 1/2.
    """
    return math.log((1.0 - c + eps) / (c + eps))


def formal_results():
    K = constants()
    eps, alpha, M = K["EPS"], K["SMOOTH_ALPHA"], K["EVIDENCE_MULT"]
    pa, pb = K["prior_fault"], K["prior_nominal"]
    log_prior_ratio = math.log(pa / pb)
    d0, d1 = delta(0.0, eps), delta(1.0, eps)

    # T1 --------------------------------------------------------------
    t1 = {
        "id": "T1_EVIDENCE_DELETION",
        "statement":
            "Delta_ab(t) = sum over j in LOW(a) symmetric-difference LOW(b) of "
            "+/- D_j(t) delta(c_j(t)). Every feature in both LOW sets or in "
            "neither contributes exactly zero. Therefore if D_j(t) = 0 for "
            "every j in that symmetric difference, Delta_ab(t) = 0 and the "
            "tick carries no information distinguishing a from b.",
        "proof": "ell_{j,a} - ell_{j,b} is log(1-c+eps) - log(c+eps) when j is "
                 "in LOW(a) only, its negation when in LOW(b) only, and 0 "
                 "otherwise since both terms are then identical. Multiply by "
                 "D_j and sum.",
        "status": "PROVED - NOVELTY NOT ESTABLISHED",
    }

    # T2 --------------------------------------------------------------
    t2 = {
        "id": "T2_SELF_MASKING_FAULT",
        "statement":
            "Call a fault F self-masking for the pair (a,b) under coupling if "
            "(i) F drives A_k -> 0 for a set of relations K, and (ii) "
            "LOW(a) symmetric-difference LOW(b) is a subset of K. Under D = A, "
            "Delta_ab(t) = 0 for every tick F is active: the hypothesis the "
            "fault supports is unidentifiable from its alternative exactly "
            "while the fault is happening. Condition (ii) is necessary as "
            "well as sufficient for Delta to vanish identically.",
        "instance_in_this_system":
            "a = gps_fault, b = nominal. LOW(gps_fault) = ['phys_gps'], "
            "LOW(nominal) = []. The symmetric difference is {phys_gps}, whose "
            "gate is gvalid * (tau>3) * fresh['gps'] -- and fresh['gps'] is "
            "exactly A_gps. A GNSS fault that makes the receiver report no "
            "fix therefore satisfies (i) and (ii) simultaneously.",
        "status": "PROVED - NOVELTY NOT ESTABLISHED",
    }

    # T3 --------------------------------------------------------------
    t3 = {
        "id": "T3_WHAT_THE_SPLIT_CAN_AND_CANNOT_RESTORE",
        "statement":
            "Splitting D from A restores identifiability for (a,b) during F if "
            "and only if there exists an observable j' with j' in "
            "LOW(a) symmetric-difference LOW(b) and D_{j'} > 0 while F is "
            "active. NECESSARY as well as sufficient: with no such j' every "
            "term of Delta_ab is zero regardless of how D is gated.",
        "corollary":
            "If the fault removes the SOURCE rather than the value -- transport "
            "loss, a dead receiver, a severed link -- no such j' exists, and "
            "the split provably cannot help. This is a PREDICTION, and the "
            "transport control tests it.",
        "status": "PROVED - NOVELTY NOT ESTABLISHED",
    }

    # T4: steady state, which is where the numbers come from -----------
    # Sustained fault, one discriminating feature pinned at c.
    def steady_posterior_ratio(c, d_on):
        s = delta(c, eps) if d_on else 0.0
        return log_prior_ratio + M * s

    lr_coupled = steady_posterior_ratio(0.0, False)
    lr_split = steady_posterior_ratio(0.0, True)
    t4 = {
        "id": "T4_STEADY_STATE_POSTERIOR",
        "statement":
            "Under a sustained fault the smoother converges, so "
            "log P(a)/P(b) -> log(pi_a/pi_b) + M * delta(c). With D = 0 the "
            "second term vanishes and the ratio returns to the PRIOR ratio: "
            "the diagnosis reverts to nominal no matter how severe the fault.",
        "numbers": {
            "log_prior_ratio": round(log_prior_ratio, 6),
            "delta_at_c0": round(d0, 6),
            "delta_at_c1": round(d1, 6),
            "log_ratio_coupled_sustained": round(lr_coupled, 6),
            "log_ratio_split_sustained": round(lr_split, 6),
            "two_hypothesis_posterior_coupled":
                round(1.0 / (1.0 + math.exp(-lr_coupled)), 6),
            "two_hypothesis_posterior_split":
                round(1.0 / (1.0 + math.exp(-lr_split)), 6),
        },
        "status": "PROVED - NOVELTY NOT ESTABLISHED",
    }

    # T5: how long the reversal takes ---------------------------------
    # S decays geometrically toward the new ll; rank flips when
    # M * (S_a - S_b) falls below -log_prior_ratio.
    thresh = -log_prior_ratio / M
    d_before = d1                      # healthy: c = 1 -> delta < 0
    # Delta starts wherever it was; the interesting case is a fault that had
    # been visible (Delta_0 = delta(0)) and is then gated off.
    ratio = thresh / d0 if d0 > 0 else None
    n_ticks = (math.log(ratio) / math.log(1.0 - alpha)
               if ratio and 0 < ratio < 1 else None)
    t5 = {
        "id": "T5_TIME_TO_RANK_REVERSAL",
        "statement":
            "After D is gated off, S_a - S_b decays as (1-alpha)^n toward "
            "zero, so the rank reverses once M * Delta_0 * (1-alpha)^n < "
            "-log(pi_a/pi_b). n = log(threshold/Delta_0)/log(1-alpha).",
        "numbers": {
            "threshold_smoothed_diff": round(thresh, 6),
            "delta_0_if_previously_saturated": round(d0, 6),
            "ticks_to_reversal": (None if n_ticks is None
                                  else round(n_ticks, 3)),
            "seconds_to_reversal_at_25hz": (None if n_ticks is None
                                            else round(n_ticks / 25.0, 4)),
            "delta_when_healthy": round(d_before, 6),
        },
        "status": "PROVED - NOVELTY NOT ESTABLISHED",
    }
    return K, [t1, t2, t3, t4, t5]


def minimal_counterexample():
    """The smallest system exhibiting the effect, solved in closed form."""
    K = constants()
    eps, M = K["EPS"], K["EVIDENCE_MULT"]
    pa, pb = K["prior_fault"], K["prior_nominal"]

    rows = []
    for label, c_value, d_value, c_status, d_status in (
            ("healthy", 1.0, 1.0, 1.0, 1.0),
            ("fault, coupled (D=A=0)", 0.0, 0.0, 0.0, 0.0),
            ("fault, split (value D=0, status D=1)", 0.0, 0.0, 0.0, 1.0)):
        s = (d_value * delta(c_value, eps)
             + d_status * delta(c_status, eps))
        lr = math.log(pa / pb) + M * s
        rows.append({
            "regime": label,
            "c_value": c_value, "D_value": d_value,
            "c_status": c_status, "D_status": d_status,
            "steady_smoothed_delta": round(s, 6),
            "log_posterior_ratio": round(lr, 6),
            "P_fault_two_hypothesis": round(1.0 / (1.0 + math.exp(-lr)), 6),
        })
    return rows


def information_loss():
    """Item 23/24, on EXACT distributions rather than estimated ones.

    The empirical support is one recording, which is not enough to estimate a
    KL divergence honestly. So the mapping phi is applied to exactly specified
    upstream distributions instead, and the loss is computed in closed form.

    Upstream alphabet: OBSERVED_VALID, OBSERVED_INVALID, NOT_OBSERVED.
    Two worlds: P_a = a receiver that has failed (mostly OBSERVED_INVALID),
    P_b = a link that has failed (mostly NOT_OBSERVED). Both produce the same
    downstream symbol under a collapsing phi.
    """
    def kl(p, q):
        return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0)

    # (VALID, INVALID, NOT_OBSERVED)
    p_receiver_failed = [0.05, 0.90, 0.05]
    p_link_failed = [0.05, 0.05, 0.90]
    up = kl(p_receiver_failed, p_link_failed)

    maps = {
        "phi_S0_drop_invalid": {
            "description": "OBSERVED_INVALID and NOT_OBSERVED both become "
                           "NO_UPDATE; only OBSERVED_VALID survives",
            "classes": [[0], [1, 2]],
        },
        "phi_S1_coupled": {
            "description": "invalidity is propagated, but D = A means the "
                           "downstream diagnostic vocabulary is still "
                           "{evidence, no evidence}",
            "classes": [[0], [1, 2]],
        },
        "phi_S2_split": {
            "description": "OBSERVED_INVALID keeps a distinct downstream "
                           "symbol because status evidence survives A = 0",
            "classes": [[0], [1], [2]],
        },
    }
    out = {}
    for name, spec in maps.items():
        pa2 = [sum(p_receiver_failed[i] for i in cls)
               for cls in spec["classes"]]
        pb2 = [sum(p_link_failed[i] for i in cls) for cls in spec["classes"]]
        down = kl(pa2, pb2)
        out[name] = {
            "description": spec["description"],
            "downstream_classes": spec["classes"],
            "D_KL_downstream_nats": round(down, 6),
            "information_loss_nats": round(up - down, 6),
            "semantic_collapse_count": 3 - len(spec["classes"]),
        }
    return {
        "upstream_alphabet": ["OBSERVED_VALID", "OBSERVED_INVALID",
                              "NOT_OBSERVED"],
        "P_receiver_failed": p_receiver_failed,
        "P_link_failed": p_link_failed,
        "D_KL_upstream_nats": round(up, 6),
        "mappings": out,
        "caveat": "These are EXACT numbers for the stated hypothetical "
                  "distributions, chosen to make the two worlds differ only "
                  "in which of the two collapsed symbols dominates. They are "
                  "NOT estimates from data: one recording cannot support a KL "
                  "estimate and none is offered.",
        "not_claimed": "The data-processing inequality is textbook. Nothing "
                       "here claims it, or this application of it, is novel.",
    }


def validate_against_replay(theory):
    """Do the closed-form predictions match the measured replays?"""
    cap = H.load_fixture(FIXTURE)
    carrier, gps = H.carrier_and_gps(cap["messages"])
    template = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                    and int(m.get("satellites_visible", 0) or 0) >= 10)
    msgs = PT.build(carrier, template, PT.PATTERNS["P5_PERMANENT"][1])

    checks = []
    for arm, key in (("S1D", "two_hypothesis_posterior_coupled"),
                     ("S2a", "two_hypothesis_posterior_split")):
        out = R.replay(msgs, arm)
        final = out["rows"][-1]["post_gps_fault"]
        pred = theory["numbers"][key]
        checks.append({
            "arm": arm,
            "regime": ("coupled, sustained fault" if arm == "S1D"
                       else "split, sustained fault"),
            "predicted_two_hypothesis": pred,
            "measured_eight_hypothesis_final": final,
            "abs_difference": round(abs(pred - final), 6),
            "note": "the closed form is a two-hypothesis reduction; the "
                    "measurement runs the full eight-cause softmax, so exact "
                    "equality is not expected and the gap is the contribution "
                    "of the other six causes",
        })
    return checks


def compute_cost():
    """Item 35: what the split actually costs, measured."""
    cap = H.load_fixture(FIXTURE)
    msgs = cap["messages"]
    out = {}
    for arm in ("S0", "S1", "S2c"):
        t0 = time.perf_counter()
        res = R.replay(msgs, arm)
        wall = time.perf_counter() - t0
        n = res["n_ticks"]
        out[arm] = {
            "wall_s": round(wall, 3),
            "n_ticks": n,
            "us_per_tick_mean": round(wall / n * 1e6, 2),
        }
    side = A.GnssStatusSidecar()
    out["additional_state_per_sensor"] = {
        "fields": sorted(vars(side)),
        "n_fields": len(vars(side)),
        "bytes_estimate": sum(sys.getsizeof(v) for v in vars(side).values()),
        "note": "five scalars and a mode string per monitored source; the "
                "cost is not in the state, it is in one extra feature per "
                "tick in an already-linear likelihood loop",
    }
    out["additional_features_per_tick"] = {
        "S0": 0, "S1": 0, "S2a": 1, "S2b": 1, "S2c": 2}
    out["caveat"] = ("wall time here includes MAVLink decoding and the whole "
                     "adapter path, so the per-tick figures are an upper "
                     "bound on the arm's own cost, not a measurement of it")
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    K, theorems = formal_results()
    t4 = next(t for t in theorems if t["id"] == "T4_STEADY_STATE_POSTERIOR")

    print("FORMAL")
    for t in theorems:
        print(f"  {t['id']:<34} {t['status']}")
    print(f"  log prior ratio          "
          f"{t4['numbers']['log_prior_ratio']}")
    print(f"  delta(c=0)               {t4['numbers']['delta_at_c0']}")
    print(f"  P(fault) coupled  steady "
          f"{t4['numbers']['two_hypothesis_posterior_coupled']}")
    print(f"  P(fault) split    steady "
          f"{t4['numbers']['two_hypothesis_posterior_split']}")

    checks = validate_against_replay(t4)
    print("\nPREDICTION vs MEASUREMENT (P5_PERMANENT, sustained invalidity)")
    for c in checks:
        print(f"  {c['arm']:<4} predicted {c['predicted_two_hypothesis']}  "
              f"measured {c['measured_eight_hypothesis_final']}  "
              f"|diff| {c['abs_difference']}")

    mc = minimal_counterexample()
    print("\nMINIMAL COUNTEREXAMPLE (2 hypotheses, 2 features, closed form)")
    for r in mc:
        print(f"  {r['regime']:<38} P(fault) = "
              f"{r['P_fault_two_hypothesis']}")

    il = information_loss()
    print("\nINFORMATION LOSS (exact, stated distributions)")
    print(f"  upstream D_KL = {il['D_KL_upstream_nats']} nats")
    for n, v in il["mappings"].items():
        print(f"  {n:<24} downstream {v['D_KL_downstream_nats']}  "
              f"loss {v['information_loss_nats']}  "
              f"collapsed {v['semantic_collapse_count']}")

    cc = compute_cost()
    print("\nCOMPUTE")
    for arm in ("S0", "S1", "S2c"):
        print(f"  {arm:<4} {cc[arm]['us_per_tick_mean']} us/tick "
              f"({cc[arm]['n_ticks']} ticks)")

    with open(os.path.join(OUT, "FORMAL_RESULTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "FORMAL_RESULTS",
                   "frozen_constants": K,
                   "theorems": theorems,
                   "prediction_vs_measurement": checks,
                   "minimal_counterexample": mc}, fh, indent=2,
                  sort_keys=True)
        fh.write("\n")
    with open(os.path.join(OUT, "INFORMATION_LOSS_ANALYSIS.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "INFORMATION_LOSS_ANALYSIS", **il}, fh,
                  indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(OUT, "COMPUTE_COST.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "COMPUTE_COST", **cc}, fh, indent=2,
                  sort_keys=True)
        fh.write("\n")
    print(f"\n  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
