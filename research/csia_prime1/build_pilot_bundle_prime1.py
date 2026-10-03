#!/usr/bin/env python3
"""PRIME-1 Phases 19-20: the external pilot bundle on release prime1, and its blindness audit.
RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/build_pilot_bundle_prime1.py [--out DIR]

**Same twelve cases as PRIME's bundle** (`research/csia_prime/build_pilot_bundle.py`,
CASES), **new P-number order** (a new seed). The product is release prime1
(`csia-assure` default).

**Blinding, stronger than PRIME's.** From every SITL log:
- the in-flight change of any `SIH_*` parameter;
- PX4's `[failure_injection_manager]` messages;
- **the failure-injection parameters themselves:** `SIH_MOT_EFF1-4` and
  `SYS_FAILURE_EN` from the initial parameter set. They are identical in
  every SITL log, but they announce a fault-injection campaign.

Matched pair B's RPM corruption is written into its log, as in PRIME.

**What the builder checks, and records in PILOT_BUNDLE_PRIME1.json (no
truth):**
- the product (prime1) on every blinded copy and on its source: events,
  symptoms and attribution must be identical (prime1 ignores injection
  records; matched B is compared with PRIME's demo facts instead);
- the SHA-256 of every participant file, the wheel, and every sample
  report the product writes for every log (determinism reference);
- **the blindness audit (BLINDNESS_AUDIT.json):** every participant artifact
  is searched for known leak tokens and for case-revealing names. Every ULog
  is also parsed for changed parameters, injection-related parameters,
  messages and header fields. The bundle is pilot-ready only with **ZERO
  KNOWN GROUND-TRUTH LEAKS**.

Output is outside git (default /home/user/prime1_raw/pilot_bundle).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from pyulog import ULog

import common_prime1 as C                  # first: puts the PRIME package on the import path
import build_pilot_bundle as B0            # noqa: E402  PRIME's builder: CASES, NOTICE, assignment, wheel

DEFAULT_OUT = C.OUT_RAW / "pilot_bundle"
SEED = 20261003
PARTICIPANT_DOCS = C.HERE / "pilot_package"
EXPERIMENTER_DOCS = C.HERE / "pilot_package_experimenter"
DROP_PARAMS = ("SIH_MOT_EFF1", "SIH_MOT_EFF2", "SIH_MOT_EFF3", "SIH_MOT_EFF4", "SYS_FAILURE_EN")
LEAK_TOKENS = ("failure_injection", "Injected:", "SIH_MOT_EFF", "SYS_FAILURE_EN", "ground truth",
               "GROUND_TRUTH", "expected answer", "expected_answer")
#: Words that are generic in PX4 logs and product documents; reported, judged against the nominal logs.
GENERIC_WORDS = ("fail", "fault", "inject")


def blind(src: Path, dst: Path, corrupt: bool) -> dict:
    u = ULog(str(src))
    params = [c for c in u.changed_parameters if c[1].startswith("SIH_")]
    u.changed_parameters[:] = [c for c in u.changed_parameters if not c[1].startswith("SIH_")]
    msgs = [m for m in u.logged_messages if "failure_injection" in m.message]
    u.logged_messages[:] = [m for m in u.logged_messages if "failure_injection" not in m.message]
    for k, lst in list(u.logged_messages_tagged.items()):
        u.logged_messages_tagged[k] = [m for m in lst if "failure_injection" not in m.message]
    dropped = sorted(k for k in DROP_PARAMS if k in u.initial_parameters)
    for k in dropped:
        del u.initial_parameters[k]
    corrupted = 0
    if corrupt:
        for d in u.data_list:
            if d.name == "esc_status":
                after = d.data["timestamp"].astype(np.int64) >= int(u.start_timestamp) + int(B0.CORRUPT_T * 1e6)
                f = d.data["esc[0].esc_rpm"]
                d.data["esc[0].esc_rpm"] = np.where(after, np.round(f * np.sqrt(0.6)), f).astype(f.dtype)
                corrupted += int(after.sum())
    u.write_ulog(str(dst))
    return {"removed_parameter_changes": len(params), "removed_messages": len(msgs),
            "dropped_initial_parameters": dropped, "corrupted_samples": corrupted}


def assure(path: Path, out: Path) -> dict:
    r = subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "assure", str(path), "--out", str(out)],
                       cwd=C.REPO, capture_output=True, text=True)
    m = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else {}
    sup = json.loads((out / "support.json").read_text())["support"]
    return {"exit": r.returncode,
            "events": [(e["t0"], e["trigger_kinds"]) for e in m.get("events", [])],
            "symptoms": sorted({c["what"] for c in m.get("key_moments", {}).get("candidate_changes", [])
                                if c["what"] != "attribution" and c["to"]}),
            "attribution": m.get("summary", {}).get("attribution", {}).get("verdict"),
            "support": sup["status"], "files": {f.name: _sha(f) for f in sorted(out.iterdir())}}


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ the blindness audit
def audit_ulog(path: Path) -> dict:
    u = ULog(str(path))
    out = {"changed_parameters": [c[1] for c in u.changed_parameters],
           "injection_parameters": sorted(k for k in u.initial_parameters
                                          if k.startswith(("SIH_MOT", "SYS_FAILURE")) or "FAIL_INJ" in k),
           "messages_with_leak_tokens": [m.message for m in u.logged_messages
                                         if any(t.lower() in m.message.lower() for t in LEAK_TOKENS)],
           "messages_with_generic_words": sorted({m.message for m in u.logged_messages
                                                  if any(w in m.message.lower() for w in GENERIC_WORDS)}),
           "info_fields_with_leak_tokens": [k for k, v in u.msg_info_dict.items()
                                            if any(t.lower() in str(v).lower() for t in LEAK_TOKENS)],
           "multi_info_with_leak_tokens": [k for k, v in u.msg_info_multiple_dict.items()
                                           if any(t.lower() in str(v).lower() for t in LEAK_TOKENS)]}
    raw = path.read_bytes()
    out["raw_bytes_leak_tokens"] = [t for t in LEAK_TOKENS if t.encode() in raw]
    return out


def audit_bundle(zpath: Path, case_names: list) -> dict:
    """Every participant artifact: known leak tokens, case names, file names, per-log ULog checks."""
    findings, logs = [], {}
    with zipfile.ZipFile(zpath) as z, tempfile.TemporaryDirectory() as td:
        for n in z.namelist():
            data = z.read(n)
            if not re.fullmatch(r"(logs/P\d\d\.ulg|install/csia_trust_layer-[0-9.]+-py3-none-any\.whl|"
                                r"[A-Z_]+\.(md|json|txt))", n):
                findings.append({"artifact": n, "leak": "unexpected file name"})
            if n.endswith(".ulg"):
                p = Path(td) / Path(n).name
                p.write_bytes(data)
                logs[Path(n).stem] = audit_ulog(p)
                continue
            if n.endswith(".whl"):
                continue                      # product code: audited separately below
            text = data.decode("utf-8", "replace")
            for t in LEAK_TOKENS:
                if t.lower() in text.lower():
                    findings.append({"artifact": n, "leak": f"token {t!r}"})
            for c in case_names:
                if c.lower() in text.lower():
                    findings.append({"artifact": n, "leak": f"case name {c!r}"})
        whl = next(n for n in z.namelist() if n.endswith(".whl"))
        wpath = Path(td) / "w.whl"
        wpath.write_bytes(z.read(whl))
        with zipfile.ZipFile(wpath) as w:
            truthy = [n for n in w.namelist() if n.startswith(("research/", "tests/")) or "GROUND_TRUTH" in n
                      or n.endswith(".ulg")]
            case_in_code = sorted({c for n in w.namelist() if n.endswith(".py")
                                   for c in case_names if c.lower() in w.read(n).decode("utf-8", "replace").lower()})
    for pid, a in logs.items():
        for k in ("changed_parameters", "injection_parameters", "messages_with_leak_tokens",
                  "info_fields_with_leak_tokens", "multi_info_with_leak_tokens", "raw_bytes_leak_tokens"):
            if a[k]:
                findings.append({"artifact": f"logs/{pid}.ulg", "leak": f"{k}: {a[k][:5]}"})
    if truthy:
        findings.append({"artifact": whl, "leak": f"research, tests, truth or logs inside the wheel: {truthy[:5]}"})
    if case_in_code:
        findings.append({"artifact": whl, "leak": f"case names in product code: {case_in_code}"})
    generic = {pid: a["messages_with_generic_words"] for pid, a in sorted(logs.items())}
    return {"known_leaks": findings, "zero_known_leaks": not findings, "per_log": logs,
            "generic_words_in_logs": generic,
            "product_code_note": "the wheel's code mentions '[failure_injection_manager]' only to IGNORE such "
                                 "messages (events.HARNESS_PREFIX); it carries no case information and no P-number "
                                 "mapping, so it is not a ground-truth leak"}


# ------------------------------------------------------------------ build
def support_matrix_md(contract: dict) -> str:
    L = ["# CSIA Flight Assurance PRIME-1: support matrix", "",
         f"**Support contract {contract['contract_version']}** (machine-readable: "
         "`support_contract_prime1.json` inside the installed package). "
         "No entry is PHYSICAL_VALIDATED: no physical evidence exists yet.", "",
         "| configuration | state | vehicle | validation level |", "|---|---|---|---|"]
    for x in contract["configurations"]:
        L.append(f"| {x['id']} | {x['state']} | {x['vehicle']} | {x['validation_level']} |")
    L += ["", "## Validation levels", ""] + [f"- **{k}**: {v}" for k, v in contract["validation_levels"].items()]
    L += ["", "## Telemetry classes", "", "| class | what the Analyzer does | validation level |", "|---|---|---|"]
    for k, v in contract["telemetry_classes"].items():
        L.append(f"| {k} | {v['supported']} | {v['validation_level']} |")
    L += ["", "## Known blind spots", ""] + [f"- {x}" for x in contract["known_blind_spots"]]
    L += ["", "## Known defects (fixed in prime1)", ""] + [f"- {d['id']}: {d['summary']}" for d in contract["known_defects"]]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = ap.parse_args().out
    if out.exists():
        shutil.rmtree(out)
    (out / "experimenter").mkdir(parents=True)
    from csia_evidence_assurance import support_prime1 as SP1
    contract = SP1.contract()
    cases = B0.CASES
    order = list(range(len(cases)))
    random.Random(SEED).shuffle(order)
    key, files, checks, sample_hashes = {}, {}, {}, {}
    demo_b = json.loads((C.PRIME / "DEMO_AB.json").read_text())["cases"]["B"]
    zpath = out / "csia_pilot_participant_prime1.zip"
    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        td = Path(td)
        for pos, i in enumerate(order, start=1):
            name, src, data, truth = cases[i]
            pid = f"P{pos:02d}"
            dst = td / f"{pid}.ulg"
            corrupt = name.startswith("matched_B")
            shown = "REAL" if data == "REAL" else "SITL"
            record = blind(src, dst, corrupt) if data.startswith("SITL") else (shutil.copyfile(src, dst) and
                                                                               {"copied_unchanged": True})
            after = assure(dst, td / f"{pid}_out")
            if corrupt:
                same = {"compared_with": "PRIME DEMO_AB.json case B",
                        "equal": not after["symptoms"] and after["attribution"] == demo_b["attribution"]["verdict"]}
            else:
                before = assure(src, td / f"{pid}_src")
                same = {"compared_with": "the source log",
                        "equal": (after["events"], after["symptoms"], after["attribution"], after["support"])
                        == (before["events"], before["symptoms"], before["attribution"], before["support"])}
            z.write(dst, f"logs/{pid}.ulg")
            files[f"logs/{pid}.ulg"] = _sha(dst)
            sample_hashes[pid] = after["files"]
            key[pid] = {"case": name, "source": src.name, "source_sha256": _sha(src), "data": data, "truth": truth,
                        "blinding": record, "product_prime1": {k: after[k] for k in ("events", "symptoms",
                                                                                     "attribution", "support")},
                        "blinded_vs_source": same}
            checks[pid] = {"data": shown, "exit_code": after["exit"], "support": after["support"],
                           "conclusions_equal": same["equal"]}
            print(pid, name, data, after["support"], same["equal"], flush=True)
            dst.unlink()
        whl = B0.wheel(td / "wheel")
        z.write(whl, f"install/{whl.name}")
        files[f"install/{whl.name}"] = _sha(whl)
        for f in sorted(PARTICIPANT_DOCS.glob("*.md")):
            z.write(f, f.name)
            files[f.name] = _sha(f)
        sm = support_matrix_md(contract)
        (C.HERE / "SUPPORT_MATRIX.md").write_text(sm, encoding="utf-8")
        z.writestr("SUPPORT_MATRIX.md", sm)
        files["SUPPORT_MATRIX.md"] = hashlib.sha256(sm.encode()).hexdigest()
        z.writestr("DATA_NOTICE.txt", B0.NOTICE)
        files["DATA_NOTICE.txt"] = hashlib.sha256(B0.NOTICE.encode()).hexdigest()
        listing = json.dumps({"logs": {p: c["data"] for p, c in sorted(checks.items())}}, indent=1, sort_keys=True) + "\n"
        z.writestr("LOGS.json", listing)
        files["LOGS.json"] = hashlib.sha256(listing.encode()).hexdigest()
    audit = audit_bundle(zpath, [c[0] for c in cases])
    C.write_json(out / "experimenter/GROUND_TRUTH.json", {
        "label": "EXPERIMENTER ONLY. Never give this file, or the repository, to a participant.",
        "seed": SEED, "release": "prime1", "cases": key})
    C.write_json(out / "experimenter/ASSIGNMENT.json", B0.assignment(sorted(key)))
    for f in sorted(EXPERIMENTER_DOCS.glob("*.md")):
        shutil.copyfile(f, out / "experimenter" / f.name)
    C.write_json(C.HERE / "BLINDNESS_AUDIT.json", dict(
        {k: v for k, v in audit.items() if k != "per_log"},
        verdict="ZERO KNOWN GROUND-TRUTH LEAKS" if audit["zero_known_leaks"] else "GROUND-TRUTH LEAKS FOUND",
        label="PRIME-1 Phase 20: blindness audit of every participant artifact",
        per_log={p: {k: v for k, v in a.items() if k != "messages_with_generic_words"}
                 for p, a in audit["per_log"].items()}))
    C.write_json(C.HERE / "PILOT_BUNDLE_PRIME1.json", {
        "label": "PRIME-1 participant bundle as built (outside git); no truth here", "release": "prime1",
        "bundle": str(zpath), "participant_files_sha256": files,
        "manifest_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "wheel": {"file": whl.name, "sha256": files[f"install/{whl.name}"]},
        "sample_report_sha256": sample_hashes, "logs": dict(sorted(checks.items())),
        "all_exit_zero": all(c["exit_code"] == 0 for c in checks.values()),
        "all_conclusions_equal_blinded_vs_source": all(c["conclusions_equal"] for c in checks.values()),
        "zero_known_leaks": audit["zero_known_leaks"]})
    print(json.dumps({"zero_known_leaks": audit["zero_known_leaks"], "leaks": audit["known_leaks"][:10]}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
