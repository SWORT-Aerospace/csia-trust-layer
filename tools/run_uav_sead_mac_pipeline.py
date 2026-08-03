"""Operator pipeline for acquiring UAV-SEAD on the Mac.

    python tools/run_uav_sead_mac_pipeline.py --stage environment \
        --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE

Stages: environment, preflight, dry-run, acquire, verify, mapping,
partition, certificate, all.

Everything the pipeline writes lands under the data root. Nothing is written
into the Git working tree, and the real dataset is never downloaded without
the operator typing the confirmation token.

See docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md for the operator walkthrough.
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.data import hub  # noqa: E402
from csia.data.mapping import analyze_mapping  # noqa: E402
from csia.data.partition import freeze_partitions  # noqa: E402
from csia.data.paths import (REPO_ROOT, DataRootError,  # noqa: E402
                             assert_outside_repo, check_writable,
                             resolve_data_root)
from csia.data.registry import (declared_license, doi,  # noqa: E402
                                get_dataset, licensing, load_registry,
                                source_block)
from csia.data.snapshot import (aggregate_hash, build_manifest,  # noqa: E402
                                materialize, provenance_record,
                                write_provenance)

DATASET_ID = "uav_sead"
CONFIRM_TOKEN = "UAV-SEAD"
TOOL_VERSION = "1.0.0"
STAGES = ("environment", "preflight", "dry-run", "acquire", "verify",
          "mapping", "partition", "certificate", "all")

ENV_REPORT = "mac_environment_check.json"
PREFLIGHT_REPORT = "uav_sead_preflight.json"
PROGRESS_REPORT = "uav_sead_progress.json"
MAPPING_REPORT = "uav_sead_mapping_analysis.json"
PARTITION_MANIFEST = "partition_manifest_v1.json"
CERT_JSON = "UAV_SEAD_ACQUISITION_CERTIFICATE.json"
CERT_MD = "UAV_SEAD_ACQUISITION_CERTIFICATE.md"

#: working-tree changes an operator is allowed to have during acquisition
PERMITTED_DIRTY = ("docs/runbooks/", ".venv/")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def git(*args, cwd=REPO_ROOT):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=60).stdout.strip()
    except Exception:
        return ""


def atomic_write_json(path, doc):
    """Never leave a half-written report if the process dies mid-write."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path


