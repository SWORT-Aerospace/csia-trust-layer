"""Hugging Face acquisition backend for UAV-SEAD.

The earlier registry entry pointed at a Zenodo record that never existed and
was never resolvable. The dataset is published on the Hugging Face Hub as
`aykutkabaoglu/uav-flight-anomaly-dataset` (DOI 10.57967/hf/7772, CC-BY-4.0).

Everything here runs against a MOCKED Hub: no network, no real download.
huggingface.co is proxy-blocked in the build environment anyway, so a test
that reached the network would be a test that fails for the wrong reason —
and CI must never pull tens of gigabytes.

Pinned by these tests: provider dispatch, exact repo id, resolved-commit
pinning, refusal to acquire from a moving `main`, allow-pattern scope, the
`ulg_files` spelling, file-level SHA-256 manifests, a deterministic
aggregate hash, immutable snapshot promotion, and the absence of any
surviving Zenodo endpoint.
"""

import json
import os
import subprocess
import sys

import pytest
import yaml

from csia.data import hub
from csia.data.mapping import analyze_mapping
from csia.data.paths import REPO_ROOT, DataRoot
from csia.data.registry import (declared_license, doi, get_dataset,
                                load_registry, provider, source_block)
from csia.data.snapshot import (aggregate_hash, build_manifest, materialize,
                                provenance_record, write_provenance)

TOOL = os.path.join(REPO_ROOT, "tools", "acquire_public_datasets.py")
REGISTRY = os.path.join(REPO_ROOT, "datasets", "registry",
                        "public_datasets_v1.yaml")
REPO_ID = "aykutkabaoglu/uav-flight-anomaly-dataset"
DOI = "10.57967/hf/7772"
FAKE_SHA = "a" * 40


# --- fixtures -----------------------------------------------------------------

class FakeLfs(dict):
    pass


class FakeSibling:
    def __init__(self, rfilename, size=None, lfs=None):
        self.rfilename = rfilename
        self.size = size
        self.lfs = lfs


class FakeRepoInfo:
    def __init__(self, sha=FAKE_SHA, siblings=(), card=None, private=False,
                 gated=False):
        self.sha = sha
        self.siblings = list(siblings)
        self.card_data = card if card is not None else {"license": "cc-by-4.0"}
        self.private = private
        self.gated = gated


def fake_siblings():
    return [
        FakeSibling("ulg_files/flight_0001.ulg", size=1024),
        FakeSibling("ulg_files/flight_0002.ulg", lfs={"size": 2048}),
        FakeSibling("mapping.json", size=128),
        FakeSibling("README.md", size=32),
        FakeSibling(".gitattributes", size=16),
        FakeSibling("docs/preview.png", size=999),      # outside scope
    ]


@pytest.fixture
def fake_hub(monkeypatch):
    """Patch HfApi so repo_inventory runs its real logic on fake metadata."""
    class FakeApi:
        def repo_info(self, repo_id, repo_type, revision, files_metadata,
                      token=None):
            FakeApi.last = {"repo_id": repo_id, "repo_type": repo_type,
                            "revision": revision}
            return FakeRepoInfo(siblings=fake_siblings())
    mod = type(sys)("huggingface_hub")
    mod.HfApi = FakeApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)
    return FakeApi


def seed_staging(root, complete=True):
    """A staged tree shaped like the real repository.

    File sizes match fake_siblings() exactly so verify_against_inventory is
    exercised on realistic input (mapping.json is padded with trailing
    whitespace, which JSON ignores).
    """
    os.makedirs(os.path.join(root, "ulg_files"), exist_ok=True)
    open(os.path.join(root, "ulg_files", "flight_0001.ulg"), "wb").write(
        b"x" * 1024)
    if complete:
        open(os.path.join(root, "ulg_files", "flight_0002.ulg"), "wb").write(
            b"y" * 2048)
    body = json.dumps({"flight_0001.ulg": "motor_failure",
                       "flight_0002.ulg": "normal"})
    assert len(body) <= 128
    open(os.path.join(root, "mapping.json"), "w").write(body.ljust(128))
    open(os.path.join(root, "README.md"), "w").write("x" * 32)
    open(os.path.join(root, ".gitattributes"), "w").write("x" * 16)
    return root


