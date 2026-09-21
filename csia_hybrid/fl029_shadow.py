"""Phase 5 — the experimental FL-029 support-map correction. SHADOW ONLY.

WHAT FL-029 IS
--------------
`csia/diagnosis/causal.py:50-59` maps each source to the indicator features
that count as evidence for it. For the two IMUs it lists:

    "imu0": ("redundant_imu", "accel_motor_current"),
    "imu1": ("redundant_imu", "accel_esc_rpm"),

and it OMITS `velocity_gps_doppler_0` and `velocity_gps_doppler_1` -- two
edges the frozen core declares, keys, and computes as live evidence on every
tick:

    declared    csia/trust_graph/graph.py:42   ("imu0", "gps", "velocity_gps_doppler", ...)
                csia/trust_graph/graph.py:44   ("imu1", "gps", "velocity_gps_doppler", ...)
    keyed       csia/runtime/online.py:207-208 _edge_meta["velocity_gps_doppler_0"] = ("imu0", "gps")
                                               _edge_meta["velocity_gps_doppler_1"] = ("imu1", "gps")
    computed    csia/runtime/online.py:527-537 E[key] = self._lam_upd(key, ...), gvalid

So the trust engine isolates on evidence the attribution model does not know
it has. The consequence measured in Phase 3.1 was that a support-aware policy
withdraws attributions that were in fact separable, producing false refusals.

WHY THIS ADDS NO SENSING AND NO COMPUTATION
--------------------------------------------
Both edges are ALREADY computed every tick by the frozen core and then
ignored by the attribution map. Correcting the map changes what is counted,
not what is measured. The evidence budget of the corrected branch is
identical to the current one, and the write-up must say so rather than
claiming an efficiency that is really a bookkeeping fix.

WHAT THIS MODULE IS NOT
------------------------
It is NOT a repair of the production core. `csia/diagnosis/causal.py` is in
`docs/v1/FROZEN_BASELINE.json` and is not edited; a test re-hashes all twelve
frozen files. This module builds a SEPARATE mapping, used only by the `B4`
branch of an experimental study, and no result derived from it may be
presented as a production-core result.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Tuple

from csia.diagnosis.causal import SOURCE_INDICATORS as _FROZEN

#: Every added indicator, with the source reference that justifies it. The
#: preregistration requires a reference per addition, so the reference lives
#: in the data structure rather than in a comment that could drift from it.
ADDITIONS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "imu0": ((
        "velocity_gps_doppler_0",
        "declared csia/trust_graph/graph.py:42 as (imu0, gps, "
        "velocity_gps_doppler); keyed csia/runtime/online.py:207; computed "
        "csia/runtime/online.py:527-537",
    ),),
    "imu1": ((
        "velocity_gps_doppler_1",
        "declared csia/trust_graph/graph.py:44 as (imu1, gps, "
        "velocity_gps_doppler); keyed csia/runtime/online.py:208; computed "
        "csia/runtime/online.py:527-537",
    ),),
}

IS_EXPERIMENTAL = True
MODIFIES_FROZEN_CORE = False


def current_map() -> Dict[str, FrozenSet[str]]:
    """The frozen map, exactly as `B3` uses it. Read, never written."""
    return {src: frozenset(feats) for src, feats in _FROZEN.items()}


def corrected_map() -> Dict[str, FrozenSet[str]]:
    """The frozen map plus the declared additions. Used only by `B4`."""
    out = {src: set(feats) for src, feats in _FROZEN.items()}
    for src, adds in ADDITIONS.items():
        if src not in out:
            raise KeyError(f"{src!r} is not a source in the frozen map")
        for feature, _reference in adds:
            out[src].add(feature)
    return {src: frozenset(feats) for src, feats in out.items()}


def added_features() -> Dict[str, Tuple[str, ...]]:
    return {src: tuple(f for f, _r in adds) for src, adds in ADDITIONS.items()}


def references() -> Dict[str, str]:
    """`feature -> source reference`, for the write-up and for tests."""
    return {feature: reference
            for adds in ADDITIONS.values()
            for feature, reference in adds}


def separating_features(mapping: Dict[str, FrozenSet[str]],
                        a: str, b: str) -> FrozenSet[str]:
    """The symmetric difference -- the only features that can separate a from b.

    A feature in BOTH low-sets, or in NEITHER, cancels exactly in the
    log-likelihood ratio between the two hypotheses. So the features that
    decide `a` against `b` are precisely `mapping[a] ^ mapping[b]`, and if
    every one of them is gated off the pair is not separable on evidence
    however confident the score looks.
    """
    return frozenset(mapping[a] ^ mapping[b])


def budget_note() -> str:
    return ("the corrected map reads two edges the frozen core already "
            "computes every tick and then discards; no new sensor, no new "
            "channel and no additional arithmetic is introduced, so the "
            "evidence budget is unchanged")
