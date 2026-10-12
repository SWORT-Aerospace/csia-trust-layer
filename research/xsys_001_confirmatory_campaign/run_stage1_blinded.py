#!/usr/bin/env python3
"""XSYS-001 confirmatory campaign: run the FROZEN stage 1 once, blinded, and
verify programmatically that it could not resolve the label source.

Operational wrapper only. It does not change stage 1: it runs
research/xsys_confirmatory_001/pipeline/stage1_evidence.py unchanged, with
--freeze-manifest set to the A2 manifest, as a subprocess under strace. It
then records the seal. It computes no outcome and never opens the label key.
It only hashes the key file, taking the path from the stage 0 report.

Blindness checks:
  B1  the blind directory holds only INDEX.json plus one <16 hex>.npz per id
  B2  every npz holds exactly the frozen ONBOARD_KEYS as numeric arrays. It
      holds no string or object array, so no label or file name can ride along
  B3  every input starts at t_rel = -5 s (the same cut for every kind)
  B4  the opaque ids are salted. No unsalted SHA-256 of an analysis id or
      flight id gives any of them
  B5  static: stage1_evidence.py names neither the key nor QC, nor the flight
      directory or any file-time attribute
  B6  dynamic (strace, every file syscall of every thread): stage 1 touched no
      forbidden path. Forbidden means:
        - the stage 0 custody directory (key, QC);
        - the raw flight and xz directories;
        - the PX4 work directories;
        - this campaign's record directory, apart from its own output;
        - any file named KEY.json or QC.json
  B7  the key file lies outside every directory stage 1 was given

Usage: run_stage1_blinded.py --blind <dir> --out <dir>/STAGE1.json --custody <stage 0 custody dir>
                             --raw <raw-artifact root> --stage0-report STAGE0_REPORT.json
"""
import argparse
import ast
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
X = REPO / "research" / "xsys_confirmatory_001"
STAGE1 = X / "pipeline" / "stage1_evidence.py"
STAGE0 = X / "pipeline" / "stage0_prepare.py"
CAL = X / "calibration" / "CALIBRATION.json"
A2_MANIFEST = X / "amendment_a2" / "FREEZE_MANIFEST_A2.json"
A1_MATRIX = X / "amendment_a1" / "ANALYSIS_MATRIX_A1.csv"
A1_FLIGHTS = X / "amendment_a1" / "FLIGHT_MATRIX_A1.csv"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def frozen_constant(path, name):
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def under(p, root):
    try:
        Path(p).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def trace_paths(text):
    paths = set()
    for line in text.splitlines():
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', line):
            s = m.group(1)
            if s.startswith("/") or s.startswith("."):
                paths.add(s)
    return paths


