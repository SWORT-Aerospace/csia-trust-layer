"""CSIA 2.2 Evidence Assurance, and the CSIA Flight Assurance Analyzer.

DELIBERATELY OUTSIDE `csia/`. Nothing in `csia/` imports this package, and
it has no flight-control authority: it is an offboard analyzer for SITL,
HIL, flight test, post-flight analysis and integration debugging.

THE PRINCIPLE
-------------
    DETECTORS PRODUCE EVIDENCE.  CSIA QUALIFIES AND REASONS ABOUT EVIDENCE.

Mature algorithms are wrapped as evidence producers: the frozen CUSUM, PX4
EKF2's own status, the XSYS-001 physical witnesses and the frozen v2 domain
plugins. 2.2 decides whether each output is admissible now, keeps dependent
outputs from posing as independent ones, and hands what remains to Semantic
Core 2.1.1 (`csia_semantic_core`, `Corrections.revised()`) unchanged. The
verdicts are 2.1.1's.

| module | what it does |
|---|---|
| `envelope` | one producer output: claim, 2.1.1 record, lineage, content time, configuration epoch, producer health |
| `lineage` | the root sources an output depends on; independence groups |
| `health` | producer health, kept apart from what the producer says |
| `contract` | what CSIA needs to interpret a producer (versioned JSON in `contracts/`) |
| `admissibility` | one status per output; rejected evidence withheld as 2.1.1's R-3 withholds it |
| `dependence` | corroboration stated by lineage group, never by count |
| `profile_gate` | PV1-PV9 and pacing citations as the profile load gate |
| `analyzer` | the Flight Assurance Analyzer: hold, admit, reason, explain |
| `report` | the deterministic JSON report, the event timeline and the human report |
| `adapters/` | the producers: v2 domains, CUSUM, PX4 estimator, XSYS witnesses |

Package documentation and evidence: `research/csia_2_2_evidence_assurance/`.
"""

from .admissibility import (ADMISSIBLE, CONFIGURATION_MISMATCH,  # noqa: F401
                            CONTRACT_INVALID, DUPLICATE, PRODUCER_INVALID,
                            PROFILE_MISMATCH, REGIME_INVALID, STALE, STATUSES,
                            AnalysisContext, assess)
from .analyzer import (ANALYZER_VERSION, AssuranceResult,  # noqa: F401
                       FlightAssuranceAnalyzer)
from .contract import ContractError, ProducerContract, load_contracts  # noqa: F401
from .envelope import EvidenceEnvelope  # noqa: F401
from .health import ProducerHealth  # noqa: F401
from .lineage import Lineage, LineageError, independence_groups  # noqa: F401
from .profile_gate import GateResult, gate  # noqa: F401

__all__ = [
    "ADMISSIBLE", "CONFIGURATION_MISMATCH", "CONTRACT_INVALID", "DUPLICATE",
    "PRODUCER_INVALID", "PROFILE_MISMATCH", "REGIME_INVALID", "STALE", "STATUSES",
    "AnalysisContext", "assess", "ANALYZER_VERSION", "AssuranceResult",
    "FlightAssuranceAnalyzer", "ContractError", "ProducerContract", "load_contracts",
    "EvidenceEnvelope", "ProducerHealth", "Lineage", "LineageError",
    "independence_groups", "GateResult", "gate",
]
