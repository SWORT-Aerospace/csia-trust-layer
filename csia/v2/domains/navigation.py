"""v1.1 as a domain plugin — §§19, 20, 36.

Spec: `engineering/v2/V1_1_NAVIGATION_PLUGIN_SPEC.md`.

    Do NOT rewrite v1.1 logic.  (§20)
    The plugin layer may not alter assurance state, function eligibility,
    support or diagnosis.  (§36)

So this module **consumes the published v1.1 output payload** — schema 1.1.0,
the same artifact `csia-monitor` reads — and transcribes it. It imports no
v1.1 producer: not the trust engine, not the diagnosis, not the eligibility
policy. It cannot alter a v1.1 verdict because it has no way to compute one.

HOW §36 IS MADE STRUCTURAL RATHER THAN PROMISED
----------------------------------------------
The transcription is a bijection. v1.1's four eligibility states map onto
four `ObservationState` values, and the function roll-up maps them straight
back:

    ELIGIBLE   <-> NOMINAL        DEGRADED   <-> DEGRADED
    INELIGIBLE <-> VIOLATED       UNKNOWN    <-> UNAVAILABLE

A v1.1 function's `required_domains` is `("SENSOR",)` and nothing else, so
nothing outside v1.1 can move it. **Per-node health records deliberately
carry `affected_functions = ()`**: they are evidence for cross-domain
attribution, and if they were attached to a v1.1 function they could degrade
a function v1.1 had called eligible — which is exactly the alteration §36
forbids.

The domain-level SENSOR state is a v2 concept and *may* be worse than any
individual v1.1 function. That is not an alteration: it is a new statement,
about the domain rather than about a v1.1 function.
"""

from __future__ import annotations

from ...v1_1.monitor import PayloadRejected, parse
from ..domain import AssuranceDomain, DomainResult, Snapshot
from ..evidence import Applicability, ObservationState

#: v1.1 eligibility state -> the categorical verdict. A bijection, and a test
#: asserts it round-trips through the function roll-up.
_STATE = {
    "ELIGIBLE": ObservationState.NOMINAL,
    "DEGRADED": ObservationState.DEGRADED,
    "INELIGIBLE": ObservationState.VIOLATED,
    "UNKNOWN": ObservationState.UNAVAILABLE,
}


