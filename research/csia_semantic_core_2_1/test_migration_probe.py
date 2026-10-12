#!/usr/bin/env python3
"""Phase H: which existing tests would change under Semantic Core 2.1?
RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1/test_migration_probe.py

It runs every test file that exercises frozen v2 twice, in separate pytest
processes:

1. as it is;
2. with `semantic_2_1_pytest_plugin`, which in that process only makes the
   frozen entry points return 2.1 decisions.

It writes `TEST_MIGRATION_PROBE.json`: per test, the outcome under each run,
and the tests whose outcome differs. The classification of each differing
test is in `TEST_MIGRATION.csv`, which is written by hand from this output
and the test sources.

No test file is edited and nothing under `tests/` is written. The junit
reports go to a temporary directory.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "TEST_MIGRATION_PROBE.json"

#: Every test file that imports frozen v2 or the audit probe, plus the Phase C
#: freeze guard.
FILES = (
    "tests/test_v2_framework.py", "tests/test_v2_localization.py",
    "tests/test_v2_scenarios.py", "tests/test_v2_api_ledger.py",
    "tests/test_v2_domains.py", "tests/test_v2_internal_interface.py",
    "tests/test_v2_navigation_baseline.py", "tests/test_phase_c_freeze.py",
    "tests/test_program_state.py", "tests/test_xsys_001_preregistration.py",
    "tests/test_xsys_001_a1_amendment.py", "tests/test_xsys_001_a2_amendment.py",
    "tests/test_csia_semantic_correctness.py",
)


def run(tag, extra, tmp):
    xml = Path(tmp) / f"{tag}.xml"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(HERE), str(REPO), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           f"--junitxml={xml}", *extra, *FILES]
    proc = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    outcomes = {}
    for case in ET.parse(xml).getroot().iter("testcase"):
        tid = f"{case.get('classname')}::{case.get('name')}"
        kind = "passed"
        for child in case:
            if child.tag in ("failure", "error"):
                kind = child.tag
                msg = (child.get("message") or "").splitlines()
                outcomes[tid] = {"outcome": kind,
                                 "message": msg[0][:300] if msg else ""}
                break
            if child.tag == "skipped":
                kind = "skipped"
        outcomes.setdefault(tid, {"outcome": kind})
    return proc.returncode, outcomes


def main():
    with tempfile.TemporaryDirectory() as tmp:
        rc0, base = run("frozen", [], tmp)
        rc1, succ = run("semantic_2_1", ["-p", "semantic_2_1_pytest_plugin"], tmp)
    changed = {t: {"frozen": base.get(t), "semantic_2_1": succ.get(t)}
               for t in sorted(set(base) | set(succ))
               if (base.get(t) or {}).get("outcome") != (succ.get(t) or {}).get("outcome")}
    out = {"files": list(FILES),
           "tests": len(base),
           "frozen_run": {"returncode": rc0, "failed": sorted(
               t for t, v in base.items() if v["outcome"] in ("failure", "error"))},
           "semantic_2_1_run": {"returncode": rc1, "failed": len([
               t for t, v in succ.items() if v["outcome"] in ("failure", "error")])},
           "tests_whose_outcome_changes_under_2_1": changed}
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"tests": len(base), "changed": len(changed),
                      "frozen_failures": out["frozen_run"]["failed"]}, indent=1))


if __name__ == "__main__":
    main()
