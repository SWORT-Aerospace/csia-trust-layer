"""Supervision above the frozen core: rules the core does not have.

WHAT THIS PACKAGE IS FOR
------------------------
The frozen failsafe supervises degradation well and absence badly. It
alarms when a sensor's TRUST falls, and for seven of eight sensors it says
nothing at all when the sensor stops delivering (SR-001). This package
adds the missing rule without touching the frozen file.

WHAT IT MAY NOT DO
------------------
* modify the frozen core -- `csia/runtime/failsafe.py` and the other five
  FROZEN_PATHS are read-only here, and this package only calls them;
* lower a level the frozen policy raised. The effective level is
  `max(frozen, supervisor)`, so the overlay can only ever add urgency;
* invent a severity. Every level but two is read off the severity the
  frozen config already assigns that sensor, and the two that cannot be
  are labelled `UNANCHORED_THIS_IS_A_CHOICE`.

IT IS STILL ADVISORY. CSIA has no command authority; this changes what the
layer would RAISE, not what any vehicle would do.
"""

from .capability_bridge import (DERIVED, DIRECT,  # noqa: F401
                                REQUIRES_ALL_LOST, SENSOR_EVIDENCE, SOURCE,
                                UNMAPPED)
from .capability_bridge import apply as apply_evidence_overrides  # noqa: F401
from .capability_bridge import evidence_overrides  # noqa: F401
from .capability_bridge import report as capability_bridge_report  # noqa: F401
from .dataloss import (ALREADY_COVERED, ANCHORED,  # noqa: F401
                       BOTH_IMUS_LOST, DERIVED_FROM, UNANCHORED,
                       UNSUPERVISED_BY_THE_FROZEN_POLICY,
                       DataLossCondition, DataLossSupervisor,
                       SupervisedFailsafe)

SEMANTICS_VERSION = "csia.supervision.semantics/1"

__all__ = [
    "ALREADY_COVERED", "ANCHORED", "BOTH_IMUS_LOST", "DERIVED_FROM",
    "UNANCHORED", "UNSUPERVISED_BY_THE_FROZEN_POLICY",
    "DataLossCondition", "DataLossSupervisor", "SupervisedFailsafe",
    "SEMANTICS_VERSION",
]
