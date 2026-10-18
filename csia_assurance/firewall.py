"""The assurance firewall: does the evidence support the asserted attribution?

THE PIPELINE, AND WHERE THIS SITS IN IT

    canonical evidence -> FROZEN CSIA CORE -> ranking / trust
                                                    |
                                                    v
                                          ASSURANCE FIREWALL   <- here
                                                    |
                                                    v
                                          qualified assurance

THE ONE RULE
------------
For the leader h*, and for EVERY other hypothesis h_j the model admits, there
must be at least one ACTIVE discriminating witness separating h* from h_j.
If any competitor has none, the attribution is not evidence-supported --
however large the score was.

    CSIA:      leader = nominal, weight = 0.9999
    firewall:  compatible = {nominal, gps_fault} -> NON_IDENTIFIABLE

That is a LEGAL AND EXPECTED outcome, not a defect in either layer. A large
score shall not force support. The score is a ranking over a model; support is
a statement about the evidence held.

FAIL CLOSED, ALWAYS
-------------------
Eleven named conditions produce NOT_EVALUABLE with an explicit reason rather
than any positive verdict, and a final exception barrier catches everything
else. Two shapes are specifically forbidden and each has its own test:

    exception  -> nominal                            NEVER
    exception  -> the previous certificate stays valid forever   NEVER

WHAT THIS IS NOT
----------------
Not a safety case, not a certification artifact, not validated by anyone
outside this repository. `witness.py` names its output an EXPERIMENTAL
SUPPORT CERTIFICATE for that reason.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

# The clean-room structural reference: standard library only, written from the
# definition rather than from the production implementation. Loaded by path so
# that this package depends on no repository package at all -- see
# `tests/test_assurance_independence.py`, which asserts the import set.
_REF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "research", "physical_validation", "cleanroom")
if _REF_DIR not in sys.path:
    sys.path.insert(0, _REF_DIR)
import structural_reference as _ref  # noqa: E402

SUPPORTED_UNIQUE = "SUPPORTED_UNIQUE"
AMBIGUOUS = "AMBIGUOUS"
NON_IDENTIFIABLE = "NON_IDENTIFIABLE"
NOT_EVALUABLE = "NOT_EVALUABLE"
UNKNOWN = "UNKNOWN"

VERDICTS = (SUPPORTED_UNIQUE, AMBIGUOUS, NON_IDENTIFIABLE, NOT_EVALUABLE,
            UNKNOWN)

#: The states in which a positive verdict may never be emitted. Named, so a
#: reader can check the list against the contract rather than reading code.
FAIL_CLOSED_REASONS = (
    "MISSING_CANONICAL_SAMPLE",
    "UNKNOWN_CONFIGURATION",
    "CONFIG_HASH_MISMATCH",
    "STALE_SUPPORT_CERTIFICATE",
    "HYPOTHESIS_SET_CHANGED",
    "EVIDENCE_TOPOLOGY_CHANGED",
    "TIMESTAMP_REGRESSION",
    "UNKNOWN_EVIDENCE_STATE",
    "INVALID_GATE_STATE",
    "UNSUPPORTED_SCHEMA_VERSION",
    "FIREWALL_INTERNAL_EXCEPTION",
)

#: The input schema this evaluator understands. An input declaring anything
#: else is UNSUPPORTED_SCHEMA_VERSION -- not "probably compatible".
SCHEMA = "csia.assurance.input/1"

#: Gate weights outside this are not "unusual", they are uninterpretable.
_GATE_MIN, _GATE_MAX = 0.0, 1.0


@dataclass(frozen=True)
class AssuranceVerdict:
    """The firewall's output. `state` is one of VERDICTS."""
    state: str
    reason: str
    leader: str | None = None
    competitors_without_witness: tuple = ()
    witnesses: Mapping[str, tuple] = field(default_factory=dict)
    active_evidence: tuple = ()
    hypothesis_set: tuple = ()
    schema: str = SCHEMA
    inputs_digest: str | None = None

    @property
    def supported(self) -> bool:
        return self.state == SUPPORTED_UNIQUE

    def to_dict(self) -> dict:
        d = asdict(self)
        d["witnesses"] = {k: list(v) for k, v in self.witnesses.items()}
        for k in ("competitors_without_witness", "active_evidence",
                  "hypothesis_set"):
            d[k] = list(d[k])
        return d


