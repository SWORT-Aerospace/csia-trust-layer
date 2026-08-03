"""Operator monitoring and scientific-integrity gates on partitioning.

Two failure modes are pinned here.

The operator one: monitoring must not depend on `watch(1)`, which stock
macOS does not ship — a runbook that assumes it strands the operator
mid-download with no way to see progress.

The scientific one: a protected split is only as strong as the identity it
groups by. Without per-aircraft grouping the same airframe can sit on both
sides of the boundary, so "unseen-aircraft generalization" is not evidenced
however good the numbers look. These tests make the tooling refuse the claim
rather than leave it to a reader's discretion.

Nothing here touches the network, CSIA, or real flight data.
"""

import json
import os
import subprocess
import sys

import pytest

from csia.data.grouping import (GENERIC_STEM_THRESHOLD, audit_grouping,
                                collect_candidates, detect_collisions,
                                normalized_stem)
from csia.data.partition import (AIRCRAFT_LEVEL_CLAIMS, QUALITY_AIRCRAFT,
                                 QUALITY_CAMPAIGN, QUALITY_FILE,
                                 QUALITY_LINEAGE, QUALITY_SESSION,
                                 QUALITY_UNGROUPED, STRONG_QUALITIES,
                                 TIER_AIRCRAFT, TIER_CAMPAIGN, TIER_FILEGROUP,
                                 TIER_FLIGHT, TIER_LINEAGE, TIER_SESSION,
                                 claim_policy, freeze_partitions,
                                 partition_quality)
from csia.data.paths import REPO_ROOT, DataRoot

sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
import run_uav_sead_mac_pipeline as pipe  # noqa: E402

TOOL = os.path.join(REPO_ROOT, "tools", "run_uav_sead_mac_pipeline.py")
RUNBOOK = os.path.join(REPO_ROOT, "docs", "runbooks",
                       "UAV_SEAD_MAC_ACQUISITION.md")
PREREG = os.path.join(REPO_ROOT, "docs", "validation",
                      "UAV_SEAD_CSIA_V1_PREREGISTRATION.md")


@pytest.fixture
def lake(tmp_path):
    root = DataRoot(str(tmp_path / "CSIA_DATA_LAKE"), "cli:--data-root")
    os.makedirs(root.path)
    root.ensure()
    return root


# --- 1-5. monitor stage -------------------------------------------------------

def test_monitor_uses_no_external_command():
    """`watch` is not on a stock macOS install; grep the source and runbook."""
    src = open(TOOL).read()
    assert "def stage_monitor" in src
    assert "time.sleep" in src
    for banned in ("watch -n", "subprocess.run([\"watch",
                   "os.system", "shutil.which(\"watch\")"):
        assert banned not in src, banned
    book = open(RUNBOOK).read()
    assert "watch -n 30" not in book, "runbook still tells the operator to use watch(1)"
    assert "--stage monitor" in book


def test_monitor_tolerates_a_missing_progress_file(lake):
    args = pipe.build_parser().parse_args(
        ["--stage", "monitor", "--once", "--data-root", lake.path])
    res = pipe.stage_monitor(lake, args)
    assert res["ok"] is True
    assert res["state"] == "NOT_STARTED"
    assert res["percent_complete"] is None
    assert res["estimated_remaining_seconds"] is None


def test_monitor_reports_every_required_field(lake):
    staging = os.path.join(lake.cache, "uav_sead", "a" * 40)
    os.makedirs(os.path.join(staging, "ulg_files"))
    open(os.path.join(staging, "ulg_files", "f1.ulg"), "wb").write(b"x" * 500)
    open(os.path.join(staging, "mapping.json"), "w").write("{}")
    pipe.atomic_write_json(lake.report(pipe.PROGRESS_REPORT), {
        "state": "DOWNLOADING", "resolved_commit_sha": "a" * 40,
        "staging": staging, "expected_files": 4, "expected_bytes": 1000,
        "retries": 2, "errors": ["transient network error"],
        "started_utc": "2026-08-03T00:00:00Z"})
    args = pipe.build_parser().parse_args(
        ["--stage", "monitor", "--once", "--data-root", lake.path])
    s = pipe.monitor_snapshot(lake)
    for field in ("state", "pinned_commit", "files_completed",
                  "expected_files", "ulg_completed", "bytes_completed",
                  "expected_bytes", "percent_complete", "cache_size_bytes",
                  "free_bytes", "last_completed_file", "retries",
                  "last_error", "started_utc", "elapsed_seconds",
                  "rate_bytes_per_second", "estimated_remaining_seconds"):
        assert field in s, field
    assert s["files_completed"] == 2 and s["ulg_completed"] == 1
    assert s["retries"] == 2
    assert s["last_error"] == "transient network error"
    assert pipe.render_monitor(s)


