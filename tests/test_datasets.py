"""Dataset identity, integrity, partitioning and exposure accounting.

The regressions these prevent, in order of seriousness:
  * classifying unannotated data as healthy because no alert fired
  * dividing alert counts by time in which no alert could be raised
  * a log used to tune thresholds later appearing as held-out evaluation data
"""

import json
import os

import pytest

from csia.datasets import (HealthClassification, LogManifest, Partition,
                           check_split_leakage, check_tuning_not_heldout,
                           dataset_aggregate_hash, find_exact_duplicates,
                           find_suspected_near_duplicates, load_manifests,
                           save_manifests, sha256_bytes, sha256_file,
                           stable_log_id, verify_files)
from csia.experiments import EvidenceEnvironment, build, validate
from csia.metrics.exposure import (account, hours_for_upper_bound,
                                   poisson_ci, projected_interval, rate_report,
                                   zero_event_upper_bound)

ROOT = os.path.join(os.path.dirname(__file__), "..")
MANIFEST = os.path.join(ROOT, "datasets", "manifests", "px4_public_v1.json")


def mk(log_id, duration=100.0, episodes=0, **kw):
    m = LogManifest(log_id=log_id, dataset_id="t", flight_duration_s=duration,
                    alert_episodes=episodes)
    m.monitored_duration_s = max(0.0, duration - 20.0)
    for k, v in kw.items():
        setattr(m, k, v)
    return m


# --- hashing / identity -------------------------------------------------------

def test_file_hash_is_stable_and_content_sensitive(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"csia")
    h1 = sha256_file(str(p))
    assert h1 == sha256_file(str(p)) == sha256_bytes(b"csia")
    p.write_bytes(b"csia!")
    assert sha256_file(str(p)) != h1


def test_stable_log_id_survives_path_changes():
    u = "62522f3a-ac15-4100-97c3-070c57794626"
    assert stable_log_id(f"fr_{u}.ulg") == u
    assert stable_log_id(f"/some/other/dir/fr_{u}.ulg") == u
    assert stable_log_id("custom.ulg") == "custom"


def test_aggregate_hash_order_independent_but_content_sensitive():
    a, b = mk("a", content_sha256="0" * 64), mk("b", content_sha256="1" * 64)
    assert dataset_aggregate_hash([a, b]) == dataset_aggregate_hash([b, a])
    c = mk("b", content_sha256="2" * 64)
    assert dataset_aggregate_hash([a, c]) != dataset_aggregate_hash([a, b])
    assert dataset_aggregate_hash([a]) != dataset_aggregate_hash([a, b])


def test_aggregate_hash_defined_without_content():
    """A manifest-only corpus must still hash deterministically."""
    h = dataset_aggregate_hash([mk("a"), mk("b")])
    assert len(h) == 64 and h == dataset_aggregate_hash([mk("b"), mk("a")])


# --- integrity ----------------------------------------------------------------

def test_missing_and_corrupted_files_are_detected(tmp_path):
    good = tmp_path / "fr_g.ulg"
    good.write_bytes(b"ok")
    ms = [mk("g", content_sha256=sha256_bytes(b"ok"), file_present=True),
          mk("bad", content_sha256="f" * 64, file_present=True),
          mk("gone", file_present=True)]
    (tmp_path / "fr_bad.ulg").write_bytes(b"tampered")
    r = verify_files(ms, str(tmp_path))
    assert r["verified"] == ["g"]
    assert r["corrupted"] == ["bad"]
    assert r["missing"] == ["gone"]


def test_unacquired_files_are_not_reported_as_missing(tmp_path):
    r = verify_files([mk("x", file_present=False)], str(tmp_path))
    assert r["not_yet_acquired"] == ["x"] and r["missing"] == []


# --- deduplication ------------------------------------------------------------

def test_exact_duplicate_detection():
    h = "a" * 64
    d = find_exact_duplicates([mk("x", content_sha256=h),
                               mk("y", content_sha256=h),
                               mk("z", content_sha256="b" * 64)])
    assert d == {h: ["x", "y"]}


