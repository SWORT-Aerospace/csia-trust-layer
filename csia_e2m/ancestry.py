"""Eight channels are not eight independent witnesses.

THE ERROR THIS EXISTS TO PREVENT
--------------------------------
A multiplexer makes it cheap to attach many sensors, and cheap to believe they
corroborate each other. They do not. Every reading behind one TCA9548A passes
through the same switch, the same upstream bus, the same controller, the same
firmware build, the same driver code, the same power rail, the same ground, the
same clock, the same USB path, the same host logger and the same configuration
file. A fault in any of those moves every channel at once.

The dangerous version is majority voting: three sensors on one mux "agree", so
the reading is treated as confirmed three times over. If the thing that is
wrong is the rail or the driver, the agreement is the *symptom*, not evidence
against the fault.

This module makes the shared dependencies explicit so a consumer can count
independent lineages instead of counting sensors. It does not decide what to do
about a shared lineage -- that is a judgement for whoever is combining the
evidence, and this layer has no authority to make it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, FrozenSet, Iterable, List, Tuple

#: The dependency kinds the owner's §12 requires be recorded. Naming them as a
#: closed set means a new sensor cannot quietly omit one.
DEPENDENCY_KINDS = (
    "multiplexer", "upstream_bus", "controller", "firmware", "driver",
    "power_rail", "ground", "clock", "serial_path", "host_logger",
    "configuration",
)


@dataclass(frozen=True)
class Lineage:
    """Everything one sensor's readings depend on besides the sensor."""

    sensor: str
    channel: int
    dependencies: Dict[str, str]

    def __post_init__(self) -> None:
        missing = [k for k in DEPENDENCY_KINDS if k not in self.dependencies]
        if missing:
            raise ValueError(
                f"{self.sensor}: lineage omits {missing}. Every kind must be "
                f"named; a dependency nobody wrote down is one nobody can "
                f"reason about")
        extra = [k for k in self.dependencies if k not in DEPENDENCY_KINDS]
        if extra:
            raise ValueError(f"{self.sensor}: unknown dependency kinds {extra}")

    def shared_with(self, other: "Lineage") -> FrozenSet[str]:
        return frozenset(k for k in DEPENDENCY_KINDS
                         if self.dependencies[k] == other.dependencies[k])


@dataclass(frozen=True)
class AncestryReport:
    """How much independence a set of sensors actually has."""

    sensors: Tuple[str, ...]
    shared_by_all: FrozenSet[str]
    pairwise: Dict[Tuple[str, str], FrozenSet[str]] = field(default_factory=dict)

    @property
    def independent_lineages(self) -> int:
        """Distinct dependency fingerprints, not sensor count.

        Three sensors on one mux, one rail and one controller have **one**
        infrastructure lineage between them, not three.
        """
        return len({tuple(sorted(v)) for v in self._fingerprints})

    _fingerprints: Tuple = field(default_factory=tuple, repr=False)

    @property
    def any_fully_shared(self) -> bool:
        return bool(self.shared_by_all)

    def as_dict(self) -> dict:
        return {
            "sensors": list(self.sensors),
            "shared_by_all": sorted(self.shared_by_all),
            "independent_lineages": self.independent_lineages,
            "sensor_count": len(self.sensors),
            "pairwise_shared": {
                f"{a}|{b}": sorted(v) for (a, b), v in self.pairwise.items()},
            "what_this_means": (
                "sensor_count is how many devices reported; "
                "independent_lineages is how many distinct infrastructure "
                "paths those reports travelled. Treating the first as the "
                "second is how a correlated fault becomes majority agreement"),
        }


def analyse(lineages: Iterable[Lineage]) -> AncestryReport:
    items: List[Lineage] = list(lineages)
    if not items:
        raise ValueError("no lineages to analyse")
    names = tuple(item.sensor for item in items)
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate sensor names in {names}")

    shared_by_all = frozenset(
        k for k in DEPENDENCY_KINDS
        if len({item.dependencies[k] for item in items}) == 1)

    pairwise: Dict[Tuple[str, str], FrozenSet[str]] = {}
    for a, b in combinations(items, 2):
        pairwise[(a.sensor, b.sensor)] = a.shared_with(b)

    fingerprints = tuple(
        frozenset(f"{k}={item.dependencies[k]}" for k in DEPENDENCY_KINDS)
        for item in items)
    return AncestryReport(sensors=names, shared_by_all=shared_by_all,
                          pairwise=pairwise, _fingerprints=fingerprints)


def corroboration_is_independent(report: AncestryReport) -> bool:
    """Whether agreement among these sensors could mean anything.

    ``False`` whenever every sensor shares at least one dependency, which for a
    single-mux bench is always. Stated as a function so a consumer that wants
    to vote has to call something that says no.
    """
    return not report.any_fully_shared


def common_mode_channels(report: AncestryReport, kind: str) -> bool:
    """Whether `kind` is common to every sensor in the report."""
    if kind not in DEPENDENCY_KINDS:
        raise ValueError(f"unknown dependency kind {kind!r}")
    return kind in report.shared_by_all
