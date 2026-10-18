"""Seeds for Phase 3.1 — the actionability-precondition study.

Its own domain again, and its own locked partition. Phase 3's locked result
(3/24 versus 1/24, exact McNemar p = 0.625) stands unchanged and **is not
pooled with anything here**; the amendment states that before execution.
Reusing Phase 3's seeds would make the two campaigns dependent and would
invite exactly that pooling by accident.

40 locked seeds rather than 24, because the question changed. Phase 3 asked
whether a difference existed between two conditions; Phase 3.1 has to
separate "zero conflicts" from "rare conflicts" from sampling noise, and a
zero count over 40 paired seeds bounds the rate far more usefully than a zero
over 24.

    development   scenario construction, debugging, threshold selection.
                  Look freely.
    validation    a dress rehearsal of the frozen design.
    locked        opened ONCE, after the Phase-3 design is frozen and
                  committed, and never tuned against.

`locked` raises unless the call site spells out that it is opening it, so
every opening is one grep away.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, Tuple

from csia_independent_validation import followup_partitions as _followup
from csia_independent_validation import partitions as _phase_one

from . import partitions as _phase_two
from . import phase3_partitions as _phase_three

DOMAIN = "csia/actionability_precondition_phase31/2026-09-20"

SIZES: Dict[str, int] = {
    "development": 12,
    "validation": 16,
    "locked": 40,
}

SEALED: Tuple[str, ...] = ("locked",)

_MASK = (1 << 31) - 1


def _derive(phase: str, index: int) -> int:
    digest = hashlib.sha256(f"{DOMAIN}|{phase}|{index}".encode()).digest()
    return int.from_bytes(digest[:4], "big") & _MASK


def _taken() -> set:
    out = set()
    for module in (_phase_one, _followup):
        for values in module.PARTITIONS.values():
            out |= set(values)
    out |= {_followup.companion(s) for s in set(out)}
    for module in (_phase_two, _phase_three):
        for values in module.PARTITIONS.values():
            out |= set(values)
    return out


def _build() -> Dict[str, Tuple[int, ...]]:
    taken = _taken()
    out: Dict[str, Tuple[int, ...]] = {}
    for phase, size in SIZES.items():
        drawn: list = []
        index = 0
        while len(drawn) < size:
            candidate = _derive(phase, index)
            index += 1
            if candidate in drawn or candidate in taken:
                continue
            if any(candidate in existing for existing in out.values()):
                continue
            drawn.append(candidate)
        out[phase] = tuple(drawn)
    return out


PARTITIONS: Dict[str, Tuple[int, ...]] = _build()


def assert_disjoint() -> None:
    seen: Dict[int, str] = {}
    for phase, values in PARTITIONS.items():
        for value in values:
            if value in seen:
                raise AssertionError(
                    f"seed {value} is in both {seen[value]} and {phase}")
            seen[value] = phase


def assert_disjoint_from_earlier_phases() -> None:
    ours = {s for values in PARTITIONS.values() for s in values}
    overlap = ours & _taken()
    if overlap:
        raise AssertionError(f"reuses earlier-phase seeds: {sorted(overlap)}")


assert_disjoint()
assert_disjoint_from_earlier_phases()


def manifest() -> dict:
    return {
        "domain": DOMAIN,
        "sizes": dict(SIZES),
        "sealed": list(SEALED),
        "partitions": {k: list(v) for k, v in PARTITIONS.items()},
        "derivation": ("int(sha256(f'{DOMAIN}|{phase}|{index}')[:4]) & "
                       "2**31-1, rejecting collisions with each other and "
                       "with every seed of the phase-one, follow-up "
                       "(including companions), Phase-2 consequence and "
                       "Phase-3 partitions"),
    }


def manifest_hash() -> str:
    return hashlib.sha256(
        json.dumps(manifest(), sort_keys=True).encode()).hexdigest()


def seeds(phase: str, *, i_am_opening_the_locked_partition: bool = False
          ) -> Tuple[int, ...]:
    if phase not in PARTITIONS:
        raise KeyError(f"unknown partition {phase!r}; have {sorted(PARTITIONS)}")
    if phase in SEALED and not i_am_opening_the_locked_partition:
        raise PermissionError(
            f"partition {phase!r} is locked. Pass "
            "i_am_opening_the_locked_partition=True at the call site, and "
            "only after the Phase-3.1 amendment is committed.")
    return PARTITIONS[phase]
