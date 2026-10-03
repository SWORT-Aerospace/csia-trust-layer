#!/usr/bin/env python3
"""PRIME-1 Phase 28: REAL_DATA_READY_CHECK. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/real_data_ready_check.py

Answers one question with measurements: **if a team sends a real PX4 log
tomorrow, can it be analysed blind, sealed and revealed without writing any
code?** It uses only the product's command line, on every real log available
here (stand-ins for a customer's log: none has a known propulsion event).

| check | how |
|---|---|
| every real log gets a support state, no crash | `csia-assure` on each real log |
| the blind engagement runs end to end | `engagement init / ingest / run / seal / reveal / verify` |
| blind mode refuses an expected event time | `ingest` with `expected_event_time_s` in blind mode |
| the sealed run cannot be redone or altered silently | `run` after `seal` is refused; a changed output fails `verify` |
| customer data is never committed | `git check-ignore` on the engagement paths and on a `.ulg` |
| analysis needs no network | no network module is imported by the product (static), and the run is repeated with the proxy variables removed |
| determinism | the same log twice gives byte-identical outputs |

What this check CANNOT show is written into the output: whether the
conclusions are right on real propulsion faults.
Writes REAL_DATA_READY_CHECK.json.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import common_prime1 as C

REAL = sorted(C.REAL_PYULOG.glob("*.ulg")) + [C.REAL_PX4_DOCS]
NETWORK_MODULES = {"socket", "urllib", "http", "requests", "httpx", "aiohttp", "ftplib", "smtplib"}


def _cli(*args, env=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "csia_evidence_assurance", *map(str, args)],
                          cwd=cwd or C.REPO, env=env, capture_output=True, text=True)


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _tree(d: Path) -> dict:
    return {str(p.relative_to(d)): _sha(p) for p in sorted(d.rglob("*")) if p.is_file()}


def network_imports() -> list:
    found = []
    for pkg in ("csia_evidence_assurance", "csia_semantic_core"):
        for p in sorted((C.REPO / pkg).rglob("*.py")):
            for node in ast.walk(ast.parse(p.read_text())):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                found += [f"{p.relative_to(C.REPO)}: {n}" for n in names if n.split(".")[0] in NETWORK_MODULES]
    return found


def main():
    res = {"label": "PRIME-1 Phase 28: REAL_DATA_READY_CHECK (command line only; real logs as stand-ins)"}
    offline_env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    with tempfile.TemporaryDirectory(dir=C.OUT_RAW) as td:
        td = Path(td)
        logs = {}
        for p in REAL:
            a, b = td / "a" / p.stem, td / "b" / p.stem
            r1 = _cli("assure", p, "--out", a)
            r2 = _cli("assure", p, "--out", b, env=offline_env)
            sup = json.loads((a / "support.json").read_text())["support"] if (a / "support.json").exists() else {}
            logs[p.name] = {"sha256": _sha(p), "exit_code": r1.returncode, "support": sup.get("status"),
                            "interpretation": sup.get("interpretation"),
                            "deterministic_and_offline": r2.returncode == 0 and _tree(a) == _tree(b)}
            print(p.name, logs[p.name], flush=True)
        res["real_logs"] = logs

        # the blind engagement, end to end, on the real log that gets a full analysis
        eng, log = td / "engagements" / "E-TEST", C.REAL_PYULOG / "sample.ulg"
        steps = {}
        intake = td / "intake.json"
        intake.write_text(json.dumps({"px4_version": "unknown", "airframe_or_vehicle_class": "quad X",
                                      "esc_telemetry": "none", "known_modifications": "none", "notes": ""}))
        leaky = td / "leaky.json"
        leaky.write_text(json.dumps({"expected_event_time_s": 42.0}))
        diag = td / "customer_diagnosis.json"
        diag.write_text(json.dumps({"customer_root_cause": "none known (stand-in log)"}))
        steps["init"] = _cli("engagement", "init", eng, "--label", "real-data-ready-check", "--mode", "blind")
        steps["ingest_refuses_expected_time"] = _cli("engagement", "ingest", eng, log, "--intake", leaky)
        steps["ingest"] = _cli("engagement", "ingest", eng, log, "--intake", intake)
        steps["run"] = _cli("engagement", "run", eng)
        steps["reveal_before_seal_refused"] = _cli("engagement", "reveal", eng, diag)
        steps["seal"] = _cli("engagement", "seal", eng)
        steps["run_after_seal_refused"] = _cli("engagement", "run", eng)
        steps["reveal"] = _cli("engagement", "reveal", eng, diag)
        steps["verify"] = _cli("engagement", "verify", eng)
        summary = next(eng.rglob("assurance_summary.txt"))
        summary.write_text(summary.read_text() + "tampered\n")
        steps["verify_after_tamper"] = _cli("engagement", "verify", eng)
        expect_fail = {"ingest_refuses_expected_time", "reveal_before_seal_refused", "run_after_seal_refused",
                       "verify_after_tamper"}
        res["engagement"] = {k: {"exit_code": r.returncode, "as_expected": (r.returncode != 0) == (k in expect_fail),
                                 "message": (r.stderr or r.stdout).strip().splitlines()[-1][:200]
                                 if (r.stderr or r.stdout).strip() else ""}
                             for k, r in steps.items()}
    ign = subprocess.run(["git", "check-ignore", "-v", "engagements/E-1/raw/flight.ulg", "customer_data/x.ulg",
                          "any/where/flight.ulg"], cwd=C.REPO, capture_output=True, text=True)
    res["customer_data_ignored_by_git"] = len(ign.stdout.strip().splitlines()) == 3
    res["network_imports_in_product"] = network_imports()
    res["ready"] = {
        "receive_and_analyse_without_code": all(x["exit_code"] == 0 for x in logs.values()),
        "deterministic_and_offline": all(x["deterministic_and_offline"] for x in logs.values()),
        "blind_engagement_protocol": all(x["as_expected"] for x in res["engagement"].values()),
        "customer_data_never_committed": res["customer_data_ignored_by_git"],
        "no_network_code": not res["network_imports_in_product"],
    }
    res["REAL_DATA_READY"] = all(res["ready"].values())
    res["not_shown_here"] = [
        "whether any conclusion is right on a real propulsion fault: none of these logs has one",
        "the real false-observation rate of the propulsion producers: every threshold is SITL-calibrated, and "
        "none of these real logs carries both actuator_motors and ESC RPM",
        "behaviour on PX4 versions other than 547e2ca beyond 'no crash, support state stated'",
    ]
    C.write_json(C.HERE / "REAL_DATA_READY_CHECK.json", res)
    print(json.dumps({"ready": res["ready"], "REAL_DATA_READY": res["REAL_DATA_READY"]}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
