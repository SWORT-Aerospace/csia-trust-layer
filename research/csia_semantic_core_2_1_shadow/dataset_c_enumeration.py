#!/usr/bin/env python3
"""DATASET C: the small-state enumeration and property measures, re-run.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/dataset_c_enumeration.py

Re-executes the 2.1 package's section D (the audit's enumeration of small
configurations, metamorphic perturbations and property measures, frozen v2
against 2.1) through the unchanged functions of
`research/csia_semantic_core_2_1/semantic_core_2_1_differential.py`, and
compares the result with the committed `SEMANTIC_CORE_2_1_RESULTS.json`
section D. A difference means 2.1's behaviour on the enumeration moved since
it was accepted for shadow. Writes DATASET_C_RESULTS.json only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness"),
          str(REPO / "research/csia_semantic_core_2_1")):
    if p not in sys.path:
        sys.path.insert(0, p)

import semantic_core_2_1_differential as D  # noqa: E402

OUT = HERE / "DATASET_C_RESULTS.json"
COMMITTED = REPO / "research/csia_semantic_core_2_1/SEMANTIC_CORE_2_1_RESULTS.json"


def main():
    committed = json.loads(D.P.OUT.read_text())
    audit, comparison, _runs = D.section_audit(committed)
    got = D.norm(D.section_D(audit))
    accepted = json.loads(COMMITTED.read_text())["D"]
    paths = D.diff_paths(accepted, got)
    out = {"harness": "semantic_core_2_1_shadow_dataset_c",
           "source": "semantic_core_2_1_differential.section_D, re-executed",
           "identical_to_accepted_section_D": not paths,
           "differing_paths": paths,
           "classification_counts": got.get("classification_counts"),
           "audit_probe_sections_identical_to_audit": {
               k: v["identical_to_audit"] for k, v in comparison.items()}}
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, indent=1))
    if paths:
        raise SystemExit("section D moved since 2.1 was accepted for shadow")


if __name__ == "__main__":
    main()
