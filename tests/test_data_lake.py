"""ACEG slice 2: data foundation, contracts, validity monitor.

Highest-value regressions prevented here:
  * missingness silently becoming zero
  * a group leaking across protected partitions
  * the embedded runtime acquiring a data-lake dependency
  * the fail-closed validity monitor authorizing an out-of-domain guarantee
"""

import json
import os

import pytest
import yaml

from csia.contracts import validate_contract
from csia.data import (CROSS_DATASET_PARTITIONS, NormalizedStore,
                       PX4UlogAdapter, RawStore, assign_partition,
                       check_group_leakage, flight_quality, survey_ulog,
                       write_fixture)
from csia.evidence.validity_monitor import (Validity, ValidityConfig,
                                            ValidityMonitor)

ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.fixture(scope="module")
def fixture_ulog(tmp_path_factory):
    p = str(tmp_path_factory.mktemp("ulog") / "fix.ulg")
    return write_fixture(p, n_imu=500, inject_gap_at=200)


@pytest.fixture(scope="module")
def records(fixture_ulog):
    return PX4UlogAdapter().normalize(fixture_ulog, "csia_fixture",
                                      "ac0", "f0")


# --- registry / acquisition ---------------------------------------------------

def test_registry_separates_published_from_verified():
    with open(os.path.join(ROOT, "datasets", "registry",
                           "public_datasets_v1.yaml")) as fh:
        reg = yaml.safe_load(fh)
    assert len(reg["datasets"]) == 7
    for name, d in reg["datasets"].items():
        assert "published_specification" in d, name
        assert d["locally_verified"]["present"] is False, \
            f"{name} claims local presence without acquisition"
        assert d["acquisition"]["status"] == "BLOCKED_NETWORK_POLICY"


def test_acquisition_status_records_failures_not_success():
    p = os.path.join(ROOT, "datasets", "reports",
                     "acquisition_status_v1.json")
    with open(p) as fh:
        st = json.load(fh)
    assert all(d["status"] in ("ALL_ATTEMPTS_FAILED", "LICENSE_ACK_REQUIRED")
               for d in st["datasets"].values())
    px4 = st["datasets"]["px4_flightreview_v1"]
    assert len(px4["attempts"]) == 26          # every UUID actually probed
    assert all(a["status"] != "DOWNLOADED" for a in px4["attempts"])


# --- immutable raw store ------------------------------------------------------

def test_raw_store_is_content_addressed_and_immutable(tmp_path, fixture_ulog):
    store = RawStore(str(tmp_path))
    a = store.ingest(fixture_ulog, "d")
    b = store.ingest(fixture_ulog, "d")
    assert a["sha256"] == b["sha256"]
    assert b["status"] == "ALREADY_PRESENT"
    import stat
    mode = stat.S_IMODE(os.stat(a["path"]).st_mode)
    assert not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH), \
        f"raw file is writable (mode {oct(mode)}); os.access is unusable " \
        "under root, so mode bits are asserted directly"


# --- PX4 ingestion ------------------------------------------------------------

def test_multi_instance_topics_preserved(records):
    imu = [r for r in records if r.topic == "vehicle_imu"]
    est = [r for r in records if r.topic == "estimator_status"]
    assert sorted(r.sensor_instance for r in imu) == [0, 1]
    assert sorted(r.sensor_instance for r in est) == [0, 1]


def test_device_ids_preserved(records):
    devs = {r.sensor_instance: r.device_id
            for r in records if r.topic == "vehicle_imu"}
    assert devs[0] != devs[1] and all(d is not None for d in devs.values())


def test_missing_field_is_null_never_zero(records):
    """The fixture's estimator_status lacks innovation_check_flags; it must
    surface as None-filled, never zero-filled."""
    est = next(r for r in records if r.topic == "estimator_status")
    col = est.columns["innovation_check_flags"]
    assert all(v is None for v in col)
    assert not any(v == 0 for v in col)


def test_absent_topic_reported_absent(tmp_path):
    from pyulog import ULog
    p = write_fixture(str(tmp_path / "nopower.ulg"), drop_system_power=True)
    av = survey_ulog(ULog(p))
    assert "system_power" in av.absent
    assert "vehicle_imu" in av.present


def test_quality_report_finds_injected_gap(records):
    q = flight_quality(records)
    imu = q["topics"]["vehicle_imu#0"]
    assert imu["max_gap_us"] > 90_000          # 25-sample gap at 250 Hz
    assert imu["timestamp_regressions"] == 0


def test_parquet_roundtrip_preserves_nulls(tmp_path, records):
    import polars as pl
    store = NormalizedStore(str(tmp_path))
    est = next(r for r in records if r.topic == "estimator_status")
    out = store.write(est, raw_sha256="ab" * 32)
    df = pl.read_parquet(out)
    assert df["innovation_check_flags"].null_count() == len(df)
    assert df["innovation_check_flags__missing"].all()
    man = json.load(open(os.path.join(os.path.dirname(out),
                                      "manifest.json")))
    assert man["raw_sha256"] == "ab" * 32
    assert man["software_commit"]


# --- partitions ---------------------------------------------------------------

