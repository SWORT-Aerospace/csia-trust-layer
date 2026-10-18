"""COMPUTE / PROCESS HEALTH — §5.

Spec: `engineering/v2/COMPUTE_DOMAIN_SPEC.md`.

§5 asks for four outputs to be **distinguishable**, and they are four separate
relations here rather than four levels of one health number:

    compute.process_alive        the process exists
    compute.process_producing    it is emitting output
    compute.deadline_met         the output arrived in time to be used
    compute.resource_headroom    the machine has room to keep doing it

They are separate because they fail separately and they mean different things
to a consumer. A perception process that is alive, producing, and 40 ms late
is not "80% healthy"; it is a process whose output is unusable for closed-loop
control and perfectly usable for logging. Collapsing that into one scalar
destroys exactly the distinction the function graph needs.

THE SENTENCE THAT DRIVES THE DESIGN — §5
----------------------------------------
    A value produced after its deadline should not automatically remain
    operationally equivalent to an on-time value.

Note "automatically". This module does not decide that a late value is
useless — it reports the deadline as violated and lets each function say what
that costs it, via `no_degradation_domains` in the function graph. Attitude
control lists COMPUTE there and stops; logging does not and continues. The
same evidence, two correct answers, because the requirement differs and the
requirement is declared per function rather than assumed globally.

STATELESS BY CONTRACT
---------------------
Restart counts, deadline-miss counts and heartbeat ages are read from the
snapshot, not accumulated here. A domain that kept counters could not be
replayed from a single snapshot, and replay is what the ledger is for.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import AssuranceDomain, DomainResult, Snapshot
from ..evidence import Applicability, ObservationState

DOMAIN = "COMPUTE"

COMPUTE_PROCESS_DEAD = "COMPUTE_PROCESS_DEAD"
COMPUTE_HEARTBEAT_STALE = "COMPUTE_HEARTBEAT_STALE"
COMPUTE_NO_OUTPUT = "COMPUTE_NO_OUTPUT"
COMPUTE_DEADLINE_MISSED = "COMPUTE_DEADLINE_MISSED"
COMPUTE_DEADLINE_MARGINAL = "COMPUTE_DEADLINE_MARGINAL"
COMPUTE_CPU_SATURATED = "COMPUTE_CPU_SATURATED"
COMPUTE_MEMORY_PRESSURE = "COMPUTE_MEMORY_PRESSURE"
COMPUTE_QUEUE_BACKLOG = "COMPUTE_QUEUE_BACKLOG"
COMPUTE_THERMAL_THROTTLED = "COMPUTE_THERMAL_THROTTLED"
COMPUTE_RESTARTED = "COMPUTE_RESTARTED"
COMPUTE_TELEMETRY_MISSING = "COMPUTE_TELEMETRY_MISSING"

REASON_CODES = (
    COMPUTE_PROCESS_DEAD, COMPUTE_HEARTBEAT_STALE, COMPUTE_NO_OUTPUT,
    COMPUTE_DEADLINE_MISSED, COMPUTE_DEADLINE_MARGINAL,
    COMPUTE_CPU_SATURATED, COMPUTE_MEMORY_PRESSURE, COMPUTE_QUEUE_BACKLOG,
    COMPUTE_THERMAL_THROTTLED, COMPUTE_RESTARTED, COMPUTE_TELEMETRY_MISSING,
)


@dataclass(frozen=True)
class ProcessSpec:
    """A process the host cares about, and what it promised to do.

    Every limit is declared. There is no default deadline, because a default
    deadline is a made-up requirement and a function graph built on made-up
    requirements produces made-up eligibility.
    """

    name: str
    #: Functions this process's health bears on. Declared per process: the
    #: perception process and the logger do not limit the same things.
    affected_functions: tuple = ()
    #: Seconds. `None` disables the relation instead of guessing.
    heartbeat_limit_s: float | None = None
    output_age_limit_s: float | None = None
    deadline_s: float | None = None
    #: Fraction of the deadline at which lateness is called marginal.
    deadline_warn_frac: float = 0.80
    queue_depth_limit: int | None = None
    #: §22: what this process needs in order to work. Structure, not a score.
    depends_on: tuple = ()


@dataclass(frozen=True)
class ResourceSpec:
    """The machine the processes run on."""

    name: str = "cpu"
    cpu_warn: float = 0.85
    cpu_fail: float = 0.97
    memory_warn: float = 0.85
    memory_fail: float = 0.95
    affected_functions: tuple = ()


class ComputeAssuranceDomain(AssuranceDomain):
    domain_id = DOMAIN
    schema_version = "2.0.0"
    required_inputs = ("COMPUTE/<process>/alive",)
    optional_inputs = ("heartbeat_age_s", "output_age_s", "runtime_s",
                       "deadline_misses", "queue_depth", "restart_count",
                       "COMPUTE/<resource>/cpu_load",
                       "COMPUTE/<resource>/memory_used_frac",
                       "COMPUTE/<resource>/throttled",
                       "COMPUTE/<resource>/reset_reason")
    relations = ("compute.process_alive", "compute.process_producing",
                 "compute.deadline_met", "compute.resource_headroom",
                 "compute.stability")
    reason_codes = REASON_CODES

    def __init__(self, processes=(), resource=ResourceSpec(),
                 affected_functions=()):
        self.processes = tuple(processes)
        self.resource = resource
        #: Domain-wide fallback for a process that declares none.
        self.affected_functions = (tuple(affected_functions)
                                   or tuple(resource.affected_functions)
                                   or ("COMPUTE_AVAILABILITY",))

    def _fns(self, spec: ProcessSpec) -> tuple:
        return tuple(spec.affected_functions) or self.affected_functions

    # ------------------------------------------------------------------
    def evaluate(self, snapshot: Snapshot) -> DomainResult:
        records, unevaluated = [], {}

        for spec in self.processes:
            sig = snapshot.component(DOMAIN, spec.name)
            fns = self._fns(spec)
            if not sig:
                records.append(self._record(
                    component=spec.name, relation="compute.process_alive",
                    observation_state=ObservationState.UNAVAILABLE,
                    applicability=Applicability.INPUTS_MISSING,
                    affected_functions=fns,
                    reason_codes=(COMPUTE_TELEMETRY_MISSING,),
                    timestamp_processed=snapshot.t,
                    expected_relation="declared process reports its state",
                    dependencies=spec.depends_on))
                unevaluated[spec.name] = "declared process absent from snapshot"
                continue

            records.extend(self._process(spec, sig, fns, snapshot,
                                         unevaluated))

        records.extend(self._resources(snapshot, unevaluated))
        return DomainResult(domain=DOMAIN, records=tuple(records),
                            unevaluated=unevaluated)

    # ------------------------------------------------------------------
    def _process(self, spec, sig, fns, snapshot, unevaluated) -> list:
        out = []
        t = snapshot.t

        # -- 1. alive ---------------------------------------------------
        alive = sig.get("alive")
        hb = _f(sig.get("heartbeat_age_s"))
        state, codes = ObservationState.NOMINAL, []
        if alive is False:
            state, codes = ObservationState.VIOLATED, [COMPUTE_PROCESS_DEAD]
        elif alive is None and hb is None:
            state, codes = (ObservationState.UNAVAILABLE,
                            [COMPUTE_TELEMETRY_MISSING])
        elif (spec.heartbeat_limit_s is not None and hb is not None
                and hb > spec.heartbeat_limit_s):
            # A heartbeat older than its limit is not a live process, whatever
            # the alive flag says. The flag is a claim; the heartbeat is
            # evidence, and where they disagree the evidence wins.
            state, codes = (ObservationState.VIOLATED,
                            [COMPUTE_HEARTBEAT_STALE])
        out.append(self._record(
            component=spec.name, relation="compute.process_alive",
            observation_state=state, applicability=Applicability.APPLICABLE,
            affected_functions=fns, reason_codes=tuple(codes),
            measured_value=hb, expected_value=spec.heartbeat_limit_s,
            timestamp_processed=t, dependencies=spec.depends_on,
            expected_relation="process alive and heartbeat within limit",
            detail={"alive_flag": alive}))

        # -- 2. producing output ----------------------------------------
        age = _f(sig.get("output_age_s"))
        if spec.output_age_limit_s is None or age is None:
            unevaluated[f"{spec.name}.output"] = (
                "no output_age_s signal or no declared output_age_limit_s")
        else:
            late = age > spec.output_age_limit_s
            out.append(self._record(
                component=spec.name, relation="compute.process_producing",
                observation_state=(ObservationState.VIOLATED if late
                                   else ObservationState.NOMINAL),
                applicability=Applicability.APPLICABLE,
                affected_functions=fns,
                reason_codes=(COMPUTE_NO_OUTPUT,) if late else (),
                measured_value=age, expected_value=spec.output_age_limit_s,
                residual=age - spec.output_age_limit_s,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="time since last output within limit"))

        # -- 3. deadline ------------------------------------------------
        runtime = _f(sig.get("runtime_s"))
        misses = sig.get("deadline_misses")
        if spec.deadline_s is None or (runtime is None and misses is None):
            unevaluated[f"{spec.name}.deadline"] = (
                "no declared deadline_s, or neither runtime_s nor "
                "deadline_misses reported")
        else:
            state, codes = ObservationState.NOMINAL, []
            slack = None
            if runtime is not None:
                slack = spec.deadline_s - runtime
                if runtime > spec.deadline_s:
                    state, codes = (ObservationState.VIOLATED,
                                    [COMPUTE_DEADLINE_MISSED])
                elif runtime > spec.deadline_s * spec.deadline_warn_frac:
                    state, codes = (ObservationState.DEGRADED,
                                    [COMPUTE_DEADLINE_MARGINAL])
            if misses:
                # A reported miss is a miss even if this tick's runtime was
                # fine: the platform observed something we did not.
                state, codes = (ObservationState.VIOLATED,
                                [COMPUTE_DEADLINE_MISSED])
            out.append(self._record(
                component=spec.name, relation="compute.deadline_met",
                observation_state=state,
                applicability=Applicability.APPLICABLE,
                affected_functions=fns, reason_codes=tuple(codes),
                measured_value=runtime, expected_value=spec.deadline_s,
                residual=(None if slack is None else -slack),
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="runtime <= deadline",
                detail={"deadline_slack_s": slack,
                        "reported_misses": misses}))

        # -- 4. stability: queue depth and restarts ---------------------
        depth = sig.get("queue_depth")
        restarts = sig.get("restart_count")
        if depth is None and restarts is None:
            unevaluated[f"{spec.name}.stability"] = (
                "no queue_depth or restart_count reported")
        else:
            state, codes = ObservationState.NOMINAL, []
            if (spec.queue_depth_limit is not None and depth is not None
                    and depth > spec.queue_depth_limit):
                state, codes = (ObservationState.DEGRADED,
                                [COMPUTE_QUEUE_BACKLOG])
            if restarts:
                state, codes = (ObservationState.DEGRADED,
                                codes + [COMPUTE_RESTARTED])
            out.append(self._record(
                component=spec.name, relation="compute.stability",
                observation_state=state,
                applicability=Applicability.APPLICABLE,
                affected_functions=fns if state is not
                ObservationState.NOMINAL else (),
                reason_codes=tuple(codes),
                measured_value=(None if depth is None else float(depth)),
                expected_value=(None if spec.queue_depth_limit is None
                                else float(spec.queue_depth_limit)),
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="queue within limit and no restarts",
                detail={"restart_count": restarts}))
        return out

    # ------------------------------------------------------------------
    def _resources(self, snapshot, unevaluated) -> list:
        res = self.resource
        sig = snapshot.component(DOMAIN, res.name)
        fns = tuple(res.affected_functions) or self.affected_functions
        if not sig:
            unevaluated[res.name] = "no resource telemetry"
            return [self._record(
                component=res.name, relation="compute.resource_headroom",
                observation_state=ObservationState.UNAVAILABLE,
                applicability=Applicability.INPUTS_MISSING,
                affected_functions=fns,
                reason_codes=(COMPUTE_TELEMETRY_MISSING,),
                timestamp_processed=snapshot.t,
                expected_relation="CPU and memory headroom reported")]

        cpu = _f(sig.get("cpu_load"))
        mem = _f(sig.get("memory_used_frac"))
        throttled = bool(sig.get("throttled", False))
        state, codes = ObservationState.NOMINAL, []
        if cpu is not None:
            if cpu > res.cpu_fail:
                state, codes = ObservationState.VIOLATED, [
                    COMPUTE_CPU_SATURATED]
            elif cpu > res.cpu_warn:
                state, codes = ObservationState.DEGRADED, [
                    COMPUTE_CPU_SATURATED]
        if mem is not None:
            if mem > res.memory_fail:
                state, codes = (ObservationState.VIOLATED,
                                codes + [COMPUTE_MEMORY_PRESSURE])
            elif mem > res.memory_warn and state is ObservationState.NOMINAL:
                state, codes = (ObservationState.DEGRADED,
                                codes + [COMPUTE_MEMORY_PRESSURE])
        if throttled and state is ObservationState.NOMINAL:
            state = ObservationState.DEGRADED
        if throttled:
            codes = codes + [COMPUTE_THERMAL_THROTTLED]
        if cpu is None and mem is None and not throttled:
            unevaluated[res.name] = "no cpu_load or memory_used_frac"
            state, codes = (ObservationState.UNAVAILABLE,
                            [COMPUTE_TELEMETRY_MISSING])

        return [self._record(
            component=res.name, relation="compute.resource_headroom",
            observation_state=state, applicability=Applicability.APPLICABLE,
            affected_functions=fns, reason_codes=tuple(codes),
            measured_value=cpu, expected_value=res.cpu_fail,
            timestamp_processed=snapshot.t,
            expected_relation="CPU and memory below their declared limits",
            detail={"cpu_load": cpu, "memory_used_frac": mem,
                    "throttled": throttled,
                    "reset_reason": sig.get("reset_reason")})]

    def declaration(self) -> dict:
        d = super().declaration()
        covered = set(self.affected_functions)
        for spec in self.processes:
            covered.update(self._fns(spec))
        covered.update(self.resource.affected_functions)
        d["affected_functions"] = sorted(covered)
        d["processes"] = [
            {"name": p.name, "deadline_s": p.deadline_s,
             "affected_functions": list(self._fns(p)),
             "depends_on": list(p.depends_on)} for p in self.processes]
        return d


def _f(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
