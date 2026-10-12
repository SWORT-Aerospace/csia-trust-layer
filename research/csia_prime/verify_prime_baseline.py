#!/usr/bin/env python3
"""CSIA PRIME Phase 0: lock the accepted state. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/verify_prime_baseline.py [--final]

Writes BASELINE_PRIME.json (FINAL_STATE_PRIME.json with --final) and nothing
else. The earlier verifiers' functions are imported and re-executed; their
result files are not rewritten.

| check | how |
|---|---|
| accepted state | RB-001's final commit 16e19d4 (and 2.3's 0f9222c) are ancestors of HEAD |
| product code | `csia_evidence_assurance/`, `csia_semantic_core/`, `csia/` identical to 16e19d4; at --final, every changed file must be a documented PRIME change (PRIME_CHANGES) |
| historical results | the 2.2, pilot, 2.3 and RB-001 packages and their test files identical to 16e19d4 |
| Semantic Core 2.1.1, frozen v2.0, ledger | as in the earlier verifiers |
| 2.1.1 governance, XSYS-001 55/55 gate, Phase C | the revision's gate functions |
| tests | the 2.2, pilot, 2.3 and RB-001 test files pass |
| report reproduction | the product regenerates 2.3's committed V1, V9 and V13 reports byte for byte |
| environment | USB bus, serial/I2C/SPI devices, and the real-log hosts, as found |
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import common_prime as C
import verify_pilot_baseline as VP

OUT = C.HERE / "BASELINE_PRIME.json"
FINAL = C.HERE / "FINAL_STATE_PRIME.json"
#: Product files PRIME may change, each with the measured gap or workflow it answers.
PRIME_CHANGES: dict = {
    "csia_evidence_assurance/__main__.py": "Track A: the `assure` sub-command (analyze's outputs unchanged)",
    "csia_evidence_assurance/assurance_view.py": "Track A: summary, receipts, coverage states, alerts (view only)",
    "csia_evidence_assurance/support.py": "Track A: support check (RR-09, a real boat log)",
    "csia_evidence_assurance/support_matrix.json": "Track A: the machine-readable support matrix (A5)",
    "csia_evidence_assurance/assure_cli.py": "Track A: the csia-assure console script",
}
HISTORICAL = ("research/csia_2_3_stock_bridge", "research/csia_2_2_offboard_pilot",
              "research/csia_2_2_evidence_assurance", "research/rb001_reality_bridge",
              "tests/test_evidence_assurance_2_2.py", "tests/test_csia_2_2_pilot.py",
              "tests/test_csia_2_3_stock_bridge.py", "tests/test_rb001_reality_bridge.py")
REPRO = ("V1", "V9", "V13")
HOSTS = ("https://logs.px4.io/", "https://zenodo.org/", "https://figshare.com/",
         "https://huggingface.co/", "https://rfly-openha.github.io/",
         "https://raw.githubusercontent.com/PX4/pyulog/main/README.md")


def reproduce_reports():
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for v in REPRO:
            d = Path(td) / v
            subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "analyze",
                            str(C.SITL_2_3 / f"{v}.ulg"), "--out", str(d)],
                           cwd=C.REPO, capture_output=True, text=True)
            committed = C.REPO / f"research/csia_2_3_stock_bridge/reports/{v}/report.txt"
            out[v] = (d / "report.txt").exists() and (d / "report.txt").read_text() == committed.read_text()
    return out


def environment():
    import glob
    env = {"usb_bus": Path("/sys/bus/usb").exists(),
           "serial_i2c_spi_devices": sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
                                            + glob.glob("/dev/i2c-*") + glob.glob("/dev/spidev*"))}
    hosts = {}
    for u in HOSTS:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20", u],
                           capture_output=True, text=True)
        hosts[u] = r.stdout.strip()
    env["hosts_http_code"] = hosts
    env["note"] = "000 = refused at the session's network policy; 200 = reachable"
    return env


def main():
    final = "--final" in sys.argv
    out = {"phase": "CSIA PRIME final state" if final else "CSIA PRIME Phase 0 baseline",
           "head": C.git("rev-parse", "--short", "HEAD")}
    anc = {}
    for c in (C.ACCEPTED_RB001, C.ACCEPTED_2_3):
        anc[c] = subprocess.run(["git", "merge-base", "--is-ancestor", c, "HEAD"], cwd=C.REPO).returncode == 0
    out["ancestry"] = dict(VP.ancestry(), **anc)
    changed = set(C.git("diff", "--name-only", C.ACCEPTED_RB001, "--",
                        "csia_evidence_assurance", "csia_semantic_core", "csia").split())
    out["product_files_changed_since_rb001"] = {f: PRIME_CHANGES.get(f, "UNDOCUMENTED")
                                                for f in sorted(changed)}
    product_ok = (not changed) or (final and changed <= set(PRIME_CHANGES))
    out["historical_results_changed_since_rb001"] = VP.unchanged(C.ACCEPTED_RB001, *HISTORICAL)
    out["semantic_core_changed_since_2_1_1"] = VP.unchanged(VP.C.SEMANTIC_2_1_1, "csia_semantic_core")
    out["frozen_v2_changed_since_2_2"] = VP.unchanged(VP.C.ACCEPTED_2_2, "csia")
    out["ledger_matches_pinned"] = C.sha(
        C.REPO / "research/physical_validation/FAILURE_LEDGER.yaml") == VP.C.LEDGER_PINNED
    out["gates_2_1_1"] = VP.gates_2_1_1()
    for name, f in (("tests_2_2", "tests/test_evidence_assurance_2_2.py"),
                    ("tests_pilot", "tests/test_csia_2_2_pilot.py"),
                    ("tests_2_3", "tests/test_csia_2_3_stock_bridge.py"),
                    ("tests_rb001", "tests/test_rb001_reality_bridge.py")):
        out[name] = VP.pytest_file(f)
    out["reports_reproduced_2_3"] = reproduce_reports()
    out["environment"] = environment()
    g = out["gates_2_1_1"]
    ok = (all(out["ancestry"].values()) and product_ok
          and out["historical_results_changed_since_rb001"] == "none"
          and out["semantic_core_changed_since_2_1_1"] == "none"
          and out["frozen_v2_changed_since_2_2"] == "none"
          and out["ledger_matches_pinned"]
          and g["governance_ok"] and g["xsys_gate_pass"] and g["phase_c_unchanged"]
          and all(out[k]["ok"] for k in ("tests_2_2", "tests_pilot", "tests_2_3", "tests_rb001"))
          and all(out["reports_reproduced_2_3"].values()))
    out["FINAL_STATE_PRIME_OK" if final else "BASELINE_PRIME_LOCKED"] = ok
    C.write_json(FINAL if final else OUT, out)
    print(json.dumps(out, indent=1, default=str)[:3500])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
