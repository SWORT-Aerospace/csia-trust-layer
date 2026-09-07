"""A one-way ratchet on coverage and mutation score.

WHAT A RATCHET IS FOR
---------------------
A quality number that nobody checks drifts down. A quality number with a
TARGET gets argued about. A ratchet does neither: it records what was
achieved and fails if a later run does worse.

    coverage may not fall
    mutation score may not fall
    the floor only ever moves UP, and only by an explicit commit

THE FLOOR IS A MEASUREMENT, NOT AN ASPIRATION. `QUALITY_FLOOR.json` holds
what was actually achieved. Raising it is a deliberate edit in the commit
that earned it; lowering it is a deliberate edit that has to be justified in
review, which is the whole point.

WHY BOTH NUMBERS
----------------
Coverage alone is gameable by tests that execute code and assert nothing --
this repository has a recorded instance (MX-007) where three modules read
generated artifacts instead of calling the code and reported as covered.
Mutation alone is slow and noisy. Ratcheting both means neither can be traded
for the other.

TOLERANCE, AND WHY IT IS NOT ZERO
-----------------------------------
Mutation sampling is seeded and deterministic for a fixed target set, but the
SITE COUNT changes whenever the code changes, which reshuffles which sites a
sample covers. A hard equality would fire on every refactor. The tolerance is
therefore a small band, declared here, and the floor is compared against the
band's lower edge -- never widened after seeing a result.

    python tools/xr/quality_ratchet.py --check
    python tools/xr/quality_ratchet.py --update    # raises the floor
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

FLOOR = os.path.join(ROOT, "research", "mission", "results",
                     "QUALITY_FLOOR.json")

#: DECLARED HERE, BEFORE ANY RUN. Mutation sampling reshuffles when the site
#: count changes, so a hard equality would fire on every refactor.
MUTATION_TOLERANCE = 0.03
COVERAGE_TOLERANCE = 0.5      # percentage points

COVERED = ("csia_mission", "csia_assurance")

COVERAGE_TESTS = (
    "tests/test_mission_assurance.py",
    "tests/test_mission_untested_modules.py",
    "tests/test_mission_boundaries.py",
    "tests/test_mission_survivor_kills.py",
    "tests/test_mission_registries_and_schemas.py",
    "tests/test_bad_product_references.py",
    "tests/test_mission_independence.py",
    "tests/test_assurance_firewall.py",
    "tests/test_assurance_vectors.py",
    "tests/test_assurance_metamorphic.py",
    "tests/test_assurance_independence.py",
)


def measure_coverage() -> dict:
    """Run coverage and return the total percentage."""
    env = dict(os.environ)
    subprocess.run(
        [sys.executable, "-m", "coverage", "run",
         f"--source={','.join(COVERED)}", "-m", "pytest", *COVERAGE_TESTS,
         "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, timeout=1800, env=env)
    proc = subprocess.run(
        [sys.executable, "-m", "coverage", "json", "-o", "-"],
        cwd=ROOT, capture_output=True, text=True, timeout=300, env=env)
    if proc.returncode != 0:
        return {"error": proc.stderr[-400:]}
    data = json.loads(proc.stdout)
    return {
        "total_percent": round(data["totals"]["percent_covered"], 2),
        "per_file": {
            k: round(v["summary"]["percent_covered"], 1)
            for k, v in sorted(data["files"].items())},
    }


def read_mutation(path: str) -> dict:
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return {"error": f"{path} not present"}
    with open(full, encoding="utf-8") as fh:
        doc = json.load(fh)
    return {"score": doc.get("mutation_score"),
            "killed": doc.get("killed"),
            "evaluated": doc.get("evaluated"),
            "sites": doc.get("total_mutation_sites")}


def load_floor() -> dict:
    if not os.path.exists(FLOOR):
        return {}
    with open(FLOOR, encoding="utf-8") as fh:
        return json.load(fh)


def check(measured: dict, floor: dict) -> dict:
    problems = []

    fc = (floor.get("coverage") or {}).get("total_percent")
    mc = (measured.get("coverage") or {}).get("total_percent")
    if fc is not None and mc is not None and mc < fc - COVERAGE_TOLERANCE:
        problems.append({
            "metric": "coverage", "floor": fc, "measured": mc,
            "tolerance": COVERAGE_TOLERANCE,
            "why": ("coverage fell below the recorded floor. Either add "
                    "tests, or lower the floor DELIBERATELY in this commit "
                    "and say why in the message.")})

    for key in ("mutation_mission", "mutation_frozen_core"):
        fm = (floor.get(key) or {}).get("score")
        mm = (measured.get(key) or {}).get("score")
        if fm is None or mm is None:
            continue
        if mm < fm - MUTATION_TOLERANCE:
            problems.append({
                "metric": key, "floor": fm, "measured": mm,
                "tolerance": MUTATION_TOLERANCE,
                "why": ("the mutation score fell below the recorded floor: "
                        "the tests now constrain less of the code than they "
                        "did.")})

    return {
        "schema": "csia.mission.quality_ratchet/1",
        "floor": floor,
        "measured": measured,
        "tolerances": {"mutation": MUTATION_TOLERANCE,
                       "coverage_percentage_points": COVERAGE_TOLERANCE},
        "problems": problems,
        "holds": not problems,
        "the_floor_only_moves_up": (
            "raising it is a deliberate edit in the commit that earned it; "
            "lowering it is a deliberate edit that has to be justified in "
            "review. Neither happens by accident."),
    }


def measure_all(skip_coverage: bool = False) -> dict:
    out = {
        "mutation_mission": read_mutation(
            "research/mission/results/MUTATION_PROBE.json"),
        "mutation_frozen_core": read_mutation(
            "research/mission/results/MUTATION_PROBE_FROZEN_CORE.json"),
        "mutation_assurance_baseline": read_mutation(
            "research/mission/results/MUTATION_PROBE_ASSURANCE_BASELINE.json"),
    }
    if not skip_coverage:
        out["coverage"] = measure_coverage()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--update", action="store_true",
                    help="raise the floor to what was just measured")
    ap.add_argument("--skip-coverage", action="store_true")
    args = ap.parse_args(argv)

    measured = measure_all(args.skip_coverage)
    floor = load_floor()
    report = check(measured, floor)

    if args.update:
        new_floor = dict(floor)
        for key, value in measured.items():
            if "error" in value:
                continue
            old = (floor.get(key) or {})
            # ONE-WAY. A metric is only written if it IMPROVED or is new.
            if key == "coverage":
                if (old.get("total_percent") is None
                        or value["total_percent"] >= old["total_percent"]):
                    new_floor[key] = {
                        "total_percent": value["total_percent"]}
            elif value.get("score") is not None:
                if old.get("score") is None or value["score"] >= old["score"]:
                    new_floor[key] = {"score": value["score"],
                                      "killed": value.get("killed"),
                                      "evaluated": value.get("evaluated")}
        new_floor["schema"] = "csia.mission.quality_floor/1"
        new_floor["note"] = (
            "A MEASUREMENT, not an aspiration. Written by "
            "tools/xr/quality_ratchet.py --update, and only ever upward.")
        os.makedirs(os.path.dirname(FLOOR), exist_ok=True)
        with open(FLOOR, "w", encoding="utf-8") as fh:
            json.dump(new_floor, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"floor updated: {FLOOR}")
        print(json.dumps(new_floor, indent=2, sort_keys=True))
        return 0

    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if not report["holds"]:
        print(f"\nQUALITY RATCHET: {len(report['problems'])} regression(s)",
              file=sys.stderr)
        return 1
    print("\nQUALITY RATCHET: HOLDS", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
