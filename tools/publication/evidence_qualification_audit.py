"""Every current-stack scalar, tied to the artifact that produced it.

WHY THIS IS A RESOLVER AND NOT A TABLE. The obvious way to build a traceability
ledger is to write the numbers into it and note where each came from. That is a
transcription, and a transcription drifts the moment an artifact is
regenerated -- silently, in the direction of whatever was true when someone last
typed it. This repository has already been bitten by exactly that: a scalar
ledger recorded one generating commit for twenty trials, and the provenance
backfill proved there were seven.

So no scalar is written here. Each entry declares WHERE its value lives -- an
artifact path plus a lookup path into it -- and the value is read at run time.
An entry whose path no longer resolves is reported UNSUPPORTED and the tool
exits non-zero. "0 unsupported scalars" therefore means the lookups were
executed, not that nobody checked.

Two entries are MEASURED here rather than looked up, because no committed
artifact carries them: the corpus maximum horizontal speed and the speed-gate
threshold it is compared against. Both are computed from committed inputs
(flight logs, frozen source) and recorded with their sources, so they are
reproducible rather than asserted.

WHAT THE analysis_type FIELD IS FOR. A reviewer must be able to tell a
preregistered campaign from a post-hoc sweep from a harness audit without
reading the prose, because conflating them is how a post-hoc result gets read as
a prediction. The four kinds are kept separate and never pooled.

`statement` is a CANDIDATE sentence -- what the evidence supports, phrased for a
manuscript. No manuscript in this repository contains the current-stack results
(see CANONICAL_MANUSCRIPT_MANIFEST.md), so every entry is NOT_IN_MANUSCRIPT.
That is a fact about the repository, not a defect in this tool.

Reads committed artifacts and frozen source. Runs nothing, re-flies nothing.

  python tools/publication/evidence_qualification_audit.py
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

R = "research/v1_1/results"
PROBE = f"{R}/PX4_LINK_RATE_PROBE.json"
LEDGER = f"{R}/EVIDENCE_COVERAGE_LEDGER.json"
QUAL_PX4 = f"{R}/qualification_px4.json"
MECH_A = f"{R}/MECHANISM_A_LINK_CONFOUND_AUDIT.json"
MECH_B = f"{R}/current_stack_replication.json"
S0 = f"{R}/s0_sensitivity_posthoc_threshold_sweep.json"
PROV = f"{R}/PROVENANCE_BACKFILL.json"

# The four kinds, never pooled.
PRE = "PREREGISTERED_CAMPAIGN"
POST = "POST_HOC_ANALYSIS"
QUALF = "QUALIFICATION_HARNESS_AUDIT"
CORPUS = "MEASURED_CORPUS_PROPERTY"

_SENTINEL = object()


def resolve(doc, path):
    """Walk a dotted path. `rows[channel=baro.altitude]` filters a list."""
    cur = doc
    for part in re.findall(r"[^.\[\]]+(?:\[[^\]]+\])?", path):
        m = re.match(r"^([^\[]+)\[([^=]+)=(.+)\]$", part)
        if m:
            key, field, want = m.groups()
            if not isinstance(cur, dict) or key not in cur:
                return _SENTINEL
            hit = [r for r in cur[key]
                   if isinstance(r, dict) and str(r.get(field)) == want]
            if len(hit) != 1:
                return _SENTINEL
            cur = hit[0]
            continue
        if isinstance(cur, dict):
            if part not in cur:
                return _SENTINEL
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return _SENTINEL
        else:
            return _SENTINEL
    return cur


def generating_commit(rel_path):
    """The commit that last wrote this artifact."""
    out = subprocess.run(
        ["git", "-C", ROOT, "log", "-1", "--format=%h", "--", rel_path],
        capture_output=True, text=True, timeout=60)
    return (out.stdout.strip() or None) if out.returncode == 0 else None


# ---------------------------------------------------------- measured here
def corpus_max_horizontal_speed():
    """Fastest horizontal tick in the whole committed corpus, and its source."""
    best, flights, per_platform = 0.0, 0, {}
    for pat in (f"{R}/mechanism_b_gps/*.json", f"{R}/shadow_flights/*.json"):
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            with open(path, encoding="utf-8") as fh:
                res = json.load(fh)
            fid, ld = res.get("flight_id"), res.get("log_dir")
            plat = res.get("platform")
            if not fid or not ld:
                continue
            seen = False
            for lp in sorted(glob.glob(os.path.join(ROOT, ld, "*.jsonl"))):
                if fid not in os.path.basename(lp):
                    continue
                with open(lp, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            rec = json.loads(line)
                        except ValueError:
                            continue
                        if rec.get("record") != "tick":
                            continue
                        ch = (rec.get("canonical") or {}).get("channels") or {}
                        v = (ch.get("velocity_ned") or {}).get("value") \
                            or (ch.get("gnss.velocity") or {}).get("value")
                        if v:
                            seen = True
                            vh = math.hypot(v[0], v[1])
                            best = max(best, vh)
                            per_platform[plat] = max(
                                per_platform.get(plat, 0.0), vh)
            flights += 1 if seen else 0
    return {"value": round(best, 4), "flights": flights,
            "per_platform": {k: round(v, 4) for k, v in per_platform.items()}}


def speed_gate_threshold():
    src = os.path.join(ROOT, "csia", "prediction", "comparator.py")
    with open(src, encoding="utf-8") as fh:
        m = re.search(r"GATE_SPEED_LO\s*=\s*([0-9.]+)", fh.read())
    return float(m.group(1)) if m else None


# ------------------------------------------------------------- the ledger
# (claim_id, statement, artifact, lookup path, analysis_type)
ENTRIES = [
    # --- link-conditioned evidence availability -------------------------
    ("px4.baro.delivered_passive_hz",
     "On the passive shadow connection PX4 delivered SCALED_PRESSURE at this "
     "rate, having requested nothing.",
     PROBE, "arms.passive.links.14540.SCALED_PRESSURE.hz", QUALF),
    ("px4.baro.delivered_driven_hz",
     "On the same connection in the same simulator build, after "
     "SET_MESSAGE_INTERVAL was requested on it, PX4 delivered the same "
     "message at this rate.",
     PROBE, "arms.request_onboard.links.14540.SCALED_PRESSURE.hz", QUALF),
    ("px4.baro.qualification_measured_hz",
     "The driven qualification connection measured this rate, which is what "
     "the channel contract was validated against.",
     QUAL_PX4, "rows[channel=baro.altitude].measured_rate_hz", QUALF),
    ("px4.baro.declared_hz",
     "The channel contract declares this rate for the platform.",
     LEDGER, "ledger.px4.relations.altitude_baro.endpoints.baro.declared_hz",
     QUALF),
    ("px4.baro.derived_max_age_s",
     "The freshness budget is derived from the declaration, not measured, so "
     "a slower delivering link is stale for part of every period.",
     LEDGER,
     "ledger.px4.relations.altitude_baro.endpoints.baro.derived_max_age_s",
     QUALF),
    ("px4.baro.channel_usable_share",
     "Share of shadow ticks on which the barometric channel was usable to the "
     "diagnostic consumer, against the freshness budget the declaration buys.",
     LEDGER,
     "ledger.px4.relations.altitude_baro.endpoints.baro.channel_usable_share",
     QUALF),
    ("px4.baro.node_stale_timeout_s",
     "A SECOND freshness budget applies at the node layer. It is a fixed "
     "constant in the frozen runtime that no rate declaration feeds, and for "
     "the barometer it is five times stricter than the budget the declared "
     "rate buys.",
     LEDGER,
     "ledger.px4.relations.altitude_baro.endpoints.baro.node_stale_timeout_s",
     QUALF),
    ("px4.baro.node_fresh_share",
     "Share of ticks on which the barometric NODE was fresh. A relation's "
     "weight is gated on its endpoint nodes, not on channel usability, so "
     "this is the quantity that governs evidence availability.",
     LEDGER,
     "ledger.px4.relations.altitude_baro.endpoints.baro.node_fresh_share",
     QUALF),
    ("px4.baro.binding_gate",
     "Which of the two freshness budgets is the stricter one for this "
     "endpoint. Reporting max_age alone predicts roughly half the ticks and "
     "the measurement shows under a tenth.",
     LEDGER,
     "ledger.px4.relations.altitude_baro.endpoints.baro.binding_gate", QUALF),
    ("ardupilot.baro.node_fresh_share",
     "The same node on ArduPilot, whose link is driven by the tee.",
     LEDGER,
     "ledger.ardupilot.relations.altitude_baro.endpoints.baro."
     "node_fresh_share", QUALF),
    ("px4.altitude_baro.live_share",
     "Share of PX4 shadow ticks on which the baro/GNSS cross-check carried "
     "non-zero gate weight.",
     LEDGER, "ledger.px4.relations.altitude_baro.relation_live_share", QUALF),
    ("ardupilot.altitude_baro.live_share",
     "The same relation on ArduPilot, whose link is driven by the tee.",
     LEDGER, "ledger.ardupilot.relations.altitude_baro.relation_live_share",
     QUALF),
    ("px4.altitude_baro.verdict",
     "Classification of the PX4 barometric starvation. It denotes an "
     "under-delivering consumer link, NOT an intrinsic platform rate and NOT "
     "a universally wrong declaration.",
     LEDGER, "ledger.px4.relations.altitude_baro.verdict", QUALF),
    ("px4.probe.simulator_sha",
     "The PX4 build these delivery rates were measured on; they are defaults "
     "of this firmware and airframe.",
     PROBE, "simulator_provenance.sha", QUALF),

    # --- operating-regime coverage limitation ---------------------------
    ("heading_course.live_share.ardupilot",
     "The only magnetometer cross-check against an independent reference "
     "carried zero gate weight across the ArduPilot corpus.",
     LEDGER, "ledger.ardupilot.relations.heading_course.relation_live_share",
     CORPUS),
    ("heading_course.live_share.px4",
     "The same relation, on PX4.",
     LEDGER, "ledger.px4.relations.heading_course.relation_live_share", CORPUS),
    ("heading_course.verdict",
     "It is dark because the flown corpus never entered its operating region, "
     "not because either platform fails to supply the inputs.",
     LEDGER, "ledger.px4.relations.heading_course.verdict", CORPUS),

    # --- Mechanism A, and whether the link starvation confounded it -----
    ("mechanism_a.verdict.ardupilot",
     "Whether the ArduPilot Mechanism A headline is affected by transport "
     "starvation.",
     MECH_A, "verdicts.ardupilot", QUALF),
    ("mechanism_a.verdict.px4",
     "Whether the PX4 Mechanism A headline is affected by transport "
     "starvation.",
     MECH_A, "verdicts.px4", QUALF),
    ("mechanism_a.gps_weight.ardupilot.control",
     "Evidence carried by GNSS-gated relations before the fault, ArduPilot.",
     MECH_A, "platforms.ardupilot.gps_gate_weight_sum.control_arm", PRE),
    ("mechanism_a.gps_weight.ardupilot.post",
     "The same quantity after fix loss.",
     MECH_A, "platforms.ardupilot.gps_gate_weight_sum.fault_arm_post", PRE),
    ("mechanism_a.gps_weight.px4.control",
     "Evidence carried by GNSS-gated relations before the fault, PX4. Smaller "
     "than ArduPilot's because three relations were already dark, for three "
     "different reasons, none of which is that PX4 lacks the relations.",
     MECH_A, "platforms.px4.gps_gate_weight_sum.control_arm", PRE),
    ("mechanism_a.gps_weight.px4.post",
     "The same quantity after fix loss.",
     MECH_A, "platforms.px4.gps_gate_weight_sum.fault_arm_post", PRE),
    ("mechanism_a.rule_b_ticks.ardupilot",
     "Ticks on which the declared downstream observable was present, so the "
     "injection is measured rather than assumed.",
     MECH_A, "platforms.ardupilot.rule_b_observable.ticks_observed", PRE),
    ("mechanism_a.rule_b_ticks.px4",
     "The same, on PX4.",
     MECH_A, "platforms.px4.rule_b_observable.ticks_observed", PRE),

    # --- Mechanism B, preregistered ------------------------------------
    ("mechanism_b.threshold",
     "The preregistered crossing threshold.",
     MECH_B, "threshold", PRE),
    ("mechanism_b.ardupilot.verdict",
     "Outcome of the preregistered ArduPilot GNSS step/ramp campaign.",
     MECH_B, "platforms.ardupilot.verdict", PRE),
    ("mechanism_b.ardupilot.trials_total",
     "Trials run in the preregistered grid.",
     MECH_B, "platforms.ardupilot.trials_total", PRE),
    ("mechanism_b.ardupilot.trials_valid",
     "Trials that satisfied the validity conditions declared before any trial "
     "was run.",
     MECH_B, "platforms.ardupilot.trials_valid", PRE),
    ("mechanism_b.ardupilot.max_reconstruction_error",
     "Worst tick-by-tick reconstruction error across all valid trials, "
     "against a preregistered tolerance.",
     MECH_B, "platforms.ardupilot.max_reconstruction_error", PRE),
    ("mechanism_b.px4.verdict",
     "PX4 outcome. No fix-preserving GNSS position offset exists on PX4 SIH, "
     "so the condition could not be run; no substitute was flown.",
     MECH_B, "platforms.px4.verdict", PRE),

    # --- post-hoc sensitivity ------------------------------------------
    ("s0.share.t075",
     "Share of reconstructed crossing delay attributable to banked history at "
     "the preregistered threshold.",
     S0, "rows[threshold=0.75].history_attributable_share", POST),
    ("s0.share.t080",
     "The same share at a higher evaluated threshold.",
     S0, "rows[threshold=0.8].history_attributable_share", POST),
    ("s0.share.t085",
     "The same share at a higher evaluated threshold still.",
     S0, "rows[threshold=0.85].history_attributable_share", POST),
    ("s0.share.t065",
     "At this threshold no crossing occurred in the reconstruction, so no "
     "share is defined.",
     S0, "rows[threshold=0.65].history_attributable_share", POST),
    ("s0.share.t070",
     "At this threshold no crossing occurred in the reconstruction, so no "
     "share is defined.",
     S0, "rows[threshold=0.7].history_attributable_share", POST),

    # --- campaign provenance -------------------------------------------
    ("provenance.mechanism_b.distinct_commits",
     "The trials were generated across successive result-recording commits, "
     "not all at one.",
     PROV, "campaigns.mechanism_b_gps.distinct_generating_commits", PRE),
    ("provenance.mechanism_b.trial_affecting_paths_changed",
     "A provenance audit found the declared trial-affecting code paths "
     "byte-identical across the generating interval.",
     PROV, "campaigns.mechanism_b_gps.code_invariance.paths_changed", PRE),
    ("provenance.mechanism_b.frozen_core_consistent",
     "Every trial ran against the same frozen diagnostic core.",
     PROV, "campaigns.mechanism_b_gps.frozen_core_consistent", PRE),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        ROOT, R, "CURRENT_STACK_EVIDENCE_QUALIFICATION_AUDIT.json"))
    args = ap.parse_args()

    cache, rows, unsupported = {}, [], []
    for cid, statement, artifact, path, kind in ENTRIES:
        abs_path = os.path.join(ROOT, artifact)
        if artifact not in cache:
            try:
                with open(abs_path, encoding="utf-8") as fh:
                    cache[artifact] = json.load(fh)
            except (OSError, ValueError):
                cache[artifact] = _SENTINEL
        doc = cache[artifact]
        value = _SENTINEL if doc is _SENTINEL else resolve(doc, path)
        ok = value is not _SENTINEL
        if not ok:
            unsupported.append(cid)
        rows.append({
            "claim_id": cid,
            "paper_text": statement,
            "value": None if not ok else value,
            "artifact": artifact,
            "lookup": path,
            "generating_commit": generating_commit(artifact),
            "analysis_type": kind,
            "status": "SUPPORTED" if ok else "UNSUPPORTED",
            "in_manuscript": False,
        })

    # Measured here, because no committed artifact carries them.
    speed = corpus_max_horizontal_speed()
    gate_lo = speed_gate_threshold()
    for cid, statement, val, src in (
        ("corpus.max_horizontal_speed_ms",
         "Fastest horizontal speed on any tick of the committed corpus.",
         speed["value"], "research/v1_1/results/**/*.jsonl (flight logs)"),
        ("gate.speed_lo_ms",
         "Horizontal speed below which the heading/course relation "
         "contributes nothing.",
         gate_lo, "csia/prediction/comparator.py:GATE_SPEED_LO"),
    ):
        ok = val is not None
        if not ok:
            unsupported.append(cid)
        rows.append({
            "claim_id": cid, "paper_text": statement,
            "value": val, "artifact": src, "lookup": "measured by this tool",
            "generating_commit": None, "analysis_type": CORPUS,
            "status": "SUPPORTED" if ok else "UNSUPPORTED",
            "in_manuscript": False,
        })

    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["analysis_type"], []).append(r["claim_id"])

    print("=== current-stack evidence qualification audit")
    print(f"  {'claim_id':46s} {'value':>26s}  type")
    for r in rows:
        v = r["value"]
        vs = ("-" if v is None else
              (json.dumps(v) if isinstance(v, (dict, list)) else str(v)))
        print(f"  {r['claim_id']:46s} {vs[:26]:>26s}  {r['analysis_type']}")
    print(f"\n  corpus max horizontal speed {speed['value']} m/s against a "
          f"{gate_lo} m/s gate, over {speed['flights']} flights "
          f"({speed['per_platform']})")
    print(f"  supported   : {len(rows) - len(unsupported)}")
    print(f"  unsupported : {len(unsupported)}"
          + (f" -> {unsupported}" if unsupported else ""))
    print("  in manuscript: 0 -- no manuscript in this repository carries the "
          "current-stack results (CANONICAL_MANUSCRIPT_MANIFEST.md)")

    out = {
        "what_this_is": ("every current-stack scalar, resolved from the "
                         "artifact that produced it at run time rather than "
                         "transcribed into this file"),
        "why_a_resolver": ("a transcribed ledger drifts silently when an "
                           "artifact is regenerated; this repository has "
                           "already had a scalar ledger record one generating "
                           "commit for twenty trials when there were seven"),
        "analysis_type_meanings": {
            PRE: "declared before any trial was run",
            POST: "computed after the fact from recorded traces; never a "
                  "prediction and never pooled with the preregistered result",
            QUALF: "a property of the measurement harness, not of the vehicle",
            CORPUS: "a property of the flights that happen to have been flown",
        },
        "claims_by_analysis_type": by_kind,
        "corpus_speed_detail": speed,
        "supported_scalars": len(rows) - len(unsupported),
        "unsupported_scalars": len(unsupported),
        "unsupported_claim_ids": unsupported,
        "entries": rows,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 1 if unsupported else 0


if __name__ == "__main__":
    sys.exit(main())
