"""Advisory recommendations — Phase 4 §24.

**Recommendations are ADVISORY. Nothing here transmits anything.** This module
returns strings. It imports no transport, holds no connection, and the output
firewall (`csia/v1_1/firewall.py`, and `csia/deploy/guard.py` beneath it)
denies the transmit surface regardless of what is recommended.

The mapping is a deterministic table over the eligibility verdicts and the
assurance level — the same inputs a human reading the ledger would use. It
introduces no threshold and no new evidence: if a recommendation appears, some
function's eligibility already changed and already carries its reason codes.
"""

from __future__ import annotations

from ..runtime.failsafe import FailsafeLevel
from . import reason_codes as RC

#: Every recommendation this module can ever return. A test asserts the
#: returned set is a subset, so a new string cannot appear in a flight record
#: without appearing here.
RECOMMENDATIONS = (
    "RESTRICT_PRECISION_NAV",
    "INHIBIT_GPS_MODES",
    "SWITCH_NAV_INERTIAL",
    "MANUAL_REVIEW",
)

_GNSS_FUNCTIONS = ("COARSE_NAVIGATION", "POSITION_HOLD",
                   "PRECISION_NAVIGATION", "GEOFENCE_SUPPORT")


def recommend(eligibility: dict, assurance_level: int) -> tuple:
    """Advisory recommendations for one tick. Deterministic and total.

    `eligibility` is `{function: state}`. Order is fixed by `RECOMMENDATIONS`
    so the ledger's content hash does not depend on dict iteration order.
    """
    states = {k: (v.state if hasattr(v, "state") else v)
              for k, v in eligibility.items()}
    out = set()

    if states.get("PRECISION_NAVIGATION") in (RC.INELIGIBLE, RC.DEGRADED):
        out.add("RESTRICT_PRECISION_NAV")

    gnss = [states[f] for f in _GNSS_FUNCTIONS if f in states]
    gnss_all_gone = bool(gnss) and all(s == RC.INELIGIBLE for s in gnss)
    if gnss_all_gone:
        out.add("INHIBIT_GPS_MODES")
        if states.get("INERTIAL_CONTINUATION") in (RC.ELIGIBLE, RC.DEGRADED):
            out.add("SWITCH_NAV_INERTIAL")

    # The policy could not decide, or nothing is left to fall back on.
    if RC.UNKNOWN in states.values():
        out.add("MANUAL_REVIEW")
    if gnss_all_gone and states.get("INERTIAL_CONTINUATION") == RC.INELIGIBLE:
        out.add("MANUAL_REVIEW")
    if int(assurance_level) >= int(FailsafeLevel.EMERGENCY):
        out.add("MANUAL_REVIEW")

    return tuple(r for r in RECOMMENDATIONS if r in out)
