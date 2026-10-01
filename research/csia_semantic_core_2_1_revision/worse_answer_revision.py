#!/usr/bin/env python3
"""Phase 12: trying to make 2.1.1 give a WORSE answer. RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/worse_answer_revision.py

"Worse" is a wrong answer, or a right answer lost for a wrong reason. LESS
CERTAIN is reported separately and is not counted as worse. The probes that
need a whole dataset are read from the harness that ran them (one source per
number); the probes below are run here:

  O1  order dependence     every dataset A tick, and every E1 tick with its
                           epochs, reasoned in reverse record order and in a
                           seeded shuffle: any decision or outcome change
  O2  duplicate dependence the same, with every record sent twice
  H1  undeclared pacing input   a real second pacing input the profile does
                           not declare dies (the estimator needs both); and
                           the IMU-failover form, where the declared input is
                           not the one in use
  X1  R-1 x R-3            a predicate fault on E1 ticks with inadmissible
                           evidence: any wrong SUPPORTED or wrong UNIQUE
  X2  overlay x R-3        a stamped record keeps its stamp through every
                           successor overlay
  U1  unknown as healthy   symptoms not raised because their evidence was not
                           admitted (from the epoch harnesses)

Writes WORSE_ANSWER_REVISION.json.
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import replace

import revision_common as RC

import predicate_fault_study as F  # noqa: E402
import semantic_probe as P  # noqa: E402
import shadow_validation as S  # noqa: E402
import transition_replay as TR  # noqa: E402
import transition_study as T  # noqa: E402

from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.localization import SUPPORTED  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import Corrections, SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import (Declaration,  # noqa: E402
                                                ProfileOverlay,
                                                load_successor)

OUT = RC.HERE / "WORSE_ANSWER_REVISION.json"
REVISED = Corrections.revised()


def decision(tr):
    """The decision, canonical: per localization its verdict, outcome and
    survivor / rejected SETS; the attribution verdict and candidate SET.
    List order inside the 2.0 view's detail is presentation (frozen
    `attribute()` lists a candidate's relations in record order) and is
    counted separately."""
    return (sorted((x.key, x.v2.verdict, x.outcome, tuple(sorted(x.supported)),
                    tuple(sorted(x.unresolved)),
                    tuple(sorted(h for h, _ in x.v2.rejected)))
                   for x in tr.localizations),
            tr.attribution.verdict, tuple(sorted(tr.attribution.candidates)))


def order_and_duplicates(runs, r2):
    out = {"dataset_A_ticks": 0, "E1_ticks": 0, "reverse_changes": 0,
           "shuffle_changes": 0, "duplicate_changes": 0, "examples": [],
           "presentation_only_changes_2_1_1": 0, "presentation_only_changes_2_1_0": 0,
           "decision_changes_2_1_0": 0}
    rng = random.Random(20261001)
    for name, (engine, res) in runs.items():
        core = SemanticCore21.from_engine(engine, REVISED, trace=False, pacing=r2.pacing_map())
        pre = SemanticCore21.from_engine(engine, trace=False)
        for t, sa in enumerate(res):
            recs = r2.apply(sa.records)
            tr0 = core.reason(recs)
            base = decision(tr0)
            p0 = pre.reason(sa.records)
            sh = list(recs)
            rng.shuffle(sh)
            for key, variant in (("reverse_changes", tuple(reversed(recs))),
                                 ("shuffle_changes", tuple(sh)),
                                 ("duplicate_changes", recs + recs)):
                tr = core.reason(variant)
                if decision(tr) != base:
                    out[key] += 1
                    if len(out["examples"]) < 5:
                        out["examples"].append([name, t, key])
                elif tr.to_v2_0_view() != tr0.to_v2_0_view():
                    out["presentation_only_changes_2_1_1"] += 1
            rv = tuple(reversed(sa.records))
            p1 = pre.reason(rv)
            out["decision_changes_2_1_0"] += int(decision(p1) != decision(p0))
            out["presentation_only_changes_2_1_0"] += int(
                decision(p1) == decision(p0) and p1.to_v2_0_view() != p0.to_v2_0_view())
            out["dataset_A_ticks"] += 1
    design = T.load_design()
    engine = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    core = SemanticCore21.from_engine(engine, REVISED, trace=False)
    switch = design["schedule"]["lane_switch_at"]
    for t, lane, recs, meta in T.stream(design):
        s = TR.stamped(recs, meta)
        ctx = TR.context(t, lane, switch)
        base = decision(core.reason(s, ctx))
        for key, variant in (("reverse_changes", tuple(reversed(s))),
                             ("duplicate_changes", s + s)):
            if decision(core.reason(variant, ctx)) != base:
                out[key] += 1
                out["examples"].append(["E1", t, key])
        out["E1_ticks"] += 1
    return out


def undeclared_pacing(runs, r2):
    engine, res = runs["PROCESS_STALL"]
    base = r2.apply(res[-1].records)
    imu = [r for r in base if r.component == "source.imu0"][0]
    with_imu1 = ProfileOverlay("t", "t", "t", (Declaration(
        "COMPUTE", "state_estimator", add_dependencies=("SENSOR/source.imu1",)),)
    ).apply(base + (replace(imu, component="source.imu1"),))
    dead1 = tuple(replace(r, observation_state=OS.VIOLATED, reason_codes=("SOURCE_STALE",))
                  if r.component == "source.imu1" else r for r in with_imu1)
    dead0 = tuple(replace(r, observation_state=OS.VIOLATED, reason_codes=("SOURCE_STALE",))
                  if r.component == "source.imu0" else r for r in with_imu1)

    def om(corr, pacing, recs):
        core = SemanticCore21.from_engine(engine, corr, trace=False, pacing=pacing)
        x = [x for x in core.reason(recs).localizations
             if x.symptom == "OUTPUT_MISSING" and x.subject == "state_estimator"][0]
        return {"verdict": x.v2.verdict, "supported": list(x.supported),
                "unresolved": list(x.unresolved)}
    only0 = {"state_estimator": ("ALL", ("SENSOR/source.imu0",))}
    both = {"state_estimator": ("ALL", ("SENSOR/source.imu0", "SENSOR/source.imu1"))}
    only1 = {"state_estimator": ("ALL", ("SENSOR/source.imu1",))}
    return {
        "reading": ("the estimator's output stops; the true reason is that a pacing input "
                    "is dead. SUPPORTED process_stall is then wrong."),
        "both_pace_ALL_only_imu0_declared_imu1_dies": {
            "2_1_0_r1": om(Corrections(), None, dead1),
            "2_1_1_declared_imu0_only": om(REVISED, only0, dead1),
            "2_1_1_declared_both": om(REVISED, both, dead1)},
        "imu_failover_declared_imu0_in_use_imu1_dies": {
            "2_1_0_r1": om(Corrections(), None, dead1),
            "2_1_1_declared_imu0": om(REVISED, only0, dead1),
            "2_1_1_declared_imu1": om(REVISED, only1, dead1)},
        "declared_imu0_dies_control": {"2_1_1_declared_imu0": om(REVISED, only0, dead0)}}


def fault_on_e1():
    design = T.load_design()
    engine = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    switch = design["schedule"]["lane_switch_at"]
    core = SemanticCore21.from_engine(engine, REVISED, trace=False)
    out = {"injections": 0, "wrong_supported": 0, "wrong_unique": 0, "withheld": 0,
           "stale_position_ticks": 0}
    for base in F.base_ids(core.predicates):
        fc = F.faulted_core(core, base)
        for t, lane, recs, meta in T.stream(design):
            tr = fc.reason(TR.stamped(recs, meta), TR.context(t, lane, switch))
            out["injections"] += 1
            ag, pos, should = T.grade(design, t, tr)
            out["wrong_unique"] += int(ag == "WRONG_UNIQUE")
            out["stale_position_ticks"] += int(bool(pos) and not should)
            for x in tr.localizations:
                out["withheld"] += int(x.outcome == "WITHHELD_PREDICATE_FAULT")
                if x.symptom == "POSITION_UNAVAILABLE" and x.v2.verdict == SUPPORTED \
                        and t >= switch:
                    out["wrong_supported"] += 1
    return out


def overlay_keeps_stamps(runs):
    engine, res = runs["NOMINAL"]
    recs = tuple(replace(r, provenance=dict(r.provenance or {},
                                            config_epoch={"k": 1})) for r in res[0].records)
    out = {}
    for name in ("aircraft_successor_r1", "aircraft_successor_r2"):
        ov = load_successor(name)
        out[name] = all(r.provenance.get("config_epoch") == {"k": 1} for r in ov.apply(recs))
    return out


def main():
    runs = S.runs_A()
    r2 = load_successor("aircraft_successor_r2")
    out = {"harness": "semantic_core_2_1_revision_worse_answer_search"}
    out["O1_O2_order_and_duplicates"] = order_and_duplicates(runs, r2)
    out["H1_undeclared_pacing_input"] = undeclared_pacing(runs, r2)
    out["X1_fault_on_e1_with_epochs"] = fault_on_e1()
    out["X2_overlay_keeps_epoch_stamps"] = overlay_keeps_stamps(runs)
    for key, src in (("U1_epoch_fail_closed", "EPOCH_ADVERSARIAL_RESULTS.json"),
                     ("U1_no_context", "TRANSITION_REPLAY_RESULTS.json")):
        d = json.loads((RC.HERE / src).read_text())
        if "variants" in d:
            out[key] = {k: {kk: v[kk] for kk in ("missed_position_ticks", "valid_withheld",
                                                  "stale_admitted", "stale_position_ticks")}
                        for k, v in d["variants"].items()}
        else:
            c = d["configurations"]["REVISED_NO_CONTEXT"]
            out[key] = {k: c[k] for k in ("missed_position_symptom_ticks",
                                          "valid_record_ticks_made_unavailable",
                                          "stale_position_symptom_ticks")}
    RC.write_json(OUT, out)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
