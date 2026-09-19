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
# The first version reused `apply_mutation` from the science runner, which
# restores with `git checkout --`. Against a synced file that silently
# reverted to the committed version, and every mutant came back
# INVALID_MUTANT because the uncommitted test files were absent from the
# sandbox entirely. Restoring from a remembered copy removes both problems.

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
             "tests/test_e2m_transport.py"]

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
        synced = sync_working_tree(
            sandbox, [m["path"] for m in MUTANTS] + [CANARY["path"]]
            + selection)
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
            results.append({**mutant, "verdict": verdict,
                            "first_failure": outcome["first_failure"],
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
        "evaluated": len(evaluated),
        "killed": len(killed),
        "survived": len(evaluated) - len(killed),
        "invalid": len(results) - len(evaluated),
        "score": score,
        "elapsed_s": round(time.time() - started, 1),
        "canary": {"verdict": "KILLED", "first_failure":
                   canary["first_failure"]},
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
