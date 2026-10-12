"""Evidence about the evidence. Three questions CSIA could not previously ask.

CSIA qualifies what a vehicle's sensors and components are doing. It has had
no way to qualify THE EVIDENCE BASE ITSELF, and that gap shows up the moment
it meets data it did not design:

  ingestion  Is this channel what it claims to be, and on what grounds?
  intent     Was the system doing what it was told, and what did
             deviating cost in evidence?
  corpus     How much INDEPENDENT evidence do I actually have across runs?

All three are domain-neutral. Nothing here knows about aircraft, batteries,
motors or missions. A channel is a named series, a commitment is a checkable
predicate, a run is a record with declared factors. The same code applies to
a spacecraft, a dialysis machine, a substation or a warehouse robot.

THE RULE THAT MAKES THEM SAFE TO ADD
-------------------------------------
    NOTHING IN THIS PACKAGE PROMOTES ANYTHING.

`ingestion` never decides a channel is trustworthy; it reports what it found and
what it could not place. `intent` never decides a deviation was wrong; it
reports what held and what that cost. `corpus` never decides a result
generalises; it reports how many independent things were actually observed.
Each returns a record. A human or an explicit policy decides.

That is the same discipline `csia_supervision/capability_bridge.py` follows
one layer down, where an overlay may only ever WITHDRAW support and UNKNOWN
never becomes a firm negative.

WHAT IS NOT HERE
----------------
No frozen path is imported. No learned component, no language model, no
network call, no clock dependence. Every decision is a comparison against a
declared threshold with its basis recorded beside it.
"""

from .ingestion import (Evidence, EvidenceKind, ChannelSpec, Mapping,
                     IngestReport, ingest, GRADE_ORDER)
from .intent import (Commitment, CommitmentOutcome, Deviation, IntentReport,
                     compare)
from .corpus import (Run, FactorReport, CorpusReport, effective_n,
                     independence, accumulate)

__all__ = [
    "Evidence", "EvidenceKind", "ChannelSpec", "Mapping", "IngestReport",
    "ingest", "GRADE_ORDER",
    "Commitment", "CommitmentOutcome", "Deviation", "IntentReport", "compare",
    "Run", "FactorReport", "CorpusReport", "effective_n", "independence",
    "accumulate",
]
