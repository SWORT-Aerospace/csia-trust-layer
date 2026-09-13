"""Hash-derived seed partitions for the independent-validation phase.

The previous phase used hand-written seed blocks (0-400, 7000-7900, ...).
Hand-written blocks are auditable but they are also *choosable*: nothing in the
artifact proves the blocks were not moved after a disappointing run. Here the
seeds are derived from a committed domain string by SHA-256, so the only degree
of freedom left is the domain string itself, which is in the manifest hash.

There are four partitions and they have different rights:

``development``
    Free. Look at anything, change anything, run it as often as you like.

``calibration``
    For fixing constants that the design needs (lag estimates, thresholds that
    are part of a *method*, not part of a *result*). Frozen before validation.

``validation``
    One full-scale rehearsal of the frozen runner. Outcomes may be inspected
    to confirm the instrument works. Outcomes may NOT be used to change the
    method; if they are, the phase restarts with a new domain string.

``final``
    Sealed. :func:`seeds` refuses it without an explicit, greppable override,
    exactly as the previous phase's sealed partition did.

Nothing here promotes anything. These are simulator seeds.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, Tuple

#: Domain separation string. Changing a single character changes every seed
#: and the manifest hash, which is the point: a phase cannot quietly reroll.
DOMAIN = "csia/independent_validation/rcec/2026-09-13"

#: How many seeds each partition gets.
SIZES: Dict[str, int] = {
    "development": 24,
    "calibration": 12,
    "validation": 24,
    "final": 40,
}

#: Partitions that :func:`seeds` refuses to hand out without an override.
SEALED: Tuple[str, ...] = ("final",)

_MASK = (1 << 31) - 1


def _derive(phase: str, index: int) -> int:
    """One seed. SHA-256 of the domain, phase and index, folded to 31 bits."""
    digest = hashlib.sha256(f"{DOMAIN}|{phase}|{index}".encode()).digest()
    return int.from_bytes(digest[:4], "big") & _MASK


def _build() -> Dict[str, Tuple[int, ...]]:
    out: Dict[str, Tuple[int, ...]] = {}
    for phase, size in SIZES.items():
        drawn: list = []
        index = 0
        # Rejection loop: a collision inside or across partitions would break
        # the disjointness that the whole design rests on, so keep drawing.
        while len(drawn) < size:
            candidate = _derive(phase, index)
            index += 1
            if candidate in drawn:
                continue
            if any(candidate in existing for existing in out.values()):
                continue
            drawn.append(candidate)
        out[phase] = tuple(drawn)
    return out


PARTITIONS: Dict[str, Tuple[int, ...]] = _build()


def assert_disjoint() -> None:
    """Raise if any seed appears in two partitions. Runs at import."""
    seen: Dict[int, str] = {}
    for phase, values in PARTITIONS.items():
        for value in values:
            if value in seen:
                raise AssertionError(
                    f"seed {value} is in both {seen[value]} and {phase}")
            seen[value] = phase


assert_disjoint()


def manifest() -> dict:
    """The committed description of this partition scheme."""
    return {
        "domain": DOMAIN,
        "sizes": dict(SIZES),
        "sealed": list(SEALED),
        "partitions": {k: list(v) for k, v in PARTITIONS.items()},
        "derivation": "int(sha256(f'{DOMAIN}|{phase}|{index}')[:4]) & 2**31-1,"
                      " rejecting collisions",
    }


def manifest_hash() -> str:
    """SHA-256 over the canonical manifest. Quote this, not the seed lists."""
    return hashlib.sha256(
        json.dumps(manifest(), sort_keys=True).encode()).hexdigest()


def seeds(phase: str, *, i_am_opening_the_sealed_partition: bool = False
          ) -> Tuple[int, ...]:
    """Seeds for ``phase``.

    A sealed partition needs the keyword argument spelled out in full at the
    call site. That is deliberate: opening the seal should be one grep away.
    """
    if phase not in PARTITIONS:
        raise KeyError(f"unknown partition {phase!r}; "
                       f"have {sorted(PARTITIONS)}")
    if phase in SEALED and not i_am_opening_the_sealed_partition:
        raise PermissionError(
            f"partition {phase!r} is sealed. Opening it is a preregistered "
            "one-time event, not a default. Pass "
            "i_am_opening_the_sealed_partition=True at the call site.")
    return PARTITIONS[phase]
