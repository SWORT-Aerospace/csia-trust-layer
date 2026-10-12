"""Phase 5 — the hybrid-detector study. ADDITIVE EXPERIMENTAL MODULES ONLY.

WHAT THIS PACKAGE MAY AND MAY NOT DO
-------------------------------------
Every module here is an **experimental adapter**. None of it is production
code, none of it is imported by the frozen core, and none of it may be
presented as a production-core result.

**The frozen core is not modified.** `csia/runtime/online.py`,
`csia/runtime/failsafe.py`, `csia/diagnosis/causal.py` and the other nine
files in `docs/v1/FROZEN_BASELINE.json` are read, imported and wrapped —
never edited. A test asserts the twelve digests still match.

**No Forge code.** `forge/README_FUTURE.md` states that no Forge production
code exists in this repository and none may be written, and
`tests/test_program_state.py` asserts the directory stays code-free. The
"FORGE-compatible capability output" this study emits is a typed record in a
schema Forge *could* consume; it lives here, not in `forge/`, and its
compatibility is **unverified** because there is no Forge to verify against.

**Nothing here commands anything.** No hardware, no RF, no HIL, no actuator,
no armed vehicle, no flight. The fast path emits a suspicion, the support
layer emits a typed support state, and the capability layer emits a record.
A model consumes them. A vehicle never does.

Importing this package is deliberately runtime-free: the partitions, the
detectors and the adapters are imported by name so that `import csia_hybrid`
costs nothing and pulls in no simulator.
"""

__all__ = ["VERSION", "IS_EXPERIMENTAL", "TOUCHES_FROZEN_CORE"]

VERSION = "0.1.0"

#: Read by tests and written into every result document, so that no artifact
#: from this package can be mistaken for a production measurement.
IS_EXPERIMENTAL = True
TOUCHES_FROZEN_CORE = False
