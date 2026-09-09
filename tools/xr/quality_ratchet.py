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

WHY THE FLOOR ALSO RECORDS A SOURCE DIGEST (MX-020)
----------------------------------------------------
This tool does not run the probes. It reads the mutation artifacts committed
under `research/mission/results/`, and **nothing regenerates them**: the
nightly's mutation stage writes to a run-scoped `build/nightly/<ts>/`, which
this tool never opens. So for a period the mutation half of the ratchet
compared committed files against a floor derived from those same committed
files, and reported HOLDS because the two sides were the same bytes. It could
not have failed. A gate that cannot fail is not a gate -- the same rule these
tests apply to everything else, applied here late.

The fix is not to run three probes every night; a stored score IS a valid
measurement of the code it was taken over, for as long as that code is
unchanged. What was missing is the link between the two. So both the floor and
(for probes run after this change) the artifact record a **digest of the target
files' contents**, and a score is comparable only while that digest still
matches the working tree. Change a target file and the gate goes
NOT_COMPARABLE until the probe is re-run -- which is the honest state, because
the stored number no longer describes the code.

Artifact-declared digests are authoritative. Where an artifact predates the
field, the floor's own recorded digest is used and the report marks the basis
`FLOOR_RECORDED` rather than `ARTIFACT_DECLARED`, so a weaker provenance is
never presented as a stronger one.

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

#: Every mutation metric the floor stores must appear here, or it is a number
#: kept by hand and gated by nothing. `mutation_assurance_baseline` was in the
#: floor and out of the loop for exactly that reason (MX-020); a test asserts
#: this tuple covers every mutation key the floor contains.
MUTATION_METRICS = ("mutation_mission", "mutation_frozen_core",
                    "mutation_assurance_baseline")

#: Which artifact each metric is read from. Declared ONCE: a second copy of
#: this mapping (there was one, in the tests) drifts the moment a metric is
#: repointed, and then asserts against a file nothing is measuring.
MUTATION_ARTIFACTS = {
    "mutation_mission": "research/mission/results/MUTATION_PROBE.json",
    # THE CORRECTED SUBSET, not the historical one. MX-015 records that the
    # 9-file subset behind MUTATION_PROBE_FROZEN_CORE.json omitted
    # tests/test_hypothesis.py, the file carrying most of the survivors, so
    # 0.35 was never "the frozen core's mutation score". That artifact stays
    # on disk unchanged as the record MX-015 refers to; gating on it would
    # mean ratcheting on a measurement known to mislead.
    "mutation_frozen_core": ("research/mission/results/"
                             "MUTATION_PROBE_FROZEN_CORE_CORRECTED.json"),
    "mutation_assurance_baseline": ("research/mission/results/"
                                    "MUTATION_PROBE_ASSURANCE_BASELINE.json"),
}

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


def targets_digest(targets) -> str | None:
    """Digest the CONTENTS of the target files as they are on disk now.

    A mutation score describes a specific body of code. Once that code
    changes the score is a statement about something that no longer exists,
    and comparing it to a new one is the MX-015 error in a different
    dimension. Returns None if any target is missing, because a partial
    digest that silently skips a deleted file would compare as equal.
    """
    if not targets:
        return None
    lines = []
    for rel in sorted(targets):
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            return None
        with open(full, "rb") as fh:
            lines.append(f"{hashlib.sha256(fh.read()).hexdigest()}  {rel}")
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()[:16]


def recount_sites(targets) -> int | None:
    """Count mutation sites in the targets now, using the probe's own counter.

    Imported from the probe rather than reimplemented: two counters that
    drift apart would report drift that is not there.
    """
    if not targets:
        return None
    try:
        import importlib.util
        probe_path = os.path.join(ROOT, "tools", "xr", "mutation_probe.py")
        spec = importlib.util.spec_from_file_location("_mp", probe_path)
        mp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mp)
    except Exception:
        return None
    total = 0
    for rel in targets:
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            return None
        with open(full, encoding="utf-8") as fh:
            total += mp._count_sites(fh.read())
    return total