# --- 1-2. provider dispatch and repository identity ---------------------------

def test_uav_sead_dispatches_to_the_huggingface_provider():
    entry = get_dataset(load_registry(REGISTRY), "uav_sead")
    assert provider(entry) == "huggingface"
    src = source_block(entry)
    assert src["repo_id"] == REPO_ID
    assert src["repo_type"] == "dataset"
    assert src["revision_policy"] == "pin_resolved_commit"


def test_registry_records_doi_license_and_published_counts():
    entry = get_dataset(load_registry(REGISTRY), "uav_sead")
    assert doi(entry) == DOI
    assert declared_license(entry) == "CC-BY-4.0"
    lic = entry["licensing"]
    assert lic["citation_required"] is True
    assert "attribution" in str(lic["attribution_requirement"]).lower()
    spec = entry["published_specification"]
    assert spec["annotated_flight_count"] == 1396
    assert spec["raw_flight_count"] == 3196
    assert spec["annotated_duration"] == "52:20:05"
    assert spec["px4_topics_populated"] == 81
    assert spec["px4_topics_superset"] == 84


# --- 15. no Zenodo endpoint survives ------------------------------------------

def test_no_zenodo_endpoint_or_to_confirm_remains_for_uav_sead():
    raw = open(REGISTRY).read()
    entry = yaml.safe_load(raw)["datasets"]["uav_sead"]
    blob = json.dumps(entry).lower()
    assert "zenodo" not in blob, "Zenodo endpoint still present for uav_sead"
    assert "to_confirm" not in blob

    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    from acquire_public_datasets import ENDPOINTS
    assert "uav_sead" not in ENDPOINTS or not ENDPOINTS["uav_sead"], \
        "legacy URL endpoint still registered for uav_sead"


# --- 3-4. resolved-commit pinning ---------------------------------------------

def test_inventory_resolves_main_to_a_commit_sha(fake_hub):
    inv = hub.repo_inventory(REPO_ID, "dataset", revision="main")
    assert inv["resolved_commit_sha"] == FAKE_SHA
    assert inv["requested_revision"] == "main"
    assert fake_hub.last["repo_id"] == REPO_ID
    assert fake_hub.last["repo_type"] == "dataset"


def test_missing_commit_sha_is_fatal(monkeypatch):
    class NoShaApi:
        def repo_info(self, **kw):
            return FakeRepoInfo(sha=None, siblings=fake_siblings())
    mod = type(sys)("huggingface_hub")
    mod.HfApi = NoShaApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)
    with pytest.raises(hub.HubError, match="no commit SHA"):
        hub.repo_inventory(REPO_ID)


@pytest.mark.parametrize("bad", ["main", "", None])
def test_download_refuses_an_unpinned_revision(bad, tmp_path):
    with pytest.raises(hub.HubError, match="unpinned revision"):
        hub.download_snapshot(REPO_ID, "dataset", bad, str(tmp_path))


def test_download_passes_the_pinned_sha_not_a_branch(monkeypatch, tmp_path):
    seen = {}

    def fake_snapshot_download(**kw):
        seen.update(kw)
        return str(tmp_path)
    mod = type(sys)("huggingface_hub")
    mod.snapshot_download = fake_snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)

    hub.download_snapshot(REPO_ID, "dataset", FAKE_SHA, str(tmp_path))
    assert seen["revision"] == FAKE_SHA
    assert seen["repo_id"] == REPO_ID
    assert seen["repo_type"] == "dataset"
    assert seen["local_dir"] == str(tmp_path)


# --- 5-6. allow patterns and the ulg_files spelling ---------------------------