def test_monitor_interval_is_configurable():
    args = pipe.build_parser().parse_args(
        ["--stage", "monitor", "--interval-seconds", "5"])
    assert args.interval_seconds == 5
    assert pipe.build_parser().parse_args(["--stage", "monitor"]) \
        .interval_seconds == 30


def test_monitor_exits_cleanly_on_keyboard_interrupt(lake, monkeypatch):
    calls = {"n": 0}

    def fake_sleep(_):
        calls["n"] += 1
        raise KeyboardInterrupt()
    monkeypatch.setattr(pipe.time, "sleep", fake_sleep)
    args = pipe.build_parser().parse_args(
        ["--stage", "monitor", "--data-root", lake.path])
    res = pipe.stage_monitor(lake, args)      # must not raise
    assert res["ok"] is True and calls["n"] == 1


def test_monitor_mutates_no_state(lake):
    pipe.atomic_write_json(lake.report(pipe.PROGRESS_REPORT),
                           {"state": "DOWNLOADING", "files_completed": 3})
    before = {p: os.path.getmtime(os.path.join(lake.reports, p))
              for p in os.listdir(lake.reports)}
    raw_before = os.listdir(lake.raw)
    args = pipe.build_parser().parse_args(
        ["--stage", "monitor", "--once", "--data-root", lake.path])
    pipe.stage_monitor(lake, args)
    after = {p: os.path.getmtime(os.path.join(lake.reports, p))
             for p in os.listdir(lake.reports)}
    assert after == before, "monitor wrote to the reports directory"
    assert os.listdir(lake.raw) == raw_before
    assert json.load(open(lake.report(pipe.PROGRESS_REPORT)))[
        "files_completed"] == 3


# --- 6-9. partition-quality classification and claim gating -------------------

@pytest.mark.parametrize("tiers,expected", [
    ({TIER_AIRCRAFT: 10}, QUALITY_AIRCRAFT),
    ({TIER_CAMPAIGN: 10}, QUALITY_CAMPAIGN),
    ({TIER_SESSION: 10}, QUALITY_SESSION),
    ({TIER_LINEAGE: 10}, QUALITY_LINEAGE),
    ({TIER_FILEGROUP: 10}, QUALITY_FILE),
    ({TIER_FLIGHT: 10}, QUALITY_UNGROUPED),
    # fail closed: the WEAKEST tier present decides the whole corpus
    ({TIER_AIRCRAFT: 999, TIER_FLIGHT: 1}, QUALITY_UNGROUPED),
    ({TIER_AIRCRAFT: 50, TIER_FILEGROUP: 2}, QUALITY_FILE),
])
def test_partition_quality_is_the_weakest_tier_present(tiers, expected):
    assert partition_quality(tiers) == expected


def test_aircraft_grouping_permits_the_blind_claim():
    p = claim_policy(QUALITY_AIRCRAFT)
    assert p["aircraft_level_blind_claim_permitted"] is True
    assert p["blind_test_label_permitted"] is True
    assert p["protected_partition_label"] == "BLIND_TEST"
    assert p["prohibited_claims"] == []


@pytest.mark.parametrize("q", [QUALITY_CAMPAIGN, QUALITY_SESSION,
                               QUALITY_LINEAGE])
def test_strong_but_non_aircraft_grouping_forbids_aircraft_claims(q):
    """Campaign/session/lineage give a real holdout, but the same airframe
    can appear on both sides — so vehicle-level claims stay prohibited."""
    p = claim_policy(q)
    assert q in STRONG_QUALITIES
    assert p["blind_test_label_permitted"] is True
    assert p["protected_partition_label"] == "BLIND_TEST"
    assert p["aircraft_level_blind_claim_permitted"] is False
    for claim in AIRCRAFT_LEVEL_CLAIMS:
        assert claim in p["prohibited_claims"], claim


@pytest.mark.parametrize("q,label", [(QUALITY_FILE, "FILE_LEVEL_HOLDOUT"),
                                     (QUALITY_UNGROUPED, "UNGROUPED_HOLDOUT")])
