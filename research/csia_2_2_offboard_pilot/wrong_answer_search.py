#!/usr/bin/env python3
"""Phase 18: an adversarial search for wrong answers on real pilot data.
NON-CONFIRMATORY. RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_offboard_pilot/wrong_answer_search.py

Every probe starts from real outputs:
- run S1's estimator envelopes (committed extract);
- the XSYS-001 witness envelopes of every trial (sealed features);
- the campaign results (CAMPAIGN_XSYS.json).

It records each finding with a minimal reproduction.

| probe | wrong answer looked for |
|---|---|
| P1 | wrong UNIQUE or wrong SUPPORTED, every XSYS-001 trial × checkpoint × variant, through the Analyzer |
| P2 | the true hypothesis removed (eliminated) |
| P3 | valid evidence rejected: any refusal of an estimator output after alignment, or of a witness inside its window |
| P4 | invalid evidence admitted: 14 single mutations of real envelopes |
| P5 | dependent evidence treated as independent: 2.2's independent lines against the ground-truth source analysis, every trial |
| P6 | no coverage treated as nominal |
| P7 | a producer fault treated as a vehicle fault: FAULTED producers saying VIOLATED, injected into real ticks |
| P8 | configuration reset mishandled: every real reset reported once, no estimator output refused for a reset |
| P9 | timeline order and content-time errors in every report produced here |

Writes WRONG_ANSWER_SEARCH.json.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace

import numpy as np

import common_pilot as C

from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia_evidence_assurance import report as R  # noqa: E402
from csia_evidence_assurance import runs  # noqa: E402
from csia_evidence_assurance.adapters import px4_estimator as PX  # noqa: E402
from csia_evidence_assurance.adapters import xsys_witness as XW  # noqa: E402
from csia_evidence_assurance.admissibility import AnalysisContext, assess  # noqa: E402
from csia_evidence_assurance.analyzer import FlightAssuranceAnalyzer  # noqa: E402
from csia_evidence_assurance.contract import load_contracts  # noqa: E402
from csia_evidence_assurance.health import ProducerHealth  # noqa: E402
from csia_semantic_core.admission import EpochContext  # noqa: E402

OUT = C.HERE / "WRONG_ANSWER_SEARCH.json"
S1 = C.HERE / "data/S1_estimator_extract.npz"
XSYS_BASE = "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py"


def xsys_slots():
    """P1, P2, P3 (witness side), P9 over every XSYS-001 slot."""
    S1m, XA, _XF = XW.pipeline()
    import stage2_score as S2
    from csia_evidence_assurance import profile_gate as PG
    from csia_semantic_core import Corrections, SemanticCore21
    data = json.loads((XW.CAMPAIGN / "stage1/STAGE1.json").read_text())
    key = json.loads((XW.CAMPAIGN / "stage0/KEY.json").read_text())["trials"]
    core = SemanticCore21((XA.SPEC,), XA.PREDICATES, (), Corrections.revised(), trace=True)
    C3 = load_contracts(*XW.CONTRACT_FILES)
    gate = PG.not_applicable("xsys001_research_spec", XSYS_BASE, "no function table")
    found = {"wrong_unique_or_supported": [], "true_hypothesis_removed": [],
             "valid_witness_rejected": [], "slots": 0, "outcomes": {}}
    for oid, t in sorted(data["trials"].items()):
        k = key[oid]
        truth_h = S2.TRUTH_H.get(k["kind"])
        for vc in sorted(t["verdicts"]):
            cp, v = vc.split("/")
            for subj in sorted(t["features"]):
                an = FlightAssuranceAnalyzer(core, C3, gate, XSYS_BASE)
                envs = XW.envelopes(subj, t["features"][subj], v, cp)
                r = an.step(XW.CHECKPOINT_T[cp], envs, events={XW.ONSET: 0.0})
                found["slots"] += 1
                for x in r.evidence["rejected"]:
                    w = x["evidence_id"].split("|")[0]
                    if not (w == "xsys:w_dyn" and v == "V4_INVALID_WINDOW"):
                        found["valid_witness_rejected"].append([k["analysis_id"], vc, subj, x])
                loc = [x for x in r.localizations if x["subject"] == subj]
                if not loc or subj != "motor_0" or truth_h is None:
                    continue
                x = loc[0]
                out = f"{k['kind']}:{x['outcome']}"
                found["outcomes"].setdefault(vc, {})
                found["outcomes"][vc][out] = found["outcomes"][vc].get(out, 0) + 1
                if x["outcome"] == "SUPPORTED" and x["candidates"] != [truth_h]:
                    found["wrong_unique_or_supported"].append([k["analysis_id"], vc, x["candidates"]])
                if any(e["hypothesis"] == truth_h for e in x["eliminated"]):
                    found["true_hypothesis_removed"].append([k["analysis_id"], vc])
    return found


def mutations():
    """P4: each single mutation of a real envelope must be refused with the
    right status."""
    log = PX.EstimatorLog.from_npz(S1)
    est = PX.EstimatorProducer(log)
    t = 60.0
    base = est.step(t)[0]
    cur, _ = est.context(t)
    cs = load_contracts("px4_ekf2_estimator_status")
    xs = load_contracts(*XW.CONTRACT_FILES)
    data = json.loads((XW.CAMPAIGN / "stage1/STAGE1.json").read_text())
    f = next(iter(data["trials"].values()))["features"]["motor_0"]
    dyn = [e for e in XW.envelopes("motor_0", f, "V3_TEMPORAL", "C3") if e.producer_id == "xsys:w_dyn"][0]

    def status(e, contracts, base_profile="csia/v2/profiles/aircraft.py", t_=t, epochs=cur,
               events=None):
        a = assess([e], contracts, AnalysisContext(t_, base_profile, EpochContext(epochs), events or {}))
        return a.admissions[0].status
    cases = {
        "wrong producer version": (replace(base, producer_version="1.15.0"), cs, "CONTRACT_INVALID"),
        "wrong contract version": (replace(base, contract_version="px4-ekf2-status-0"), cs, "CONTRACT_INVALID"),
        "unknown claim": (replace(base, claim="INNOVATION_TAS"), cs, "CONTRACT_INVALID"),
        "claim on another record": (replace(base, record=replace(base.record, relation="compute.deadline_met")),
                                    cs, "CONTRACT_INVALID"),
        "attributability changed": (replace(base, record=replace(base.record, attributable=True)), cs,
                                    "CONTRACT_INVALID"),
        "lineage missing": (replace(base, lineage=None), cs, "CONTRACT_INVALID"),
        "content time NaN": (replace(base, content_time=float("nan")), cs, "CONTRACT_INVALID"),
        "content after production": (replace(base, produced_time=base.content_time - 0.01), cs,
                                     "PRODUCER_INVALID"),
        "content in the future": (replace(base, content_time=t + 1.0, produced_time=t + 1.0), cs,
                                  "PRODUCER_INVALID"),
        "stale content": (base, cs, "STALE"),        # judged at t + 1 s below
        "epoch missing": (replace(base, config_epoch={}), cs, "CONTRACT_INVALID"),
        "epoch from another lane": (replace(base, config_epoch={PX.LANE_KEY: 0}), cs,
                                    "CONFIGURATION_MISMATCH"),
        "profile mismatch": (base, cs, "PROFILE_MISMATCH"),
        "witness outside its window": (replace(dyn, content_time=15.0), xs, "REGIME_INVALID"),
    }
    out = {}
    for name, (e, contracts, want) in cases.items():
        if name == "stale content":
            got = status(e, contracts, t_=t + 1.0)
        elif name == "profile mismatch":
            got = status(e, contracts, base_profile="csia/v2/profiles/pump_skid.py")
        elif name == "witness outside its window":
            got = status(e, contracts, base_profile=XSYS_BASE, t_=15.0, events={XW.ONSET: 0.0})
        else:
            got = status(e, contracts)
        out[name] = {"expected": want, "got": got, "missed": got != want}
    return out


def faulted_producer_injection():
    """P7: VIOLATED outputs from a FAULTED (or UNAVAILABLE) producer, added
    to real XSYS ticks, must change no decision and never appear as
    adverse evidence."""
    data = json.loads((XW.CAMPAIGN / "stage1/STAGE1.json").read_text())
    key = json.loads((XW.CAMPAIGN / "stage0/KEY.json").read_text())["trials"]
    S1m, XA, _XF = XW.pipeline()
    from csia_evidence_assurance import profile_gate as PG
    from csia_semantic_core import Corrections, SemanticCore21
    core = SemanticCore21((XA.SPEC,), XA.PREDICATES, (), Corrections.revised(), trace=True)
    cs = load_contracts(*XW.CONTRACT_FILES)
    gate = PG.not_applicable("xsys001_research_spec", XSYS_BASE, "no function table")
    import copy
    rogue = {}
    for pid, c in cs.items():
        raw = copy.deepcopy(c.raw)
        raw.update(producer_id="rogue:" + pid, health_reporting="REPORTED")
        from csia_evidence_assurance.contract import ProducerContract
        rogue["rogue:" + pid] = ProducerContract.from_dict(raw)
    changed, leaked, n = [], [], 0
    for oid, t in sorted(data["trials"].items()):
        f = t["features"]["motor_0"]
        clean = FlightAssuranceAnalyzer(core, cs, gate, XSYS_BASE).step(
            15.0, XW.envelopes("motor_0", f, "V3_TEMPORAL", "C3"), events={XW.ONSET: 0.0})
        for health in (ProducerHealth.FAULTED, ProducerHealth.UNAVAILABLE):
            envs = XW.envelopes("motor_0", f, "V3_TEMPORAL", "C3")
            bad = [replace(e, producer_id="rogue:" + e.producer_id, producer_health=health,
                           record=replace(e.record, observation_state=(
                               OS.NOMINAL if e.record.observation_state is OS.VIOLATED else OS.VIOLATED)))
                   for e in envs]
            dirty = FlightAssuranceAnalyzer(core, {**cs, **rogue}, gate, XSYS_BASE).step(
                15.0, envs + bad, events={XW.ONSET: 0.0})
            n += 1
            dec = lambda r: [(x["key"], x["outcome"], x["candidates"]) for x in r.localizations]  # noqa: E731
            if dec(dirty) != dec(clean):
                changed.append([key[oid]["analysis_id"], health.value])
            if any(e.startswith("rogue:") for e in dirty.state["abnormal"]["adverse_evidence"]):
                leaked.append([key[oid]["analysis_id"], health.value])
    return {"injections": n, "decision_changed": changed, "faulted_output_as_adverse": leaked}


def campaign_checks():
    """P3 (estimator side), P5, P6, P8 from CAMPAIGN_XSYS.json and S1."""
    camp = json.loads((C.HERE / "CAMPAIGN_XSYS.json").read_text())
    out = {"lineage_mismatch": [], "estimator_rejected_after_alignment": [],
           "no_coverage_as_nominal": [], "trials": len(camp["trials"])}
    for aid, t in sorted(camp["trials"].items()):
        if t["independent_lines_2_2"] != t["independent_lines_ground_truth"]:
            out["lineage_mismatch"].append([aid, t["independent_lines_2_2"],
                                            t["independent_lines_ground_truth"],
                                            t["adverse_producers"]])
        bad = {k: v for k, v in t["rejected"].items()}
        if bad:
            out["estimator_rejected_after_alignment"].append([aid, bad])
    run = runs.estimator_log(PX.EstimatorLog.from_npz(S1), tick_s=0.1)
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts)
    for c in m["coverage"]:
        if "NO_COVERAGE" in c["ticks_by_state"] and len(c["ticks_by_state"]) > 1:
            out["no_coverage_as_nominal"].append(c)
    cu = runs.cusum_scenario("imu0_bias_drift")
    mc = R.machine_report(cu.results, cu.inputs, cu.gate, cu.contracts)
    for c in mc["coverage"]:
        if c["record"].startswith(("source.imu0", "SENSOR/source.imu0")) and \
                set(c["ticks_by_state"]) != {"NO_COVERAGE"}:
            out["no_coverage_as_nominal"].append(c)
    # P8: every real reset reported once, nothing refused for a reset
    log = PX.EstimatorLog.from_npz(S1)
    d = log.status[0]
    real = {f: int(np.sum((np.diff(d[f].astype(int)) % 256) > 0)) for f in PX.RESET_NAMES}
    reported = {f: sum(1 for c in m["key_moments"]["configuration_changes"]
                       if c["key"] == f"ekf2.reset.{f}") for f in PX.RESET_NAMES}
    out["resets"] = {"real_increments_in_log": real, "reported_changes": reported,
                     "refused_outputs_after_alignment": sum(
                         1 for r in run.results for x in r.evidence["rejected"]
                         if x["status"] != "PRODUCER_INVALID")}
    # P9: ordering and content time
    times = [iv["from"] for iv in m["timeline"]]
    km = m["key_moments"]
    seq = [c["t"] for c in km["configuration_changes"]]
    out["timeline_monotonic"] = times == sorted(times) and seq == sorted(seq)
    late = 0
    for r in run.results:
        for e in r.evidence["used"]:
            ct = float(e.rsplit("|", 1)[1])
            late += ct > r.event_time + 1e-9
    out["admitted_with_content_after_tick"] = late
    return out


def main():
    res = {"label": "NON-CONFIRMATORY; adversarial search on real pilot data"}
    res["P1_P2_P3w_P9_xsys"] = xsys_slots()
    res["P4_mutations"] = mutations()
    res["P7_faulted_producer"] = faulted_producer_injection()
    res["P3e_P5_P6_P8_P9_campaign"] = campaign_checks()
    x, mu, fp, cp = (res["P1_P2_P3w_P9_xsys"], res["P4_mutations"], res["P7_faulted_producer"],
                     res["P3e_P5_P6_P8_P9_campaign"])
    res["summary"] = {
        "wrong_unique_or_supported": len(x["wrong_unique_or_supported"]),
        "true_hypothesis_removed": len(x["true_hypothesis_removed"]),
        "valid_witness_rejected": len(x["valid_witness_rejected"]),
        "invalid_evidence_admitted": sum(v["missed"] for v in mu.values()),
        "faulted_producer_changed_decision": len(fp["decision_changed"]),
        "faulted_output_as_adverse": len(fp["faulted_output_as_adverse"]),
        "lineage_mismatch_vs_ground_truth": len(cp["lineage_mismatch"]),
        "estimator_rejected_in_trials": len(cp["estimator_rejected_after_alignment"]),
        "no_coverage_as_nominal": len(cp["no_coverage_as_nominal"]),
        "reset_reporting_matches_log": cp["resets"]["real_increments_in_log"] == cp["resets"]["reported_changes"],
        "timeline_monotonic": cp["timeline_monotonic"],
        "admitted_with_content_after_tick": cp["admitted_with_content_after_tick"],
    }
    C.write_json(OUT, res)
    print(json.dumps(res["summary"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
