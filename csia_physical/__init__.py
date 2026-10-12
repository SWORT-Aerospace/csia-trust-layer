"""Physical ingestion — the ADDITIVE layer above `csia_e2m`.

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT
----------------------------------------------
`csia_e2m` already implements the acquisition half of physical ingestion: the
CRC'd serial record, the append-only JSONL logger, the run manifest, the
deterministic replay, the fault-injection adapter, the identity assessment
and the deterministic fake controller. It carries 158 tests and a mutation
result of 38 evaluated / 36 killed / 2 survived, and those two survivors are
quoted and pinned.

**So this package does not reimplement any of it.** Duplicating the
acquisition layer would fork it, and the published 38/36/2 would stop
describing the code actually in use. `csia_physical` imports `csia_e2m`
read-only and supplies only the four things it does not have:

    annotations.py     fault and ground-truth annotation, as a SIDECAR
    csia_adapter.py    observations -> CSIA-shaped input, missing never zero
    evidence_schema.py derived evidence, kept separate from raw observation
    support_schema.py  support state and a FORGE-compatible capability record

WHY ANNOTATIONS ARE A SIDECAR AND NOT A LOG FIELD
--------------------------------------------------
The raw log is what the controller said. "A fault was injected at t=12.4 s"
and "the ground truth is that channel 3 is the faulty one" are **operator
claims**, not controller output, and writing them into the same stream would
make an immutable record of measurement into a mutable record of belief.

They are therefore written to a separate annotation file keyed by run id, and
joined at analysis time. The raw log stays byte-identical whether or not
anybody ever annotates it, and a reader can always recover what the hardware
reported without what the operator believed.

WALL TIME, FOR THE SAME REASON, IS A RUN-LEVEL FACT
-----------------------------------------------------
`csia_e2m.logging` records `time.monotonic_ns` per record and says why: the
wall clock can step backwards under NTP mid-run. That decision is correct and
is not reversed here. Wall time is recorded **once per run** in the annotation
sidecar, as the operator-facing anchor that says which afternoon the run
happened on, and every intra-run interval is still computed from the
monotonic clock.

STATUS
------
**NO HARDWARE HAS BEEN OPERATED.** All four E2M gates are open
(`research/bus_provenance/E2M_GATE_STATUS.md`) and this environment reports
`NO_HARDWARE_ACCESS`. Every hardware constant stays `BLOCKED`; nothing here
guesses a register address, a voltage limit, a timing limit or a datasheet
value, and the paths that would need one raise instead of running.

**Nothing in this package imports a hardware interface into the frozen
research packages, and nothing here is Forge.** The capability record uses a
schema a Forge-like consumer could ingest and says on its face that the
compatibility is unverified.
"""

__all__ = ["VERSION", "IS_EXPERIMENTAL", "HARDWARE_OPERATED",
           "TOUCHES_FROZEN_CORE", "REIMPLEMENTS_E2M"]

VERSION = "0.1.0"

#: Read by tests and stamped into every document this package emits.
IS_EXPERIMENTAL = True

#: The single most important flag in the package. No result derived from this
#: code may be described as live hardware validation while it is False.
HARDWARE_OPERATED = False

TOUCHES_FROZEN_CORE = False
REIMPLEMENTS_E2M = False
