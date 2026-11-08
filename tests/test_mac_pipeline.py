"""Mac operator acquisition pipeline: gates, safety, partition freeze.

Every test runs offline against a mocked Hub and synthetic staging trees.
The real dataset is never downloaded — not here, and not in CI.

The safety properties pinned here are the ones that protect the science:
a snapshot is never promoted from an incomplete download, partitions are
frozen from metadata before any signal content could be inspected, groups
never straddle a protected boundary, and the certificate cannot claim
evaluation has started.
"""

import json
import os
import subprocess
import sys

import pytest

from csia.data.partition import (POLICY_VERSION, TIER_AIRCRAFT,
                                 TIER_CAMPAIGN, TIER_FLIGHT, TIER_SESSION,
                                 derive_group, freeze_partitions)
from csia.data.paths import REPO_ROOT, DataRoot
from csia.data.snapshot import aggregate_hash, build_manifest, materialize

sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
import run_uav_sead_mac_pipeline as pipe  # noqa: E402

TOOL = os.path.join(REPO_ROOT, "tools", "run_uav_sead_mac_pipeline.py")
MAC_DATA_ROOT = "/Volumes/CSIA_DATA/CSIA_DATA_LAKE"
FAKE_SHA = "b" * 40


def run_tool(*argv):
    env = dict(os.environ)
    env.pop("CSIA_DATA_ROOT", None)
    return subprocess.run([sys.executable, TOOL, *argv], capture_output=True,
                          text=True, timeout=180, cwd=REPO_ROOT, env=env)


@pytest.fixture
def lake(tmp_path):
    root = DataRoot(str(tmp_path / "CSIA_DATA_LAKE"), "cli:--data-root")
    os.makedirs(root.path)
    root.ensure()
    return root


# --- 1. Mac data-root detection -----------------------------------------------

def test_mac_data_root_layout_is_built_under_the_ssd():
    root = DataRoot(MAC_DATA_ROOT, "cli:--data-root")
    assert not root.is_repo_local
    assert root.raw_dir("uav_sead") == f"{MAC_DATA_ROOT}/raw/uav_sead"
    assert root.report("uav_sead_preflight.json") == \
        f"{MAC_DATA_ROOT}/reports/uav_sead_preflight.json"
    assert root.manifests == f"{MAC_DATA_ROOT}/manifests"
    assert root.cache == f"{MAC_DATA_ROOT}/cache"


# --- 2-5. environment gates ---------------------------------------------------

def test_missing_or_unwritable_data_root_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe.hub, "repo_inventory",
                        lambda *a, **k: {"resolved_commit_sha": FAKE_SHA})
    root = DataRoot(str(tmp_path / "absent"), "cli:--data-root")
    args = pipe.build_parser().parse_args(["--stage", "environment"])
    doc = pipe.stage_environment(root, args)
    assert doc["ok"] is False
    assert any("does not exist" in b for b in doc["blockers"])


def test_insufficient_space_blocks_preflight(lake, monkeypatch):
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: {
        "provider": "huggingface",
        "repo_id": "aykutkabaoglu/uav-flight-anomaly-dataset",
        "repo_type": "dataset", "requested_revision": "main",
        "resolved_commit_sha": FAKE_SHA,
        "files": [{"path": "ulg_files/a.ulg", "size": 1 << 50}],
        "file_count": 1, "excluded_paths": [], "excluded_count": 0,
        "total_bytes": 1 << 50, "sizes_unknown_for": 0, "size_known": True,
        "hub_license": "cc-by-4.0", "private": False, "gated": False})
    args = pipe.build_parser().parse_args(["--stage", "preflight"])
    doc = pipe.stage_preflight(lake, args)
    assert doc["download_authorized"] is False
    assert any("insufficient free space" in b for b in doc["blockers"])


def test_git_root_data_root_is_rejected_by_the_cli():
    r = run_tool("--stage", "preflight", "--data-root",
                 os.path.join(REPO_ROOT, "datasets"))
    assert r.returncode == 2
    assert "inside the Git repository" in r.stderr