def read_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def log_path(root, name):
    d = os.path.join(root.reports, "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


def say(msg, quiet=False):
    if not quiet:
        print(msg)


# --- stage: environment -------------------------------------------------------

def stage_environment(root, args) -> dict:
    reg_path = os.path.join(REPO_ROOT, "datasets", "registry",
                            "public_datasets_v1.yaml")
    checks, blockers, warnings = {}, [], []

    checks["repository_path"] = REPO_ROOT
    checks["git_branch"] = git("rev-parse", "--abbrev-ref", "HEAD")
    checks["git_commit"] = git("rev-parse", "HEAD")
    porcelain = git("status", "--porcelain")
    dirty = [ln for ln in porcelain.splitlines() if ln.strip()]
    permitted = [ln for ln in dirty
                 if any(p in ln for p in PERMITTED_DIRTY)]
    checks["git_clean"] = not dirty
    checks["git_dirty_entries"] = dirty
    checks["git_dirty_permitted_only"] = bool(dirty) and len(
        permitted) == len(dirty)

    git("fetch", "--quiet", "origin", checks["git_branch"] or "HEAD")
    behind = git("rev-list", "--count",
                 f"HEAD..origin/{checks['git_branch']}") or "0"
    checks["commits_behind_remote"] = int(behind) if behind.isdigit() else None
    if checks["commits_behind_remote"]:
        warnings.append(
            f"branch is {checks['commits_behind_remote']} commit(s) behind "
            f"origin — run: git pull origin {checks['git_branch']}")

    checks["python_version"] = platform.python_version()
    checks["python_executable"] = sys.executable
    checks["in_virtualenv"] = sys.prefix != getattr(sys, "base_prefix",
                                                    sys.prefix)
    checks["venv_inside_repository"] = sys.prefix.startswith(REPO_ROOT)
    checks["platform"] = platform.platform()
    if not checks["in_virtualenv"]:
        blockers.append("not running inside a virtual environment — "
                        "activate .venv first (see the runbook)")
    if sys.version_info < (3, 11):
        blockers.append(f"Python {platform.python_version()} is below the "
                        f"declared minimum 3.11")

    versions = {}
    #: import name -> installed distribution name, where they differ
    dists = {"yaml": "PyYAML"}
    for mod in ("duckdb", "huggingface_hub", "jsonschema", "polars",
                "pyarrow", "pymavlink", "pyulog", "yaml"):
        try:
            __import__(mod)
            # importlib.metadata, not module.__version__: jsonschema
            # deprecated the attribute, and several packages never had one.
            from importlib.metadata import version as dist_version
            versions[mod] = dist_version(dists.get(mod, mod))
        except Exception as exc:
            versions[mod] = f"MISSING: {type(exc).__name__}"
            blockers.append(f"dependency {mod} does not import — run: "
                            f"pip install -e \".[data,dev,logs,mavlink]\"")
    checks["dependency_versions"] = versions

    # Every pipeline output must land under the data root. If any of them
    # would resolve inside the repository, tracked files could be modified.
    would_touch_repo = [p for p in (root.reports, root.raw, root.manifests,
                                    root.cache, root.normalized, root.exports)
                        if p.startswith(REPO_ROOT)]
    checks["tracked_files_would_be_modified"] = bool(would_touch_repo)
    checks["repo_paths_that_would_be_written"] = would_touch_repo
    if would_touch_repo:
        blockers.append(f"pipeline outputs would be written inside the "
                        f"repository: {would_touch_repo}")

    checks["data_root"] = root.path
    checks["data_root_source"] = root.source
    checks["data_root_outside_git"] = not root.is_repo_local
    if root.is_repo_local:
        blockers.append(f"data root {root.path} is inside the Git repository")
    ssd = "/Volumes/CSIA_DATA"
    checks["ssd_mount"] = ssd
    checks["ssd_mounted"] = os.path.isdir(ssd)
    checks["data_root_exists"] = os.path.isdir(root.path)
    if not checks["data_root_exists"]:
        blockers.append(f"data root does not exist: {root.path}")
    else:
        try:
            check_writable(root.path)
            checks["data_root_writable"] = True
        except DataRootError as exc:
            checks["data_root_writable"] = False
            blockers.append(str(exc))
        free = root.free_bytes()
        total = shutil.disk_usage(root.path).total
        checks["free_bytes"] = free
        checks["free_gib"] = round(free / (1 << 30), 2)
        checks["total_gib"] = round(total / (1 << 30), 2)
        checks["subtrees"] = {n: os.path.isdir(root.sub(n))
                              for n in ("raw", "normalized", "manifests",
                                        "reports", "cache", "exports")}

    checks["registry_path"] = reg_path
    try:
        entry = get_dataset(load_registry(reg_path), DATASET_ID)
        src = source_block(entry)
        checks["registered_repo_id"] = src.get("repo_id")
        checks["registered_doi"] = doi(entry)
        checks["registered_license"] = declared_license(entry)
    except Exception as exc:
        blockers.append(f"registry unreadable: {exc}")

    try:
        inv = hub.repo_inventory(checks.get("registered_repo_id"), "dataset",
                                 token=args_token(args))
        checks["hub_reachable"] = True
        checks["hub_resolved_commit"] = inv["resolved_commit_sha"]
    except Exception as exc:
        checks["hub_reachable"] = False
        checks["hub_error"] = str(exc)
        blockers.append(f"Hugging Face API unreachable: {exc}")

    checks["system_date_utc"] = now()
    checks["system_date_local"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    checks["timezone"] = time.strftime("%Z %z")

    doc = {"stage": "environment", "tool_version": TOOL_VERSION,
           "generated_utc": now(), "checks": checks,
           "blockers": blockers, "warnings": warnings, "ok": not blockers}
    atomic_write_json(root.report(ENV_REPORT), doc)
    return doc


def args_token(args):
    return getattr(args, "hf_token", None) or os.environ.get("HF_TOKEN") or None


# --- stage: preflight ---------------------------------------------------------

def stage_preflight(root, args) -> dict:
    reg = load_registry(os.path.join(REPO_ROOT, "datasets", "registry",
                                     "public_datasets_v1.yaml"))
    entry = get_dataset(reg, DATASET_ID)
    src = source_block(entry)
    lic = licensing(entry)
    patterns = src.get("allow_patterns") or hub.ALLOW_PATTERNS
    blockers, warnings = [], []

    repo_commit = git("rev-parse", "HEAD")
    porcelain = [ln for ln in git("status", "--porcelain").splitlines()
                 if ln.strip()]
    unpermitted = [ln for ln in porcelain
                   if not any(p in ln for p in PERMITTED_DIRTY)]
    if unpermitted:
        blockers.append(
            f"working tree has {len(unpermitted)} unpermitted change(s); "
            f"commit or stash them first: {unpermitted[:5]}")
    if not repo_commit:
        blockers.append("repository commit is not pinned (no git HEAD)")
    if root.is_repo_local:
        blockers.append(f"data root {root.path} resolves inside Git")
    if not os.path.isdir(root.path):
        blockers.append(f"data root does not exist: {root.path}")
    else:
        try:
            check_writable(root.path)
        except DataRootError as exc:
            blockers.append(str(exc))

    inv, resolved = None, None
    try:
        inv = hub.repo_inventory(src["repo_id"], src.get("repo_type",
                                                         "dataset"),
                                 revision=src.get("revision", "main"),
                                 token=args_token(args), patterns=patterns)
        resolved = inv["resolved_commit_sha"]
    except hub.HubError as exc:
        blockers.append(f"Hub inventory could not be resolved: {exc}")

    doc = {
        "stage": "preflight",
        "generated_utc": now(),
        "tool_version": TOOL_VERSION,
        "repository_commit": repo_commit,
        "acquisition_tool_version": TOOL_VERSION,
        "dataset_id": DATASET_ID,
        "provider": "Hugging Face",
        "huggingface_repo_id": src.get("repo_id"),
        "registered_repo_id": src.get("repo_id"),
        "repo_type": src.get("repo_type", "dataset"),
        "revision_source": src.get("revision", "main"),
        "revision_policy": src.get("revision_policy"),
        "resolved_commit_sha": resolved,
        "doi": doi(entry),
        "registry_license": lic["license"],
        "attribution_requirement": lic.get("attribution_requirement"),
        "included_patterns": list(patterns),
        "data_root": root.path,
        "cache_destination": (os.path.join(root.cache, DATASET_ID, resolved)
                              if resolved else None),
        "immutable_snapshot_destination": os.path.join(
            root.raw, DATASET_ID, "<AGGREGATE_MANIFEST_HASH>"),
        "manifest_destination": os.path.join(root.manifests, DATASET_ID),
        "report_destination": root.report(PREFLIGHT_REPORT),
        "available_bytes": root.free_bytes(),
        "available_gib": round(root.free_bytes() / (1 << 30), 2),
    }

    if not resolved:
        blockers.append("resolved commit is missing — refusing acquisition")
    if inv:
        ulg = [f for f in inv["files"] if f["path"].lower().endswith(".ulg")]
        need, why = hub.required_free_bytes(inv)
        doc.update(
            hub_license=inv["hub_license"],
            file_count=inv["file_count"],
            ulg_file_count=len(ulg),
            expected_total_bytes=inv["total_bytes"],
            expected_total_gib=round(inv["total_bytes"] / (1 << 30), 2),
            expected_size_exact=inv["size_known"],
            excluded_patterns=inv["excluded_paths"][:50],
            excluded_count=inv["excluded_count"],
            required_safety_margin_bytes=need,
            required_safety_margin_gib=round(need / (1 << 30), 2),
            required_margin_rationale=why,
            authentication_required=hub.authentication_required(inv))

        reg_norm = str(lic["license"] or "").lower().replace("_", "-")
        hub_norm = str(inv["hub_license"] or "").lower().replace("_", "-")
        match = bool(hub_norm) and reg_norm == hub_norm
        doc["license_match"] = match
        if inv["hub_license"] and not match:
            blockers.append(f"license mismatch: registry {lic['license']!r} "
                            f"vs Hub {inv['hub_license']!r}")
        elif not inv["hub_license"]:
            warnings.append("Hub card reported no license; registry value "
                            "used, unverified against the Hub")
        if src.get("repo_id") != inv["repo_id"]:
            blockers.append("repository ID differs from the registered ID")
        if not inv["size_known"]:
            warnings.append(f"Hub total is not exact "
                            f"({inv['sizes_unknown_for']} file(s) report no "
                            f"size); conservative margin enforced")
        if os.path.isdir(root.path) and root.free_bytes() < need:
            blockers.append(
                f"insufficient free space: need "
                f"{need / (1 << 30):.1f} GiB ({why}), have "
                f"{root.free_bytes() / (1 << 30):.1f} GiB")
        if doc.get("authentication_required"):
            blockers.append("repository is private/gated — export HF_TOKEN")
        if len(ulg) == 0:
            warnings.append("no .ulg files matched the allow patterns")

    doc["blockers"] = blockers
    doc["warnings"] = warnings
    doc["download_authorized"] = not blockers
    atomic_write_json(root.report(PREFLIGHT_REPORT), doc)
    return doc


# --- stage: acquire / dry-run -------------------------------------------------

def write_progress(root, **fields):
    p = root.report(PROGRESS_REPORT)
    doc = read_json(p) or {}
    doc.update(fields)
    doc["updated_utc"] = now()
    atomic_write_json(p, doc)
    return doc


def stage_acquire(root, args, dry_run=False) -> dict:
    pre = read_json(root.report(PREFLIGHT_REPORT))
    if not pre:
        return {"stage": "acquire", "ok": False,
                "error": "no preflight certificate — run --stage preflight"}
    if not pre.get("download_authorized"):
        return {"stage": "acquire", "ok": False,
                "error": "preflight did not authorize download",
                "blockers": pre.get("blockers")}
    pinned = pre.get("resolved_commit_sha")
    if not pinned:
        return {"stage": "acquire", "ok": False,
                "error": "preflight recorded no resolved commit"}

    if not dry_run and args.confirm_download != CONFIRM_TOKEN:
        return {"stage": "acquire", "ok": False,
                "error": f"refusing to download without "
                         f"--confirm-download {CONFIRM_TOKEN}",
                "hint": f"re-run with: --confirm-download {CONFIRM_TOKEN}"}

    reg = load_registry(os.path.join(REPO_ROOT, "datasets", "registry",
                                     "public_datasets_v1.yaml"))
    entry = get_dataset(reg, DATASET_ID)
    src = source_block(entry)
    patterns = src.get("allow_patterns") or hub.ALLOW_PATTERNS

    # The upstream branch may have moved since preflight. Acquiring a
    # different commit than the one certified would silently invalidate the
    # certificate, so it is refused rather than re-pinned.
    try:
        inv = hub.repo_inventory(src["repo_id"], src.get("repo_type",
                                                         "dataset"),
                                 revision=pinned, token=args_token(args),
                                 patterns=patterns)
    except hub.HubError as exc:
        return {"stage": "acquire", "ok": False, "error": str(exc)}
    if inv["resolved_commit_sha"] != pinned:
        return {"stage": "acquire", "ok": False,
                "error": f"upstream commit changed: preflight pinned "
                         f"{pinned}, Hub now resolves "
                         f"{inv['resolved_commit_sha']}. Re-run preflight "
                         f"and review before acquiring."}

    staging = os.path.join(root.cache, DATASET_ID, pinned)
    if dry_run:
        return {"stage": "dry-run", "ok": True, "resolved_commit_sha": pinned,
                "would_download_files": inv["file_count"],
                "would_download_bytes": inv["total_bytes"],
                "staging": staging,
                "would_promote_to": os.path.join(root.raw, DATASET_ID,
                                                 "<AGGREGATE_MANIFEST_HASH>"),
                "note": "no request issued for payload, nothing written"}

    write_progress(root, stage="acquire", state="STARTED",
                   resolved_commit_sha=pinned, staging=staging,
                   expected_files=inv["file_count"],
                   expected_bytes=inv["total_bytes"],
                   files_completed=0, bytes_completed=0, errors=[],
                   retries=0, started_utc=now())

    logf = log_path(root, f"acquire_{pinned[:12]}_"
                          f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
                          f".log")
    attempt, last_error = 0, None
    for attempt in range(1, args.retries + 1):
        try:
            with open(logf, "a") as fh:
                fh.write(f"[{now()}] attempt {attempt} pinned={pinned}\n")
            hub.download_snapshot(src["repo_id"],
                                  src.get("repo_type", "dataset"), pinned,
                                  staging, patterns=patterns,
                                  token=args_token(args))
            last_error = None
            break
        except KeyboardInterrupt:
            write_progress(root, state="INTERRUPTED",
                           note="Ctrl-C: completed files preserved in cache; "
                                "re-run the identical command to resume")
            with open(logf, "a") as fh:
                fh.write(f"[{now()}] interrupted by operator\n")
            raise
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            with open(logf, "a") as fh:
                fh.write(f"[{now()}] error: {last_error}\n")
            write_progress(root, state="RETRYING", retries=attempt,
                           errors=(read_json(root.report(PROGRESS_REPORT))
                                   or {}).get("errors", []) + [last_error])
            if attempt < args.retries:
                time.sleep(min(2 ** attempt, 30))

    done = build_manifest(staging) if os.path.isdir(staging) else []
    write_progress(root, state=("DOWNLOADED" if last_error is None
                                else "FAILED"),
                   retries=attempt, files_completed=len(done),
                   bytes_completed=sum(e["size"] for e in done),
                   log_file=logf,
                   errors=([last_error] if last_error else []))
    if last_error:
        return {"stage": "acquire", "ok": False, "error": last_error,
                "resolved_commit_sha": pinned, "log": logf,
                "hint": "re-run the identical command to resume"}
    return {"stage": "acquire", "ok": True, "resolved_commit_sha": pinned,
            "staging": staging, "files_completed": len(done),
            "bytes_completed": sum(e["size"] for e in done), "log": logf}


# --- stage: verify ------------------------------------------------------------

def stage_verify(root, args) -> dict:
    pre = read_json(root.report(PREFLIGHT_REPORT)) or {}
    pinned = pre.get("resolved_commit_sha")
    if not pinned:
        return {"stage": "verify", "ok": False,
                "error": "no pinned commit in the preflight certificate"}
    staging = os.path.join(root.cache, DATASET_ID, pinned)
    if not os.path.isdir(staging):
        return {"stage": "verify", "ok": False,
                "error": f"no staged download at {staging}"}

    reg = load_registry(os.path.join(REPO_ROOT, "datasets", "registry",
                                     "public_datasets_v1.yaml"))
    entry = get_dataset(reg, DATASET_ID)
    src = source_block(entry)
    patterns = src.get("allow_patterns") or hub.ALLOW_PATTERNS
    try:
        inv = hub.repo_inventory(src["repo_id"], "dataset", revision=pinned,
                                 token=args_token(args), patterns=patterns)
    except hub.HubError as exc:
        return {"stage": "verify", "ok": False,
                "error": f"cannot re-read inventory: {exc}"}

    check = hub.verify_against_inventory(staging, inv)
    if not check["complete"]:
        write_progress(root, state="INCOMPLETE", verification=check)
        return {"stage": "verify", "ok": False,
                "error": "staged tree is incomplete — snapshot NOT promoted",
                "verification": check,
                "hint": "re-run --stage acquire to resume"}

    manifest = build_manifest(staging)
    if pre.get("file_count") and len(manifest) != pre["file_count"]:
        return {"stage": "verify", "ok": False,
                "error": f"file count {len(manifest)} != preflight "
                         f"{pre['file_count']} — snapshot NOT promoted"}
    total = sum(e["size"] for e in manifest)
    if pre.get("expected_size_exact") and pre.get("expected_total_bytes") \
            and total != pre["expected_total_bytes"]:
        return {"stage": "verify", "ok": False,
                "error": f"byte count {total} != preflight "
                         f"{pre['expected_total_bytes']}"}

    digest = aggregate_hash(manifest)
    if aggregate_hash(build_manifest(staging)) != digest:
        return {"stage": "verify", "ok": False,
                "error": "manifest is not reproducible — refusing promotion"}

    placed = materialize(staging, assert_outside_repo(root.raw), DATASET_ID,
                         manifest, digest)
    prov = provenance_record(DATASET_ID, inv, manifest, digest,
                             placed["path"], now(), declared_license(entry),
                             doi(entry))
    prov_path = write_provenance(root.manifests, DATASET_ID, prov)
    write_progress(root, state="PROMOTED", aggregate_sha256=digest,
                   raw_path=placed["path"])
    return {"stage": "verify", "ok": True, "aggregate_sha256": digest,
            "raw_path": placed["path"], "ingest_status": placed["status"],
            "file_count": len(manifest), "total_bytes": total,
            "ulg_count": sum(1 for e in manifest
                             if e["path"].lower().endswith(".ulg")),
            "provenance_manifest": prov_path,
            "resolved_commit_sha": pinned}


# --- stage: mapping -----------------------------------------------------------

def find_snapshot(root, args):
    base = root.raw_dir(DATASET_ID)
    if not os.path.isdir(base):
        return None, "no acquired snapshot"
    snaps = sorted(d for d in os.listdir(base) if len(d) == 64)
    if args.snapshot:
        snaps = [s for s in snaps if s == args.snapshot]
    if not snaps:
        return None, "no snapshot found"
    if len(snaps) > 1:
        return None, (f"{len(snaps)} snapshots present; pass --snapshot "
                      f"<AGGREGATE_MANIFEST_HASH>")
    return os.path.join(base, snaps[0]), None


def stage_mapping(root, args) -> dict:
    snap, err = find_snapshot(root, args)
    if err:
        return {"stage": "mapping", "ok": False, "error": err}
    mapping = os.path.join(snap, "mapping.json")
    if not os.path.isfile(mapping):
        return {"stage": "mapping", "ok": False,
                "error": f"mapping.json absent from {snap}"}
    res = analyze_mapping(mapping, os.path.join(snap, "ulg_files"))
    res.update(stage="mapping", snapshot=snap,
               aggregate_sha256=os.path.basename(snap), generated_utc=now())
    # discrepancies are reported, never repaired
    res["ok"] = bool(res.get("structure_confidently_parsed"))
    atomic_write_json(root.report(MAPPING_REPORT), res)
    return res


# --- stage: partition ---------------------------------------------------------

def stage_partition(root, args) -> dict:
    mapres = read_json(root.report(MAPPING_REPORT))
    if not mapres:
        return {"stage": "partition", "ok": False,
                "error": "mapping verification has not run — "
                         "run --stage mapping first"}
    if not mapres.get("ok"):
        return {"stage": "partition", "ok": False,
                "error": "mapping verification did not succeed; refusing to "
                         "partition on an unparsed mapping",
                "mapping_report": root.report(MAPPING_REPORT)}
    snap, err = find_snapshot(root, args)
    if err:
        return {"stage": "partition", "ok": False, "error": err}

    prov = read_json(os.path.join(root.manifests, DATASET_ID,
                                  f"{os.path.basename(snap)}.json")) or {}
    by_path = {e["path"]: e for e in prov.get("files", [])}

    with open(os.path.join(snap, "mapping.json")) as fh:
        doc = json.load(fh)
    entries = (doc.items() if isinstance(doc, dict)
               else enumerate(doc) if isinstance(doc, list) else [])

    flights = {}
    for key, value in entries:
        meta = value if isinstance(value, dict) else {}
        ref = None
        if isinstance(value, dict):
            for k in ("file", "filename", "log", "path", "ulg", "name"):
                if k in {str(x).lower() for x in value}:
                    ref = next(v for kk, v in value.items()
                               if str(kk).lower() == k)
                    break
        ref = str(ref or key).strip()
        base = os.path.basename(ref)
        rec = next((v for p, v in by_path.items()
                    if os.path.basename(p) == base), None)
        flights[base] = {"sha256": (rec or {}).get("sha256"),
                         "metadata": meta}

    man = freeze_partitions(flights, os.path.basename(snap),
                            git("rev-parse", "HEAD"), now(),
                            external_replication_groups=args.external_group)
    man.update(stage="partition", dataset_id=DATASET_ID, snapshot=snap,
               mapping_report=root.report(MAPPING_REPORT))
    out = os.path.join(root.manifests, DATASET_ID, PARTITION_MANIFEST)
    atomic_write_json(out, man)
    man["manifest_path"] = out
    man["ok"] = man["leakage_free"]
    return man


# --- stage: certificate -------------------------------------------------------

def stage_certificate(root, args) -> dict:
    env = read_json(root.report(ENV_REPORT)) or {}
    pre = read_json(root.report(PREFLIGHT_REPORT)) or {}
    mapres = read_json(root.report(MAPPING_REPORT)) or {}
    snap, err = find_snapshot(root, args)
    if err:
        return {"stage": "certificate", "ok": False, "error": err}
    digest = os.path.basename(snap)
    prov = read_json(os.path.join(root.manifests, DATASET_ID,
                                  f"{digest}.json")) or {}
    part = read_json(os.path.join(root.manifests, DATASET_ID,
                                  PARTITION_MANIFEST)) or {}

    missing = [n for n, d in (("preflight", pre), ("mapping", mapres),
                              ("partition", part), ("provenance", prov))
               if not d]
    if missing:
        return {"stage": "certificate", "ok": False,
                "error": f"cannot certify: missing {', '.join(missing)}"}

    cert = {
        "certificate_version": "1.0.0",
        "generated_utc": now(),
        "dataset_identity": {
            "csia_dataset_id": DATASET_ID,
            "title": "UAV Flight Anomaly Dataset (PX4 ULog)",
            "provider": "Hugging Face",
            "huggingface_repo_id": pre.get("huggingface_repo_id"),
            "doi": pre.get("doi"),
            "license": pre.get("registry_license"),
            "hub_license": pre.get("hub_license"),
            "license_match": pre.get("license_match"),
            "attribution_requirement": pre.get("attribution_requirement"),
        },
        "pinned_commit": prov.get("resolved_commit_sha"),
        "acquisition_timestamp_utc": prov.get("acquired_utc"),
        "source_file_count": prov.get("file_count"),
        "ulg_file_count": sum(1 for f in prov.get("files", [])
                              if f["path"].lower().endswith(".ulg")),
        "total_bytes": prov.get("total_bytes"),
        "aggregate_manifest_sha256": digest,
        "raw_snapshot_path": snap,
        "mapping": {
            "total_mapped_entries": mapres.get("total_mapped_entries"),
            "annotated_entries": mapres.get("annotated_entries"),
            "claimed_annotated": mapres.get("expected_annotated"),
            "annotated_count_matches_claim":
                mapres.get("annotated_count_matches_claim"),
            "discrepancy": mapres.get("claim_discrepancy"),
            "duplicate_mapping_count": mapres.get("duplicate_mapping_count"),
            "missing_referenced_count":
                mapres.get("missing_referenced_count"),
            "present_but_unreferenced_count":
                mapres.get("present_but_unreferenced_count"),
        },
        "partitions": {
            "counts": part.get("partition_counts"),
            "group_count": part.get("group_count"),
            "grouping_tiers_used": part.get("grouping_tiers_used"),
            "leakage_free": part.get("leakage_free"),
            "leakage": part.get("leakage"),
            "policy_version": part.get("policy_version"),
            "seed": part.get("seed"),
        },
        "repository_commit": pre.get("repository_commit"),
        "python_version": env.get("checks", {}).get("python_version"),
        "dependency_versions": env.get("checks", {}).get(
            "dependency_versions"),
        "ssd_path": root.path,
        "git_clean": env.get("checks", {}).get("git_clean"),
        "csia_evaluation_started": False,
        "evaluation_note": "acquisition only. No CSIA run, no threshold "
                           "selection, no residual or alert inspection has "
                           "occurred. Partitions were frozen from metadata "
                           "before any signal content was examined.",
    }
    atomic_write_json(root.report(CERT_JSON), cert)

    d = cert["dataset_identity"]
    md = [
        "# UAV-SEAD acquisition certificate", "",
        f"- Generated: `{cert['generated_utc']}`",
        f"- Dataset: {d['title']} (`{d['csia_dataset_id']}`)",
        f"- Provider: {d['provider']} — `{d['huggingface_repo_id']}`",
        f"- DOI: `{d['doi']}`",
        f"- Licence: `{d['license']}` (Hub: `{d['hub_license']}`, "
        f"match: {d['license_match']})",
        f"- Attribution: {d['attribution_requirement']}", "",
        "## Snapshot", "",
        f"- Pinned upstream commit: `{cert['pinned_commit']}`",
        f"- Acquired: `{cert['acquisition_timestamp_utc']}`",
        f"- Files: {cert['source_file_count']} "
        f"({cert['ulg_file_count']} `.ulg`)",
        f"- Total bytes: {cert['total_bytes']}",
        f"- Aggregate manifest SHA-256: `{cert['aggregate_manifest_sha256']}`",
        f"- Raw path: `{cert['raw_snapshot_path']}`", "",
        "## Mapping", "",
        f"- Mapped entries: {cert['mapping']['total_mapped_entries']}",
        f"- Annotated: {cert['mapping']['annotated_entries']} "
        f"(claimed {cert['mapping']['claimed_annotated']}; "
        f"reproduced: {cert['mapping']['annotated_count_matches_claim']})",
        f"- Duplicates: {cert['mapping']['duplicate_mapping_count']}, "
        f"missing referenced: {cert['mapping']['missing_referenced_count']}, "
        f"unreferenced present: "
        f"{cert['mapping']['present_but_unreferenced_count']}",
    ]
    if cert["mapping"]["discrepancy"]:
        md += ["", f"> **Discrepancy:** {cert['mapping']['discrepancy']}"]
    md += [
        "", "## Partitions (frozen before any signal inspection)", "",
        f"- Counts: `{cert['partitions']['counts']}`",
        f"- Groups: {cert['partitions']['group_count']} "
        f"via `{cert['partitions']['grouping_tiers_used']}`",
        f"- Leakage-free: **{cert['partitions']['leakage_free']}**",
        f"- Policy `{cert['partitions']['policy_version']}`, "
        f"seed `{cert['partitions']['seed']}`", "",
        "## Environment", "",
        f"- Repository commit: `{cert['repository_commit']}`",
        f"- Python: `{cert['python_version']}`",
        f"- SSD: `{cert['ssd_path']}`",
        f"- Git clean: {cert['git_clean']}", "",
        "## Evaluation status", "",
        f"- `csia_evaluation_started: {str(cert['csia_evaluation_started']).lower()}`",
        "", cert["evaluation_note"], "",
    ]
    md_path = root.report(CERT_MD)
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    tmp = md_path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(md))
    os.replace(tmp, md_path)
    cert["ok"] = True
    cert["certificate_json"] = root.report(CERT_JSON)
    cert["certificate_md"] = md_path
    return cert


# --- CLI ----------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        prog="run_uav_sead_mac_pipeline.py",
        description="Operator pipeline for acquiring UAV-SEAD on the Mac.")
    ap.add_argument("--stage", required=True, choices=STAGES)
    ap.add_argument("--data-root", default=None, metavar="PATH")
    ap.add_argument("--confirm-download", default=None, metavar="TOKEN",
                    help=f"must be exactly {CONFIRM_TOKEN} to download")
    ap.add_argument("--snapshot", default=None,
                    metavar="AGGREGATE_MANIFEST_HASH")
    ap.add_argument("--external-group", action="append", default=[],
                    metavar="GROUP_ID",
                    help="group id to hold back as EXTERNAL_REPLICATION")
    ap.add_argument("--hf-token", default=None)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    return ap