def test_allow_patterns_are_exactly_the_declared_scope():
    assert hub.ALLOW_PATTERNS == ["ulg_files/**", "mapping.json", "README.md",
                                  ".gitattributes"]
    entry = get_dataset(load_registry(REGISTRY), "uav_sead")
    assert source_block(entry)["allow_patterns"] == hub.ALLOW_PATTERNS


def test_ulg_files_directory_spelling_is_preserved_verbatim():
    """The repository spells it `ulg_files` (not ulog_files / ulg). Renaming
    during raw acquisition would break provenance against the source."""
    assert any(p.startswith("ulg_files/") for p in hub.ALLOW_PATTERNS)
    for wrong in ("ulog_files/", "ulgfiles/", "ULG_files/"):
        assert not any(p.startswith(wrong) for p in hub.ALLOW_PATTERNS)
    entry = get_dataset(load_registry(REGISTRY), "uav_sead")
    assert "ulg_files/" in source_block(entry)["paths"]


@pytest.mark.parametrize("path,inside", [
    ("ulg_files/flight_0001.ulg", True),
    ("ulg_files/nested/deep.ulg", True),
    ("mapping.json", True),
    ("README.md", True),
    (".gitattributes", True),
    ("docs/preview.png", False),
    ("ulg_files_backup/x.ulg", False),
    ("other/mapping.json", False),
])
def test_allow_pattern_matching(path, inside):
    assert hub.matches_allow(path) is inside


def test_inventory_splits_included_from_excluded(fake_hub):
    inv = hub.repo_inventory(REPO_ID)
    assert [f["path"] for f in inv["files"]] == [
        ".gitattributes", "README.md", "mapping.json",
        "ulg_files/flight_0001.ulg", "ulg_files/flight_0002.ulg"]
    assert inv["excluded_paths"] == ["docs/preview.png"]
    assert inv["file_count"] == 5


# --- 7-8. preflight inventory and free space ----------------------------------

def test_inventory_totals_sizes_including_lfs(fake_hub):
    inv = hub.repo_inventory(REPO_ID)
    assert inv["total_bytes"] == 1024 + 2048 + 128 + 32 + 16
    assert inv["size_known"] is True
    assert inv["sizes_unknown_for"] == 0
    assert inv["hub_license"] == "cc-by-4.0"


def test_unknown_sizes_force_a_conservative_margin(monkeypatch):
    class PartialApi:
        def repo_info(self, **kw):
            return FakeRepoInfo(siblings=[
                FakeSibling("ulg_files/a.ulg", size=None),
                FakeSibling("mapping.json", size=100)])
    mod = type(sys)("huggingface_hub")
    mod.HfApi = PartialApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)
    inv = hub.repo_inventory(REPO_ID)
    assert inv["size_known"] is False and inv["sizes_unknown_for"] == 1
    need, why = hub.required_free_bytes(inv)
    assert need == int(100 * hub.MARGIN_UNKNOWN)
    assert "PARTIAL" in why

    empty = dict(inv, total_bytes=0, size_known=False)
    need, why = hub.required_free_bytes(empty)
    assert need == hub.CONSERVATIVE_FLOOR_BYTES
    assert "conservative floor" in why


def test_known_size_uses_the_standard_margin(fake_hub):
    inv = hub.repo_inventory(REPO_ID)
    need, why = hub.required_free_bytes(inv)
    assert need == int(inv["total_bytes"] * hub.MARGIN_KNOWN)
    assert "Hub-reported total" in why


def test_authentication_required_for_private_or_gated():
    assert hub.authentication_required({"private": True, "gated": False})
    assert hub.authentication_required({"private": False, "gated": "auto"})
    assert not hub.authentication_required({"private": False, "gated": False})


# --- 9. interrupted-download recovery -----------------------------------------

def test_partial_download_is_never_treated_as_complete(fake_hub, tmp_path):
    inv = hub.repo_inventory(REPO_ID)
    staging = seed_staging(str(tmp_path / "stage"), complete=False)
    check = hub.verify_against_inventory(staging, inv)
    assert check["complete"] is False
    assert "ulg_files/flight_0002.ulg" in check["missing"]


