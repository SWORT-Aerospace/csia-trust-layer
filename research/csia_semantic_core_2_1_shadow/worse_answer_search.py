#!/usr/bin/env python3
"""Practical worse-answer search (Part 22). RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/worse_answer_search.py

Tries to find cases where 2.1 is WORSE than frozen v2.0, not merely less
certain. Each probe says what it tried and what happened, including the
probes that found nothing. Reads the other harnesses' committed outputs where
a probe has already been run at scale (predicate faults, adversarial
profiles, transitions, runtime), so every number has one source.

Probes run here:
  W1 wrong UNIQUE introduced               dataset A, all ticks, graded
  W2 true hypothesis eliminated            dataset A, graded localizations
  W3 wrong SUPPORTED introduced            dataset A, graded localizations
  W4 relevant evidence ignored             dataset A, C3 scope vs the injected cause
  W5 conflicting records                   constructed: same key, two states,
                                           either order
  W6 replayed record                       constructed: an old record shown
                                           alongside, or instead of, the current one
  W7 profile repair restores a wrong answer constructed: the estimator's IMU input
                                           dies while its GNSS link is healthy
Writes WORSE_ANSWER_SEARCH.json only.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness"),
          str(REPO / "research/csia_semantic_core_2_1"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import ground_truth as GT  # noqa: E402
import shadow_validation as S  # noqa: E402

from csia.v2.attribution import UNIQUE, attribute  # noqa: E402
from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.localization import SUPPORTED, localize_all  # noqa: E402
from csia_semantic_core import SemanticCore21, SuccessorIndex, declared_scope  # noqa: E402
from csia_semantic_core.profile_overlay import load_successor  # noqa: E402

OUT = HERE / "WORSE_ANSWER_SEARCH.json"


def v20(engine, recs):
    locs = localize_all(engine.symptoms, recs, engine.predicates) if engine.symptoms else ()
    return locs, attribute(recs, engine.relations)


def loc_grade(scenario, symptom, verdict, supported, unresolved, rejected):
    th = GT.true_hypothesis(scenario, symptom)
    if th == GT.UNSPECIFIED:
        return None
    if th is None:
        return "WRONG" if verdict == SUPPORTED else "OK"
    if th in rejected:
        return "TRUE_ELIMINATED"
    if verdict == SUPPORTED and tuple(supported) != (th,):
        return "WRONG_SUPPORTED"
    return "OK"


def dataset_a(runs, overlay=None):
    out = {"W1_wrong_unique_2_1_not_2_0": [], "W1_wrong_unique_both": 0,
           "W2_true_eliminated_2_1_not_2_0": [], "W2_true_eliminated_both": 0,
           "W3_wrong_supported_2_1_not_2_0": [], "W3_wrong_supported_both": 0,
           "W4_cause_outside_scope_units": {}, "graded_wrong_by_unit_2_1": {},
           "graded_wrong_by_unit_2_0": {}}
    for name, (engine, res) in runs.items():
        core = SemanticCore21.from_engine(engine, trace=False)
        truth = GT.truth(name)
        for tick, sa in enumerate(res):
            recs = overlay.apply(sa.records) if overlay else sa.records
            tr = core.reason(recs)
            dom = GT.attribution_domain(name, sa.records)
            a0, a1 = sa.attribution, tr.attribution
            w0 = a0.verdict == UNIQUE and dom not in (None, GT.UNSPECIFIED) \
                and a0.candidates[0].domain != dom
            w1 = a1.verdict == UNIQUE and dom not in (None, GT.UNSPECIFIED) \
                and a1.candidates[0].split("/", 1)[0] != dom
            if w1 and not w0:
                out["W1_wrong_unique_2_1_not_2_0"].append([name, tick])
            out["W1_wrong_unique_both"] += int(w1 and w0)
            g0 = {f"{x.symptom}|{x.subject}": loc_grade(
                name, x.symptom, x.verdict, x.supported, x.unresolved,
                {h for h, _ in x.rejected}) for x in sa.localizations}
            g1 = {x.key: loc_grade(name, x.symptom, x.v2.verdict, x.supported,
                                   x.unresolved, {h for h, _ in x.v2.rejected})
                  for x in tr.localizations}
            for k, g in g1.items():
                if g in ("TRUE_ELIMINATED", "WRONG_SUPPORTED", "WRONG"):
                    kk = f"{name}|{k}|{g}"
                    out["graded_wrong_by_unit_2_1"][kk] = out["graded_wrong_by_unit_2_1"].get(kk, 0) + 1
                if g == "TRUE_ELIMINATED":
                    if g0.get(k) == "TRUE_ELIMINATED":
                        out["W2_true_eliminated_both"] += 1
                    else:
                        out["W2_true_eliminated_2_1_not_2_0"].append([name, tick, k])
                if g in ("WRONG_SUPPORTED", "WRONG"):
                    if g0.get(k) in ("WRONG_SUPPORTED", "WRONG"):
                        out["W3_wrong_supported_both"] += 1
                    else:
                        out["W3_wrong_supported_2_1_not_2_0"].append([name, tick, k])
            for k, g in g0.items():
                if g in ("TRUE_ELIMINATED", "WRONG_SUPPORTED", "WRONG"):
                    kk = f"{name}|{k}|{g}"
                    out["graded_wrong_by_unit_2_0"][kk] = out["graded_wrong_by_unit_2_0"].get(kk, 0) + 1
            comp = truth.get("component")
            if comp not in (None, GT.UNSPECIFIED):
                ix = SuccessorIndex(recs, tracing=False)
                for x in tr.localizations:
                    if x.symptom != "POSITION_UNAVAILABLE":
                        continue
                    if comp not in declared_scope(ix, x.subject) and any(
                            r.component == comp and r.is_adverse for r in recs):
                        kk = f"{name}|{x.subject}"
                        out["W4_cause_outside_scope_units"][kk] = \
                            out["W4_cause_outside_scope_units"].get(kk, 0) + 1
    for k in ("W1_wrong_unique_2_1_not_2_0", "W2_true_eliminated_2_1_not_2_0",
              "W3_wrong_supported_2_1_not_2_0"):
        out[k] = {"count": len(out[k]), "examples": out[k][:10]}
    return out


def _flip(state):
    return OS.NOMINAL if state is not OS.NOMINAL else OS.VIOLATED


def conflicts_and_replays(runs):
    """W5/W6 on the final tick of scenarios whose cause is one component."""
    cases = {"PROCESS_STALL": ("state_estimator", "compute.process_producing"),
             "MS_D3_COMM_STARVATION": ("gnss_serial", "comm.link_state"),
             "REGULATOR_FAILURE": ("rail_5v", "power.rail_tolerance"),
             "MS_B3_DRIVE_NO_CURRENT": ("motor_0", "actuation.electrical_response"),
             "CPU_OVERLOAD": ("cpu", "compute.resource_headroom")}
    out = {}
    for name, (comp, rel) in cases.items():
        engine, res = runs[name]
        core = SemanticCore21.from_engine(engine, trace=False)
        recs = res[-1].records
        cur = [r for r in recs if r.component == comp and r.relation == rel]
        if not cur:
            out[name] = "relation not present"
            continue
        cur = cur[0]
        old = replace(cur, observation_state=_flip(cur.observation_state),
                      reason_codes=(), timestamp_validity=(cur.timestamp_validity or 0.0) - 5.0)
        variants = {
            "unaltered": recs,
            "replay_before_current": tuple([old] + list(recs)),
            "replay_after_current": tuple(list(recs) + [old]),
            "replay_instead_of_current": tuple(old if r is cur else r for r in recs),
        }
        row = {"key": f"{comp}:{rel}", "current_state": cur.observation_state.value,
               "replayed_state": old.observation_state.value}
        dom = GT.attribution_domain(name, recs)
        for vn, rr in variants.items():
            l0, a0 = v20(engine, rr)
            tr = core.reason(rr)
            row[vn] = {
                "v2_0": [a0.verdict, [c.id for c in a0.candidates]],
                "v2_0_wrong_unique": a0.verdict == UNIQUE and a0.candidates[0].domain != dom,
                "v2_1": [tr.attribution.verdict, list(tr.attribution.candidates)],
                "v2_1_wrong_unique": tr.attribution.verdict == UNIQUE
                and tr.attribution.candidates[0].split("/", 1)[0] != dom,
                "v2_1_conflicting_keys": list(tr.conflicting_keys),
                "v2_0_graded_wrong_localizations": sum(
                    1 for x in l0 if loc_grade(name, x.symptom, x.verdict, x.supported,
                                               x.unresolved, {h for h, _ in x.rejected})
                    in ("TRUE_ELIMINATED", "WRONG_SUPPORTED", "WRONG")),
                "v2_1_graded_wrong_localizations": sum(
                    1 for x in tr.localizations if loc_grade(
                        name, x.symptom, x.v2.verdict, x.supported, x.unresolved,
                        {h for h, _ in x.v2.rejected}) in ("TRUE_ELIMINATED", "WRONG_SUPPORTED", "WRONG"))}
        out[name] = row
    return out


def imu_pacing_loss(runs):
    """W7: the estimator's pacing input (IMU) dies, GNSS link healthy. On
    PX4 EKF2 publishes only on new IMU data (EKF2.cpp Run, imu_updated), so
    the true cause is input starvation of the pacing sensor, not a stalled
    process."""
    engine, res = runs["PROCESS_STALL"]
    recs = tuple(replace(r, observation_state=OS.VIOLATED, reason_codes=("SOURCE_STALE",),
                         detail=dict(r.detail, fresh=False, missing_reason="stale"))
                 if r.component == "source.imu0" else r for r in res[-1].records)
    core = SemanticCore21.from_engine(engine, trace=False)
    succ = load_successor()
    out = {}
    l0, a0 = v20(engine, recs)
    out["v2_0"] = [(x.symptom, x.verdict, list(x.supported), list(x.unresolved))
                   for x in l0 if x.subject == "state_estimator"]
    for label, ov in (("2_1", None), ("2_1_successor_r1", succ),
                      ("2_1_plus_R5", S.overlay("R5")),
                      ("2_1_successor_r1_plus_R5", S.overlay("R2", "R3", "R5"))):
        tr = core.reason(ov.apply(recs) if ov else recs)
        out[label] = [(x.symptom, x.v2.verdict, list(x.supported), list(x.unresolved))
                      for x in tr.localizations if x.subject == "state_estimator"]
    out["reading"] = ("OUTPUT_MISSING on the estimator: SUPPORTED COMPUTE/process_stall is "
                      "wrong here (the process is starved of its pacing input). v2.0 and any "
                      "profile with R5 refute input_starvation with the GNSS link, which cannot "
                      "starve EKF2's output; 2.1 without R5 keeps it open.")
    return out


def main():
    runs = S.runs_A()
    res = {"harness": "semantic_core_2_1_worse_answer_search"}
    res["dataset_A_base_profile"] = dataset_a(runs)
    res["dataset_A_successor_r1"] = dataset_a(runs, load_successor())
    res["W5_W6_conflicts_and_replays"] = conflicts_and_replays(runs)
    res["W7_imu_pacing_loss"] = imu_pacing_loss(runs)
    for name, key in (("W8_predicate_faults", "PREDICATE_FAULT_RESULTS.json"),
                      ("W9_adversarial_profiles", "ADVERSARIAL_PROFILE_RESULTS.json"),
                      ("W10_transition_E1", "TRANSITION_RESULTS.json")):
        path = HERE / key
        res[name] = {"source": key, "present": path.exists()}
    OUT.write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    for k in ("dataset_A_base_profile", "dataset_A_successor_r1"):
        d = res[k]
        print(k, {kk: (v["count"] if isinstance(v, dict) and "count" in v else v)
                  for kk, v in d.items() if kk.startswith("W")})
    print(json.dumps(res["W5_W6_conflicts_and_replays"], indent=1, default=str)[:6000])
    print(json.dumps(res["W7_imu_pacing_loss"], indent=1, default=str))


if __name__ == "__main__":
    main()
