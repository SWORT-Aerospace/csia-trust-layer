"""Capability and mission-product assurance, built AROUND the frozen core.

WHERE THIS SITS, AND WHY THAT IS THE WHOLE POINT
-------------------------------------------------
    VEHICLE / PAYLOAD
        v
    CANONICAL EVIDENCE
        v
    FROZEN CSIA CORE            csia/          <- not touched by this package
        v
    INDEPENDENT SUPPORT FIREWALL csia_assurance/
        v
    CAPABILITY ASSURANCE         csia_mission.capability     <- here
        v
    MISSION PRODUCT ASSURANCE    csia_mission.product        <- here
        v
    FUTURE PLANNER (ZETH)        csia_mission.planner gates it; does not implement it

Each arrow is one-way. A capability cannot reach back and change what the
firewall said; a product cannot change a capability; a planner cannot change
either. The layering is not decoration -- it is the mechanism by which a
future mission-planning system CANNOT override evidence semantics, because
there is no code path by which it could.

WHAT THIS PACKAGE MAY NOT DO, ENFORCED BY TEST
-----------------------------------------------
    * import `csia` (the frozen scientific core)
    * recompute any score, likelihood, posterior or ranking
    * read a hypothesis ranking at all
    * promote UNKNOWN to SUPPORTED
    * treat presence of a sensor as evidence that a capability is supported

`tests/test_mission_independence.py` runs a fresh interpreter and asserts the
first of those from `sys.modules`. The rest are pinned by behaviour.

WHAT IT IS NOT
--------------
It is not Forge, not SACA, not ZETH. `forge_seed` is a small deterministic
dependency compiler and says so in its own name. `planner` is a GATE plus a
deterministic mock, and refuses to be mistaken for a planner. Nothing here has
flight authority, and nothing here commands anything.

EVERY OUTPUT IS EXPERIMENTAL
----------------------------
Certificates carry `EXPERIMENTAL_` status strings. Nothing in this package is
certified, certification-grade, or airworthy, and the vocabulary is chosen so
that a reader who sees only one record still cannot conclude otherwise.
"""

from .capability import (                                   # noqa: F401
    CAPABILITY_STATES, CapabilityContract, CapabilityReport,
    CapabilitySupportCertificate, DEGRADED_SUPPORTED, NOT_EVALUABLE,
    NOT_SUPPORTED, SUPPORTED, UNKNOWN, evaluate_capabilities,
    build_capability_certificate)
from .product import (                                      # noqa: F401
    MissionProductCertificate, MissionProductContract,
    PRODUCT_DEGRADED, PRODUCT_NOT_EVALUABLE, PRODUCT_NOT_SUPPORTED,
    PRODUCT_STATES, PRODUCT_SUPPORTED, ProductAssuranceResult,
    build_product_certificate, evaluate_products)
from .compute import ComputeEvidence, COMPUTE_UNKNOWN       # noqa: F401

__all__ = [
    "CAPABILITY_STATES", "CapabilityContract", "CapabilityReport",
    "CapabilitySupportCertificate", "SUPPORTED", "DEGRADED_SUPPORTED",
    "NOT_SUPPORTED", "NOT_EVALUABLE", "UNKNOWN", "evaluate_capabilities",
    "build_capability_certificate",
    "MissionProductContract", "ProductAssuranceResult",
    "MissionProductCertificate", "PRODUCT_STATES", "PRODUCT_SUPPORTED",
    "PRODUCT_DEGRADED", "PRODUCT_NOT_SUPPORTED", "PRODUCT_NOT_EVALUABLE",
    "evaluate_products", "build_product_certificate",
    "ComputeEvidence", "COMPUTE_UNKNOWN",
]

#: Bumped when SEMANTICS change, never for a refactor. Deliberately a
#: DIFFERENT version line from `csia_assurance.SEMANTICS_VERSION`: this layer
#: can change without the firewall changing, and conflating them would let a
#: capability semantics change masquerade as a firewall one.
SEMANTICS_VERSION = "csia.mission.semantics/1"

#: Every status string this package emits begins with this. A grep for it
#: finds every place a claim is made, which is the point.
EXPERIMENTAL_PREFIX = "EXPERIMENTAL_"
