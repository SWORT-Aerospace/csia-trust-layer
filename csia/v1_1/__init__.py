"""CSIA v1.1 runtime layer — the architecture selected by Phase 3B.

Phase 3B chose `E: TRUST_FLAT_PLUS_SEQUENTIAL`. Phase 4 turns that choice
into a stable product interface: a versioned trust mode, a deterministic
function-eligibility policy, a reproducible assurance ledger and a versioned
read-only output API.

WHY THIS PACKAGE EXISTS AT ALL, AND WHY IT IS NOT `csia/trust_engine`
---------------------------------------------------------------------
`csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`,
`csia/runtime/failsafe.py`, `csia/scenarios.py` and `csia/profiles.py` are
FROZEN. The freeze is enforced twice — by a git diff against
`csia-v1.0-research-final` and by recorded SHA-256 hashes in
`docs/v1/FROZEN_BASELINE.json` — and the guard says in as many words that it
is not a test to update.

Phase 4's brief requires two things at once: make FLAT the v1.1 default, and
keep the frozen v1 baseline reproducible. Editing the frozen engine would
satisfy the first by breaking the second. So the trust mode lives here, one
level above the freeze, and LEGACY mode is not a re-implementation of the old
behaviour — it is literally the frozen code path, unmodified.

Nothing in this package changes a threshold, weight, gate, relation or
likelihood of the v1 core. It selects, composes and reports.
"""

from .trust_mode import (DEFAULT_TRUST_MODE, FlatTrustCore,  # noqa: F401
                         TrustMode, make_core, make_engine, trust_mode_of)

__all__ = ["TrustMode", "DEFAULT_TRUST_MODE", "FlatTrustCore",
           "make_core", "make_engine", "trust_mode_of"]