def test_weak_grouping_renames_the_holdout_and_forbids_blind_language(q,
                                                                      label):
    p = claim_policy(q)
    assert p["protected_partition_label"] == label
    assert p["blind_test_label_permitted"] is False
    assert p["aircraft_level_blind_claim_permitted"] is False
    for claim in AIRCRAFT_LEVEL_CLAIMS:
        assert claim in p["prohibited_claims"]
    assert any("externally blind" in c for c in p["prohibited_claims"])


def test_manifest_renames_the_protected_partition_when_grouping_is_weak():
    """The label itself must change: a downstream reader seeing BLIND_TEST
    would otherwise claim more than the grouping supports."""
    # names with no trailing counter share no stem => no file group at all
    weak = {f"{c}{c}{c}.ulg": {"metadata": {}}
            for c in "abcdefghijklmnopqrstuvwxyz"}
    man = freeze_partitions(weak, "0" * 64, "c", "t")
    assert man["partition_quality"] == QUALITY_UNGROUPED
    assert man["protected_partition_label"] == "UNGROUPED_HOLDOUT"
    assert "BLIND_TEST" not in man["partition_counts"]
    assert "UNGROUPED_HOLDOUT" in man["partition_counts"]
    assert all(a["partition"] != "BLIND_TEST"
               for a in man["assignments"].values())
    assert man["aircraft_level_blind_claim_permitted"] is False

    strong = {f"f{i}.ulg": {"metadata": {"aircraft_id": f"AC{i % 6}"}}
              for i in range(40)}
    man = freeze_partitions(strong, "0" * 64, "c", "t")
    assert man["partition_quality"] == QUALITY_AIRCRAFT
    assert "BLIND_TEST" in man["partition_counts"]
    assert man["aircraft_level_blind_claim_permitted"] is True


def test_manifest_reports_distributions_and_risks():
    flights = {f"f{i}.ulg": {"metadata": {"aircraft_id": f"AC{i % 5}"}}
               for i in range(30)}
    labels = {f: ("normal" if i % 3 else "motor_failure")
              for i, f in enumerate(flights)}
    man = freeze_partitions(flights, "0" * 64, "c", "t", labels=labels)
    assert man["group_size_distribution"]
    assert man["group_size_min"] and man["group_size_max"]
    assert man["label_distribution_by_partition"]
    assert man["anomaly_family_distribution_by_partition"]
    assert isinstance(man["potential_leakage_risks"], list)
    assert man["grouping_fields_used"]
    assert man["permitted_evaluation_claims"]


# --- 10-11. grouping audit and collision refusal ------------------------------

def test_grouping_audit_ranks_candidates_and_reports_limitations():
    flights = {f"f{i}.ulg": {"metadata": {"aircraft_id": f"AC{i % 4}",
                                          "note": "x"}}
               for i in range(20)}
    audit = audit_grouping(flights, None, read_ulog=False)
    assert audit["flight_count"] == 20
    assert audit["signal_content_read"] is False
    assert audit["selected_grouping_rule"]["identity_class"] == "aircraft"
    assert audit["candidate_count"] >= 2
    assert audit["rejected_grouping_rules"]
    assert audit["safe_to_partition"] is True
    for r in audit["rejected_grouping_rules"]:
        assert r.get("reason")


def test_grouping_audit_rejects_incomplete_and_per_flight_fields():
    flights = {"a.ulg": {"metadata": {"aircraft_id": "AC1", "uuid": "u1"}},
               "b.ulg": {"metadata": {"uuid": "u2"}}}     # aircraft missing
    audit = audit_grouping(flights, None, read_ulog=False)
    rejected = {r["field"] for r in audit["rejected_grouping_rules"]}
    assert "mapping:aircraft_id" in rejected
    assert audit["selected_grouping_rule"] is None
    assert any("no complete" in x for x in audit["scientific_limitations"])


def test_audit_flags_specific_stem_collisions_but_ignores_generic_prefixes():
    related = {"log_7_1.ulg": {}, "log_7_2.ulg": {}}
    coll = detect_collisions(lambda f: f, related)          # each its own group
    assert coll["collision_count"] == 1
    assert coll["related_file_collisions"][0]["stem"] == "log_7"

    generic = {f"flight_{i}.ulg": {} for i in range(GENERIC_STEM_THRESHOLD + 5)}
    coll = detect_collisions(lambda f: f, generic)
    assert coll["collision_count"] == 0, \
        "a naming convention was mistaken for an identity"
    assert coll["generic_stems_ignored"]