def _fail(reason: str, **kw) -> AssuranceVerdict:
    return AssuranceVerdict(state=NOT_EVALUABLE, reason=reason, **kw)


def _check_contract(rec: Mapping[str, Any], prior: Mapping | None):
    """Every fail-closed condition, in one place, returning a reason or None.

    Ordered so the cheapest structural checks run first; the order does not
    change any verdict, because any single hit is decisive.
    """
    if rec.get("schema") != SCHEMA:
        return "UNSUPPORTED_SCHEMA_VERSION"

    if not rec.get("canonical_sample_present", False):
        return "MISSING_CANONICAL_SAMPLE"

    cfg = rec.get("config_hash")
    if not cfg or not isinstance(cfg, str):
        return "UNKNOWN_CONFIGURATION"

    sigs = rec.get("signatures")
    if not isinstance(sigs, Mapping) or not sigs:
        return "UNKNOWN_CONFIGURATION"

    gates = rec.get("gates")
    if not isinstance(gates, Mapping):
        return "INVALID_GATE_STATE"
    for name, value in gates.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "INVALID_GATE_STATE"
        # NaN is the case a bare range check misses: NaN fails every
        # comparison, so `not (lo <= v <= hi)` is the only form that catches
        # it. Written this way on purpose.
        if not (_GATE_MIN <= float(value) <= _GATE_MAX):
            return "INVALID_GATE_STATE"
        # SUBNORMAL GATE WEIGHTS ARE REFUSED, and this is a VALIDITY rule,
        # not a threshold.
        #
        # Found by the hostile-input campaign: a gate of 5e-324 -- the
        # smallest positive double -- is strictly greater than zero, so it
        # counted as ACTIVE and licensed SUPPORTED_UNIQUE off a quantity
        # numerically indistinguishable from nothing. The minimized
        # reproducer is two hypotheses, one relation, that weight.
        #
        # The tempting fix is a tolerance in the activity test. That is
        # exactly what the clean-room reference refuses to have -- "a
        # tolerance here would be a threshold, and a threshold is the thing
        # this reference exists not to have" -- and adding one would put a
        # tunable number inside the layer whose value is that it has none.
        #
        # So the rejection goes HERE instead, with the other malformed-value
        # rejections. A subnormal weight cannot arise from any computation
        # this pipeline performs; it is a symptom of numerical corruption,
        # and "I cannot interpret this input" is the honest answer. The
        # activity test stays `v > 0`, unchanged.
        f = float(value)
        if f != 0.0 and abs(f) < sys.float_info.min:
            return "INVALID_GATE_STATE"

    states = rec.get("evidence_states") or {}
    if not isinstance(states, Mapping):
        return "UNKNOWN_EVIDENCE_STATE"
    known = {"ACTIVE", "INACTIVE", "INAPPLICABLE", "STALE", "ABSENT"}
    for name, st in states.items():
        if st not in known:
            return "UNKNOWN_EVIDENCE_STATE"

    ts = rec.get("timestamp")
    if ts is None or isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return "UNKNOWN_EVIDENCE_STATE"

    if prior is not None:
        if prior.get("config_hash") != cfg:
            return "CONFIG_HASH_MISMATCH"
        if prior.get("software_hash") != rec.get("software_hash"):
            return "CONFIG_HASH_MISMATCH"
        prior_ts = prior.get("timestamp")
        if isinstance(prior_ts, (int, float)) and ts < prior_ts:
            return "TIMESTAMP_REGRESSION"
        if (prior.get("hypothesis_set") is not None
                and sorted(prior["hypothesis_set"]) != sorted(sigs)):
            return "HYPOTHESIS_SET_CHANGED"
        if (prior.get("evidence_topology") is not None
                and sorted(prior["evidence_topology"]) != sorted(gates)):
            return "EVIDENCE_TOPOLOGY_CHANGED"
        expiry = prior.get("valid_until")
        if isinstance(expiry, (int, float)) and ts > expiry:
            return "STALE_SUPPORT_CERTIFICATE"
    return None


