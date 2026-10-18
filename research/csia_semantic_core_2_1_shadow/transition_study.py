#!/usr/bin/env python3
"""Configuration-transition shadow experiment E1 (Parts 13-17, 49).
NON-CONFIRMATORY. RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/transition_study.py

Executes TRANSITION_DESIGN.json exactly as frozen (commit e0fc81a, before this
runner existed). The script refuses to run if the design file's SHA-256 is
not the frozen one. Writes TRANSITION_RESULTS.json only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness")):
    if p not in sys.path:
        sys.path.insert(0, p)

import semantic_probe as P  # noqa: E402

from csia.v2.attribution import AMBIGUOUS, NO_EVIDENCE, UNIQUE  # noqa: E402
from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import SemanticCore21  # noqa: E402

DESIGN = HERE / "TRANSITION_DESIGN.json"
FROZEN_SHA256 = "f84f8e5acbf9d581632286469ef32d038081000a36001e2b9d6d510edbc77c75"
OUT = HERE / "TRANSITION_RESULTS.json"
IMU = "source.imu0"
EST = "state_estimator"
NAV = ("COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION")


def load_design():
    raw = DESIGN.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != FROZEN_SHA256:
        raise SystemExit(f"design changed since it was frozen: {got}")
    return json.loads(raw)


def stream(design):
    """-> per tick: (records, meta), meta = {record key: (content_tick, epoch,
    valid)} for the records the transition touches. Everything else is the
    NOMINAL run's own record, current, valid, no epoch."""
    s = design["schedule"]
    fail, switch = s["imu0_fails_at"], s["lane_switch_at"]
    lo, hi = s["estimator_lane0_degraded"]
    win, period = s["latched_miss_window_ticks"], s["imu0_health_update_period_ticks"]
    _engine, res = P.run_scenario(SCENARIOS["NOMINAL"], ticks=s["ticks"])
    misses = list(range(lo, hi + 1))
    out = []
    for t, sa in enumerate(res):
        lane = 0 if t < switch else 1
        recs, meta = [], {}
        for r in sa.records:
            key = f"{r.domain}/{r.component}:{r.relation}"
            if r.component == IMU and t >= fail:
                pub = fail + ((t - fail) // period) * period
                r = replace(r, observation_state=OS.VIOLATED, reason_codes=("SOURCE_STALE",),
                            detail=dict(r.detail, fresh=False, missing_reason="stale"))
                meta[key] = (pub, None, True)
            elif r.component == EST and r.relation == "compute.deadline_met":
                recent = [m for m in misses if t - win < m <= t]
                if recent:
                    last = max(recent)
                    epoch = 0 if last < switch else 1
                    r = replace(r, observation_state=OS.VIOLATED,
                                reason_codes=("COMPUTE_DEADLINE_MISSED",),
                                detail=dict(r.detail, reported_misses=len(recent)))
                    meta[key] = (last, epoch, epoch == lane)
                else:
                    meta[key] = (t, lane, True)
            elif r.component == EST and r.relation == "compute.stability":
                if lo <= t <= hi:
                    r = replace(r, observation_state=OS.DEGRADED,
                                reason_codes=("COMPUTE_QUEUE_BACKLOG",))
                meta[key] = (t, lane, True)
            recs.append(r)
        out.append((t, lane, tuple(recs), meta))
    return out


def admit(policy, t, lane, recs, meta):
    """Inadmissible records become UNAVAILABLE (never deleted)."""
    out, stale_admitted, over_invalidated = [], 0, 0
    for r in recs:
        key = f"{r.domain}/{r.component}:{r.relation}"
        content, epoch, valid = meta.get(key, (t, None, True))
        if policy == "C_NONE":
            ok = True
        elif policy.startswith("A_FIXED_AGE_W"):
            ok = (t - content) <= int(policy.rsplit("W", 1)[1])
        elif policy == "B_STATE_EPOCH":
            ok = epoch is None or epoch == lane
        else:
            raise ValueError(policy)
        stale_admitted += int(ok and not valid)
        over_invalidated += int(valid and not ok)
        out.append(r if ok else replace(r, observation_state=OS.UNAVAILABLE))
    return tuple(out), stale_admitted, over_invalidated


def grade(design, t, tr):
    fail, switch = design["schedule"]["imu0_fails_at"], design["schedule"]["lane_switch_at"]
    a = tr.attribution
    cands = list(a.candidates)
    pos = sorted({x.subject for x in tr.localizations
                  if x.symptom == "POSITION_UNAVAILABLE" and x.subject in NAV})
    should_pos = fail <= t < switch
    if t < fail:
        ag = "CORRECT_NO_EVIDENCE" if a.verdict == NO_EVIDENCE else "SPURIOUS"
    elif a.verdict == UNIQUE:
        ag = "CORRECT_UNIQUE" if cands == [f"SENSOR/{IMU}"] else "WRONG_UNIQUE"
    elif a.verdict == AMBIGUOUS:
        ag = "CORRECT_AMBIGUOUS" if f"SENSOR/{IMU}" in cands else "WRONG_AMBIGUOUS"
    elif a.verdict == NO_EVIDENCE:
        ag = "NO_EVIDENCE_WHEN_CAUSE_PRESENT"
    else:
        ag = a.verdict
    return ag, pos, should_pos


def main():
    design = load_design()
    ticks = stream(design)
    engine = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    core = SemanticCore21.from_engine(engine, trace=True)
    switch = design["schedule"]["lane_switch_at"]
    results = {"id": design["id"], "design_sha256": FROZEN_SHA256,
               "label": "NON-CONFIRMATORY shadow experiment; records modelled on PX4 behaviour, not measured",
               "policies": {}}
    for policy in design["policies"]:
        row = {"attribution": {}, "stale_position_symptom_ticks": 0,
               "missed_position_symptom_ticks": 0, "stale_record_ticks_admitted": 0,
               "valid_record_ticks_made_unavailable": 0, "per_tick": []}
        for t, lane, recs, meta in ticks:
            admitted, stale, over = admit(policy, t, lane, recs, meta)
            tr = core.reason(admitted)
            ag, pos, should = grade(design, t, tr)
            row["attribution"][ag] = row["attribution"].get(ag, 0) + 1
            row["stale_position_symptom_ticks"] += int(bool(pos) and not should)
            row["missed_position_symptom_ticks"] += int(should and not pos)
            row["stale_record_ticks_admitted"] += stale
            row["valid_record_ticks_made_unavailable"] += over
            row["per_tick"].append({
                "t": t, "lane": lane, "attribution": tr.attribution.verdict,
                "candidates": list(tr.attribution.candidates), "grade": ag,
                "position_unavailable_on": pos,
                "withheld_because": list(tr.attribution.withheld_unique_because)})
        after = [x for x in row["per_tick"] if x["t"] >= switch]
        rec = None
        for i, x in enumerate(after):
            if all(y["grade"] == "CORRECT_UNIQUE" for y in after[i:]):
                rec = x["t"]
                break
        row["recovery_tick"] = rec
        results["policies"][policy] = row
        print(policy, {k: row[k] for k in ("attribution", "stale_position_symptom_ticks",
                                           "missed_position_symptom_ticks",
                                           "stale_record_ticks_admitted",
                                           "valid_record_ticks_made_unavailable", "recovery_tick")})
    OUT.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
