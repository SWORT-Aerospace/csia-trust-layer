"""Immutable seed partitions, and the hash that makes them immutable.

WHY THIS IS A MODULE AND NOT A CONSTANT IN THE CAMPAIGN
--------------------------------------------------------
A seed partition that lives next to the code that uses it can be widened by
the same edit that reads it. Putting the partitions here, hashing the
manifest, and asserting the hash in `tests/test_rcec_repair.py` means a
partition cannot move without a visible diff and a failing test.

THE RULE
--------
    A SEED BELONGS TO EXACTLY ONE PARTITION, FOREVER.

`assert_disjoint()` is called at import time. If any seed appears in two
partitions the package refuses to load, because a debugging run that touched
a locked seed has contaminated the locked set and no later care recovers it.

THE ORIGINAL PARTITIONS ARE NOT REPLACED
-----------------------------------------
`ORIGINAL_*` are the partitions the first preregistration fixed and they stay
exactly as they were. The amendment adds new partitions alongside them; it
does not redefine the old ones, because the MX-039 and MX-040 results were
measured on those seeds and rewriting them would invalidate artifacts that
are already committed.

WHY THE AMENDED LOCKED SET EXISTS AT ALL
------------------------------------------
The original locked set was opened. Its results are published in
`results/RCEC_CAMPAIGN.json` and its numbers are in `RESULTS.md`. Once a
locked set has been looked at it can never again answer a question that was
formed after looking, and the repair described in
`PREREGISTRATION_AMENDMENT_1.md` was formed after looking. A new locked set
is the only honest way to evaluate the repaired experiment.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Tuple

SCHEMA = "csia.active_evidence.partitions/1"

# --- the original preregistration, unchanged --------------------------------
ORIGINAL_DEVELOPMENT: Tuple[int, ...] = (0, 100, 200, 300, 400)
ORIGINAL_CALIBRATION: Tuple[int, ...] = (999,)
ORIGINAL_LOCKED: Tuple[int, ...] = (7000, 7100, 7200, 7300, 7400,
                                    7500, 7600, 7700, 7800, 7900)

# --- amendment 1, added 2026-09-13 ------------------------------------------
#: Repair work only. Reconstructing the pilot, feasibility search, optimizer
#: comparison, binding-constraint tables, lag sweeps, spectral-bound checks.
DIAGNOSTIC: Tuple[int, ...] = tuple(11000 + 100 * i for i in range(8))

#: Fitting anything that must be fitted: the lag model, any threshold the
#: amendment permits to move.
AMENDED_CALIBRATION: Tuple[int, ...] = tuple(12000 + 100 * i for i in range(6))

#: Choosing between repaired variants. Read as often as needed.
AMENDED_VALIDATION: Tuple[int, ...] = tuple(13000 + 100 * i for i in range(10))

#: OPENED ONCE, AFTER EVERY CHOICE IS FROZEN. Not read during repair.
AMENDED_LOCKED: Tuple[int, ...] = tuple(14000 + 100 * i for i in range(20))

PARTITIONS: Dict[str, Tuple[int, ...]] = {
    "original_development": ORIGINAL_DEVELOPMENT,
    "original_calibration": ORIGINAL_CALIBRATION,
    "original_locked": ORIGINAL_LOCKED,
    "diagnostic": DIAGNOSTIC,
    "amended_calibration": AMENDED_CALIBRATION,
    "amended_validation": AMENDED_VALIDATION,
    "amended_locked": AMENDED_LOCKED,
}

#: Partitions that must never be read while the experiment is being repaired.
SEALED = ("amended_locked",)


def assert_disjoint() -> None:
    """Every seed in exactly one partition. Checked at import."""
    seen: Dict[int, str] = {}
    for name, seeds in PARTITIONS.items():
        for s in seeds:
            if s in seen:
                raise RuntimeError(
                    f"seed {s} appears in both {seen[s]!r} and {name!r}. A "
                    f"seed in two partitions means a debugging run has "
                    f"touched an evaluation set, and no later care recovers "
                    f"it")
            seen[s] = name


def manifest() -> dict:
    return {"schema": SCHEMA,
            "partitions": {k: list(v) for k, v in sorted(PARTITIONS.items())},
            "sealed": list(SEALED),
            "rule": ("a seed belongs to exactly one partition, forever; "
                     "assert_disjoint() runs at import and refuses to load "
                     "the package otherwise")}


def manifest_hash() -> str:
    """SHA-256 of the canonical manifest. Pinned by a test."""
    payload = json.dumps(manifest(), sort_keys=True,
                         separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def seeds(name: str) -> Tuple[int, ...]:
    """Read a partition. Refuses to hand out a sealed one.

    `allow_sealed` does not exist. A caller that needs the locked set at the
    end of the repair imports `AMENDED_LOCKED` directly, which is one
    greppable line in one file rather than a flag that can be passed by
    accident.
    """
    if name in SEALED:
        raise PermissionError(
            f"partition {name!r} is sealed. It is opened once, after every "
            f"choice is frozen, by importing it directly -- not through a "
            f"function that could be called during repair")
    if name not in PARTITIONS:
        raise KeyError(f"no partition {name!r}; have {sorted(PARTITIONS)}")
    return PARTITIONS[name]


assert_disjoint()
