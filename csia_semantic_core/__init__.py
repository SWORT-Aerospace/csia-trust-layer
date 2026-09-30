"""CSIA Semantic Core 2.1.0: the post-freeze successor to the v2 reasoning
semantics.

DELIBERATELY OUTSIDE `csia/`. Frozen v2 (`csia/v2`, semantics 2.0.0) is the
historical implementation and is not edited. This package imports it and
wraps `localize()`, `attribute()`, `EvidenceIndex` and the predicate table.
Nothing in `csia/` imports this package, and **2.1.0 is not the default
runtime**. The frozen engine still produces 2.0.0 documents.

WHAT 2.1.0 CORRECTS
-------------------
Owner-approved, from the semantic correctness audit
(`research/csia_semantic_correctness/`):

| correction | fixes | changes decisions? |
|---|---|---|
| C1 relevance-gated discriminator | SC-01 | only turns UNIQUE into AMBIGUOUS |
| F2 localization-agreement gate | SC-02 | only turns UNIQUE into AMBIGUOUS |
| C2 Kleene aggregation (18 predicates) | SC-03, SC-04 | yes, where evidence could not look |
| C3 subject scope (5 predicates and one detector) | SC-05 | yes, where evidence is outside the declared scope |
| C4 error transparency | SC-06, SC-07 | no; faults are reported |
| C6 idempotence and same-key conflicts | SC-12, SC-13 | yes, only for duplicated or conflicting records |
| C5 labels, C7 trace | SC-09, SC-10, SC-11, SC-16, SC-20, SC-21 | no |

NOT HERE
--------
- correlation-aware fusion;
- multi-fault attribution;
- rail source lookup (C8);
- intake validation;
- withholding SUPPORTED on a faulted refuter;
- profile data corrections.

Any of these would need a separate decision.

The C runtime (`embedded/`) does not implement 2.1.0.
"""

from .attribution import (AttributionResult, attribute_2_1,  # noqa: F401
                          declared_alternatives)
from .core import (HISTORICAL_SEMANTICS_VERSION, SCHEMA,  # noqa: F401
                   SEMANTICS_VERSION, Corrections, SemanticCore21, TickResult,
                   reason_historical_tick, records_from_v2_0_document)
from .index import SuccessorIndex, record_id  # noqa: F401
from .localization import (COMPLETE, EVIDENCE_UNAVAILABLE,  # noqa: F401
                           INSUFFICIENT_EVIDENCE, NO_CONSISTENT_HYPOTHESIS,
                           OUTCOMES, PREDICATE_FAULT, LocalizationResult,
                           PredicateError, localize_2_1, localize_all_2_1)
from .predicates import (C2_PREDICATES, C3_PREDICATES,  # noqa: F401
                         PredicateTableError, SuccessorPredicate,
                         declared_scope, successor_predicate_table,
                         successor_symptoms, validate_table)
from .profile_check import scope_report  # noqa: F401

__all__ = [
    "SEMANTICS_VERSION", "SCHEMA", "HISTORICAL_SEMANTICS_VERSION",
    "Corrections", "SemanticCore21", "TickResult", "reason_historical_tick",
    "records_from_v2_0_document", "SuccessorIndex", "record_id",
    "LocalizationResult", "PredicateError", "localize_2_1",
    "localize_all_2_1", "OUTCOMES", "NO_CONSISTENT_HYPOTHESIS",
    "INSUFFICIENT_EVIDENCE", "COMPLETE", "EVIDENCE_UNAVAILABLE",
    "PREDICATE_FAULT", "AttributionResult", "attribute_2_1",
    "declared_alternatives", "SuccessorPredicate",
    "successor_predicate_table", "successor_symptoms", "validate_table",
    "PredicateTableError", "declared_scope", "C2_PREDICATES",
    "C3_PREDICATES", "scope_report",
]
