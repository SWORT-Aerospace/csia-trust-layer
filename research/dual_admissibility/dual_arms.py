"""Six research semantics for A (operational) and D (diagnostic) admissibility.

RESEARCH-ONLY. `csia/` is not modified. The adapter policies come from the
committed invalidity-masking harness; the only new object is `DiagArm`, which
replaces `layer.diag` with a wrapper around a stock `DiagnosisCore` built from
an extended hypothesis map.

        adapter policy      status   h_acc   D gating       h_acc freshness
  S0    drop invalid          -        -        -                -
  S1    propagate invalid     -        -        -                -
  S1Da  propagate invalid    yes       -      D = A            message
  S1Db  propagate invalid     -      yes      D = A            message
  S1D   propagate invalid    yes     yes      D = A            message
  S2a   propagate invalid    yes       -      independent      message
  S2b   propagate invalid     -      yes      independent      message
  S2c   propagate invalid    yes     yes      independent      message
  S2b2  propagate invalid     -      yes      independent      valid_hacc *
  S2c2  propagate invalid    yes     yes      independent      valid_hacc *

  * POST-HOC. See the freshness note below.

THE COUPLED ARMS ARE WHAT DECIDE THE QUESTION. Each carries exactly the same
evidence terms as its split counterpart -- S1Da/S2a, S1Db/S2b, S1D/S2c -- and
differs in a single boolean. If a coupled arm lands on S1 while its split
counterpart does not, decoupling D from A is what did the work. If the two
land together, the evidence term did it and the honest label is
DETECTOR_DOMINANT.

VALUE VERSUS STATUS. No arm admits the invalid navigation value. Under every
propagating arm the position/velocity sample carries valid=False, so gvalid and
fresh close and every value-bearing relation -- altitude_baro,
velocity_gps_doppler_0/1, heading_course, phys_gps -- is gated OFF by the
frozen core itself. What S2 restores is metadata that does not depend on the
navigation solution being valid: the receiver's own no-fix report, and h_acc,
each admitted only under its own validity predicate.

NO NEW SCALES WERE CHOSEN HERE. The h_acc transform is the one frozen in
research/maer/maer_hacc_transform.py (h0 = 300 mm, kappa_h = log 2, EW alpha
0.15) and never used in a scored run. The status feature is binary in the
frozen core's own consistency domain, c in {0, 1}, which is the strongest
encoding that domain permits -- recorded as a known confound rather than
tuned. The message-freshness window reuses STALE_TIMEOUT_S['gps'] = 0.5 s.
"""

from __future__ import annotations

import bisect
import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

STATUS_FEATURE = "gnss_no_fix_status"
HACC_FEATURE = "gnss_hacc_health"
TARGET_CAUSE = "gps_fault"
A_PROBE_FEATURE = "phys_gps"      # the frozen gate that IS A for gps

ARMS = ("S0", "S1",
        "S1Da", "S1Db", "S1D",
        "S2a", "S2b", "S2c",
        "S2b2", "S2c2")

# arm -> (adapter policy, status on, hacc on, D coupled to A, hacc freshness)
#
# The coupled arms exist ONLY as controls: each carries exactly the same
# evidence terms as its split counterpart and differs in one boolean.
#
#   S1Da / S2a   status only
#   S1Db / S2b   h_acc only
#   S1D  / S2c   both
#
# hacc freshness mode:
#   "message"     ANY GPS_RAW_INT counts as making the h_acc evidence
#                 current. This is the version frozen before the patterns
#                 were run, and it is WRONG in the same way the
#                 invalidity-masking work package described: a message
#                 carrying no usable h_acc still refreshes the last usable
#                 one, so a healthy pre-onset accuracy keeps being served as
#                 a current statement about the receiver.
#   "valid_hacc"  only a message whose h_acc PASSES the frozen predicate
#                 refreshes it. This is a POST-HOC correction, found by
#                 looking at the P5 result, and it is labelled as such
#                 everywhere it appears. It is an instrument bug fix, not a
#                 tuning knob -- no constant changes -- but it was still
#                 found after seeing an outcome.
_SPEC = {
    "S0":   ("DROP",                    False, False, False, "message"),
    "S1":   ("PROPAGATE_INVALID_HOLD",  False, False, False, "message"),
    "S1Da": ("PROPAGATE_INVALID_HOLD",  True,  False, True,  "message"),
    "S1Db": ("PROPAGATE_INVALID_HOLD",  False, True,  True,  "message"),
    "S1D":  ("PROPAGATE_INVALID_HOLD",  True,  True,  True,  "message"),
    "S2a":  ("PROPAGATE_INVALID_HOLD",  True,  False, False, "message"),
    "S2b":  ("PROPAGATE_INVALID_HOLD",  False, True,  False, "message"),
    "S2c":  ("PROPAGATE_INVALID_HOLD",  True,  True,  False, "message"),
    "S2b2": ("PROPAGATE_INVALID_HOLD",  False, True,  False, "valid_hacc"),
    "S2c2": ("PROPAGATE_INVALID_HOLD",  True,  True,  False, "valid_hacc"),
}
POST_HOC_ARMS = ("S2b2", "S2c2")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", os.path.join(
    ROOT, "research", "invalidity_masking", "masking_harness.py"))
