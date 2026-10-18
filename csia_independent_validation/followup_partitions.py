"""Seeds for the follow-up that breaks the paired-design cancellation.

A separate module with its own domain string, not an extension of
``partitions.py``. The completed phase's manifest hash is recorded inside every
campaign artifact it produced and pinned by a test; adding seeds there would
change that hash and make committed evidence disagree with the code that made
it. A new question gets new seeds.

Nothing here reuses a seed from the completed phase, and
:func:`assert_disjoint_from_phase_one` proves it at import.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, Tuple

from . import partitions as _phase_one

#: Changing one character changes every seed and the manifest hash.
DOMAIN = "csia/independent_validation/followup/paired-design/2026-09-14"

#: Companion seeds live in their own namespace so a baseline window can never
#: collide with the fault window it is being compared against.
COMPANION_DOMAIN = DOMAIN + "/companion"

SIZES: Dict[str, int] = {
    "development": 8,
    "validation": 16,
    "final": 24,
}

SEALED: Tuple[str, ...] = ("final",)

_MASK = (1 << 31) - 1


def _derive(domain: str, phase: str, index: int) -> int:
    digest = hashlib.sha256(f"{domain}|{phase}|{index}".encode()).digest()
    return int.from_bytes(digest[:4], "big") & _MASK


def _build() -> Dict[str, Tuple[int, ...]]:
    taken = {s for values in _phase_one.PARTITIONS.values() for s in values}
    out: Dict[str, Tuple[int, ...]] = {}
    for phase, size in SIZES.items():
        drawn: list = []
        index = 0
        while len(drawn) < size:
            candidate = _derive(DOMAIN, phase, index)
            index += 1
            if candidate in drawn or candidate in taken:
                continue
            if any(candidate in existing for existing in out.values()):
                continue
            drawn.append(candidate)
        out[phase] = tuple(drawn)
    return out


PARTITIONS: Dict[str, Tuple[int, ...]] = _build()


def companion(seed: int) -> int:
    """The baseline window's seed for a given fault window's seed.

    Derived, not offset. ``seed + 1`` or ``seed ^ 0xFF`` would be a choice
    somebody could have made differently after seeing a result; a hash in a
    separate namespace is not.
    """
    return _derive(COMPANION_DOMAIN, "companion", seed)


def assert_disjoint() -> None:
    seen: Dict[int, str] = {}
    for phase, values in PARTITIONS.items():
        for value in values:
            if value in seen:
                raise AssertionError(
                    f"seed {value} is in both {seen[value]} and {phase}")
            seen[value] = phase


def assert_disjoint_from_phase_one() -> None:
    prior = {s for values in _phase_one.PARTITIONS.values() for s in values}
    ours = {s for values in PARTITIONS.values() for s in values}
    overlap = prior & ours
    if overlap:
        raise AssertionError(f"follow-up reuses phase-one seeds: {overlap}")


def assert_companions_are_not_fault_seeds() -> None:
    """A baseline must not accidentally be the very window it baselines."""
    everything = {s for values in PARTITIONS.values() for s in values}
    everything |= {s for values in _phase_one.PARTITIONS.values()
                   for s in values}
    for seed in sorted(everything):
        if companion(seed) in everything:
            raise AssertionError(
                f"companion of {seed} collides with a campaign seed")


assert_disjoint()
assert_disjoint_from_phase_one()
assert_companions_are_not_fault_seeds()


def manifest() -> dict:
    return {
        "domain": DOMAIN,
        "companion_domain": COMPANION_DOMAIN,
        "sizes": dict(SIZES),
        "sealed": list(SEALED),
        "partitions": {k: list(v) for k, v in PARTITIONS.items()},
        "derivation": ("int(sha256(f'{DOMAIN}|{phase}|{index}')[:4]) & "
                       "2**31-1, rejecting collisions with each other and "
                       "with every phase-one seed"),
    }


def manifest_hash() -> str:
    return hashlib.sha256(
        json.dumps(manifest(), sort_keys=True).encode()).hexdigest()


def seeds(phase: str, *, i_am_opening_the_sealed_partition: bool = False
          ) -> Tuple[int, ...]:
    if phase not in PARTITIONS:
        raise KeyError(f"unknown partition {phase!r}; have {sorted(PARTITIONS)}")
    if phase in SEALED and not i_am_opening_the_sealed_partition:
        raise PermissionError(
            f"partition {phase!r} is sealed. Pass "
            "i_am_opening_the_sealed_partition=True at the call site.")
    return PARTITIONS[phase]
