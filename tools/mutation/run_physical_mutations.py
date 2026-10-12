"""Mutation testing for the ADDITIVE physical-ingestion layer.

A SIXTH RUNNER, AND IT DELIBERATELY DOES NOT TOUCH `csia_e2m`
--------------------------------------------------------------
`csia_e2m` and `csia_bus_provenance` are covered by
`run_e2m_mutations.py` at 38 evaluated / 36 killed / 2 survived, and those
two survivors are quoted. This runner mutates only `csia_physical/*`, so the
E2M denominator does not move and neither survivor can be killed as a side
effect.

**No earlier phase's score is evidence about this code**, and this one is
not evidence about theirs.

BYTECODE IS PURGED AFTER EVERY EDIT
-------------------------------------
A same-length replacement restored inside one mtime tick leaves CPython
reusing the MUTATED .pyc, so the restore silently does nothing and every
later mutant is killed by damage that is not its own. That was observed on
the Phase-5 runner and is recorded as FL-042. This runner purges
`__pycache__` after apply, after restore, and before the baseline.

    python tools/mutation/run_physical_mutations.py
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "mutation"))

from run_e2m_mutations import (apply_from, package_files,  # noqa: E402
                               read_originals, restore_from,
                               sync_working_tree, working_tree_delta)
from run_mutations import (classify, drop_sandbox, make_sandbox,  # noqa: E402
                           run_tests)


def purge_bytecode(sandbox: str) -> int:
    """Delete every __pycache__ in the sandbox. See FL-042."""
    removed = 0
    for dirpath, dirnames, _files in os.walk(sandbox):
        for d in list(dirnames):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)
                dirnames.remove(d)
                removed += 1
    return removed


MUTANTS = []


def M(mid, family, path, old, new, breaks):
    MUTANTS.append({"id": mid, "family": family, "path": path, "old": old,
                    "new": new, "breaks": breaks})


ADAPTER = "csia_physical/csia_adapter.py"
ANNOT = "csia_physical/annotations.py"
EVID = "csia_physical/evidence_schema.py"
SUPPORT = "csia_physical/support_schema.py"
INIT = "csia_physical/__init__.py"

# ------------------------------------------- MISSINGNESS MUST NOT BECOME ZERO
M("PH-01", "MISSINGNESS", ADAPTER,
  "        cv = ChannelValue.absent(channel_name, missing_reason_for(status),\n"
  "                                 quality=Quality.UNAVAILABLE)",
  "        cv = ChannelValue(channel=channel_name, value=0,\n"
  "                          unit=observation.unit or \"\",\n"
  "                          quality=Quality.UNAVAILABLE)",
  "Serves a missing measurement as 0. This is the exact defect on record in "
  "research/evidence_semantics/ -- a -1 sentinel served as 5.00 A -- and a "
  "relation consumes a zero happily.")

M("PH-02", "MISSINGNESS", ADAPTER,
  "        if observation.value_milli is None:\n"
  "            raise AdapterError(",
  "        if False:\n"
  "            raise AdapterError(",
  "Lets a status of OK with no measurement through, so the adapter invents a "
  "value rather than refusing.")

M("PH-03", "MISSINGNESS", ADAPTER,
  "    return STATUS_TO_MISSING.get(status, UNKNOWN_STATUS_REASON)",
  "    return STATUS_TO_MISSING.get(status, MissingReason.NOT_RECEIVED)",
  "Absorbs an unknown status as 'not received', so a protocol change is "
  "silently reinterpreted as a fact about the bus.")

M("PH-04", "MISSINGNESS", ADAPTER,
  "    ERR_READBACK_MISMATCH: MissingReason.NOT_QUALIFIED,",
  "    ERR_READBACK_MISMATCH: MissingReason.NOT_RECEIVED,",
  "Reports a readback mismatch as 'not received'. Bytes DID arrive; the "
  "problem is that nobody can say which device sent them, and that is the "
  "distinction the mux identity work exists to preserve.")

# ------------------------------------------------------- THE GATES MUST HOLD
M("PH-05", "GATE", ADAPTER,
  "    if quality is Quality.INFORMATIVE:\n        raise QualificationBlocked(",
  "    if False:\n        raise QualificationBlocked(",
  "Allows a bench channel to be marked INFORMATIVE -- admissible as "
  "diagnostic evidence -- while the datasheet and inventory gates are open.")

M("PH-06", "GATE", ADAPTER,
  "MAX_QUALITY_WHILE_GATED = Quality.AVAILABLE_UNVALIDATED",
  "MAX_QUALITY_WHILE_GATED = Quality.INFORMATIVE",
  "Raises the gated ceiling to the one admissible rung, so every adapted "
  "channel becomes usable evidence without anything being verified.")

M("PH-07", "GATE", ADAPTER,
  '    raise QualificationBlocked(\n        "channel qualification requires',
  '    return None\n    raise QualificationBlocked(\n        "channel qualification requires',
  "Makes qualify() succeed silently instead of refusing while the hardware "
  "gates are open.")

# ------------------------------------------------- IDENTITY MISATTRIBUTION
M("PH-08", "IDENTITY", ADAPTER,
  "        if obs.sensor not in naming:\n            raise AdapterError(",
  "        if False:\n            raise AdapterError(",
  "Lets an undeclared sensor through, so the adapter invents a CSIA channel "
  "name for a device nobody declared. That IS misattribution.")

M("PH-09", "IDENTITY", ADAPTER,
  '            "readback_channel": self.readback_channel,',
  '            "readback_channel": self.commanded_channel,',
  "Reports the commanded channel as the readback, so a mux that answered on "
  "the wrong channel becomes indistinguishable from one that answered "
  "correctly.")

# ------------------------------------------------ RAW AND DERIVED SEPARATE
M("PH-10", "SEPARATION", EVID,
  "        if not self.derived_from:\n            raise EvidenceError(",
  "        if False:\n            raise EvidenceError(",
  "Permits an evidence record with no inputs, which is an assertion wearing "
  "the shape of a derivation.")

M("PH-11", "SEPARATION", EVID,
  "        if self.outcome != INDETERMINATE and not self.inputs_admissible:\n"
  "            raise EvidenceError(",
  "        if False:\n            raise EvidenceError(",
  "Permits AGREE or DISAGREE to be concluded from inadmissible inputs, which "
  "is the whole point of capping the channels.")

M("PH-12", "SEPARATION", ANNOT,
  "        if path.exists():\n            raise AnnotationError(",
  "        if False:\n            raise AnnotationError(",
  "Lets an annotation overwrite a previous one, so the operator's record of "
  "what they believed becomes mutable.")

M("PH-13", "SEPARATION", ANNOT,
  '            "wall_time_is_run_level_only": True,',
  '            "wall_time_is_run_level_only": False,',
  "Denies that wall time is run-level only, which is the claim that keeps "
  "per-record timing on the monotonic clock.")

# ------------------------------------------------------- GROUND TRUTH
M("PH-14", "GROUND_TRUTH", ANNOT,
  "CIRCULAR_BASES: Tuple[str, ...] = (BASIS_INFERRED,)",
  "CIRCULAR_BASES: Tuple[str, ...] = ()",
  "Stops flagging a ground truth inferred from the data under test, so a "
  "circular claim reads as an independent one.")

M("PH-15", "GROUND_TRUTH", ANNOT,
  "        if self.basis not in BASES:\n            raise AnnotationError(",
  "        if False:\n            raise AnnotationError(",
  "Accepts any string as a ground-truth basis, so 'how do you know' stops "
  "being answerable.")

M("PH-16", "GROUND_TRUTH", ANNOT,
  "        if not self.method:\n            raise AnnotationError(",
  "        if False:\n            raise AnnotationError(",
  "Accepts a fault annotation with no method, so how the fault was injected "
  "-- the part that makes it reproducible -- becomes optional.")

# ------------------------------------------------------- SUPPORT AND FORGE
M("PH-17", "SUPPORT", SUPPORT,
  "        if self.status == IDENTIFIABLE and self.inadmissible_channels:\n"
  "            raise SupportError(",
  "        if False:\n            raise SupportError(",
  "Permits IDENTIFIABLE support while a channel is inadmissible, so an "
  "unverified bench read can separate two hypotheses.")

M("PH-18", "SUPPORT", SUPPORT,
  "        states = {f: UNKNOWN for f in functions}\n"
  "        limiting = {f: support.reason for f in functions}",
  "        states = {f: INELIGIBLE for f in functions}\n"
  "        limiting = {f: support.reason for f in functions}",
  "Collapses UNKNOWN into INELIGIBLE, so 'we cannot determine this' is "
  "reported as a confident restriction.")

M("PH-19", "FORGE", SUPPORT,
  "FORGE_COMPATIBILITY_VERIFIED = False",
  "FORGE_COMPATIBILITY_VERIFIED = True",
  "Claims a verified Forge integration. No Forge code exists in this "
  "repository and governance forbids writing any.")

M("PH-20", "CLAIM", INIT,
  "HARDWARE_OPERATED = False",
  "HARDWARE_OPERATED = True",
  "Claims hardware was operated. All four E2M gates are open and this "
  "environment reports NO_HARDWARE_ACCESS.")

CANARY = {
    "id": "CANARY", "family": "CANARY", "path": ADAPTER,
    "old": 'ADAPTER_SCHEMA = "csia.physical.csia_input/1"',
    "new": 'ADAPTER_SCHEMA = "XXXX"',
    "breaks": "renames the adapter schema; nothing should validate",
}

DESELECT = []
SELECTION = ["tests/test_physical_ingest.py"]

OUT = os.path.join(ROOT, "research", "physical_ingest",
                   "PHYSICAL_MUTATION_RESULTS.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args(argv)

    selection = [s for s in SELECTION
                 if s.startswith("--")
                 or os.path.isfile(os.path.join(ROOT, s))]
    wanted = [m for m in MUTANTS
              if args.only is None or m["id"] in args.only]

    sandbox = make_sandbox()
    started = time.time()
    try:
        targets = sorted({m["path"] for m in MUTANTS} | {CANARY["path"]})
        synced = sync_working_tree(
            sandbox, targets + package_files(targets) + selection
            + working_tree_delta())
        originals = read_originals(sandbox, targets)

        purge_bytecode(sandbox)
        baseline = run_tests(sandbox, selection, timeout=args.timeout)
        if baseline["returncode"] != 0:
            raise SystemExit(
                "ABORT: the UNMUTATED selection does not pass in the sandbox "
                f"(exit {baseline['returncode']}, first failure "
                f"{baseline['first_failure']!r}). Refusing to report.")

        if not apply_from(sandbox, originals, CANARY):
            raise SystemExit("ABORT: canary anchor not found")
        purge_bytecode(sandbox)
        canary = run_tests(sandbox, selection, timeout=args.timeout)
        restore_from(sandbox, originals, CANARY["path"])
        purge_bytecode(sandbox)
        if canary["returncode"] == 0:
            raise SystemExit("ABORT: the canary SURVIVED.")

        results = []
        for mutant in wanted:
            if not apply_from(sandbox, originals, mutant):
                results.append({**mutant, "verdict": "INVALID_MUTANT",
                                "why": "anchor text not found"})
                print(f"  {mutant['id']:8s} INVALID_MUTANT", flush=True)
                continue
            purge_bytecode(sandbox)
            outcome = run_tests(sandbox, selection, timeout=args.timeout)
            restore_from(sandbox, originals, mutant["path"])
            purge_bytecode(sandbox)
            verdict = classify(mutant, outcome)
            first = outcome["first_failure"]
            results.append({**mutant, "verdict": verdict,
                            "first_failure": first,
                            "first_failure_is_test_node":
                                bool(first) and "::" in first,
                            "seconds": outcome["seconds"]})
            print(f"  {mutant['id']:8s} {verdict:15s} {first or ''}",
                  flush=True)
    finally:
        drop_sandbox(sandbox)

    evaluated = [r for r in results if r["verdict"] in ("KILLED", "SURVIVED")]
    killed = [r for r in evaluated if r["verdict"] == "KILLED"]
    score = (len(killed) / len(evaluated)) if evaluated else None
    document = {
        "schema": "csia.physical.mutation/1",
        "layer": "csia_physical -- the ADDITIVE physical-ingestion layer",
        "is_experimental": True,
        "hardware_operated": False,
        "separate_from": ("E2M (38/36/2), Phase-3.1 (11/8/3), Phase-3.2 "
                          "(12/12/0), Phase-4 (17/17/0) and Phase-5. This "
                          "runner mutates ONLY csia_physical/*, so the E2M "
                          "denominator does not move and neither E2M "
                          "survivor can be killed as a side effect."),
        "does_not_mutate": ["csia_e2m/*", "csia_bus_provenance/*",
                            "the twelve frozen-core files"],
        "targets": sorted({m["path"] for m in MUTANTS}),
        "selection": selection,
        "bytecode_purged_after_every_source_edit": True,
        "why_bytecode_is_purged": (
            "a same-length replacement restored within one mtime tick leaves "
            "CPython reusing the MUTATED .pyc, so the restore silently does "
            "nothing and later mutants are killed by damage that is not "
            "their own. See FL-042."),
        "working_tree_files_synced_into_sandbox": synced,
        "evaluated": len(evaluated), "killed": len(killed),
        "survived": len(evaluated) - len(killed),
        "invalid": len(results) - len(evaluated), "score": score,
        "elapsed_s": round(time.time() - started, 1),
        "baseline_unmutated": {"returncode": baseline["returncode"],
                               "seconds": baseline["seconds"]},
        "canary": {"verdict": "KILLED",
                   "first_failure": canary["first_failure"]},
        "kills_attributed_to_a_test_node": sum(
            1 for r in results if r["verdict"] == "KILLED"
            and r.get("first_failure_is_test_node")),
        "kills_attributed_to_a_bare_file": sum(
            1 for r in results if r["verdict"] == "KILLED"
            and not r.get("first_failure_is_test_node")),
        "results": results,
        "what_this_is_not": (
            "not evidence that hardware works, not a live-hardware result, "
            "and not a re-measurement of csia_e2m."),
    }
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
