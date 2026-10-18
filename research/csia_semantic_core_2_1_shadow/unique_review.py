#!/usr/bin/env python3
"""The seven weakened UNIQUE scenarios and the two corrected wrong UNIQUE
scenarios (Parts 8, 9, 46). RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/unique_review.py

For every scenario where 2.1 withheld a UNIQUE that frozen v2.0 gave, this
records, from the decision traces rather than the ground-truth label:
- which gate withheld it (C1 and/or F2) and on which ticks;
- for F2, each hypothesis the same-tick localization retains, whether it is
  retained CONFIRMED (a confirming predicate is True) or only UNRESOLVED,
  and whether its refuters were MEASURED FALSE or UNMEASURED (None);
- the frozen v2.0 discriminators the UNIQUE rested on, and whether each is
  a declared alternative of the candidate (relevant) or not;
- whether the UNIQUE comes back under the successor profile r1, under r1
  plus the rejected candidate R5, and under every candidate together.

For the two wrong-cause UNIQUE verdicts that 2.1 withholds (MS_B5 and
MS_TS_B5), it checks every tick under every profile variant, and compares
their evidence with their matched twins (MS_B4, MS_TS_B4): if the twins'
evidence is identical tick by tick, no reasoner can name a different unique
cause for them, and a UNIQUE on one is a UNIQUE on the other.

Writes UNIQUE_REVIEW.json only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness"),
          str(REPO / "research/csia_semantic_core_2_1"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import semantic_probe as P  # noqa: E402
import shadow_validation as S  # noqa: E402

from csia.v2.attribution import UNIQUE  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import (ProfileOverlay,  # noqa: E402
                                                load_successor)

OUT = HERE / "UNIQUE_REVIEW.json"
WEAKENED = ("ACTUATOR_NO_RESPONSE", "CLOCK_DRIFT", "MS_B3_DRIVE_NO_CURRENT",
            "MS_B4_MECHANICAL", "STALLED_ACTUATOR", "PROCESS_STALL",
            "MS_D2_ESTIMATOR_STALE", "TS_STALLED")
WRONG = ("MS_B5_RESPONSE_SENSOR", "MS_TS_B5_RESPONSE_SENSOR")
TWINS = {"MS_B5_RESPONSE_SENSOR": "MS_B4_MECHANICAL",
         "MS_TS_B5_RESPONSE_SENSOR": "MS_TS_B4_MECHANICAL"}


def variants():
    succ = load_successor("aircraft_successor_r1")
    r5 = S.overlay("R5")
    return {"none": None, "successor_r1": succ,
            "successor_r1_plus_R5": ProfileOverlay(
                succ.name, "r1+R5", succ.base_profile,
                succ.declarations + r5.declarations),
            "successor_r1_plus_R5a": ProfileOverlay(
                succ.name, "r1+R5a", succ.base_profile,
                succ.declarations + S.overlay("R5a").declarations),
            "all_candidates_R1_R5": S.overlay("R1", "R2", "R3", "R4", "R5"),
            "with_R_BAD": S.overlay("R1", "R2", "R3", "R4", "R5", "R-BAD")}


def retained_detail(spec, loc, hid):
    h = {x.hypothesis_id: x for x in spec.hypotheses}[hid]
    vals = loc.v2.detail["predicate_values"]
    return {"hypothesis": hid,
            "retained_as": "CONFIRMED" if hid in loc.supported else "UNRESOLVED",
            "confirmers": {p: vals.get(p) for p in h.confirmed_by},
            "refuters": {p: vals.get(p) for p in h.refuted_by},
            "refuters_all_unmeasured": bool(h.refuted_by) and all(
                vals.get(p) is None for p in h.refuted_by),
            "refuters_measured_false": [p for p in h.refuted_by if vals.get(p) is False]}


def tick_detail(core, specs, sa, recs):
    tr = core.reason(recs)
    a = tr.attribution
    cand = a.candidates[0] if a.candidates else None
    comp = cand.split("/", 1)[1] if cand else None
    f2 = []
    for x in tr.localizations:
        if x.subject != comp:
            continue
        dom = cand.split("/", 1)[0]
        kept = [h for h in tuple(x.supported) + tuple(x.unresolved)
                if h.split("/", 1)[0] != dom]
        if kept:
            f2.append({"symptom": x.symptom, "verdict": x.v2.verdict,
                       "retained": [retained_detail(specs[x.symptom], x, h)
                                    for h in kept]})
    alts = set(a.trace.get("declared_alternatives", ()))
    v20 = sa.attribution
    return {"v2_0": {"verdict": v20.verdict,
                     "candidates": [c.id for c in v20.candidates],
                     "discriminators": [
                         {"id": d, "declared_alternative_of_candidate":
                          d.split(":", 1)[0] in alts}
                         for d in v20.discriminators]},
            "v2_1": {"verdict": a.verdict, "candidates": list(a.candidates),
                     "withheld_because": list(a.withheld_unique_because),
                     "declared_alternatives": sorted(alts),
                     "unexcluded_alternatives": a.trace.get("unexcluded_alternatives", []),
                     "relevant_discriminators": a.trace.get("relevant_discriminators", []),
                     "f2_retained": f2}}


def evidence_signature(records):
    return sorted((r.domain, r.component, r.relation, r.observation_state.value,
                   tuple(r.reason_codes)) for r in records)


def main():
    V = variants()
    out = {"harness": "semantic_core_2_1_unique_review",
           "variants": {k: (None if v is None else v.digest()) for k, v in V.items()},
           "weakened": {}, "wrong_unique": {}, "twins": {}}
    cache = {}
    for name in WEAKENED + WRONG + tuple(TWINS.values()):
        cache[name] = P.run_scenario(SCENARIOS[name])
    for name in WEAKENED:
        engine, res = cache[name]
        core = SemanticCore21.from_engine(engine, trace=True)
        specs = {s.symptom_id: s for s in core.symptoms}
        per = {}
        for vname, ov in V.items():
            u = [t for t, sa in enumerate(res)
                 if core.reason(ov.apply(sa.records) if ov else sa.records)
                 .attribution.verdict == UNIQUE]
            per[vname] = u
        v20_unique = [t for t, sa in enumerate(res) if sa.attribution.verdict == UNIQUE]
        weakened = sorted(set(v20_unique) - set(per["none"]))
        pick = weakened[-1]
        gates = {}
        for t in weakened:
            tr = core.reason(res[t].records)
            k = "+".join(tr.attribution.withheld_unique_because)
            gates[k] = gates.get(k, 0) + 1
        out["weakened"][name] = {
            "v2_0_unique_ticks": len(v20_unique),
            "weakened_ticks": len(weakened),
            "weakened_first_last": [weakened[0], weakened[-1]],
            "withheld_by": gates,
            "unique_ticks_by_variant": {k: len(v) for k, v in per.items()},
            "weakened_ticks_restored_by_variant": {
                k: len(set(weakened) & set(v)) for k, v in per.items()},
            "detail_at_tick": pick,
            "detail": tick_detail(core, specs, res[pick], res[pick].records),
            "detail_under_successor_r1": tick_detail(
                core, specs, res[pick], V["successor_r1"].apply(res[pick].records))["v2_1"]}
    for name in WRONG:
        engine, res = cache[name]
        core = SemanticCore21.from_engine(engine, trace=True)
        specs = {s.symptom_id: s for s in core.symptoms}
        row = {"v2_0_wrong_unique_ticks": sum(
            1 for sa in res if sa.attribution.verdict == UNIQUE
            and sa.attribution.candidates[0].domain != "SENSOR")}
        for vname, ov in V.items():
            n = 0
            for sa in res:
                a = core.reason(ov.apply(sa.records) if ov else sa.records).attribution
                n += int(a.verdict == UNIQUE and a.candidates[0].split("/", 1)[0] != "SENSOR")
            row[f"wrong_unique_ticks_{vname}"] = n
        last = res[-1]
        row["detail_final"] = tick_detail(core, specs, last, last.records)
        out["wrong_unique"][name] = row
    for b5, b4 in TWINS.items():
        r5, r4 = cache[b5][1], cache[b4][1]
        same = sum(evidence_signature(x.records) == evidence_signature(y.records)
                   for x, y in zip(r5, r4))
        v20_same = sum(x.attribution.verdict == y.attribution.verdict
                       and [c.id for c in x.attribution.candidates]
                       == [c.id for c in y.attribution.candidates]
                       for x, y in zip(r5, r4))
        first_diff = next((t for t, (x, y) in enumerate(zip(r5, r4))
                           if evidence_signature(x.records) != evidence_signature(y.records)), None)
        diff_example = None
        if first_diff is not None:
            a = set(evidence_signature(r5[first_diff].records))
            b = set(evidence_signature(r4[first_diff].records))
            diff_example = {"only_in_" + b5: [list(x) for x in sorted(a - b)][:6],
                            "only_in_" + b4: [list(x) for x in sorted(b - a)][:6]}
        out["twins"][f"{b5}~{b4}"] = {
            "ticks": len(r5), "ticks_with_identical_evidence_states": same,
            "ticks_where_v2_0_gives_the_same_attribution": v20_same,
            "first_tick_evidence_differs": first_diff,
            "difference_at_that_tick": diff_example}
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
    brief = {k: {kk: v[kk] for kk in ("weakened_ticks", "withheld_by",
                                      "weakened_ticks_restored_by_variant")}
             for k, v in out["weakened"].items()}
    print(json.dumps({"weakened": brief, "wrong": {k: {kk: vv for kk, vv in v.items()
                                                       if kk != "detail_final"}
                                                   for k, v in out["wrong_unique"].items()},
                      "twins": out["twins"]}, indent=1))


if __name__ == "__main__":
    main()
