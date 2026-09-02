"""Versioned read-only output API — Phase 4 §§20–23, 26, 28.

One payload per tick, validated against
`engineering/v1_1/csia_output_v1_1.schema.json`.

TWO NAMING DECISIONS THAT ARE NOT COSMETIC
------------------------------------------
**`posterior`, never `confidence`** (§22). It is a posterior probability under
a stated prior and likelihood. "Confidence" would assert a calibration nothing
in this system establishes, and the `gps_dropout` case — leader `nominal` at
0.9998 with zero discriminating evidence — is exactly where a consumer reading
the word "confidence" would be misled.

**`UNKNOWN` appears in two enums and means two different things**, so the two
never share a field: `function_eligibility[*].state == "UNKNOWN"` is *the
policy cannot determine eligibility*, while
`diagnosis.unknown_fault_model == "NOT_IMPLEMENTED"` is a constant saying the
unmodeled-fault hypothesis does not exist.

COMPATIBILITY — §26
-------------------
`project_v1()` produces the v1-shaped subset for an existing consumer, and
`assert_schema_version()` rejects a mismatch loudly. There is no third
behaviour: **no field is ever silently reinterpreted.**
"""

from __future__ import annotations

import functools
import json
import os

from ..runtime.failsafe import FailsafeLevel
from . import advisory
from . import sequential as SEQ
from .trust_mode import TrustMode, trust_mode_of

SCHEMA_VERSION = "1.1.0"
FROZEN_CORE_TAG = "csia-v1.0-research-final"

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "engineering", "v1_1", "csia_output_v1_1.schema.json")


class SchemaVersionError(ValueError):
    """Raised on a version mismatch. Deliberately an error: a consumer that
    kept reading a payload whose fields had been redefined is the failure
    §26 exists to prevent."""


@functools.lru_cache(maxsize=2)
def schema(path: str | None = None) -> dict:
    with open(path or _SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def build(*, t, platform, assurance_level, armed, trust, trust_mode,
          sequential_state, support_row, fresh, relation_gates,
          active_relations, suppressed_relations, suppression_reasons,
          verdicts, provenance, missing_reason=None, current_valid=None,
          ledger_event=None, transition_times=None) -> dict:
    """Assemble one payload. Pure: no I/O, no clock, no randomness."""
    mode = trust_mode_of(trust_mode)
    level = (assurance_level if isinstance(assurance_level, str)
             else FailsafeLevel(int(assurance_level)).name)
    tt = transition_times or {}

    elig = {}
    for name, v in sorted(verdicts.items()):
        elig[name] = {
            "state": v.state,
            "reason_codes": list(v.reason_codes),
            "required_inputs_available": bool(v.required_inputs_available),
            "support_sufficient": bool(v.support_sufficient),
            "transition_time": tt.get(name),
        }

    disc = dict(support_row.discriminating_terms)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": round(float(t), 4),
        "platform": platform,
        "assurance": {
            "level": level,
            "level_value": int(FailsafeLevel[level]),
            "armed": bool(armed),
            "transition_time": tt.get("__assurance__"),
        },
        "trust": {"mode": mode.value,
                  "nodes": {k: round(float(v), 9)
                            for k, v in sorted(trust.items())}},
        "sequential": {
            "k": SEQ.CUSUM_K, "h": SEQ.CUSUM_H,
            "covered_nodes": list(SEQ.COVERED_NODES),
            "nodes_without_residual": dict(SEQ.NO_RESIDUAL),
            "alarming": sorted(sequential_state.get("alarming", ())),
            "S": {k: round(float(v), 6)
                  for k, v in sorted(sequential_state.get("S", {}).items())},
        },
        "diagnosis": {
            "leader": support_row.leader,
            "posterior": round(float(support_row.posterior), 9),
            "runner_up": support_row.runner_up,
            "score_margin": round(float(support_row.score_margin), 9),
            "active_evidence_count": int(support_row.active_terms),
            "discriminating_evidence_count": (min(disc.values()) if disc
                                              else 0),
            "identifiable": bool(support_row.leader_identifiable),
            "ambiguity": support_row.ambiguity,
            "prior_sensitive": bool(support_row.prior_sensitive),
            "support_state": support_row.support_state,
            "unknown_fault_model": "NOT_IMPLEMENTED",
            "non_identifiable_against": sorted(
                support_row.non_identifiable_against),
        },
        "support": {
            "state": support_row.support_state,
            "leader_identifiable": bool(support_row.leader_identifiable),
            "non_identifiable_against": sorted(
                support_row.non_identifiable_against),
            "discriminating_evidence": {k: int(v) for k, v in sorted(
                disc.items())},
        },
        "ambiguity": support_row.ambiguity,
        "evidence": {
            "fresh": {k: bool(v) for k, v in sorted(fresh.items())},
            "missing_reason": dict(sorted((missing_reason or {}).items())),
            "current_valid": current_valid,
            "active_relations": sorted(active_relations),
            "suppressed_relations": sorted(suppressed_relations),
            "suppression_reasons": dict(sorted(suppression_reasons.items())),
            "active_evidence_count": int(support_row.active_terms),
        },
        "function_eligibility": elig,
        "recommendations": list(advisory.recommend(
            {n: v.state for n, v in verdicts.items()},
            int(FailsafeLevel[level]))),
        "provenance_summary": {
            "software_sha": provenance["software_sha"],
            "configuration_hash": provenance["configuration_hash"],
            "input_trace_hash": provenance.get("input_trace_hash", ""),
            "trust_mode": mode.value,
            "frozen_core_tag": FROZEN_CORE_TAG,
            "authority": "READ_ONLY",
        },
    }
    if ledger_event is not None:
        payload["ledger_event"] = {
            k: ledger_event[k] for k in
            ("event_id", "event_type", "subject", "previous_state",
             "new_state", "reason_codes", "content_sha256",
             "previous_event_hash") if k in ledger_event}
    # `relation_gates` is accepted so callers pass one consistent bundle; the
    # split into active/suppressed is the caller's, computed once.
    del relation_gates
    return payload


