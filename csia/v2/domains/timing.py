"""TIMING ASSURANCE — §6. "Make time first-class."

Spec: `engineering/v2/TIMING_DOMAIN_SPEC.md`.

WHY THIS IS A DOMAIN AND NOT A FIELD
------------------------------------
v1.1 already has a staleness watchdog, and it answers one question: is this
sample too old to use? That is a threshold on a single age, and it is the
right question for the trust engine. It cannot answer the question §6 asks:

    the value is late — WHERE did the time go?

Four stamps make that answerable, and one does not:

    t_validity   when the world was actually sampled
    t_arrival    when the bytes reached us
    t_processed  when we finished computing on them
    t_decision   when the result was available to act on

The differences between consecutive stamps partition the total delay into
segments that belong to different owners:

    SENSOR_SLOW       the source sampled late          (validity interval)
    TRANSPORT_DELAY   arrival - validity
    PROCESSING_DELAY  processed - arrival
    DECISION_DELAY    decision - processed

A single `age` field is the sum of all four and identifies none of them. That
is the entire argument for this module: the same 60 ms of lateness sends you
to the sensor, the network, the CPU or the scheduler, and a monitor that
cannot say which has not helped.

BUDGETS ARE DECLARED, NOT LEARNED
---------------------------------
Each channel declares a budget per segment plus an end-to-end deadline. The
segment classification names the segments that **exceeded their own budget**,
not merely the largest one: the largest segment of a perfectly acceptable
total is not a finding, and reporting it as one trains an operator to ignore
the domain.

CLOCK CONSISTENCY
-----------------
A stamp ordering that cannot happen physically — arrival before validity,
processing before arrival — is reported as VIOLATED with
`TIMING_CLOCK_INCONSISTENT` rather than as a negative latency. Negative
latencies get averaged into fake headroom; this is the CLOCK_DRIFT scenario
of §27, and it is a fault in the timebase, not in the channel.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import AssuranceDomain, DomainResult, Snapshot
from ..evidence import Applicability, ObservationState

DOMAIN = "TIMING"

SENSOR_SLOW = "SENSOR_SLOW"
TRANSPORT_DELAY = "TRANSPORT_DELAY"
PROCESSING_DELAY = "PROCESSING_DELAY"
DECISION_DELAY = "DECISION_DELAY"
#: §6's four classes, in the order the delay is incurred.
SEGMENTS = (SENSOR_SLOW, TRANSPORT_DELAY, PROCESSING_DELAY, DECISION_DELAY)

TIMING_SEGMENT_OVER_BUDGET = "TIMING_SEGMENT_OVER_BUDGET"
TIMING_SEGMENT_MARGINAL = "TIMING_SEGMENT_MARGINAL"
TIMING_DEADLINE_MISSED = "TIMING_DEADLINE_MISSED"
TIMING_DEADLINE_MARGINAL = "TIMING_DEADLINE_MARGINAL"
TIMING_JITTER_EXCESSIVE = "TIMING_JITTER_EXCESSIVE"
TIMING_RATE_LOW = "TIMING_RATE_LOW"
TIMING_CLOCK_INCONSISTENT = "TIMING_CLOCK_INCONSISTENT"
TIMING_STAMPS_MISSING = "TIMING_STAMPS_MISSING"

REASON_CODES = (
    TIMING_SEGMENT_OVER_BUDGET, TIMING_SEGMENT_MARGINAL,
    TIMING_DEADLINE_MISSED, TIMING_DEADLINE_MARGINAL,
    TIMING_JITTER_EXCESSIVE, TIMING_RATE_LOW, TIMING_CLOCK_INCONSISTENT,
    TIMING_STAMPS_MISSING,
)

#: Which stamp pair each segment is measured across, and the reason a missing
#: stamp makes it unmeasurable rather than zero.
_SEGMENT_STAMPS = {
    TRANSPORT_DELAY: ("t_validity", "t_arrival"),
    PROCESSING_DELAY: ("t_arrival", "t_processed"),
    DECISION_DELAY: ("t_processed", "t_decision"),
}


@dataclass(frozen=True)
class ChannelSpec:
    """One timed path through the system, with its declared budgets.

    A budget of `None` means the host has not stated one, and the segment is
    then measured and reported but not judged. Measuring without judging is
    useful — the number appears in the ledger and in any later analysis —
    and it is honest in a way that a default budget is not.
    """

    name: str
    affected_functions: tuple = ()
    transport_budget_s: float | None = None
    processing_budget_s: float | None = None
    decision_budget_s: float | None = None
    #: End-to-end requirement: t_decision (or t_processed) - t_validity.
    end_to_end_deadline_s: float | None = None
    #: The source's own sampling interval. Exceeding it is SENSOR_SLOW.
    expected_period_s: float | None = None
    period_tolerance_frac: float = 0.50
    jitter_limit_s: float | None = None
    #: Fraction of a budget at which a segment is called marginal.
    warn_frac: float = 0.80
    depends_on: tuple = ()


class TimingAssuranceDomain(AssuranceDomain):
    domain_id = DOMAIN
    schema_version = "2.0.0"
    required_inputs = ("TIMING/<channel>/t_validity",)
    optional_inputs = ("t_arrival", "t_processed", "t_decision",
                       "interval_s", "jitter_s")
    relations = ("timing.clock_consistency", "timing.segment_budget",
                 "timing.end_to_end", "timing.rate", "timing.jitter")
    reason_codes = REASON_CODES

    def __init__(self, channels=(), affected_functions=("TIMELINESS",)):
        self.channels = tuple(channels)
        self.affected_functions = tuple(affected_functions)

    def _fns(self, spec: ChannelSpec) -> tuple:
        return tuple(spec.affected_functions) or self.affected_functions

    # ------------------------------------------------------------------
    def evaluate(self, snapshot: Snapshot) -> DomainResult:
        records, unevaluated = [], {}
        for spec in self.channels:
            sig = snapshot.component(DOMAIN, spec.name)
            fns = self._fns(spec)
            if not sig:
                records.append(self._record(
                    component=spec.name, relation="timing.end_to_end",
                    observation_state=ObservationState.UNAVAILABLE,
                    applicability=Applicability.INPUTS_MISSING,
                    affected_functions=fns,
                    reason_codes=(TIMING_STAMPS_MISSING,),
                    timestamp_processed=snapshot.t,
                    expected_relation="declared channel reports timestamps",
                    dependencies=spec.depends_on))
                unevaluated[spec.name] = "declared channel absent from snapshot"
                continue
            records.extend(self._channel(spec, sig, fns, snapshot,
                                         unevaluated))
        return DomainResult(domain=DOMAIN, records=tuple(records),
                            unevaluated=unevaluated)

    # ------------------------------------------------------------------
    def _channel(self, spec, sig, fns, snapshot, unevaluated) -> list:
        out, t = [], snapshot.t
        stamps = {k: _f(sig.get(k)) for k in
                  ("t_validity", "t_arrival", "t_processed", "t_decision")}

        # -- 1. clock consistency, BEFORE any latency is believed --------
        ordered = [(k, v) for k, v in stamps.items() if v is not None]
        inversions = [f"{a[0]}>{b[0]}"
                      for a, b in zip(ordered, ordered[1:]) if a[1] > b[1]]
        out.append(self._record(
            component=spec.name, relation="timing.clock_consistency",
            observation_state=(ObservationState.VIOLATED if inversions
                               else ObservationState.NOMINAL),
            applicability=Applicability.APPLICABLE,
            affected_functions=fns,
            reason_codes=(TIMING_CLOCK_INCONSISTENT,) if inversions else (),
            timestamp_validity=stamps["t_validity"],
            timestamp_arrival=stamps["t_arrival"],
            timestamp_processed=(t if stamps["t_processed"] is None
                                 else stamps["t_processed"]),
            dependencies=spec.depends_on,
            expected_relation="t_validity <= t_arrival <= t_processed "
                              "<= t_decision",
            detail={"inversions": inversions,
                    "note": "reported as a timebase fault, NOT as a negative "
                            "latency"} if inversions else {}))
        if inversions:
            # Every latency below would be arithmetic on stamps we have just
            # shown to be untrustworthy. Stop rather than publish numbers.
            unevaluated[spec.name] = (
                f"stamp ordering violated ({', '.join(inversions)}); "
                f"latencies not computed")
            return out

        budgets = {TRANSPORT_DELAY: spec.transport_budget_s,
                   PROCESSING_DELAY: spec.processing_budget_s,
                   DECISION_DELAY: spec.decision_budget_s}

        # -- 2. per-segment budgets --------------------------------------
        measured = {}
        for segment, (a, b) in _SEGMENT_STAMPS.items():
            lo, hi = stamps[a], stamps[b]
            if lo is None or hi is None:
                unevaluated[f"{spec.name}.{segment}"] = (
                    f"needs {a} and {b}")
                continue
            value = hi - lo
            measured[segment] = value
            budget = budgets[segment]
            if budget is None:
                state, codes = ObservationState.NOT_APPLICABLE, ()
            elif value > budget:
                state, codes = (ObservationState.VIOLATED,
                                (TIMING_SEGMENT_OVER_BUDGET,))
            elif value > budget * spec.warn_frac:
                state, codes = (ObservationState.DEGRADED,
                                (TIMING_SEGMENT_MARGINAL,))
            else:
                state, codes = ObservationState.NOMINAL, ()
            out.append(self._record(
                component=f"{spec.name}.{segment.lower()}",
                relation="timing.segment_budget",
                observation_state=state,
                applicability=(Applicability.NOT_APPLICABLE
                               if budget is None
                               else Applicability.APPLICABLE),
                affected_functions=fns, reason_codes=codes,
                measured_value=value, expected_value=budget,
                residual=(None if budget is None else value - budget),
                timestamp_validity=stamps["t_validity"],
                timestamp_arrival=stamps["t_arrival"],
                timestamp_processed=stamps["t_processed"],
                dependencies=spec.depends_on,
                expected_relation=f"{b} - {a} <= budget",
                detail={"segment": segment,
                        "budget_declared": budget is not None}))

        # -- 3. SENSOR_SLOW: the source's own sampling interval ----------
        interval = _f(sig.get("interval_s"))
        if spec.expected_period_s is None or interval is None:
            unevaluated[f"{spec.name}.{SENSOR_SLOW}"] = (
                "needs interval_s and a declared expected_period_s")
        else:
            limit = spec.expected_period_s * (1.0 + spec.period_tolerance_frac)
            slow = interval > limit
            measured[SENSOR_SLOW] = interval
            out.append(self._record(
                component=f"{spec.name}.{SENSOR_SLOW.lower()}",
                relation="timing.rate",
                observation_state=(ObservationState.VIOLATED if slow
                                   else ObservationState.NOMINAL),
                applicability=Applicability.APPLICABLE,
                affected_functions=fns,
                reason_codes=(TIMING_RATE_LOW,) if slow else (),
                measured_value=interval, expected_value=spec.expected_period_s,
                residual=interval - spec.expected_period_s,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation=f"sampling interval <= "
                                  f"{spec.period_tolerance_frac:+.0%} of the "
                                  f"declared period",
                detail={"segment": SENSOR_SLOW, "limit_s": limit}))

        # -- 4. jitter ---------------------------------------------------
        jitter = _f(sig.get("jitter_s"))
        if jitter is None or spec.jitter_limit_s is None:
            unevaluated[f"{spec.name}.jitter"] = (
                "needs a jitter_s signal and a declared jitter_limit_s")
        else:
            bad = jitter > spec.jitter_limit_s
            out.append(self._record(
                component=spec.name, relation="timing.jitter",
                observation_state=(ObservationState.DEGRADED if bad
                                   else ObservationState.NOMINAL),
                applicability=Applicability.APPLICABLE,
                affected_functions=fns if bad else (),
                reason_codes=(TIMING_JITTER_EXCESSIVE,) if bad else (),
                measured_value=jitter, expected_value=spec.jitter_limit_s,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="jitter within declared limit"))

        # -- 5. end-to-end, and WHICH segment spent the budget -----------
        end_stamp = (stamps["t_processed"] if stamps["t_decision"] is None
                     else stamps["t_decision"])
        if stamps["t_validity"] is None or end_stamp is None:
            unevaluated[f"{spec.name}.end_to_end"] = (
                "needs t_validity and at least t_processed")
            return out
        total = end_stamp - stamps["t_validity"]
        deadline = spec.end_to_end_deadline_s
        if deadline is None:
            state, codes = ObservationState.NOT_APPLICABLE, ()
        elif total > deadline:
            state, codes = ObservationState.VIOLATED, (TIMING_DEADLINE_MISSED,)
        elif total > deadline * spec.warn_frac:
            state, codes = (ObservationState.DEGRADED,
                            (TIMING_DEADLINE_MARGINAL,))
        else:
            state, codes = ObservationState.NOMINAL, ()

        # The classification names segments that BLEW THEIR OWN BUDGET, in
        # the order delay is incurred. Not "the biggest one" -- the biggest
        # share of an acceptable total is not a finding.
        over = tuple(seg for seg in SEGMENTS
                     if seg in measured and budgets.get(seg) is not None
                     and measured[seg] > budgets[seg])
        if SENSOR_SLOW in measured and spec.expected_period_s is not None:
            limit = spec.expected_period_s * (1.0 + spec.period_tolerance_frac)
            if measured[SENSOR_SLOW] > limit:
                over = (SENSOR_SLOW,) + over

        out.append(self._record(
            component=spec.name, relation="timing.end_to_end",
            observation_state=state,
            applicability=(Applicability.NOT_APPLICABLE if deadline is None
                           else Applicability.APPLICABLE),
            affected_functions=fns, reason_codes=codes,
            measured_value=total, expected_value=deadline,
            residual=(None if deadline is None else total - deadline),
            timestamp_validity=stamps["t_validity"],
            timestamp_arrival=stamps["t_arrival"],
            timestamp_processed=stamps["t_processed"],
            dependencies=spec.depends_on,
            expected_relation="end-to-end latency within the function's "
                              "declared deadline",
            detail={"segments_s": {k: round(v, 9)
                                   for k, v in sorted(measured.items())},
                    "segments_over_budget": list(over),
                    "classification": over[0] if over else None,
                    "t_decision_present": stamps["t_decision"] is not None}))
        return out

    def declaration(self) -> dict:
        d = super().declaration()
        covered = set(self.affected_functions)
        for c in self.channels:
            covered.update(self._fns(c))
        d["affected_functions"] = sorted(covered)
        d["channels"] = [
            {"name": c.name,
             "end_to_end_deadline_s": c.end_to_end_deadline_s,
             "affected_functions": list(self._fns(c)),
             "depends_on": list(c.depends_on)} for c in self.channels]
        d["segment_classes"] = list(SEGMENTS)
        return d


def _f(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
