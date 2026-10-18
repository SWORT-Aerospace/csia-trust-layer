"""ACTUATION / PROPULSION — §8, built as the sixth domain.

Spec: `engineering/v2/ACTUATION_DOMAIN_SPEC.md`.

§26 permits a sixth domain "if architecture remains clean". It was built
because it is the one that tests the claim: actuation is the domain that
genuinely spans electrical and mechanical evidence, it is the one the motor
test stand of §37 is built around, and it needs no framework change at all.
That last point is the finding — this module adds no core concept, no new
evidence field and no engine hook. It is a plugin like the others.

THE CHAIN — §8
--------------
    requested command -> transmitted command -> controller/ESC response
    -> current -> RPM/position -> physical response

Each arrow is a relation, and the value is in which arrow breaks:

    comm gap        requested != transmitted        (COMMUNICATION candidate)
    no electrical   command up, current flat        (power path / ESC / wiring)
    stalled         current up, RPM flat            (mechanical / load)
    no motion       RPM up, no physical response    (transmission / airframe)

    Never uniquely attribute without sufficient evidence.  (§8)

So this module names CANDIDATES and does not name causes. `actuation.electrical
_response` going adverse says "command produced no current"; whether that is
the ESC, the power path or the wiring is not decidable from these signals, and
the record's `dependencies` name the alternatives so the attribution layer can
say AMBIGUOUS with the alternatives listed instead of picking one.

WHY "HIGH CURRENT + LOW RPM" IS A SEPARATE RELATION FROM "NO CURRENT"
--------------------------------------------------------------------
They point in opposite directions. A motor drawing its expected current and
not turning is mechanically obstructed or has lost its position feedback; a
motor drawing nothing is not being driven. Merging them into one
"actuator unhealthy" would discard the only discriminating information the
domain has.

STATELESS, SO NO DERIVATIVES
----------------------------
§8's relations are written as trends ("command up -> RPM up"). A stateless
domain cannot difference across ticks, so the relations here are the
*level-form* equivalents: at a declared command level, a declared current and
RPM are expected, within declared tolerances, above a floor below which the
expectation is not distinguishable. Where a host does compute a trend it can
supply it as a signal; nothing here fabricates one.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import AssuranceDomain, DomainResult, Snapshot
from ..evidence import Applicability, ObservationState

DOMAIN = "ACTUATION"

ACT_COMMAND_NOT_TRANSMITTED = "ACT_COMMAND_NOT_TRANSMITTED"
ACT_NO_ELECTRICAL_RESPONSE = "ACT_NO_ELECTRICAL_RESPONSE"
ACT_STALLED = "ACT_STALLED"
ACT_RESPONSE_LOW = "ACT_RESPONSE_LOW"
ACT_OVERCURRENT = "ACT_OVERCURRENT"
ACT_NO_PHYSICAL_RESPONSE = "ACT_NO_PHYSICAL_RESPONSE"
ACT_TELEMETRY_MISSING = "ACT_TELEMETRY_MISSING"

REASON_CODES = (
    ACT_COMMAND_NOT_TRANSMITTED, ACT_NO_ELECTRICAL_RESPONSE, ACT_STALLED,
    ACT_RESPONSE_LOW, ACT_OVERCURRENT, ACT_NO_PHYSICAL_RESPONSE,
    ACT_TELEMETRY_MISSING,
)


@dataclass(frozen=True)
class ActuatorSpec:
    """One actuator and the response its host declares it should give.

    `full_*` are the values at command = 1.0. They come from a motor/ESC
    datasheet or a bench characterisation; they are configuration, and the
    defaults are the synthetic harness's, not a measurement of any hardware.
    """

    name: str
    affected_functions: tuple = ()
    full_current_a: float | None = None
    full_rpm: float | None = None
    #: Fractional tolerance on the expected response.
    current_tolerance_frac: float = 0.35
    rpm_tolerance_frac: float = 0.20
    #: Below this command the expectations are not distinguishable from
    #: standing losses, and every relation reports NOT_APPLICABLE.
    min_command: float = 0.15
    #: A command/transmitted mismatch above this is a transmission finding.
    command_match_tolerance: float = 0.02
    #: Current at or above this fraction of expected WITH rpm at or below
    #: `stall_rpm_frac` of expected is the stall signature.
    stall_current_frac: float = 0.70
    stall_rpm_frac: float = 0.30
    #: Overcurrent, one-sided.
    overcurrent_frac: float = 1.40
    #: Optional physical response channel (thrust, torque, position rate).
    physical_signal: str | None = None
    full_physical: float | None = None
    physical_tolerance_frac: float = 0.35
    #: §22: the alternatives a "no electrical response" finding cannot
    #: separate. Named, not scored.
    depends_on: tuple = ()


class ActuationAssuranceDomain(AssuranceDomain):
    domain_id = DOMAIN
    schema_version = "2.0.0"
    required_inputs = ("ACTUATION/<actuator>/command",)
    optional_inputs = ("command_transmitted", "current_a", "rpm",
                       "<physical_signal>")
    relations = ("actuation.command_path", "actuation.electrical_response",
                 "actuation.mechanical_response",
                 "actuation.physical_response")
    reason_codes = REASON_CODES

    def __init__(self, actuators=(), affected_functions=("PROPULSION",)):
        self.actuators = tuple(actuators)
        self.affected_functions = tuple(affected_functions)

    def _fns(self, spec: ActuatorSpec) -> tuple:
        return tuple(spec.affected_functions) or self.affected_functions

    # ------------------------------------------------------------------
    def evaluate(self, snapshot: Snapshot) -> DomainResult:
        records, unevaluated = [], {}
        for spec in self.actuators:
            sig = snapshot.component(DOMAIN, spec.name)
            fns = self._fns(spec)
            cmd = _f(sig.get("command"))
            if cmd is None:
                records.append(self._record(
                    component=spec.name, relation="actuation.command_path",
                    observation_state=ObservationState.UNAVAILABLE,
                    applicability=Applicability.INPUTS_MISSING,
                    affected_functions=fns,
                    reason_codes=(ACT_TELEMETRY_MISSING,),
                    timestamp_processed=snapshot.t,
                    dependencies=spec.depends_on,
                    expected_relation="declared actuator reports its command"))
                unevaluated[spec.name] = "no command signal"
                continue
            records.extend(self._actuator(spec, sig, fns, cmd, snapshot,
                                          unevaluated))
        return DomainResult(domain=DOMAIN, records=tuple(records),
                            unevaluated=unevaluated)

    # ------------------------------------------------------------------
    def _actuator(self, spec, sig, fns, cmd, snapshot, unevaluated) -> list:
        out, t = [], snapshot.t

        # -- 1. command path: requested vs transmitted -------------------
        tx = _f(sig.get("command_transmitted"))
        if tx is None:
            unevaluated[f"{spec.name}.command_path"] = (
                "no command_transmitted signal to compare against")
        else:
            gap = abs(tx - cmd)
            bad = gap > spec.command_match_tolerance
            out.append(self._record(
                component=spec.name, relation="actuation.command_path",
                observation_state=(ObservationState.VIOLATED if bad
                                   else ObservationState.NOMINAL),
                applicability=Applicability.APPLICABLE,
                affected_functions=fns,
                reason_codes=(ACT_COMMAND_NOT_TRANSMITTED,) if bad else (),
                measured_value=tx, expected_value=cmd, residual=tx - cmd,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="transmitted command matches requested",
                detail={"tolerance": spec.command_match_tolerance,
                        "candidate": "COMMUNICATION or command path"
                                     if bad else None}))

        below_floor = cmd < spec.min_command
        current = _f(sig.get("current_a"))
        rpm = _f(sig.get("rpm"))
        exp_i = (None if spec.full_current_a is None
                 else cmd * spec.full_current_a)
        exp_rpm = None if spec.full_rpm is None else cmd * spec.full_rpm

        # -- 2. electrical response --------------------------------------
        if current is None or exp_i is None:
            unevaluated[f"{spec.name}.electrical"] = (
                "needs current_a and a declared full_current_a")
        elif below_floor:
            out.append(self._na(spec, "actuation.electrical_response", cmd, t))
        else:
            resid = current - exp_i
            no_response = -resid > exp_i * spec.current_tolerance_frac
            over = current > exp_i * spec.overcurrent_frac
            state, codes = ObservationState.NOMINAL, ()
            if no_response:
                state, codes = (ObservationState.VIOLATED,
                                (ACT_NO_ELECTRICAL_RESPONSE,))
            elif over:
                state, codes = ObservationState.DEGRADED, (ACT_OVERCURRENT,)
            out.append(self._record(
                component=spec.name,
                relation="actuation.electrical_response",
                observation_state=state,
                applicability=Applicability.APPLICABLE,
                affected_functions=fns, reason_codes=codes,
                measured_value=current, expected_value=exp_i, residual=resid,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="current ~= command * full-load current",
                detail={"tolerance_frac": spec.current_tolerance_frac,
                        "candidates": list(spec.depends_on) if no_response
                        else None,
                        "note": "commanded but drawing no current: ESC, "
                                "power path and wiring are not separable "
                                "from these signals"
                                if no_response else None}))

        # -- 3. mechanical response: the stall signature -----------------
        if rpm is None or exp_rpm is None:
            unevaluated[f"{spec.name}.mechanical"] = (
                "needs rpm and a declared full_rpm")
        elif below_floor:
            out.append(self._na(spec, "actuation.mechanical_response", cmd, t))
        else:
            resid = rpm - exp_rpm
            low = -resid > exp_rpm * spec.rpm_tolerance_frac
            # The stall signature needs BOTH halves: current present AND rpm
            # absent. Either alone is a different finding, and reporting a
            # stall on rpm alone would mean a dead ESC read as a seized motor.
            stalled = bool(
                low and current is not None and exp_i
                and current >= exp_i * spec.stall_current_frac
                and rpm <= exp_rpm * spec.stall_rpm_frac)
            state, codes = ObservationState.NOMINAL, ()
            if stalled:
                state, codes = ObservationState.VIOLATED, (ACT_STALLED,)
            elif low:
                state, codes = ObservationState.DEGRADED, (ACT_RESPONSE_LOW,)
            out.append(self._record(
                component=spec.name,
                relation="actuation.mechanical_response",
                observation_state=state,
                applicability=Applicability.APPLICABLE,
                affected_functions=fns, reason_codes=codes,
                measured_value=rpm, expected_value=exp_rpm, residual=resid,
                timestamp_processed=t, dependencies=spec.depends_on,
                expected_relation="rpm ~= command * full-load rpm",
                detail={"tolerance_frac": spec.rpm_tolerance_frac,
                        "current_a": current,
                        "signature": "current present, rpm absent -> "
                                     "mechanical/load candidate"
                                     if stalled else None}))

        # -- 4. physical response ----------------------------------------
        if spec.physical_signal is None or spec.full_physical is None:
            unevaluated[f"{spec.name}.physical"] = (
                "no declared physical response channel")
            return out
        phys = _f(sig.get(spec.physical_signal))
        if phys is None:
            unevaluated[f"{spec.name}.physical"] = (
                f"declared channel {spec.physical_signal!r} not reported")
            return out
        if below_floor:
            out.append(self._na(spec, "actuation.physical_response", cmd, t))
            return out
        exp_p = cmd * spec.full_physical
        resid = phys - exp_p
        bad = -resid > exp_p * spec.physical_tolerance_frac
        out.append(self._record(
            component=spec.name, relation="actuation.physical_response",
            observation_state=(ObservationState.VIOLATED if bad
                               else ObservationState.NOMINAL),
            applicability=Applicability.APPLICABLE,
            affected_functions=fns,
            reason_codes=(ACT_NO_PHYSICAL_RESPONSE,) if bad else (),
            measured_value=phys, expected_value=exp_p, residual=resid,
            timestamp_processed=t, dependencies=spec.depends_on,
            expected_relation=f"{spec.physical_signal} ~= command * full",
            detail={"tolerance_frac": spec.physical_tolerance_frac,
                    "rpm": rpm}))
        return out

    def _na(self, spec, relation, cmd, t):
        return self._record(
            component=spec.name, relation=relation,
            observation_state=ObservationState.NOT_APPLICABLE,
            applicability=Applicability.NOT_APPLICABLE,
            affected_functions=(), timestamp_processed=t,
            measured_value=cmd, dependencies=spec.depends_on,
            expected_relation="command below the floor at which a response "
                              "is distinguishable",
            detail={"command": cmd, "min_command": spec.min_command})

    def declaration(self) -> dict:
        d = super().declaration()
        covered = set(self.affected_functions)
        for a in self.actuators:
            covered.update(self._fns(a))
        d["affected_functions"] = sorted(covered)
        d["actuators"] = [{"name": a.name,
                           "affected_functions": list(self._fns(a)),
                           "depends_on": list(a.depends_on)}
                          for a in self.actuators]
        return d


def _f(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