def test_dirty_tree_blocks_preflight(lake, monkeypatch):
    monkeypatch.setattr(pipe, "git", lambda *a, **k: (
        " M csia/trust_engine/engine.py" if a[:1] == ("status",) else "abc123"))
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: {
        "provider": "huggingface", "repo_id":
            "aykutkabaoglu/uav-flight-anomaly-dataset",
        "repo_type": "dataset", "requested_revision": "main",
        "resolved_commit_sha": FAKE_SHA,
        "files": [{"path": "mapping.json", "size": 10}], "file_count": 1,
        "excluded_paths": [], "excluded_count": 0, "total_bytes": 10,
        "sizes_unknown_for": 0, "size_known": True,
        "hub_license": "cc-by-4.0", "private": False, "gated": False})
    args = pipe.build_parser().parse_args(["--stage", "preflight"])
    doc = pipe.stage_preflight(lake, args)
    assert doc["download_authorized"] is False
    assert any("unpermitted change" in b for b in doc["blockers"])


def test_license_mismatch_blocks_preflight(lake, monkeypatch):
    monkeypatch.setattr(pipe, "git", lambda *a, **k: "abc123")
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: {
        "provider": "huggingface", "repo_id":
            "aykutkabaoglu/uav-flight-anomaly-dataset",
        "repo_type": "dataset", "requested_revision": "main",
        "resolved_commit_sha": FAKE_SHA,
        "files": [{"path": "mapping.json", "size": 10}], "file_count": 1,
        "excluded_paths": [], "excluded_count": 0, "total_bytes": 10,
        "sizes_unknown_for": 0, "size_known": True,
        "hub_license": "mit", "private": False, "gated": False})
    args = pipe.build_parser().parse_args(["--stage", "preflight"])
    doc = pipe.stage_preflight(lake, args)
    assert doc["license_match"] is False
    assert any("license mismatch" in b for b in doc["blockers"])


# --- 6. Python 3.13 -----------------------------------------------------------

def test_declared_dependencies_import_on_this_interpreter():
    """Runs under every CI matrix interpreter, 3.13 included."""
    import importlib
    for mod in ("duckdb", "huggingface_hub", "jsonschema", "polars",
                "pyarrow", "pyulog", "yaml"):
        assert importlib.import_module(mod) is not None, mod


def test_ci_matrix_covers_python_312_and_313():
    wf = open(os.path.join(REPO_ROOT, ".github", "workflows",
                           "ci.yml")).read()
    assert '"3.12"' in wf and '"3.13"' in wf
    assert "matrix:" in wf and "python-version:" in wf


# --- 7-8. download confirmation token -----------------------------------------

def test_acquire_refuses_without_the_exact_confirmation_token(lake):
    r = run_tool("--stage", "acquire", "--data-root", lake.path)
    assert r.returncode == 3
    assert "UAV-SEAD" in r.stdout


@pytest.mark.parametrize("token", ["uav-sead", "UAV_SEAD", "UAVSEAD", "yes",
                                   "", None])
def test_only_the_exact_token_is_accepted(lake, token, monkeypatch):
    argv = ["--stage", "acquire", "--data-root", lake.path]
    if token is not None:
        argv += ["--confirm-download", token]
    args = pipe.build_parser().parse_args(argv)
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "download_authorized": True, "resolved_commit_sha": FAKE_SHA})
    res = pipe.stage_acquire(lake, args, dry_run=False)
    assert res["ok"] is False
    assert "confirm-download" in res["error"]


def test_dry_run_needs_no_token_and_downloads_nothing(lake, monkeypatch):
    calls = []
    monkeypatch.setattr(pipe.hub, "download_snapshot",
                        lambda *a, **k: calls.append(a))
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: {
        "resolved_commit_sha": FAKE_SHA, "file_count": 3, "total_bytes": 99,
        "files": [], "excluded_paths": [], "excluded_count": 0,
        "sizes_unknown_for": 0, "size_known": True, "hub_license": None,
        "private": False, "gated": False, "repo_id": "x",
        "repo_type": "dataset", "requested_revision": FAKE_SHA})
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "download_authorized": True, "resolved_commit_sha": FAKE_SHA})
    args = pipe.build_parser().parse_args(["--stage", "dry-run",
                                           "--data-root", lake.path])
    res = pipe.stage_acquire(lake, args, dry_run=True)
    assert res["ok"] is True and calls == []
    assert not os.listdir(lake.raw)