def test_partition_assignment_deterministic_and_group_stable():
    a = assign_partition("aircraft_X")
    assert a == assign_partition("aircraft_X")
    assert a in CROSS_DATASET_PARTITIONS
    parts = {assign_partition(f"ac{i}") for i in range(200)}
    assert {"DEVELOPMENT", "CALIBRATION", "VALIDATION",
            "BLIND_TEST"} <= parts


def test_group_leakage_detected():
    leaks = check_group_leakage({
        "f1": ("acA", "DEVELOPMENT"), "f2": ("acA", "BLIND_TEST"),
        "f3": ("acB", "VALIDATION"), "f4": ("acB", "VALIDATION")})
    assert len(leaks) == 1 and leaks[0]["group"] == "acA"


# --- Trust Contract -----------------------------------------------------------

def contract():
    with open(os.path.join(ROOT, "specifications",
                           "csia_trust_contract_v0.1.yaml")) as fh:
        return yaml.safe_load(fh)


def test_reference_contract_verdict_is_incomplete_for_a_real_gap():
    r = validate_contract(contract())
    assert r["verdict"] == "CSIA_CONTRACT_INCOMPLETE"
    assert any("timing" in g for g in r["gaps"])


def test_contract_completing_the_gap_becomes_valid():
    doc = contract()
    doc["functions"][2]["uncertainty"] = {"semantics": "bound", "value": 1e-6}
    doc["functions"][2]["missing_data_semantics"] = "omitted"
    assert validate_contract(doc)["verdict"] == "CSIA_CONTRACT_VALID"


def test_contract_schema_violation_is_invalid():
    doc = contract()
    del doc["identity"]["device_id"]
    assert validate_contract(doc)["verdict"] == "CSIA_CONTRACT_INVALID"


def test_contract_active_action_must_be_prohibited():
    doc = contract()
    doc["authorization"]["active_action_prohibited"] = False
    assert validate_contract(doc)["verdict"] == "CSIA_CONTRACT_INVALID"


# --- validity monitor (fail-closed) -------------------------------------------

def test_monitor_supported_on_iid_null():
    import random
    random.seed(3)
    m = ValidityMonitor(calibration_var=1.0)
    for _ in range(400):
        m.update(random.gauss(0, 1))
    assert m.state() is Validity.SUPPORTED
    auth = m.authorization()
    assert auth["anytime_guarantee_active"] is True
    assert auth["evidence_authorized_action_permitted"] is False  # shadow only


def test_monitor_violated_above_hard_dependence_limit():
    import math
    import random
    random.seed(4)
    m = ValidityMonitor()
    s = 0.0
    for _ in range(400):
        s = 0.995 * s + math.sqrt(1 - 0.995 ** 2) * random.gauss(0, 1)
        m.update(s)
    assert m.state() is Validity.VIOLATED
    assert m.authorization()["anytime_guarantee_active"] is False


def test_monitor_uncertain_on_variance_shift_and_context_change():
    import random
    random.seed(5)
    m = ValidityMonitor(calibration_var=1.0)
    m.note_context("hover")
    for _ in range(400):
        m.update(random.gauss(0, 3.0))         # variance 9x calibration
    assert m.state() is Validity.UNCERTAIN
    m2 = ValidityMonitor()
    m2.note_context("hover")
    for _ in range(200):
        m2.update(random.gauss(0, 1))
    m2.note_context("aggressive")              # context transition
    for _ in range(50):
        m2.update(random.gauss(0, 1))
    assert m2.state() is Validity.UNCERTAIN


def test_monitor_fails_closed_when_starved():
    m = ValidityMonitor()
    assert m.update(0.1) is Validity.UNCERTAIN   # 1 sample: never SUPPORTED
    assert m.authorization()["causal_diagnosis_mode"] == "RESEARCH_ONLY"


# --- core-mode isolation ------------------------------------------------------

def test_embedded_runtime_does_not_import_data_lake_packages():
    """csia.runtime + csia.native must stay importable with no polars/duckdb/
    pyarrow in their import graphs."""
    import subprocess
    import sys
    code = (
        "import sys\n"
        "banned = ('polars', 'duckdb', 'pyarrow')\n"
        "import csia.runtime, csia.native, csia.trust_engine.engine\n"
        "loaded = [b for b in banned if any(m == b or m.startswith(b + '.')\n"
        "          for m in sys.modules)]\n"
        "assert not loaded, f'embedded path imported {loaded}'\n"
        "print('core-mode clean')\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "core-mode clean" in r.stdout


# --- baseline report honesty --------------------------------------------------

def test_v1_baseline_reports_zero_real_flights_honestly():
    p = os.path.join(ROOT, "datasets", "reports",
                     "csia_v1_cross_dataset_baseline_v1.json")
    with open(p) as fh:
        doc = json.load(fh)["payload"]
    assert doc["processable_real_flights"] == 0
    assert doc["eligible_monitored_hours"] == 0.0
    assert "NOT COMPUTABLE" in doc["detection_metrics"]
    assert doc["pipeline_validation"]["fixture_note"].startswith("SYNTHETIC")