def test_normalized_stem_strips_only_trailing_counters():
    assert normalized_stem("ulg_files/log_0042_3.ulg") == "log_0042"
    assert normalized_stem("AC7_mission.ulg") == "AC7_mission"


def test_partition_stage_refuses_on_unresolved_collisions(lake, monkeypatch):
    snap = os.path.join(lake.raw, "uav_sead", "a" * 64)
    os.makedirs(os.path.join(snap, "ulg_files"))
    # aircraft_id is shared across several flights (so it is a usable
    # grouping rule), but log_7_1/log_7_2 look related and belong to
    # DIFFERENT aircraft — exactly the collision that must stop partitioning
    open(os.path.join(snap, "mapping.json"), "w").write(json.dumps({
        "log_7_1.ulg": {"anomaly": "gps", "aircraft_id": "AC1"},
        "alpha_one.ulg": {"anomaly": "normal", "aircraft_id": "AC1"},
        "beta_two.ulg": {"anomaly": "normal", "aircraft_id": "AC1"},
        "log_7_2.ulg": {"anomaly": "normal", "aircraft_id": "AC2"},
        "gamma_three.ulg": {"anomaly": "gps", "aircraft_id": "AC2"},
        "delta_four.ulg": {"anomaly": "normal", "aircraft_id": "AC2"}}))
    pipe.atomic_write_json(lake.report(pipe.MAPPING_REPORT), {"ok": True})
    args = pipe.build_parser().parse_args(
        ["--stage", "partition", "--data-root", lake.path,
         "--no-ulog-metadata"])
    res = pipe.stage_partition(lake, args)
    assert res["ok"] is False
    assert "collision" in res["error"]
    assert not os.path.isfile(os.path.join(lake.manifests, "uav_sead",
                                           pipe.PARTITION_MANIFEST))
    assert os.path.isfile(lake.report(pipe.GROUPING_AUDIT))


def test_grouping_audit_report_is_written_under_the_data_root(lake):
    snap = os.path.join(lake.raw, "uav_sead", "b" * 64)
    os.makedirs(os.path.join(snap, "ulg_files"))
    open(os.path.join(snap, "mapping.json"), "w").write(json.dumps(
        {f"ac{i % 3}_m{i}.ulg": {"anomaly": "normal",
                                 "aircraft_id": f"AC{i % 3}"}
         for i in range(12)}))
    pipe.atomic_write_json(lake.report(pipe.MAPPING_REPORT), {"ok": True})
    args = pipe.build_parser().parse_args(
        ["--stage", "partition", "--data-root", lake.path,
         "--no-ulog-metadata"])
    res = pipe.stage_partition(lake, args)
    assert res["ok"] is True, res.get("error")
    audit_path = lake.report(pipe.GROUPING_AUDIT)
    assert audit_path.startswith(lake.path)
    assert not audit_path.startswith(REPO_ROOT)
    audit = json.load(open(audit_path))
    assert audit["selected_grouping_rule"]["identity_class"] == "aircraft"
    assert res["partition_quality"] == QUALITY_AIRCRAFT


# --- 12-13. certificate claim limits ------------------------------------------

def build_certified_lake(lake, aircraft=True):
    from csia.data.snapshot import (aggregate_hash, build_manifest,
                                    materialize, provenance_record,
                                    write_provenance)
    staging = os.path.join(lake.cache, "uav_sead", "c" * 40)
    os.makedirs(os.path.join(staging, "ulg_files"))
    mapping = {}
    for i in range(12):
        name = (f"ac{i % 3}_m{i}.ulg" if aircraft
                else f"{'abcdefghijkl'[i]}{'abcdefghijkl'[i]}x.ulg")
        open(os.path.join(staging, "ulg_files", name), "wb").write(b"x" * 10)
        meta = {"anomaly": "normal" if i % 2 else "motor_failure"}
        if aircraft:
            meta["aircraft_id"] = f"AC{i % 3}"
        mapping[name] = meta
    open(os.path.join(staging, "mapping.json"), "w").write(json.dumps(mapping))

    manifest = build_manifest(staging)
    digest = aggregate_hash(manifest)
    placed = materialize(staging, lake.raw, "uav_sead", manifest, digest)
    write_provenance(lake.manifests, "uav_sead", provenance_record(
        "uav_sead", {"provider": "huggingface", "repo_id": "x",
                     "repo_type": "dataset", "resolved_commit_sha": "c" * 40,
                     "requested_revision": "main"},
        manifest, digest, placed["path"], "2026-08-03T00:00:00Z",
        "CC-BY-4.0", "10.57967/hf/7772"))
    pipe.atomic_write_json(lake.report(pipe.ENV_REPORT), {
        "checks": {"python_version": "3.13.12", "git_clean": True,
                   "dependency_versions": {}}})
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "repository_commit": "abc", "huggingface_repo_id": "x",
        "doi": "10.57967/hf/7772", "registry_license": "CC-BY-4.0",
        "hub_license": "cc-by-4.0", "license_match": True})
    for stage in ("mapping", "partition"):
        args = pipe.build_parser().parse_args(
            ["--stage", stage, "--data-root", lake.path,
             "--no-ulog-metadata"])
        res = pipe.run_stage(stage, lake, args)
        assert res.get("ok"), (stage, res.get("error"))
    args = pipe.build_parser().parse_args(
        ["--stage", "certificate", "--data-root", lake.path])
    return pipe.stage_certificate(lake, args)


