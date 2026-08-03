"""Reproducible public-dataset acquisition (ACEG slice 2, Part 3).

    python tools/acquire_public_datasets.py --status-only
    python tools/acquire_public_datasets.py --dataset uav_sead --preflight
    python tools/acquire_public_datasets.py --dataset uav_sead \
        --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE

Dataset universe comes from datasets/registry/public_datasets_v1.yaml — a
mapping keyed by dataset id. A registry that yields zero entries is a fatal
error, never a "0/0 complete" success message.

Storage: every runtime artifact lives under the resolved data root
(--data-root, then CSIA_DATA_ROOT, then the repo-local fixture path for
tests only). Acquired payload is REFUSED inside the Git working tree.

Safety: raw files are hashed BEFORE extraction or normalization and stored
write-once under <data-root>/raw/<dataset>/<sha256>/; archives are extracted
with path-traversal protection; restricted licences must be acknowledged
with --acknowledge-license <id>; downloads resume via HTTP Range.
"""

import argparse
import json
import os
import socket
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.data.paths import (DataRootError, assert_outside_repo,  # noqa: E402
                             require_external_data_root, resolve_data_root)
from csia.data.registry import (RegistryError,  # noqa: E402
                                acknowledgement_required, expected_inventory,
                                expected_size_bytes, get_dataset, licensing,
                                load_registry, select_datasets)
from csia.data.store import RawStore  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATUS_REPORT_NAME = "acquisition_status_v1.json"

#: Download endpoints per registry id. URLs marked TO_CONFIRM must be
#: finalized on the unrestricted host from the official source pages recorded
#: in the registry; the tool treats a TO_CONFIRM URL as "resolve manually".
#: Keys are validated against the registry (tests/test_acquisition.py).
ENDPOINTS = {
    "uav_sead": ["TO_CONFIRM:https://zenodo.org/"],
    "alfa": ["TO_CONFIRM:https://theairlab.org/alfa-dataset"],
    "insane": ["TO_CONFIRM:https://sst.aau.at/cns/"],
    "blackbird": ["TO_CONFIRM:https://github.com/mit-aera/Blackbird-Dataset"],
    "euroc_mav": ["TO_CONFIRM:http://robotics.ethz.ch/~asl-datasets/"],
    "tum_vi": ["TO_CONFIRM:https://vision.in.tum.de/"],
    "px4_flightreview_v1": [],   # generated from the committed report below
}


def px4_corpus_urls():
    rep = os.path.join(ROOT, "data", "real_logs_report.json")
    with open(rep) as fh:
        d = json.load(fh)
    return [f"https://review.px4.io/download_log?log={f['log'][3:-4]}"
            for f in d["flights"]]


def endpoints_for(dataset_id: str) -> list:
    urls = ENDPOINTS.get(dataset_id, [])
    if not urls and dataset_id == "px4_flightreview_v1":
        return px4_corpus_urls()
    return list(urls)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- download -----------------------------------------------------------------

def probe(url, cache_dir=None, timeout=25):
    """One attempt; returns a structured record, success or not.

    Resumes a partial download when a .part file is present and the server
    honours Range. Never raises: the failure record IS the deliverable.
    """
    rec = {"url": url, "ts_utc": _now()}
    if url.startswith("TO_CONFIRM:"):
        rec.update(status="URL_UNRESOLVED",
                   error="endpoint must be confirmed from the official "
                         "source page on an unrestricted host",
                   next_action="resolve exact archive URL, rerun")
        return rec, None
    host = url.split("/")[2]
    try:
        rec["dns"] = socket.gethostbyname(host)
    except OSError as e:
        rec["dns"] = f"FAILED: {e}"

    part = None
    have = 0
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        import hashlib
        key = hashlib.sha256(url.encode()).hexdigest()[:32]
        part = os.path.join(cache_dir, f"{key}.part")
        have = os.path.getsize(part) if os.path.exists(part) else 0

    headers = {"User-Agent": "csia-acq/1"}
    if have:
        headers["Range"] = f"bytes={have}-"
        rec["resume_from_bytes"] = have
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resumed = getattr(r, "status", None) == 206
            if part:
                with open(part, "ab" if resumed else "wb") as fh:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
                rec.update(status="DOWNLOADED", http=r.status,
                           bytes=os.path.getsize(part), resumed=resumed,
                           cached_at=part)
                return rec, part
            data = r.read()
            rec.update(status="DOWNLOADED", http=r.status, bytes=len(data))
            return rec, data
    except urllib.error.HTTPError as e:
        rec.update(status="HTTP_ERROR", http=e.code, error=str(e))
    except Exception as e:
        rec.update(status="NETWORK_ERROR", error=f"{type(e).__name__}: {e}")
    rec["next_action"] = "rerun on unrestricted host; command recorded"
    return rec, None


