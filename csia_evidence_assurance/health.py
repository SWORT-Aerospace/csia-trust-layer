"""Producer health: whether a monitor can be trusted, kept apart from what
the monitor says.

The states follow the available / degraded / unavailable usage of health
management practice (V0: terminology only), plus FAULTED for a producer
whose own self-check failed, and UNKNOWN for a producer that did not say.

| state | the producer is | its output is |
|---|---|---|
| VALID | operating within its declared regime and rate | evidence |
| DEGRADED | operating outside a declared quality bound | evidence, with a warning on the result |
| UNAVAILABLE | not producing (gated out, silent) | not evidence |
| FAULTED | producing, but its self-check failed or its metadata is impossible | not evidence; the fault is reported |
| UNKNOWN | not reporting health although its contract says it must | not evidence |

**The rule that matters:** a NOMINAL claim from an UNAVAILABLE, FAULTED or
UNKNOWN producer never reaches the reasoning core as NOMINAL. That is 2.1's
Kleene rule for missing evidence (C2), extended to the producer.

A producer whose contract declares that it does not report health
(`health_reporting: IN_PROCESS`, the frozen v2 domain plugins, which run in
the analyzer's own process and whose failures the plugin runtime already
turns into UNAVAILABLE records) is VALID when it produced an output this
tick. That basis is written on the result.
"""

from __future__ import annotations

from enum import Enum


class ProducerHealth(str, Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    FAULTED = "FAULTED"
    UNKNOWN = "UNKNOWN"


#: Health states whose output may reach the core.
USABLE = (ProducerHealth.VALID, ProducerHealth.DEGRADED)
