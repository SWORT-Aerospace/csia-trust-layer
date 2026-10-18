"""Hardware-independent aircraft interface (CSIA v1.1, phases S2/S5/S6).

This package is the boundary between *a specific autopilot* and *the CSIA
diagnostic core*. Nothing below it knows what an autopilot is; nothing above it
knows what a MAVLink message is.

    vehicle telemetry
          |
          v
    platform adapter        <- csia.aircraft.adapters.*
          |                    owns field mapping, units, frames, freshness,
          |                    missing-value handling, semantic qualification
          v
    AircraftSample          <- csia.aircraft.sample
          |                    canonical units, explicit validity metadata
          v
    CSIA diagnostic core    <- csia.runtime.online (FROZEN v1, untouched)

The one rule this package enforces that v1 did not:

    A CHANNEL THAT IS PRESENT AND FRESH IS NOT AUTOMATICALLY EVIDENCE.

A channel reaches the core only if its semantics are qualified INFORMATIVE in
`docs/simulation/CHANNEL_SEMANTICS.yaml`. Anything else arrives as MISSING with
a machine-readable reason, so the layer abstains rather than concluding from a
constant. See docs/v1/V1_FINAL_RESEARCH_VERDICT.md W-5 for the measured defect
that motivated this.
"""

from .sample import (AircraftSample, ChannelValue, Quality,
                     MissingReason, SensorFrame)

__all__ = ["AircraftSample", "ChannelValue", "Quality", "MissingReason",
           "SensorFrame"]
