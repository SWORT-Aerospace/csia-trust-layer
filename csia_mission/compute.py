"""A platform-neutral compute-evidence record.

WHY COMPUTE NEEDS AN EVIDENCE RECORD AT ALL
---------------------------------------------
A mapping product that depends on onboard processing is not supported merely
because the camera worked. If the compute that would build the map missed its
deadline, the map is not a map -- and a product layer with no notion of
compute state has no way to say so. That is BAD_PRODUCT_03 in the conformance
suite, and it is a real failure mode rather than a hypothetical one.

PLATFORM-NEUTRAL, AND SPECIFICALLY NOT SACA-SHAPED
----------------------------------------------------
Nothing in this file requires any particular compute platform. A Linux host
can populate a subset today from `/proc` and `resource`; a richer platform
could populate more later. **Fields that platform cannot answer stay UNKNOWN.**

That last sentence is the whole design. The tempting alternative -- default a
field to "fine" when the platform cannot report it -- turns every unsupported
platform into a silently healthy one. The vocabulary therefore has a value
meaning "not measured", and it is the DEFAULT rather than an exceptional case.

WHAT A LINUX HOST CAN AND CANNOT SAY
--------------------------------------
    availability     yes -- the process is running and responded
    deadline_state   yes -- measured against a declared budget
    scheduler_state  partially -- nice value and policy are readable
    memory_state     yes -- RSS against a declared budget
    thermal_state    sometimes -- /sys/class/thermal may not exist
    execution_state  no -- requires platform support this host lacks
    integrity_state  NO -- requires attestation hardware. Stays UNKNOWN.

`integrity_state` is the honest one. There is no attestation here, so there
is no integrity evidence, and a field reading "OK" would be a fabrication.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

COMPUTE_UNKNOWN = "UNKNOWN"
COMPUTE_SUPPORTED = "SUPPORTED"
COMPUTE_DEGRADED = "DEGRADED"
COMPUTE_NOT_SUPPORTED = "NOT_SUPPORTED"

COMPUTE_STATES = (COMPUTE_SUPPORTED, COMPUTE_DEGRADED, COMPUTE_NOT_SUPPORTED,
                  COMPUTE_UNKNOWN)

#: Fields no implementation in this repository can populate honestly. Listed
#: so that a future provider filling one in is a visible change, and so a
#: reader can see the gap without reading the collector.
NOT_MEASURABLE_HERE = ("execution_state", "integrity_state")


@dataclass(frozen=True)
class ComputeEvidence:
    """One compute domain's state. Every field defaults to UNKNOWN."""
    compute_domain: str
    availability: str = COMPUTE_UNKNOWN
    deadline_state: str = COMPUTE_UNKNOWN
    scheduler_state: str = COMPUTE_UNKNOWN
    memory_state: str = COMPUTE_UNKNOWN
    thermal_state: str = COMPUTE_UNKNOWN
    execution_state: str = COMPUTE_UNKNOWN
    integrity_state: str = COMPUTE_UNKNOWN
    timestamp: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)
    detail: Mapping[str, Any] = field(default_factory=dict)

    def rollup(self) -> str:
        """One state for the capability layer to consume. Worst wins.

        UNKNOWN fields are NOT ignored: a domain whose deadline state nobody
        measured cannot be called SUPPORTED, because the measurement that
        would justify it was never taken. Only `execution_state` and
        `integrity_state` are exempt, because NOTHING here can measure them
        and treating their permanent absence as a fault would make every
        rollup NOT_SUPPORTED forever, which reports nothing.
        """
        considered = [self.availability, self.deadline_state,
                      self.scheduler_state, self.memory_state,
                      self.thermal_state]
        if COMPUTE_NOT_SUPPORTED in considered:
            return COMPUTE_NOT_SUPPORTED
        if COMPUTE_UNKNOWN in considered:
            return COMPUTE_UNKNOWN
        if COMPUTE_DEGRADED in considered:
            return COMPUTE_DEGRADED
        return COMPUTE_SUPPORTED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["provenance"] = dict(d["provenance"])
        d["detail"] = dict(d["detail"])
        d["rollup"] = self.rollup()
        d["not_measurable_on_this_platform"] = list(NOT_MEASURABLE_HERE)
        return d


