#!/usr/bin/env python3
"""Verify the XSYS-001 confirmatory raw data on this branch (standard library only).

For each of the 66 flights in campaign_records/CAMPAIGN_COMPLETION.json:
  - flights_xz/<flight>.ulg.xz has the SHA-256 the completion record gives;
  - decompressing it reproduces the ORIGINAL raw ULog SHA-256 the completion
    record gives (so the raw ULog is recoverable bit for bit);
  - the trial record and console log match RAW_DATA_MANIFEST.json.
It also checks that CAMPAIGN_COMPLETION.json matches its sealed hash.

Usage: python3 verify_raw_data.py [--restore <dir>]   (--restore also writes the .ulg files)
"""
import argparse
import hashlib
import json
import lzma
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore")
    a = ap.parse_args()
    rec = HERE / "campaign_records"
    comp_p = rec / "CAMPAIGN_COMPLETION.json"
    ok_seal = sha(comp_p) == (rec / "CAMPAIGN_COMPLETION.sha256").read_text().split()[0]
    comp = json.loads(comp_p.read_text())
    man = json.loads((rec / "RAW_DATA_MANIFEST.json").read_text())
    by_name = {f["filename"]: f["sha256"] for f in man["files"]}
    out = Path(a.restore) if a.restore else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    bad = []
    for f in comp["flights"]:
        fid = f["flight_id"]
        xz = HERE / "flights_xz" / f"{fid}.ulg.xz"
        if not xz.exists() or sha(xz) != f["ulog_xz_sha256"]:
            bad.append((fid, "xz hash"))
            continue
        h = hashlib.sha256()
        sink = open(out / f"{fid}.ulg", "wb") if out else None
        with lzma.open(xz, "rb") as z:
            for c in iter(lambda: z.read(1 << 20), b""):
                h.update(c)
                if sink:
                    sink.write(c)
        if sink:
            sink.close()
        if h.hexdigest() != f["ulog_sha256"]:
            bad.append((fid, "decompressed raw hash"))
        for sub, name in (("trial_records", f"{fid}.json"), ("console_logs", f"{fid}.console.txt")):
            if sha(HERE / sub / name) != by_name.get(name):
                bad.append((fid, name))
    res = {"completion_record_matches_seal": ok_seal, "flights_checked": len(comp["flights"]),
           "failures": bad, "ok": ok_seal and not bad and len(comp["flights"]) == 66}
    print(json.dumps(res, indent=1))
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
