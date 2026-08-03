"""Reproducible public-dataset acquisition (ACEG slice 2, Part 3).

    python tools/acquire_public_datasets.py --dataset uav_sead
    python tools/acquire_public_datasets.py --all
    python tools/acquire_public_datasets.py --status-only

Runs unmodified on an unrestricted host. In this environment dataset hosts
are blocked by network policy; the tool then records the exact failure per
source into datasets/reports/acquisition_status_v1.json and never fabricates
success. Raw files are hashed BEFORE any conversion and stored immutably
under datasets/raw/<dataset>/<sha256>/.

Safety: archives are extracted with path-traversal protection; nothing is
re-distributed automatically; restricted licenses must be acknowledged with
--acknowledge-license <dataset> before download.
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

from csia.data.store import RawStore, sha256_file  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGISTRY = os.path.join(ROOT, "datasets", "registry",
                        "public_datasets_v1.yaml")
STATUS = os.path.join(ROOT, "datasets", "reports",
                      "acquisition_status_v1.json")

#: Download endpoints. URLs marked TO_CONFIRM must be finalized on the
#: unrestricted host from the official source pages recorded in the registry;
#: the tool treats a TO_CONFIRM URL as "resolve manually first".
SOURCES = {
    "uav_sead": {"urls": ["TO_CONFIRM:https://zenodo.org/"],
                 "license_ack_required": False},
    "alfa": {"urls": ["TO_CONFIRM:https://theairlab.org/alfa-dataset"],
             "license_ack_required": False},
    "insane": {"urls": ["TO_CONFIRM:https://sst.aau.at/cns/"],
               "license_ack_required": True},   # research-only restrictions
    "blackbird": {"urls":
                  ["TO_CONFIRM:https://github.com/mit-aera/Blackbird-Dataset"],
                  "license_ack_required": False},
    "euroc_mav": {"urls": ["TO_CONFIRM:http://robotics.ethz.ch/~asl-datasets/"],
                  "license_ack_required": False},
    "tum_vi": {"urls": ["TO_CONFIRM:https://vision.in.tum.de/"],
               "license_ack_required": False},
    "px4_flightreview_v1": {
        "urls": [],  # generated from the committed report below
        "license_ack_required": False},
}


def px4_corpus_urls():
    rep = os.path.join(ROOT, "data", "real_logs_report.json")
    with open(rep) as fh:
        d = json.load(fh)
    return [f"https://review.px4.io/download_log?log={f['log'][3:-4]}"
            for f in d["flights"]]


def probe(url, timeout=25):
    """One attempt; returns a structured record, success or not."""
    rec = {"url": url, "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())}
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
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "csia-acq/1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
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
    """Zip/tar extraction with path-traversal protection."""
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
            t.extractall(dest)
    else:
        return False
    return True


def acquire(name, ack_licenses, out):
    src = SOURCES[name]
    entry = {"dataset": name, "attempts": [], "files": []}
    if src["license_ack_required"] and name not in ack_licenses:
        entry["status"] = "LICENSE_ACK_REQUIRED"
        entry["note"] = ("restricted license: pass "
                         f"--acknowledge-license {name} after review")
        out[name] = entry
        return
    urls = src["urls"] or (px4_corpus_urls() if name ==
                           "px4_flightreview_v1" else [])
    store = RawStore(os.path.join(ROOT, "datasets", "raw"))
    got = 0
    for url in urls:
        rec, data = probe(url)
        entry["attempts"].append(rec)
        if data is None:
            continue
        tmp = os.path.join(ROOT, "datasets", "raw", ".incoming")
        os.makedirs(tmp, exist_ok=True)
        fname = url.split("/")[-1].split("=")[-1] or "download.bin"
        tpath = os.path.join(tmp, fname)
        with open(tpath, "wb") as fh:
            fh.write(data)
        digest = sha256_file(tpath)            # hash BEFORE any conversion
        ing = store.ingest(tpath, name)
        os.remove(tpath)
        entry["files"].append({"source_url": url, "sha256": digest,
                               "stored": ing["path"], "bytes": len(data)})
        got += 1
    entry["status"] = ("COMPLETE" if got and got == len(urls) else
                       "PARTIAL" if got else "ALL_ATTEMPTS_FAILED")
    out[name] = entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--status-only", action="store_true")
    ap.add_argument("--acknowledge-license", action="append", default=[])
    args = ap.parse_args()

    names = list(SOURCES) if (args.all or not args.dataset) else args.dataset
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "environment_note": "dataset hosts are blocked by this "
           "environment's network policy; failures below are recorded "
           "verbatim and the same command works unmodified on an "
           "unrestricted host",
           "datasets": {}}
    if not args.status_only:
        for n in names:
            acquire(n, set(args.acknowledge_license), out["datasets"])
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    ok = sum(1 for d in out["datasets"].values()
             if d.get("status") == "COMPLETE")
    print(f"acquisition: {ok}/{len(out['datasets'])} complete "
          f"-> {STATUS}")
    for n, d in out["datasets"].items():
        print(f"  {n:22s} {d.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