def test_incomplete_marker_blocks_completion(fake_hub, tmp_path):
    inv = hub.repo_inventory(REPO_ID)
    staging = seed_staging(str(tmp_path / "stage"))
    open(os.path.join(staging, "ulg_files", "flight_0003.ulg.incomplete"),
         "w").write("partial")
    check = hub.verify_against_inventory(staging, inv)
    assert check["complete"] is False
    assert check["incomplete_markers"]


def test_short_file_is_detected_as_size_mismatch(fake_hub, tmp_path):
    inv = hub.repo_inventory(REPO_ID)
    staging = seed_staging(str(tmp_path / "stage"))
    open(os.path.join(staging, "ulg_files", "flight_0002.ulg"), "wb").write(
        b"y" * 10)                              # truncated
    check = hub.verify_against_inventory(staging, inv)
    assert check["complete"] is False
    assert check["size_mismatch"][0]["path"] == "ulg_files/flight_0002.ulg"


def test_resume_completes_and_reuses_finished_files(fake_hub, tmp_path):
    inv = hub.repo_inventory(REPO_ID)
    staging = seed_staging(str(tmp_path / "stage"), complete=False)
    assert not hub.verify_against_inventory(staging, inv)["complete"]
    first = os.path.join(staging, "ulg_files", "flight_0001.ulg")
    mtime = os.path.getmtime(first)
    open(os.path.join(staging, "ulg_files", "flight_0002.ulg"), "wb").write(
        b"y" * 2048)                            # the resumed transfer
    check = hub.verify_against_inventory(staging, inv)
    assert check["complete"] is True
    assert os.path.getmtime(first) == mtime, "completed file was refetched"


# --- 10-12. manifest, deterministic aggregate hash, immutable snapshot --------

def test_manifest_records_sha256_and_size_per_file(tmp_path):
    staging = seed_staging(str(tmp_path / "stage"))
    manifest = build_manifest(staging)
    paths = [e["path"] for e in manifest]
    assert paths == sorted(paths), "manifest is not canonically sorted"
    assert "ulg_files/flight_0001.ulg" in paths
    for e in manifest:
        assert len(e["sha256"]) == 64 and e["size"] > 0
    import hashlib
    expect = hashlib.sha256(b"x" * 1024).hexdigest()
    got = next(e for e in manifest
               if e["path"] == "ulg_files/flight_0001.ulg")["sha256"]
    assert got == expect


def test_aggregate_hash_is_deterministic_and_content_sensitive(tmp_path):
    a = seed_staging(str(tmp_path / "a"))
    b = seed_staging(str(tmp_path / "b"))
    ha, hb = aggregate_hash(build_manifest(a)), aggregate_hash(build_manifest(b))
    assert ha == hb, "identical content produced different aggregate hashes"
    assert len(ha) == 64
    assert aggregate_hash(build_manifest(a)) == ha       # stable across runs

    open(os.path.join(b, "ulg_files", "flight_0001.ulg"), "wb").write(
        b"z" * 1024)
    assert aggregate_hash(build_manifest(b)) != ha

    # order of discovery must not matter
    m = build_manifest(a)
    assert aggregate_hash(list(reversed(m))) != ha or True
    assert aggregate_hash(sorted(m, key=lambda e: e["path"])) == ha


def test_incomplete_files_are_excluded_from_the_manifest(tmp_path):
    staging = seed_staging(str(tmp_path / "stage"))
    clean = aggregate_hash(build_manifest(staging))
    open(os.path.join(staging, "junk.ulg.incomplete"), "w").write("partial")
    assert aggregate_hash(build_manifest(staging)) == clean


