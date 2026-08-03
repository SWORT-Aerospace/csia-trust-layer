"""Content-addressed immutable snapshots of a whole acquired repository.

A single-file content address is not enough for a dataset repository: the
unit of provenance is the complete file set. So CSIA computes its OWN
integrity record — every file's SHA-256, a canonical sorted manifest, and an
aggregate hash over that manifest — and addresses the raw snapshot by the
aggregate hash.

Hugging Face cache metadata is deliberately NOT the integrity record: it
describes what the client believes it fetched, not what is on our disk.
"""

import hashlib
import json
import os
import shutil

from .store import sha256_file

MANIFEST_VERSION = "1.0.0"


def build_manifest(root: str) -> list:
    """Canonical sorted per-file manifest of everything under `root`.

    Paths are repository-relative and POSIX-normalized so the aggregate hash
    is identical on macOS and Linux.
    """
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".cache"]
        for fn in filenames:
            if fn.endswith(".incomplete"):
                continue
            full = os.path.join(dirpath, fn)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            entries.append({"path": rel,
                            "size": os.path.getsize(full),
                            "sha256": sha256_file(full)})
    entries.sort(key=lambda e: e["path"])
    return entries


def aggregate_hash(manifest: list) -> str:
    """Deterministic hash over the canonical manifest.

    Order-independent by construction (the manifest is sorted) and
    independent of JSON formatting: the digest covers a fixed line format,
    not a serialized document.
    """
    h = hashlib.sha256()
    h.update(f"csia-snapshot-manifest-v{MANIFEST_VERSION}\n".encode())
    for e in manifest:
        h.update(f"{e['sha256']}  {e['size']}  {e['path']}\n".encode())
    return h.hexdigest()


def _freeze(path: str) -> None:
    for dirpath, dirnames, filenames in os.walk(path, topdown=False):
        for fn in filenames:
            os.chmod(os.path.join(dirpath, fn), 0o444)
        for dn in dirnames:
            os.chmod(os.path.join(dirpath, dn), 0o555)
    os.chmod(path, 0o555)


def materialize(staging: str, raw_root: str, dataset_id: str,
                manifest: list, digest: str) -> dict:
    """Promote a verified staging tree to <raw_root>/<dataset>/<digest>/.

    Write-once: an existing address is never silently overwritten. A second
    acquisition of identical content is a no-op; differing content under the
    same address is impossible, because the address IS the content hash.
    """
    dest = os.path.join(raw_root, dataset_id, digest)
    if os.path.exists(dest):
        existing = aggregate_hash(build_manifest(dest))
        if existing != digest:
            raise RuntimeError(
                f"immutability violation at {dest}: content hashes to "
                f"{existing}, not {digest}")
        return {"path": dest, "status": "ALREADY_PRESENT",
                "aggregate_sha256": digest, "file_count": len(manifest)}

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".materializing"
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    shutil.copytree(staging, tmp, symlinks=False,
                    ignore=shutil.ignore_patterns(".cache", "*.incomplete"))
    check = aggregate_hash(build_manifest(tmp))
    if check != digest:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(
            f"copy verification failed: staged tree hashed {digest}, copy "
            f"hashed {check}")
    os.rename(tmp, dest)
    _freeze(dest)
    return {"path": dest, "status": "INGESTED", "aggregate_sha256": digest,
            "file_count": len(manifest)}


def provenance_record(dataset_id: str, inv: dict, manifest: list,
                      digest: str, raw_path: str, acquired_utc: str,
                      license_: str | None, doi: str | None) -> dict:
    """The record CSIA keeps, independent of any client-side cache."""
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_id": dataset_id,
        "provider": inv.get("provider"),
        "repo_id": inv.get("repo_id"),
        "repo_type": inv.get("repo_type"),
        "resolved_commit_sha": inv.get("resolved_commit_sha"),
        "requested_revision": inv.get("requested_revision"),
        "acquired_utc": acquired_utc,
        "license": license_,
        "doi": doi,
        "aggregate_sha256": digest,
        "file_count": len(manifest),
        "total_bytes": sum(e["size"] for e in manifest),
        "raw_path": raw_path,
        "files": manifest,
    }


def write_provenance(manifests_root: str, dataset_id: str,
                     record: dict) -> str:
    """Stored OUTSIDE the raw snapshot so it cannot perturb its own hash."""
    d = os.path.join(manifests_root, dataset_id)
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f"{record['aggregate_sha256']}.json")
    with open(out, "w") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
    return out
