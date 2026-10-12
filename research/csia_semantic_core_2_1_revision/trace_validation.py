#!/usr/bin/env python3
"""Phase 14: does the 2.1.1 trace answer the brief's questions? RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/trace_validation.py

Measured by content on real cases, not by trace length:

  Q1 why was the verdict withheld?
       every WITHHELD_PREDICATE_FAULT names the failed predicate, the
       hypothesis and the role (`withheld_because`); every withheld UNIQUE
       names its gate (`withheld_unique_because`)
  Q2 which predicate failed, and did it matter?
       every failed predicate a localization evaluated has a `fault_impact`
       entry per hypothesis naming it, with MATERIAL / NOT_MATERIAL and why
  Q3 why is a dependency pacing or not?
       every OUTPUT_MISSING localization under R-2 shows the pacing inputs
       read and every other declared dependency set aside as
       DECLARED_DEPENDENCY_NOT_PACING; the result carries the digest of the
       pacing declarations (whose justification and source are in the
       successor profile)
  Q4 why was evidence stale, which epoch generated it, what is current?
       every inadmissible record names producer, key, evidence epoch,
       current epoch, reason, action, and the transition event when the
       context gave one
  Q5 which alternative remained?
       every withheld SUPPORTED keeps its survivors; every withheld UNIQUE
       lists the retained hypotheses or unexcluded alternatives

Cases: dataset A under 2.1.1 + r2 (Q1 UNIQUE, Q3, Q5); every tick of
MS_A1 and MS_A2 with each of 6 predicates failed (Q1, Q2, Q5); E1 and the
fourteen epoch variants (Q4). Also the trace's size.

Writes TRACE_VALIDATION.json.
"""
from __future__ import annotations

import json
import statistics
import sys

import revision_common as RC

import epoch_adversarial as EA  # noqa: E402
import predicate_fault_study as F  # noqa: E402
import shadow_validation as S  # noqa: E402
import transition_study as T  # noqa: E402

import semantic_probe as P  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import Corrections, SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import load_successor  # noqa: E402

OUT = RC.HERE / "TRACE_VALIDATION.json"
REVISED = Corrections.revised()
FAULTS = ("NO_TIMING_SEGMENT_OVER_BUDGET", "FUNCTION_TIMING_WITHIN_DEADLINE",
          "ESTIMATOR_PROCESS_HEALTHY", "TRANSPORT_WITHIN_BUDGET",
          "SOURCE_INTERVAL_NOMINAL", "FUNCTION_LINKS_NOMINAL")


