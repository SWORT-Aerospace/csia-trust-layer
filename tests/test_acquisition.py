"""Public-dataset acquisition path: registry, data root, safety, CLI modes.

Regressions pinned here, all observed on commit 320a5b4:

  * `--status-only` printed "acquisition: 0/0 complete" for a registry
    holding 7 datasets — the tool never read the registry at all (the
    REGISTRY constant was defined and never used), and `--status-only`
    skipped the only loop that populated the report;
  * the same run overwrote the TRACKED report
    datasets/reports/acquisition_status_v1.json with an empty dataset map,
    dirtying the working tree;
  * storage was repository-local, with no --data-root and no CSIA_DATA_ROOT;
  * PyArrow was missing from the `data` extra.

No test here touches the network: acquisition is exercised via --dry-run and
--preflight only, and the registry/data-root logic is pure.
"""

import json
import os
import subprocess
import sys
import tomllib

import pytest
import yaml

from csia.data.paths import (REPO_ROOT, DataRoot, DataRootError,
                             check_free_space, check_writable,
                             require_external_data_root, resolve_data_root)
from csia.data.registry import (RegistryError, UnknownDatasetError,
                                acknowledgement_required, dataset_ids,
                                get_dataset, load_registry, select_datasets)

TOOL = os.path.join(REPO_ROOT, "tools", "acquire_public_datasets.py")
REGISTRY = os.path.join(REPO_ROOT, "datasets", "registry",
                        "public_datasets_v1.yaml")
EXPECTED_IDS = ["alfa", "blackbird", "euroc_mav", "insane",
                "px4_flightreview_v1", "tum_vi", "uav_sead"]


def run_tool(*argv, env=None, cwd=None):
    e = dict(os.environ)
    e.pop("CSIA_DATA_ROOT", None)
    e.update(env or {})
    return subprocess.run([sys.executable, TOOL, *argv], capture_output=True,
                          text=True, timeout=180, cwd=cwd or REPO_ROOT, env=e)


# --- 1-2. dictionary-form registry, exactly 7 entries -------------------------

def test_registry_is_parsed_as_a_mapping_keyed_by_dataset_id():
    reg = load_registry(REGISTRY)
    assert isinstance(reg["datasets"], dict)
    assert reg["registry_version"] == "1.0.0"
    for key, entry in reg["datasets"].items():
        assert isinstance(key, str) and isinstance(entry, dict), key


def test_registry_declares_exactly_seven_datasets():
    assert dataset_ids(load_registry(REGISTRY)) == EXPECTED_IDS


# --- 3-5. id recognition and fatal registries ---------------------------------

def test_uav_sead_is_recognized():
    reg = load_registry(REGISTRY)
    entry = get_dataset(reg, "uav_sead")
    assert entry["title"].startswith("UAV-SEAD")
    assert select_datasets(reg, ["uav_sead"]) == ["uav_sead"]


def test_unknown_dataset_is_rejected_and_lists_valid_ids():
    reg = load_registry(REGISTRY)
    with pytest.raises(UnknownDatasetError) as exc:
        get_dataset(reg, "uav-sead")            # hyphen, not underscore
    for known in EXPECTED_IDS:
        assert known in str(exc.value)
    with pytest.raises(UnknownDatasetError):
        select_datasets(reg, ["uav_sead", "nope"])


@pytest.mark.parametrize("body,reason", [
    ('registry_version: "1"\ndatasets: {}\n', "zero"),
    ('registry_version: "1"\n', "no 'datasets'"),
    ('registry_version: "1"\ndatasets: [uav_sead]\n', "mapping"),
])
def test_zero_entry_or_malformed_registry_is_fatal(tmp_path, body, reason):
    p = tmp_path / "reg.yaml"
    p.write_text(body)
    with pytest.raises(RegistryError) as exc:
        load_registry(str(p))
    assert reason in str(exc.value)


