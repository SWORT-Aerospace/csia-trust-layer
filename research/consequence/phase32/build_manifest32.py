"""Emit the Phase-3.2 SHA-256 manifest. Standard library only."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

FILES = {
    "amendment": ["research/consequence/phase32/PREREGISTRATION_PHASE32.md"],
    "phase32_implementation": [
        "csia_consequence/phase32_partitions.py",
        "csia_consequence/consequence_model31.py",
    ],
    "campaign_and_analysis": [
        "research/consequence/phase32/campaign32.py",
        "research/consequence/phase32/evaluate32.py",
    ],
    "frozen_inputs_earlier_phases": [
        "research/consequence/results/GATE_INVENTORY.json",
        "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json",
        "research/consequence/phase3/results/PHASE3_TRACES_LOCKED.json",
        "research/consequence/phase31/PREREGISTRATION_PHASE31.md",
        "research/consequence/phase31/results/PHASE31_RESULTS_LOCKED.json",
        "research/consequence/phase31/results/PHASE31_TRACES_LOCKED.json",
        "research/consequence/phase31/results/PHASE31_MUTATION_RESULTS.json",
        "research/bus_provenance/results/E2M_MUTATION_RESULTS.json",
        "research/physical_validation/FAILURE_LEDGER.yaml",
    ],
    "results": [
        "research/consequence/phase32/results/PHASE32_TRACES_DEVELOPMENT.json",
        "research/consequence/phase32/results/PHASE32_RESULTS_DEVELOPMENT.json",
        "research/consequence/phase32/results/PHASE32_TRACES_LOCKED.json",
        "research/consequence/phase32/results/PHASE32_RESULTS_LOCKED.json",
        "research/consequence/phase32/results/PHASE32_MUTATION_RESULTS.json",
    ],
    "write_up": [
        "research/consequence/phase32/PHASE32_RESULTS.md",
        "research/consequence/phase32/REPRODUCE32.md",
    ],
    "tests_and_mutation": [
        "tests/test_consequence_phase32.py",
        "tools/mutation/run_phase32_mutations.py",
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
        "schema": "csia.consequence.phase32_manifest/1",
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
                       "research/consequence/phase32/SHA256_MANIFEST32.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)} ({len(files)} files, "
          f"frozen-core mismatches: {document['frozen_core']['mismatches']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
