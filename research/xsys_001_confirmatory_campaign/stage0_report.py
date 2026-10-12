#!/usr/bin/env python3
"""XSYS-001 confirmatory campaign: Stage 0 custody report (sealed before Stage 1).

Operational record-keeping only. It summarizes what the FROZEN stage 0
(amendment_a1/pipeline_a1/stage0_prepare_a1.py with the A2 manifest) produced:
flights and analysis trials included or excluded with their reasons, every
manipulation and logging check, the matched pairs, the blinded stage-1 inputs
and their hashes, and the SHA-256 of the label key. The key's CONTENT is never
copied here; stage 1 never receives this report or the key.

Usage: stage0_report.py --qc QC.json --key KEY.json --blind <blind dir> --out STAGE0_REPORT.json
"""
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
A1 = REPO / "research" / "xsys_confirmatory_001" / "amendment_a1"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qc", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--blind", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    qc = json.loads(Path(a.qc).read_text())
    blind = Path(a.blind)
    analysis = list(csv.DictReader(open(A1 / "ANALYSIS_MATRIX_A1.csv")))
    fl = qc["flights"]
    at = qc["analysis_trials"]
    pairs = sorted({r["pair_id"] for r in analysis if r["pair_id"]})
    pair_trials = {p: [r["analysis_id"] for r in analysis if r["pair_id"] == p] for p in pairs}
    valid_pairs = [p for p, ids in pair_trials.items() if all(at[i]["decision"] == "INCLUDED" for i in ids)]
    index = json.loads((blind / "INDEX.json").read_text())
    npz = sorted(blind.glob("*.npz"))
    checks = {}
    for fid, f in fl.items():
        checks[fid] = {k: v for k, v in f.get("checks", {}).items()}
    mc_names = sorted({k for f in fl.values() for k in f.get("checks", {}) if k.startswith(("Q_", "MC_"))})
    mc_pass = {k: sum(1 for f in fl.values() if f.get("checks", {}).get(k) is True) for k in mc_names}
    mc_fail = {k: sorted(fid for fid, f in fl.items() if f.get("checks", {}).get(k) is False) for k in mc_names}
    b_checks = {aid: t.get("checks", {}) for aid, t in at.items() if t.get("checks")}
    rep = {
        "campaign_id": "XSYS-001-CONFIRMATORY",
        "record": "STAGE 0 CUSTODY REPORT - sealed before stage 1; contains no CSIA outcome and no label key content",
        "stage0_mode": qc["mode"], "stage0_manifest_sha256": qc["freeze_manifest_sha256"],
        "campaign_terminated": qc.get("campaign_terminated"),
        "tolerances": qc["tolerances"],
        "expected_flights": 66, "attempted_flights": len(fl),
        "valid_flights": sorted(f for f, v in fl.items() if v["decision"] == "INCLUDED"),
        "excluded_flights": {f: v["reason"] for f, v in fl.items() if v["decision"] != "INCLUDED"},
        "expected_analysis_trials": len(analysis),
        "included_analysis_trials": sum(1 for t in at.values() if t["decision"] == "INCLUDED"),
        "excluded_analysis_trials": {aid: t["reason"] for aid, t in at.items() if t["decision"] != "INCLUDED"},
        "expected_matched_pairs": len(pairs), "valid_matched_pairs": len(valid_pairs),
        "excluded_matched_pairs": sorted(set(pairs) - set(valid_pairs)),
        "manipulation_checks": {"passed_count": mc_pass, "failed_flights": mc_fail, "per_flight": checks},
        "case_b_construction_checks": b_checks,
        "stage1_inputs": {"opaque_count": len(npz), "index_count": len(index),
                          "index_sha256": sha256(blind / "INDEX.json"),
                          "npz_sha256": {p.stem: sha256(p) for p in npz},
                          "npz_bytes_total": sum(p.stat().st_size for p in npz)},
        "label_key_sha256": sha256(a.key),
        "qc_sha256": sha256(a.qc),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    Path(a.out).write_text(json.dumps(rep, indent=1, default=float) + "\n")
    digest = sha256(a.out)
    Path(a.out).with_suffix(".sha256").write_text(f"{digest}  {Path(a.out).name}\n")
    print(json.dumps({k: rep[k] for k in ("attempted_flights", "excluded_flights", "included_analysis_trials",
                                          "excluded_analysis_trials", "expected_matched_pairs", "valid_matched_pairs",
                                          "excluded_matched_pairs")}
                     | {"failed_checks": {k: v for k, v in mc_fail.items() if v},
                        "stage1_inputs": rep["stage1_inputs"]["opaque_count"], "report_sha256": digest}, indent=1))


if __name__ == "__main__":
    main()
