#!/usr/bin/env python3
"""Phase 7: configuration transition E1, replayed exactly. NON-CONFIRMATORY.
RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/transition_replay.py

E1's design is the shadow study's frozen TRANSITION_DESIGN.json (commit
e0fc81a). `transition_study.load_design()` refuses to run if its SHA-256
differs. The record stream, the grading and the metrics are that study's
own, imported, not re-implemented. Nothing here was changed after the first
result.

What is new is the reasoner:

    V2_0                     frozen v2.0 on every record (no validity management)
    PRE_2_1_0                2.1.0 on every record (the shadow study's C_NONE)
    REVISED_2_1_1            2.1.1, all revisions, the implemented epoch rule
    REVISED_2_1_1_R2         the same, with successor profile r2
    REVISED_NO_CONTEXT       2.1.1 given the stamped records but no epoch
                             context (diagnostic: the rule fails closed)

How the design's "estimator epoch" reaches the implemented rule:
  - every record the design gives an epoch (the estimator's deadline and
    stability records) is stamped
    provenance["config_epoch"] = {"ekf2.selector.instance_changed_count": epoch};
  - records the design gives no epoch (the IMU's own health, everything
    else) are not stamped;
  - the context is {"ekf2.selector.instance_changed_count": lane}: in E1 the
    lane goes 0 -> 1 once, so the counter equals the lane;
  - the context names the transition event from the switch tick on.
The implemented rule then decides admission; the design's own B_STATE_EPOCH
admission is not applied.

Writes TRANSITION_REPLAY_RESULTS.json.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from types import SimpleNamespace

import revision_common as RC

import semantic_probe as P  # noqa: E402
import transition_study as T  # noqa: E402

from csia.v2.attribution import attribute  # noqa: E402
from csia.v2.localization import localize_all  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import (Corrections, EpochContext,  # noqa: E402
                                SemanticCore21)
from csia_semantic_core.profile_overlay import load_successor  # noqa: E402

OUT = RC.HERE / "TRANSITION_REPLAY_RESULTS.json"
KEY = "ekf2.selector.instance_changed_count"
EVENT = ("estimator_selector_status.instance_changed_count 0 -> 1 at tick {t}: "
         "primary EKF instance changed after SENSOR/source.imu0 failed")


def stamped(recs, meta):
    out = []
    for r in recs:
        k = f"{r.domain}/{r.component}:{r.relation}"
        epoch = meta.get(k, (None, None, True))[1]
        if epoch is not None:
            r = replace(r, provenance=dict(r.provenance or {},
                                           config_epoch={KEY: epoch}))
        out.append(r)
    return tuple(out)


def context(t, lane, switch):
    return EpochContext({KEY: lane},
                        {KEY: EVENT.format(t=switch)} if t >= switch else {})


def v20_view(engine, recs):
    locs = localize_all(engine.symptoms, recs, engine.predicates)
    a = attribute(recs, engine.relations)
    return SimpleNamespace(
        attribution=SimpleNamespace(verdict=a.verdict,
                                    candidates=tuple(c.id for c in a.candidates),
                                    withheld_unique_because=()),
        localizations=tuple(SimpleNamespace(symptom=x.symptom, subject=x.subject)
                            for x in locs))


def run(name, design, ticks, reason, admitted_of):
    switch = design["schedule"]["lane_switch_at"]
    row = {"attribution": {}, "stale_position_symptom_ticks": 0,
           "missed_position_symptom_ticks": 0,
           "stale_record_ticks_admitted": 0,
           "valid_record_ticks_made_unavailable": 0, "per_tick": []}
    for t, lane, recs, meta in ticks:
        tr = reason(t, lane, recs, meta)
        ag, pos, should = T.grade(design, t, tr)
        row["attribution"][ag] = row["attribution"].get(ag, 0) + 1
        row["stale_position_symptom_ticks"] += int(bool(pos) and not should)
        row["missed_position_symptom_ticks"] += int(should and not pos)
        stale, over = admitted_of(t, lane, recs, meta, tr)
        row["stale_record_ticks_admitted"] += stale
        row["valid_record_ticks_made_unavailable"] += over
        adm = getattr(tr, "admission", None)
        row["per_tick"].append({
            "t": t, "lane": lane, "attribution": tr.attribution.verdict,
            "candidates": list(tr.attribution.candidates), "grade": ag,
            "position_unavailable_on": pos,
            "inadmissible": [] if not adm else [
                {k: e[k] for k in ("record", "reason", "evidence_epoch",
                                   "current_epoch", "action", "transition_event")}
                for e in adm["inadmissible"]]})
    after = [x for x in row["per_tick"] if x["t"] >= switch]
    row["recovery_tick"] = next((x["t"] for i, x in enumerate(after)
                                 if all(y["grade"] == "CORRECT_UNIQUE"
                                        for y in after[i:])), None)
    return row


def main():
    design = T.load_design()
    ticks = T.stream(design)
    switch = design["schedule"]["lane_switch_at"]
    engine = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    pre = SemanticCore21.from_engine(engine, trace=True)
    rev = SemanticCore21.from_engine(engine, Corrections.revised(), trace=True)
    r2 = load_successor("aircraft_successor_r2")
    rev2 = SemanticCore21.from_engine(engine, Corrections.revised(), trace=True,
                                      pacing=r2.pacing_map())

    def admitted_none(t, lane, recs, meta, tr):
        _a, stale, over = T.admit("C_NONE", t, lane, recs, meta)
        return stale, over

    def admitted_impl(t, lane, recs, meta, tr):
        """Against the design's record-validity truth: an INVALID record the
        rule admitted, or a VALID one it did not."""
        bad = {e["record"] for e in tr.admission["inadmissible"]}
        stale = over = 0
        for r in recs:
            k = f"{r.domain}/{r.component}:{r.relation}"
            valid = meta.get(k, (t, None, True))[2]
            stale += int(not valid and k not in bad)
            over += int(valid and k in bad)
        return stale, over

    out = {"id": design["id"], "design_sha256": T.FROZEN_SHA256,
           "label": "NON-CONFIRMATORY; E1 design frozen in the shadow study, replayed unchanged",
           "epoch_key": KEY, "configurations": {}}
    cfgs = {
        "V2_0": (lambda t, lane, recs, meta: v20_view(engine, recs), admitted_none),
        "PRE_2_1_0": (lambda t, lane, recs, meta: pre.reason(recs), admitted_none),
        "REVISED_2_1_1": (lambda t, lane, recs, meta: rev.reason(
            stamped(recs, meta), context(t, lane, switch)), admitted_impl),
        "REVISED_2_1_1_R2": (lambda t, lane, recs, meta: rev2.reason(
            r2.apply(stamped(recs, meta)), context(t, lane, switch)), admitted_impl),
        "REVISED_NO_CONTEXT": (lambda t, lane, recs, meta: rev.reason(
            stamped(recs, meta)), admitted_impl),
    }
    for name, (reason, adm) in cfgs.items():
        row = run(name, design, ticks, reason, adm)
        out["configurations"][name] = row
        print(name, {k: row[k] for k in (
            "attribution", "stale_position_symptom_ticks",
            "missed_position_symptom_ticks", "stale_record_ticks_admitted",
            "valid_record_ticks_made_unavailable", "recovery_tick")})
    shadow_ref = T.OUT.read_text()
    import json
    ref = json.loads(shadow_ref)["policies"]["B_STATE_EPOCH"]
    impl = out["configurations"]["REVISED_2_1_1"]
    out["implemented_rule_matches_design_reference_B_STATE_EPOCH"] = {
        k: [ref[k], impl[k]] for k in ("attribution", "stale_position_symptom_ticks",
                                       "missed_position_symptom_ticks",
                                       "stale_record_ticks_admitted",
                                       "valid_record_ticks_made_unavailable",
                                       "recovery_tick")}
    RC.write_json(OUT, out)


if __name__ == "__main__":
    sys.exit(main())
