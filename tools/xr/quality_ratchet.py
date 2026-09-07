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

WHY THE FLOOR RECORDS A SUBSET FINGERPRINT (MX-015)
---------------------------------------------------
A mutation score is only comparable to another mutation score over THE SAME
CODE AND THE SAME TESTS. MX-015 records what happens when that is forgotten:
two subsets were compared, a conclusion was drawn about the frozen core, and
the decisive test file was missing from BOTH sides -- so the comparison
measured the two omissions rather than the tests. Including it moved
`hypothesis.py` from 0.000 to 0.448.

That error is easy to wire into a nightly gate: measure with one test subset,
compare against a floor earned under another, and read the difference as a
quality change. So the floor stores a fingerprint of the targets and the test
subset that produced it, and a comparison across differing fingerprints is
reported as NOT COMPARABLE.

**NOT COMPARABLE IS NOT PASS.** It is the same rule as the nightly's
INCONCLUSIVE: a check that could not be performed never reads as a check that
succeeded. It exits non-zero, and the report separates it from a genuine
regression so the two are not confused.

    python tools/xr/quality_ratchet.py --check
    python tools/xr/quality_ratchet.py --update    # raises the floor
"""

from __future__ import annotations

import argparse
import hashlib
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


def subset_fingerprint(doc: dict) -> str | None:
    """Hash the targets and test subset a mutation run was measured over.

    TWO SCORES ARE COMPARABLE ONLY IF THIS MATCHES. Order is normalised so a
    reordered list is not read as a different subset; anything else -- a file
    added, a file dropped -- changes the hash, which is the point. Returns
    None when the artifact does not declare both, so a missing fingerprint is
    distinguishable from a differing one.
    """
    targets = doc.get("targets")
    tests = doc.get("test_subset")
    if not targets or not tests:
        return None
    payload = json.dumps(
        {"targets": sorted(targets), "test_subset": sorted(tests)},
        sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def read_mutation(path: str) -> dict:
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return {"error": f"{path} not present"}
    with open(full, encoding="utf-8") as fh:
        doc = json.load(fh)
    return {"score": doc.get("mutation_score"),
            "killed": doc.get("killed"),
            "evaluated": doc.get("evaluated"),
            "sites": doc.get("total_mutation_sites"),
            "subset_fingerprint": subset_fingerprint(doc),
            "targets": doc.get("targets"),
            "test_subset": doc.get("test_subset")}


def load_floor() -> dict:
    if not os.path.exists(FLOOR):
        return {}
    with open(FLOOR, encoding="utf-8") as fh:
        return json.load(fh)


def check(measured: dict, floor: dict) -> dict:
    problems = []
    not_comparable = []

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

        # COMPARABILITY IS CHECKED BEFORE THE SCORES ARE. A score measured
        # over a different target set or a different test subset is not a
        # worse or better version of the floor -- it is a different
        # measurement, and comparing the two is MX-015.
        ff = (floor.get(key) or {}).get("subset_fingerprint")
        mf = (measured.get(key) or {}).get("subset_fingerprint")
        if ff is None or mf is None:
            not_comparable.append({
                "metric": key, "reason": "UNFINGERPRINTED",
                "floor_fingerprint": ff, "measured_fingerprint": mf,
                "why": ("one side does not declare the targets and test "
                        "subset it was measured over, so comparability "
                        "cannot be established. Re-measure with a probe that "
                        "records both, then --update.")})
            continue
        if ff != mf:
            not_comparable.append({
                "metric": key, "reason": "SUBSET_CHANGED",
                "floor_fingerprint": ff, "measured_fingerprint": mf,
                "floor_test_subset": (floor.get(key) or {}).get("test_subset"),
                "measured_test_subset":
                    (measured.get(key) or {}).get("test_subset"),
                "floor_score": fm, "measured_score": mm,
                "why": ("the targets or the test subset changed, so this "
                        "score and the floor are not measurements of the "
                        "same thing. A difference between them says nothing "
                        "about quality. Decide DELIBERATELY whether the new "
                        "subset is the one to ratchet on, and --update if "
                        "so. See MX-015.")})
            continue

        if mm < fm - MUTATION_TOLERANCE:
            problems.append({
                "metric": key, "floor": fm, "measured": mm,
                "tolerance": MUTATION_TOLERANCE,
                "why": ("the mutation score fell below the recorded floor: "
                        "the tests now constrain less of the code than they "
                        "did.")})

    if problems:
        verdict = "REGRESSION"
    elif not_comparable:
        verdict = "NOT_COMPARABLE"
    else:
        verdict = "HOLDS"

    return {
        "schema": "csia.mission.quality_ratchet/2",
        "floor": floor,
        "measured": measured,
        "tolerances": {"mutation": MUTATION_TOLERANCE,
                       "coverage_percentage_points": COVERAGE_TOLERANCE},
        "problems": problems,
        "not_comparable": not_comparable,
        "verdict": verdict,
        "holds": verdict == "HOLDS",
        "not_comparable_is_not_pass": (
            "a comparison that could not be performed NEVER reads as a "
            "comparison that succeeded. NOT_COMPARABLE exits non-zero, like "
            "the nightly's INCONCLUSIVE, and is reported separately from a "
            "REGRESSION so the two are not confused."),
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
        actions = []
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
                    actions.append(f"{key}: raised")
            elif value.get("score") is not None:
                # THE ONE-WAY RULE ONLY MEANS SOMETHING WITHIN ONE
                # MEASUREMENT DEFINITION. Across a changed subset, "improved"
                # is not a fact about quality (MX-015), so a re-baseline is
                # written unconditionally and labelled as one -- `--update`
                # IS the deliberate act that accepts the new subset.
                old_fp, new_fp = (old.get("subset_fingerprint"),
                                  value.get("subset_fingerprint"))
                rebaseline = old_fp != new_fp
                if (rebaseline or old.get("score") is None
                        or value["score"] >= old["score"]):
                    new_floor[key] = {
                        "score": value["score"],
                        "killed": value.get("killed"),
                        "evaluated": value.get("evaluated"),
                        "subset_fingerprint": new_fp,
                        "targets": value.get("targets"),
                        "test_subset": value.get("test_subset")}
                    # SAY WHICH OF THE THREE THINGS HAPPENED. A score that
                    # did not move must not be reported as a re-baseline
                    # just because the floor previously carried no
                    # fingerprint to compare against.
                    if old.get("score") is None:
                        what = "new"
                    elif old_fp is None:
                        what = ("fingerprinted, score unchanged"
                                if value["score"] == old["score"]
                                else f"fingerprinted, {old['score']} -> "
                                     f"{value['score']} (the floor carried "
                                     "no subset, so this is NOT a verified "
                                     "quality change)")
                    elif rebaseline:
                        what = (f"RE-BASELINED onto a different subset "
                                f"({old['score']} -> {value['score']}, NOT a "
                                "quality comparison)")
                    else:
                        what = f"raised {old['score']} -> {value['score']}"
                    actions.append(f"{key}: {what}")
        new_floor["schema"] = "csia.mission.quality_floor/2"
        new_floor["note"] = (
            "A MEASUREMENT, not an aspiration. Written by "
            "tools/xr/quality_ratchet.py --update, and only ever upward "
            "WITHIN ONE SUBSET. Each mutation entry records the targets and "
            "test subset it was measured over: a score earned under a "
            "different subset is a different measurement, not a better or "
            "worse one. See MX-015 in "
            "research/physical_validation/FAILURE_LEDGER.yaml.")
        os.makedirs(os.path.dirname(FLOOR), exist_ok=True)
        with open(FLOOR, "w", encoding="utf-8") as fh:
            json.dump(new_floor, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"floor updated: {FLOOR}")
        for line in actions:
            print(f"  {line}")
        print(json.dumps(new_floor, indent=2, sort_keys=True))
        return 0

    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if report["verdict"] == "REGRESSION":
        print(f"\nQUALITY RATCHET: {len(report['problems'])} regression(s)",
              file=sys.stderr)
        return 1
    if report["verdict"] == "NOT_COMPARABLE":
        # NOT PASS. The same rule as the nightly's INCONCLUSIVE.
        print("\nQUALITY RATCHET: NOT COMPARABLE -- "
              f"{len(report['not_comparable'])} metric(s) measured over a "
              "different subset than the floor. This is NOT a pass and NOT a "
              "regression; nothing was compared.", file=sys.stderr)
        return 2
    print("\nQUALITY RATCHET: HOLDS", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