class NavigationAssuranceDomain(AssuranceDomain):
    """Wraps v1.1's published output. Computes no v1.1 quantity itself."""

    domain_id = "SENSOR"
    schema_version = "2.0.0"
    required_inputs = ("v1_1_payload",)
    optional_inputs = ()
    relations = ("v1_1.function_eligibility", "v1_1.source_health",
                 "v1_1.support", "v1_1.sequential", "sensor.aggregate")
    reason_codes = ("V1_1_PAYLOAD_MISSING", "V1_1_PAYLOAD_REJECTED",
                    "V1_1_FUNCTION_NOT_ELIGIBLE", "SOURCE_NOT_FRESH",
                    "SOURCE_TRUST_LOW", "SUPPORT_NOT_IDENTIFIABLE",
                    "SEQUENTIAL_ALARM")

    def __init__(self, affected_functions=(), trust_floor: float | None = None,
                 source_dependencies=None):
        #: v2 cross-domain functions this domain's AGGREGATE health bears on.
        #: The v1.1 functions are discovered from the payload and are handled
        #: separately, so they cannot be altered from here.
        self.affected_functions = tuple(affected_functions) or ("SENSING",)
        #: Optional, and NOT a new threshold when left as None. A host that
        #: wants a trust floor states one; the plugin does not invent one,
        #: because v1.1's own thresholds already decided its functions.
        self.trust_floor = trust_floor
        #: §22, and what §28 Scenario E needs: `{node: ("POWER/rail_5v", ...)}`
        #: — which rail, bus or converter each source hangs off. This is
        #: PLATFORM WIRING, so the host declares it; v1.1 does not know it and
        #: nothing here infers it. Two sensors sharing an entry is a
        #: structural fact about the harness, not a correlation estimate.
        self.source_dependencies = dict(source_dependencies or {})

    # ------------------------------------------------------------------
    def evaluate(self, snapshot: Snapshot) -> DomainResult:
        payload = snapshot.v1_1_payload
        if payload is None:
            return DomainResult(
                domain=self.domain_id,
                records=(self._record(
                    component="v1_1", relation="v1_1.function_eligibility",
                    observation_state=ObservationState.UNAVAILABLE,
                    applicability=Applicability.INPUTS_MISSING,
                    affected_functions=self.affected_functions,
                    reason_codes=("V1_1_PAYLOAD_MISSING",),
                    timestamp_processed=snapshot.t),),
                unevaluated={"v1_1": "no payload in snapshot"})

        try:
            view = parse(payload)
        except PayloadRejected as exc:
            return DomainResult(
                domain=self.domain_id,
                records=(self._record(
                    component="v1_1", relation="v1_1.function_eligibility",
                    observation_state=ObservationState.UNAVAILABLE,
                    applicability=Applicability.INPUTS_MISSING,
                    affected_functions=self.affected_functions,
                    reason_codes=("V1_1_PAYLOAD_REJECTED",),
                    timestamp_processed=snapshot.t,
                    detail={"error": str(exc)[:200]}),),
                unevaluated={"v1_1": f"payload rejected: {str(exc)[:120]}"})

        records = []
        t_valid = float(view.timestamp)

        # -- 1. v1.1 function eligibility, TRANSCRIBED -------------------
        for name, state in sorted(view.function_eligibility.items()):
            records.append(self._record(
                component=f"v1_1.{name}",
                relation="v1_1.function_eligibility",
                observation_state=_STATE[state],
                applicability=Applicability.APPLICABLE,
                affected_functions=(name,),
                reason_codes=tuple(view.function_reasons.get(name, ())),
                timestamp_validity=t_valid, timestamp_processed=snapshot.t,
                expected_relation="v1.1 eligibility, unmodified",
                # A function verdict is a conclusion, not a component that
                # can fail. It is evidence; it is not an answer to "what
                # broke", and the sources it was computed from are already
                # candidates in their own right.
                attributable=False,
                provenance={"schema_version": payload["schema_version"],
                            "trust_mode": payload["trust"]["mode"]},
                detail={"v1_1_state": state}))

        # -- 2. per-node source health. NOT attached to a v1.1 function --
        fresh = payload["evidence"]["fresh"]
        alarming = set(payload["sequential"].get("alarming", ()))
        for node in sorted(view.trust):
            trust = float(view.trust[node])
            is_fresh = bool(fresh.get(node, False))
            codes, state = [], ObservationState.NOMINAL
            if not is_fresh:
                state, _ = ObservationState.VIOLATED, codes.append(
                    "SOURCE_NOT_FRESH")
            elif node in alarming:
                state, _ = ObservationState.DEGRADED, codes.append(
                    "SEQUENTIAL_ALARM")
            elif self.trust_floor is not None and trust < self.trust_floor:
                state, _ = ObservationState.DEGRADED, codes.append(
                    "SOURCE_TRUST_LOW")
            records.append(self._record(
                component=f"source.{node}", relation="v1_1.source_health",
                observation_state=state,
                applicability=Applicability.APPLICABLE,
                affected_functions=(),          # §36: cannot move a v1.1 fn
                reason_codes=tuple(codes),
                dependencies=tuple(self.source_dependencies.get(node, ())),
                measured_value=trust,
                timestamp_validity=t_valid, timestamp_processed=snapshot.t,
                expected_relation="v1.1 trust and freshness for this source",
                detail={"fresh": is_fresh,
                        "missing_reason":
                            payload["evidence"].get("missing_reason", {})
                            .get(node)}))

        # -- 3. support / diagnosis, transcribed -------------------------
        diag = payload["diagnosis"]
        supported = bool(diag["identifiable"])
        records.append(self._record(
            component="v1_1.diagnosis", relation="v1_1.support",
            observation_state=(ObservationState.NOMINAL if supported
                               else ObservationState.DEGRADED),
            applicability=Applicability.APPLICABLE,
            affected_functions=(),
            reason_codes=() if supported else ("SUPPORT_NOT_IDENTIFIABLE",),
            measured_value=float(diag["posterior"]),
            timestamp_validity=t_valid, timestamp_processed=snapshot.t,
            expected_relation="v1.1 leader identifiable against every "
                              "modeled competitor",
            attributable=False,
            detail={"leader": diag["leader"],
                    "support_state": diag["support_state"],
                    "ambiguity": diag["ambiguity"],
                    "discriminating_evidence_count":
                        diag["discriminating_evidence_count"],
                    "unknown_fault_model": diag.get("unknown_fault_model")}))

        # -- 4. the aggregate, which IS allowed to reach v2 functions ----
        health = [r for r in records if r.relation == "v1_1.source_health"]
        agg = max((r.observation_state for r in health),
                  key=lambda s: {ObservationState.NOMINAL: 0,
                                 ObservationState.NOT_APPLICABLE: 0,
                                 ObservationState.DEGRADED: 1,
                                 ObservationState.VIOLATED: 2,
                                 ObservationState.UNAVAILABLE: 3}[s],
                  default=ObservationState.UNAVAILABLE)
        records.append(self._record(
            component="sensor.aggregate", relation="sensor.aggregate",
            observation_state=agg,
            applicability=Applicability.APPLICABLE,
            affected_functions=self.affected_functions,
            reason_codes=tuple(dict.fromkeys(
                c for r in health for c in r.reason_codes)),
            timestamp_validity=t_valid, timestamp_processed=snapshot.t,
            expected_relation="worst source health across the v1.1 nodes",
            attributable=False,
            detail={"nodes": len(health)}))

        return DomainResult(domain=self.domain_id, records=tuple(records))

    # ------------------------------------------------------------------
    def declaration(self) -> dict:
        d = super().declaration()
        d["affected_functions"] = list(self.affected_functions)
        d["source_dependencies"] = {k: list(v) for k, v in
                                    sorted(self.source_dependencies.items())}
        d["note"] = ("consumes csia_output_v1_1 schema 1.1.0; imports no "
                     "v1.1 producer and computes no v1.1 quantity")
        return d
