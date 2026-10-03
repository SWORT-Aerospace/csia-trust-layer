"""Product releases of the ordinary-ULog (stock) path. OFFBOARD ONLY.

A release fixes everything that decides an analysis of an ordinary PX4 log:
the timebase, event discovery, the stock producers' versions and the
contracts they are admitted under. The historical release stays the default
of every function that takes a release, so a historical output can never
change by accident.

| release | what | used by |
|---|---|---|
| `2.3` | the stock bridge exactly as validated in CSIA 2.3 and used by PRIME | `analyze`; `assure --release prime`; every historical report |
| `prime1` | the PRIME-1 successor (below) | `assure` (and `csia-assure`) by default |

**What `prime1` changes, and why** (`research/csia_prime1/`):

| change | answers | how |
|---|---|---|
| canonical integer-microsecond timebase | D-PRIME-1: a sub-microsecond representation difference changed an admissibility decision | every stock-topic time is snapped to the PX4 ULog resolution (1 us) on ingestion; event anchors are therefore on the grid; the 2.2 gate compares times as integer ticks of the declared resolution (`admissibility.AnalysisContext.time_resolution_s`), coarser per producer when a producer declares a coarser clock |
| bidirectional RPM-telemetry discovery | D-PRIME-2: an RPM excess opened no event | two explicit one-sided CUSUM arms on the same telemetry-response statistic: `propulsion.rpm_deficit` (RPM_DEFICIT_EVENT) and `propulsion.rpm_excess` (RPM_EXCESS_EVENT). Same k and h: the 2.3 calibration rule already measured the null deviation as an absolute value |
| telemetry baseline validity | D-PRIME-2: a late event compared a corrupted BEFORE window with a corrupted AFTER window and read NOMINAL | the telemetry-response statistic is withheld (UNAVAILABLE, `TELEMETRY_BASELINE_INCONSISTENT`) when the BEFORE window's level disagrees grossly with the other rotors |
| ESC-offline trigger | an ESC reporting itself offline is PX4 information, not a deficit | `px4.esc_offline`: falling edge of an `esc_online_flags` bit in flight |
| steadiness-gated compensation alarms | PRIME C3: the compensation CUSUM raises hundreds of maneuver events per hour | a compensation alarm opens an event only when the body rate around its onset is within the compensation's own validity regime (the shipped theta_steady) |
| identical-condition merge | PRIME RR-10: a flapping PX4 warning re-raised the same event dozens of times | a re-raised identical PX4 condition within 60 s opens no new event |
| test-harness messages ignored | PRIME blinding finding: PX4's failure-injection message is ground truth, not vehicle evidence | `[failure_injection_manager]` messages are never triggers; they are counted in a labelled debug field only |

Nothing in Semantic Core 2.1.1 changes. No threshold is new except the
declared, uncalibrated gross-inconsistency band of the baseline-validity
condition (`TELEMETRY_LEVEL_BAND`).
"""
from __future__ import annotations

from dataclasses import dataclass

HISTORICAL = "2.3"
PRIME1 = "prime1"


@dataclass(frozen=True)
class Release:
    name: str
    #: The analysis timebase resolution (s). None: the historical float comparison (1 ns tolerance).
    time_resolution_s: float | None
    #: Event-discovery mode (`events.discover`).
    discovery: str
    #: Telemetry-response producer version and the contract file it is admitted under.
    telemetry_producer_version: str
    telemetry_contract: str
    description: str


RELEASES = {
    HISTORICAL: Release(HISTORICAL, None, "2.3", "csia-2.3-stock-r1", "stock_esc_telemetry_response",
                        "CSIA 2.3 stock bridge (historical)"),
    PRIME1: Release(PRIME1, 1e-6, "prime1", "csia-prime1-stock-tel-r1", "stock_esc_telemetry_response_prime1",
                    "CSIA Flight Assurance PRIME-1"),
}

#: The baseline-validity band on q (ESC-reported rotor speed squared per commanded thrust,
#: against the median rotor). DECLARED, NOT CALIBRATED: a gross-inconsistency guard chosen so
#: that ordinary rotor-to-rotor variation (a few to tens of percent in q) never trips it, while
#: a telemetry report off by more than about 41 % in RPM against its peers does. It must be
#: re-examined on real nominal data before any claim depends on its exact value.
TELEMETRY_LEVEL_BAND = 2.0


def get(name: str) -> Release:
    if name not in RELEASES:
        raise ValueError(f"unknown release {name!r}; known: {sorted(RELEASES)}")
    return RELEASES[name]