def test_zero_entry_registry_exits_nonzero_rather_than_printing_0_of_0(
        tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text('registry_version: "1"\ndatasets: {}\n')
    r = run_tool("--status-only", "--registry", str(p))
    assert r.returncode == 2, r.stdout
    assert "0/0 complete" not in r.stdout
    assert "zero datasets" in r.stderr


# --- 6-9. data-root precedence and destinations -------------------------------

def test_cli_data_root_wins_over_environment(tmp_path):
    cli, env = str(tmp_path / "cli"), str(tmp_path / "env")
    root = resolve_data_root(cli, env={"CSIA_DATA_ROOT": env})
    assert root.path == os.path.abspath(cli)
    assert root.source == "cli:--data-root"


def test_environment_variable_is_used_when_no_cli_value(tmp_path):
    env = str(tmp_path / "env")
    root = resolve_data_root(None, env={"CSIA_DATA_ROOT": env})
    assert root.path == os.path.abspath(env)
    assert root.source == "env:CSIA_DATA_ROOT"
    # an empty/whitespace value must not shadow the fallback
    assert resolve_data_root(None, env={"CSIA_DATA_ROOT": "  "}).is_repo_local


def test_repository_fallback_is_last_and_is_marked_repo_local():
    root = resolve_data_root(None, env={})
    assert root.is_repo_local
    assert root.source == "repository-fixture-fallback"
    # must NOT be <repo>/datasets: that tree holds tracked fixtures
    assert root.path != os.path.join(REPO_ROOT, "datasets")


def test_external_ssd_destinations_are_built_under_the_data_root():
    root = DataRoot("/Volumes/CSIA_DATA/CSIA_DATA_LAKE", "cli:--data-root")
    assert not root.is_repo_local
    base = "/Volumes/CSIA_DATA/CSIA_DATA_LAKE"
    assert root.raw_dir("uav_sead") == f"{base}/raw/uav_sead"
    assert root.reports == f"{base}/reports"
    assert root.manifests == f"{base}/manifests"
    assert root.normalized == f"{base}/normalized"
    assert root.cache == f"{base}/cache"
    assert root.exports == f"{base}/exports"


# --- 10. acquired payload may never land inside the Git repository ------------

def test_repo_local_data_root_is_refused_for_acquisition():
    root = resolve_data_root(None, env={})
    assert root.is_repo_local
    with pytest.raises(DataRootError) as exc:
        require_external_data_root(root)
    assert "inside the Git repository" in str(exc.value)
    assert "CSIA_DATA_ROOT" in str(exc.value)


def test_acquire_run_refuses_a_repository_data_root(tmp_path):
    r = run_tool("--dataset", "uav_sead", "--data-root",
                 os.path.join(REPO_ROOT, "datasets"))
    assert r.returncode == 2, r.stdout
    assert "inside the Git repository" in r.stderr


# --- 11. status-only must not touch tracked files -----------------------------

def test_status_only_recognizes_all_seven_and_leaves_the_repo_clean(tmp_path):
    tracked = os.path.join(REPO_ROOT, "datasets", "reports",
                           "acquisition_status_v1.json")
    before = open(tracked, "rb").read()
    dirty_before = subprocess.run(["git", "status", "--porcelain"],
                                  cwd=REPO_ROOT, capture_output=True,
                                  text=True).stdout

    r = run_tool("--status-only", "--data-root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "acquisition: 0/0 complete" not in r.stdout
    assert "0/7 complete" in r.stdout
    for name in EXPECTED_IDS:
        assert name in r.stdout

    assert open(tracked, "rb").read() == before, \
        "--status-only rewrote the committed report fixture"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                          capture_output=True, text=True).stdout \
        == dirty_before, "--status-only dirtied the working tree"


def test_status_only_works_with_the_repository_fallback_root():
    """Read-only mode tolerates the fallback, and still writes nothing
    tracked (the fallback root is gitignored)."""
    dirty_before = subprocess.run(["git", "status", "--porcelain"],
                                  cwd=REPO_ROOT, capture_output=True,
                                  text=True).stdout
    r = run_tool("--status-only")
    assert r.returncode == 0, r.stderr
    assert "0/7 complete" in r.stdout
    assert subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                          capture_output=True, text=True).stdout \
        == dirty_before


# --- 12. dry run downloads nothing --------------------------------------------

def test_dry_run_downloads_nothing_and_writes_no_payload(tmp_path):
    root = tmp_path / "lake"
    root.mkdir()
    r = run_tool("--dataset", "uav_sead", "--dry-run", "--data-root",
                 str(root))
    assert r.returncode == 0, r.stderr
    report = json.load(open(root / "reports" / "acquisition_status_v1.json"))
    entry = report["datasets"]["uav_sead"]
    assert entry["status"] == "DRY_RUN"
    assert entry["attempts"] == [] and entry["files"] == []
    assert report["mode"] == "dry-run"
    raw = root / "raw"
    assert not raw.exists() or not any(raw.rglob("*")), \
        "dry run wrote payload into the raw store"


# --- 13. preflight ------------------------------------------------------------

