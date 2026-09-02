"""COMMUNICATION / BUS — §7.

Spec: `engineering/v2/COMMUNICATION_DOMAIN_SPEC.md`.

    Do not treat link failure as sensor failure.  (§7)

That instruction is the whole reason this domain exists, and honouring it is
structural rather than a matter of care. In v1.1 a GNSS receiver that stops
being heard becomes a stale source, and a stale source is — correctly, within
the sensor domain — evidence against the sensor. The sensor domain cannot
distinguish "the receiver died" from "the receiver is fine and the serial link
dropped", because from inside that domain the two are the same observation.

v2 can distinguish them, and only because the link is monitored SEPARATELY and
emits its own evidence. When the link reports bus-off, the candidate set
contains `COMMUNICATION/<link>`; the sensor's silence is explained by
something with adverse evidence of its own, and the cross-domain relation
`comm_sensor.link_vs_source` records that the sensor is downstream of it.

TRANSPORT-AGNOSTIC BY CONSTRUCTION — §§7, 25
--------------------------------------------
UART, CAN/CAN-FD, MAVLink, Ethernet, DDS and SPI/I2C differ in what telemetry
they expose, not in what assurance question is being asked. So `LinkSpec`
carries a free-text `transport` for the record and the domain judges only the
signals that are present: a link that reports no CRC counter is not evaluated
for CRC, and says so. Nothing here parses a protocol, and no protocol name
changes a decision — a test asserts that the verdicts are identical when the
transport label changes.

SEQUENCE GAPS ARE A RATE-INDEPENDENT MEASURE
--------------------------------------------
A link can hold its nominal message rate while dropping every third message,
if the sender retries, and it can drop below rate with no loss at all if the
sender legitimately has less to say. Rate and loss are therefore separate
relations with separate thresholds, and neither is derived from the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import AssuranceDomain, DomainResult, Snapshot
from ..evidence import Applicability, ObservationState

DOMAIN = "COMMUNICATION"

COMM_LINK_DOWN = "COMM_LINK_DOWN"
COMM_BUS_OFF = "COMM_BUS_OFF"
COMM_RATE_LOW = "COMM_RATE_LOW"
COMM_RATE_MARGINAL = "COMM_RATE_MARGINAL"
COMM_PACKET_LOSS = "COMM_PACKET_LOSS"
COMM_CRC_ERRORS = "COMM_CRC_ERRORS"
COMM_DUPLICATES = "COMM_DUPLICATES"
COMM_REORDERING = "COMM_REORDERING"
COMM_QUEUE_DELAY = "COMM_QUEUE_DELAY"
COMM_RECONNECTING = "COMM_RECONNECTING"
COMM_TELEMETRY_MISSING = "COMM_TELEMETRY_MISSING"

REASON_CODES = (
    COMM_LINK_DOWN, COMM_BUS_OFF, COMM_RATE_LOW, COMM_RATE_MARGINAL,
    COMM_PACKET_LOSS, COMM_CRC_ERRORS, COMM_DUPLICATES, COMM_REORDERING,
    COMM_QUEUE_DELAY, COMM_RECONNECTING, COMM_TELEMETRY_MISSING,
)


@dataclass(frozen=True)
class LinkSpec:
    """One link, with the limits its host declares for it."""

    name: str
    #: Free text, for the record only. Never branched on.
    transport: str = "unspecified"
    affected_functions: tuple = ()
    expected_rate_hz: float | None = None
    #: Fractions of the expected rate at which the link is called marginal
    #: and failed. A telemetry link at 60% of nominal is still carrying
    #: telemetry; one at 10% is not.
    rate_warn_frac: float = 0.80
    rate_fail_frac: float = 0.50
    #: Loss is a fraction in [0, 1] over whatever window the host measured.
    loss_warn: float | None = None
    loss_fail: float | None = None
    crc_error_limit: int | None = None
    queue_delay_warn_s: float | None = None
    queue_delay_fail_s: float | None = None
    #: What rides on this link. §22: structure, so a silent sensor can be
    #: connected to a dead link without inferring a correlation.
    carries: tuple = ()
    depends_on: tuple = ()


class CommunicationAssuranceDomain(AssuranceDomain):
    domain_id = DOMAIN
    schema_version = "2.0.0"
    required_inputs = ("COMMUNICATION/<link>/link_up",)
    optional_inputs = ("observed_rate_hz", "sequence_gaps", "messages_expected",
                       "messages_received", "loss_frac", "duplicates",
                       "reordered", "crc_errors", "bus_off", "reconnects",
                       "queue_delay_s")
    relations = ("comm.link_state", "comm.rate", "comm.loss",
                 "comm.integrity", "comm.ordering", "comm.queue")
    reason_codes = REASON_CODES

    def __init__(self, links=(), affected_functions=("TELEMETRY",)):
        self.links = tuple(links)
        self.affected_functions = tuple(affected_functions)

    def _fns(self, spec: LinkSpec) -> tuple:
        return tuple(spec.affected_functions) or self.affected_functions

    # ------------------------------------------------------------------
    def evaluate(self, snapshot: Snapshot) -> DomainResult:
        records, unevaluated = [], {}
        for spec in self.links:
            sig = snapshot.component(DOMAIN, spec.name)
            fns = self._fns(spec)
            if not sig:
                records.append(self._record(
                    component=spec.name, relation="comm.link_state",
                    observation_state=ObservationState.UNAVAILABLE,
                    applicability=Applicability.INPUTS_MISSING,
                    affected_functions=fns,
                    reason_codes=(COMM_TELEMETRY_MISSING,),
                    timestamp_processed=snapshot.t,
                    dependencies=spec.depends_on,
                    expected_relation="declared link reports its state",
                    detail={"transport": spec.transport,
                            "carries": list(spec.carries)}))
                unevaluated[spec.name] = "declared link absent from snapshot"
                continue
            records.extend(self._link(spec, sig, fns, snapshot, unevaluated))
        return DomainResult(domain=DOMAIN, records=tuple(records),
                            unevaluated=unevaluated)

    # ------------------------------------------------------------------
    def _link(self, spec, sig, fns, snapshot, unevaluated) -> list:
        out, t = [], snapshot.t
        up = sig.get("link_up")
        bus_off = bool(sig.get("bus_off", False))
        reconnects = sig.get("reconnects") or 0

        state, codes = ObservationState.NOMINAL, []
        if bus_off:
            state, codes = ObservationState.VIOLATED, [COMM_BUS_OFF]
        elif up is False:
            state, codes = ObservationState.VIOLATED, [COMM_LINK_DOWN]
        elif up is None:
            state, codes = (ObservationState.UNAVAILABLE,
                            [COMM_TELEMETRY_MISSING])
        elif reconnects:
            state, codes = ObservationState.DEGRADED, [COMM_RECONNECTING]
        out.append(self._record(
            component=spec.name, relation="comm.link_state",
            observation_state=state, applicability=Applicability.APPLICABLE,
            affected_functions=fns, reason_codes=tuple(codes),
            timestamp_processed=t, dependencies=spec.depends_on,
            expected_relation="link up and not in bus-off",
            detail={"transport": spec.transport, "link_up": up,
                    "bus_off": bus_off, "reconnects": reconnects,
                    "carries": list(spec.carries)}))

        # A down link cannot also be judged on its rate: zero messages over a
        # dead link is the SAME finding reported twice, and double-reporting
        # it would make one fault look like several.
        if state is ObservationState.VIOLATED:
            unevaluated[spec.name] = (
                "link down or bus-off; rate, loss and integrity not "
                "separately judged")
            return out

        # -- rate --------------------------------------------------------
        rate = _f(sig.get("observed_rate_hz"))
        if rate is None or spec.expected_rate_hz is None:
            unevaluated[f"{spec.name}.rate"] = (
                "needs observed_rate_hz and a declared expected_rate_hz")
        else:
            frac = rate / spec.expected_rate_hz if spec.expected_rate_hz \
                else 0.0
            if frac < spec.rate_fail_frac:
                rs, rc = ObservationState.VIOLATED, (COMM_RATE_LOW,)
            elif frac < spec.rate_warn_frac:
                rs, rc = ObservationState.DEGRADED, (COMM_RATE_MARGINAL,)
            else:
                rs, rc = ObservationState.NOMINAL, ()
            out.append(self._record(
                component=spec.name, relation="comm.rate",
                observation_state=rs, applicability=Applicability.APPLICABLE,
                affected_functions=fns, reason_codes=rc,
                measured_value=rate, expected_value=spec.expected_rate_hz,
                residual=rate - spec.expected_rate_hz,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="observed rate within its declared "
                                  "fraction of nominal",
                detail={"rate_frac": round(frac, 6),
                        "transport": spec.transport}))

        # -- loss, measured independently of rate ------------------------
        loss = _f(sig.get("loss_frac"))
        if loss is None:
            gaps = sig.get("sequence_gaps")
            expected = _f(sig.get("messages_expected"))
            if gaps is not None and expected:
                loss = float(gaps) / expected
        if loss is None or spec.loss_fail is None:
            unevaluated[f"{spec.name}.loss"] = (
                "needs loss_frac (or sequence_gaps + messages_expected) and "
                "a declared loss_fail")
        else:
            warn = spec.loss_warn if spec.loss_warn is not None \
                else spec.loss_fail
            if loss > spec.loss_fail:
                ls, lc = ObservationState.VIOLATED, (COMM_PACKET_LOSS,)
            elif loss > warn:
                ls, lc = ObservationState.DEGRADED, (COMM_PACKET_LOSS,)
            else:
                ls, lc = ObservationState.NOMINAL, ()
            out.append(self._record(
                component=spec.name, relation="comm.loss",
                observation_state=ls, applicability=Applicability.APPLICABLE,
                affected_functions=fns, reason_codes=lc,
                measured_value=loss, expected_value=spec.loss_fail,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="loss fraction within declared limit",
                detail={"warn": warn,
                        "sequence_gaps": sig.get("sequence_gaps")}))

        # -- integrity ---------------------------------------------------
        crc = sig.get("crc_errors")
        if crc is None or spec.crc_error_limit is None:
            unevaluated[f"{spec.name}.integrity"] = (
                "needs crc_errors and a declared crc_error_limit")
        else:
            bad = int(crc) > spec.crc_error_limit
            out.append(self._record(
                component=spec.name, relation="comm.integrity",
                observation_state=(ObservationState.DEGRADED if bad
                                   else ObservationState.NOMINAL),
                applicability=Applicability.APPLICABLE,
                affected_functions=fns if bad else (),
                reason_codes=(COMM_CRC_ERRORS,) if bad else (),
                measured_value=float(crc),
                expected_value=float(spec.crc_error_limit),
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="CRC errors within declared limit"))

        # -- ordering ----------------------------------------------------
        dups, reord = sig.get("duplicates"), sig.get("reordered")
        if dups is None and reord is None:
            unevaluated[f"{spec.name}.ordering"] = (
                "no duplicates or reordered counters")
        else:
            codes = []
            if dups:
                codes.append(COMM_DUPLICATES)
            if reord:
                codes.append(COMM_REORDERING)
            out.append(self._record(
                component=spec.name, relation="comm.ordering",
                observation_state=(ObservationState.DEGRADED if codes
                                   else ObservationState.NOMINAL),
                applicability=Applicability.APPLICABLE,
                affected_functions=fns if codes else (),
                reason_codes=tuple(codes), timestamp_processed=t,
                dependencies=spec.depends_on,
                expected_relation="no duplicated or reordered messages",
                detail={"duplicates": dups, "reordered": reord}))

        # -- queue delay -------------------------------------------------
        qd = _f(sig.get("queue_delay_s"))
        if qd is None or spec.queue_delay_fail_s is None:
            unevaluated[f"{spec.name}.queue"] = (
                "needs queue_delay_s and a declared queue_delay_fail_s")
        else:
            warn = (spec.queue_delay_warn_s
                    if spec.queue_delay_warn_s is not None
                    else spec.queue_delay_fail_s)
            if qd > spec.queue_delay_fail_s:
                qs, qc = ObservationState.VIOLATED, (COMM_QUEUE_DELAY,)
            elif qd > warn:
                qs, qc = ObservationState.DEGRADED, (COMM_QUEUE_DELAY,)
            else:
                qs, qc = ObservationState.NOMINAL, ()
            out.append(self._record(
                component=spec.name, relation="comm.queue",
                observation_state=qs, applicability=Applicability.APPLICABLE,
                affected_functions=fns, reason_codes=qc,
                measured_value=qd, expected_value=spec.queue_delay_fail_s,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="transmit queue delay within limit",
                detail={"warn_s": warn}))
        return out

    def declaration(self) -> dict:
        d = super().declaration()
        covered = set(self.affected_functions)
        for link in self.links:
            covered.update(self._fns(link))
        d["affected_functions"] = sorted(covered)
        d["links"] = [{"name": link.name, "transport": link.transport,
                       "carries": list(link.carries),
                       "affected_functions": list(self._fns(link)),
                       "depends_on": list(link.depends_on)}
                      for link in self.links]
        return d


def _f(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
