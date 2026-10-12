"""The deterministic provenance chain, and the hash every layer uses.

THE CHAIN
---------
    RAW SENSOR / PAYLOAD DATA
        v
    CANONICAL EVIDENCE
        v
    FROZEN CSIA OUTPUT
        v
    SUPPORT FIREWALL
        v
    CAPABILITY SUPPORT
        v
    MISSION PRODUCT QUALIFICATION
        v
    MISSION REPORT

Every transition records: input hashes, software version, configuration hash,
output hash. A link whose declared input hash does not equal the previous
link's output hash BREAKS the chain, and `verify` says which link and why.

NO BLOCKCHAIN, AND NO CRYPTOGRAPHIC NON-REPUDIATION CLAIM
----------------------------------------------------------
These are content hashes. They detect ACCIDENTAL divergence -- a re-run
against different inputs, a configuration that changed between stages, a
record edited after the fact by someone not trying to hide it. They do not
detect a determined forger, because nothing is signed and the hashes are
computed by the same process that writes them.

Saying so here is not throat-clearing. A hash chain looks like tamper
evidence, and a reader who assumes it is one would be wrong in a way this
file can prevent by being explicit.

WHY CANONICAL SERIALISATION IS LOAD-BEARING
--------------------------------------------
Two records with the same content must hash the same on any host and in any
Python version, or a portability comparison becomes a hash comparison of
dictionary iteration order. `sort_keys=True` plus a fixed separator set plus
`default=str` is the whole rule, and it is applied in exactly one place so
there cannot be two.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

#: The chain's stages, in order. A link naming a stage not in this tuple is
#: rejected: an unnamed stage is a gap nobody can audit.
STAGES = (
    "RAW",
    "CANONICAL_EVIDENCE",
    "FROZEN_CSIA_OUTPUT",
    "SUPPORT_FIREWALL",
    "CAPABILITY_SUPPORT",
    "MISSION_PRODUCT_QUALIFICATION",
    "MISSION_REPORT",
)


def content_hash(obj: Any) -> str:
    """The one canonical hash. Every layer calls this; none rolls its own."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"),
                   default=str).encode()).hexdigest()


@dataclass(frozen=True)
class ProvenanceLink:
    stage: str
    input_hashes: tuple
    output_hash: str
    software_version: str
    configuration_hash: str
    timestamp: float
    note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["input_hashes"] = list(self.input_hashes)
        return d


@dataclass
class ProvenanceChain:
    """An append-only chain. `verify` is where the value is."""
    links: list = field(default_factory=list)

    def append(self, stage: str, inputs, output, software_version: str,
               configuration_hash: str, timestamp: float,
               note: str = "") -> ProvenanceLink:
        if stage not in STAGES:
            raise ValueError(
                f"unknown provenance stage {stage!r}; known: {list(STAGES)}. "
                f"An unnamed stage is a gap nobody can audit.")
        in_hashes = tuple(
            h if isinstance(h, str) and len(h) == 64 else content_hash(h)
            for h in (inputs if isinstance(inputs, (list, tuple))
                      else [inputs]))
        link = ProvenanceLink(
            stage=stage,
            input_hashes=in_hashes,
            output_hash=(output if isinstance(output, str) and len(output) == 64
                         else content_hash(output)),
            software_version=software_version,
            configuration_hash=configuration_hash,
            timestamp=timestamp,
            note=note,
        )
        self.links.append(link)
        return link

    def verify(self) -> dict:
        """Every way this chain can be broken, reported separately.

        Four failure modes, not pooled, because the fixes differ:

            OUT_OF_ORDER          stages do not run in the declared order
            BROKEN_LINK           a stage's input is not the previous output
            CONFIGURATION_DRIFT   the configuration hash changed mid-chain
            TIME_REGRESSION       a later stage is stamped earlier
        """
        problems: list = []
        last_stage_index = -1
        for i, link in enumerate(self.links):
            idx = STAGES.index(link.stage)
            if idx <= last_stage_index:
                problems.append({"link": i, "stage": link.stage,
                                 "problem": "OUT_OF_ORDER"})
            last_stage_index = max(last_stage_index, idx)

            if i > 0:
                prev = self.links[i - 1]
                if prev.output_hash not in link.input_hashes:
                    problems.append({
                        "link": i, "stage": link.stage,
                        "problem": "BROKEN_LINK",
                        "expected_input": prev.output_hash,
                        "declared_inputs": list(link.input_hashes)})
                if prev.configuration_hash != link.configuration_hash:
                    problems.append({
                        "link": i, "stage": link.stage,
                        "problem": "CONFIGURATION_DRIFT",
                        "from": prev.configuration_hash,
                        "to": link.configuration_hash})
                if link.timestamp < prev.timestamp:
                    problems.append({"link": i, "stage": link.stage,
                                     "problem": "TIME_REGRESSION"})

        return {
            "links": len(self.links),
            "stages_present": [x.stage for x in self.links],
            "problems": problems,
            "intact": not problems,
            "what_this_does_not_prove": (
                "that nobody tampered with the record. Nothing here is "
                "signed and the hashes are written by the same process that "
                "computes them. This detects ACCIDENTAL divergence -- a "
                "re-run against different inputs, a configuration that "
                "changed mid-chain, a record edited by someone not trying to "
                "hide it. It is not tamper evidence."),
        }

    def to_dict(self) -> dict:
        return {"schema": "csia.mission.provenance_chain/1",
                "links": [x.to_dict() for x in self.links],
                "verification": self.verify()}


def configuration_hash(vehicle: Mapping | None = None,
                       payload: Mapping | None = None,
                       software: Mapping | None = None) -> str:
    """One hash over everything that would make two runs incomparable.

    Deliberately covers all three: a run is a different run if the airframe
    changed, if the payload changed, OR if the code changed, and a hash that
    covered only one of them would let the other two drift silently.
    """
    return content_hash({"vehicle": dict(vehicle or {}),
                         "payload": dict(payload or {}),
                         "software": dict(software or {})})