def run_stage(name, root, args):
    return {
        "environment": lambda: stage_environment(root, args),
        "preflight": lambda: stage_preflight(root, args),
        "dry-run": lambda: stage_acquire(root, args, dry_run=True),
        "acquire": lambda: stage_acquire(root, args, dry_run=False),
        "verify": lambda: stage_verify(root, args),
        "mapping": lambda: stage_mapping(root, args),
        "partition": lambda: stage_partition(root, args),
        "certificate": lambda: stage_certificate(root, args),
    }[name]()


def summarize(name, res):
    ok = res.get("ok", res.get("download_authorized", True))
    print(f"\n=== stage: {name} -> {'OK' if ok else 'BLOCKED'} ===")
    for key in ("error", "hint", "resolved_commit_sha", "aggregate_sha256",
                "raw_path", "file_count", "ulg_count", "total_bytes",
                "annotated_entries", "annotated_count_matches_claim",
                "partition_counts", "leakage_free", "certificate_md",
                "would_download_files", "would_download_bytes"):
        if key in res and res[key] is not None:
            print(f"  {key:32s} {res[key]}")
    for b in res.get("blockers", []) or []:
        print(f"  blocker: {b}")
    for w in res.get("warnings", []) or []:
        print(f"  warning: {w}")
    return ok


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_data_root(args.data_root)
    if root.is_repo_local and args.stage != "environment":
        print(f"error: data root {root.path} is inside the Git repository; "
              f"pass --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE",
              file=sys.stderr)
        return 2
    if not root.is_repo_local and os.path.isdir(root.path):
        root.ensure()

    order = (["environment", "preflight", "dry-run", "acquire", "verify",
              "mapping", "partition", "certificate"]
             if args.stage == "all" else [args.stage])

    results, rc = {}, 0
    for name in order:
        if name == "acquire" and args.confirm_download != CONFIRM_TOKEN:
            print(f"\n=== stage: acquire -> BLOCKED ===")
            print(f"  refusing to download without --confirm-download "
                  f"{CONFIRM_TOKEN}")
            print(f"  re-run when ready:")
            print(f"    python tools/run_uav_sead_mac_pipeline.py --stage all"
                  f" \\\n      --data-root {root.path} \\"
                  f"\n      --confirm-download {CONFIRM_TOKEN}")
            return 3
        res = run_stage(name, root, args)
        results[name] = res
        if not summarize(name, res):
            rc = 1
            break
    if args.json:
        print(json.dumps(results, indent=1, sort_keys=True, default=str))
    return rc


if __name__ == "__main__":
    sys.exit(main())
