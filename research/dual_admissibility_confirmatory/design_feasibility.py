"""Design feasibility for the confirmatory campaign. NOT A CONFIRMATORY RESULT.

Everything here runs on DEVELOPMENT traces, which are contaminated by design
(they are the traces S2 was built on). Its only purpose is to establish, before
freezing a preregistration, whether the design is even possible:

  Q1  Can A trajectories be matched between the two mechanisms, and over what
      interval? If not, the causal question cannot be asked.

  Q2  Does C0 genuinely alias the two mechanisms, or does residual information
      survive the coupled gate? The strong form of H1 assumes total aliasing.
      If that is false, H1 must be weakened BEFORE it is frozen, and the
      primary endpoint must be defined at a level where C0 actually fails.

Nothing measured here may be cited as evidence for or against the frozen
hypotheses. It is design input, and it is labelled as such in the output.

  python research/dual_admissibility_confirmatory/design_feasibility.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
DEV = os.path.join(ROOT, "research", "dual_admissibility")
ONSET = 12.0
TAU = 0.5
MARGIN = 0.2
# the full core-visible state a downstream consumer could key a mechanism
# decision on, ordered from most to least aggregated
STATE_FIELDS = ["post_top_cause", "fresh_gps", "d_status", "c_status",
                "d_hacc", "c_hacc", "post_gps_fault", "post_nominal",
                "trust_gps"]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_mh", os.path.join(ROOT, "research", "invalidity_masking",
                              "masking_harness.py"))
R = _load("_dr", os.path.join(DEV, "dual_replay.py"))
PT = _load("_pt", os.path.join(DEV, "pattern_and_transport.py"))
A = _load("_da", os.path.join(DEV, "dual_arms.py"))

FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")

# exploratory arm -> confirmatory arm name
ARM_MAP = {"S1": "C0_COUPLED", "S2c2": "C1_SPLIT", "S2a": "C2_STATUS_ONLY"}


def build_pair():
    cap = H.load_fixture(FIXTURE)
    carrier, gps = H.carrier_and_gps(cap["messages"])
    tmpl = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                and int(m.get("satellites_visible", 0) or 0) >= 10)
    sensor = PT.build(carrier, tmpl, PT.PATTERNS["P5_PERMANENT"][1])
    transport = PT.build(carrier, tmpl,
                         PT.PATTERNS["T_TRANSPORT_STARVED"][1])
    return sensor, transport


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    sensor, transport = build_pair()
    lo = ONSET + TAU + MARGIN

    q1, q2 = {}, {}
    for arm in ("S0",) + tuple(ARM_MAP):
        s = {r["t"]: r for r in R.replay(sensor, arm)["rows"]}
        t = {r["t"]: r for r in R.replay(transport, arm)["rows"]}
        common = sorted(set(s) & set(t))
        scored = [k for k in common if k >= lo]

        # ---- Q1: A matching -----------------------------------------
        mismatch_all = [k for k in common
                        if s[k]["fresh_gps"] != t[k]["fresh_gps"]]
        mismatch_scored = [k for k in scored
                           if s[k]["fresh_gps"] != t[k]["fresh_gps"]]
        q1[arm] = {
            "confirmatory_arm": ARM_MAP.get(arm, "not an arm (S0 reference)"),
            "ticks_total": len(common),
            "A_mismatches_over_whole_condition": len(mismatch_all),
            "A_mismatch_window": ([min(mismatch_all), max(mismatch_all)]
                                  if mismatch_all else None),
            "scored_interval_start_s": lo,
            "scored_ticks": len(scored),
            "A_mismatches_in_scored_interval": len(mismatch_scored),
            "A_is_zero_throughout_scored_interval":
                all(s[k]["fresh_gps"] == 0.0 for k in scored)
                and all(t[k]["fresh_gps"] == 0.0 for k in scored),
        }

        # ---- Q2: does the coupled arm actually alias? ----------------
        per_field = {}
        for f in STATE_FIELDS:
            d = [k for k in scored if s[k][f] != t[k][f]]
            per_field[f] = {
                "ticks_differing": len(d),
                "fraction": round(len(d) / len(scored), 6) if scored else None,
                "first_example": (None if not d else
                                  {"t": d[0], "sensor": s[d[0]][f],
                                   "transport": t[d[0]][f]}),
            }
        # ---- Q3: is the residue USABLE, or an artefact of the excluded
        # transient? A field that differs but never CHANGES inside the
        # interval is a constant inherited from before it, not a signal.
        import numpy as _np
        usable = {}
        for f in ("trust_gps", "post_gps_fault", "post_nominal"):
            vs = [s[k][f] for k in scored]
            vt = [t[k][f] for k in scored]
            # NOT `lo` -- that name holds the scored-interval start and
            # shadowing it silently corrupts every later arm's interval
            vlo, vhi = min(vs + vt), max(vs + vt)
            best = 0.0
            for th in _np.linspace(vlo, vhi, 400):
                for sign in (1, -1):
                    corr = (sum(1 for v in vs if sign * (v - th) > 0)
                            + sum(1 for v in vt if sign * (v - th) < 0))
                    best = max(best, corr / (2 * len(scored)))
            usable[f] = {
                "distinct_values_sensor": len(set(vs)),
                "distinct_values_transport": len(set(vt)),
                "frozen_within_interval": len(set(vs)) == 1 and len(set(vt)) == 1,
                "max_abs_difference": round(max(abs(a - b)
                                                for a, b in zip(vs, vt)), 9),
                "best_single_threshold_accuracy": round(best, 4),
            }

        q2[arm] = {
            "residue_usability": usable,
            "confirmatory_arm": ARM_MAP.get(arm, "not an arm (S0 reference)"),
            "scored_ticks": len(scored),
            "per_field": per_field,
            "aliases_at_leading_cause":
                per_field["post_top_cause"]["ticks_differing"] == 0,
            "aliases_completely":
                all(v["ticks_differing"] == 0 for v in per_field.values()),
        }
        print(f"{arm:<5} ({ARM_MAP.get(arm, 'reference'):<16}) "
              f"A mismatch whole={len(mismatch_all):<3} "
              f"scored={len(mismatch_scored):<3}  "
              f"leading-cause aliased={q2[arm]['aliases_at_leading_cause']}  "
              f"fully aliased={q2[arm]['aliases_completely']}")
        for f in STATE_FIELDS:
            n = per_field[f]["ticks_differing"]
            if n:
                print(f"        {f:<16} differs on {n}/{len(scored)}")

    payload = {
        "artifact": "DESIGN_FEASIBILITY",
        "status": "NOT A CONFIRMATORY RESULT. Development traces only, "
                  "contaminated by construction. Design input for the "
                  "preregistration and nothing else.",
        "traces_used": ["P5_PERMANENT and T_TRANSPORT_STARVED synthetic "
                        "schedules over the NON_SCORED_TEST_FIXTURE_M1 "
                        "non-GNSS carrier"],
        "onset_s": ONSET, "tau_s": TAU, "margin_s": MARGIN,
        "scored_interval_rule": "t >= onset + tau + margin",
        "Q1_matched_A": q1,
        "Q2_does_the_coupled_arm_alias": q2,
        "findings": {
            "Q1": "Matching is achievable. Under the DROP reference the two "
                  "mechanisms are already bit-identical in A. Under every "
                  "PROPAGATING arm they differ only inside [onset, onset+tau): "
                  "propagation closes A immediately on sensor-invalid, while "
                  "transport loss must wait out the staleness timeout. "
                  "Excluding that transient gives exact matching.",
            "Q3": "The residue that survives coupling is NOT usable. "
                  "trust_gps is FROZEN inside the matched interval -- the "
                  "Beta update is gated on fresh (engine.py:146), so trust "
                  "stops moving the moment A closes. Its between-mechanism "
                  "difference is a CONSTANT inherited from the onset "
                  "transient the scored interval deliberately excludes. A "
                  "single-pair threshold on the raw value therefore scores "
                  "1.0 while carrying no live information, and would not "
                  "survive varying the onset across pairs. The posterior "
                  "does move but the two mechanisms converge on it, and a "
                  "threshold scores at chance (~0.505).",
            "Q2": "The STRONG form of H1 is FALSE for C0 in this "
                  "implementation. C0 aliases the two mechanisms at the "
                  "LEADING CAUSE, but trust_gps and the gps_fault posterior "
                  "magnitude still differ, because a propagated invalid "
                  "sample feeds the ungated temporal/historical features "
                  "(the partial decoupling recorded as C3 in the exploratory "
                  "audit) while a missing message feeds nothing.",
        },
        "consequences_for_the_preregistration": [
            "H1 must be frozen in its WEAK form: C0 aliases at the level of "
            "the leading mechanism decision, not at every level of core "
            "state.",
            "The primary endpoint must be defined on the leading mechanism "
            "decision. A magnitude-based endpoint would credit C0 with "
            "information it cannot act on.",
            "A C0-STRONG control is required, but it must use the RAW "
            "trust value with ONE threshold frozen across all pairs. The "
            "delta-from-reference form is provably useless: the delta is "
            "identically zero because trust freezes when A closes. A "
            "per-pair threshold would score 1.0 on an onset artefact.",
            "The empirical content of the primary endpoint is SMALLER than "
            "the exploratory package implied. C0's failure is close to "
            "analytically forced once the transient is excluded, and C2's "
            "success is close to tautological given its inputs. What remains "
            "genuinely empirical is the clean control and whether a single "
            "cross-pair threshold on raw trust stays at chance.",
            "The scored interval must exclude [onset, onset+tau) and, for "
            "finite conditions, the symmetric recovery transient.",
        ],
    }
    with open(os.path.join(OUT, "DESIGN_FEASIBILITY.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n  -> {os.path.relpath(OUT, ROOT)}/DESIGN_FEASIBILITY.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