def _active_gates(rec: Mapping[str, Any]) -> dict:
    """Gate weight, further masked by the declared evidence state.

    A gate can carry weight while its evidence is STALE or INAPPLICABLE. The
    weight alone is therefore NOT sufficient to call a term active, and
    treating it as sufficient is the exact shape of the defect this whole
    programme is about.
    """
    states = rec.get("evidence_states") or {}
    out = {}
    for name, weight in (rec.get("gates") or {}).items():
        st = states.get(name, "ACTIVE")
        out[name] = float(weight) if st == "ACTIVE" else 0.0
    return out


def qualify(record: Mapping[str, Any],
            prior: Mapping[str, Any] | None = None) -> AssuranceVerdict:
    """Qualify one decision. Never raises: an exception is a NOT_EVALUABLE.

    `record` is a plain mapping -- deliberately not a CSIA object, so this
    layer never touches production types:

        schema, timestamp, config_hash, software_hash,
        canonical_sample_present, leader,
        signatures        {hypothesis: [feature expected LOW under it]}
        gates             {feature: weight in [0,1]}
        evidence_states   {feature: ACTIVE|INACTIVE|INAPPLICABLE|STALE|ABSENT}

    `prior`, when given, is the previous accepted record; it is what makes
    configuration change, topology change, timestamp regression and
    certificate expiry detectable at all.
    """
    try:
        reason = _check_contract(record, prior)
        if reason:
            return _fail(reason)

        sigs = {k: list(v) for k, v in record["signatures"].items()}
        leader = record.get("leader")
        if leader is None:
            return AssuranceVerdict(
                state=UNKNOWN,
                reason="NO_LEADER_ASSERTED",
                hypothesis_set=tuple(sorted(sigs)))
        if leader not in sigs:
            return _fail("HYPOTHESIS_SET_CHANGED",
                         hypothesis_set=tuple(sorted(sigs)))

        active = _active_gates(record)
        active_names = tuple(sorted(k for k, v in active.items() if v > 0))

        if len(sigs) < 2:
            return _fail("SINGLE_HYPOTHESIS_MODEL",
                         leader=leader,
                         hypothesis_set=tuple(sorted(sigs)),
                         active_evidence=active_names)

        wit = _ref.support_witnesses(leader, sigs, active)
        witnesses = {k: tuple(sorted(v)) for k, v in wit.items()}
        empty = tuple(sorted(k for k, v in witnesses.items() if not v))

        if not empty:
            state, why = SUPPORTED_UNIQUE, "ACTIVE_WITNESS_AGAINST_EVERY_COMPETITOR"
        elif len(empty) == len(witnesses):
            state, why = NON_IDENTIFIABLE, "NO_ACTIVE_WITNESS_AGAINST_ANY_COMPETITOR"
        else:
            state, why = AMBIGUOUS, "NO_ACTIVE_WITNESS_AGAINST_SOME_COMPETITORS"

        return AssuranceVerdict(
            state=state, reason=why, leader=leader,
            competitors_without_witness=empty,
            witnesses=witnesses,
            active_evidence=active_names,
            hypothesis_set=tuple(sorted(sigs)),
            inputs_digest=record.get("evidence_hash"))

    except Exception as exc:                    # noqa: BLE001
        # THE BARRIER. Any escape becomes NOT_EVALUABLE with the exception
        # named -- never a positive verdict, never a silent fallback to the
        # leader, and never "keep the previous certificate".
        return AssuranceVerdict(
            state=NOT_EVALUABLE,
            reason=f"FIREWALL_INTERNAL_EXCEPTION: "
                   f"{type(exc).__name__}: {exc}")