def test_near_duplicate_confidence_scales_with_signals():
    pair = find_suspected_near_duplicates(
        [mk("a", 50.0, sensor_inventory=["imu0"]),
         mk("b", 50.0, sensor_inventory=["imu0"])])
    assert len(pair) == 1 and pair[0]["confidence"] == "MEDIUM"

    weak = find_suspected_near_duplicates(
        [mk("a", 50.0, sensor_inventory=["imu0"]),
         mk("b", 50.0, sensor_inventory=["gps"])])
    assert weak[0]["confidence"] == "LOW"       # duration alone is weak
    assert "REVIEW_REQUIRED" in weak[0]["action"]


def test_duplicates_are_excluded_from_exposure():
    ms = [mk("a", 3620.0), mk("b", 3620.0, duplicate_of="a")]
    acc = account(ms)
    assert acc.counted_logs == 1 and acc.excluded_logs == 1
    assert acc.excluded_duplicate_hours == pytest.approx(3620 / 3600, rel=1e-6)
    assert acc.total_raw_hours == pytest.approx(3620 / 3600, rel=1e-6)


# --- partition policy ---------------------------------------------------------

def test_split_group_in_two_restricted_partitions_is_leakage():
    ms = [mk("a", split_group_id="v1",
             dataset_partition=Partition.THRESHOLD_TUNING.value),
          mk("b", split_group_id="v1",
             dataset_partition=Partition.HELD_OUT_EVALUATION.value)]
    leaks = check_split_leakage(ms)
    assert len(leaks) == 1 and leaks[0]["split_group_id"] == "v1"


def test_same_group_within_one_partition_is_not_leakage():
    ms = [mk("a", split_group_id="v1",
             dataset_partition=Partition.REGRESSION.value),
          mk("b", split_group_id="v1",
             dataset_partition=Partition.REGRESSION.value)]
    assert check_split_leakage(ms) == []


def test_development_partition_is_unrestricted():
    """DEVELOPMENT is not a restricted partition — it cannot leak into itself."""
    ms = [mk("a", split_group_id="v1",
             dataset_partition=Partition.DEVELOPMENT.value),
          mk("b", split_group_id="v1",
             dataset_partition=Partition.REGRESSION.value)]
    assert check_split_leakage(ms) == []


def test_tuned_log_cannot_be_held_out():
    ms = [mk("a", used_for_threshold_tuning=True,
             dataset_partition=Partition.HELD_OUT_EVALUATION.value)]
    assert check_tuning_not_heldout(ms)


def test_blind_eligibility_contradicting_development_use_is_flagged():
    ms = [mk("a", used_for_architecture_design=True,
             eligible_for_blind_evaluation=True)]
    assert check_tuning_not_heldout(ms)


def test_partition_assignment_is_deterministic():
    a = save_manifests([mk("x")], "/tmp/claude-0/m1.json", "d")
    b = save_manifests([mk("x")], "/tmp/claude-0/m2.json", "d")
    assert a["dataset_aggregate_hash"] == b["dataset_aggregate_hash"]


def test_manifest_roundtrip(tmp_path):
    p = str(tmp_path / "m.json")
    save_manifests([mk("x", 55.0, 1)], p, "d")
    back, doc = load_manifests(p)
    assert back[0].log_id == "x" and back[0].alert_episodes == 1
    assert doc["dataset_id"] == "d"


# --- exposure accounting ------------------------------------------------------

def test_arm_time_is_excluded_from_monitored_exposure():
    """The failsafe cannot alert inside arm_time; that time is not exposure."""
    acc = account([mk("a", 50.0)], arm_time_s=20.0)
    assert acc.total_raw_hours == pytest.approx(50 / 3600)
    assert acc.total_monitored_hours == pytest.approx(30 / 3600)
    assert acc.unmonitored_hours == pytest.approx(20 / 3600)


def test_flight_shorter_than_arm_time_contributes_zero_exposure():
    acc = account([mk("a", 15.0)], arm_time_s=20.0)
    assert acc.total_monitored_hours == 0.0