def _thermal_state() -> tuple:
    """Read a thermal zone if one exists. Absent means UNKNOWN, not cool."""
    base = "/sys/class/thermal"
    if not os.path.isdir(base):
        return COMPUTE_UNKNOWN, {"why": "no /sys/class/thermal on this host"}
    temps = []
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name, "temp")
        try:
            with open(path, encoding="utf-8") as fh:
                temps.append(int(fh.read().strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    if not temps:
        return COMPUTE_UNKNOWN, {"why": "no readable thermal zone"}
    hottest = max(temps)
    # The thresholds are DECLARED HERE and are a property of this collector,
    # not of CSIA. They are not a diagnostic threshold and they touch nothing
    # in the frozen core.
    if hottest >= 90.0:
        return COMPUTE_NOT_SUPPORTED, {"max_c": hottest}
    if hottest >= 75.0:
        return COMPUTE_DEGRADED, {"max_c": hottest}
    return COMPUTE_SUPPORTED, {"max_c": hottest}


def collect_linux(compute_domain: str,
                  deadline_budget_s: float | None = None,
                  observed_latency_s: float | None = None,
                  memory_budget_bytes: int | None = None,
                  now: float | None = None) -> ComputeEvidence:
    """Populate what a Linux host can honestly answer. Nothing else.

    `deadline_state` is UNKNOWN unless BOTH a budget and an observation are
    supplied. A budget with no measurement is a plan; a measurement with no
    budget is a number. Neither is evidence about a deadline.
    """
    now = time.time() if now is None else now
    detail: dict = {}

    availability = COMPUTE_SUPPORTED          # this code is running
    detail["availability_basis"] = ("the collector executed; this says the "
                                    "process is alive, and nothing more")

    if deadline_budget_s is None or observed_latency_s is None:
        deadline_state = COMPUTE_UNKNOWN
        detail["deadline_basis"] = (
            "UNKNOWN: a budget without a measurement is a plan, and a "
            "measurement without a budget is a number")
    else:
        ratio = observed_latency_s / deadline_budget_s if deadline_budget_s \
            else float("inf")
        detail["deadline_ratio"] = ratio
        deadline_state = (COMPUTE_SUPPORTED if ratio <= 1.0
                          else COMPUTE_DEGRADED if ratio <= 2.0
                          else COMPUTE_NOT_SUPPORTED)

    try:
        nice = os.nice(0)
        detail["nice"] = nice
        scheduler_state = COMPUTE_SUPPORTED if nice <= 0 else COMPUTE_DEGRADED
    except OSError:
        scheduler_state = COMPUTE_UNKNOWN

    memory_state = COMPUTE_UNKNOWN
    try:
        import resource
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        detail["max_rss_bytes"] = rss_kb * 1024
        if memory_budget_bytes:
            ratio = (rss_kb * 1024) / memory_budget_bytes
            detail["memory_ratio"] = ratio
            memory_state = (COMPUTE_SUPPORTED if ratio <= 0.8
                            else COMPUTE_DEGRADED if ratio <= 1.0
                            else COMPUTE_NOT_SUPPORTED)
        else:
            detail["memory_basis"] = "UNKNOWN: no declared budget to compare"
    except (ImportError, OSError):
        pass

    thermal_state, thermal_detail = _thermal_state()
    detail["thermal"] = thermal_detail

    return ComputeEvidence(
        compute_domain=compute_domain,
        availability=availability,
        deadline_state=deadline_state,
        scheduler_state=scheduler_state,
        memory_state=memory_state,
        thermal_state=thermal_state,
        # Both stay UNKNOWN. See NOT_MEASURABLE_HERE and the module docstring.
        execution_state=COMPUTE_UNKNOWN,
        integrity_state=COMPUTE_UNKNOWN,
        timestamp=now,
        provenance={"collector": "csia_mission.compute.collect_linux",
                    "platform": "linux",
                    "requires_no_special_hardware": True},
        detail=detail,
    )


def as_capability_input(records) -> dict:
    """{domain: rollup} for `evaluate_capabilities(compute=...)`."""
    return {r.compute_domain: r.rollup() for r in records}
