"""The reference implementations the conformance suite probes.

EVERY IMPLEMENTATION EXPOSES THE SAME FIVE METHODS. The conformance checker
calls them with constructed inputs and judges the answers. It never inspects
a class name, a docstring or a module path -- see `conformance.py` and the
`BAD_PRODUCT_08_actually_fine` control.

    qualify_product(contract, evidence, capabilities, now)      -> result
    certificate_valid(cert, vehicle_hash, evidence_hash)        -> (bool, str)
    capability_after_recovery(history, now)                     -> state
    authorize(action, capabilities, products)                   -> decision
    accepts_score_as_support(score)                             -> bool
"""

from __future__ import annotations

from ..capability import (CapabilityReport, DEGRADED_SUPPORTED,
                          EvidenceStatus, NOT_SUPPORTED, SUPPORTED, UNKNOWN)
from ..planner import AUTHORIZED, REJECTED, authorize as good_authorize
from ..product import (PRODUCT_SUPPORTED, ProductAssuranceResult,
                       certificate_still_valid, evaluate_product)


class _Base:
    """The correct behaviour. Each bad reference overrides exactly one part."""

    name = "reference"

    def qualify_product(self, contract, evidence, capabilities, now):
        return evaluate_product(contract, evidence, capabilities, now)

    def certificate_valid(self, cert, vehicle_hash, evidence_hash):
        return certificate_still_valid(cert, vehicle_hash, evidence_hash)

    def capability_after_recovery(self, observations, now):
        """observations: [(state, t)] since the evidence reappeared.

        Correct: a capability is restored only after enough consecutive
        supported observations spanning enough time.
        """
        streak, first = 0, None
        for state, t in observations:
            if state in (SUPPORTED, DEGRADED_SUPPORTED):
                streak += 1
                if first is None:
                    first = t
            else:
                streak, first = 0, None
        if streak >= 3 and first is not None and (now - first) >= 2.0:
            return SUPPORTED
        return DEGRADED_SUPPORTED if streak else NOT_SUPPORTED

    def authorize(self, action, capabilities, products=None):
        return good_authorize(action, capabilities, products).decision

    def accepts_score_as_support(self, score):
        """A score is never support. Correct answer is always False."""
        return False


GOOD_REFERENCE = _Base()
GOOD_REFERENCE.name = "good_reference"


# ---------------------------------------------------------------------------


class _Bad01(_Base):
    """The absolute map stays supported after position support disappears.

    THE REAL-WORLD SHAPE: one flat dependency graph in which the product's
    state was computed once, at capture time, and never re-derived against
    the evidence that is available NOW.
    """
    name = "BAD_PRODUCT_01_absolute_map_survives_position_loss"
    defect = "ABSOLUTE_PROPERTY_SURVIVES_POSITION_LOSS"

    def qualify_product(self, contract, evidence, capabilities, now):
        real = evaluate_product(contract, evidence, capabilities, now)
        states = dict(real.property_states)
        for prop in ("absolute_geolocation", "survey_grade"):
            if prop in states:
                states[prop] = SUPPORTED
        supported = tuple(sorted(k for k, v in states.items()
                                 if v in (SUPPORTED, DEGRADED_SUPPORTED)))
        return ProductAssuranceResult(
            product_id=real.product_id,
            state=PRODUCT_SUPPORTED,
            supported_properties=supported,
            unsupported_properties=(),
            unknown_properties=(),
            permitted_uses=real.permitted_uses + (
                "survey_grade_absolute_measurement",),
            prohibited_uses=(),
            missing_dependencies=real.missing_dependencies,
            expired_dependencies=real.expired_dependencies,
            property_states=states,
            property_reasons=real.property_reasons,
        )


class _Bad02(_Base):
    """Stale camera calibration accepted.

    THE REAL-WORLD SHAPE: the calibration record has an expiry, and the code
    reads `calibration is not None` instead of checking it.
    """
    name = "BAD_PRODUCT_02_stale_calibration_accepted"
    defect = "EXPIRED_CALIBRATION_TREATED_AS_VALID"

    def qualify_product(self, contract, evidence, capabilities, now):
        # Present-but-expired is silently refreshed. Note it does NOT touch
        # genuinely absent or unsupported evidence -- which is what makes this
        # a plausible bug rather than an obvious one.
        patched = {}
        for eid, item in evidence.items():
            if item.expired_at(now):
                patched[eid] = EvidenceStatus(
                    eid, item.supported, expires_at=None,
                    witness=item.witness, source=item.source)
            else:
                patched[eid] = item
        return evaluate_product(contract, patched, capabilities, now)


