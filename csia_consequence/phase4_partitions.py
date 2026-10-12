"""Seeds for Phase 4 — the detector-performance study.

Its own domain and its own three partitions, disjoint from every consequence
phase. Phase 4 asks a different question -- detector delay against false-alarm
rate -- and its thresholds are TUNED on `development`. A tuned threshold
evaluated on the seeds it was tuned on is not a measurement, which is why the
`validation` partition exists here and why `locked` carries the final curves.

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
from . import phase31_partitions as _phase_three_one
from . import phase32_partitions as _phase_three_two

DOMAIN = "csia/detector_performance_phase4/2026-09-20"

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
    for module in (_phase_two, _phase_three, _phase_three_one,
                   _phase_three_two):
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
                       "(including companions), Phase-2 consequence, "
                       "Phase-3, Phase-3.1 and Phase-3.2 partitions"),
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
            "only after the Phase-4 preregistration is committed.")
    return PARTITIONS[phase]