def audit_trace(text, blind, out, custody, raw):
    """(forbidden paths, class counts) for an strace %file trace of stage 1."""
    resolved = {}
    for s in trace_paths(text):
        q = Path(s) if s.startswith("/") else (REPO / s)
        try:
            resolved[s] = str(q.resolve())
        except OSError:
            resolved[s] = str(q)
    seal_path = out.with_suffix(".seal.json")
    forbidden_roots = [custody, raw / "flights", raw / "flights_xz", raw / "work", raw / "stage0"]
    ancestors = {str(q) for d in (blind, out.parent) for q in d.parents} | {str(blind), str(out.parent)}
    hits = []
    for s, r in sorted(resolved.items()):
        name = Path(r).name
        if r in ancestors:                                    # a directory on the way to an input or output
            continue
        if name in ("KEY.json", "QC.json") or any(under(r, fr) for fr in forbidden_roots):
            hits.append(s)
        elif under(r, HERE) and Path(r) not in (out, seal_path) and not under(r, out.parent):
            hits.append(s)
        elif under(r, raw) and not under(r, blind):
            hits.append(s)
    man = json.loads(A2_MANIFEST.read_text())
    frozen_abs = {str((REPO / rel).resolve()) for rel in man["frozen_files"]}
    cls = {"blind_input": 0, "frozen_manifest_file_hashed": 0, "stage1_output": 0, "repo_code": 0,
           "python_runtime_or_system": 0, "other": []}
    for s, r in resolved.items():
        if under(r, blind):
            cls["blind_input"] += 1
        elif r in frozen_abs:
            cls["frozen_manifest_file_hashed"] += 1
        elif under(r, out.parent):
            cls["stage1_output"] += 1
        elif under(r, REPO):
            cls["repo_code"] += 1
        elif r.startswith(("/usr", "/lib", "/etc", "/proc", "/dev", "/sys", sys.base_prefix, sys.prefix)):
            cls["python_runtime_or_system"] += 1
        else:
            cls["other"].append(s)
    return hits, cls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--custody", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--stage0-report", required=True)
    a = ap.parse_args()
    blind, out, custody, raw = Path(a.blind).resolve(), Path(a.out).resolve(), Path(a.custody).resolve(), Path(a.raw).resolve()
    seal_path = out.with_suffix(".seal.json")
    if out.exists() or seal_path.exists():
        raise SystemExit(f"{out} or its seal already exists: stage 1 runs exactly once")
    s0 = json.loads(Path(a.stage0_report).read_text())
    key_path = custody / "KEY.json"
    checks = {}

    # B1-B4: the inputs themselves
    files = sorted(p.name for p in blind.iterdir())
    index = json.loads((blind / "INDEX.json").read_text())
    hexid = re.compile(r"^[0-9a-f]{16}$")
    checks["B1_blind_dir_only_index_and_opaque_npz"] = (
        set(files) == {"INDEX.json"} | {f"{o}.npz" for o in index}
        and all(hexid.match(o) for o in index) and len(index) == len(set(index)))
    onboard = tuple(frozen_constant(STAGE0, "ONBOARD_KEYS"))
    b2, b3 = True, True
    for o in index:
        with np.load(blind / f"{o}.npz", allow_pickle=False) as z:
            b2 &= tuple(sorted(z.files)) == tuple(sorted(onboard))
            b2 &= all(z[k].dtype.kind in "fiub" for k in z.files)
            t0 = float(z["t_rel"][0])
        b3 &= -5.0 - 1e-9 <= t0 <= -4.99                    # the frozen span_covered tolerance
    checks["B2_npz_only_frozen_numeric_onboard_keys"] = bool(b2)
    checks["B3_every_input_cut_at_t_rel_minus_5"] = bool(b3)
    names = [r["analysis_id"] for r in csv.DictReader(open(A1_MATRIX))]
    names += [r["flight_id"] for r in csv.DictReader(open(A1_FLIGHTS))]
    unsalted = {hashlib.sha256(n.encode()).hexdigest()[:16] for n in names}
    checks["B4_opaque_ids_salted_not_derivable_from_ids"] = not (unsalted & set(index))
    src = STAGE1.read_text()
    forbidden_tokens = ("KEY.json", "QC.json", "--key", "--qc", "st_mtime", "getmtime", "st_ctime", "--flights")
    checks["B5_stage1_source_names_no_label_source"] = not [t for t in forbidden_tokens if t in src]
    checks["B7_key_outside_every_stage1_input"] = key_path.exists() and not under(key_path, blind) and not under(key_path, out.parent)
    probe = (f'openat(AT_FDCWD, "{key_path}", O_RDONLY|O_CLOEXEC) = 3\n'
             f'newfstatat(AT_FDCWD, "{raw / "flights" / "CAMPAIGN.json"}", {{}}, 0) = 0\n')
    probe_hits, _ = audit_trace(probe, blind, out, custody, raw)
    checks["B6_self_test_audit_detects_planted_key_and_flight_access"] = len(probe_hits) == 2
    if not (checks["B7_key_outside_every_stage1_input"] and sha256(key_path) == s0["label_key_sha256"]):
        raise SystemExit("the key is not where the sealed stage 0 report says, or differs from it")
    if not all(checks.values()):
        raise SystemExit(f"blindness pre-check failed, stage 1 NOT run: {checks}")

    # the frozen stage 1, once, under strace
    trace = out.parent / "STAGE1_STRACE.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["strace", "-f", "-qq", "-s", "4096", "-e", "trace=%file", "-o", str(trace), sys.executable, str(STAGE1),
           "--blind", str(blind), "--calibration", str(CAL), "--out", str(out), "--freeze-manifest", str(A2_MANIFEST)]
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.time()
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, env=env)
    wall = time.perf_counter() - t
    if p.returncode != 0:
        raise SystemExit(f"stage 1 failed (rc {p.returncode}):\n{p.stderr[-2000:]}")

    # B6: every path any thread touched
    hits, cls, n_paths = (*audit_trace(trace.read_text(), blind, out, custody, raw),
                          len(trace_paths(trace.read_text())))
    checks["B6_strace_no_forbidden_path_touched"] = not hits

    seal = json.loads(seal_path.read_text())
    man = json.loads(A2_MANIFEST.read_text())
    body_sha = sha256(out)
    frozen_code = {rel: sha256(REPO / rel) for rel in (
        "research/xsys_confirmatory_001/pipeline/stage1_evidence.py",
        "research/xsys_confirmatory_001/pipeline/xsys_features.py",
        "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py",
        "research/xsys_confirmatory_001/pipeline/xsys_freeze_check.py",
        "research/xsys_confirmatory_001/calibration/CALIBRATION.json",
        "csia/v2/localization.py", "csia/v2/evidence.py")}
    record = {
        "campaign_id": "XSYS-001-CONFIRMATORY",
        "record": "STAGE 1 SEAL RECORD - blinded; written before stage 2; no label joined",
        "stage1_command": ["<python>", "research/xsys_confirmatory_001/pipeline/stage1_evidence.py",
                           "--blind", "<raw>/stage1_inputs/blind", "--calibration",
                           "research/xsys_confirmatory_001/calibration/CALIBRATION.json",
                           "--out", str(out.relative_to(REPO)) if under(out, REPO) else str(out),
                           "--freeze-manifest", "research/xsys_confirmatory_001/amendment_a2/FREEZE_MANIFEST_A2.json"],
        "run_under": "strace -f -s 4096 -e trace=%file (every file syscall of every thread)",
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "sealed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seal["sealed_at_unix"])),
        "wall_s_including_strace": wall,
        "input_count": len(index), "output_trial_count": len(json.loads(out.read_text())["trials"]),
        "input_index_sha256": sha256(blind / "INDEX.json"),
        "input_npz_sha256": seal["inputs_sha256"],
        "inputs_match_stage0_report": seal["inputs_sha256"] == s0["stage1_inputs"]["npz_sha256"]
                                      and len(index) == s0["stage1_inputs"]["opaque_count"],
        "input_set_sha256": hashlib.sha256(json.dumps(seal["inputs_sha256"], sort_keys=True).encode()).hexdigest(),
        "output_file": out.name, "output_sha256": body_sha,
        "output_matches_seal": body_sha == seal["stage1_output_sha256"],
        "seal_file": seal_path.name, "seal_sha256": sha256(seal_path),
        "frozen_code_sha256": frozen_code,
        "frozen_code_matches_a2_manifest": all(man["frozen_files"].get(k) == v for k, v in frozen_code.items()),
        "manifest_chain": {"XSYS-001": man["grandparent_manifest"]["sha256"],
                           "XSYS-001-A1": man["parent_manifest"]["sha256"],
                           "XSYS-001-A2": sha256(A2_MANIFEST)},
        "stage1_verified_manifest_sha256": seal["freeze_manifest_sha256"],
        "stage0_report_sha256": sha256(a.stage0_report),
        "label_key_sha256_from_stage0_report": s0["label_key_sha256"],
        "label_key_given_to_stage1": False,
        "blindness_checks": checks,
        "strace_paths_touched": n_paths, "strace_forbidden_hits": hits, "strace_path_classes": cls,
        "strace_sha256": sha256(trace),
        "blind": all(checks.values()),
    }
    rp = out.parent / "STAGE1_SEAL_RECORD.json"
    rp.write_text(json.dumps(record, indent=1) + "\n")
    digest = sha256(rp)
    rp.with_suffix(".sha256").write_text(f"{digest}  {rp.name}\n")
    print(json.dumps({"blind": record["blind"], "checks": checks, "input_count": record["input_count"],
                      "output_trial_count": record["output_trial_count"], "output_sha256": body_sha,
                      "output_matches_seal": record["output_matches_seal"],
                      "inputs_match_stage0_report": record["inputs_match_stage0_report"],
                      "frozen_code_matches_a2_manifest": record["frozen_code_matches_a2_manifest"],
                      "forbidden_hits": hits, "other_paths": cls["other"][:20], "record_sha256": digest}, indent=1))


if __name__ == "__main__":
    main()
