"""Assemble E2M_ASSURANCE.json from measured artifacts, not from prose.

Every field is read from a file something else produced -- a pytest run, a
coverage run, the mutation runner -- or measured here. Nothing is transcribed
by hand, because four entries in this repository's counterexample log begin
with somebody reading a number and typing it somewhere else.

    python tools/hardware/e2m_assurance_report.py \
        --suite <pytest output> --coverage <coverage json> \
        --mutation research/bus_provenance/results/E2M_MUTATION_RESULTS.json

It refuses to write a report claiming a green suite from a run whose recorded
exit code is not zero, and a run with no `PYTEST_EXIT=` marker reads as None
rather than as success -- the `pytest | tail` defect this repository has three
counterexample entries for.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "research/bus_provenance/results/E2M_ASSURANCE.json"

#: The repository's own floors. Not thresholds invented for this report.
FLOORS = {
    "coverage_percent": 86.86,
    "mutation_frozen_core": 0.5583,
    "mutation_assurance": 0.6125,
    "mutation_mission": 0.6726,
}


def _suite(path: pathlib.Path) -> dict:
    text = path.read_text(errors="replace")
    exit_match = re.search(r"PYTEST_EXIT=(\d+)", text)
    code = int(exit_match.group(1)) if exit_match else None
    dots = [ln.strip() for ln in text.splitlines()
            if re.fullmatch(r"[.sxXF]+\s*(\[\s*\d+%\])?", ln.strip())]
    passed = sum(ln.count(".") for ln in dots)
    skipped = sum(ln.count("s") for ln in dots)
    failed = sum(ln.count("F") for ln in dots)
    reasons = [ln.strip() for ln in text.splitlines()
               if ln.startswith("SKIPPED")]
    return {"exit_code": code, "passed": passed, "skipped": skipped,
            "failed": failed, "skip_reasons": reasons,
            "failures": [ln for ln in text.splitlines()
                         if ln.startswith(("FAILED ", "ERROR "))]}


def _git(*args):
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", required=True, type=pathlib.Path)
    ap.add_argument("--coverage", type=pathlib.Path, default=None)
    ap.add_argument("--mutation", type=pathlib.Path,
                    default=ROOT / "research/bus_provenance/results"
                                   "/E2M_MUTATION_RESULTS.json")
    ap.add_argument("--crc-suite", type=pathlib.Path, default=None)
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    args = ap.parse_args(argv)

    suite = _suite(args.suite)
    if suite["exit_code"] != 0:
        print(f"refusing to write an assurance report from a run whose "
              f"recorded exit was {suite['exit_code']!r}. "
              f"Failures: {suite['failures'][:5]}", file=sys.stderr)
        return 1

    coverage = None
    if args.coverage and args.coverage.is_file():
        doc = json.loads(args.coverage.read_text())
        coverage = {
            "total_percent": round(doc["totals"]["percent_covered"], 2),
            "by_file": {k: round(v["summary"]["percent_covered"], 1)
                        for k, v in sorted(doc["files"].items())},
        }

    mutation = None
    if args.mutation and args.mutation.is_file():
        doc = json.loads(args.mutation.read_text())
        mutation = {
            "evaluated": doc["evaluated"], "killed": doc["killed"],
            "survived": doc["survived"], "invalid": doc["invalid"],
            "score": doc["score"], "by_family": doc["by_family"],
            "survivors": [{"id": r["id"], "family": r["family"],
                           "path": r["path"], "breaks": r["breaks"]}
                          for r in doc["results"]
                          if r["verdict"] == "SURVIVED"],
        }

    report = {
        "schema": "csia.e2m.assurance/1",
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "working_tree_dirty": bool(_git("status", "--porcelain")),
        "hardware_status": "NOT_RUN",
        "campaign_state": "AUTHORIZED_NOT_RUN",
        "test_command": "python -m pytest -q -rs",
        "suite": suite,
        "coverage": coverage,
        "mutation_command":
            "python tools/mutation/run_e2m_mutations.py",
        "mutation": mutation,
        "repository_floors": FLOORS,
        "floor_comparison": {
            "coverage_meets_repository_floor":
                None if coverage is None
                else coverage["total_percent"] >= FLOORS["coverage_percent"],
            "mutation_meets_highest_repository_floor":
                None if not mutation or mutation["score"] is None
                else mutation["score"] >= FLOORS["mutation_mission"],
            "note": ("the repository floors were measured on OTHER packages "
                     "with other mutant sets. Clearing them is evidence that "
                     "this suite is in the same league, not that it is "
                     "equivalent. Mutation scores are not comparable across "
                     "different mutant lists."),
        },
        "distinctions_that_must_not_collapse": {
            "software_tested_is_not_hardware_tested": True,
            "fake_driver_tested_is_not_live_sensor_tested": True,
            "replay_tested_is_not_acquisition_tested": True,
            "bench_tested_is_not_flight_tested": True,
            "authorized_is_not_executed": True,
            "skipped_hardware_tests_are_not_passes": True,
        },
        "unresolved_blockers": [
            {"gate": 1, "name": "TCA9548A datasheet",
             "state": "OPEN",
             "removal": "place the original PDF at hardware/datasheets/"
                        "tca9548a/tca9548a.pdf and run "
                        "tools/hardware/ingest_datasheet.py; a human then "
                        "checks each constant against a cited page"},
            {"gate": 2, "name": "sensor inventory", "state": "OPEN",
             "removal": "fill hardware/inventory/e2m_sensors.yaml"},
            {"gate": 3, "name": "electrical compatibility",
             "state": "OPEN, blocked by gates 1 and 2",
             "removal": "fill hardware/wiring/E2M_PIN_TABLE.md from the "
                        "primary documents"},
            {"gate": 4, "name": "execution environment",
             "state": "NO_HARDWARE_ACCESS",
             "removal": "clearable only on the operator's machine"},
        ],
        "what_this_report_is_not": (
            "not evidence about hardware. Every number here comes from tests "
            "against a fake controller, recorded fixtures and a compiled host "
            "copy of the firmware CRC. No frame in this repository came from "
            "a bus."),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(f"wrote {args.out.relative_to(ROOT)}")
    print(f"  suite   {suite['passed']} passed, {suite['skipped']} skipped, "
          f"exit {suite['exit_code']}")
    if coverage:
        print(f"  coverage {coverage['total_percent']}% "
              f"(floor {FLOORS['coverage_percent']}%)")
    if mutation:
        print(f"  mutation {mutation['killed']}/{mutation['evaluated']} "
              f"= {mutation['score']}  survivors {len(mutation['survivors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