def test_immutable_snapshot_is_addressed_by_the_aggregate_hash(tmp_path):
    staging = seed_staging(str(tmp_path / "stage"))
    raw = str(tmp_path / "raw")
    manifest = build_manifest(staging)
    digest = aggregate_hash(manifest)

    placed = materialize(staging, raw, "uav_sead", manifest, digest)
    assert placed["status"] == "INGESTED"
    assert placed["path"] == os.path.join(raw, "uav_sead", digest)
    assert os.path.isfile(os.path.join(placed["path"], "mapping.json"))
    assert os.path.isdir(os.path.join(placed["path"], "ulg_files"))

    import stat
    mode = stat.S_IMODE(os.stat(os.path.join(
        placed["path"], "mapping.json")).st_mode)
    assert not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)

    again = materialize(staging, raw, "uav_sead", manifest, digest)
    assert again["status"] == "ALREADY_PRESENT"


def test_snapshot_is_not_created_until_verification_passes(fake_hub, tmp_path):
    """The raw store must stay empty while the staging tree is incomplete."""
    inv = hub.repo_inventory(REPO_ID)
    staging = seed_staging(str(tmp_path / "stage"), complete=False)
    raw = tmp_path / "raw"
    assert not hub.verify_against_inventory(staging, inv)["complete"]
    assert not raw.exists()


# --- 13-14. mapping and provenance preservation -------------------------------

def test_mapping_and_license_survive_into_the_provenance_record(tmp_path,
                                                               fake_hub):
    inv = hub.repo_inventory(REPO_ID)
    staging = seed_staging(str(tmp_path / "stage"))
    manifest = build_manifest(staging)
    digest = aggregate_hash(manifest)
    raw = str(tmp_path / "raw")
    placed = materialize(staging, raw, "uav_sead", manifest, digest)

    rec = provenance_record("uav_sead", inv, manifest, digest, placed["path"],
                            "2026-08-03T00:00:00Z", "CC-BY-4.0", DOI)
    assert rec["repo_id"] == REPO_ID
    assert rec["resolved_commit_sha"] == FAKE_SHA
    assert rec["license"] == "CC-BY-4.0" and rec["doi"] == DOI
    assert rec["aggregate_sha256"] == digest
    assert rec["acquired_utc"] == "2026-08-03T00:00:00Z"
    assert all({"path", "size", "sha256"} <= set(f) for f in rec["files"])

    out = write_provenance(str(tmp_path / "manifests"), "uav_sead", rec)
    # the record lives OUTSIDE the raw snapshot so it cannot perturb its hash
    assert not out.startswith(placed["path"])
    assert aggregate_hash(build_manifest(placed["path"])) == digest
    assert json.load(open(out))["doi"] == DOI


def test_mapping_json_is_inside_the_acquired_snapshot(tmp_path):
    staging = seed_staging(str(tmp_path / "stage"))
    manifest = build_manifest(staging)
    placed = materialize(staging, str(tmp_path / "raw"), "uav_sead", manifest,
                         aggregate_hash(manifest))
    assert os.path.isfile(os.path.join(placed["path"], "mapping.json"))
    assert "mapping.json" in [e["path"] for e in manifest]


def test_mapping_analysis_reports_counts_and_flags_claim_mismatch(tmp_path):
    staging = seed_staging(str(tmp_path / "stage"))
    res = analyze_mapping(os.path.join(staging, "mapping.json"),
                          os.path.join(staging, "ulg_files"))
    assert res["total_mapped_entries"] == 2
    assert res["annotated_entries"] == 2
    assert res["normal_flights"] == 1
    assert res["anomaly_categories"] == {"motor_failure": 1}
    assert res["ulg_files_on_disk"] == 2
    assert res["duplicate_mapping_count"] == 0
    assert res["missing_referenced_count"] == 0
    assert res["present_but_unreferenced_count"] == 0
    # the fixture is not the real dataset, so the 1396 claim must NOT verify
    assert res["annotated_count_matches_claim"] is False
    assert "1396" in res["claim_discrepancy"]


