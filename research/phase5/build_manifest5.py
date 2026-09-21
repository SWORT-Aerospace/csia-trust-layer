"""Emit the Phase-5 SHA-256 manifest. Standard library only."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FILES = {
    "preregistration": ["research/phase5/PREREGISTRATION_PHASE5.md"],
    "experimental_modules": [
        "csia_hybrid/__init__.py",
        "csia_hybrid/phase5_partitions.py",
        "csia_hybrid/fast_path.py",
        "csia_hybrid/support_view.py",
        "csia_hybrid/fl029_shadow.py",
        "csia_hybrid/multiscale.py",
        "csia_hybrid/capability.py",
        "csia_hybrid/baselines.py",
    ],
    "campaign_and_analysis": [
        "research/phase5/campaign5.py",
        "research/phase5/evaluate5.py",
    ],
    "results": [
        "research/phase5/results/PHASE5_RUNS_DEVELOPMENT.json",
        "research/phase5/results/PHASE5_RUNS_VALIDATION.json",
        "research/phase5/results/PHASE5_RUNS_LOCKED.json",
        "research/phase5/results/PHASE5_RESULTS_VALIDATION.json",
        "research/phase5/results/PHASE5_RESULTS_LOCKED.json",
        "research/phase5/results/PHASE5_MUTATION_RESULTS.json",
    ],
    "write_up": [
        "research/phase5/PHASE5_RESULTS.md",
        "research/phase5/REPRODUCE5.md",
    ],
    "tests_and_mutation": [
        "tests/test_phase5_hybrid.py",
        "tests/test_phase5_pipeline.py",
        "tools/mutation/run_phase5_mutations.py",
    ],
    #: Listed so this manifest records that Phase 5 ran against the earlier
    #: phases UNMODIFIED. Phase 5 is not pooled with any of them.
    "unchanged_earlier_phases": [
        "research/phase4/results/PHASE4_RUNS_LOCKED.json",
        "research/phase4/results/PHASE4_RESULTS_LOCKED.json",
        "research/phase4/results/PHASE4_MUTATION_RESULTS.json",
        "research/consequence/phase32/results/PHASE32_RESULTS_LOCKED.json",
        "research/consequence/phase31/results/PHASE31_RESULTS_LOCKED.json",
        "research/consequence/phase3/results/PHASE3_RESULTS_LOCKED.json",
        "research/bus_provenance/results/E2M_MUTATION_RESULTS.json",
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
    files = {}
    missing = []
    for group in FILES.values():
        for rel in group:
            if os.path.exists(os.path.join(ROOT, rel)):
                files[rel] = digest(rel)
            else:
                missing.append(rel)
    document = {
        "schema": "csia.phase5.manifest/1",
        "head_at_build": head,
        "is_experimental": True,
        "groups": {g: sorted(m) for g, m in sorted(FILES.items())},
        "files": dict(sorted(files.items())),
        "missing_at_build": sorted(missing),
        "frozen_core": {
            "files_checked": len(baseline["files"]),
            "mismatches": [
                rel for rel, want in baseline["files"].items()
                if digest(rel) != (want if isinstance(want, str)
                                   else want["sha256"])]},
        "pooled_with_earlier_phases": False,
        "note": ("A manifest says a document and the artifact it quotes were "
                 "committed together. It says nothing about whether either "
                 "is right."),
    }
    out = os.path.join(ROOT, "research/phase5/SHA256_MANIFEST5.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)} ({len(files)} files, "
          f"{len(missing)} missing, frozen-core mismatches: "
          f"{document['frozen_core']['mismatches']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
