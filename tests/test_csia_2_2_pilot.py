"""CSIA 2.2 offboard pilot: the Analyzer MVP and the real-data pins.

research/csia_2_2_offboard_pilot/ has the design and the evidence. These
tests pin:
- run S1 (the first real EKF2-selector log), from its committed extract;
- the coverage states, including silent detectors and no coverage;
- the evidence basis and the evidence that would discriminate;
- the key moments;
- the manifest;
- the one-command and batch workflows;
- report determinism.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from csia_evidence_assurance import report as R
from csia_evidence_assurance import runs
from csia_evidence_assurance.adapters import cusum as CU
from csia_evidence_assurance.adapters import px4_estimator as PX
from csia_evidence_assurance.contract import ContractError, ProducerContract, load_contracts

REPO = Path(__file__).resolve().parents[1]
PILOT = REPO / "research/csia_2_2_offboard_pilot"
S1 = PILOT / "data/S1_estimator_extract.npz"


@pytest.fixture(scope="module")
def s1_run():
    return runs.estimator_log(PX.EstimatorLog.from_npz(S1), tick_s=0.1)


@pytest.fixture(scope="module")
def s1_report(s1_run):
    return R.machine_report(s1_run.results, s1_run.inputs, s1_run.gate, s1_run.contracts)


# ------------------------------------------------------------------ run S1
def test_s1_is_a_real_selector_log_with_one_lane(s1_run):
    log = PX.EstimatorLog.from_npz(S1)
    assert log.multi_mode() and log.selector is not None
    assert set(np.unique(log.selector["instance_changed_count"])) == {1}
    assert set(np.unique(log.selector["primary_instance"])) == {0}
    assert sorted(log.status) == [0]
    assert log.origin["sha256"] == json.loads((PILOT / "S1_RESULTS.json").read_text())["run"]["ulog_sha256"]


def test_s1_selector_mode_stamps_and_no_mismatch(s1_run):
    assert s1_run.inputs["selector"] == "SELECTOR"
    statuses = {x["status"] for r in s1_run.results for x in r.evidence["rejected"]}
    assert statuses == {"PRODUCER_INVALID"}            # before alignment only
    assert all(e.config_epoch == {PX.LANE_KEY: 1} for e in s1_run.analyzer.store.values())


def test_s1_magnetometer_loss_is_a_named_configuration_change(s1_report):
    ch = [c for c in s1_report["key_moments"]["configuration_changes"]
          if c["key"] == "ekf2.aiding.hdg" and c["t"] >= 75.0]
    assert len(ch) == 1 and ch[0]["t"] == pytest.approx(75.5)
    assert "3-axis magnetometer -> none" in ch[0]["event"]
    hdg = [c for c in s1_report["coverage"] if c["claim"] == "INNOVATION_HDG"][0]
    assert hdg["ticks_by_state"]["NOT_APPLICABLE"] >= 250


def test_wa2_every_real_reset_is_reported_even_before_the_first_selection(s1_report):
    """Pilot finding WA-2: EKF2 reset at 0.428 s, before the selector's first
    message (0.516 s). The resets must still appear as configuration
    changes; no evidence is emitted before a lane is primary."""
    log = PX.EstimatorLog.from_npz(S1)
    d = log.status[0]
    for f in PX.RESET_NAMES:
        real = int(np.sum((np.diff(d[f].astype(int)) % 256) > 0))
        reported = sum(1 for c in s1_report["key_moments"]["configuration_changes"]
                       if c["key"] == f"ekf2.reset.{f}")
        assert reported == real, f
    est = PX.EstimatorProducer(log)
    first_sel_s = (int(log.selector["timestamp"][0]) - log.t0_us) * 1e-6
    assert est.step(first_sel_s - 0.01) == []


# ------------------------------------------------------------------ coverage states
def test_a_silent_detector_is_no_anomaly_and_an_unseen_source_is_no_coverage():
    run = runs.cusum_scenario("imu0_bias_drift")
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts)
    by = {(c["producer_id"], c["record"]): c["ticks_by_state"] for c in m["coverage"]}
    for node in ("imu0", "imu1", "baro"):
        assert by[(CU.PRODUCER_ID, f"source.{node}")] == {"NO_COVERAGE": 1500}
    # the faulted IMU is never reported as observed nominal by the CUSUM
    assert not any(k[1].startswith("SENSOR/source.imu0") for k in by)
    assert by[(CU.PRODUCER_ID, "SENSOR/source.battery:cusum.sustained_shift")] == {"NO_ANOMALY": 1500}
    assert by[(CU.PRODUCER_ID, "SENSOR/source.gps:cusum.sustained_shift")] == \
        {"NO_ANOMALY": 1424, "UNAVAILABLE": 76}
    assert not any("NOMINAL" in v for v in by.values())


def test_wa3_a_verdict_names_the_profile_records_nothing_observed(s1_report):
    """A PX4 log alone: the estimator's claims are outside the profile, so no
    profile record is observed and "no symptom" must say so."""
    pc = s1_report["profile_coverage"]
    assert pc["enumerable"] and pc["profile_records"] == 68
    assert pc["observed"] == [] and pc["never_admitted"] == []
    assert len(pc["no_output"]) == 68 and "ACTUATION/motor_0:actuation.mechanical_response" in pc["no_output"]
    assert pc["outside_profile"] == [f"COMPUTE/state_estimator:estimator.innovation.{k}"
                                     for k in ("hdg", "hgt", "pos", "vel")]
    txt = R.human_report(s1_report)
    assert "scope: the run observed 0 of the profile's 68 records" in txt
    assert "NO PRODUCER in this run: 68: ACTUATION/motor_0 (3)" in txt
    # a run that observes every record carries no scope line
    v2 = runs.v2_scenario("NOMINAL")
    m = R.machine_report(v2.results, v2.inputs, v2.gate, v2.contracts)
    assert len(m["profile_coverage"]["observed"]) == m["profile_coverage"]["profile_records"] == 68
    assert "scope:" not in R.human_report(m)
    # a profile with no record list is reported as not enumerable
    cu = runs.cusum_scenario("imu0_bias_drift")
    mc = R.machine_report(cu.results, cu.inputs, cu.gate, cu.contracts)
    pc = mc["profile_coverage"]
    assert "SENSOR/source.imu0:v1_1.source_health" in pc["no_output"] and pc["observed"] == []
    assert pc["outside_profile"] == [f"SENSOR/source.{n}:cusum.sustained_shift" for n in
                                     ("battery", "gps", "mag", "motor_esc", "vibration")]


def test_estimator_checks_report_nominal_and_unavailable(s1_report):
    pos = [c for c in s1_report["coverage"] if c["claim"] == "INNOVATION_POS"][0]["ticks_by_state"]
    assert set(pos) == {"NOMINAL", "UNAVAILABLE"}


def test_nominal_means_is_validated_and_defaults_to_nominal():
    c = ProducerContract.load("px4_ekf2_estimator_status")
    assert {s.nominal_means for s in c.claims.values()} == {"NOMINAL"}
    assert load_contracts("cusum_v1_1_sequential")[CU.PRODUCER_ID].claims[CU.CLAIM].nominal_means \
        == "NO_ANOMALY"
    raw = dict(ProducerContract.load("cusum_v1_1_sequential").raw)
    raw["claims"] = {"SUSTAINED_SHIFT": dict(raw["claims"]["SUSTAINED_SHIFT"], nominal_means="FINE")}
    with pytest.raises(ContractError):
        ProducerContract.from_dict(raw)


# ------------------------------------------------------------------ explanation
def test_ambiguity_names_the_evidence_that_would_discriminate():
    run = runs.xsys_trial("XS1A1-C00-A-E055", "V4_INVALID_WINDOW")
    loc = [x for x in run.results[-1].localizations if x["subject"] == "motor_0"][0]
    assert loc["outcome"] == "AMBIGUOUS"
    assert [d["predicate"] for d in loc["would_discriminate"]] == ["CTRL_T3_NOMINAL", "DYN_T1_NOMINAL"]


def test_a_diagnosis_shows_what_its_evidence_rests_on():
    run = runs.xsys_trial("XS1A1-C00-A-E055", "V3_TEMPORAL")
    loc = [x for x in run.results[-1].localizations if x["subject"] == "motor_0"][0]
    assert loc["outcome"] == "SUPPORTED" and loc["would_discriminate"] == []
    basis = loc["evidence_basis"]
    rpm = [v for k, v in basis.items() if k.startswith("xsys:w_rpm")][0]
    dyn = [v for k, v in basis.items() if k.startswith("xsys:w_dyn")][0]
    assert "channel:esc_rpm.motor_0" in rpm            # telemetry
    assert "sensor:imu.1310988" in dyn                 # physical


def test_key_moments_answer_when():
    run = runs.xsys_trial("XS1A1-C00-A-E055", "V3_TEMPORAL")
    k = R.machine_report(run.results, run.inputs, run.gate, run.contracts)["key_moments"]
    assert k["first_abnormal"]["t"] == pytest.approx(0.2)
    assert k["first_abnormal"]["observed_by"] == ["xsys:w_dyn", "xsys:w_rpm"]
    assert {"t": 0.2, "became_certain": "COMMAND_NO_RESPONSE|motor_0 SUPPORTED ACTUATION/mechanical"} \
        in k["certainty"]
    v4 = runs.xsys_trial("XS1A1-C00-A-E055", "V4_INVALID_WINDOW")
    k4 = R.machine_report(v4.results, v4.inputs, v4.gate, v4.contracts)["key_moments"]
    assert k4["certainty"] == []
    assert {e["status"] for e in k4["evidence_invalidated"]} == {"REGIME_INVALID"}


def test_wa1_one_imu_chip_is_one_root():
    """Pilot finding WA-1: gyro and accelerometer of one IMU device were two
    roots, so a gyro monitor and an accelerometer monitor of the same chip
    counted as independent lines."""
    from csia_evidence_assurance.lineage import independent_lines
    est = PX.EstimatorProducer(PX.EstimatorLog.from_npz(S1))
    env = est.step(60.0)[0]
    imu = [r for r in env.lineage.roots if r.startswith("sensor:imu.")]
    assert imu == ["sensor:imu.1310988"]
    assert not any(r.startswith(("sensor:gyro.", "sensor:accel.")) for r in env.lineage.roots)
    from csia_evidence_assurance.adapters import xsys_witness as XW
    assert XW.lineage("dyn", "motor_0").overlaps(env.lineage)
    assert independent_lines([("dyn", XW.lineage("dyn", "motor_0")), ("est", env.lineage)]) == (1, True)


# ------------------------------------------------------------------ manifest and workflow
def test_manifest_is_reproducible_and_path_free(s1_run, s1_report):
    body = R.dumps(s1_report)
    man = R.manifest(s1_report, body, {"tick_s": 0.1})
    assert man["report_sha256"] == hashlib.sha256(body).hexdigest()
    assert man["semantic_version"] == "2.1.1" and man["analyzer_version"] == "2.2.1"
    assert man["profile"]["digest"] and man["profile"]["gate"] == "ACCEPTED"
    assert set(man["code"]) == {"csia_evidence_assurance", "csia_semantic_core"}
    assert man["producers"]["px4:ekf2.estimator_status"]["digest"]
    text = json.dumps(man)
    assert "/home/" not in text and "/tmp/" not in text
    assert R.dumps(man) == R.dumps(R.manifest(s1_report, body, {"tick_s": 0.1}))


def test_analyze_and_analyze_many_commands(tmp_path):
    py = [sys.executable, "-m", "csia_evidence_assurance"]
    p = subprocess.run(py + ["analyze", "PROCESS_STALL", "--out", str(tmp_path / "one")],
                       cwd=REPO, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert {f.name for f in (tmp_path / "one").iterdir()} == {"report.json", "report.txt",
                                                              "manifest.json"}
    lst = tmp_path / "inputs.txt"
    lst.write_text("NOMINAL\nPROCESS_STALL\nnot_an_input\n")
    p = subprocess.run(py + ["analyze-many", str(lst), "--out", str(tmp_path / "many")],
                       cwd=REPO, capture_output=True, text=True)
    assert p.returncode == 1                           # one input failed; the batch completed
    idx = json.loads((tmp_path / "many/batch_index.json").read_text())
    assert [r["input"] for r in idx["inputs"]] == ["NOMINAL", "PROCESS_STALL"]
    assert list(idx["failed"]) == ["not_an_input"]
    for f in ("batch_summary.txt", "coverage_matrix.json", "coverage_matrix.txt", "batch_metrics.json"):
        assert (tmp_path / "many" / f).exists()
    one = (tmp_path / "one/report.json").read_bytes()
    assert one == (tmp_path / "many/PROCESS_STALL/report.json").read_bytes()


def test_report_bytes_do_not_depend_on_process_or_directory(tmp_path):
    code = ("import sys;from csia_evidence_assurance import runs, report as R;"
            "r=runs.resolve(sys.argv[1]);"
            "sys.stdout.buffer.write(R.dumps(R.machine_report(r.results,r.inputs,r.gate,r.contracts)))")
    outs = []
    for seed, cwd in (("0", REPO), ("12345", tmp_path)):
        p = subprocess.run([sys.executable, "-c", code, str(S1)], cwd=cwd, capture_output=True,
                           env={"PYTHONHASHSEED": seed, "PYTHONPATH": str(REPO),
                                "PATH": "/usr/bin:/bin"})
        assert p.returncode == 0, p.stderr.decode()[-500:]
        outs.append(p.stdout)
    assert outs[0] == outs[1]


# ------------------------------------------------------------------ pinned reports (Phase 20)
PINNED = {
    "U4_s1_selector": "80035ab1256b72887ad5593f6eb99729c6ecd541ea607f091844baf201562566",
    "U5_cusum_power_sag": "92d88ae17f149cfdc385831c05abd215e2dff83cdf260e67ebce4a14176d825e",
    "U6_cusum_imu0_drift": "c8ca0bf203ec400885e5b8c1cb524257aae492bc1fda01e1e69abe5ca0a30927",
    "U8_predicate_fault": "9c86f295ce89b79ae602069692e28220cea8a072651fd97e653b0e5629ee780b",
}


@pytest.mark.parametrize("case", sorted(PINNED))
def test_pinned_reports_regenerate_byte_for_byte(case):
    """The reports needing no raw data: regenerated now, against the pinned
    hash and the committed file. U7 (E1) is pinned through the 2.2 replay."""
    if case == "U4_s1_selector":
        run = runs.estimator_log(PX.EstimatorLog.from_npz(S1), tick_s=0.1)
    elif case == "U8_predicate_fault":
        sys.path.insert(0, str(REPO / "research/csia_2_2_evidence_assurance"))
        import datasets_2_2 as D
        run, _extra = D.predicate_fault_run()
    else:
        run = runs.cusum_scenario({"U5_cusum_power_sag": "power_sag",
                                   "U6_cusum_imu0_drift": "imu0_bias_drift"}[case])
    body = R.dumps(R.machine_report(run.results, run.inputs, run.gate, run.contracts))
    assert hashlib.sha256(body).hexdigest() == PINNED[case]
    assert (PILOT / "reports" / case / "report.json").read_bytes() == body
    hashes = json.loads((PILOT / "REPORT_HASHES.json").read_text())
    assert hashes[case] == PINNED[case]
