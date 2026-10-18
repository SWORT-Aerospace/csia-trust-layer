"""Emit the Phase-4 SHA-256 manifest. Standard library only."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FILES = {
    "preregistration": ["research/phase4/PREREGISTRATION_PHASE4.md"],
    "implementation": [
        "csia_consequence/phase4_partitions.py",
        "research/phase4/campaign4.py",
        "research/phase4/evaluate4.py",
        "research/phase4/replay_check4.py",
    ],
    "results": [
        "research/phase4/results/PHASE4_RUNS_DEVELOPMENT.json",
        "research/phase4/results/PHASE4_RUNS_LOCKED.json",
        "research/phase4/results/PHASE4_RESULTS_LOCKED.json",
        "research/phase4/results/PHASE4_MUTATION_RESULTS.json",
    ],
    "write_up": [
        "research/phase4/PHASE4_RESULTS.md",
        "research/phase4/REPRODUCE4.md",
    ],
    "tests_and_mutation": [
        "tests/test_phase4_detectors.py",
        "tests/test_phase4_pipeline.py",
        "tools/mutation/run_phase4_mutations.py",
    ],
    #: Listed so this manifest records that Phase 4 ran against the earlier
    #: phases UNMODIFIED. Phase 4 measures detector performance and is not
    #: pooled with any of them.
    "unchanged_consequence_phases": [
        "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json",
        "research/consequence/phase31/results/PHASE31_RESULTS_LOCKED.json",
        "research/consequence/phase32/results/PHASE32_RESULTS_LOCKED.json",
        "research/consequence/phase32/results/PHASE32_MUTATION_RESULTS.json",
        "research/physical_validation/FAILURE_LEDGER.yaml",
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
        "schema": "csia.phase4.manifest/1",
        "head_at_build": head,
        "groups": {g: sorted(m) for g, m in sorted(FILES.items())},
        "files": dict(sorted(files.items())),
        "frozen_core": {
            "files_checked": len(baseline["files"]),
            "mismatches": [rel for rel, want in baseline["files"].items()
                           if digest(rel) != want]},
        "pooled_with_consequence_phases": False,
        "note": ("A manifest says a document and the artifact it quotes were "
                 "committed together. It says nothing about whether either "
                 "is right."),
    }
    out = os.path.join(ROOT, "research/phase4/SHA256_MANIFEST4.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)} ({len(files)} files, "
          f"frozen-core mismatches: {document['frozen_core']['mismatches']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