def main():
    runs = S.runs_A()
    r2 = load_successor("aircraft_successor_r2")
    out = {"harness": "semantic_core_2_1_revision_trace_validation"}
    q1u = {"withheld_unique": 0, "named_gate": 0, "names_alternative": 0}
    q3 = {"output_missing_localizations": 0, "pacing_read_named": 0,
          "non_pacing_dependencies_named": 0, "result_has_pacing_digest": 0}
    sizes_pre, sizes_rev = [], []
    for name, (engine, res) in runs.items():
        core = SemanticCore21.from_engine(engine, REVISED, trace=True, pacing=r2.pacing_map())
        pre = SemanticCore21.from_engine(engine, trace=True)
        for t, sa in enumerate(res):
            tr = core.reason(r2.apply(sa.records))
            if t % 10 == 0:
                sizes_rev.append(len(json.dumps(tr.to_dict(), default=str)))
                sizes_pre.append(len(json.dumps(pre.reason(sa.records).to_dict(), default=str)))
            a = tr.attribution
            if a.withheld_unique_because:
                q1u["withheld_unique"] += 1
                q1u["named_gate"] += 1
                q1u["names_alternative"] += int(bool(
                    a.trace.get("localization_disagreement") or a.trace.get("unexcluded_alternatives")))
            for x in tr.localizations:
                if x.symptom != "OUTPUT_MISSING":
                    continue
                q3["output_missing_localizations"] += 1
                pt = x.trace["predicates"]["PACING_INPUTS_NOMINAL"]
                q3["pacing_read_named"] += int(bool(pt.get("read")))
                q3["non_pacing_dependencies_named"] += int(
                    set(pt.get("ignored", {}).values()) == {"DECLARED_DEPENDENCY_NOT_PACING"})
                q3["result_has_pacing_digest"] += int(tr.to_dict().get(
                    "pacing_declarations_digest") is not None)
    out["Q1_withheld_unique"] = q1u
    out["Q3_pacing"] = q3
    out["Q3_example"] = None
    engine, res = runs["PROCESS_STALL"]
    core = SemanticCore21.from_engine(engine, REVISED, trace=True, pacing=r2.pacing_map())
    tr = core.reason(r2.apply(res[-1].records))
    x = [x for x in tr.localizations if x.symptom == "OUTPUT_MISSING"][0]
    out["Q3_example"] = {"unit": x.key, "outcome": x.outcome,
                         "rejected": [list(r) for r in x.v2.rejected],
                         "PACING_INPUTS_NOMINAL": x.trace["predicates"]["PACING_INPUTS_NOMINAL"],
                         "pacing_declarations_digest": tr.pacing_digest,
                         "declaration_source": r2.declarations[2].source}
    q12 = {"localizations_with_fault": 0, "every_failed_id_has_impact_entry": 0,
           "withheld": 0, "withheld_names_predicate_hypothesis_role": 0,
           "withheld_keeps_survivors": 0, "material_entries": 0, "not_material_entries": 0}
    example = None
    for name in ("MS_A1_SENSOR_DELAY", "MS_A2_COMMUNICATION_DELAY"):
        engine, res = runs[name]
        core = SemanticCore21.from_engine(engine, REVISED, trace=True, pacing=r2.pacing_map())
        for base in FAULTS:
            fc = F.faulted_core(core, base)
            for sa in res:
                tr = fc.reason(r2.apply(sa.records))
                for x in tr.localizations:
                    if not x.predicate_errors:
                        continue
                    q12["localizations_with_fault"] += 1
                    spec = {s.symptom_id: s for s in core.symptoms}[x.symptom]
                    named = {p for h in spec.hypotheses for p in h.confirmed_by + h.refuted_by}
                    failed = {i for e in x.predicate_errors for i in e.evaluated_as} & named
                    covered = {e["evaluated_as"] for e in x.fault_impact}
                    q12["every_failed_id_has_impact_entry"] += int(failed <= covered)
                    for e in x.fault_impact:
                        q12["material_entries" if e["dependency"] == "MATERIAL"
                            else "not_material_entries"] += 1
                    if x.outcome == "WITHHELD_PREDICATE_FAULT":
                        q12["withheld"] += 1
                        wb = x.trace.get("withheld_because", [])
                        q12["withheld_names_predicate_hypothesis_role"] += int(bool(wb) and all(
                            {"predicate", "hypothesis", "role"} <= set(w) for w in wb))
                        q12["withheld_keeps_survivors"] += int(bool(x.supported or x.unresolved))
                        if example is None:
                            example = {"scenario": name, "unit": x.key, "outcome": x.outcome,
                                       "outcome_reason": x.outcome_reason,
                                       "v2_0_view_verdict": x.v2.verdict,
                                       "survivors": list(x.supported) + list(x.unresolved),
                                       "withheld_because": wb,
                                       "fault_impact": list(x.fault_impact),
                                       "predicate_errors": [e.to_dict() for e in x.predicate_errors]}
    out["Q1_Q2_Q5_predicate_faults"] = q12
    out["Q1_Q2_example"] = example
    q4 = {"inadmissible_entries": 0, "complete_fields": 0, "with_transition_event": 0,
          "without_event_by_reason": {}}
    design = T.load_design()
    base = T.stream(design)
    engine0 = P.run_scenario(SCENARIOS["NOMINAL"], ticks=1)[0]
    core = SemanticCore21.from_engine(engine0, REVISED, trace=True)
    q4_example = None
    for vname in EA.NAMES:
        for t, recs, ctx, _truth in EA.variant(base, vname):
            for e in core.reason(recs, ctx).admission["inadmissible"]:
                q4["inadmissible_entries"] += 1
                q4["complete_fields"] += int(all(k in e for k in (
                    "record", "source", "key", "evidence_epoch", "current_epoch",
                    "reason", "action", "transition_event")))
                if e["transition_event"]:
                    q4["with_transition_event"] += 1
                else:
                    q4["without_event_by_reason"][e["reason"]] = \
                        q4["without_event_by_reason"].get(e["reason"], 0) + 1
                if q4_example is None and vname == "BASE":
                    q4_example = e
    out["Q4_stale_evidence"] = q4
    out["Q4_example"] = q4_example
    out["trace_size_bytes"] = {"2_1_0_median": int(statistics.median(sizes_pre)),
                               "2_1_1_r2_median": int(statistics.median(sizes_rev)),
                               "2_1_0_max": max(sizes_pre), "2_1_1_r2_max": max(sizes_rev),
                               "sampled_ticks": len(sizes_rev)}
    RC.write_json(OUT, out)
    print(json.dumps(out, indent=1, default=str)[:7000])


if __name__ == "__main__":
    sys.exit(main())
