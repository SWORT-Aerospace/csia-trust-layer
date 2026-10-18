#!/usr/bin/env python3
"""Dataset E: configuration transition E1 through the 2.2 Analyzer.
NON-CONFIRMATORY. RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_evidence_assurance/e1_2_2.py

E1 is the shadow study's frozen design (TRANSITION_DESIGN.json; the design
loader refuses a changed file). Its record stream and grader are imported,
not re-implemented. The 2.1.1 revision replayed it as REVISED_2_1_1_R2 (stale
position-symptom ticks 9 -> 0).

What 2.2 adds is the path: every record becomes an envelope from its v2
domain producer. The estimator's deadline and stability records carry the
design's epoch as their stamp. The contract declares that dependency, and
admissibility hands them to 2.1.1's own R-3 with the lane context. A record
whose stamp disagrees is CONFIGURATION_MISMATCH.

The permanent regression (`tests/test_evidence_assurance_2_2.py`) pins:
- 0 stale position-symptom ticks;
- the per-tick verdicts and candidates equal to the revision's
  REVISED_2_1_1_R2.

Writes E1_2_2_RESULTS.json.
"""
from __future__ import annotations

import json
import sys

import common_2_2 as C

import transition_study as T  # noqa: E402

from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_evidence_assurance import profile_gate as PG  # noqa: E402
from csia_evidence_assurance.adapters import v2_domains as V2  # noqa: E402
from csia_evidence_assurance.analyzer import FlightAssuranceAnalyzer  # noqa: E402
from csia_semantic_core import Corrections, EpochContext, SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import load_successor  # noqa: E402

import semantic_probe as P  # noqa: E402

OUT = C.HERE / "E1_2_2_RESULTS.json"
KEY = "ekf2.selector.instance_changed_count"
EVENT = ("estimator_selector_status.instance_changed_count 0 -> 1 at tick {t}: "
         "primary EKF instance changed after SENSOR/source.imu0 failed")
DT = 0.05          # the v2 scenario runner's tick period
REVISION_RESULTS = C.REVISION / "TRANSITION_REPLAY_RESULTS.json"


def run(collect=None):
    """`collect`: a list that receives every AssuranceResult, and the
    analyzer's gate and contracts, for the dataset reports."""
    design = T.load_design()
    ticks = T.stream(design)
    switch = design["schedule"]["lane_switch_at"]
    engine = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    r2 = load_successor("aircraft_successor_r2")
    core = SemanticCore21.from_engine(engine, Corrections.revised(), trace=True,
                                      pacing=r2.pacing_map())
    epoch_claims = {("compute", "compute.deadline_met", T.EST): (KEY,),
                    ("compute", "compute.stability", T.EST): (KEY,)}
    contracts = V2.legacy_contracts(engine, V2.AIRCRAFT_BASE, epoch_claims)
    gate = PG.gate(r2, ticks[0][2], engine.functions)
    an = FlightAssuranceAnalyzer(core, contracts, gate, V2.AIRCRAFT_BASE)
    row = {"attribution": {}, "stale_position_symptom_ticks": 0,
           "missed_position_symptom_ticks": 0, "config_mismatch_ticks": 0,
           "per_tick": []}
    for t, lane, recs, meta in ticks:
        def epoch_of(r, meta=meta):
            ep = meta.get(f"{r.domain}/{r.component}:{r.relation}", (None, None, True))[1]
            return None if ep is None else {KEY: ep}
        ctx = EpochContext({KEY: lane}, {KEY: EVENT.format(t=switch)} if t >= switch else {})
        res = an.step(t * DT, V2.envelopes(r2.apply(recs), t * DT, contracts, epoch_of),
                      epochs=ctx)
        tr = an.last_tick
        if collect is not None:
            collect.append(res)
        ag, pos, should = T.grade(design, t, tr)
        row["attribution"][ag] = row["attribution"].get(ag, 0) + 1
        row["stale_position_symptom_ticks"] += int(bool(pos) and not should)
        row["missed_position_symptom_ticks"] += int(should and not pos)
        mism = [x for x in res.evidence["rejected"] if x["status"] == "CONFIGURATION_MISMATCH"]
        row["config_mismatch_ticks"] += int(bool(mism))
        row["other_rejections"] = row.get("other_rejections", 0) + sum(
            x["status"] != "CONFIGURATION_MISMATCH" for x in res.evidence["rejected"])
        row["per_tick"].append({
            "t": t, "lane": lane, "attribution": tr.attribution.verdict,
            "candidates": list(tr.attribution.candidates), "grade": ag,
            "position_unavailable_on": pos,
            "configuration_mismatch": [{"evidence_id": x["evidence_id"],
                                        "reasons": x["reasons"]} for x in mism]})
    if collect is not None:
        collect.insert(0, (gate, contracts))
    after = [x for x in row["per_tick"] if x["t"] >= switch]
    row["recovery_tick"] = next((x["t"] for i, x in enumerate(after)
                                 if all(y["grade"] == "CORRECT_UNIQUE" for y in after[i:])),
                                None)
    ref = json.loads(REVISION_RESULTS.read_text())["configurations"]
    rev = ref["REVISED_2_1_1_R2"]["per_tick"]
    row["per_tick_equal_to_revision_REVISED_2_1_1_R2"] = all(
        (a["attribution"], a["candidates"], a["position_unavailable_on"])
        == (b["attribution"], b["candidates"], b["position_unavailable_on"])
        for a, b in zip(row["per_tick"], rev)) and len(rev) == len(row["per_tick"])
    row["pre_2_1_0_stale_position_symptom_ticks"] = ref["PRE_2_1_0"]["stale_position_symptom_ticks"]
    return {"id": design["id"], "design_sha256": T.FROZEN_SHA256,
            "label": "NON-CONFIRMATORY; E1 design frozen in the shadow study, through 2.2",
            "epoch_key": KEY, "result": row}


def main():
    out = run()
    r = out["result"]
    print({k: r[k] for k in ("attribution", "stale_position_symptom_ticks",
                             "missed_position_symptom_ticks", "config_mismatch_ticks",
                             "other_rejections",
                             "recovery_tick", "per_tick_equal_to_revision_REVISED_2_1_1_R2",
                             "pre_2_1_0_stale_position_symptom_ticks")})
    C.write_json(OUT, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