def validate(payload: dict, path: str | None = None) -> None:
    """Raise if the payload does not match the schema."""
    import jsonschema
    jsonschema.validate(payload, schema(path))


def assert_schema_version(payload: dict, expected: str = SCHEMA_VERSION):
    """§26: a consumer either understands the version or refuses it."""
    got = payload.get("schema_version")
    if got != expected:
        raise SchemaVersionError(
            f"CSIA output schema {got!r}, consumer expects {expected!r}. "
            f"No field is reinterpreted across a version change; either "
            f"upgrade the consumer or ask for a compatibility projection.")


#: The v1 output shape, as the pre-Phase-4 consumers saw it.
V1_FIELDS = ("t", "level", "trust", "posterior", "leader")


def project_v1(payload: dict) -> dict:
    """§26: a compatibility projection for a v1 consumer.

    Only fields whose MEANING is unchanged since v1 are projected. `trust`
    carries the mode alongside it because a v1 consumer that silently received
    FLAT trajectories believing them to be v1's would be exactly the silent
    reinterpretation §26 forbids — so the projection makes the mode
    unmissable rather than dropping it.
    """
    assert_schema_version(payload)
    return {
        "t": payload["timestamp"],
        "level": payload["assurance"]["level"],
        "trust": dict(payload["trust"]["nodes"]),
        "trust_mode": payload["trust"]["mode"],
        "posterior": payload["diagnosis"]["posterior"],
        "leader": payload["diagnosis"]["leader"],
        "_v1_compat_note": (
            "projection of CSIA output schema "
            f"{payload['schema_version']}; fields added after v1 are not "
            "represented here and none is reinterpreted"),
    }


def is_legacy_trust(payload: dict) -> bool:
    return payload["trust"]["mode"] == \
        TrustMode.LEGACY_NEIGHBOR_PROPAGATION.value
