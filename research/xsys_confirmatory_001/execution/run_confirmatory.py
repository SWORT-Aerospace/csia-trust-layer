#!/usr/bin/env python3
"""XSYS-001 confirmatory executor. Consumes the FROZEN matrix; generates nothing.

Before the first flight it refuses to start unless:
  1. every file listed in the freeze manifest has its frozen SHA-256;
  2. the PX4 source tree is commit 547e2caa9883bc1609325f02b4914b4e2482fe62
     plus exactly the frozen SIH patch (its diff is compared with the frozen
     patch's diff, byte for byte);
  3. the build's bin/px4 exists. Its SHA-256 is recorded ONCE in
     CAMPAIGN.json; stage 0 then requires every flight to have used it.

It flies the flights in EXECUTION_ORDER.csv order, never another order, with
the parameters of their FLIGHT_MATRIX.csv row, never others. It is resumable:
a flight whose record exists under the same manifest is not flown again.

Technical failures (the driver exits non-zero or leaves no ULog) are retried
ONCE with the identical configuration; both attempts are logged. Three
consecutive technical failures stop the campaign. Nothing here reads a
verdict, a witness or any outcome, so nothing here can stop on a result.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PX4_COMMIT = "547e2caa9883bc1609325f02b4914b4e2482fe62"
MAX_CONSECUTIVE_TECH_FAILURES = 3


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def verify_manifest(manifest_path):
    m = json.loads(Path(manifest_path).read_text())
    bad = [rel for rel, want in m["frozen_files"].items() if sha256(REPO / rel) != want]
    if bad:
        raise SystemExit(f"FREEZE VIOLATION: files differ from the freeze manifest: {bad}")
    return m, sha256(manifest_path)


def patch_diff_body(text):
    """The diff part of a git format-patch file, without mail headers or the
    trailing version signature."""
    start = text.index("diff --git")
    end = text.rfind("\n-- \n")
    return text[start:end if end > start else len(text)].rstrip() + "\n"


def _git(px4_src, *args):
    p = subprocess.run(["git", "-C", str(px4_src), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"PX4 source: git {' '.join(args)} failed: {p.stderr.strip()[:200]}")
    return p.stdout


def verify_source(px4_src, patch_file):
    head_parent = _git(px4_src, "rev-parse", "HEAD^").strip()
    if head_parent != PX4_COMMIT:
        raise SystemExit(f"PX4 source: HEAD^ is {head_parent}, not {PX4_COMMIT}")
    if _git(px4_src, "status", "--porcelain", "--untracked-files=no").strip():
        raise SystemExit("PX4 source: working tree has uncommitted changes")
    got = _git(px4_src, "diff", PX4_COMMIT, "HEAD")
    want = patch_diff_body(Path(patch_file).read_text())
    if got.rstrip() + "\n" != want:
        raise SystemExit("PX4 source: the diff from 547e2ca is not exactly the frozen SIH patch")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(REPO / "research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json"))
    ap.add_argument("--px4-src", required=True, help="PX4 tree at 547e2ca + the frozen patch, committed")
    ap.add_argument("--build", required=True, help="<px4-src>/build/px4_sitl_default")
    ap.add_argument("--out", required=True, help="directory receiving <flight_id>.ulg/.json")
    ap.add_argument("--work", required=True)
    ap.add_argument("--dry-run", action="store_true", help="verify and print the commands; fly nothing")
    a = ap.parse_args()

    manifest, manifest_sha = verify_manifest(a.manifest)
    prereg = REPO / "research/xsys_confirmatory_001/prereg"
    verify_source(a.px4_src, REPO / manifest["px4"]["patch_file"])
    binary = Path(a.build) / "bin" / "px4"
    if not binary.exists():
        raise SystemExit(f"no PX4 binary at {binary}")
    rows = {r["flight_id"]: r for r in csv.DictReader(open(prereg / "FLIGHT_MATRIX.csv"))}
    order = [r["flight_id"] for r in csv.DictReader(open(prereg / "EXECUTION_ORDER.csv"))]
    if sorted(order) != sorted(rows):
        raise SystemExit("EXECUTION_ORDER.csv is not a permutation of FLIGHT_MATRIX.csv")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    campaign_path = out / "CAMPAIGN.json"
    bin_sha = sha256(binary)
    if campaign_path.exists():
        camp = json.loads(campaign_path.read_text())
        if camp["freeze_manifest_sha256"] != manifest_sha or camp["px4_sha256"] != bin_sha:
            raise SystemExit("CAMPAIGN.json belongs to another manifest or binary: refusing to mix campaigns")
    else:
        camp = {"freeze_manifest_sha256": manifest_sha, "px4_sha256": bin_sha, "px4_commit": PX4_COMMIT,
                "source_verified": True, "started_unix": time.time(), "dry_run": a.dry_run,
                "binary_equals_reference_build_informational":
                    bin_sha == manifest["px4"]["reference_binary_sha256_informational"],
                "python": sys.version.split()[0]}
        if not a.dry_run:
            campaign_path.write_text(json.dumps(camp, indent=1))
    log = out / "EXECUTION_LOG.jsonl"
    consecutive = 0
    py = sys.executable
    for pos, fid in enumerate(order, 1):
        r = rows[fid]
        rec_path = out / f"{fid}.json"
        if rec_path.exists() and (out / f"{fid}.ulg").exists():
            if json.loads(rec_path.read_text())["extra"].get("freeze_manifest_sha256") != manifest_sha:
                raise SystemExit(f"{fid}: existing record was produced under another manifest")
            continue
        extra = {"flight_id": fid, "position": pos, "freeze_manifest_sha256": manifest_sha,
                 "condition": r["condition"], "nuisance_id": r["nuisance_id"]}
        for attempt in (1, 2):
            cmd = [py, str(HERE / "xsys_run_trial.py"), "--build", a.build, "--workdir", str(Path(a.work) / fid),
                   "--out", str(out), "--name", fid, "--heading-deg", r["heading_deg"],
                   "--onset-param", r["onset_param"], "--onset-value", r["onset_value"],
                   "--t-arm", r["t_arm_s"], "--t-onset", r["t_onset_s"], "--t-end", r["t_end_s"],
                   "--speed", "1", "--instance", "0", "--extra-json", json.dumps({**extra, "attempt": attempt})]
            if a.dry_run:
                print(" ".join(cmd[1:4]), fid, r["heading_deg"], r["onset_param"], r["onset_value"], r["t_onset_s"])
                break
            t0 = time.time()
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            ok = p.returncode == 0 and (out / f"{fid}.ulg").exists()
            with open(log, "a") as f:
                f.write(json.dumps({"flight_id": fid, "position": pos, "attempt": attempt, "returncode": p.returncode,
                                    "ok": ok, "wall_s": round(time.time() - t0, 1),
                                    "stderr_tail": p.stderr[-400:]}) + "\n")
            if ok:
                consecutive = 0
                break
            consecutive += 1
            if consecutive >= MAX_CONSECUTIVE_TECH_FAILURES:
                raise SystemExit(f"campaign stopped: {consecutive} consecutive technical failures (at {fid})")
    print(json.dumps({"flights_in_order": len(order), "manifest_sha256": manifest_sha, "px4_sha256": bin_sha,
                      "source_verified": True, "dry_run": a.dry_run,
                      "binary_equals_reference_build": camp["binary_equals_reference_build_informational"]
                      if "binary_equals_reference_build_informational" in camp else None}))


if __name__ == "__main__":
    main()
