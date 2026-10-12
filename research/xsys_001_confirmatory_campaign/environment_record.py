#!/usr/bin/env python3
"""XSYS-001 confirmatory campaign: environment and version record.

Operational record-keeping only. It captures the software and machine the
campaign and its analysis ran on, and compares the Python stack with the
reference environment the A2 manifest records.

Usage: environment_record.py --px4-src <dir> --px4-binary <path> --out ENVIRONMENT.json
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
A2 = REPO / "research" / "xsys_confirmatory_001" / "amendment_a2" / "FREEZE_MANIFEST_A2.json"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--px4-src", required=True)
    ap.add_argument("--px4-binary", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ref = json.loads(A2.read_text())["reference_environment_informational"]
    vers = {}
    for pkg in ("numpy", "scipy", "pyulog", "pymavlink"):
        try:
            vers[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            vers[pkg] = None
    vers["python"] = platform.python_version()
    cpu = ""
    try:
        cpu = next(ln.split(":", 1)[1].strip() for ln in Path("/proc/cpuinfo").read_text().splitlines()
                   if ln.startswith("model name"))
    except (OSError, StopIteration):
        pass
    rec = {
        "campaign_id": "XSYS-001-CONFIRMATORY",
        "record": "ENVIRONMENT AND VERSIONS of the confirmatory campaign and its analysis",
        "python_executable": sys.executable,
        "versions": vers,
        "reference_environment_informational_A2": ref,
        "python_stack_equals_reference": all(vers.get(k) == v for k, v in ref.items()),
        "px4": {"source_head": git("rev-parse", "HEAD", cwd=a.px4_src),
                "source_head_parent": git("rev-parse", "HEAD^", cwd=a.px4_src),
                "source_status_clean": git("status", "--porcelain", "--untracked-files=no", cwd=a.px4_src) == "",
                "binary_sha256": sha256(a.px4_binary)},
        "repository_head": git("rev-parse", "HEAD", cwd=REPO),
        "machine": {"platform": platform.platform(), "machine": platform.machine(), "cpu_model": cpu,
                    "logical_cpus": os.cpu_count()},
        "strace": subprocess.run(["strace", "-V"], capture_output=True, text=True).stdout.splitlines()[:1],
        "xz": subprocess.run(["xz", "--version"], capture_output=True, text=True).stdout.splitlines()[:1],
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "execution_note": ("an ephemeral cloud container; PX4 SIH lockstep at 250 Hz, speed factor 1; "
                           "the raw-artifact directory is local to this container"),
    }
    Path(a.out).write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({"python_stack_equals_reference": rec["python_stack_equals_reference"], **rec["px4"]}, indent=1))


if __name__ == "__main__":
    main()
