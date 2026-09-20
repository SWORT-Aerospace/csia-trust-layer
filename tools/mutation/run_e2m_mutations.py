"""Mutation testing against the E2M acquisition layer and the bus-provenance model.

WHY A SEPARATE RUNNER
---------------------
`run_mutations.py` carries the *scientific* mutant list, and its results are
pinned by `QUALITY_FLOOR.json` with a `subset_fingerprint` and a
`targets_digest`. Appending to that list would change those digests and make a
committed baseline disagree with the code that produced it -- the defect
`MX-015` and `MX-020` exist for. So this is an additive sibling with its own
mutant list, its own selection and its own output file. The sandbox machinery
is imported rather than reimplemented.

WHAT A SURVIVOR MEANS HERE
--------------------------
The same thing it means there: a line can be changed without a single test
objecting, so no claim is pinned to it. A survivor is a finding about the
EVIDENCE, not a bug to paper over by writing a test that happens to catch that
one mutant.

The mutants below are not arbitrary. Each one is a specific way the owner's
§11 and §16 could be violated silently -- ASSUMED promoted to established
identity, a readback mistaken for physical attribution, a missing measurement
becoming zero, a corrupted frame accepted, a sequence gap absorbed. If a test
suite cannot tell those from correct behaviour, it is not holding the line the
decision document says it holds.

    python tools/mutation/run_e2m_mutations.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "mutation"))

from run_mutations import (classify, drop_sandbox,  # noqa: E402
                           make_sandbox, run_tests, _env, _run)


# The sandbox is `git worktree add --detach HEAD`, so it carries COMMITTED
# state only. This runner is meant to be usable BEFORE committing -- that is
# the whole point of measuring whether new tests kill new mutants -- so the
# working-tree version of every target and every selected test file is copied
# in, and the copy is what gets mutated and restored.
#
# TWO DEFECTS THIS MACHINERY HAS ALREADY PRODUCED, BOTH RECORDED RATHER THAN
# QUIETLY REPAIRED:
#
# 1. The first version reused `apply_mutation` from the science runner, which
#    restores with `git checkout --`. Against a synced file that silently
#    reverted to the committed version, and every mutant came back
#    INVALID_MUTANT because the uncommitted test files were absent from the
#    sandbox entirely. Restoring from a remembered copy removes both problems.
#
# 2. Syncing only the MUTATED files is not enough. The SUPPORT mutants added
#    `csia_consequence/gates.py` and `support.py`, but no mutant touches
#    `csia_consequence/partitions.py`, which `tests/test_consequence_gates.py`
#    imports. In the sandbox that import failed, pytest reported a COLLECTION
#    ERROR and exited 1, and `classify()` -- which cannot tell a collection
#    error from a behavioural failure -- returned KILLED for all 24 mutants.
#    A reported score of 1.0000 was therefore meaningless. The signature was
#    visible in the artifact: every `first_failure` was a bare file path with
#    no `::test_name`.
#
#    Two changes follow from that. `package_files()` syncs the whole package
#    directory of every mutant target, not just the mutated module. And
#    `main()` now runs the selection UNMUTATED first and aborts unless it
#    exits zero -- the counterpart to the canary. The canary proves the
#    selection is CONNECTED to the target; the baseline proves the selection
#    is GREEN, so that a later failure can be attributed to the mutant.

#: Working-tree files larger than this are not copied into the sandbox.
#: The first value tried was 1 MB, and it was wrong: the Phase-3 locked trace
#: file is 2.3 MB and `tests/test_consequence_phase3.py` reads it, so the cap
#: would have re-created the exact false-red it was meant to avoid. The sync
#: runs ONCE per campaign, not once per mutant, so a few megabytes costs
#: nothing measurable. The cap is here to stop an accidental multi-hundred-
#: megabyte artifact, not to shave megabytes off a copy.
MAX_SYNC_BYTES = 16_000_000

#: Files skipped by that cap, recorded so the omission is visible.
OVERSIZE: list = []


def working_tree_delta() -> list:
    """Every ``*.py`` where the working tree differs from HEAD.

    Defect 3, found by the baseline check the moment it was added:
    `tests/test_consequence_gates.py` puts `research/consequence/` on
    `sys.path` and imports `independent_gate_evaluator`, which is untracked
    and lives in no package directory, so `package_files()` did not reach it
    either. The full selection failed to collect and the baseline refused to
    report -- which is the check doing its job.

    Rather than name a third special case, this takes the general definition:
    the sandbox IS `HEAD`, so what it is missing is exactly the set of files
    the working tree has changed or added.

    Defect 4, found the same way -- by the baseline check refusing to report:
    restricting this to `*.py` was too narrow. `tests/test_consequence_phase3
    .py` reads the Phase-3 result JSON and compares it against a fresh
    analysis, so the DATA files are as load-bearing as the source. The scope
    is now source plus JSON, under a size cap sized to admit them.

    `MAX_SYNC_BYTES` is the cap, and a file that exceeds it is REPORTED in the
    run's artifact rather than dropped in silence -- a test that fails because
    its fixture was quietly too big is the same false-green this whole
    machinery exists to prevent.
    """
    proc = _run(["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"git status failed:\n{proc.stderr}")
    out = []
    for line in (proc.stdout or "").splitlines():
        if len(line) < 4:
            continue
        status, rel = line[:2], line[3:].strip()
        if "D" in status:            # deleted; nothing to copy
            continue
        if " -> " in rel:            # rename; take the destination
            rel = rel.split(" -> ", 1)[1]
        rel = rel.strip('"')
        if not rel.endswith((".py", ".json")) or "__pycache__" in rel:
            continue
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            continue
        if os.path.getsize(full) > MAX_SYNC_BYTES:
            OVERSIZE.append([rel, os.path.getsize(full)])
            continue
        out.append(rel)
    return out


def package_files(paths) -> list:
    """Every ``*.py`` in every package directory that holds a target.

    Coarser than the mutant list on purpose. A test importing a sibling
    module the mutant list never mentions is exactly the case that produced
    defect 2 above, and listing siblings by hand would reintroduce it the
    next time a module is added.
    """
    out = []
    for rel in paths:
        directory = os.path.dirname(rel)
        if not directory:
            continue
        full = os.path.join(ROOT, directory)
        if not os.path.isdir(full):
            continue
        for name in sorted(os.listdir(full)):
            if name.endswith(".py"):
                out.append(os.path.join(directory, name))
    return out


def sync_working_tree(sandbox: str, paths) -> list:
    copied = []
    for rel in sorted(set(paths)):
        source = os.path.join(ROOT, rel)
        if not os.path.isfile(source):
            continue
        target = os.path.join(sandbox, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)
        copied.append(rel)
    return copied


def read_originals(sandbox: str, paths) -> dict:
    out = {}
    for rel in sorted(set(paths)):
        full = os.path.join(sandbox, rel)
        if os.path.isfile(full):
            with open(full, encoding="utf-8") as fh:
                out[rel] = fh.read()
    return out


def apply_from(sandbox: str, originals: dict, mutant: dict) -> bool:
    text = originals.get(mutant["path"])
    if text is None or text.count(mutant["old"]) < 1:
        return False
    with open(os.path.join(sandbox, mutant["path"]), "w",
              encoding="utf-8") as fh:
        fh.write(text.replace(mutant["old"], mutant["new"], 1))
    return True


def restore_from(sandbox: str, originals: dict, rel: str) -> None:
    with open(os.path.join(sandbox, rel), "w", encoding="utf-8") as fh:
        fh.write(originals[rel])

MUTANTS = []


def M(mid, family, path, old, new, breaks, note=""):
    MUTANTS.append({"id": mid, "family": family, "path": path, "old": old,
                    "new": new, "breaks": breaks, "note": note})


# ----------------------------------------------------------------- IDENTITY
# The owner's section 11: ASSUMED must not establish attribution, and a
# register readback bounds the mux control state only.

M("ID-01", "IDENTITY", "csia_bus_provenance/provenance.py",
  "ESTABLISHED = frozenset({VERIFIED})",
  "ESTABLISHED = frozenset({VERIFIED, ASSUMED})",
  "Promotes ASSUMED to an established identity. This is the exact defect an "
  "earlier draft of the module shipped, and the one its own counterexample "
  "refuted. If nothing fails, the central claim is unpinned.")

M("ID-02", "IDENTITY", "csia_bus_provenance/provenance.py",
  "    if binding == ASSUMED:\n        return allow_assumed",
  "    if binding == ASSUMED:\n        return True",
  "Makes accepts() take ASSUMED regardless of the caller's opt-in, so the "
  "cost stops appearing in the caller's source.")

M("ID-03", "IDENTITY", "csia_e2m/identity.py",
  "ESTABLISHES_ATTRIBUTION = frozenset({PHYSICALLY_VERIFIED})",
  "ESTABLISHES_ATTRIBUTION = frozenset({PHYSICALLY_VERIFIED, "
  "READBACK_CONFIRMED})",
  "Treats a control-register readback as proof of which part is on the "
  "channel. The owner's section 11 forbids exactly this equivalence.")

M("ID-04", "IDENTITY", "csia_e2m/identity.py",
  "ESTABLISHES_ATTRIBUTION = frozenset({PHYSICALLY_VERIFIED})",
  "ESTABLISHES_ATTRIBUTION = frozenset({PHYSICALLY_VERIFIED, ASSUMED})",
  "Promotes ASSUMED in the longer chain-of-custody vocabulary.")

M("ID-05", "IDENTITY", "csia_e2m/identity.py",
  "CONTRADICTED = frozenset({MISATTRIBUTED, CONFLICTED})",
  "CONTRADICTED = frozenset({MISATTRIBUTED})",
  "Stops treating a conflict between operator and device identity as bad "
  "news, so a disagreement reads as merely weak evidence.")

# -------------------------------------------------------------- CHANNEL BOUNDS

M("CH-01", "CHANNEL", "csia_e2m/protocol.py",
  "        if not 0 <= self.commanded_channel <= 7:",
  "        if not 0 <= self.commanded_channel <= 15:",
  "Widens the commanded-channel bound past what a TCA9548A has. A frame "
  "naming channel 11 would be accepted as a real read.")

M("CH-02", "CHANNEL", "csia_e2m/replay.py",
  "        if not 0 <= channel <= 7:",
  "        if not 0 <= channel <= 255:",
  "Same widening at the replay boundary, where an impossible channel would "
  "reach a CSIA-facing observation.")

# --------------------------------------------------------------- MISSINGNESS
# Evidence-semantics finding 2 at the adapter boundary: missing is not zero.

M("MISS-01", "MISSING", "csia_e2m/protocol.py",
  "        return self.status == OK",
  "        return True",
  "Declares every record to carry a measurement, so an ERR_SENSOR_NACK "
  "frame's milli=0 is served as a real reading of zero.")

M("MISS-02", "MISSING", "csia_e2m/replay.py",
  "        has_value = status == OK",
  "        has_value = True",
  "The same, one layer up: a NACKed sensor becomes an observation of 0.")

M("MISS-03", "MISSING", "csia_e2m/replay.py",
  "        if has_value and not unit:",
  "        if False:",
  "Accepts a measurement with no unit. A number without a unit is not a "
  "measurement.")

# --------------------------------------------------------------------- CRC

M("CRC-01", "CRC", "csia_e2m/protocol.py",
  "    if actual != given_value:",
  "    if False:",
  "Disables CRC verification entirely. Every corrupted frame parses.")

M("CRC-02", "CRC", "csia_e2m/protocol.py",
  '    if "*" not in line:',
  "    if False:",
  "Accepts a frame with no CRC delimiter at all.")

M("CRC-03", "CRC", "csia_e2m/protocol.py",
  "    if len(parts) != FIELD_COUNT:",
  "    if len(parts) > 99:",
  "Accepts a truncated frame with too few fields, which is what a board "
  "resetting mid-write produces.")

M("CRC-04", "CRC", "csia_e2m/protocol.py",
  "        crc ^= byte << 8",
  "        crc ^= byte",
  "Breaks the CRC polynomial itself. The host and the firmware would then "
  "disagree, which the differential test exists to catch.")

M("CRC-05", "CRC", "csia_e2m/protocol.py",
  '    if any(c not in "0123456789ABCDEF" for c in given):',
  "    if False:",
  "Drops the uppercase requirement on the CRC field. `int(given, 16)` is "
  "case-insensitive, so 28B9 and 28b9 parse identically and a frame with one "
  "bit flipped in the CRC field decodes as valid. This was a live hole until "
  "the property test caught it; the mutant exists so it cannot come back "
  "unnoticed.")

# ---------------------------------------------------------- SEQUENCE + TIME

M("SEQ-01", "SEQUENCE", "csia_e2m/logging.py",
  "        if self._last_seq is not None and record.seq != self._last_seq + 1:",
  "        if False:",
  "Stops recording sequence gaps, so a dropped run of records becomes an "
  "unbroken stream.")

M("TIME-01", "TIME", "csia_e2m/replay.py",
  "        if previous_host_ns is not None and host_ns < previous_host_ns:",
  "        if False:",
  "Accepts a backwards host timestamp instead of refusing to replay, which "
  "silently permits out-of-order event time.")

# ------------------------------------------------------------------ TOPOLOGY

M("TOPO-01", "TOPOLOGY", "csia_bus_provenance/provenance.py",
  "    if len(candidates) > 1:",
  "    if False:",
  "Stops reporting AMBIGUOUS when two devices share an address under one "
  "register value, so the first candidate is returned as the source.")

M("TOPO-02", "TOPOLOGY", "csia_bus_provenance/provenance.py",
  "    if not candidates:",
  "    if False:",
  "Stops reporting NO_RESPONDER when nothing holds the address.")

# ------------------------------------------------------- SUPPORT (phase 2/5)
# Each of these is a way the support classifier could silently stop meaning
# what the preregistration says it means.

M("SUP-01", "SUPPORT", "csia_consequence/support.py",
  "    return low_sets[a] ^ low_sets[b]",
  "    return low_sets[a] | low_sets[b]",
  "Replaces symmetric difference with union, so a feature present in BOTH "
  "LOW-sets counts as separating. That feature contributes an identical term "
  "to both log-likelihoods and cancels exactly; treating it as a witness "
  "manufactures support that does not exist.")

M("SUP-02", "SUPPORT", "csia_consequence/support.py",
  "    if len(hypotheses) == 1:",
  "    if False:",
  "Lets a one-hypothesis set report IDENTIFIABLE. A set with nothing to "
  "distinguish trivially 'identifies' its only member, which is not evidence.")

M("SUP-03", "SUPPORT", "csia_consequence/support.py",
  "    active = tuple(sorted(k for k, w in gates.items() if w > gate_epsilon))",
  "    active = tuple(sorted(k for k, w in gates.items()))",
  "Counts gated-off features as active, so self-occlusion becomes "
  "IDENTIFIABLE.")

M("SUP-04", "SUPPORT", "csia_consequence/support.py",
  "    if not unseparated:",
  "    if True:",
  "Reports IDENTIFIABLE whenever anything separates, collapsing AMBIGUOUS "
  "into a confident answer.")

M("SUP-05", "SUPPORT", "csia_consequence/gates.py",
  "        return (self.coupling == FRESHNESS_INDEPENDENT",
  "        return (self.coupling != FRESHNESS_INDEPENDENT",
  "Inverts the uncovered-candidate test, so freshness-coupled gates are "
  "reported as uncovered and the eight become the wrong eight.")

M("SUP-06", "SUPPORT", "csia_consequence/support.py",
  "        if self.reason not in REASONS:",
  "        if False:",
  "Lets an unknown reason code through, so a state could be explained by a "
  "string nobody defined.")

# ----------------------------------------------- PHASE 3 (consequence/policy)
# Each of these is a way the Phase-3 measurement could silently stop measuring
# what the preregistration says it measures.

M("P3-01", "PHASE3", "csia_consequence/action_adapter.py",
  "    if base.response in ATTRIBUTING and \\\n            pair_report.status != _support.IDENTIFIABLE:",
  "    if False:",
  "Stops P2 withdrawing an attribution when the pair that attribution "
  "discriminates is not identifiable. P2 then IS P0, and any H3 result would "
  "be an artefact of nothing.")

M("P3-02", "PHASE3", "csia_consequence/action_adapter.py",
  "    if base.response in ATTRIBUTING and",
  "    if base.response not in ATTRIBUTING and",
  "Makes P2 withdraw exactly the responses that assert no attribution -- a "
  "controlled descent cancelled because attribution is ambiguous. That is a "
  "false refusal with a real cost, and the phase claims it does not happen.")

M("P3-03", "PHASE3", "csia_consequence/action_adapter.py",
  "        weights[key] = float(gate)",
  "        weights[key] = 1.0",
  "Reports every edge gate as fully open, so no occlusion is ever visible to "
  "support and the whole Phase-3 question disappears.")

M("P3-04", "PHASE3", "csia_consequence/action_adapter.py",
  "    return p2_support(state, sources=DECISION_PAIR, provenance=provenance)",
  "    return p2_support(state, provenance=provenance)",
  "Asks whether ANY two sources are separable instead of whether THIS "
  "attribution is supported. The policy would then consult a different "
  "question from the one it is about to act on.")

M("P3-05", "PHASE3", "csia_consequence/consequence_model.py",
  "        return (WRONG_SOURCE_FACTOR if chosen == faulty_source\n"
  "                else MITIGATED_FRACTION)",
  "        return MITIGATED_FRACTION",
  "Makes selecting the FAULTY inertial unit cost the same as selecting the "
  "good one. H2 then cannot be falsified in either direction, because a "
  "confident wrong attribution becomes indistinguishable from a right one.")

M("P3-06", "PHASE3", "csia_consequence/consequence_model.py",
  "        if tick[\"airborne\"]:",
  "        if True:",
  "Accrues position error while the vehicle is on the ground, which would "
  "manufacture a consequence out of a pre-flight fault that has none.")

M("P3-07", "PHASE3", "csia_consequence/consequence_model.py",
  "        return R_SELECT_IMU1 if faulty_source == \"imu0\" else R_SELECT_IMU0",
  "        return R_SELECT_IMU0 if faulty_source == \"imu0\" else R_SELECT_IMU1",
  "Inverts ground truth: the correct response becomes selecting the faulty "
  "unit. Every CORRECT_ACTIONABLE and INCORRECT_ACTIONABLE verdict flips.")

M("P3-08", "PHASE3",
  "research/consequence/phase3/independent_consequence_evaluator.py",
  "    return RESPONSE_CLASS[a] != RESPONSE_CLASS[b]",
  "    return False",
  "Declares no two responses materially different, so H2's third clause can "
  "never be satisfied and the evaluator would report a rejection whatever "
  "the traces said.")

M("P3-09", "PHASE3",
  "research/consequence/phase3/independent_consequence_evaluator.py",
  "            if response in ATTRIBUTING:\n                unsupported_s += span",
  "            if False:\n                unsupported_s += span",
  "Stops counting a confident attribution issued while its separating "
  "evidence is gated off -- the one measurement the phase is for.")

M("P3-10", "PHASE3",
  "research/consequence/phase3/independent_consequence_evaluator.py",
  "        if not seg[\"airborne\"]:\n            continue\n"
  "        if not all(seg[\"gates_open\"].values()):",
  "        if not all(seg[\"gates_open\"].values()):",
  "Counts occlusion on the ground toward the overlap with the decision "
  "window. The armed-gate result turns on that overlap being zero, and this "
  "would make it non-zero for a reason that means nothing.")

M("P3-11", "PHASE3", "research/consequence/phase3/analyze.py",
  "    return min(1.0, 2.0 * tail)",
  "    return tail",
  "Turns the exact McNemar test one-sided. H2's verdict is decided by this "
  "number, and halving it is the cheapest possible way to manufacture a "
  "finding out of 3-versus-1.")

M("P3-12", "PHASE3", "research/consequence/phase3/analyze.py",
  '        "verdict": ("SUPPORTED" if physical and attributable\n'
  '                    else "NOT SUPPORTED"),',
  '        "verdict": ("SUPPORTED" if physical\n'
  '                    else "NOT SUPPORTED"),',
  "Declares H2 supported whenever any conflict exists, dropping the "
  "requirement that a matched control separate it from chance. That is the "
  "difference between a result and a coincidence.")

M("P3-13", "PHASE3", "research/consequence/phase3/analyze.py",
  "    physical = [c for c in conflicts\n"
  "                if not (c[\"gate_group\"] == \"armed_gate_pair\"\n"
  "                        and c[\"condition\"] == \"F\")]",
  "    physical = list(conflicts)",
  "Counts the physically inconsistent control -- a vehicle reporting "
  "disarmed while its sensors show it flying -- as evidence about real "
  "flight.")

#: The canary must be killed. If it survives, the sandbox is not live or the
#: selection is disconnected, and every reported survivor would be false.
CANARY = {
    "id": "CANARY", "family": "CANARY",
    "path": "csia_e2m/protocol.py",
    "old": "MAGIC = \"E2M1\"", "new": "MAGIC = \"XXXX\"",
    "breaks": "changes the frame magic; nothing should decode",
}

SELECTION = ["tests/test_e2m_acquisition.py", "tests/test_bus_provenance.py",
             "tests/test_e2m_properties.py", "tests/test_e2m_schemas.py",
             "tests/test_e2m_transport.py",
             "tests/test_consequence_gates.py",
             "tests/test_consequence_support.py",
             "tests/test_consequence_phase3.py"]

OUT = os.path.join(ROOT, "research", "bus_provenance", "results",
                   "E2M_MUTATION_RESULTS.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)

    selection = [s for s in SELECTION
                 if os.path.isfile(os.path.join(ROOT, s))]
    wanted = [m for m in MUTANTS
              if args.only is None or m["id"] in args.only]

    sandbox = make_sandbox()
    started = time.time()
    try:
        targets = [m["path"] for m in MUTANTS] + [CANARY["path"]]
        synced = sync_working_tree(
            sandbox, targets + package_files(targets) + selection
            + working_tree_delta())
        originals = read_originals(
            sandbox, [m["path"] for m in MUTANTS] + [CANARY["path"]])
        # The sandbox must import the sandbox, not the editable install.
        proc = _run([sys.executable, "-c",
                     "import csia_e2m, json; print(json.dumps("
                     "csia_e2m.__file__))"],
                    cwd=sandbox, env=_env(sandbox))
        if proc.returncode != 0:
            raise SystemExit(f"sandbox import failed:\n{proc.stderr}")
        loaded = json.loads(proc.stdout.strip())
        if not os.path.realpath(loaded).startswith(os.path.realpath(sandbox)):
            raise SystemExit(
                f"ABORT: sandbox not live. csia_e2m resolved to {loaded}, "
                f"outside {sandbox}; every result would be a false SURVIVED.")

        # BASELINE. Unmutated, and it must be green. Without this a broken
        # sandbox reads as a perfect score, because every mutant "fails".
        baseline = run_tests(sandbox, selection, timeout=args.timeout)
        if baseline["returncode"] != 0:
            raise SystemExit(
                "ABORT: the UNMUTATED selection does not pass in the "
                f"sandbox (exit {baseline['returncode']}, first failure "
                f"{baseline['first_failure']!r}). Every mutant would be "
                "reported KILLED by that same failure, so the score would "
                "be meaningless. Refusing to report.")

        if not apply_from(sandbox, originals, CANARY):
            raise SystemExit("ABORT: canary anchor not found")
        canary = run_tests(sandbox, selection, timeout=args.timeout)
        restore_from(sandbox, originals, CANARY["path"])
        if canary["returncode"] == 0:
            raise SystemExit(
                "ABORT: the canary SURVIVED. Changing the frame magic broke "
                "nothing the selection noticed, so the selection is wrong or "
                "the sandbox is not live. Refusing to report results that "
                "would all be false survivors.")

        results = []
        for mutant in wanted:
            if not apply_from(sandbox, originals, mutant):
                results.append({**mutant, "verdict": "INVALID_MUTANT",
                                "why": "anchor text not found in the file"})
                print(f"  {mutant['id']:10s} INVALID_MUTANT (anchor missing)",
                      flush=True)
                continue
            outcome = run_tests(sandbox, selection, timeout=args.timeout)
            restore_from(sandbox, originals, mutant["path"])
            verdict = classify(mutant, outcome)
            first = outcome["first_failure"]
            results.append({**mutant, "verdict": verdict,
                            "first_failure": first,
                            # A kill attributed to a bare file path rather
                            # than a test node is the collection-error
                            # signature of defect 2. The baseline check above
                            # should make it impossible; recording it means a
                            # reader does not have to take that on trust.
                            "first_failure_is_test_node":
                                bool(first) and "::" in first,
                            "seconds": outcome["seconds"]})
            print(f"  {mutant['id']:10s} {verdict:15s} "
                  f"{outcome['first_failure'] or ''}", flush=True)
    finally:
        drop_sandbox(sandbox)

    evaluated = [r for r in results if r["verdict"] in ("KILLED", "SURVIVED")]
    killed = [r for r in evaluated if r["verdict"] == "KILLED"]
    score = (len(killed) / len(evaluated)) if evaluated else None

    document = {
        "schema": "csia.e2m.mutation_results/1",
        "targets": sorted({m["path"] for m in MUTANTS}),
        "selection": selection,
        "working_tree_files_synced_into_sandbox": synced,
        "uncommitted_files_synced": working_tree_delta(),
        "oversize_working_tree_files_not_synced": list(OVERSIZE),
        "max_sync_bytes": MAX_SYNC_BYTES,
        "evaluated": len(evaluated),
        "killed": len(killed),
        "survived": len(evaluated) - len(killed),
        "invalid": len(results) - len(evaluated),
        "score": score,
        "elapsed_s": round(time.time() - started, 1),
        "baseline_unmutated": {"returncode": baseline["returncode"],
                               "seconds": baseline["seconds"]},
        "canary": {"verdict": "KILLED", "first_failure":
                   canary["first_failure"]},
        "kills_attributed_to_a_test_node": sum(
            1 for r in results
            if r["verdict"] == "KILLED" and r.get("first_failure_is_test_node")),
        "kills_attributed_to_a_bare_file": sum(
            1 for r in results
            if r["verdict"] == "KILLED"
            and not r.get("first_failure_is_test_node")),
        "by_family": {},
        "results": results,
        "what_this_is_not": (
            "not evidence about hardware. Every mutant and every test here "
            "runs against a fake controller and recorded fixtures. A high "
            "score means the tests would notice a change in the SOFTWARE."),
    }
    for r in evaluated:
        fam = document["by_family"].setdefault(
            r["family"], {"evaluated": 0, "killed": 0})
        fam["evaluated"] += 1
        fam["killed"] += r["verdict"] == "KILLED"
    for fam in document["by_family"].values():
        fam["score"] = fam["killed"] / fam["evaluated"]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")

    print(f"\nevaluated {len(evaluated)}  killed {len(killed)}  "
          f"survived {len(evaluated) - len(killed)}  "
          f"score {score if score is None else round(score, 4)}")
    print(f"wrote {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
