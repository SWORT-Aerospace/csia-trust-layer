#!/usr/bin/env python3
"""XSYS-001 confirmatory campaign: completion record and raw-data manifest.

Operational record-keeping only. Runs AFTER every frozen flight has been
attempted and BEFORE stage 0. It reads the executor's own records, hashes
every raw file, verifies the xz archive copy of every ULog by decompression
(the copies are made beforehand with xz -9e; the originals are kept), and
seals the completion record. It contains no CSIA outcome and
computes none.

Usage: seal_campaign.py --raw <raw-artifact dir> --records <this directory>
"""
import argparse
import csv
import hashlib
import json
import lzma
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
A1 = REPO / "research" / "xsys_confirmatory_001" / "amendment_a1"
A2 = REPO / "research" / "xsys_confirmatory_001" / "amendment_a2"
CAMPAIGN_ID = "XSYS-001-CONFIRMATORY"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--records", required=True)
    a = ap.parse_args()
    raw = Path(a.raw)
    fl = raw / "flights"
    rec_dir = Path(a.records)
    matrix = list(csv.DictReader(open(A1 / "FLIGHT_MATRIX_A1.csv")))
    order = [r["flight_id"] for r in csv.DictReader(open(A1 / "EXECUTION_ORDER_A1.csv"))]
    camp = json.loads((fl / "CAMPAIGN.json").read_text())
    log = [json.loads(line) for line in (fl / "EXECUTION_LOG.jsonl").read_text().splitlines()]
    a2m = json.loads((A2 / "FREEZE_MANIFEST_A2.json").read_text())

    attempts = {}
    for e in log:
        attempts.setdefault(e["flight_id"], []).append({k: e[k] for k in ("attempt", "ok", "returncode", "wall_s")})
    flights, raw_files = [], []
    xz_dir = raw / "flights_xz"
    xz_dir.mkdir(exist_ok=True)
    for fid in order:
        ulg, js, con = fl / f"{fid}.ulg", fl / f"{fid}.json", fl / f"{fid}.console.txt"
        entry = {"flight_id": fid, "attempts": attempts.get(fid, []), "ulog_present": ulg.exists()}
        if ulg.exists():
            rec = json.loads(js.read_text())
            u_sha = sha256(ulg)
            entry.update({"ulog_sha256": u_sha, "ulog_bytes": ulg.stat().st_size,
                          "record_ulog_sha256_matches": rec.get("ulog_sha256") == u_sha,
                          "record_manifest_sha256": rec["extra"].get("freeze_manifest_sha256"),
                          "px4_sha256": rec.get("px4_sha256")})
            xz = xz_dir / f"{fid}.ulg.xz"
            if not xz.exists():
                raise SystemExit(f"{xz} missing: compress first (xz -9e, originals kept)")
            with lzma.open(xz, "rb") as z:
                h = hashlib.sha256()
                for c in iter(lambda: z.read(1 << 20), b""):
                    h.update(c)
            entry["xz_roundtrip_ok"] = h.hexdigest() == u_sha
            for p, kind in ((ulg, "ulog"), (xz, "ulog.xz"), (js, "trial_record"), (con, "console")):
                if p.exists():
                    raw_files.append({"campaign_id": CAMPAIGN_ID, "trial_id": fid, "kind": kind,
                                      "filename": p.name, "location": str(p), "sha256": sha256(p),
                                      "bytes": p.stat().st_size})
        flights.append(entry)
    for p in (fl / "CAMPAIGN.json", fl / "EXECUTION_LOG.jsonl"):
        raw_files.append({"campaign_id": CAMPAIGN_ID, "trial_id": "", "kind": "campaign_record", "filename": p.name,
                          "location": str(p), "sha256": sha256(p), "bytes": p.stat().st_size})

    ok = [f for f in flights if f["ulog_present"]]
    completion = {
        "campaign_id": CAMPAIGN_ID,
        "record": "CAMPAIGN COMPLETION - operational only, no CSIA outcome",
        "protocol_manifests": {"XSYS-001": a2m["grandparent_manifest"]["sha256"],
                               "XSYS-001-A1": a2m["parent_manifest"]["sha256"],
                               "XSYS-001-A2": sha256(A2 / "FREEZE_MANIFEST_A2.json")},
        "campaign_json_manifest_sha256": camp["freeze_manifest_sha256"],
        "expected_flights": len(matrix),
        "attempted_flights": sum(1 for f in flights if f["attempts"]),
        "successful_operational_runs": len(ok),
        "failed_operational_runs": [f["flight_id"] for f in flights if f["attempts"] and not f["ulog_present"]],
        "never_attempted": [f["flight_id"] for f in flights if not f["attempts"]],
        "retries": [f["flight_id"] for f in flights if len(f["attempts"]) > 1],
        "attempt_log_entries": len(log),
        "final_flight_ids": [f["flight_id"] for f in ok],
        "source": {"px4_commit": camp["px4_commit"], "source_verified": camp["source_verified"],
                   "patch_file": a2m["px4"]["patch_file"], "patch_sha256": a2m["px4"]["patch_sha256"]},
        "px4_binary_sha256": camp["px4_sha256"],
        "all_flights_used_campaign_binary": all(f.get("px4_sha256") == camp["px4_sha256"] for f in ok),
        "all_records_carry_A2_manifest": all(f.get("record_manifest_sha256") == camp["freeze_manifest_sha256"] for f in ok),
        "all_record_ulog_hashes_match": all(f.get("record_ulog_sha256_matches") for f in ok),
        "all_xz_roundtrips_ok": all(f.get("xz_roundtrip_ok") for f in ok),
        "flight_matrix_sha256": sha256(A1 / "FLIGHT_MATRIX_A1.csv"),
        "analysis_matrix_sha256": sha256(A1 / "ANALYSIS_MATRIX_A1.csv"),
        "execution_order_sha256": sha256(A1 / "EXECUTION_ORDER_A1.csv"),
        "start_utc": (raw / "CAMPAIGN_START_UTC.txt").read_text().strip(),
        "completion_utc": (raw / "CAMPAIGN_END_UTC.txt").read_text().strip(),
        "executor_exit": (raw / "executor.log").read_text().strip().splitlines()[-1],
        "raw_log_hashes": {f["flight_id"]: f.get("ulog_sha256") for f in flights},
        "flights": flights,
        "sealed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    manifest = {"campaign_id": CAMPAIGN_ID, "raw_artifact_location": str(raw),
                "note": ("raw ULogs are NOT in git history (authorization: 'Do not automatically commit huge raw "
                         "ULogs'); this manifest records every raw file by name, SHA-256, size, campaign and trial"),
                "files": raw_files, "total_bytes": sum(f["bytes"] for f in raw_files),
                "ulog_bytes": sum(f["bytes"] for f in raw_files if f["kind"] == "ulog"),
                "ulog_xz_bytes": sum(f["bytes"] for f in raw_files if f["kind"] == "ulog.xz")}
    rec_dir.mkdir(parents=True, exist_ok=True)
    (rec_dir / "campaign").mkdir(exist_ok=True)
    (rec_dir / "campaign" / "records").mkdir(exist_ok=True)
    shutil.copy(fl / "CAMPAIGN.json", rec_dir / "campaign" / "CAMPAIGN.json")
    shutil.copy(fl / "EXECUTION_LOG.jsonl", rec_dir / "campaign" / "EXECUTION_LOG.jsonl")
    for f in ok:
        shutil.copy(fl / f"{f['flight_id']}.json", rec_dir / "campaign" / "records" / f"{f['flight_id']}.json")
    (rec_dir / "RAW_DATA_MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
    completion["raw_data_manifest_sha256"] = sha256(rec_dir / "RAW_DATA_MANIFEST.json")
    (rec_dir / "CAMPAIGN_COMPLETION.json").write_text(json.dumps(completion, indent=1) + "\n")
    digest = sha256(rec_dir / "CAMPAIGN_COMPLETION.json")
    (rec_dir / "CAMPAIGN_COMPLETION.sha256").write_text(f"{digest}  CAMPAIGN_COMPLETION.json\n")
    print(json.dumps({k: completion[k] for k in ("expected_flights", "attempted_flights", "successful_operational_runs",
                                                 "failed_operational_runs", "never_attempted", "retries",
                                                 "all_flights_used_campaign_binary", "all_records_carry_A2_manifest",
                                                 "all_record_ulog_hashes_match", "all_xz_roundtrips_ok")}
                     | {"completion_sha256": digest, "ulog_GB": round(manifest["ulog_bytes"] / 1e9, 2),
                        "xz_GB": round(manifest["ulog_xz_bytes"] / 1e9, 2)}, indent=1))


if __name__ == "__main__":
    main()
