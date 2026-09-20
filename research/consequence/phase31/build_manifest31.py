"""Emit the Phase-3.1 SHA-256 manifest. Standard library only."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

FILES = {
    "amendment": ["research/consequence/phase31/PREREGISTRATION_PHASE31.md"],
    "phase31_implementation": [
        "csia_consequence/phase31_partitions.py",
        "csia_consequence/consequence_model31.py",
    ],
    "campaign_and_analysis": [
        "research/consequence/phase31/campaign31.py",
        "research/consequence/phase31/evaluate31.py",
    ],
    "frozen_inputs_phase2_and_phase3": [
        "research/consequence/results/GATE_INVENTORY.json",
        "research/consequence/results/INDEPENDENT_GATE_EVALUATION.json",
        "research/consequence/phase3/PREREGISTRATION_PHASE3.md",
        "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json",
        "research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json",
        "research/consequence/phase3/results/PHASE3_EVALUATION_LOCKED.json",
        "research/bus_provenance/results/E2M_MUTATION_RESULTS.json",
    ],
    "results": [
        "research/consequence/phase31/results/PHASE31_TRACES_DEVELOPMENT.json",
        "research/consequence/phase31/results/PHASE31_RESULTS_DEVELOPMENT.json",
        "research/consequence/phase31/results/PHASE31_TRACES_LOCKED.json",
        "research/consequence/phase31/results/PHASE31_RESULTS_LOCKED.json",
        "research/consequence/phase31/results/PHASE31_MUTATION_RESULTS.json",
    ],
    "write_up": [
        "research/consequence/phase31/PHASE31_RESULTS.md",
        "research/consequence/phase31/REPRODUCE31.md",
    ],
    "tests_and_mutation": [
        "tests/test_consequence_phase31.py",
        "tools/mutation/run_phase31_mutations.py",
    ],
}


def digest(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main() -> int:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True
                          ).stdout.strip()
    with open(os.path.join(ROOT, "docs/v1/FROZEN_BASELINE.json"),
              encoding="utf-8") as fh:
        baseline = json.load(fh)
    files = {rel: digest(rel) for group in FILES.values() for rel in group}
    document = {
        "schema": "csia.consequence.phase31_manifest/1",
        "head_at_build": head,
        "groups": {g: sorted(m) for g, m in sorted(FILES.items())},
        "files": dict(sorted(files.items())),
        "frozen_core": {
            "files_checked": len(baseline["files"]),
            "mismatches": [rel for rel, want in baseline["files"].items()
                           if digest(rel) != want]},
        "phase3_is_unchanged": (
            "the four Phase-3 artifacts above are listed so this manifest "
            "records that Phase 3.1 ran against them unmodified"),
        "note": ("A manifest says a document and the artifact it quotes were "
                 "committed together. It says nothing about whether either "
                 "is right."),
    }
    out = os.path.join(ROOT,
                       "research/consequence/phase31/SHA256_MANIFEST31.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)} ({len(files)} files, "
          f"frozen-core mismatches: {document['frozen_core']['mismatches']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
