#!/usr/bin/env python3
"""Phases 28-29: historical replay through 2.2, with difference receipts.
NON-CONFIRMATORY. RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_evidence_assurance/replay_2_2.py

The question at every slot: does 2.2 change a decision 2.1.1 would make on
the same evidence? It may change one only by correctly rejecting evidence,
and every change gets a receipt.

| corpus | comparator | slots |
|---|---|---|
| the 44 frozen v2 scenarios, 60 ticks each | 2.1.1 (`Corrections.revised()`) + r2 on aircraft, the frozen profile elsewhere, on the same records | 2,640 ticks |
| XSYS-001, every trial, checkpoint, variant and motor, from the sealed stage-1 features | 2.1.1 on `xsys_v2_adapter.records_for`, exactly as the revision's XSYS gate | 3,872 |
| E1 | the revision's REVISED_2_1_1_R2 (`e1_2_2.py`) | 60 ticks |

For XSYS, the confirmatory primary result (C3 / V3_TEMPORAL) is recomputed
from 2.2's decisions with stage 2's own scoring functions.

Writes REPLAY_2_2_RESULTS.json and DIFFERENCE_RECEIPTS.json.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter

import common_2_2 as C

import e1_2_2  # noqa: E402

from csia.v2 import scenarios as SC  # noqa: E402
from csia.v2.profiles import SCENARIOS, build_engine_for  # noqa: E402
from csia.v2.profiles.aircraft_scenarios import example_payload_feed  # noqa: E402
from csia_evidence_assurance import profile_gate as PG  # noqa: E402
from csia_evidence_assurance.adapters import v2_domains as V2  # noqa: E402
from csia_evidence_assurance.adapters import xsys_witness as XW  # noqa: E402
from csia_evidence_assurance.analyzer import FlightAssuranceAnalyzer  # noqa: E402
from csia_evidence_assurance.contract import load_contracts  # noqa: E402
from csia_semantic_core import Corrections, SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import load_successor  # noqa: E402

OUT = C.HERE / "REPLAY_2_2_RESULTS.json"
RECEIPTS = C.HERE / "DIFFERENCE_RECEIPTS.json"
TICKS = 60
XSYS_BASE = "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py"


def norm(x):
    return json.loads(json.dumps(x, sort_keys=True, default=str))


# ------------------------------------------------------------------ v2 corpus
def corpus():
    out = {"scenarios": 0, "ticks": 0, "rejected": Counter(), "decision_differences": 0,
           "gates": Counter(), "per_scenario": {}}
    for name in sorted(SCENARIOS):
        sc = SCENARIOS[name]
        engine = build_engine_for(sc)
        feed = (example_payload_feed(getattr(sc, "v1_1_variant", "clean"))
                if sc.system == "aircraft" else None)
        res = SC.run(engine, sc, ticks=TICKS, payload_for=feed)
        ov = load_successor(V2.SUCCESSOR[sc.system]) if sc.system in V2.SUCCESSOR else None
        base = V2.PROFILE_BASE[sc.system]
        contracts = V2.legacy_contracts(engine, base)
        core = SemanticCore21.from_engine(engine, Corrections.revised(), trace=True,
                                          pacing=ov.pacing_map() if ov else None)
        gate = PG.gate(ov, res[0].records, engine.functions)
        out["gates"][f"{sc.system}:{gate.status}"] += 1
        an = FlightAssuranceAnalyzer(core, contracts, gate, base)
        diffs = rej = 0
        for sa in res:
            recs = ov.apply(sa.records) if ov else sa.records
            r = an.step(float(sa.t), V2.envelopes(recs, sa.t, contracts))
            d = core.reason(recs)
            for x in r.evidence["rejected"]:
                out["rejected"][f"{x['status']}:{x['reasons'][0]}"] += 1
                rej += 1
            old = (d.attribution.verdict, list(d.attribution.candidates),
                   [(x.key, x.outcome, list(x.supported), list(x.unresolved)) for x in d.localizations])
            new = (r.attribution["verdict"], r.attribution["candidates"],
                   [(x["key"], x["outcome"], x["supported"], x["unresolved"])
                    for x in r.localizations])
            diffs += int(norm(old) != norm(new))
        out["scenarios"] += 1
        out["ticks"] += len(res)
        out["decision_differences"] += diffs
        out["per_scenario"][name] = {"system": sc.system, "ticks": len(res),
                                     "rejected": rej, "decision_differences": diffs}
    out["rejected"] = dict(sorted(out["rejected"].items()))
    out["gates"] = dict(sorted(out["gates"].items()))
    return out


# ------------------------------------------------------------------ XSYS-001
def xsys():
    S1, XA, _XF = XW.pipeline()
    import stage2_score as S2
    data = json.loads((XW.CAMPAIGN / "stage1/STAGE1.json").read_text())
    results = json.loads((XW.CAMPAIGN / "stage2/RESULTS.json").read_text())
    record = json.loads((XW.CAMPAIGN / "stage2/PRIMARY_RESULT_RECORD.json").read_text())
    key = json.loads((XW.CAMPAIGN / "stage0/KEY.json").read_text())["trials"]
    contracts = load_contracts(*XW.CONTRACT_FILES)
    gate = PG.not_applicable("xsys001_research_spec", XSYS_BASE, "no function table")
    direct = SemanticCore21((XA.SPEC,), XA.PREDICATES, (), Corrections.revised(), trace=False)
    core = SemanticCore21((XA.SPEC,), XA.PREDICATES, (), Corrections.revised(), trace=True)
    n, diffs, rejected = 0, Counter(), Counter()
    receipts, verdicts_old, verdicts_new = [], {}, {}
    for oid, t in sorted(data["trials"].items()):
        vo, vn = verdicts_old.setdefault(oid, {}), verdicts_new.setdefault(oid, {})
        for vc in sorted(t["verdicts"]):
            cp, v = vc.split("/")
            po, pn = vo.setdefault(vc, {}), vn.setdefault(vc, {})
            for subj in sorted(t["features"]):
                f = t["features"][subj]
                rpm, dyn, ctrl, w = S1.plan(v, cp, f)
                stats = {"L": f["L_T1"] if cp == "C1" else f["L_T3"],
                         "D": f["D_T3"] if v == "V4_INVALID_WINDOW" else f["D_T1"],
                         "C": f["C_T3"]}
                recs = XA.records_for(subj, rpm, dyn, ctrl, stats, w)
                old = [x for x in direct.reason(recs).localizations if x.subject == subj]
                an = FlightAssuranceAnalyzer(core, contracts, gate, XSYS_BASE)
                res = an.step(XW.CHECKPOINT_T[cp], XW.envelopes(subj, f, v, cp),
                              events={XW.ONSET: 0.0})
                new = [x for x in an.last_tick.localizations if x.subject == subj]
                po[subj] = None if not old else norm(old[0].to_v2_0_dict())
                pn[subj] = None if not new else norm(new[0].to_v2_0_dict())
                for x in res.evidence["rejected"]:
                    rejected[f"{v}/{cp}:{x['status']}"] += 1
                n += 1
                pick = ("verdict", "supported", "unresolved", "rejected")
                od = None if po[subj] is None else {k: po[subj][k] for k in pick}
                nd = None if pn[subj] is None else {k: pn[subj][k] for k in pick}
                if od == nd:
                    continue
                diffs[f"{v}/{cp}"] += 1
                k = key[oid]
                truth_h = S2.TRUTH_H.get(k["kind"])
                receipts.append(_xsys_receipt(oid, k, vc, subj, recs, res, od, nd,
                                              S2.outcome_symptomatic(po[subj], truth_h)
                                              if truth_h and subj == "motor_0" else None,
                                              S2.outcome_symptomatic(pn[subj], truth_h)
                                              if truth_h and subj == "motor_0" else None))
    p_old = _primary(S2, results, verdicts_old)
    p_new = _primary(S2, results, verdicts_new)
    return {"slots": n, "decision_differences": dict(sorted(diffs.items())),
            "rejected": dict(sorted(rejected.items())),
            "primary_C3_V3_from_2_1_1": p_old, "primary_C3_V3_from_2_2": p_new,
            "primary_unchanged": ({k: v for k, v in p_old.items() if k != "outcomes"}
                                  == {k: v for k, v in p_new.items() if k != "outcomes"}),
            "outcomes_changed_outside_V4_C3": sum(
                1 for c in p_old["outcomes"] if c != "C3/V4_INVALID_WINDOW"
                and p_old["outcomes"][c] != p_new["outcomes"].get(c)),
            "primary_matches_sealed_record": (
                p_new["n_pairs"] == record["VALID_MATCHED_PAIRS"]
                and p_new["n_success"] == record["RESOLVED_MATCHED_PAIRS"]
                and p_new["lower95"] == record["ONE_SIDED_95_LB"]
                and p_new["wrong_A_B"] == record["WRONG"])}, receipts


def _xsys_receipt(oid, k, vc, subj, recs, res, od, nd, o_old, o_new):
    old_adm = [f"{r.domain}/{r.component}:{r.relation}={r.observation_state.value}"
               f" (window {r.detail.get('window')})" for r in recs
               if r.detail.get("window") != "withheld"]
    rej = res.evidence["rejected"]
    return {
        "corpus": "XSYS-001", "slot": f"{k['analysis_id']}|{vc}|{subj}", "opaque_id": oid,
        "truth": k["truth"],
        "OLD_ADMITTED_EVIDENCE": old_adm,
        "NEW_REJECTED_EVIDENCE": [x["evidence_id"] for x in rej],
        "REJECTION_REASON": [f"{x['status']}: {'; '.join(x['reasons'])}" for x in rej],
        "OLD_VERDICT": od, "NEW_VERDICT": nd,
        "OLD_OUTCOME_AGAINST_TRUTH": o_old, "NEW_OUTCOME_AGAINST_TRUTH": o_new,
        "EXPECTED": "YES" if rej and all(x["status"] == "REGIME_INVALID" for x in rej) else "NO",
        "WHY": ("W_DYN was validated in T1 only (0-200 ms after onset). This variant feeds the "
                "same statistic computed over T3 (10-15 s), which the frozen harness itself "
                "labels 'INVALID: outside its window'. 2.2's contract states the validated "
                "window, so the output is REGIME_INVALID and reaches 2.1.1 as UNAVAILABLE. "
                "The verdict is then what the remaining valid evidence supports."),
    }


def _primary(S2, results, verdicts):
    import numpy as np
    per_trial = {}
    for aid, k in results["trials"].items():
        v = verdicts[k["opaque_id"]]
        outc = {}
        for cpv, per_motor in v.items():
            outc[cpv] = (S2.outcome_nominal(per_motor) if k["kind"] == "N" else
                         S2.outcome_symptomatic(per_motor.get("motor_0"), S2.TRUTH_H[k["kind"]]))
        per_trial[aid] = {**k, "outcomes": outc}
    pairs: dict = {}
    for t in per_trial.values():
        if t["kind"] in ("A", "B"):
            pairs.setdefault(t["pair_id"], {})[t["kind"]] = t
    cpv = "/".join(S2.PRIMARY)
    by_cond: dict = {}
    for p in pairs.values():
        if "A" in p and "B" in p:
            ok = (p["A"]["outcomes"].get(cpv) == "UNIQUE_CORRECT"
                  and p["B"]["outcomes"].get(cpv) == "UNIQUE_CORRECT")
            by_cond.setdefault(p["A"]["nuisance_id"], []).append(1.0 if ok else 0.0)
    vals = [x for xs in by_cond.values() for x in xs]
    res = S2.cluster_bound(float(np.mean(vals)) if vals else 0.0, len(by_cond))
    wrong = sum(1 for t in per_trial.values() if t["kind"] in ("A", "B")
                and t["outcomes"].get(cpv) == "WRONG")
    res.update({"n_pairs": len(vals), "n_success": int(sum(vals)), "wrong_A_B": wrong})
    outcomes_by_cpv: dict = {}
    for t in per_trial.values():
        for c, o in t["outcomes"].items():
            outcomes_by_cpv.setdefault(c, Counter())[f"{t['kind']}:{o}"] += 1
    res["outcomes"] = {c: dict(sorted(v.items())) for c, v in sorted(outcomes_by_cpv.items())}
    return res


def main():
    t0 = time.perf_counter()
    out = {"label": "NON-CONFIRMATORY; historical replay through 2.2 against 2.1.1",
           "baseline": C.REVISION_HEAD}
    out["v2_corpus"] = corpus()
    out["xsys"], receipts = xsys()
    e1 = e1_2_2.run()["result"]
    out["e1"] = {k: e1[k] for k in ("attribution", "stale_position_symptom_ticks",
                                    "missed_position_symptom_ticks", "config_mismatch_ticks",
                                    "recovery_tick", "per_tick_equal_to_revision_REVISED_2_1_1_R2",
                                    "pre_2_1_0_stale_position_symptom_ticks")}
    cls = Counter((r["OLD_OUTCOME_AGAINST_TRUTH"], r["NEW_OUTCOME_AGAINST_TRUTH"])
                  for r in receipts)
    out["receipts"] = {"count": len(receipts),
                       "expected": sum(r["EXPECTED"] == "YES" for r in receipts),
                       "unexpected": sum(r["EXPECTED"] != "YES" for r in receipts),
                       "outcome_transitions": {f"{a} -> {b}": n for (a, b), n in
                                               sorted(cls.items(), key=str)}}
    out["seconds"] = round(time.perf_counter() - t0, 1)
    C.write_json(OUT, out)
    C.write_json(RECEIPTS, {"label": "Phase 29 difference receipts: one per changed decision",
                            "receipts": receipts})
    print(json.dumps({"v2": {k: out["v2_corpus"][k] for k in
                             ("scenarios", "ticks", "rejected", "decision_differences", "gates")},
                      "xsys": {k: out["xsys"][k] for k in
                               ("slots", "decision_differences", "rejected", "primary_unchanged",
                                "outcomes_changed_outside_V4_C3",
                                "primary_matches_sealed_record")},
                      "e1": out["e1"], "receipts": out["receipts"], "s": out["seconds"]},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