def read_mutation(path: str) -> dict:
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return {"error": f"{path} not present"}
    with open(full, encoding="utf-8") as fh:
        doc = json.load(fh)
    targets = doc.get("targets")
    return {"score": doc.get("mutation_score"),
            "killed": doc.get("killed"),
            "evaluated": doc.get("evaluated"),
            "sites": doc.get("total_mutation_sites"),
            "subset_fingerprint": subset_fingerprint(doc),
            "targets": targets,
            "test_subset": doc.get("test_subset"),
            # What the probe itself recorded, if it was run after MX-020.
            "targets_digest_declared": doc.get("targets_digest"),
            # What those same files hash to right now.
            "targets_digest_live": targets_digest(targets),
            # An INDEPENDENT staleness signal that needs nothing new in the
            # artifact: the site count is a pure function of the targets'
            # syntax trees, and every artifact already records the one it
            # saw. Disagreement proves the artifact is stale even when the
            # digest evidence is only the floor's own weaker record.
            "sites_recomputed": recount_sites(targets),
            "artifact": path}


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

    # ALL THREE mutation metrics, not two. `mutation_assurance_baseline` was
    # measured, stored in the floor and then left out of this loop, so it was
    # a number kept up to date by hand and gated by nothing (MX-020).
    provenance = {}
    for key in MUTATION_METRICS:
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

        # IS THE STORED SCORE STILL ABOUT THE CODE IN THE TREE? Nothing
        # regenerates these artifacts, so without this the comparison is a
        # file against itself and HOLDS is guaranteed (MX-020).
        declared = (measured.get(key) or {}).get("targets_digest_declared")
        live = (measured.get(key) or {}).get("targets_digest_live")
        floor_digest = (floor.get(key) or {}).get("targets_digest")
        basis, reference = (("ARTIFACT_DECLARED", declared) if declared
                            else ("FLOOR_RECORDED", floor_digest))
        provenance[key] = {
            "basis": basis, "reference": reference, "live": live,
            "artifact": (measured.get(key) or {}).get("artifact"),
            "means": ("the probe recorded the source it measured"
                      if basis == "ARTIFACT_DECLARED" else
                      "the artifact predates targets_digest, so the floor's "
                      "own record of the source at --update time is used "
                      "instead. Weaker: it assumes the artifact was fresh "
                      "when the floor was raised."),
        }
        if reference is None or live is None:
            not_comparable.append({
                "metric": key, "reason": "UNKNOWN_SOURCE_PROVENANCE",
                "artifact_digest": declared, "floor_digest": floor_digest,
                "live_digest": live,
                "why": ("nothing links this score to a specific state of the "
                        "target files, so it cannot be shown to describe the "
                        "code in this tree. Re-run the probe and --update.")})
            continue
        # Independent of the digests: an artifact that saw a different number
        # of mutation sites than the targets have now is stale, full stop.
        stored_sites = (measured.get(key) or {}).get("sites")
        now_sites = (measured.get(key) or {}).get("sites_recomputed")
        provenance[key]["sites_recorded"] = stored_sites
        provenance[key]["sites_recomputed"] = now_sites
        if (stored_sites is not None and now_sites is not None
                and stored_sites != now_sites):
            not_comparable.append({
                "metric": key, "reason": "SITE_COUNT_DRIFT",
                "sites_in_artifact": stored_sites, "sites_now": now_sites,
                "why": ("the targets contain a different number of mutation "
                        "sites than when this artifact was written, so the "
                        "artifact is stale regardless of what the digests "
                        "say. Re-run the probe.")})
            continue

        if reference != live:
            not_comparable.append({
                "metric": key, "reason": "SOURCE_CHANGED", "basis": basis,
                "reference_digest": reference, "live_digest": live,
                "floor_score": fm, "measured_score": mm,
                "why": ("the target files have changed since this score was "
                        "recorded, so the stored number describes code that "
                        "is no longer here. It is neither a pass nor a "
                        "regression until the probe is re-run over the "
                        "current source.")})
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
        "source_provenance": provenance,
        "this_tool_does_not_run_the_probes": (
            "it reads the committed mutation artifacts; nothing regenerates "
            "them automatically. That is safe only because a score is "
            "compared against the source digest it was taken over, so a "
            "stored number cannot keep reading green after the code it "
            "describes has changed. See MX-020."),
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
    out = {key: read_mutation(path)
           for key, path in MUTATION_ARTIFACTS.items()}
    if not skip_coverage:
        out["coverage"] = measure_coverage()
    return out