class _Bad03(_Base):
    """Compute-health failure ignored.

    THE REAL-WORLD SHAPE: the product layer has no notion of compute state at
    all, so a mapping product is supported because the camera worked, even
    though the process that would build the map missed every deadline.
    """
    name = "BAD_PRODUCT_03_compute_failure_ignored"
    defect = "COMPUTE_STATE_NOT_CONSULTED"

    def qualify_product(self, contract, evidence, capabilities, now):
        # Any capability that is NOT_SUPPORTED *because of compute* is
        # upgraded. Everything else is honoured, which is exactly how this
        # bug survives review.
        patched = {}
        for cid, rep in capabilities.items():
            if any(r.startswith("COMPUTE_") for r in rep.reason_codes):
                patched[cid] = CapabilityReport(
                    cid, SUPPORTED, ("ALL_REQUIREMENTS_MET",),
                    load_bearing_evidence=rep.load_bearing_evidence)
            else:
                patched[cid] = rep
        return evaluate_product(contract, evidence, patched, now)


class _Bad04(_Base):
    """A product certificate survives a configuration change."""
    name = "BAD_PRODUCT_04_certificate_survives_reconfiguration"
    defect = "CERTIFICATE_NOT_INVALIDATED_BY_CONFIGURATION_CHANGE"

    def certificate_valid(self, cert, vehicle_hash, evidence_hash):
        # "The data was still good, the aircraft just changed" -- which is
        # true and is not the point. The certificate describes a product from
        # a specific article in a specific configuration.
        return True, "STILL_VALID"


class _Bad05(_Base):
    """Capability restored immediately, without fresh evidence."""
    name = "BAD_PRODUCT_05_instant_restore_on_presence"
    defect = "RESTORED_ON_PRESENCE_NOT_ON_EVIDENCE"

    def capability_after_recovery(self, observations, now):
        for state, _t in observations:
            if state in (SUPPORTED, DEGRADED_SUPPORTED):
                return SUPPORTED
        return NOT_SUPPORTED


class _Bad06(_Base):
    """The planner overrides a NOT_SUPPORTED capability."""
    name = "BAD_PRODUCT_06_planner_overrides_unsupported"
    defect = "PLANNER_OVERRIDES_SUPPORT_STATE"

    def authorize(self, action, capabilities, products=None):
        decision = good_authorize(action, capabilities, products)
        if decision.decision == REJECTED:
            # "Advisory mode": proceed anyway and record the concern. This is
            # the most seductive of the seven, because it looks like
            # engineering judgement rather than a bypass.
            return AUTHORIZED
        return decision.decision


class _Bad07(_Base):
    """A high hypothesis score alone certifies a product.

    THE REAL-WORLD SHAPE: the system never separated RANKING from SUPPORT.
    This is the finding the entire CSIA programme is built on, appearing one
    layer up, which is exactly where it would reappear if the layering were
    not enforced.
    """
    name = "BAD_PRODUCT_07_score_alone_certifies"
    defect = "RANKING_ACCEPTED_AS_SUPPORT"

    def accepts_score_as_support(self, score):
        return score >= 0.9

    def qualify_product(self, contract, evidence, capabilities, now):
        real = evaluate_product(contract, evidence, capabilities, now)
        score = getattr(contract, "_score_hint", None)
        if score is not None and score >= 0.9:
            states = {k: SUPPORTED for k in real.property_states}
            return ProductAssuranceResult(
                product_id=real.product_id, state=PRODUCT_SUPPORTED,
                supported_properties=tuple(sorted(states)),
                unsupported_properties=(), unknown_properties=(),
                permitted_uses=real.permitted_uses, prohibited_uses=(),
                missing_dependencies=(), expired_dependencies=(),
                property_states=states,
                property_reasons={k: ("HIGH_SCORE",) for k in states})
        return real


class _Good08(_Base):
    """CORRECT, but named as though it were one of the bad ones.

    THE CONTROL. A conformance checker that rejects on name rather than on
    behaviour fails here, and this file exists mostly so that it does.
    """
    name = "BAD_PRODUCT_08_actually_fine"
    defect = None


BAD_PRODUCT_01_absolute_map_survives_position_loss = _Bad01()
BAD_PRODUCT_02_stale_calibration_accepted = _Bad02()
BAD_PRODUCT_03_compute_failure_ignored = _Bad03()
BAD_PRODUCT_04_certificate_survives_reconfiguration = _Bad04()
BAD_PRODUCT_05_instant_restore_on_presence = _Bad05()
BAD_PRODUCT_06_planner_overrides_unsupported = _Bad06()
BAD_PRODUCT_07_score_alone_certifies = _Bad07()
BAD_PRODUCT_08_actually_fine = _Good08()

#: (implementation, must_be_rejected)
ALL_REFERENCES = (
    (GOOD_REFERENCE, False),
    (BAD_PRODUCT_01_absolute_map_survives_position_loss, True),
    (BAD_PRODUCT_02_stale_calibration_accepted, True),
    (BAD_PRODUCT_03_compute_failure_ignored, True),
    (BAD_PRODUCT_04_certificate_survives_reconfiguration, True),
    (BAD_PRODUCT_05_instant_restore_on_presence, True),
    (BAD_PRODUCT_06_planner_overrides_unsupported, True),
    (BAD_PRODUCT_07_score_alone_certifies, True),
    (BAD_PRODUCT_08_actually_fine, False),
)

_ = UNKNOWN  # re-exported vocabulary; referenced so linters see the import