REQUIRED_PREFLIGHT_FIELDS = [
    "data_root", "free_bytes", "dataset_id", "title", "official_source",
    "license", "commercial_use", "expected_inventory", "raw_destination",
    "manifest_destination", "report_destination", "download_authorized",
    "license_acknowledgment_required",
]


def test_preflight_reports_every_required_field(tmp_path):
    root = tmp_path / "lake"
    root.mkdir()
    r = run_tool("--dataset", "uav_sead", "--preflight", "--json",
                 "--data-root", str(root))
    p = json.loads(r.stdout)[0]
    for field in REQUIRED_PREFLIGHT_FIELDS:
        assert field in p, field
    assert p["dataset_id"] == "uav_sead"
    assert p["title"].startswith("UAV-SEAD")
    assert p["raw_destination"] == str(root / "raw" / "uav_sead")
    assert p["report_destination"] == str(
        root / "reports" / "acquisition_status_v1.json")
    assert p["free_bytes"] > 0
    # endpoint is still TO_CONFIRM upstream, so downloading is NOT authorized
    assert p["download_authorized"] is False
    assert any("TO_CONFIRM" in b for b in p["blockers"])


def test_preflight_human_output_names_the_required_fields(tmp_path):
    root = tmp_path / "lake"
    root.mkdir()
    r = run_tool("--dataset", "uav_sead", "--preflight", "--data-root",
                 str(root))
    for label in ("data root", "free disk space", "license",
                  "commercial use", "raw destination", "manifest destination",
                  "report destination", "DOWNLOAD AUTHORIZED",
                  "license ack required", "expected inventory",
                  "official source"):
        assert label in r.stdout, label


def test_preflight_writes_nothing_at_all(tmp_path):
    root = tmp_path / "lake"
    root.mkdir()
    run_tool("--dataset", "uav_sead", "--preflight", "--data-root", str(root))
    assert list(root.iterdir()) == [], "preflight created files"


def test_restricted_license_blocks_until_acknowledged(tmp_path):
    root = tmp_path / "lake"
    root.mkdir()
    reg = load_registry(REGISTRY)
    assert acknowledgement_required(get_dataset(reg, "insane")) is True
    assert acknowledgement_required(get_dataset(reg, "uav_sead")) is False

    r = run_tool("--dataset", "insane", "--dry-run", "--data-root", str(root))
    rep = json.load(open(root / "reports" / "acquisition_status_v1.json"))
    assert rep["datasets"]["insane"]["status"] == "LICENSE_ACK_REQUIRED"

    r = run_tool("--dataset", "insane", "--dry-run", "--acknowledge-license",
                 "insane", "--data-root", str(root))
    assert r.returncode == 0, r.stderr
    rep = json.load(open(root / "reports" / "acquisition_status_v1.json"))
    assert rep["datasets"]["insane"]["status"] == "DRY_RUN"


# --- 14-15. dependency declaration --------------------------------------------

def test_pyarrow_is_declared_in_the_data_extra():
    with open(os.path.join(REPO_ROOT, "pyproject.toml"), "rb") as fh:
        extras = tomllib.load(fh)["project"]["optional-dependencies"]
    names = {r.split(">")[0].split("=")[0].split("[")[0].strip().lower()
             for r in extras["data"]}
    assert {"pyarrow", "polars", "duckdb", "pyyaml"} <= names, names


def test_every_declared_data_dependency_imports():
    """The exact smoke set the CI workflow runs, asserted from inside the
    suite so a clean `pip install -e '.[data,dev,logs,mavlink]'` is proven
    sufficient without a separate environment."""
    import importlib
    for mod in ("duckdb", "jsonschema", "polars", "pyarrow", "pyulog",
                "yaml"):
        assert importlib.import_module(mod) is not None, mod


def test_ci_smoke_step_covers_every_data_dependency():
    wf = open(os.path.join(REPO_ROOT, ".github", "workflows",
                           "ci.yml")).read()
    smoke = [ln for ln in wf.splitlines() if "import duckdb" in ln]
    assert smoke, "ci.yml lost its dependency smoke step"
    for mod in ("duckdb", "jsonschema", "polars", "pyarrow", "pyulog",
                "yaml"):
        assert mod in smoke[0], mod


# --- 16. writability and free space -------------------------------------------

def test_missing_data_root_is_rejected(tmp_path):
    with pytest.raises(DataRootError) as exc:
        check_writable(str(tmp_path / "does-not-exist"))
    assert "does not exist" in str(exc.value)


def test_a_file_is_not_a_usable_data_root(tmp_path):
    f = tmp_path / "not-a-dir"
    f.write_text("x")
    with pytest.raises(DataRootError):
        check_writable(str(f))