def safe_extract(archive_path, dest):
    """Zip/tar extraction with path-traversal protection.

    Tar additionally uses the stdlib 'data' filter, which strips absolute
    paths, links escaping the destination, device nodes and setuid bits —
    name checking alone does not stop a malicious link member.
    """
    assert_outside_repo(dest)
    os.makedirs(dest, exist_ok=True)

    def ok(name):
        p = os.path.realpath(os.path.join(dest, name))
        if not p.startswith(os.path.realpath(dest) + os.sep):
            raise RuntimeError(f"path traversal blocked: {name}")
        return True

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as z:
            for n in z.namelist():
                ok(n)
            z.extractall(dest)
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as t:
            for m in t.getmembers():
                ok(m.name)
            try:
                t.extractall(dest, filter="data")
            except TypeError:            # Python < 3.12
                t.extractall(dest)
    else:
        return False
    return True


# --- modes --------------------------------------------------------------------

def preflight(reg, dataset_id, root, ack_licenses):
    """Everything a human needs to authorize a download. No network, no write."""
    entry = get_dataset(reg, dataset_id)
    lic = licensing(entry)
    need_ack = acknowledgement_required(entry)
    acknowledged = dataset_id in ack_licenses
    size = expected_size_bytes(entry)
    urls = endpoints_for(dataset_id)
    unresolved = [u for u in urls if u.startswith("TO_CONFIRM:")]
    root_exists = os.path.isdir(root.path)
    free = root.free_bytes()

    blockers = []
    if root.is_repo_local:
        blockers.append(
            "data root is inside the Git repository — pass --data-root or "
            "set CSIA_DATA_ROOT to an external volume")
    if not root_exists:
        blockers.append(f"data root does not exist: {root.path}")
    if need_ack and not acknowledged:
        blockers.append(
            f"restricted licence requires --acknowledge-license {dataset_id}")
    if not urls:
        blockers.append("no download endpoint registered for this dataset")
    if unresolved:
        blockers.append(
            f"{len(unresolved)} endpoint(s) still TO_CONFIRM — resolve the "
            "exact archive URL from the official source page first")
    if size and root_exists and free < size:
        blockers.append(
            f"insufficient free space: need ~{size / (1 << 30):.1f} GiB, "
            f"have {free / (1 << 30):.1f} GiB")

    return {
        "dataset_id": dataset_id,
        "title": entry.get("title", "UNKNOWN"),
        "official_source": entry.get("official_source", "UNKNOWN"),
        "license": lic["license"],
        "commercial_use": lic["commercial_use"],
        "redistribution": lic["redistribution"],
        "citation_required": lic["citation_required"],
        "prohibited_claims": entry.get("prohibited_claims", []),
        "license_acknowledgment_required": need_ack,
        "license_acknowledged": acknowledged,
        "expected_inventory": expected_inventory(entry),
        "expected_size_bytes": size,
        "expected_size_gib": round(size / (1 << 30), 2) if size else None,
        "endpoints": urls,
        "unresolved_endpoints": len(unresolved),
        "data_root": root.path,
        "data_root_source": root.source,
        "data_root_is_repo_local": root.is_repo_local,
        "free_bytes": free,
        "free_gib": round(free / (1 << 30), 2),
        "raw_destination": root.raw_dir(dataset_id),
        "manifest_destination": root.manifests,
        "report_destination": root.report(STATUS_REPORT_NAME),
        "download_authorized": not blockers,
        "blockers": blockers,
    }