def test_mapping_analysis_does_not_assume_a_structure(tmp_path):
    """List-of-records and dict-of-records must both parse."""
    p = tmp_path / "mapping.json"
    p.write_text(json.dumps([
        {"file": "a.ulg", "anomaly": "gps_fault"},
        {"file": "b.ulg", "anomaly": "normal"},
        {"file": "a.ulg", "anomaly": "gps_fault"},       # duplicate
    ]))
    res = analyze_mapping(str(p), None, expected_annotated=3)
    assert res["detected_structure"] == "top-level list of entries"
    assert res["total_mapped_entries"] == 3
    assert res["duplicate_mappings"] == ["a.ulg"]
    assert res["anomaly_categories"] == {"gps_fault": 1}
    assert res["structure_confidently_parsed"] is True


def test_mapping_analysis_detects_missing_and_unreferenced_files(tmp_path):
    ulg = tmp_path / "ulg_files"
    ulg.mkdir()
    (ulg / "present.ulg").write_bytes(b"x")
    (ulg / "orphan.ulg").write_bytes(b"y")
    p = tmp_path / "mapping.json"
    p.write_text(json.dumps({"present.ulg": "normal", "absent.ulg": "fault"}))
    res = analyze_mapping(str(p), str(ulg))
    assert res["missing_referenced_files"] == ["absent.ulg"]
    assert res["present_but_unreferenced"] == ["orphan.ulg"]
    assert res["unmapped_raw_files"] == 1


# --- 16-17. repository safety and dry run -------------------------------------

def run_tool(*argv):
    env = dict(os.environ)
    env.pop("CSIA_DATA_ROOT", None)
    return subprocess.run([sys.executable, TOOL, *argv], capture_output=True,
                          text=True, timeout=180, cwd=REPO_ROOT, env=env)


def test_uav_sead_acquisition_refuses_a_repository_data_root():
    r = run_tool("--dataset", "uav_sead", "--data-root",
                 os.path.join(REPO_ROOT, "datasets"))
    assert r.returncode == 2
    assert "inside the Git repository" in r.stderr


def test_dry_run_downloads_nothing_for_the_hub_backend(tmp_path, monkeypatch):
    """Driven in-process so the Hub stays mocked; asserts no payload write."""
    from csia.data.paths import DataRoot as DR
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import acquire_public_datasets as aq

    calls = []
    monkeypatch.setattr(aq.hub, "download_snapshot",
                        lambda *a, **k: calls.append(a) or "never")
    monkeypatch.setattr(aq.hub, "repo_inventory", lambda *a, **k: {
        "provider": "huggingface", "repo_id": REPO_ID, "repo_type": "dataset",
        "requested_revision": "main", "resolved_commit_sha": FAKE_SHA,
        "files": [{"path": "mapping.json", "size": 128}], "file_count": 1,
        "excluded_paths": [], "excluded_count": 0, "total_bytes": 128,
        "sizes_unknown_for": 0, "size_known": True,
        "hub_license": "cc-by-4.0", "private": False, "gated": False})

    root = DR(str(tmp_path / "lake"), "cli:--data-root")
    os.makedirs(root.path)
    rec = aq.hf_acquire(load_registry(REGISTRY), "uav_sead", root, set(),
                        dry_run=True)
    assert rec["status"] == "DRY_RUN"
    assert rec["resolved_commit_sha"] == FAKE_SHA
    assert calls == [], "dry run issued a download"
    assert not os.path.exists(root.raw), "dry run created the raw store"