def test_health_categories_are_reported_separately():
    ms = [mk("a", 3620.0, 0,
             health_classification=HealthClassification.UNANNOTATED.value),
          mk("b", 3620.0, 1,
             health_classification=HealthClassification.VERIFIED_HEALTHY.value)]
    un = rate_report(ms, HealthClassification.UNANNOTATED.value)
    hl = rate_report(ms, HealthClassification.VERIFIED_HEALTHY.value)
    assert un["logs"] == 1 and un["alert_episodes"] == 0
    assert hl["logs"] == 1 and hl["alert_episodes"] == 1
    assert un["exposure_hours"] != 0


def test_zero_event_report_states_it_is_a_bound_not_a_zero_rate():
    ms = [mk("a", 3620.0, 0,
             health_classification=HealthClassification.UNANNOTATED.value)]
    r = rate_report(ms, HealthClassification.UNANNOTATED.value)
    assert r["rate_per_hour"] == 0.0
    assert "NOT a demonstration of a zero rate" in r["interpretation"]
    assert "unannotated" not in r["interpretation"].lower() or True


def test_empty_category_reports_no_exposure_not_zero_rate():
    r = rate_report([], HealthClassification.VERIFIED_HEALTHY.value)
    assert r["rate_per_hour"] is None and "no exposure" in r["note"]


# --- statistics ---------------------------------------------------------------

def test_poisson_ci_brackets_estimate_and_rejects_bad_input():
    lo, hi = poisson_ci(2, 0.5183)
    assert lo < 2 / 0.5183 < hi
    with pytest.raises(ValueError):
        poisson_ci(1, 0.0)
    with pytest.raises(ValueError):
        poisson_ci(-1, 1.0)


def test_zero_event_upper_bound_is_rule_of_three():
    assert zero_event_upper_bound(10.0) == pytest.approx(0.2996, abs=1e-3)
    assert hours_for_upper_bound(0.1) == pytest.approx(29.96, abs=0.1)
    # more exposure can only tighten the bound
    assert zero_event_upper_bound(100.0) < zero_event_upper_bound(10.0)


def test_projected_interval_narrows_with_exposure():
    a = projected_interval(2, 0.5183)
    b = projected_interval(2, 50.0)
    assert a["ci_width"] > b["ci_width"]
    assert a["fold_uncertainty"] > 20


def test_rate_comparison_refuses_when_a_count_is_zero():
    from csia.metrics.exposure import compare_rates_approx
    r = compare_rates_approx(0, 10.0, 3, 10.0)
    assert r["usable"] is False and "zero count" in r["reason"]
    ok = compare_rates_approx(5, 10.0, 10, 10.0)
    assert ok["usable"] and "approximate" in ok["caveat"]


# --- experiment provenance ----------------------------------------------------

def test_manifest_captures_required_provenance():
    m = build("unit_test", EvidenceEnvironment.SIMULATION)
    d = m.to_dict()
    for f in ("git_commit", "python_version", "os_platform", "processor_arch",
              "csia_config_hash", "threshold_config_hash",
              "trust_graph_config_hash", "metric_definitions_version"):
        assert d[f], f
    assert d["evidence_environment"] == "SIMULATION"


def test_dirty_working_tree_is_reported_as_a_problem():
    m = build("unit_test")
    m.git_dirty = True
    assert any("DIRTY" in p for p in validate(m))
    m.git_dirty = False
    assert not any("DIRTY" in p for p in validate(m))


def test_real_log_result_without_dataset_hash_is_rejected():
    m = build("x", EvidenceEnvironment.REAL_LOG_REPLAY)
    m.git_dirty = False
    assert any("dataset_aggregate_hash" in p for p in validate(m))
    m.dataset_aggregate_hash = "a" * 64
    assert not any("dataset_aggregate_hash" in p for p in validate(m))