# --- 9-10. commit pinning -----------------------------------------------------

def test_acquire_uses_the_preflight_pinned_commit(lake, monkeypatch):
    seen = {}
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: {
        "resolved_commit_sha": FAKE_SHA, "file_count": 1, "total_bytes": 1,
        "files": [], "excluded_paths": [], "excluded_count": 0,
        "sizes_unknown_for": 0, "size_known": True, "hub_license": None,
        "private": False, "gated": False, "repo_id": "x",
        "repo_type": "dataset", "requested_revision": FAKE_SHA})
    monkeypatch.setattr(pipe.hub, "download_snapshot",
                        lambda repo, rtype, sha, dest, **k:
                        seen.update(sha=sha, dest=dest))
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "download_authorized": True, "resolved_commit_sha": FAKE_SHA})
    args = pipe.build_parser().parse_args(
        ["--stage", "acquire", "--data-root", lake.path,
         "--confirm-download", "UAV-SEAD"])
    pipe.stage_acquire(lake, args, dry_run=False)
    assert seen["sha"] == FAKE_SHA
    assert FAKE_SHA in seen["dest"]


def test_changed_upstream_commit_refuses_acquisition(lake, monkeypatch):
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: {
        "resolved_commit_sha": "c" * 40, "file_count": 1, "total_bytes": 1,
        "files": [], "excluded_paths": [], "excluded_count": 0,
        "sizes_unknown_for": 0, "size_known": True, "hub_license": None,
        "private": False, "gated": False, "repo_id": "x",
        "repo_type": "dataset", "requested_revision": FAKE_SHA})
    called = []
    monkeypatch.setattr(pipe.hub, "download_snapshot",
                        lambda *a, **k: called.append(a))
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "download_authorized": True, "resolved_commit_sha": FAKE_SHA})
    args = pipe.build_parser().parse_args(
        ["--stage", "acquire", "--data-root", lake.path,
         "--confirm-download", "UAV-SEAD"])
    res = pipe.stage_acquire(lake, args, dry_run=False)
    assert res["ok"] is False
    assert "upstream commit changed" in res["error"]
    assert called == [], "downloaded despite a changed upstream commit"


# --- 11-12. atomic, interrupt-safe progress -----------------------------------

def test_progress_writes_are_atomic_and_leave_no_partial_file(lake):
    p = lake.report(pipe.PROGRESS_REPORT)
    pipe.write_progress(lake, stage="acquire", state="STARTED")
    assert json.load(open(p))["state"] == "STARTED"
    pipe.write_progress(lake, state="DOWNLOADED", files_completed=7)
    doc = json.load(open(p))
    assert doc["state"] == "DOWNLOADED" and doc["files_completed"] == 7
    assert doc["stage"] == "acquire", "atomic update dropped earlier fields"
    leftovers = [f for f in os.listdir(lake.reports) if ".tmp." in f]
    assert leftovers == [], leftovers


def test_progress_file_stays_valid_json_after_many_updates(lake):
    for i in range(25):
        pipe.write_progress(lake, files_completed=i)
    assert json.load(open(lake.report(pipe.PROGRESS_REPORT)))[
        "files_completed"] == 24


def test_ctrl_c_records_interrupted_state_and_reraises(lake, monkeypatch):
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: {
        "resolved_commit_sha": FAKE_SHA, "file_count": 1, "total_bytes": 1,
        "files": [], "excluded_paths": [], "excluded_count": 0,
        "sizes_unknown_for": 0, "size_known": True, "hub_license": None,
        "private": False, "gated": False, "repo_id": "x",
        "repo_type": "dataset", "requested_revision": FAKE_SHA})

    def interrupt(*a, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(pipe.hub, "download_snapshot", interrupt)
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "download_authorized": True, "resolved_commit_sha": FAKE_SHA})
    args = pipe.build_parser().parse_args(
        ["--stage", "acquire", "--data-root", lake.path,
         "--confirm-download", "UAV-SEAD"])
    with pytest.raises(KeyboardInterrupt):
        pipe.stage_acquire(lake, args, dry_run=False)
    doc = json.load(open(lake.report(pipe.PROGRESS_REPORT)))
    assert doc["state"] == "INTERRUPTED"
    assert "resume" in doc["note"]


