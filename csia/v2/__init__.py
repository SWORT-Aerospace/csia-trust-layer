"""CSIA v2 — cross-system assurance architecture.

The product abstraction moves from SENSOR ASSURANCE to SYSTEM FUNCTION
ASSURANCE. The question becomes:

    which functions of this system remain justified right now, on what
    evidence, and what domain is limiting them?

**No novelty is claimed** (§39). Modularity and cross-domain monitoring are
ordinary product architecture; research novelty is a separate workstream.

WHERE v2 SITS — §19
-------------------
v2 is built **above** the v1.1 output API 1.1.0, not inside the frozen v1.1
runtime. `csia/v1_1` and the frozen v1 core are untouched by everything here;
v1.1 becomes the NAVIGATION/SENSOR domain plugin, wrapping its own published
output (`csia/v2/domains/navigation.py`) and rewriting none of its logic.

WHAT IS NOT HERE — §§18, 31
---------------------------
- No extension of the eight-hypothesis Bayesian diagnosis core. Domain
  evidence is heterogeneous by design and is not forced into a likelihood.
- No ML or LLM anywhere in the decision path. An optional AI analyst is
  documented in `engineering/v2/V2_VISION.md` and deliberately not built.
"""

from . import api  # noqa: F401
from .attribution import Attribution, CrossDomainRelation  # noqa: F401
from .domain import AssuranceDomain, DomainResult, Snapshot  # noqa: F401
from .engine import AssuranceEngine, SystemAssurance  # noqa: F401
from .evidence import (Applicability, EvidenceRecord,  # noqa: F401
                       ObservationState)
from .functions import FunctionGraph, SystemFunction  # noqa: F401
from .ledger import (V2AssuranceLedger, V2LedgerContext,  # noqa: F401
                     plugin_manifest_hash)
from .registry import DomainRegistry, PluginRejected  # noqa: F401

__all__ = [
    "AssuranceDomain", "AssuranceEngine", "Applicability", "Attribution",
    "CrossDomainRelation", "DomainRegistry", "DomainResult", "EvidenceRecord",
    "FunctionGraph", "ObservationState", "PluginRejected", "Snapshot",
    "SystemAssurance", "SystemFunction", "V2AssuranceLedger",
    "V2LedgerContext", "api", "plugin_manifest_hash",
]
