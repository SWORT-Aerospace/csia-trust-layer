"""Seven deliberately wrong mission-assurance implementations.

WHY THEY EXIST
--------------
A conformance suite that only ever sees a correct implementation tests
nothing. These seven are each wrong in ONE specific, named way, and the suite
must reject each of them for the right reason.

THE RULE THE SUITE MUST OBEY
-----------------------------
**Rejection may not depend on the implementation's NAME.** A checker that
looks for "BAD_" in a class name passes this file and fails the first real
defect. Every rejection below has to come from observing BEHAVIOUR on inputs
the checker constructs, and `tests/test_bad_product_references.py` asserts
that by feeding the checker a correct implementation named
`BAD_PRODUCT_08_actually_fine` -- which must PASS.

THE SEVEN
---------
    BAD_PRODUCT_01  absolute map stays supported after position support goes
    BAD_PRODUCT_02  stale camera calibration accepted
    BAD_PRODUCT_03  compute-health failure ignored
    BAD_PRODUCT_04  certificate survives a configuration change
    BAD_PRODUCT_05  capability restored immediately, without fresh evidence
    BAD_PRODUCT_06  planner overrides a NOT_SUPPORTED capability
    BAD_PRODUCT_07  a high hypothesis score alone certifies a product

Each is a real failure mode, not a strawman. 01 is what you get from one flat
dependency graph. 03 is what you get from a product layer with no compute
notion. 05 is what you get from restoring on presence. 07 is what you get
from a system that never separated ranking from support -- which is the
finding the whole CSIA programme is built on.
"""

from .implementations import (                              # noqa: F401
    BAD_PRODUCT_01_absolute_map_survives_position_loss,
    BAD_PRODUCT_02_stale_calibration_accepted,
    BAD_PRODUCT_03_compute_failure_ignored,
    BAD_PRODUCT_04_certificate_survives_reconfiguration,
    BAD_PRODUCT_05_instant_restore_on_presence,
    BAD_PRODUCT_06_planner_overrides_unsupported,
    BAD_PRODUCT_07_score_alone_certifies,
    BAD_PRODUCT_08_actually_fine,
    GOOD_REFERENCE,
    ALL_REFERENCES,
)

__all__ = [
    "BAD_PRODUCT_01_absolute_map_survives_position_loss",
    "BAD_PRODUCT_02_stale_calibration_accepted",
    "BAD_PRODUCT_03_compute_failure_ignored",
    "BAD_PRODUCT_04_certificate_survives_reconfiguration",
    "BAD_PRODUCT_05_instant_restore_on_presence",
    "BAD_PRODUCT_06_planner_overrides_unsupported",
    "BAD_PRODUCT_07_score_alone_certifies",
    "BAD_PRODUCT_08_actually_fine",
    "GOOD_REFERENCE",
    "ALL_REFERENCES",
]