# --- 13-16. verification and promotion ----------------------------------------

def seed(root, complete=True):
    os.makedirs(os.path.join(root, "ulg_files"), exist_ok=True)
    open(os.path.join(root, "ulg_files", "a.ulg"), "wb").write(b"a" * 100)
    if complete:
        open(os.path.join(root, "ulg_files", "b.ulg"), "wb").write(b"b" * 200)
    open(os.path.join(root, "mapping.json"), "w").write(
        json.dumps({"a.ulg": "motor_failure", "b.ulg": "normal"}))
    return root


def test_incomplete_download_is_never_promoted(lake, monkeypatch):
    inv = {"files": [{"path": "ulg_files/a.ulg", "size": 100},
                     {"path": "ulg_files/b.ulg", "size": 200}],
           "file_count": 2, "resolved_commit_sha": FAKE_SHA}
    staging = os.path.join(lake.cache, "uav_sead", FAKE_SHA)
    seed(staging, complete=False)
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: inv)
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "resolved_commit_sha": FAKE_SHA, "file_count": 2})
    args = pipe.build_parser().parse_args(["--stage", "verify",
                                           "--data-root", lake.path])
    res = pipe.stage_verify(lake, args)
    assert res["ok"] is False and "incomplete" in res["error"]
    assert not os.path.isdir(lake.raw_dir("uav_sead")) or \
        not os.listdir(lake.raw_dir("uav_sead"))


def test_inventory_count_mismatch_blocks_promotion(lake, monkeypatch):
    inv = {"files": [{"path": "ulg_files/a.ulg", "size": 100},
                     {"path": "ulg_files/b.ulg", "size": 200}],
           "file_count": 2, "resolved_commit_sha": FAKE_SHA}
    staging = os.path.join(lake.cache, "uav_sead", FAKE_SHA)
    seed(staging)
    monkeypatch.setattr(pipe.hub, "repo_inventory", lambda *a, **k: inv)
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "resolved_commit_sha": FAKE_SHA, "file_count": 99})   # disagrees
    args = pipe.build_parser().parse_args(["--stage", "verify",
                                           "--data-root", lake.path])
    res = pipe.stage_verify(lake, args)
    assert res["ok"] is False and "file count" in res["error"]


def test_aggregate_hash_is_deterministic_across_trees(tmp_path):
    a, b = seed(str(tmp_path / "a")), seed(str(tmp_path / "b"))
    assert aggregate_hash(build_manifest(a)) == aggregate_hash(
        build_manifest(b))


def test_promotion_is_atomic_and_read_only(tmp_path):
    staging = seed(str(tmp_path / "stage"))
    manifest = build_manifest(staging)
    digest = aggregate_hash(manifest)
    placed = materialize(staging, str(tmp_path / "raw"), "uav_sead", manifest,
                         digest)
    assert placed["path"].endswith(digest)
    assert not [d for d in os.listdir(os.path.dirname(placed["path"]))
                if d.endswith(".materializing")]
    import stat
    mode = stat.S_IMODE(os.stat(os.path.join(placed["path"],
                                             "mapping.json")).st_mode)
    assert not mode & stat.S_IWUSR


# --- 17-19. partitioning ------------------------------------------------------

def test_partition_refuses_without_successful_mapping(lake):
    args = pipe.build_parser().parse_args(["--stage", "partition",
                                           "--data-root", lake.path])
    res = pipe.stage_partition(lake, args)
    assert res["ok"] is False
    assert "mapping" in res["error"]

    pipe.atomic_write_json(lake.report(pipe.MAPPING_REPORT), {"ok": False})
    res = pipe.stage_partition(lake, args)
    assert res["ok"] is False
    assert "refusing to partition" in res["error"]


def test_grouping_prefers_aircraft_then_campaign_then_session_then_flight():
    g = derive_group("f1.ulg", {"aircraft_id": "AC7", "session": "S1"})
    assert g["tier"] == TIER_AIRCRAFT and g["value"] == "AC7"
    g = derive_group("f1.ulg", {"campaign": "C2", "session_id": "S1"})
    assert g["tier"] == TIER_CAMPAIGN and g["value"] == "C2"
    # session is its own tier: it is weaker evidence than a campaign
    g = derive_group("f1.ulg", {"session_id": "S1"})
    assert g["tier"] == TIER_SESSION and g["value"] == "S1"
    g = derive_group("solitary.ulg", {})
    assert g["tier"] == TIER_FLIGHT


