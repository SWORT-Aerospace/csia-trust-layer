"""A SECOND, INDEPENDENT reduction of the E1 raw traces.

WHY A SECOND REDUCTION
----------------------
Every published E1 number passed through exactly one program. If that
program has a bug, nothing in the repository would show it: the artifact,
the claim table and the paper all descend from the same reduction, so they
agree with each other by construction and would agree just as loudly if it
were wrong.

The archive exists precisely so this can be checked. `raw_traces` in the
result file says it plainly: "RAW FIRST. The full per-step traces are
archived gzipped ... BEFORE this reduction. This file is derived and can be
deleted and regenerated; the archive cannot."

WHAT MAKES THIS INDEPENDENT
---------------------------
It was written from the TRACE FORMAT and the PREREGISTERED WINDOW
DEFINITIONS, not from `extract_trust_a2.py`. The original extractor was
not read while writing it. The aggregation rule was recovered by testing
candidates against one published trial -- mean, median and last-value --
and the median reproduced the published figure to the last digit while the
others did not. That is a reconstruction of the rule from the data, which
is what an independent reduction is allowed to do; copying the rule out of
the original program is what it is not.

WHAT A MATCH DOES AND DOES NOT ESTABLISH
----------------------------------------
It establishes that the published numbers follow from the archived traces
under a plainly-stated rule. It does NOT establish that the traces
describe reality, that the windows were the right windows, or that the
experiment answers its question. A second reduction checks arithmetic and
bookkeeping, not physics.

    python tools/csia_experiment/reduce_e1_independently.py --check
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

RESULTS = os.path.join(ROOT, "research", "physical_validation", "results")

CAMPAIGNS = (
    {"id": "A2_ARDUPILOT",
     "published": "mechanism_a_a2_trust_ardupilot.json",
     "archive": "a2_traces_raw"},
    {"id": "P1_PX4",
     "published": "mechanism_a_p1_trust_px4.json",
     "archive": "p1_traces_raw"},
)

#: The node whose trust the campaign is about. Named here rather than
#: inferred, because a reduction that silently picks a different node would
#: produce plausible numbers about the wrong thing.
NODE = "gps"


def _steps(archive: str, trace_name: str) -> list:
    path = os.path.join(RESULTS, archive, trace_name)
    with gzip.open(path, "rt") as fh:
        return [r for r in (json.loads(line) for line in fh)
                if r.get("record") == "step"]


def _window_median(steps, lo: float, hi: float, node: str):
    """Median trust over [lo, hi), and the step count.

    Half-open on the right: the published n_steps for a 1.0 s window at
    25 Hz is 25, not 26, which is what a half-open interval gives.
    """
    values = [s["trust"][node] for s in steps if lo <= s["t"] < hi]
    if not values:
        return None, 0
    return statistics.median(values), len(values)


def reduce_campaign(campaign: dict) -> dict:
    published_path = os.path.join(RESULTS, campaign["published"])
    if not os.path.exists(published_path):
        return {"campaign": campaign["id"], "error": "published file absent"}
    with open(published_path, encoding="utf-8") as fh:
        published = json.load(fh)

    windows = {k: (float(v[0]), float(v[1]))
               for k, v in published["windows"].items()}
    archive_dir = os.path.join(RESULTS, campaign["archive"])
    if not os.path.isdir(archive_dir):
        return {"campaign": campaign["id"], "error": "trace archive absent"}

    trials, mismatches, missing = [], [], []
    for trial in published["trials"]:
        name = trial.get("trace")
        if not name or not os.path.exists(os.path.join(archive_dir, name)):
            missing.append(trial.get("trial_id"))
            continue
        steps = _steps(campaign["archive"], name)

        recomputed = {}
        for wname, (lo, hi) in windows.items():
            median, n = _window_median(steps, lo, hi, NODE)
            recomputed[wname] = {"trust": median, "n_steps": n}

        pre = recomputed["PRE"]["trust"]
        post = recomputed["POST"]["trust"]
        delta = None if (pre is None or post is None) else post - pre

        row = {"trial_id": trial.get("trial_id"), "arm": trial.get("arm"),
               "validity": trial.get("validity"),
               "trust_pre": pre, "trust_post": post, "trust_delta": delta,
               "n_steps_total": len(steps)}
        trials.append(row)

        # Compare against the published values for this trial.
        for field, mine in (("trust_pre", pre), ("trust_post", post),
                            ("trust_delta", delta)):
            theirs = trial.get(field)
            if theirs is None or mine is None:
                continue
            if abs(mine - theirs) > 1e-12:
                mismatches.append({
                    "trial_id": trial.get("trial_id"), "field": field,
                    "published": theirs, "independent": mine,
                    "difference": mine - theirs})
        for wname, wvals in (trial.get("windows") or {}).items():
            if wname not in recomputed:
                continue
            if wvals.get("n_steps") != recomputed[wname]["n_steps"]:
                mismatches.append({
                    "trial_id": trial.get("trial_id"),
                    "field": f"windows.{wname}.n_steps",
                    "published": wvals.get("n_steps"),
                    "independent": recomputed[wname]["n_steps"]})
            mine_t = recomputed[wname]["trust"]
            if (wvals.get("trust") is not None and mine_t is not None
                    and abs(mine_t - wvals["trust"]) > 1e-12):
                mismatches.append({
                    "trial_id": trial.get("trial_id"),
                    "field": f"windows.{wname}.trust",
                    "published": wvals["trust"], "independent": mine_t,
                    "difference": mine_t - wvals["trust"]})

    # The campaign-level distribution, recomputed from my own per-trial rows.
    fault = [t["trust_delta"] for t in trials
             if t["arm"] == "FAULT" and t["validity"] == "VALID"
             and t["trust_delta"] is not None]
    fault.sort()
    #: BOTH QUARTILE DEFINITIONS, because "IQR" is not one number.
    #: The published artifact's `statistics_policy` promises "N, median, min,
    #: max and IQR at the TRIAL level" and never says WHICH quartile
    #: definition. The first version of this reducer picked `inclusive` and
    #: disagreed with the published q1/q3/iqr -- not because either was
    #: wrong, but because they are different statistics. On A2 the two
    #: differ by 8% of the IQR (1.19e-5 against 1.29e-5), which is the third
    #: significant figure of a headline number.
    #: They are reported side by side rather than one being chosen, and the
    #: comparison below records which one the published figures used.
    dist, dist_alt = {}, {}
    if fault:
        base = {"n": len(fault), "median": statistics.median(fault),
                "min": fault[0], "max": fault[-1]}
        for method, target in (("exclusive", dist), ("inclusive", dist_alt)):
            q = statistics.quantiles(fault, n=4, method=method)
            target.update(base)
            target.update({"q1": q[0], "q3": q[2], "iqr": q[2] - q[0],
                           "quartile_method": method})

    pub_dist = published.get("question_B_fault_delta_distribution") or {}

    def _diff(candidate):
        out = []
        for key in ("n", "median", "min", "max", "q1", "q3", "iqr"):
            if key not in pub_dist or key not in candidate:
                continue
            a, b = candidate[key], pub_dist[key]
            if isinstance(a, int) and isinstance(b, int):
                if a != b:
                    out.append({"field": key, "published": b,
                                "independent": a})
            elif abs(a - b) > 1e-12:
                out.append({"field": key, "published": b, "independent": a,
                            "difference": a - b})
        return out

    by_method = {"exclusive": _diff(dist), "inclusive": _diff(dist_alt)}
    matching = [m for m, d in by_method.items() if not d]
    # The published numbers are reproduced under whichever definition they
    # used; a disagreement is only real if NEITHER reproduces them.
    dist_mismatch = [] if matching else by_method["exclusive"]

    positive = sum(1 for t in trials if t["arm"] == "FAULT"
                   and t["validity"] == "VALID"
                   and (t["trust_delta"] or 0) > 0)
    pub_primary = published.get("primary_question_A_does_trust_increase") or {}

    return {
        "campaign": campaign["id"],
        "trials_reduced": len(trials),
        "traces_missing": missing,
        "per_trial_mismatches": mismatches,
        "distribution_independent_exclusive": dist,
        "distribution_independent_inclusive": dist_alt,
        "distribution_published": {k: pub_dist.get(k) for k in
                                   ("n", "median", "min", "max", "q1", "q3",
                                    "iqr")},
        "quartile_methods_that_reproduce_the_published_figures": matching,
        "distribution_differences_by_method": by_method,
        "distribution_mismatches": dist_mismatch,
        "n_median_min_max_agree": not [
            m for m in by_method["exclusive"]
            if m["field"] in ("n", "median", "min", "max")],
        "fault_trials_with_positive_delta_independent": positive,
        "fault_trials_with_positive_delta_published":
            pub_primary.get("fault_trials_with_positive_delta"),
        "agrees": (not mismatches and not dist_mismatch and not missing
                   and positive == pub_primary.get(
                       "fault_trials_with_positive_delta")),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    campaigns = [reduce_campaign(c) for c in CAMPAIGNS]
    report = {
        "schema": "csia.e1.independent_reduction/1",
        "node": NODE,
        "rule": ("median of the node's trust over each half-open window; "
                 "trust_delta = POST - PRE"),
        "how_the_rule_was_obtained": (
            "reconstructed by testing mean, median and last-value against a "
            "single published trial. The median reproduced it to the last "
            "digit and the others did not. The original extractor was not "
            "read."),
        "what_agreement_establishes": (
            "that the published numbers follow from the archived traces "
            "under a stated rule. NOT that the traces describe reality, "
            "that the windows were the right windows, or that the "
            "experiment answers its question."),
        "campaigns": campaigns,
        "all_agree": all(c.get("agrees") for c in campaigns),
    }

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"wrote {args.out}")

    for c in campaigns:
        if "error" in c:
            print(f"{c['campaign']}: {c['error']}")
            continue
        print(f"{c['campaign']}: {c['trials_reduced']} trials, "
              f"{len(c['per_trial_mismatches'])} per-trial mismatches, "
              f"{len(c['distribution_mismatches'])} distribution mismatches "
              f"-> {'AGREES' if c['agrees'] else 'DISAGREES'}")
    if not report["all_agree"]:
        print("\nINDEPENDENT REDUCTION DISAGREES WITH THE PUBLISHED RESULT",
              file=sys.stderr)
        return 1
    print("\nINDEPENDENT REDUCTION AGREES", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
