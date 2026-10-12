"""The five MAER research arms, as a read-only wrapper around the frozen core.

WHY A WRAPPER AND NOT A FORK. The per-tick feature dict `feats` is local to
`OnlineTrustLayer._tick` and is not exposed on `TrustState`, so a sidecar
cannot reconstruct `phys_gps` -- which is `gps_fault`'s only evidence -- from
the public state. Copying `ingest` to get at it would duplicate 400 lines of
frozen logic and destroy the "one code path" guarantee.

`layer.diag` is a plain attribute holding a `DiagnosisCore`. Replacing it from
OUTSIDE the frozen package with an object exposing the same `.step(feats)`
gives exact access to the real feature dict, injects nothing into
`csia/`, and leaves production behaviour bit-identical when no arm is
attached. That is the research-only wrapper the preregistration allows.

A1 AND A1G ARE ONE IMPLEMENTATION WITH ONE PARAMETER. `gate_mode` is the only
thing that differs; every other input, constant, transform, EWMA state,
consistency conversion, feature identity, hypothesis association, scorer,
smoothing, tempering and normalization is shared code. `arm_config_hash()`
proves it: the two configs differ in exactly one field.

Preregistration: research/maer/MAER_PREREGISTRATION.md at d34c629.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location(
    "_maer_hacc", os.path.join(_HERE, "maer_hacc_transform.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

# The feature name the h_acc relation is published under.
HACC_FEATURE = "phys_gps_hacc"
TARGET_CAUSE = "gps_fault"

# Frozen CUSUM parameters (research/phase2/results/baseline_comparison.json).
CUSUM_K = 0.5
CUSUM_H = 500.0

ARMS = ("A0", "A1", "A1G", "A2", "A3")


def causes_for(arm):
    """Hypothesis map. A1/A1G/A3 add the h_acc feature to gps_fault's low-set."""
    from csia.diagnosis.bayes import CAUSES
    causes = {k: list(v) for k, v in CAUSES.items()}
    if arm in ("A1", "A1G", "A3"):
        causes[TARGET_CAUSE] = causes[TARGET_CAUSE] + [HACC_FEATURE]
    return causes


def gate_mode_for(arm):
    """THE ONLY THING THAT DIFFERS BETWEEN A1 AND A1G."""
    if arm in ("A1", "A3"):
        return "ungated"
    if arm == "A1G":
        return "gvalid"
    return "none"


def arm_config(arm):
    """Every knob of an arm, for hashing and for the manifest."""
    return {
        "arm": arm,
        "gate_mode": gate_mode_for(arm),
        "hacc_feature": HACC_FEATURE if arm in ("A1", "A1G", "A3") else None,
        "h0_mm": T.H0_MM,
        "kappa_h": T.KAPPA_H,
        "ew_alpha": T.EW_ALPHA,
        "validity_predicate": "h_acc present, != UINT32_MAX, > 0, "
                              "eph != UINT16_MAX, satellites_visible > 0",
        "cusum": {"k": CUSUM_K, "h": CUSUM_H} if arm in ("A2", "A3") else None,
        "target_cause": TARGET_CAUSE,
    }


def arm_config_hash(arm):
    return hashlib.sha256(
        json.dumps(arm_config(arm), sort_keys=True).encode()).hexdigest()


class HaccSidecar:
    """One implementation of the receiver-health relation, one gate parameter.

    `gate_mode`:
        "none"     contribute nothing (A0, A2)
        "ungated"  contribution x 1        (A1, A3)
        "gvalid"   contribution x gvalid   (A1G)
    """

    def __init__(self, gate_mode="none"):
        self.gate_mode = gate_mode
        self._ew = None            # EWMA state, held across valid samples only
        self.last = None           # (consistency, gate, valid)

    def observe(self, gps_raw_msg):
        """Fold one GPS_RAW_INT sample. Invalid samples do not update state."""
        if gps_raw_msg is None or not T.hacc_valid(gps_raw_msg):
            self.last = None
            return False
        raw = T.degradation_units(gps_raw_msg["h_acc"]) ** 2
        self._ew = raw if self._ew is None else (
            self._ew + T.EW_ALPHA * (raw - self._ew))
        self.last = T.consistency(self._ew)
        return True

    def contribution(self, gvalid):
        """(consistency, gate) or None. THE GATE IS THE ONLY ARM DIFFERENCE."""
        if self.gate_mode == "none" or self.last is None:
            return None
        gate = 1.0 if self.gate_mode == "ungated" else float(gvalid)
        return (self.last, gate)


class Cusum:
    """The frozen B4 one-sided CUSUM, read-only on a standardised residual."""

    def __init__(self, k=CUSUM_K, h=CUSUM_H):
        self.k, self.h = k, h
        self.S = 0.0
        self.alarm_t = None

    def update(self, z, t):
        self.S = max(0.0, self.S + z - self.k)
        if self.alarm_t is None and self.S > self.h:
            self.alarm_t = t
        return self.S


class ArmWrapper:
    """Replaces `layer.diag`, records the true feature dict, injects per arm.

    Read-only with respect to the frozen core: it receives the feature dict the
    core built, optionally adds ONE feature, and delegates to a real
    `DiagnosisCore` constructed with this arm's hypothesis map.
    """

    def __init__(self, arm):
        from csia.diagnosis.bayes import DiagnosisCore
        self.arm = arm
        self.core = DiagnosisCore(causes=causes_for(arm))
        self.sidecar = HaccSidecar(gate_mode_for(arm))
        self.rows = []

    def step(self, feats):
        # gvalid is exactly the gate the frozen core put on altitude_baro.
        gvalid = float((feats.get("altitude_baro") or (1.0, 0.0))[1])
        contrib = self.sidecar.contribution(gvalid)
        if contrib is not None:
            feats = dict(feats)
            feats[HACC_FEATURE] = contrib
        post = self.core.step(feats)
        self.rows.append({
            "gvalid": gvalid,
            "hacc_consistency": None if contrib is None else contrib[0],
            "hacc_gate": None if contrib is None else contrib[1],
            "hacc_contributing": bool(contrib is not None
                                      and contrib[1] > 1e-9),
            "top": max(post, key=post.get),
            "gps_fault_p": float(post.get(TARGET_CAUSE, 0.0)),
            "nominal_p": float(post.get("nominal", 0.0)),
        })
        return post