def test_writable_data_root_passes_a_real_write_probe(tmp_path):
    check_writable(str(tmp_path))
    assert not list(tmp_path.iterdir()), "write probe left a file behind"


def test_insufficient_free_space_is_rejected(tmp_path):
    root = DataRoot(str(tmp_path), "cli:--data-root")
    assert root.free_bytes() > 0
    check_free_space(root, 1024)                      # plenty
    with pytest.raises(DataRootError) as exc:
        check_free_space(root, root.free_bytes() + (1 << 40))
    assert "insufficient free space" in str(exc.value)


# --- 17. runtime report location ----------------------------------------------

def test_runtime_report_is_written_under_the_data_root_reports_dir(tmp_path):
    root = tmp_path / "lake"
    root.mkdir()
    r = run_tool("--status-only", "--data-root", str(root))
    assert r.returncode == 0, r.stderr
    dest = root / "reports" / "acquisition_status_v1.json"
    assert dest.is_file()
    doc = json.load(open(dest))
    assert doc["registry_dataset_count"] == 7
    assert set(doc["datasets"]) == set(EXPECTED_IDS)
    assert doc["data_root"] == str(root)
    assert str(dest) in r.stdout


# --- 18-19. raw immutability and safe extraction ------------------------------

def test_raw_store_never_silently_overwrites_a_content_address(tmp_path):
    from csia.data.store import RawStore
    src = tmp_path / "payload.bin"
    src.write_bytes(b"raw-archive-bytes")
    store = RawStore(str(tmp_path / "raw"))

    first = store.ingest(str(src), "uav_sead")
    assert first["status"] == "INGESTED"
    again = store.ingest(str(src), "uav_sead")
    assert again["status"] == "ALREADY_PRESENT"
    assert again["sha256"] == first["sha256"]

    import stat
    mode = stat.S_IMODE(os.stat(first["path"]).st_mode)
    assert not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)

    # a differing file at the same address is an immutability violation
    with open(first["path"], "rb") as fh:
        assert fh.read() == b"raw-archive-bytes"
    os.chmod(first["path"], 0o644)
    with open(first["path"], "wb") as fh:
        fh.write(b"tampered")
    with pytest.raises(RuntimeError, match="immutability violation"):
        store.ingest(str(src), "uav_sead")


def test_archive_extraction_blocks_path_traversal(tmp_path):
    import tarfile as tf
    import zipfile as zf
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    from acquire_public_datasets import safe_extract

    outside = tmp_path / "lake"
    outside.mkdir()

    zpath = tmp_path / "evil.zip"
    with zf.ZipFile(zpath, "w") as z:
        z.writestr("../../escaped.txt", "pwned")
    with pytest.raises(RuntimeError, match="path traversal blocked"):
        safe_extract(str(zpath), str(outside / "z"))

    tpath = tmp_path / "evil.tar"
    member = tmp_path / "ok.txt"
    member.write_text("hi")
    with tf.open(tpath, "w") as t:
        t.add(str(member), arcname="../../escaped.txt")
    with pytest.raises(RuntimeError, match="path traversal blocked"):
        safe_extract(str(tpath), str(outside / "t"))

    assert not (tmp_path.parent / "escaped.txt").exists()


def test_extraction_into_the_repository_is_refused(tmp_path):
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    from acquire_public_datasets import safe_extract
    import zipfile as zf
    zpath = tmp_path / "ok.zip"
    with zf.ZipFile(zpath, "w") as z:
        z.writestr("a.txt", "hi")
    with pytest.raises(DataRootError, match="inside the Git repository"):
        safe_extract(str(zpath), os.path.join(REPO_ROOT, "datasets", "raw"))


# --- endpoint table must not drift from the registry --------------------------

def test_every_endpoint_key_is_a_registered_dataset():
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    from acquire_public_datasets import ENDPOINTS
    known = set(dataset_ids(load_registry(REGISTRY)))
    assert set(ENDPOINTS) <= known, set(ENDPOINTS) - known
    assert known <= set(ENDPOINTS), known - set(ENDPOINTS)


def test_committed_report_fixture_still_matches_the_registry():
    """The tracked report stays a static fixture; it must stay consistent
    with the registry it describes."""
    doc = json.load(open(os.path.join(
        REPO_ROOT, "datasets", "reports", "acquisition_status_v1.json")))
    reg = yaml.safe_load(open(REGISTRY))
    assert set(doc["datasets"]) <= set(reg["datasets"])
