"""Reanalyse NON_SCORED_TEST_FIXTURE_M1: every invalid fix, and what the gate did.

This is a REANALYSIS of a recording that already exists in the tree. No
simulator is launched and no new scenario is generated. The recording was made
for the MAER campaign, was declared a non-scored fixture when that campaign
stopped (research/maer/results/scored/MAER_STAGE2_STOP.json), and is used here
as an OBSERVATION of a real ArduPilot jamming episode -- N = 1 realisation.

Writes:
  results/INVALID_MESSAGE_GATE_TRACE.csv   one row per core tick
  results/DROP_VS_PROPAGATE_INVALID.csv    the three policies, same bytes
  results/DIAGNOSTIC_CONSEQUENCES.json     what the masking changes downstream

  python research/invalidity_masking/invalid_message_gate_trace.py
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
OUT = os.path.join(_HERE, "results")


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", "masking_harness.py")


def raw_stream_facts(messages, onset):
    """What the recording contains, before any CSIA code touches it."""
    gps = [m for m in messages if m.get("mavpackettype") == "GPS_RAW_INT"]
    post = [m for m in gps if float(m["_t_recv"]) >= onset]
    fixes = {}
    for m in post:
        fixes[int(m.get("fix_type", 0) or 0)] = \
            fixes.get(int(m.get("fix_type", 0) or 0), 0) + 1
    invalid = [m for m in post if int(m.get("fix_type", 0) or 0) < 3]
    # runs of consecutive invalid messages, and the accepted-sample gaps
    runs, cur = [], 0
    for m in post:
        if int(m.get("fix_type", 0) or 0) < 3:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    # Gaps between ACCEPTED samples, computed over the WHOLE stream and then
    # filtered to those that END after onset. Restricting the input to the
    # post-onset slice would silently drop the gap straddling the onset --
    # which in this recording is the longest one, because the jam begins with
    # an unbroken invalid run.
    acc_all = [float(m["_t_recv"]) for m in gps
               if int(m.get("fix_type", 0) or 0) >= 3]
    gaps = [round(b - a, 6) for a, b in zip(acc_all, acc_all[1:])
            if b >= onset]
    # longest CONTINUOUS invalid interval, in seconds
    inv_spans, run_t0 = [], None
    for m in gps:
        t = float(m["_t_recv"])
        if int(m.get("fix_type", 0) or 0) < 3:
            if run_t0 is None:
                run_t0 = t
        elif run_t0 is not None:
            inv_spans.append((run_t0, t))
            run_t0 = None
    if run_t0 is not None:
        inv_spans.append((run_t0, float(gps[-1]["_t_recv"])))
    post_spans = [(a, b) for a, b in inv_spans if b >= onset]
    return {
        "n_gps_raw_total": len(gps),
        "n_gps_raw_post_onset": len(post),
        "fix_type_histogram_post_onset": dict(sorted(fixes.items())),
        "n_invalid_post_onset": len(invalid),
        "invalid_fraction_post_onset": (round(len(invalid) / len(post), 6)
                                        if post else None),
        "invalid_run_lengths": {str(k): runs.count(k)
                                for k in sorted(set(runs))},
        "longest_invalid_run_messages": max(runs) if runs else 0,
        "n_accepted_post_onset": sum(
            1 for m in post if int(m.get("fix_type", 0) or 0) >= 3),
        "delivered_gps_raw_hz_post_onset": (
            round(len(post) / (float(post[-1]["_t_recv"])
                               - float(post[0]["_t_recv"])), 3)
            if len(post) > 1 else None),
        "max_accepted_gap_s": max(gaps) if gaps else None,
        "median_accepted_gap_s": (sorted(gaps)[len(gaps) // 2]
                                  if gaps else None),
        "longest_continuous_invalid_interval_s": (
            round(max(b - a for a, b in post_spans), 6)
            if post_spans else 0.0),
        "gps_stale_timeout_s": H.GPS_STALE_TIMEOUT_S,
        "max_accepted_gap_exceeds_timeout":
            (bool(max(gaps) > H.GPS_STALE_TIMEOUT_S) if gaps else None),
    }


def main() -> int:
    with open(FIXTURE, "rb") as fh:
        fixture_sha = hashlib.sha256(fh.read()).hexdigest()
    cap = H.load_fixture(FIXTURE)
    meta, messages = cap["meta"], cap["messages"]
    onset = float(meta["t_inject_rel_s"])

    raw = raw_stream_facts(messages, onset)
    print(f"  raw stream, post-onset: {raw['n_gps_raw_post_onset']} GPS_RAW_INT"
          f", {raw['n_invalid_post_onset']} invalid "
          f"({raw['invalid_fraction_post_onset']:.3f})")
    print(f"  delivered {raw['delivered_gps_raw_hz_post_onset']} Hz; longest "
          f"invalid run {raw['longest_invalid_run_messages']} msgs = "
          f"{raw['longest_continuous_invalid_interval_s']} s")
    print(f"  max accepted gap {raw['max_accepted_gap_s']} s vs timeout "
          f"{raw['gps_stale_timeout_s']} s -> exceeds: "
          f"{raw['max_accepted_gap_exceeds_timeout']}")

    os.makedirs(OUT, exist_ok=True)
    outs, summaries = {}, []
    for policy in H.POLICIES:
        out = H.replay(messages, policy)
        outs[policy] = out
        s = H.summarise(out, t_from=onset)
        s["fixture"] = meta["tag"]
        summaries.append(s)
        print(f"  {policy:<24} masked {s['n_masked_ticks']}/"
              f"{s['n_ticks_last_obs_invalid']} invalid-observation ticks "
              f"(fraction {s['masking_fraction']})")

    # per-tick trace, stock policy: this is what the deployed stack does
    rows = outs["DROP"]["rows"]
    fields = list(rows[0].keys())
    with open(os.path.join(OUT, "INVALID_MESSAGE_GATE_TRACE.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(OUT, "DROP_VS_PROPAGATE_INVALID.csv"), "w",
              newline="", encoding="utf-8") as fh:
        cols = list(summaries[0].keys())
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(summaries)

    # --- downstream consequences ------------------------------------------
    drop = {r["t"]: r for r in outs["DROP"]["rows"]}
    hold = {r["t"]: r for r in outs["PROPAGATE_INVALID_HOLD"]["rows"]}
    zero = {r["t"]: r for r in outs["PROPAGATE_INVALID_ZERO"]["rows"]}
    common = sorted(set(drop) & set(hold) & set(zero))
    post = [t for t in common if t >= onset]
    disagree_gate = [t for t in post
                     if drop[t]["fresh_gps"] != hold[t]["fresh_gps"]]
    consequences = {
        "artifact": "DIAGNOSTIC_CONSEQUENCES",
        "fixture": meta["tag"],
        "fixture_sha256": fixture_sha,
        "input_sha256_recorded_at_capture": meta["input_sha256"],
        "simulator": meta["simulator"],
        "intervention": meta["intervention"],
        "onset_s": onset,
        "n_realisations": 1,
        "raw_stream": raw,
        "policies": {s["policy"]: s for s in summaries},
        "paired_ticks_post_onset": len(post),
        "ticks_where_gate_differs_DROP_vs_HOLD": len(disagree_gate),
        "gate_difference_fraction": (round(len(disagree_gate) / len(post), 6)
                                     if post else None),
        "trust_gps_post_onset": {
            p: {"min": round(min(r["trust_gps"] for r in outs[p]["rows"]
                                 if r["t"] >= onset), 6),
                "final": outs[p]["rows"][-1]["trust_gps"]}
            for p in H.POLICIES},
        # Stated explicitly because it runs the opposite way to the intuition
        # that masking must mean weaker detection. On THIS recording it does
        # not: withdrawing GPS evidence also withdraws the evidence that was
        # detecting the jam.
        "detection_comparison": {
            "question": "does masking the invalidity weaken fault detection "
                        "on this recording?",
            "gps_fault_posterior_final": {
                p: s["final_post_gps_fault"] for p, s in
                ((x["policy"], x) for x in summaries)},
            "ticks_with_gps_fault_as_top_cause": {
                p: s["n_ticks_top_cause_gps_fault"] for p, s in
                ((x["policy"], x) for x in summaries)},
            "min_trust_gps": {p: s["min_trust_gps"] for p, s in
                              ((x["policy"], x) for x in summaries)},
            "max_slot_age_with_open_gate_s": {
                p: s["max_slot_age_with_open_gate_s"] for p, s in
                ((x["policy"], x) for x in summaries)},
            "answer": "NO on this recording. The masking policy reaches a "
                      "HIGHER gps_fault posterior than either propagating "
                      "policy. What masking changes is how old the "
                      "measurement behind an open gate is allowed to be.",
        },
        "caveats": [
            "N = 1 recorded jamming episode. These are properties of THIS "
            "run, not an estimate over runs.",
            "PROPAGATE_INVALID_HOLD and _ZERO are research-only adapter "
            "subclasses. Only DROP is committed behaviour.",
            "The trust and gate numbers are produced by the frozen core "
            "unmodified; the harness reads its published state.",
        ],
    }
    with open(os.path.join(OUT, "DIAGNOSTIC_CONSEQUENCES.json"), "w",
              encoding="utf-8") as fh:
        json.dump(consequences, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  gate differs on {len(disagree_gate)}/{len(post)} paired "
          f"post-onset ticks (DROP vs PROPAGATE_INVALID_HOLD)")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