def test_same_aircraft_never_straddles_protected_partitions():
    flights = {f"ac1_flight_{i}.ulg": {"sha256": f"{i:064d}",
                                       "metadata": {"aircraft_id": "AC1"}}
               for i in range(25)}
    flights.update({f"ac2_flight_{i}.ulg": {"sha256": f"{i+100:064d}",
                                            "metadata": {"aircraft_id": "AC2"}}
                    for i in range(25)})
    man = freeze_partitions(flights, "d" * 64, "commit", "2026-08-03T00:00:00Z")
    assert man["leakage"] == [] and man["leakage_free"] is True
    parts = {}
    for a in man["assignments"].values():
        parts.setdefault(a["group_id"], set()).add(a["partition"])
    assert all(len(v) == 1 for v in parts.values())
    assert man["group_count"] == 2
    assert man["policy_version"] == POLICY_VERSION
    assert man["frozen_before_signal_inspection"] is True


def test_partition_assignment_is_deterministic():
    flights = {f"f{i}.ulg": {"sha256": None,
                             "metadata": {"aircraft_id": f"AC{i % 9}"}}
               for i in range(60)}
    a = freeze_partitions(flights, "e" * 64, "c", "t")
    b = freeze_partitions(flights, "e" * 64, "c", "t")
    assert a["assignments"] == b["assignments"]
    assert set(a["partition_counts"]) >= {"DEVELOPMENT", "CALIBRATION",
                                          "VALIDATION", "BLIND_TEST"}


def test_per_flight_fallback_is_recorded_as_a_weakness():
    flights = {"lonely.ulg": {"sha256": None, "metadata": {}}}
    man = freeze_partitions(flights, "f" * 64, "c", "t")
    assert man["weakest_grouping_tier"] == TIER_FLIGHT
    assert "NO group protection" in man["grouping_warning"]


def test_external_replication_is_opt_in_only():
    flights = {"a.ulg": {"metadata": {"aircraft_id": "AC1"}},
               "b.ulg": {"metadata": {"aircraft_id": "AC2"}}}
    man = freeze_partitions(flights, "0" * 64, "c", "t")
    assert man["partition_counts"]["EXTERNAL_REPLICATION"] == 0
    held = freeze_partitions(
        flights, "0" * 64, "c", "t",
        external_replication_groups=[f"{TIER_AIRCRAFT}:AC1"])
    assert held["partition_counts"]["EXTERNAL_REPLICATION"] == 1


# --- 20-22. certificate and repository hygiene --------------------------------

def build_full_lake(lake):
    staging = seed(os.path.join(lake.cache, "uav_sead", FAKE_SHA))
    manifest = build_manifest(staging)
    digest = aggregate_hash(manifest)
    placed = materialize(staging, lake.raw, "uav_sead", manifest, digest)
    from csia.data.snapshot import provenance_record, write_provenance
    inv = {"provider": "huggingface", "repo_id": "aykutkabaoglu/x",
           "repo_type": "dataset", "resolved_commit_sha": FAKE_SHA,
           "requested_revision": "main"}
    write_provenance(lake.manifests, "uav_sead", provenance_record(
        "uav_sead", inv, manifest, digest, placed["path"],
        "2026-08-03T00:00:00Z", "CC-BY-4.0", "10.57967/hf/7772"))
    pipe.atomic_write_json(lake.report(pipe.ENV_REPORT), {
        "checks": {"python_version": "3.13.12", "git_clean": True,
                   "dependency_versions": {"huggingface_hub": "1.26.0"}}})
    pipe.atomic_write_json(lake.report(pipe.PREFLIGHT_REPORT), {
        "repository_commit": "abc123", "huggingface_repo_id":
            "aykutkabaoglu/uav-flight-anomaly-dataset",
        "doi": "10.57967/hf/7772", "registry_license": "CC-BY-4.0",
        "hub_license": "cc-by-4.0", "license_match": True,
        "attribution_requirement": "cite the DOI"})
    return digest


