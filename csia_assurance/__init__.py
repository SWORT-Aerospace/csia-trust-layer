"""CSIA assurance firewall -- an independent qualification layer.

DELIBERATELY OUTSIDE `csia/`. This package is NOT part of the frozen
scientific core and must not become part of it without the review gate in
`docs/ASSURANCE_REFERENCE_SEMANTICS.md` section 9. Its top-level position is
the reminder: a reader who sees `csia_assurance` cannot mistake it for
`csia`.

WHAT IT DOES
    It answers ONE question about a decision the frozen core has already made:

        does the evidence actually held support the attribution asserted?

    It does NOT recompute the score, does not rank, does not diagnose, and
    cannot change what the core said. It qualifies.

WHAT IT IMPORTS
    The standard library, and the clean-room structural reference. Nothing
    from `csia`. `tests/test_assurance_independence.py` runs a fresh
    interpreter and asserts that.
"""

from .firewall import (AssuranceVerdict, qualify,      # noqa: F401
                       SUPPORTED_UNIQUE, AMBIGUOUS, NON_IDENTIFIABLE,
                       NOT_EVALUABLE, UNKNOWN, FAIL_CLOSED_REASONS)
from .witness import (DiagnosticSupportWitness,        # noqa: F401
                      SupportCertificate, build_certificate)

__all__ = [
    "AssuranceVerdict", "qualify",
    "SUPPORTED_UNIQUE", "AMBIGUOUS", "NON_IDENTIFIABLE", "NOT_EVALUABLE",
    "UNKNOWN", "FAIL_CLOSED_REASONS",
    "DiagnosticSupportWitness", "SupportCertificate", "build_certificate",
]

#: Bumped when the SEMANTICS change, never for a refactor. A certificate
#: carrying a different version than the evaluator is stale by definition.
SEMANTICS_VERSION = "csia.assurance.semantics/1"
