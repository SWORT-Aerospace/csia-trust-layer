"""Emit the Phase-3 SHA-256 manifest.

Standard library only. Lists every file the phase produced or depends on, so
a reader can establish that the document they are holding and the artifact it
quotes are the same pair that were committed together.

    python research/consequence/phase3/build_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

#: Grouped so a reader can see what kind of thing each file is.
FILES = {
    "preregistration": [
        "research/consequence/phase3/PREREGISTRATION_PHASE3.md",
    ],
    "code_under_measurement_frozen": [
        "csia/runtime/online.py",
        "csia/runtime/failsafe.py",
        "csia/diagnosis/causal.py",
        "csia/diagnosis/hypothesis.py",
    ],
    "phase3_implementation": [
        "csia_consequence/phase3_partitions.py",
        "csia_consequence/action_adapter.py",
        "csia_consequence/consequence_model.py",
        "csia_consequence/support.py",
    ],
    "campaign_and_analysis": [
        "research/consequence/phase3/campaign.py",
        "research/consequence/phase3/independent_consequence_evaluator.py",
        "research/consequence/phase3/analyze.py",
    ],
    "phase2_inputs": [
        "research/consequence/results/GATE_INVENTORY.json",
        "research/consequence/results/INDEPENDENT_GATE_EVALUATION.json",
        "csia_consequence/gates.py",
        "research/consequence/independent_gate_evaluator.py",
    ],
    "results": [
        "research/consequence/phase3/results/PHASE3_TRACES_DEVELOPMENT.json",
        "research/consequence/phase3/results/PHASE3_EVALUATION_DEVELOPMENT.json",
        "research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json",
        "research/consequence/phase3/results/PHASE3_EVALUATION_LOCKED.json",
        "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json",
    ],
    "write_up": [
        "research/consequence/phase3/PHASE3_RESULTS.md",
        "research/consequence/phase3/REPRODUCE.md",
    ],
    "tests": [
        "tests/test_consequence_phase3.py",
    ],
    "mutation": [
        "tools/mutation/run_e2m_mutations.py",
        "research/bus_provenance/results/E2M_MUTATION_RESULTS.json",
    ],
}


def digest(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def frozen_core() -> dict:
    with open(os.path.join(ROOT, "docs/v1/FROZEN_BASELINE.json"),
              encoding="utf-8") as fh:
        baseline = json.load(fh)
    mismatches = [rel for rel, want in baseline["files"].items()
                  if digest(rel) != want]
    return {"files_checked": len(baseline["files"]),
            "mismatches": mismatches,
            "aggregate_recipe": ("sha256 over '{path}:{sha256}\\n' for the "
                                 "baseline files in sorted path order"),
            "aggregate": hashlib.sha256("".join(
                f"{rel}:{digest(rel)}\n"
                for rel in sorted(baseline["files"])).encode()).hexdigest()}


def main() -> int:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True)
    files = {}
    for group, members in FILES.items():
        for rel in members:
            files[rel] = digest(rel)
    document = {
        "schema": "csia.consequence.phase3_manifest/1",
        "head_at_build": proc.stdout.strip(),
        "groups": {g: sorted(m) for g, m in sorted(FILES.items())},
        "files": dict(sorted(files.items())),
        "frozen_core": frozen_core(),
        "note": ("A manifest establishes that a document and the artifact it "
                 "quotes were committed together. It establishes nothing "
                 "about whether either is right."),
    }
    out = os.path.join(ROOT, "research/consequence/phase3/SHA256_MANIFEST.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)}  ({len(files)} files, "
          f"frozen-core mismatches: {document['frozen_core']['mismatches']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