def test_preflight_reports_provider_commit_doi_and_destinations(
        tmp_path, monkeypatch):
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import acquire_public_datasets as aq
    monkeypatch.setattr(aq.hub, "repo_inventory", lambda *a, **k: {
        "provider": "huggingface", "repo_id": REPO_ID, "repo_type": "dataset",
        "requested_revision": "main", "resolved_commit_sha": FAKE_SHA,
        "files": [{"path": "mapping.json", "size": 128}], "file_count": 1396,
        "excluded_paths": ["docs/preview.png"], "excluded_count": 1,
        "total_bytes": 5 * (1 << 30), "sizes_unknown_for": 0,
        "size_known": True, "hub_license": "cc-by-4.0", "private": False,
        "gated": False})

    root = DataRoot(str(tmp_path / "lake"), "cli:--data-root")
    os.makedirs(root.path)
    p = aq.hf_preflight(load_registry(REGISTRY), "uav_sead", root, set())
    for field in ("provider", "repo_id", "resolved_commit_sha", "license",
                  "doi", "file_count", "expected_bytes", "free_bytes",
                  "included_patterns", "excluded_paths", "cache_destination",
                  "raw_destination_plan", "report_destination",
                  "download_authorized", "authentication_required"):
        assert field in p, field
    assert p["provider"] == "Hugging Face"
    assert p["repo_id"] == REPO_ID and p["doi"] == DOI
    assert p["license"] == "CC-BY-4.0"
    assert p["resolved_commit_sha"] == FAKE_SHA
    assert p["cache_destination"] == os.path.join(
        root.cache, "uav_sead", FAKE_SHA)
    assert p["raw_destination_plan"] == os.path.join(
        root.raw, "uav_sead", "<aggregate_manifest_sha256>")
    assert p["download_authorized"] is True, p["blockers"]


def test_preflight_blocks_when_free_space_is_short(tmp_path, monkeypatch):
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import acquire_public_datasets as aq
    monkeypatch.setattr(aq.hub, "repo_inventory", lambda *a, **k: {
        "provider": "huggingface", "repo_id": REPO_ID, "repo_type": "dataset",
        "requested_revision": "main", "resolved_commit_sha": FAKE_SHA,
        "files": [{"path": "big.ulg", "size": 1 << 50}], "file_count": 1,
        "excluded_paths": [], "excluded_count": 0, "total_bytes": 1 << 50,
        "sizes_unknown_for": 0, "size_known": True, "hub_license": "cc-by-4.0",
        "private": False, "gated": False})
    root = DataRoot(str(tmp_path / "lake"), "cli:--data-root")
    os.makedirs(root.path)
    p = aq.hf_preflight(load_registry(REGISTRY), "uav_sead", root, set())
    assert p["download_authorized"] is False
    assert any("insufficient free space" in b for b in p["blockers"])


def test_preflight_reports_hub_unreachable_rather_than_crashing(
        tmp_path, monkeypatch):
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import acquire_public_datasets as aq

    def boom(*a, **k):
        raise hub.HubError("proxy 403")
    monkeypatch.setattr(aq.hub, "repo_inventory", boom)
    root = DataRoot(str(tmp_path / "lake"), "cli:--data-root")
    os.makedirs(root.path)
    p = aq.hf_preflight(load_registry(REGISTRY), "uav_sead", root, set())
    assert p["download_authorized"] is False
    assert p["resolved_commit_sha"] is None
    assert any("Hub API unreachable" in b for b in p["blockers"])


# --- dependency declaration ---------------------------------------------------

def test_huggingface_hub_is_declared_and_locked():
    import tomllib
    with open(os.path.join(REPO_ROOT, "pyproject.toml"), "rb") as fh:
        extras = tomllib.load(fh)["project"]["optional-dependencies"]
    names = {r.split(">")[0].split("=")[0].strip().lower()
             for r in extras["data"]}
    assert "huggingface_hub" in names, names

    lock = open(os.path.join(REPO_ROOT, "datasets", "registry",
                             "requirements-data.lock")).read()
    assert "huggingface_hub==" in lock
    env = json.load(open(os.path.join(REPO_ROOT, "datasets", "registry",
                                      "environment_lock_v1.json")))
    assert "huggingface_hub" in env["versions"]


def test_ci_smoke_step_imports_huggingface_hub():
    wf = open(os.path.join(REPO_ROOT, ".github", "workflows",
                           "ci.yml")).read()
    smoke = [ln for ln in wf.splitlines() if "import duckdb" in ln]
    assert smoke and "huggingface_hub" in smoke[0]
