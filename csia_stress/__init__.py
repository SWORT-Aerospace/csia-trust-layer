"""Stress and degraded-environment testing for the frozen CSIA core.

WHAT THIS PACKAGE MAY DO
------------------------
Compose simultaneous sensor degradations through the frozen core's PUBLIC
API -- `Fault(...)` and `run_pipeline(faults=...)` -- and measure what the
core does with them.

WHAT IT MAY NOT DO
------------------
Touch the frozen core. `csia/trust_engine`, `csia/diagnosis`,
`csia/runtime/online.py`, `csia/runtime/failsafe.py`, `csia/scenarios.py`
and `csia/profiles.py` are frozen. Nothing here modifies a threshold, a
gate, a weight, a prior or a signature. Every measurement is taken by
CALLING the core, never by adjusting it.

It also does not transmit anything. A "GNSS-denied" profile is a `dropout`
fault on a simulated sensor. There is no jammer and no spoofing
transmitter here.

THE TWO PROPERTIES THAT MAKE THE RESULTS MEAN ANYTHING
------------------------------------------------------
1. **No vacuous stimulus.** 29 of the 48 (kind, target) combinations the
   frozen core accepts are silently ignored by the sensors. Profiles are
   validated against a MEASURED applicability matrix and a profile built
   on an inert pair is refused at construction, so a stress run can never
   report clean because it stressed nothing.

2. **No invented threshold.** Recovery is read off the failsafe's own
   NORMAL state, not off a trust cutoff chosen by this package.

And one that keeps the reporting honest: a profile that never trips the
failsafe is recorded as NOT_DETECTED, which is never folded into a pass.
"""

from .applicability import (APPLIED, IGNORED, ApplicabilityMatrix,  # noqa: F401
                            VacuousFault, derive_matrix, matrix)
from .observables import (DETECTED, NOT_DETECTED, NOT_RECOVERED,  # noqa: F401
                          RECOVERED, StressRun, run_profile)
from .profiles import (FLIGHT_PROFILES, UNMODELLED,  # noqa: F401
                       StressProfile, by_id, catalog)
from .source import StressFlightSource  # noqa: F401

SEMANTICS_VERSION = "csia.stress.semantics/1"

__all__ = [
    "APPLIED", "IGNORED", "ApplicabilityMatrix", "VacuousFault",
    "derive_matrix", "matrix",
    "DETECTED", "NOT_DETECTED", "NOT_RECOVERED", "RECOVERED",
    "StressRun", "run_profile",
    "FLIGHT_PROFILES", "UNMODELLED", "StressProfile", "by_id", "catalog",
    "StressFlightSource", "SEMANTICS_VERSION",
]