def test_certificate_permits_the_aircraft_claim_only_with_vehicle_grouping(
        lake):
    cert = build_certified_lake(lake, aircraft=True)
    assert cert["ok"] is True
    assert cert["aircraft_level_blind_claim_permitted"] is True
    assert cert["partitions"]["partition_quality"] == QUALITY_AIRCRAFT
    assert cert["partitions"]["protected_partition_label"] == "BLIND_TEST"
    assert cert["csia_evaluation_started"] is False


def test_certificate_forbids_the_aircraft_claim_without_grouping(tmp_path):
    lake = DataRoot(str(tmp_path / "L"), "cli:--data-root")
    os.makedirs(lake.path)
    lake.ensure()
    cert = build_certified_lake(lake, aircraft=False)
    assert cert["aircraft_level_blind_claim_permitted"] is False
    assert cert["blind_test_label_permitted"] is False
    assert cert["partitions"]["protected_partition_label"] == \
        "UNGROUPED_HOLDOUT"
    for claim in AIRCRAFT_LEVEL_CLAIMS:
        assert claim in cert["prohibited_claims"], claim
    body = open(lake.report(pipe.CERT_MD)).read()
    assert "aircraft_level_blind_claim_permitted: false" in body
    assert "UNGROUPED_HOLDOUT" in body
    assert "BLIND_TEST" not in body.split("### Claims")[0].split(
        "## Partitions")[1]


def test_certificate_records_grouping_limitations(tmp_path):
    lake = DataRoot(str(tmp_path / "L2"), "cli:--data-root")
    os.makedirs(lake.path)
    lake.ensure()
    cert = build_certified_lake(lake, aircraft=False)
    assert cert["grouping_audit"]["scientific_limitations"]
    assert cert["claim_rationale"]


# --- 14-15. documents ---------------------------------------------------------

def test_preregistration_exists_and_is_frozen_before_results():
    body = open(PREREG).read()
    assert "FROZEN before any CSIA result" in body
    for mode in ("Frozen CSIA v1", "Calibration-only",
                 "oracle retuning"):
        assert mode in body, mode
    for outcome in ("Outcome A", "Outcome B", "Outcome C"):
        assert outcome in body, outcome
    for metric in ("event precision", "event recall", "event F1",
                   "false-alert episodes per monitored hour",
                   "correct abstention", "confident incorrect isolation"):
        assert metric in body, metric
    for restriction in ("No threshold tuning on protected holdout data",
                        "No millisecond latency claims",
                        "No retroactive partition changes"):
        assert restriction in body, restriction
    assert "AIRCRAFT_GROUPED" in body and "UNGROUPED_HOLDOUT" in body


def test_runbook_git_update_is_fail_fast():
    body = open(RUNBOOK).read()
    assert "git pull --ff-only origin claude/code-reviewer-repo-export-zicovg" \
        in body
    assert "git fetch origin" in body
    assert "git switch claude/code-reviewer-repo-export-zicovg" in body
    # a dirty tree must stop the operator, never be auto-cleaned
    assert "git stash" not in body, \
        "runbook still tells the operator to stash over a dirty tree"
    assert "git reset" not in body
    dirty = body.split("### Dirty Git tree")[1][:600].lower()
    assert "stop" in dirty


def test_runbook_documents_grouping_quality_consequences():
    body = open(RUNBOOK).read()
    for token in ("partition_quality", "AIRCRAFT_GROUPED",
                  "FILE_LEVEL_HOLDOUT", "UNGROUPED_HOLDOUT",
                  "uav_sead_grouping_audit.json"):
        assert token in body, token