def test_certificate_reports_identity_counts_and_partitions(lake):
    digest = build_full_lake(lake)
    args = pipe.build_parser().parse_args(["--stage", "mapping",
                                           "--data-root", lake.path])
    assert pipe.stage_mapping(lake, args)["ok"] is True
    args = pipe.build_parser().parse_args(["--stage", "partition",
                                           "--data-root", lake.path])
    assert pipe.stage_partition(lake, args)["ok"] is True
    args = pipe.build_parser().parse_args(["--stage", "certificate",
                                           "--data-root", lake.path])
    cert = pipe.stage_certificate(lake, args)

    assert cert["ok"] is True
    assert cert["aggregate_manifest_sha256"] == digest
    assert cert["pinned_commit"] == FAKE_SHA
    assert cert["dataset_identity"]["doi"] == "10.57967/hf/7772"
    assert cert["dataset_identity"]["license"] == "CC-BY-4.0"
    assert cert["ulg_file_count"] == 2
    assert cert["partitions"]["leakage_free"] is True
    assert cert["python_version"] == "3.13.12"
    assert os.path.isfile(lake.report(pipe.CERT_JSON))
    body = open(lake.report(pipe.CERT_MD)).read()
    assert "UAV-SEAD acquisition certificate" in body
    assert "csia_evaluation_started: false" in body


def test_certificate_always_says_evaluation_has_not_started(lake):
    build_full_lake(lake)
    for stage in ("mapping", "partition", "certificate"):
        args = pipe.build_parser().parse_args(["--stage", stage,
                                               "--data-root", lake.path])
        res = pipe.run_stage(stage, lake, args)
    assert res["csia_evaluation_started"] is False
    assert json.load(open(lake.report(pipe.CERT_JSON)))[
        "csia_evaluation_started"] is False


def test_certificate_refuses_before_the_prerequisite_stages(lake):
    build_full_lake(lake)
    args = pipe.build_parser().parse_args(["--stage", "certificate",
                                           "--data-root", lake.path])
    res = pipe.stage_certificate(lake, args)
    assert res["ok"] is False and "missing" in res["error"]


def test_no_pipeline_output_lands_inside_the_repository(lake):
    build_full_lake(lake)
    before = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                            capture_output=True, text=True).stdout
    for stage in ("mapping", "partition", "certificate"):
        args = pipe.build_parser().parse_args(["--stage", stage,
                                               "--data-root", lake.path])
        pipe.run_stage(stage, lake, args)
    after = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                           capture_output=True, text=True).stdout
    assert after == before, "pipeline dirtied the Git working tree"
    for name in (pipe.CERT_JSON, pipe.CERT_MD, pipe.MAPPING_REPORT):
        assert lake.report(name).startswith(lake.path)
        assert not lake.report(name).startswith(REPO_ROOT)


# --- runbook ------------------------------------------------------------------

RUNBOOK = os.path.join(REPO_ROOT, "docs", "runbooks",
                       "UAV_SEAD_MAC_ACQUISITION.md")


def test_runbook_exists_and_uses_portable_paths():
    body = open(RUNBOOK).read()
    assert MAC_DATA_ROOT in body
    # The volume path above is a fixed mount point and stays. The code folder
    # is addressed through $HOME instead of an absolute home directory, so no
    # operator's username is written into a file that goes out for review.
    assert "$HOME/swort/csia-trust-layer" in body
    assert "/Users/" not in body, "operator username leaked back into runbook"
    assert "--confirm-download UAV-SEAD" in body
    for placeholder in ("<RESOLVED_HF_COMMIT>", "<AGGREGATE_MANIFEST_HASH>"):
        assert placeholder in body
    for stage in ("environment", "preflight", "dry-run", "acquire", "verify",
                  "mapping", "partition", "certificate"):
        assert stage in body, stage


def test_runbook_documents_every_recovery_case():
    body = open(RUNBOOK).read().lower()
    for case in ("ssd disconnected", "sleep", "ctrl-c", "internet",
                 "rate limit", "partial cache", "upstream", "free space",
                 "mapping count", "dirty git", "hash verification",
                 "promotion", "duplicate snapshot", "environment missing",
                 "wrong interpreter"):
        assert case in body, case
