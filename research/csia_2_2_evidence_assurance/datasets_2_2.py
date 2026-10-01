#!/usr/bin/env python3
"""Phase 27: the Flight Assurance Analyzer on datasets A-H. NON-CONFIRMATORY.
RESEARCH ONLY.

    .venv/bin/python research/csia_2_2_evidence_assurance/datasets_2_2.py [--skip-ulog]

Each dataset was chosen by a rule fixed before it was run (DATASETS.md):

| id | what | source |
|---|---|---|
| A | nominal | v2 scenario NOMINAL |
| B | a correct UNIQUE | v2 scenario PROCESS_STALL |
| C | a genuine AMBIGUOUS | v2 scenario MS_B4_MECHANICAL (ground truth: the matched pair's cause is not separable) |
| D | the MS_B5 wrong-UNIQUE case | v2 scenario MS_B5_RESPONSE_SENSOR |
| E | E1, the configuration transition | the shadow study's frozen design (`e1_2_2.py`) |
| F | a predicate fault | MS_A1_SENSOR_DELAY; the first base predicate (sorted) whose fault 2.1.1 reports as material |
| G | correlated three-monitor | NOMINAL plus synthetic monitors of IMU1: threshold, CUSUM and EKF residual, a relay of the threshold, a stale monitor, a faulted monitor, and a monitor of IMU2 |
| H | XSYS-001-derived | the C00 E055 matched pair (A and B trials), V3_TEMPORAL with the PX4 estimator from the trial's flight log; and the A trial under V4_INVALID_WINDOW |

Also run:
- the frozen CUSUM on v1 scenarios power_sag (correlated alarms) and
  imu0_bias_drift (outside CUSUM coverage);
- the estimator over the whole E055 flight.

For every dataset: `datasets/<id>/report.json` (byte-stable) and
`report.txt`. The summary is in DATASETS_2_2.json. Reports are written only
if they changed, so re-running leaves the tree clean.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import common_2_2 as C

import e1_2_2  # noqa: E402
import ground_truth as GT  # noqa: E402
import predicate_fault_study as F  # noqa: E402

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState as OS  # noqa: E402
from csia_evidence_assurance import report as R  # noqa: E402
from csia_evidence_assurance import runs  # noqa: E402
from csia_evidence_assurance.contract import ProducerContract  # noqa: E402
from csia_evidence_assurance.envelope import EvidenceEnvelope  # noqa: E402
from csia_evidence_assurance.health import ProducerHealth  # noqa: E402
from csia_evidence_assurance.lineage import Lineage  # noqa: E402

OUT_DIR = C.HERE / "datasets"
SUMMARY = C.HERE / "DATASETS_2_2.json"
RAW = Path("/home/user/xsys_001_confirmatory_raw_artifacts/flights")
H_PAIR = ("XS1A1-C00-A-E055", "XS1A1-C00-B-E055")


def write(name, run, extra=None):
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts)
    d = OUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    for fname, body in (("report.json", R.dumps(m)),
                        ("report.txt", R.human_report(m).encode())):
        p = d / fname
        if not p.exists() or p.read_bytes() != body:
            p.write_bytes(body)
    f = m["final"]
    s = {"ticks": m["ticks"], "intervals": m["intervals"],
         "final_headline": f["state"]["headline"] if f else None,
         "final_localizations": ([[x["key"], x["outcome"], x["candidates"]]
                                  for x in f["localizations"]] if f else None),
         "final_attribution": f["attribution"].get("verdict") if f else None,
         "final_candidates": f["attribution"].get("candidates") if f else None,
         "rejected_over_run": _rejected(run.results),
         "report_sha256": C.sha(d / "report.json")}
    s.update(extra or {})
    return s


def _rejected(results) -> dict:
    out: dict = {}
    for r in results:
        for x in r.evidence["rejected"]:
            k = f"{x['status']}:{re.sub(r'_?[0-9.]+s', '', x['reasons'][0].split(':')[0])}"
            out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ F
def predicate_fault_run():
    base_run = runs.v2_scenario("MS_A1_SENSOR_DELAY")
    an = base_run.analyzer
    clean = an.last_tick
    chosen = None
    for base in F.base_ids(an.core.predicates):
        fc = F.faulted_core(an.core, base)
        tr = fc.reason(_last_records("MS_A1_SENSOR_DELAY"))
        if any(x.fault_impact and any(e["dependency"] == "MATERIAL" for e in x.fault_impact)
               for x in tr.localizations):
            chosen = base
            break
    run = runs.v2_scenario("MS_A1_SENSOR_DELAY")
    fc = F.faulted_core(run.analyzer.core, chosen)
    from csia_evidence_assurance.analyzer import FlightAssuranceAnalyzer
    from csia_evidence_assurance.adapters import v2_domains as V2
    from csia_semantic_core.profile_overlay import load_successor
    ov = load_successor("aircraft_successor_r2")
    an2 = FlightAssuranceAnalyzer(fc, run.contracts, run.gate, V2.AIRCRAFT_BASE)
    out = []
    for t, recs in _all_records("MS_A1_SENSOR_DELAY"):
        recs = ov.apply(recs)
        out.append(an2.step(t, V2.envelopes(recs, t, run.contracts)))
    run.results = out
    run.inputs = dict(run.inputs, injected_predicate_fault=chosen,
                      selection_rule="first base predicate (sorted) whose fault 2.1.1 "
                                     "reports as MATERIAL on the last tick")
    clean_outcomes = sorted((x.key, x.outcome) for x in clean.localizations)
    return run, {"injected_predicate": chosen, "clean_outcomes": clean_outcomes}


def _all_records(name):
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import SCENARIOS, build_engine_for
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed
    sc = SCENARIOS[name]
    engine = build_engine_for(sc)
    res = SC.run(engine, sc, ticks=runs.V2_TICKS,
                 payload_for=example_payload_feed(getattr(sc, "v1_1_variant", "clean")))
    return [(float(sa.t), sa.records) for sa in res]


def _last_records(name):
    from csia_semantic_core.profile_overlay import load_successor
    return load_successor("aircraft_successor_r2").apply(_all_records(name)[-1][1])


# ------------------------------------------------------------------ G
G_MONITORS = {
    # producer: (lineage roots, health, component)
    "imu1:threshold": (("sensor:imu1",), ProducerHealth.VALID, "source.imu1"),
    "imu1:cusum": (("sensor:imu1", "model:cusum_imu1"), ProducerHealth.VALID, "source.imu1"),
    "imu1:ekf_residual": (("sensor:imu1", "model:ekf2"), ProducerHealth.VALID, "source.imu1"),
    "relay:imu1_threshold": (("sensor:imu1",), ProducerHealth.VALID, "source.imu1"),
    "imu1:slow_monitor": (("sensor:imu1", "model:slow"), ProducerHealth.VALID, "source.imu1"),
    "imu1:faulted_monitor": (("sensor:imu1", "model:faulted"), ProducerHealth.FAULTED,
                             "source.imu1"),
    "imu2:threshold": (("sensor:imu2",), ProducerHealth.VALID, "source.imu2"),
}
#: The slow monitor stops publishing here; its last output is held and goes stale.
G_SLOW_STOPS_AT = 1.0


def g_contract(pid):
    return ProducerContract.from_dict({
        "schema": "csia.evidence_contract/1", "producer_id": pid, "producer_version": "1",
        "contract_version": "g-1",
        "claims": {"IMU_ALARM": {"meaning": "synthetic IMU alarm (dataset G)", "domain": "SENSOR",
                                 "relation": "dataset_g.imu_alarm", "attributable": False}},
        "lineage": "PER_OUTPUT", "update": {"mode": "SAMPLE_AND_HOLD", "period_s": 0.05},
        "validity": {"max_content_age_s": 0.5}, "health_reporting": "REPORTED",
        "profile_compatibility": ["csia/v2/profiles/aircraft.py"]})


def correlated_run():
    run = runs.v2_scenario("NOMINAL")
    from csia_evidence_assurance.analyzer import FlightAssuranceAnalyzer
    from csia_evidence_assurance.adapters import v2_domains as V2
    from csia_semantic_core.profile_overlay import load_successor
    ov = load_successor("aircraft_successor_r2")
    cs = dict(run.contracts)
    cs.update({p: g_contract(p) for p in G_MONITORS})
    an = FlightAssuranceAnalyzer(run.analyzer.core, cs, run.gate, V2.AIRCRAFT_BASE)
    out = []
    for t, recs in _all_records("NOMINAL"):
        envs = V2.envelopes(ov.apply(recs), t, run.contracts)
        alarm = t >= 1.0
        for pid, (roots, health, comp) in G_MONITORS.items():
            src = pid if not pid.startswith("relay:") else "imu1:threshold"
            rec = EvidenceRecord(domain="SENSOR", component=comp, relation="dataset_g.imu_alarm",
                                 source=src,
                                 observation_state=(OS.DEGRADED if alarm and comp == "source.imu1"
                                                    else OS.NOMINAL),
                                 applicability=Applicability.APPLICABLE, attributable=False)
            if pid == "imu1:slow_monitor" and t >= G_SLOW_STOPS_AT:
                continue
            envs.append(EvidenceEnvelope(pid, "1", "g-1", "IMU_ALARM", rec, Lineage.of(*roots),
                                         round(t, 6), health, produced_time=round(t, 6)))
        out.append(an.step(t, envs))
    run.results = out
    run.contracts = cs
    run.inputs = dict(run.inputs, kind="dataset_g_correlated_monitors",
                      monitors=sorted(G_MONITORS))
    last = out[-1]
    imu1 = [c for c in last.corroboration["by_component"] if c["component"] == "SENSOR/source.imu1"]
    return run, {"imu1_adverse_outputs": len(imu1[0]["adverse_evidence"]) if imu1 else 0,
                 "imu1_independent_lines": imu1[0]["independent_lines"] if imu1 else 0,
                 "imu1_producers": imu1[0]["producers"] if imu1 else []}


# ------------------------------------------------------------------ H
def gyro_ids():
    """sensor_selection.gyro_device_id in every campaign flight log."""
    from pyulog import ULog
    ids = {}
    for p in sorted(RAW.glob("*.ulg")):
        u = ULog(str(p), ["sensor_selection"])
        d = u.get_dataset("sensor_selection").data
        ids[p.stem] = sorted({int(x) for x in d["gyro_device_id"]})
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ulog", action="store_true",
                    help="skip everything that needs the raw XSYS-001 flight logs")
    a = ap.parse_args()
    summary = {"label": "NON-CONFIRMATORY; datasets chosen by the rules in DATASETS.md"}
    for did, name in (("A_nominal", "NOMINAL"), ("B_correct_unique", "PROCESS_STALL"),
                      ("C_genuine_ambiguous", "MS_B4_MECHANICAL"),
                      ("D_ms_b5", "MS_B5_RESPONSE_SENSOR")):
        t = GT.truth(name)
        summary[did] = write(did, runs.v2_scenario(name),
                             {"scenario": name, "ground_truth_domain": t.get("domain"),
                              "ground_truth_hypotheses": t.get("hypotheses", {})})
        print(did, summary[did]["final_attribution"], summary[did]["final_candidates"])
    coll = []
    e1 = e1_2_2.run(collect=coll)["result"]
    gate, contracts = coll[0]
    summary["E_e1"] = write("E_e1", runs.Run(coll[1:], {"kind": "e1_transition",
                                                         "design_sha256": e1_2_2.T.FROZEN_SHA256},
                                             gate, contracts),
                            {k: e1[k] for k in ("stale_position_symptom_ticks",
                                                "config_mismatch_ticks", "recovery_tick")})
    run, extra = predicate_fault_run()
    summary["F_predicate_fault"] = write("F_predicate_fault", run, extra)
    run, extra = correlated_run()
    summary["G_correlated_monitors"] = write("G_correlated_monitors", run, extra)
    for name in ("power_sag", "imu0_bias_drift"):
        summary[f"S_cusum_{name}"] = write(f"S_cusum_{name}", runs.cusum_scenario(name))
    if not a.skip_ulog and RAW.exists():
        ids = gyro_ids()
        summary["H_gyro_device_ids"] = {"flights": len(ids),
                                        "distinct": sorted({i for v in ids.values() for i in v}),
                                        "xsys_witness_constant": runs.XW.XSYS_GYRO_DEVICE_ID}
        key = runs.xsys_key()["trials"]
        for aid in H_PAIR:
            k = next(v for v in key.values() if v["analysis_id"] == aid)
            log = RAW / f"{k['source_flight_id']}.ulg"
            summary[f"H_{aid}"] = write(f"H_{aid}", runs.xsys_trial(aid, "V3_TEMPORAL", log),
                                        {"truth": k["truth"], "flight": log.name})
        k = next(v for v in key.values() if v["analysis_id"] == H_PAIR[0])
        summary[f"H_{H_PAIR[0]}_V4"] = write(
            f"H_{H_PAIR[0]}_V4", runs.xsys_trial(H_PAIR[0], "V4_INVALID_WINDOW",
                                                 RAW / f"{k['source_flight_id']}.ulg"),
            {"truth": k["truth"]})
        summary["H_full_flight_estimator"] = write(
            "H_full_flight_estimator", runs.ulog(RAW / f"{k['source_flight_id']}.ulg"))
    C.write_json(SUMMARY, summary)
    print(json.dumps({k: (v.get("final_headline") if isinstance(v, dict) else v)
                      for k, v in summary.items()}, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
