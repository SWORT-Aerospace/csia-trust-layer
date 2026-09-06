"""EXPERIMENTAL SUPPORT CERTIFICATE -- the machine-readable witness.

THE NAME IS DELIBERATE AND IS NOT NEGOTIABLE IN THIS FILE.
This is an **experimental support certificate**. It is NOT:

    a certified safety artifact
    a certification credential
    evidence of airworthiness
    anything that has been reviewed by anybody outside this repository

A test asserts the string "EXPERIMENTAL" survives in the emitted record, so a
downstream consumer cannot strip the qualification by accident.

WHAT A CERTIFICATE ASSERTS
--------------------------
That at time `t`, under configuration `config_hash` and software
`software_hash`, the leader was separated from EVERY competitor the model
admits by at least one ACTIVE discriminator, and here are those
discriminators.

WHAT MAKES IT STALE
-------------------
Anything that changes what "active" or "competitor" means: a different
configuration, a different hypothesis set, a different evidence topology, a
timestamp beyond `valid_until`, or a different semantics version. The
firewall re-checks all of those on the next record; the certificate itself
carries the fields that make the check possible rather than asserting its own
freshness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Mapping

#: Written into every certificate. See the module docstring.
STATUS = "EXPERIMENTAL_SUPPORT_CERTIFICATE"


@dataclass(frozen=True)
class DiagnosticSupportWitness:
    """One target-vs-competitor separation, and what did the separating."""
    target_hypothesis: str
    competitor_hypothesis: str
    active_discriminator_ids: tuple
    evidence_source_ids: tuple
    applicability_state: str
    freshness_state: str
    timestamp: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["active_discriminator_ids"] = list(self.active_discriminator_ids)
        d["evidence_source_ids"] = list(self.evidence_source_ids)
        return d


@dataclass(frozen=True)
class SupportCertificate:
    """Enough witnesses to separate the target from every modeled competitor.

    `complete` is False whenever any competitor lacks a witness. A certificate
    is emitted in that case too, and says so -- an incomplete certificate is a
    record of WHY support was refused, which is more useful than no record.
    """
    status: str
    target_hypothesis: str
    witnesses: tuple
    competitors_without_witness: tuple
    complete: bool
    timestamp: float
    config_hash: str
    software_hash: str
    evidence_hash: str
    semantics_version: str
    hypothesis_set: tuple
    evidence_topology: tuple
    valid_until: float | None = None
    certificate_hash: str = field(default="", compare=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["witnesses"] = [w.to_dict() if isinstance(w, DiagnosticSupportWitness)
                          else dict(w) for w in self.witnesses]
        for k in ("competitors_without_witness", "hypothesis_set",
                  "evidence_topology"):
            d[k] = list(d[k])
        return d


def _digest(payload: dict) -> str:
    """Content hash over the certificate minus its own hash field.

    A hash that covered itself would be uncomputable; a hash that covered only
    some fields would let the rest be edited silently. So: everything except
    `certificate_hash`, canonically serialised.
    """
    body = {k: v for k, v in payload.items() if k != "certificate_hash"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"),
                   default=str).encode()).hexdigest()


def build_certificate(verdict, record: Mapping,
                      semantics_version: str,
                      validity_window_s: float | None = None
                      ) -> SupportCertificate:
    """Turn a firewall verdict plus its input record into a certificate.

    Emitted for AMBIGUOUS and NON_IDENTIFIABLE too, with `complete=False`.
    Refusing to emit on refusal would mean the only durable record of a
    decision was the record of the decisions that went well.
    """
    states = record.get("evidence_states") or {}
    sources = record.get("evidence_sources") or {}
    ts = float(record.get("timestamp", 0.0))

    witnesses = []
    for competitor, discriminators in sorted(
            (verdict.witnesses or {}).items()):
        if not discriminators:
            continue
        witnesses.append(DiagnosticSupportWitness(
            target_hypothesis=verdict.leader,
            competitor_hypothesis=competitor,
            active_discriminator_ids=tuple(discriminators),
            evidence_source_ids=tuple(sorted(
                {sources.get(d, "UNDECLARED") for d in discriminators})),
            applicability_state="APPLICABLE",
            freshness_state="FRESH",
            timestamp=ts,
        ))

    payload = SupportCertificate(
        status=STATUS,
        target_hypothesis=verdict.leader or "NONE",
        witnesses=tuple(witnesses),
        competitors_without_witness=tuple(
            verdict.competitors_without_witness),
        complete=(verdict.state == "SUPPORTED_UNIQUE"),
        timestamp=ts,
        config_hash=str(record.get("config_hash", "UNKNOWN")),
        software_hash=str(record.get("software_hash", "UNKNOWN")),
        evidence_hash=str(record.get("evidence_hash", "UNKNOWN")),
        semantics_version=semantics_version,
        hypothesis_set=tuple(sorted(record.get("signatures") or {})),
        evidence_topology=tuple(sorted(record.get("gates") or {})),
        valid_until=(ts + validity_window_s
                     if validity_window_s is not None else None),
    )
    d = payload.to_dict()
    return SupportCertificate(**{**{k: v for k, v in asdict(payload).items()
                                    if k != "certificate_hash"},
                                 "witnesses": payload.witnesses,
                                 "certificate_hash": _digest(d)})


def certificate_is_current(cert: SupportCertificate, record: Mapping,
                           semantics_version: str) -> tuple:
    """(bool, reason). What makes a certificate stale, checked explicitly.

    Returns the FIRST reason found rather than a list: a certificate that is
    stale for one reason is stale, and enumerating the rest invites a reader
    to weigh them.
    """
    if cert.semantics_version != semantics_version:
        return False, "SEMANTICS_VERSION_CHANGED"
    if cert.config_hash != str(record.get("config_hash", "UNKNOWN")):
        return False, "CONFIG_HASH_MISMATCH"
    if cert.software_hash != str(record.get("software_hash", "UNKNOWN")):
        return False, "SOFTWARE_HASH_MISMATCH"
    if sorted(cert.hypothesis_set) != sorted(record.get("signatures") or {}):
        return False, "HYPOTHESIS_SET_CHANGED"
    if sorted(cert.evidence_topology) != sorted(record.get("gates") or {}):
        return False, "EVIDENCE_TOPOLOGY_CHANGED"
    ts = record.get("timestamp")
    if isinstance(ts, (int, float)):
        if ts < cert.timestamp:
            return False, "TIMESTAMP_REGRESSION"
        if cert.valid_until is not None and ts > cert.valid_until:
            return False, "EXPIRED"
    return True, "CURRENT"