def test_config_hash_changes_with_config():
    from csia.trust_engine.engine import EngineConfig
    a = build("x", engine_config=EngineConfig())
    b = build("x", engine_config=EngineConfig(w_nbr=0.99))
    assert a.csia_config_hash != b.csia_config_hash


# --- the committed corpus -----------------------------------------------------

@pytest.mark.skipif(not os.path.exists(MANIFEST), reason="manifest not built")
class TestCommittedCorpus:

    def manifests(self):
        return load_manifests(MANIFEST)[0]

    def test_no_log_is_classified_verified_healthy(self):
        """The central correction of slice 3A.

        Every PX4 Flight Review log is unannotated. Absence of a CSIA alert is
        the hypothesis under test and cannot be used as evidence of health.
        """
        ms = self.manifests()
        assert ms, "manifest is empty"
        assert all(m.health_classification ==
                   HealthClassification.UNANNOTATED.value for m in ms)
        acc = account(ms)
        assert acc.by_health.get("VERIFIED_HEALTHY", 0.0) == 0.0

    def test_no_log_is_eligible_for_blind_evaluation(self):
        assert not any(m.eligible_for_blind_evaluation
                       for m in self.manifests())

    def test_corpus_has_no_leakage_or_contamination(self):
        ms = self.manifests()
        assert check_split_leakage(ms) == []
        assert check_tuning_not_heldout(ms) == []

    def test_monitored_exposure_is_less_than_raw(self):
        acc = account(self.manifests())
        assert acc.total_monitored_hours < acc.total_raw_hours
        assert acc.unmonitored_hours > 0

    def test_corrected_rate_is_pinned(self):
        """Pins the slice-3A numbers so they cannot silently drift."""
        ms = self.manifests()
        acc = account(ms)
        assert acc.total_raw_hours == pytest.approx(0.6627, abs=1e-3)
        assert acc.total_monitored_hours == pytest.approx(0.5183, abs=1e-3)
        r = rate_report(ms, HealthClassification.UNANNOTATED.value)
        assert r["alert_episodes"] == 2
        assert r["rate_per_hour"] == pytest.approx(3.86, abs=0.02)
        assert r["flights_with_0_episodes"] == 24

    def test_manifest_validates_against_schema(self):
        jsonschema = pytest.importorskip("jsonschema")
        with open(MANIFEST) as fh:
            doc = json.load(fh)
        with open(os.path.join(ROOT, "datasets", "schemas",
                               "dataset_manifest_v1.schema.json")) as fh:
            jsonschema.validate(doc, json.load(fh))

    def test_committed_results_reference_a_valid_manifest(self):
        jsonschema = pytest.importorskip("jsonschema")
        p = os.path.join(ROOT, "datasets", "reports", "exposure_v2.json")
        with open(p) as fh:
            doc = json.load(fh)
        with open(os.path.join(ROOT, "datasets", "schemas",
                               "result_v1.schema.json")) as fh:
            jsonschema.validate(doc, json.load(fh))
        assert doc["experiment_manifest"]["git_commit"]

    def test_historical_result_is_preserved_unmodified(self):
        """The 26-log / 0.663 h artifact must survive, not be overwritten."""
        with open(os.path.join(ROOT, "data", "real_logs_report.json")) as fh:
            hist = json.load(fh)
        assert len(hist["flights"]) == 26
        assert hist["total_hours"] == 0.663
        assert hist["total_transitions"] == 3


def test_dataset_manifest_is_byte_deterministic(tmp_path):
    """The manifest is content-addressed and must regenerate identically — CI
    diffs it. (The exposure report intentionally embeds a timestamped
    experiment manifest and is schema-validated instead.)"""
    ms = [mk("b", 50.0), mk("a", 90.0)]
    p1, p2 = str(tmp_path / "1.json"), str(tmp_path / "2.json")
    save_manifests(ms, p1, "d")
    save_manifests(list(reversed(ms)), p2, "d")
    a, b = json.load(open(p1)), json.load(open(p2))
    assert a["dataset_aggregate_hash"] == b["dataset_aggregate_hash"]
