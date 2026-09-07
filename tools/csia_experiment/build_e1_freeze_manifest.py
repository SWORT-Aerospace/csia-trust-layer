"""Generate the E1 freeze manifest: what was frozen, and by what hash.

E1 IS **CURRENT-STACK REPEATED SOFTWARE VALIDATION**. It is not physical
validation, and this file says so in the state name so that a reader who sees
only the manifest cannot mistake it.

WHY EVERY HASH IS COMPUTED HERE
--------------------------------
A freeze manifest whose hashes were typed is a claim about a state, not a
record of one. Every digest below is computed from the file at generation
time; `tests/test_e1_freeze_manifest.py` recomputes and compares, so a file
that moves after the freeze fails loudly instead of silently invalidating the
manifest.

Directories are hashed as a MANIFEST OF PER-FILE DIGESTS, not as a tarball:
a tarball hash changes with mtime and ordering, which would make the manifest
unstable for reasons that have nothing to do with the evidence.

WHAT A FREEZE DOES NOT MEAN
----------------------------
It does not mean the work is correct, complete, or independently replicated.
It means: this is the state the E1 claims were adjudicated against, and any
later change to a listed file is visible.
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

STATE_NAME = "E1 - CURRENT-STACK REPEATED SOFTWARE VALIDATION"

#: The six frozen scientific paths. Named here, not globbed, so adding a file
#: to the core cannot silently enter the freeze.
FROZEN_PATHS = (
    "csia/trust_engine",
    "csia/diagnosis",
    "csia/runtime/online.py",
    "csia/runtime/failsafe.py",
    "csia/scenarios.py",
    "csia/profiles.py",
)

CAMPAIGNS = (
    "campaigns/physical_validation/mechanism_a_repeat_ap",
    "campaigns/physical_validation/mechanism_a_trust_completion_a2",
    "campaigns/physical_validation/mechanism_a_px4_repeat_p1",
)

PREREGS = (
    "research/physical_validation/prereg/"
    "MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md",
    "research/physical_validation/prereg/"
    "MECHANISM_A_ARDUPILOT_TRUST_COMPLETION_PREREG.md",
    "research/physical_validation/prereg/MECHANISM_A_PX4_REPEATED_PREREG.md",
    "research/physical_validation/prereg/"
    "PX4_ORIGINAL_ENVIRONMENT_RECONSTRUCTION.md",
)

RAW_TRACE_ARCHIVES = (
    "research/physical_validation/results/a2_traces_raw",
    "research/physical_validation/results/p1_traces_raw",
)

EXTRACTORS = (
    "tools/csia_experiment/extract_trust_a2.py",
    "tools/csia_experiment/extract_mechanism_a.py",
    "tools/csia_experiment/run_mechanism_a_repeat.py",
    "tools/csia_experiment/watchdog_replay.py",
    "tools/csia_experiment/build_e1_claim_table.py",
)

CLAIM_TABLE = "research/physical_validation/E1_FINAL_CLAIM_TABLE.csv"

PAPERS = (
    "papers/csia_systems/main.tex",
    "papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml",
    "papers/gate_conditioning/main.tex",
)

RESULTS = (
    "research/physical_validation/results/mechanism_a_repeat_ardupilot.json",
    "research/physical_validation/results/mechanism_a_a2_trust_ardupilot.json",
    "research/physical_validation/results/mechanism_a_p1_trust_px4.json",
    "research/physical_validation/results/"
    "ARDUPILOT_MECHANISM_A_REPEAT_TABLE.csv",
    "research/physical_validation/results/PX4_MECHANISM_A_REPEAT_TABLE.csv",
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


#: Build artifacts that are NOT source and must not be hashed as if they
#: were. See `sha256_tree`.
BUILD_ARTIFACT_DIRS = ("__pycache__",)
BUILD_ARTIFACT_SUFFIXES = (".pyc", ".pyo")


def is_source(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in BUILD_ARTIFACT_DIRS for p in parts):
        return False
    return not rel_path.endswith(BUILD_ARTIFACT_SUFFIXES)


def sha256_tree(rel: str, source_only: bool = False) -> dict:
    """A directory's digest, as a hash over sorted `sha256  relpath` lines.

    Stable under filesystem ordering, unlike a tarball hash, and the
    per-file count is reported so a silently-shrunk directory is visible.

    `source_only=True` EXCLUDES BUILD ARTIFACTS, and that is the only form
    that means anything across machines.

    WHY, MEASURED (HF-008): the default form walks every file, so
    `__pycache__/*.pyc` is hashed alongside the source. CPython's default
    timestamp-based invalidation embeds the SOURCE MTIME in the .pyc
    header, so a file rewritten and restored byte-identically still yields
    a different .pyc and a different directory digest. The docstring used
    to claim stability under mtime; through the bytecode it had none.

    It is worse than a false alarm. The recorded E1 digests count
    `csia/trust_engine` as 4 files where the directory holds 2 sources, and
    `csia/diagnosis` as 12 where it holds 6. A FRESH CLONE HAS NO
    `__pycache__` AT ALL, so those digests cannot be reproduced anywhere
    the artifact was not built -- the same shape as the freeze-tag test
    that skips on a fresh clone, and a skip looks like a pass.
    """
    base = os.path.join(ROOT, rel)
    entries = []
    for dirpath, _dirs, names in os.walk(base):
        for n in sorted(names):
            p = os.path.join(dirpath, n)
            rel_path = os.path.relpath(p, base)
            if source_only and not is_source(rel_path):
                continue
            entries.append(f"{sha256_file(p)}  {rel_path}")
    entries.sort()
    body = "\n".join(entries) + "\n"
    return {"files": len(entries),
            "sha256_of_file_manifest": hashlib.sha256(
                body.encode()).hexdigest()}


def _files(rels):
    out = {}
    for rel in rels:
        p = os.path.join(ROOT, rel)
        out[rel] = sha256_file(p) if os.path.isfile(p) else "ABSENT"
    return out


def _frozen():
    out = {}
    for rel in FROZEN_PATHS:
        p = os.path.join(ROOT, rel)
        out[rel] = (sha256_file(p) if os.path.isfile(p)
                    else sha256_tree(rel) if os.path.isdir(p) else "ABSENT")
    return out


def _git(*args):
    proc = subprocess.run(["git", "-C", ROOT, *args], capture_output=True,
                          text=True, timeout=60)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _campaign_counts():
    out = {}
    for rel in CAMPAIGNS:
        report = os.path.join(ROOT, rel, "_report.json")
        if not os.path.exists(report):
            out[rel] = {"report": "ABSENT"}
            continue
        with open(report, encoding="utf-8") as fh:
            r = json.load(fh)
        out[rel] = {k: r.get(k) for k in
                    ("planned", "attempted", "valid", "invalid",
                     "not_attempted")}
        out[rel]["by_state"] = r.get("by_state")
        out[rel]["tree"] = sha256_tree(rel)
    return out


def build(test_count: int | None, test_failures: int | None) -> dict:
    return {
        "schema": "csia.research.e1_freeze_manifest/1",
        "state": STATE_NAME,
        "state_is_not": [
            "physical validation",
            "hardware validation",
            "flight validation",
            "any evidence tier above E1",
        ],
        "what_a_freeze_means": (
            "This is the state the E1 claims were adjudicated against, and "
            "any later change to a listed file is visible. It does NOT mean "
            "the work is correct, complete, or independently replicated."),
        "generated_by": "tools/csia_experiment/build_e1_freeze_manifest.py",
        "head_commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "frozen_core": {
            "paths": list(FROZEN_PATHS),
            "digests": _frozen(),
            "note": (
                "Byte-identical to tag csia-v1.0-research-final. THE TAG IS "
                "LOCAL ONLY (push refused HTTP 403), so the tag-diff test "
                "SKIPS on a fresh clone; the recorded-hash check runs "
                "everywhere and is what these digests support."),
        },
        "campaigns": _campaign_counts(),
        "preregistrations": {
            "digests": _files(PREREGS),
            "note": (
                "Each was committed BEFORE the trials it governs, which is "
                "checkable from git rather than from a claim in the "
                "document; tests/test_prereg_freeze.py compares each blob "
                "against its freeze commit."),
        },
        "raw_trace_archives": {
            rel: sha256_tree(rel) for rel in RAW_TRACE_ARCHIVES
            if os.path.isdir(os.path.join(ROOT, rel))
        },
        "extractors": _files(EXTRACTORS),
        "claim_table": _files((CLAIM_TABLE,)),
        "results": _files(RESULTS),
        "papers": _files(PAPERS),
        "tests": {
            "collected": test_count,
            "failures": test_failures,
            "note": ("Counts are passed in by the operator running the suite; "
                     "this script does not run pytest, so it cannot report a "
                     "number it did not observe."),
        },
        "known_open_at_freeze": [
            "FL-019: why ArduPilot's PRE-fault trust was insensitive to the "
            "0.5 s -> 1.0 s watchdog change is UNRESOLVED. Not forced.",
            "The four freeze tags are local-only; the remote carries only "
            "v0.7.0. A fresh clone's tag-diff test skips.",
            "Zero bibliography entries are publisher-verified.",
            "50 unmapped prose numeric literals remain in the systems "
            "manuscript. They predate this pass, which added four scalars "
            "and bound all four (S14-S17), so the count is unchanged.",
            "CONFIGURATION-02 is still pinned by a file hash alone, "
            "deliberately.",
            "independent_checker_agreement remains ARTIFACT_SUMMARY_ONLY.",
            "No independent replication of any campaign has been attempted.",
        ],
        "next_tier": {
            "tier": "E2",
            "objective": (
                "run the SAME frozen CSIA core against real "
                "flight-controller hardware over a real telemetry boundary"),
            "not_yet": "physical GNSS fault -- that is E3",
            "packet": "hardware/validation_rig/E2_BUILD_PACKET.md",
            "blocked_on": "physical hardware the user must supply",
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tests", type=int, default=None,
                    help="collected test count, as observed by the operator")
    ap.add_argument("--failures", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "physical_validation", "E1_FREEZE_MANIFEST.yaml"))
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    import yaml
    doc = build(args.tests, args.failures)
    text = ("%YAML 1.2\n---\n"
            "# GENERATED by tools/csia_experiment/build_e1_freeze_manifest.py\n"
            "# Do not edit by hand: tests/test_e1_freeze_manifest.py\n"
            "# recomputes every digest and compares.\n"
            + yaml.safe_dump(doc, sort_keys=False, width=78,
                             default_flow_style=False))
    from tools.evidence_guard import protected_write
    with protected_write(args.out, regenerate=args.regenerate) as fh:
        fh.write(text)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