HACC = _load("_maer_hacc", os.path.join(
    ROOT, "research", "maer", "maer_hacc_transform.py"))

MSG_FRESH_S = H.GPS_STALE_TIMEOUT_S      # 0.5 s, the same constant


def policy_for(arm):
    return _SPEC[arm][0]


def arm_config(arm):
    pol, status, hacc, coupled, hfresh = _SPEC[arm]
    return {
        "arm": arm,
        "adapter_policy": pol,
        "status_evidence": status,
        "hacc_evidence": hacc,
        "d_coupled_to_a": coupled,
        "hacc_freshness_mode": hfresh,
        "post_hoc": arm in POST_HOC_ARMS,
        "status_feature": STATUS_FEATURE,
        "hacc_feature": HACC_FEATURE,
        "target_cause": TARGET_CAUSE,
        "msg_fresh_s": MSG_FRESH_S,
        "h0_mm": HACC.H0_MM,
        "kappa_h": HACC.KAPPA_H,
        "ew_alpha": HACC.EW_ALPHA,
        "hacc_validity_predicate": "maer_hacc_transform.hacc_valid",
        "status_consistency_domain": [0.0, 1.0],
    }


def arm_config_hash(arm):
    return hashlib.sha256(
        json.dumps(arm_config(arm), sort_keys=True).encode()).hexdigest()


def causes_for(arm):
    """The hypothesis map this arm's DiagnosisCore is built from."""
    from csia.diagnosis.bayes import CAUSES
    causes = {k: list(v) for k, v in CAUSES.items()}
    _, status, hacc, _, _ = _SPEC[arm]
    if status:
        causes[TARGET_CAUSE] = causes[TARGET_CAUSE] + [STATUS_FEATURE]
    if hacc:
        causes[TARGET_CAUSE] = causes[TARGET_CAUSE] + [HACC_FEATURE]
    return causes


# --------------------------------------------------------------- sidecar
class GnssStatusSidecar:
    """Receiver STATUS, kept separately from the navigation VALUE.

    `observe` sees a raw GPS_RAW_INT and nothing else -- no scenario label, no
    ground truth. It records two things:

      * whether the receiver declared a 3D fix, and when the message arrived;
      * h_acc, smoothed by the frozen MAER transform, but ONLY from messages
        whose h_acc passes that transform's own validity predicate.

    Neither depends on the position or velocity being usable, which is what
    makes them admissible while the navigation value is not.

    TIME-INDEXED, and it has to be. The core emits the tick at time tau only
    once a LATER sample arrives, so a sidecar holding just "the last thing I
    saw" answers a query for tau with state from after tau. That was a real
    bug here: the word IV and the word VV produced identical downstream
    traces, because the tick carrying the invalid fix was emitted after the
    following valid one had already overwritten the sidecar. Keeping an
    ordered log and looking up "as of tau" removes the artefact entirely.
    """

    def __init__(self, hacc_freshness="message"):
        if hacc_freshness not in ("message", "valid_hacc"):
            raise ValueError(hacc_freshness)
        self.hacc_freshness = hacc_freshness
        self._msg = []       # (t, fix_ok)          every GPS_RAW_INT
        self._hacc = []      # (t, lam)             usable h_acc only

    # -- observation ---------------------------------------------------
    def observe(self, msg, t):
        t = float(t)
        fix = msg.get("fix_type")
        self._msg.append((t, bool(fix is not None and int(fix) >= 3)))
        if HACC.hacc_valid(msg):
            # EXACTLY maer_hacc_transform.lam_stream: smooth units SQUARED,
            # and let an invalid sample contribute nothing rather than a value.
            raw = HACC.degradation_units(msg["h_acc"]) ** 2
            prev = self._hacc[-1][1] if self._hacc else None
            lam = raw if prev is None else prev + HACC.EW_ALPHA * (raw - prev)
            self._hacc.append((t, lam))
            return True
        return False

    # -- as-of lookups -------------------------------------------------
    @staticmethod
    def _as_of(log, tau):
        i = bisect.bisect_right(log, (tau, float("inf"))) - 1
        return log[i] if i >= 0 else None

    def _msg_fresh(self, tau):
        e = self._as_of(self._msg, tau)
        return e is not None and (tau - e[0]) <= MSG_FRESH_S

    def status_contribution(self, tau):
        """(consistency, gate) for the no-fix status, or None.

        The gate is message freshness, NOT sample acceptance. That is the
        whole point: the status is evidence only when a message actually
        arrived, so transport starvation produces NO status evidence rather
        than a false 'the receiver said it has no fix'.
        """
        e = self._as_of(self._msg, tau)
        if e is None or (tau - e[0]) > MSG_FRESH_S:
            return None
        return (1.0 if e[1] else 0.0), 1.0

    def _hacc_ref(self, tau):
        h = self._as_of(self._hacc, tau)
        if h is None:
            return None
        if self.hacc_freshness == "valid_hacc":
            return h if (tau - h[0]) <= MSG_FRESH_S else None
        # "message" mode: ANY message refreshes the last usable h_acc
        return h if self._msg_fresh(tau) else None

    def hacc_contribution(self, tau):
        """(consistency, gate) for receiver-reported horizontal accuracy."""
        h = self._hacc_ref(tau)
        if h is None:
            return None
        return HACC.consistency(h[1]), 1.0

    # -- introspection, for tests --------------------------------------
    @property
    def hacc_seen(self):
        return bool(self._hacc)