def print_preflight(p):
    def yes(b):
        return "YES" if b else "NO"
    size = p["expected_size_gib"]
    print(f"=== preflight: {p['dataset_id']} ===")
    print(f"  title                  {p['title']}")
    print(f"  official source        {p['official_source']}")
    print(f"  license                {p['license']}")
    print(f"  commercial use         {p['commercial_use']}")
    print(f"  redistribution         {p['redistribution']}")
    print(f"  citation required      {yes(p['citation_required'])}")
    print(f"  license ack required   "
          f"{yes(p['license_acknowledgment_required'])}"
          f"   (acknowledged: {yes(p['license_acknowledged'])})")
    print(f"  expected inventory     {p['expected_inventory']}")
    print(f"  expected size          {size if size else 'UNKNOWN'} GiB")
    print(f"  endpoints              {p['endpoints']}")
    print(f"  data root              {p['data_root']}  "
          f"[{p['data_root_source']}]")
    print(f"  free disk space        {p['free_gib']} GiB "
          f"({p['free_bytes']} bytes)")
    print(f"  raw destination        {p['raw_destination']}")
    print(f"  manifest destination   {p['manifest_destination']}")
    print(f"  report destination     {p['report_destination']}")
    print(f"  DOWNLOAD AUTHORIZED    {yes(p['download_authorized'])}")
    for b in p["blockers"]:
        print(f"    blocker: {b}")
    for c in p.get("prohibited_claims", []):
        print(f"    prohibited claim: {c}")


def status_of(reg, dataset_id, root):
    """Registry-declared status + what is on disk. No network, no write."""
    entry = get_dataset(reg, dataset_id)
    acq = entry.get("acquisition") or {}
    raw_dir = root.raw_dir(dataset_id)
    hashes = []
    if os.path.isdir(raw_dir):
        hashes = sorted(h for h in os.listdir(raw_dir) if len(h) == 64)
    return {
        "dataset": dataset_id,
        "title": entry.get("title", "UNKNOWN"),
        "registry_status": acq.get("status", "UNKNOWN"),
        "registry_error": acq.get("error"),
        "license_acknowledgment_required": acknowledgement_required(entry),
        "raw_destination": raw_dir,
        "locally_present_hashes": hashes,
        "status": "PRESENT" if hashes else acq.get("status", "NOT_ACQUIRED"),
        "attempts": [],
        "files": [],
    }


def acquire(reg, dataset_id, root, ack_licenses, dry_run=False):
    entry = get_dataset(reg, dataset_id)
    rec = {"dataset": dataset_id, "attempts": [], "files": []}

    if acknowledgement_required(entry) and dataset_id not in ack_licenses:
        rec["status"] = "LICENSE_ACK_REQUIRED"
        rec["note"] = ("restricted licence: review, then pass "
                       f"--acknowledge-license {dataset_id}")
        return rec

    urls = endpoints_for(dataset_id)
    if dry_run:
        rec["status"] = "DRY_RUN"
        rec["would_download"] = urls
        rec["would_write_raw_to"] = root.raw_dir(dataset_id)
        rec["note"] = "dry run: no request issued, no payload written"
        return rec

    store = RawStore(assert_outside_repo(root.raw))
    cache = os.path.join(root.cache, dataset_id)
    got = 0
    for url in urls:
        att, payload = probe(url, cache_dir=cache)
        rec["attempts"].append(att)
        if payload is None:
            continue
        if isinstance(payload, bytes):
            os.makedirs(cache, exist_ok=True)
            fname = url.split("/")[-1].split("=")[-1] or "download.bin"
            tpath = os.path.join(cache, fname)
            with open(tpath, "wb") as fh:
                fh.write(payload)
        else:
            tpath = payload
        # hash BEFORE any extraction or normalization; RawStore is write-once
        ing = store.ingest(tpath, dataset_id)
        os.remove(tpath)
        rec["files"].append({"source_url": url, "sha256": ing["sha256"],
                             "stored": ing["path"],
                             "ingest_status": ing["status"],
                             "acquired_utc": att["ts_utc"],
                             "bytes": att.get("bytes")})
        got += 1
    rec["status"] = ("COMPLETE" if got and got == len(urls) else
                     "PARTIAL" if got else "ALL_ATTEMPTS_FAILED")
    return rec


