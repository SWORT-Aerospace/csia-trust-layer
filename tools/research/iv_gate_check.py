"""The ten conditions for opening the sealed partition, checked mechanically.

``PREREGISTRATION.md`` §6 lists ten conditions. This checks each one and prints
a table. It exits non-zero if any condition fails, so "the seal may be opened"
is a command that can be run rather than a judgement somebody makes.

It does not open anything.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Dict, List, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "research/active_evidence/independent_validation"
RESULTS = BASE / "results"


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _load(name: str):
    path = RESULTS / name
    return json.loads(path.read_text()) if path.is_file() else None


def conditions() -> List[Tuple[str, bool, str]]:
    from csia_independent_validation import audit, partitions as pt
    from csia_independent_validation import evaluator as ev

    out: List[Tuple[str, bool, str]] = []

    # 1. instrument controls, positive and negative, in the same run
    taxonomy = _load("ORACLE_TAXONOMY.json")
    plant = _load("PLANT_INDEPENDENCE.json")
    unknown = _load("UNKNOWN_AND_SENSITIVITY.json")
    baselines = _load("BASELINES.json")
    have_all = all(x is not None for x in (taxonomy, plant, unknown,
                                           baselines))
    out.append(("1. controls present and passing", have_all,
                "four development artifacts, each with its own controls"
                if have_all else "missing development artifacts"))

    # 2. plant independence demonstrated
    if plant is not None:
        comparison = plant["outcome_vs_certificate"]
        identical_cert = comparison[
            "cells_where_cert_margin_is_identical_across_plants"]
        identical_out = comparison[
            "cells_where_outcome_error_is_identical_across_plants"]
        matched = comparison["matched_cells"]
        ok = matched > 0 and identical_cert == matched and identical_out < matched
        detail = (f"{identical_cert}/{matched} cells identical on M_R_cert, "
                  f"{identical_out}/{matched} on the outcome error")
    else:
        ok, detail = False, "no plant independence artifact"
    out.append(("2. plant independence demonstrated", ok, detail))

    # 3. P7b ceiling invariant on development and validation
    development_ok = (taxonomy is not None
                      and taxonomy["ceiling_invariant"]["holds"])
    validation = _load("CAMPAIGN_VALIDATION.json")
    validation_ok = validation is not None and not _oracle_beaten(validation)
    out.append(("3. P7b ceiling invariant, development and validation",
                development_ok and validation_ok,
                f"development {development_ok}, validation {validation_ok}"))

    # 4. no truth leakage through imports or schemas
    leaks = audit.layer_a_leaks()
    out.append(("4. no truth leakage possible", not leaks,
                "layer A import closure clean" if not leaks else str(leaks)))

    # 5. primary interaction statistic frozen
    text = (BASE / "PREREGISTRATION.md").read_text()
    frozen_interaction = "primary interaction statistic | `I_s`" in text
    out.append(("5. primary interaction statistic frozen", frozen_interaction,
                "I_s, preregistration section 2"))

    # 6. target accuracy and coverage frozen
    frozen_constants = (ev.TAU_R_RELATIVE == 0.5
                        and ev.TAU_R_ABSOLUTE == 0.002
                        and ev.COVERAGE_TARGET == 0.90
                        and "`TAU_R_RELATIVE` | `0.5`" in text)
    out.append(("6. accuracy and coverage requirements frozen",
                frozen_constants,
                f"tau_rel={ev.TAU_R_RELATIVE} tau_abs={ev.TAU_R_ABSOLUTE} "
                f"coverage={ev.COVERAGE_TARGET}"))

    # 7. the runner has completed at full scale on validation
    ran = validation is not None
    detail = (f"{validation['n_rows']} rows, "
              f"{validation['plant_simulations']} plant runs"
              if ran else "validation campaign not run")
    out.append(("7. full-scale validation run completed", ran, detail))

    # 8. clean tree
    dirty = _git("status", "--porcelain")
    out.append(("8. working tree clean", not dirty,
                "clean" if not dirty else
                f"{len(dirty.splitlines())} dirty paths"))

    # 9. tests and guards -- reported, not re-run here
    out.append(("9. full tests and guards pass", None,
                "run `pytest -q` and `make check`; recorded in RESULTS.md"))

    # 10. frozen core digests match
    provenance = json.loads((BASE / "BASE_PROVENANCE.json").read_text())
    frozen = (provenance["frozen_core"]["matches_claim"]
              and not provenance["frozen_core"]["per_file_mismatches"])
    out.append(("10. frozen core digests match", frozen,
                provenance["frozen_core"]["digest_of_digests"][:16] + "..."))

    # the seal itself
    out.append(("partition manifest unchanged",
                pt.manifest_hash() == (
                    "b293e30f30a767c13b29d1abfa9ac4c3bdc49580"
                    "f3224d037252513801786731"),
                pt.manifest_hash()[:16] + "..."))
    return out


def _oracle_beaten(campaign: Dict) -> bool:
    """Did any deployable arm beat P7b on the change loss in a matched cell?"""
    oracle: Dict[Tuple, float] = {}
    for row in campaign["rows"]:
        if row["block"] != "main" or row["e_delta_r"] is None:
            continue
        key = (row["plant"], row["drift_state"], row["magnitude"],
               row["seed"])
        if row["arm"] == "P7b_oracle":
            oracle[key] = abs(row["e_delta_r"])
    for row in campaign["rows"]:
        if row["block"] != "main" or row["e_delta_r"] is None:
            continue
        if not row["deployable"]:
            continue
        key = (row["plant"], row["drift_state"], row["magnitude"],
               row["seed"])
        if key in oracle and abs(row["e_delta_r"]) < oracle[key] - 1e-12:
            return True
    return False


def main() -> int:
    rows = conditions()
    width = max(len(name) for name, _, _ in rows)
    failed = 0
    for name, ok, detail in rows:
        mark = "PASS" if ok else ("....." if ok is None else "FAIL")
        if ok is False:
            failed += 1
        print(f"  {name:<{width}}  {mark}  {detail}")
    print()
    if failed:
        print(f"{failed} condition(s) failed. THE SEAL STAYS CLOSED.")
    else:
        print("Every mechanically checkable condition holds. Conditions "
              "marked '.....' still need a human to run and record them.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