# --------------------------------------------------------------- arm
class DiagArm:
    """Wraps DiagnosisCore. One class, one gating parameter.

    On S0 and S1 no feature is added and the hypothesis map is the stock one,
    so the wrapper is behaviourally the stock core -- asserted by test.
    """

    def __init__(self, arm):
        from csia.diagnosis.bayes import DiagnosisCore
        if arm not in ARMS:
            raise ValueError(arm)
        self.arm = arm
        (_, self.status_on, self.hacc_on, self.d_coupled,
         hfresh) = _SPEC[arm]
        self.core = DiagnosisCore(causes=causes_for(arm))
        self.sidecar = GnssStatusSidecar(hacc_freshness=hfresh)
        self.rows = []
        self._tau = 0.0
        # Preferred over set_time: during OnlineTrustLayer.ingest and .flush
        # the layer runs _tick in a loop that the caller cannot get between,
        # and layer.next_tick IS the tau being processed. Reading it keeps the
        # sidecar's clock exact on every tick rather than only on the ones the
        # caller happens to see.
        self.time_fn = None

    def set_time(self, tau):
        self._tau = float(tau)

    def bind_clock(self, fn):
        self.time_fn = fn

    def step(self, feats):
        tau = float(self.time_fn()) if self.time_fn else self._tau
        self._tau = tau
        # A for gps, read from the FROZEN core's own gate rather than
        # re-derived: phys_gps's gate is gvalid * (tau>3) * fresh['gps'].
        a_gps = float((feats.get(A_PROBE_FEATURE) or (1.0, 0.0))[1])
        added = {}
        if self.status_on:
            c = self.sidecar.status_contribution(tau)
            if c is not None:
                added[STATUS_FEATURE] = (c[0], c[1] * (a_gps
                                                       if self.d_coupled
                                                       else 1.0))
        if self.hacc_on:
            c = self.sidecar.hacc_contribution(tau)
            if c is not None:
                added[HACC_FEATURE] = (c[0], c[1] * (a_gps
                                                     if self.d_coupled
                                                     else 1.0))
        if added:
            feats = dict(feats)
            feats.update(added)
        post = self.core.step(feats)
        self.rows.append({
            "t": tau,
            "a_gps": a_gps,
            "d_status": (added.get(STATUS_FEATURE, (None, 0.0))[1]
                         if self.status_on else None),
            "d_hacc": (added.get(HACC_FEATURE, (None, 0.0))[1]
                       if self.hacc_on else None),
            "c_status": (added.get(STATUS_FEATURE, (None, None))[0]
                         if self.status_on else None),
            "c_hacc": (added.get(HACC_FEATURE, (None, None))[0]
                       if self.hacc_on else None),
        })
        return post


def diagnosis_core_accepts_causes():
    """Does the frozen DiagnosisCore take a hypothesis map at construction?"""
    import inspect

    from csia.diagnosis.bayes import DiagnosisCore
    return "causes" in inspect.signature(DiagnosisCore.__init__).parameters
