"""Mission-product assurance: what the data you collected may be used for.

THE IDEA THAT MAKES THIS LAYER WORTH HAVING
---------------------------------------------
A product is not supported-or-not. It has QUALITY PROPERTIES, and they are
qualified INDEPENDENTLY:

    bridge_07_rgb
        image                  VALID
        relative_geometry      SUPPORTED
        absolute_geolocation   NOT_SUPPORTED
        permitted_use          visual_damage_assessment
        prohibited_use         survey_grade_absolute_measurement

That imagery is still useful. An inspector can look at it and see a crack.
What they may not do is measure where the crack is to survey grade, because
the evidence supporting absolute geolocation is gone.

A layer that reported one boolean would have thrown the imagery away with the
geolocation. Losing GNSS support does not make a photograph stop being a
photograph, and the single most valuable thing this layer does is refuse to
pretend otherwise.

THE FOUR STATES
---------------
    PRODUCT_SUPPORTED       every declared property is supported
    PRODUCT_DEGRADED        at least one property supported, at least one not
    PRODUCT_NOT_SUPPORTED   no property is supported
    PRODUCT_NOT_EVALUABLE   the contract or its inputs cannot be read

PERMITTED AND PROHIBITED USE ARE BOTH EXPLICIT
------------------------------------------------
Not "permitted use, and everything else is implicitly fine." A prohibited-use
list that must be written down is a list somebody has to think about, and the
thinking is the deliverable. A product whose contract declares a use that
depends on an unsupported property gets that use moved into `prohibited_use`
automatically -- and the automatic move is the mechanism, not a reminder.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping

from .capability import (CapabilityReport, DEGRADED_SUPPORTED, EvidenceStatus,
                         NOT_SUPPORTED, SUPPORTED, UNKNOWN)

PRODUCT_SUPPORTED = "PRODUCT_SUPPORTED"
PRODUCT_DEGRADED = "PRODUCT_DEGRADED"
PRODUCT_NOT_SUPPORTED = "PRODUCT_NOT_SUPPORTED"
PRODUCT_NOT_EVALUABLE = "PRODUCT_NOT_EVALUABLE"

PRODUCT_STATES = (PRODUCT_SUPPORTED, PRODUCT_DEGRADED, PRODUCT_NOT_SUPPORTED,
                  PRODUCT_NOT_EVALUABLE)

#: The quality vocabulary. A property outside it is rejected rather than
#: passed through: an unrecognised quality name in a certificate is a claim
#: nobody defined.
QUALITY_PROPERTIES = (
    "imagery_quality",
    "relative_geometry",
    "absolute_geolocation",
    "thermal_alignment",
    "survey_grade",
    "visual_inspection_only",
    "temporal_consistency",
    "radiometric_calibration",
)

PROPERTY_STATES = (SUPPORTED, DEGRADED_SUPPORTED, NOT_SUPPORTED, UNKNOWN)


class ProductContractError(ValueError):
    """A product contract that cannot be read as written."""


@dataclass(frozen=True)
class QualityRequirement:
    """One quality property and exactly what it rests on.

    Splitting the requirements PER PROPERTY rather than per product is the
    whole mechanism. If `absolute_geolocation` and `imagery_quality` shared
    one requirement list, losing GNSS would take the imagery with it.
    """
    property_name: str
    requires_all: tuple = ()
    requires_capabilities: tuple = ()
    requires_one_of: tuple = ()
    permits: tuple = ()
    prohibits_without: tuple = ()

    def validate(self) -> None:
        if self.property_name not in QUALITY_PROPERTIES:
            raise ProductContractError(
                f"{self.property_name!r} is not a declared quality property. "
                f"Known: {list(QUALITY_PROPERTIES)}. An unrecognised quality "
                f"name in a certificate is a claim nobody defined.")


@dataclass(frozen=True)
class MissionProductContract:
    product_id: str
    product_type: str
    qualities: tuple = ()
    requires_all: tuple = ()
    requires_capabilities: tuple = ()
    requires_one_of: tuple = ()
    description: str = ""

    def validate(self) -> None:
        if not self.product_id or not self.product_type:
            raise ProductContractError(
                "a product contract needs a product_id and a product_type")
        if not self.qualities:
            raise ProductContractError(
                f"{self.product_id}: no quality properties declared. A "
                f"product with one undifferentiated state is exactly what "
                f"this layer exists not to produce.")
        seen = set()
        for q in self.qualities:
            q.validate()
            if q.property_name in seen:
                raise ProductContractError(
                    f"{self.product_id}: {q.property_name} declared twice")
            seen.add(q.property_name)

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_type": self.product_type,
            "requires_all": list(self.requires_all),
            "requires_capabilities": list(self.requires_capabilities),
            "requires_one_of": [list(g) for g in self.requires_one_of],
            "qualities": [
                {"property_name": q.property_name,
                 "requires_all": list(q.requires_all),
                 "requires_capabilities": list(q.requires_capabilities),
                 "requires_one_of": [list(g) for g in q.requires_one_of],
                 "permits": list(q.permits),
                 "prohibits_without": list(q.prohibits_without)}
                for q in self.qualities],
            "description": self.description,
        }


@dataclass(frozen=True)
class ProductAssuranceResult:
    product_id: str
    state: str
    supported_properties: tuple
    unsupported_properties: tuple
    unknown_properties: tuple
    permitted_uses: tuple
    prohibited_uses: tuple
    missing_dependencies: tuple
    expired_dependencies: tuple
    property_states: Mapping[str, str]
    property_reasons: Mapping[str, tuple]
    configuration_hash: str = ""
    evidence_hash: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("supported_properties", "unsupported_properties",
                  "unknown_properties", "permitted_uses", "prohibited_uses",
                  "missing_dependencies", "expired_dependencies"):
            d[k] = list(d[k])
        d["property_states"] = dict(d["property_states"])
        d["property_reasons"] = {k: list(v)
                                 for k, v in d["property_reasons"].items()}
        return d


# ---------------------------------------------------------------------------


def _resolve(requires_all, requires_one_of, requires_capabilities,
             evidence: Mapping[str, EvidenceStatus],
             capabilities: Mapping[str, CapabilityReport],
             now: float):
    """The shared dependency resolution, returning (state, reasons, missing,
    expired)."""
    reasons: list = []
    missing: list = []
    expired: list = []
    states: list = []

    for eid in requires_all:
        item = evidence.get(eid)
        if item is None:
            missing.append(eid)
            reasons.append(f"EVIDENCE_ABSENT:{eid}")
            states.append(UNKNOWN)
            continue
        if item.expired_at(now):
            expired.append(eid)
            reasons.append(f"EVIDENCE_EXPIRED:{eid}")
            states.append(NOT_SUPPORTED)
            continue
        st = item.state_at(now)
        if st == UNKNOWN:
            reasons.append(f"EVIDENCE_UNKNOWN:{eid}")
        elif st == NOT_SUPPORTED:
            missing.append(eid)
            reasons.append(f"EVIDENCE_NOT_SUPPORTED:{eid}")
        states.append(st)

    for group in requires_one_of:
        options = list(group) if isinstance(group, (list, tuple)) else [group]
        best = NOT_SUPPORTED
        for eid in options:
            item = evidence.get(eid)
            if item is None:
                continue
            st = item.state_at(now)
            if st == SUPPORTED:
                best = SUPPORTED
                break
            if st == UNKNOWN and best == NOT_SUPPORTED:
                best = UNKNOWN
        if best != SUPPORTED:
            reasons.append(f"NO_ALTERNATIVE:{'|'.join(options)}")
            missing.extend(o for o in options if o not in missing)
        states.append(best)

    for cid in requires_capabilities:
        rep = capabilities.get(cid)
        if rep is None:
            reasons.append(f"CAPABILITY_UNKNOWN:{cid}")
            states.append(UNKNOWN)
            continue
        if rep.state in (SUPPORTED, DEGRADED_SUPPORTED):
            states.append(rep.state)
        elif rep.state == UNKNOWN:
            reasons.append(f"CAPABILITY_UNKNOWN:{cid}")
            states.append(UNKNOWN)
        else:
            reasons.append(f"CAPABILITY_NOT_SUPPORTED:{cid}")
            missing.append(cid)
            states.append(NOT_SUPPORTED)

    if not states:
        return SUPPORTED, reasons, missing, expired

    # Worst wins, and UNKNOWN is never rounded up to SUPPORTED.
    if NOT_SUPPORTED in states:
        state = NOT_SUPPORTED
    elif UNKNOWN in states:
        state = UNKNOWN
    elif DEGRADED_SUPPORTED in states:
        state = DEGRADED_SUPPORTED
    else:
        state = SUPPORTED
    return state, reasons, missing, expired


def evaluate_product(contract: MissionProductContract,
                     evidence: Mapping[str, EvidenceStatus],
                     capabilities: Mapping[str, CapabilityReport],
                     now: float,
                     configuration_hash: str = "",
                     evidence_hash: str = "") -> ProductAssuranceResult:
    try:
        contract.validate()
    except ProductContractError as exc:
        return ProductAssuranceResult(
            product_id=contract.product_id, state=PRODUCT_NOT_EVALUABLE,
            supported_properties=(), unsupported_properties=(),
            unknown_properties=(), permitted_uses=(), prohibited_uses=(),
            missing_dependencies=(), expired_dependencies=(),
            property_states={}, property_reasons={},
            configuration_hash=configuration_hash,
            evidence_hash=evidence_hash, detail=str(exc))

    # The product-level gate. If the product's own base dependencies are not
    # met, no property can be supported -- there is no data to qualify.
    base_state, base_reasons, missing, expired = _resolve(
        contract.requires_all, contract.requires_one_of,
        contract.requires_capabilities, evidence, capabilities, now)

    prop_states: dict = {}
    prop_reasons: dict = {}
    permitted: list = []
    prohibited: list = []

    for q in contract.qualities:
        if base_state == NOT_SUPPORTED:
            prop_states[q.property_name] = NOT_SUPPORTED
            prop_reasons[q.property_name] = tuple(
                ["PRODUCT_BASE_DEPENDENCY_NOT_MET"] + base_reasons)
        elif base_state == UNKNOWN:
            prop_states[q.property_name] = UNKNOWN
            prop_reasons[q.property_name] = tuple(
                ["PRODUCT_BASE_DEPENDENCY_UNKNOWN"] + base_reasons)
        else:
            st, reasons, miss, exp = _resolve(
                q.requires_all, q.requires_one_of, q.requires_capabilities,
                evidence, capabilities, now)
            prop_states[q.property_name] = st
            prop_reasons[q.property_name] = tuple(reasons or ["MET"])
            missing.extend(m for m in miss if m not in missing)
            expired.extend(e for e in exp if e not in expired)

        if prop_states[q.property_name] in (SUPPORTED, DEGRADED_SUPPORTED):
            permitted.extend(q.permits)
        else:
            # THE AUTOMATIC MOVE. A use that depends on a property which is
            # not supported becomes PROHIBITED, without anybody remembering
            # to move it. This is the mechanism that makes the layer worth
            # having rather than a place to write intentions.
            prohibited.extend(q.prohibits_without)

    supported = tuple(sorted(k for k, v in prop_states.items()
                             if v in (SUPPORTED, DEGRADED_SUPPORTED)))
    unknown = tuple(sorted(k for k, v in prop_states.items() if v == UNKNOWN))
    unsupported = tuple(sorted(k for k, v in prop_states.items()
                               if v == NOT_SUPPORTED))

    if supported and not unsupported and not unknown:
        state = PRODUCT_SUPPORTED
    elif supported:
        state = PRODUCT_DEGRADED
    elif unknown and not unsupported:
        # NOT the same as NOT_SUPPORTED, and not rounded to it. "We cannot
        # tell" is a distinct answer from "we can tell it is unusable".
        state = PRODUCT_NOT_EVALUABLE
    else:
        state = PRODUCT_NOT_SUPPORTED

    # A use may not be both permitted and prohibited. Prohibition wins, and
    # the conflict is recorded rather than resolved silently.
    permitted_set = [p for p in dict.fromkeys(permitted)
                     if p not in set(prohibited)]

    return ProductAssuranceResult(
        product_id=contract.product_id,
        state=state,
        supported_properties=supported,
        unsupported_properties=unsupported,
        unknown_properties=unknown,
        permitted_uses=tuple(permitted_set),
        prohibited_uses=tuple(dict.fromkeys(prohibited)),
        missing_dependencies=tuple(sorted(set(missing))),
        expired_dependencies=tuple(sorted(set(expired))),
        property_states=dict(sorted(prop_states.items())),
        property_reasons=dict(sorted(prop_reasons.items())),
        configuration_hash=configuration_hash,
        evidence_hash=evidence_hash,
    )


def evaluate_products(contracts: Iterable[MissionProductContract],
                      evidence: Mapping[str, EvidenceStatus],
                      capabilities: Mapping[str, CapabilityReport],
                      now: float,
                      configuration_hash: str = "",
                      evidence_hash: str = "") -> dict:
    return {c.product_id: evaluate_product(c, evidence, capabilities, now,
                                           configuration_hash, evidence_hash)
            for c in contracts}


# ---------------------------------------------------------------------------


PRODUCT_CERT_STATUS = "EXPERIMENTAL_MISSION_PRODUCT_CERTIFICATE"


@dataclass(frozen=True)
class MissionProductCertificate:
    status: str
    product_id: str
    product_type: str
    source_data_hashes: tuple
    payload_module_id: str
    calibration_id: str
    vehicle_configuration_hash: str
    position_support: str
    attitude_support: str
    timing_support: str
    compute_support: str
    quality_properties: Mapping[str, str]
    permitted_use: tuple
    prohibited_use: tuple
    processing_software: Mapping[str, str]
    issue_time: float
    evidence_manifest_hash: str
    semantics_version: str
    certificate_hash: str = field(default="", compare=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("source_data_hashes", "permitted_use", "prohibited_use"):
            d[k] = list(d[k])
        d["quality_properties"] = dict(d["quality_properties"])
        d["processing_software"] = dict(d["processing_software"])
        return d


def build_product_certificate(result: ProductAssuranceResult,
                              contract: MissionProductContract,
                              source_data_hashes: Iterable[str],
                              payload_module_id: str,
                              calibration_id: str,
                              vehicle_configuration_hash: str,
                              capabilities: Mapping[str, CapabilityReport],
                              processing_software: Mapping[str, str],
                              issue_time: float,
                              evidence_manifest_hash: str,
                              compute_support: str = UNKNOWN
                              ) -> MissionProductCertificate:
    """A certificate that reports the SUPPORTS, not a single verdict.

    `position_support`, `attitude_support`, `timing_support` and
    `compute_support` are separate fields on purpose. A consumer deciding
    whether it may take a measurement from this imagery reads
    `position_support`; one deciding whether the image is worth looking at
    does not. Collapsing them into a product-level grade would force both
    consumers to the stricter answer.
    """
    from .provenance import content_hash

    def cap(name: str) -> str:
        rep = capabilities.get(name)
        return rep.state if rep else UNKNOWN

    cert_body = {
        "status": PRODUCT_CERT_STATUS,
        "product_id": result.product_id,
        "product_type": contract.product_type,
        "source_data_hashes": tuple(source_data_hashes),
        "payload_module_id": payload_module_id,
        "calibration_id": calibration_id,
        "vehicle_configuration_hash": vehicle_configuration_hash,
        "position_support": cap("absolute_navigation"),
        "attitude_support": cap("attitude_hold"),
        "timing_support": cap("timing"),
        "compute_support": compute_support,
        "quality_properties": dict(result.property_states),
        "permitted_use": tuple(result.permitted_uses),
        "prohibited_use": tuple(result.prohibited_uses),
        "processing_software": dict(processing_software),
        "issue_time": issue_time,
        "evidence_manifest_hash": evidence_manifest_hash,
        "semantics_version": "csia.mission.semantics/1",
    }
    hashable = {k: (list(v) if isinstance(v, tuple) else v)
                for k, v in cert_body.items()}
    return MissionProductCertificate(**cert_body,
                                     certificate_hash=content_hash(hashable))


def certificate_still_valid(cert: MissionProductCertificate,
                            vehicle_configuration_hash: str,
                            evidence_manifest_hash: str) -> tuple:
    """(valid, reason). A configuration change INVALIDATES a certificate.

    Not "probably still fine". The certificate describes a product produced
    by a specific aircraft in a specific configuration from a specific
    evidence set. Change any of those and it is describing something else.
    """
    if cert.vehicle_configuration_hash != vehicle_configuration_hash:
        return False, "VEHICLE_CONFIGURATION_CHANGED"
    if cert.evidence_manifest_hash != evidence_manifest_hash:
        return False, "EVIDENCE_MANIFEST_CHANGED"
    return True, "CONFIGURATION_UNCHANGED"