INSTRUMENT = "tools.xr.quality_ratchet"


def _controls():
    """The pair this gate must pass before it reports anything.

    MX-020 IS THE REASON. This gate spent its whole life reporting HOLDS
    because it compared committed files against a floor derived from those
    same files -- it was structurally incapable of saying anything else, and
    nothing noticed. The POSITIVE control injects a synthetic regression and
    requires the gate to call it: a gate that cannot fail on a fabricated
    fall cannot fail on a real one.

    The NEGATIVE control feeds an identical measured/floor pair and requires
    HOLDS, catching the opposite defect -- a gate stuck on REGRESSION, which
    would be just as useless and rather louder.

    Both expectations follow from the definition of the comparison, not from
    anything this tool has previously reported.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _entry(score):
        return {"score": score, "subset_fingerprint": "c" * 16,
                "killed": 1, "evaluated": 2,
                "targets_digest": "d" * 16,
                "targets_digest_declared": "d" * 16,
                "targets_digest_live": "d" * 16,
                "sites": 100, "sites_recomputed": 100}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="an injected mutation-score fall is reported",
            kind=POSITIVE,
            run=lambda: check({"mutation_mission": _entry(0.10)},
                              {"mutation_mission": _entry(0.90)})["verdict"],
            expect=lambda verdict: verdict == "REGRESSION",
            basis=("a fall of 0.80 is far outside the declared tolerance of "
                   f"{MUTATION_TOLERANCE}; REGRESSION follows from the "
                   "comparison's definition"),
        ),
        negative=Control(
            name="an identical pair is not reported as a regression",
            kind=NEGATIVE,
            run=lambda: check({"mutation_mission": _entry(0.67)},
                              {"mutation_mission": _entry(0.67)})["verdict"],
            expect=lambda verdict: verdict == "HOLDS",
            basis=("equal scores over an identical subset and source cannot "
                   "be a quality change, by definition"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--update", action="store_true",
                    help="raise the floor to what was just measured")
    ap.add_argument("--skip-coverage", action="store_true")
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE. A gate that cannot demonstrate it
    # still detects a regression must not pronounce on a real one.
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    control_report = guard(INSTRUMENT)

    measured = measure_all(args.skip_coverage)
    floor = load_floor()
    report = stamp(check(measured, floor), control_report)

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
                        # WHAT SOURCE THIS SCORE DESCRIBES. Prefer what the
                        # probe itself recorded; fall back to hashing the
                        # targets now, which assumes the artifact is fresh --
                        # so say which of the two it was rather than leaving
                        # a reader to assume the stronger one.
                        "targets_digest": (value.get("targets_digest_declared")
                                           or value.get("targets_digest_live")),
                        "targets_digest_basis": (
                            "ARTIFACT_DECLARED"
                            if value.get("targets_digest_declared")
                            else "FLOOR_RECORDED_AT_UPDATE"),
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
            "research/physical_validation/FAILURE_LEDGER.yaml. Each entry "
            "also records targets_digest -- the contents of the target files "
            "the score was taken over. Nothing regenerates the mutation "
            "artifacts automatically, so this digest is what stops a stored "
            "score from reading green about code that has since changed. "
            "See MX-020.")
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
        # NAME THE ACTUAL REASON. "different subset" was the only reason
        # once, and printing it for a stale artifact or an unprovenanced one
        # would send the reader to fix the wrong thing.
        reasons = {}
        for nc in report["not_comparable"]:
            reasons.setdefault(nc["reason"], []).append(nc["metric"])
        print("\nQUALITY RATCHET: NOT COMPARABLE -- "
              f"{len(report['not_comparable'])} metric(s). This is NOT a "
              "pass and NOT a regression; nothing was compared.",
              file=sys.stderr)
        for reason, metrics in sorted(reasons.items()):
            print(f"  {reason}: {', '.join(sorted(metrics))}",
                  file=sys.stderr)
        return 2
    print("\nQUALITY RATCHET: HOLDS", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
