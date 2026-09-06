"""Extract Campaign A2's preregistered trust quantities from the raw traces.

PREREGISTERED IN section 4-6 of
    research/physical_validation/prereg/
    MECHANISM_A_ARDUPILOT_TRUST_COMPLETION_PREREG.md
frozen at commit ceeaf4a before the first A2 trial.

RAW FIRST, DERIVED SECOND. The full per-engine-step trace is archived by the
runner; this reduces it to the four preregistered windows and NOTHING ELSE.
The windows were fixed in the preregistration before any trace existed and are
not adjustable here -- a window moved after seeing a trace is not a
measurement.

    PRE   [10.0, 12.0)    settled pre-fault
    AT    [12.0, 13.0)    the second containing the downstream effect
    POST  [14.0, 20.0)    settled post-fault
    LATE  [20.0, end]     drift check

Each window's value is the MEDIAN over the window, at the TRIAL level. Ticks
are not independent replicates and are never counted as such.

WHAT THIS DOES NOT DO
---------------------
It computes no p-value, no confidence interval and no significance test. These
are runs of a deterministic simulator differing in seed and timing jitter; an
interval over them would describe the simulator's jitter while reading as a
statement about vehicles. The preregistration forbids it in advance.

It also does not decide whether the result is good. The preregistration states
that success is NOT "trust must rise": if the repeat contradicts the n=1
observation, the contradiction is the result.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

PREREG = ("research/physical_validation/prereg/"
          "MECHANISM_A_ARDUPILOT_TRUST_COMPLETION_PREREG.md")

#: FROZEN IN THE PREREGISTRATION. Do not tune.
WINDOWS = {
    "PRE": (10.0, 12.0),
    "AT": (12.0, 13.0),
    "POST": (14.0, 20.0),
    "LATE": (20.0, float("inf")),
}

#: The original n=1 ArduPilot observation this campaign asks about.
ORIGINAL_N1 = {"trust_pre": 0.9213, "trust_post": 0.9300,
               "delta": 0.0087}

GPS_TRACE_EDGES = ("altitude_baro", "velocity_gps_doppler_0",
                   "velocity_gps_doppler_1", "heading_course")


def load_trace(path: str):
    header, steps = None, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("record") == "trace_header":
                header = row
            elif row.get("record") == "step":
                steps.append(row)
    return header, steps


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def gate_weight_sum(step) -> float:
    edges = step.get("edges") or {}
    return sum(float(edges[k][1]) for k in GPS_TRACE_EDGES if k in edges)


def windowed(steps, t0, node="gps"):
    """Per-window medians of every preregistered per-step quantity."""
    out = {}
    for name, (lo, hi) in WINDOWS.items():
        sel = [s for s in steps if lo <= (s["t"] - t0) < hi]
        out[name] = {
            "n_steps": len(sel),
            "trust": _median(s.get("trust", {}).get(node) for s in sel),
            "S": _median((s.get("S") or {}).get(node) for s in sel),
            "evidence": _median(s.get("evidence", {}).get(node) for s in sel),
            "fresh_share": (
                round(sum(1 for s in sel
                          if s.get("fresh", {}).get(node)) / len(sel), 6)
                if sel else None),
            "gate_weight_sum": _median(gate_weight_sum(s) for s in sel),
        }
    return out


def failsafe_levels(steps):
    seen, first_change = [], None
    for s in steps:
        policy = s.get("policy")
        if not policy:
            continue
        level = policy.get("level") if isinstance(policy, dict) else None
        if level is None:
            continue
        if not seen or seen[-1][1] != level:
            seen.append((round(s["t"], 3), level))
    return seen


def extract(trace_path: str, onset_s: float = 12.0) -> dict:
    header, steps = load_trace(trace_path)
    if not steps:
        return {"trace": os.path.basename(trace_path),
                "error": "no step rows"}
    t0 = steps[0]["t"]
    win = windowed(steps, t0)

    pre, post = win["PRE"]["trust"], win["POST"]["trust"]
    return {
        "trace": os.path.basename(trace_path),
        "engine_config": (header or {}).get("engine_config"),
        "tick_hz": (header or {}).get("tick_hz"),
        "n_steps": len(steps),
        "windows": win,
        "trust_pre": pre,
        "trust_post": post,
        "trust_delta": (None if pre is None or post is None else post - pre),
        "failsafe_transitions": failsafe_levels(steps),
        "gate_collapse_t": next(
            (round(s["t"] - t0, 6) for s in steps
             if (s["t"] - t0) >= onset_s and gate_weight_sum(s) == 0.0), None),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="/tmp/a2/trace")
    ap.add_argument("--campaign", default=os.path.join(
        ROOT, "campaigns", "physical_validation",
        "mechanism_a_trust_completion_a2"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--csv", default=None)
    args = ap.parse_args(argv)

    trials = []
    for manifest_path in sorted(glob.glob(os.path.join(args.campaign,
                                                       "MECHA2-*.json"))):
        with open(manifest_path, encoding="utf-8") as fh:
            man = json.load(fh)
        record, trial_id = man["record"], man["trial_id"]
        arm = record.get("arm")
        trace = os.path.join(args.traces, f"{trial_id}_{arm}.trace.jsonl")
        row = {"trial_id": trial_id, "arm": arm,
               "validity": man["adjudication"]["state"],
               "fix_loss_confirmed": (record.get("measured_injection") or {})
               .get("confirmed"),
               "ardupilot_commit": record.get("ardupilot_commit")}
        if not os.path.exists(trace):
            # A trial whose trace is missing contributes NOTHING and is listed
            # rather than dropped -- a denominator that shrinks to what was
            # readable is the defect this whole discipline exists to prevent.
            row["trust_trajectory"] = "NOT_CAPTURED"
            row["error"] = "trace file absent"
        else:
            row.update(extract(trace))
            row["trust_trajectory"] = ("CAPTURED"
                                       if row.get("trust_pre") is not None
                                       else "NOT_CAPTURED")
        trials.append(row)

    def deltas(arm):
        return sorted(t["trust_delta"] for t in trials
                      if t["arm"] == arm and t["validity"] == "VALID"
                      and t.get("trust_delta") is not None)

    def stats(xs):
        if not xs:
            return {"n": 0}
        q = statistics.quantiles(xs, n=4) if len(xs) >= 4 else [None] * 3
        return {"n": len(xs), "median": statistics.median(xs),
                "min": xs[0], "max": xs[-1],
                "q1": q[0], "q3": q[2],
                "iqr": (None if q[0] is None else q[2] - q[0])}

    fault_d, control_d = deltas("FAULT"), deltas("CONTROL")
    inside = (bool(fault_d)
              and fault_d[0] <= ORIGINAL_N1["delta"] <= fault_d[-1])

    summary = {
        "schema": "csia.research.mechanism_a_a2_trust/1",
        "campaign_id": "CAMPAIGN_A2",
        "prereg": PREREG,
        "windows": {k: list(v) for k, v in WINDOWS.items()},
        "statistics_policy": (
            "N, median, min, max and IQR at the TRIAL level. No p-values and "
            "no confidence intervals: these are runs of a deterministic "
            "simulator, not draws from a population."),
        "primary_question_A_does_trust_increase": {
            "fault_trials_with_positive_delta": sum(1 for d in fault_d if d > 0),
            "fault_trials_total": len(fault_d),
            "answer_is_not_a_success_criterion": (
                "the preregistration states success is NOT 'trust must rise'; "
                "a contradiction of the n=1 observation is a result"),
        },
        "question_B_fault_delta_distribution": stats(fault_d),
        "question_C_control_delta_distribution": stats(control_d),
        "question_D_original_n1": {
            **ORIGINAL_N1,
            "inside_repeated_fault_range": inside,
            "fault_range": [fault_d[0], fault_d[-1]] if fault_d else None,
        },
        "trials": trials,
    }

    text = json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)

    if args.csv:
        write_table(trials, args.csv)
        print(f"wrote {args.csv}")
    return 0


TABLE_COLUMNS = [
    "trial_id", "role", "validity", "fix_loss", "pre_live_relations",
    "post_live_relations", "gate_pre", "gate_post", "gate_collapse_latency",
    "nominal_rank_pre", "nominal_rank_post", "gps_fault_rank_pre",
    "gps_fault_rank_post", "nominal_weight_pre", "nominal_weight_post",
    "gps_fault_weight_pre", "gps_fault_weight_post", "trust_pre", "trust_post",
    "trust_delta", "failsafe_pre", "failsafe_post",
]


def write_table(trials, path):
    """The preregistered per-trial table.

    Columns the TRACE cannot supply are written as NOT_CAPTURED rather than
    left blank: a blank cell reads as zero to a spreadsheet, and the whole
    point of A2 is that a missing measurement must be named.
    """
    import csv

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=TABLE_COLUMNS)
        w.writeheader()
        for t in trials:
            win = t.get("windows") or {}
            pre, post = win.get("PRE", {}), win.get("POST", {})
            row = {c: "NOT_CAPTURED" for c in TABLE_COLUMNS}
            row.update({
                "trial_id": t["trial_id"],
                "role": t["arm"],
                "validity": t["validity"],
                "fix_loss": t.get("fix_loss_confirmed"),
                "gate_pre": pre.get("gate_weight_sum"),
                "gate_post": post.get("gate_weight_sum"),
                "gate_collapse_latency": (
                    None if t.get("gate_collapse_t") is None
                    else round(t["gate_collapse_t"] - 12.0, 6)),
                "trust_pre": t.get("trust_pre"),
                "trust_post": t.get("trust_post"),
                "trust_delta": t.get("trust_delta"),
            })
            transitions = t.get("failsafe_transitions") or []
            if transitions:
                row["failsafe_pre"] = transitions[0][1]
                row["failsafe_post"] = transitions[-1][1]
            w.writerow(row)


if __name__ == "__main__":                              # pragma: no cover
    sys.exit(main())