# --- CLI ----------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        prog="acquire_public_datasets.py",
        description="Acquire registered public datasets into the CSIA data "
                    "lake. Payload never lands inside the Git repository.")
    ap.add_argument("--dataset", action="append", default=[], metavar="ID",
                    help="registry dataset id (repeatable)")
    ap.add_argument("--all", action="store_true",
                    help="select every registered dataset")
    ap.add_argument("--data-root", default=None, metavar="PATH",
                    help="data lake root; overrides CSIA_DATA_ROOT")
    ap.add_argument("--registry", default=None, metavar="PATH",
                    help="override the registry file (tests)")
    ap.add_argument("--status-only", action="store_true",
                    help="report registry + on-disk state; no network, no "
                         "repository write")
    ap.add_argument("--preflight", action="store_true",
                    help="print everything needed to authorize a download")
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve and plan, but issue no request and write "
                         "no payload")
    ap.add_argument("--acknowledge-license", action="append", default=[],
                    metavar="ID", help="acknowledge a restricted licence")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable output on stdout")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reg = load_registry(args.registry)
        names = select_datasets(reg, args.dataset, args.all)
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    root = resolve_data_root(args.data_root)
    ack = set(args.acknowledge_license)

    # --- preflight: read-only; writes nothing, anywhere ----------------------
    if args.preflight:
        reports = [preflight(reg, n, root, ack) for n in names]
        if args.json:
            print(json.dumps(reports, indent=1, sort_keys=True))
        else:
            for p in reports:
                print_preflight(p)
        return 0 if all(p["download_authorized"] for p in reports) else 1

    mode = ("status-only" if args.status_only
            else "dry-run" if args.dry_run else "acquire")

    # Acquisition and dry-run plans must target an external root. Status-only
    # is read-only, so it tolerates the repo-local fixture fallback.
    if mode != "status-only":
        try:
            need = max((expected_size_bytes(get_dataset(reg, n)) or 0)
                       for n in names) or None
            require_external_data_root(root, None if args.dry_run else need)
        except DataRootError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    out = {
        "generated_utc": _now(),
        "mode": mode,
        "registry_version": reg["registry_version"],
        "registry_path": reg["path"],
        "registry_dataset_count": len(reg["datasets"]),
        "data_root": root.path,
        "data_root_source": root.source,
        "environment_note": "acquisition failures below are recorded "
                            "verbatim; the same command runs unmodified on "
                            "an unrestricted host",
        "datasets": {},
    }
    for n in names:
        out["datasets"][n] = (
            status_of(reg, n, root) if mode == "status-only"
            else acquire(reg, n, root, ack, dry_run=args.dry_run))

    # Runtime reports live under the data root, never in the repository. The
    # committed datasets/reports/acquisition_status_v1.json stays a static
    # schema fixture and is not rewritten by any run.
    dest = root.report(STATUS_REPORT_NAME)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)

    if args.json:
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0

    n_sel = len(out["datasets"])
    complete = sum(1 for d in out["datasets"].values()
                   if d.get("status") in ("COMPLETE", "PRESENT"))
    print(f"registry: {len(reg['datasets'])} datasets ({reg['path']})")
    print(f"data root: {root.path}  [{root.source}]")
    print(f"acquisition: {complete}/{n_sel} complete -> {dest}")
    for n, d in out["datasets"].items():
        print(f"  {n:22s} {d.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
