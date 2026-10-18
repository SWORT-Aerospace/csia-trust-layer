"""POWER INTEGRITY — §4, the first domain built from scratch under v2.

Spec: `engineering/v2/POWER_DOMAIN_SPEC.md`.

    No novel algorithm required.  (§4)

Nothing here is novel and nothing here is claimed to be. P = V·I is Joule's
law, a regulator tolerance band comes off a datasheet, and battery droop under
load is Ohm's law across an internal resistance. The engineering content of
this module is not the arithmetic — it is **which comparison is made, what is
declared rather than inferred, and what the result is allowed to conclude**.

THE ONE RELATION THAT IS ACTUALLY WORTH SOMETHING — §28 SCENARIO B
------------------------------------------------------------------
    battery healthy + 5 V rail failing -> downstream regulator/distribution
    suspicion, NOT battery fault

A monitor that reports "POWER: FAULT" has told the operator nothing they
could act on. The distinction between "the battery is failing" and "the
battery is fine and the thing between it and your sensors is failing" is the
whole value, and it is available for free from evidence the platform already
has — provided the battery is monitored SEPARATELY from the rails it feeds,
and provided a healthy battery reading is emitted **affirmatively** rather
than merely omitted. That is why `power.source_health` emits a NOMINAL record
on a good tick instead of staying silent: silence cannot exonerate anything.

WHAT IS CONFIGURATION AND WHAT IS PHYSICS
-----------------------------------------
Every threshold in this module is host-declared configuration carried on
`RailSpec` / `BatterySpec` / `LoadSpec`. The defaults below are the values the
synthetic harness runs with, chosen as ordinary electronics practice — a 5 V
regulator specified to +/-5%, a warning band inside it — and they are **not
derived from any hardware measurement**, because no hardware has been
measured. A deployment states its own from its own datasheets.

Where a declared input is absent the relation is not evaluated and says so.
It does not fall back to a default and it does not quietly pass.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..domain import AssuranceDomain, DomainResult, Snapshot
from ..evidence import Applicability, ObservationState

DOMAIN = "POWER"

# ------------------------------------------------------------------ codes
POWER_TELEMETRY_MISSING = "POWER_TELEMETRY_MISSING"
POWER_RAIL_MARGINAL = "POWER_RAIL_MARGINAL"
POWER_RAIL_OUT_OF_TOLERANCE = "POWER_RAIL_OUT_OF_TOLERANCE"
POWER_RAIL_UNAVAILABLE = "POWER_RAIL_UNAVAILABLE"
POWER_BALANCE_INCONSISTENT = "POWER_BALANCE_INCONSISTENT"
POWER_CELL_IMBALANCE = "POWER_CELL_IMBALANCE"
POWER_EXCESS_DROOP = "POWER_EXCESS_DROOP"
POWER_DISTRIBUTION_SUSPECT = "POWER_DISTRIBUTION_SUSPECT"
POWER_LOAD_WITHOUT_CURRENT = "POWER_LOAD_WITHOUT_CURRENT"

REASON_CODES = (
    POWER_TELEMETRY_MISSING, POWER_RAIL_MARGINAL, POWER_RAIL_OUT_OF_TOLERANCE,
    POWER_RAIL_UNAVAILABLE, POWER_BALANCE_INCONSISTENT, POWER_CELL_IMBALANCE,
    POWER_EXCESS_DROOP, POWER_DISTRIBUTION_SUSPECT,
    POWER_LOAD_WITHOUT_CURRENT,
)


# ----------------------------------------------------------------- config
@dataclass(frozen=True)
class RailSpec:
    """A regulated rail, as the host declares it.

    `nominal_v` and the two bands come from the regulator's datasheet. They
    are not learned, not adapted and not widened after seeing a result.
    """

    name: str
    nominal_v: float
    #: Fractional deviation at which the rail is called marginal / failed.
    #: Defaults are the synthetic profile's, i.e. ordinary practice for a
    #: +/-5%-specified regulator. NOT measured from hardware.
    warn_frac: float = 0.02
    fail_frac: float = 0.05
    #: §22: explicit structure. Which upstream node this rail hangs off, so
    #: two sensors sagging on one rail can be recognised as one dependency
    #: rather than scored for correlation.
    depends_on: tuple = ()
    #: What this rail FEEDS, in function terms. Empty falls back to the
    #: domain-wide list.
    #:
    #: Scoping per rail is not a refinement, it is the difference between a
    #: useful answer and a useless one. A 5 V regulator failing on a vehicle
    #: whose IMUs run off 3V3 does not stop dead reckoning, and a domain that
    #: attached every rail to every function would say it did — reporting
    #: total loss of a vehicle that can still fly home on its inertial
    #: solution. The host knows its harness; it declares it here.
    affected_functions: tuple = ()


@dataclass(frozen=True)
class BatterySpec:
    """The source. Monitored separately from everything it feeds."""

    name: str = "battery"
    #: P = V*I agreement, when the platform reports P independently.
    power_tolerance_frac: float = 0.05
    power_tolerance_floor_w: float = 0.5
    #: Cell spread. `None` disables the relation rather than guessing a
    #: chemistry-appropriate limit.
    cell_spread_warn_v: float | None = None
    cell_spread_fail_v: float | None = None
    #: Droop: expected V = voltage_reference_v - I*esr_ohm. The reference is a
    #: SIGNAL the host supplies (a slow no-load estimate), not state kept here
    #: -- a domain is stateless by contract, and a domain that filtered its
    #: own reference could not be replayed from one snapshot.
    esr_ohm: float | None = None
    droop_warn_v: float | None = None
    droop_fail_v: float | None = None
    #: What the source feeds. Empty falls back to the domain-wide list --
    #: and for a battery that fallback is usually right, because everything
    #: is downstream of the source.
    affected_functions: tuple = ()


@dataclass(frozen=True)
class LoadSpec:
    """Declared load/current response — the POWER half of §4's last relation.

    The full command -> current -> motion chain belongs to ACTUATION; what
    POWER can say on its own is narrower and is kept narrow: a declared demand
    fraction should draw a declared current, and if it draws far less the
    power path is a candidate. Attributing that to the actuator, the ESC or
    the wiring needs the actuation domain and the cross-domain relation.
    """

    component: str
    demand_signal: str = "demand_frac"
    full_load_current_a: float = 0.0
    tolerance_frac: float = 0.30
    #: Below this demand the relation says nothing: near zero demand the
    #: expected current is within the noise of any shunt.
    min_demand_frac: float = 0.20


#: The synthetic aircraft/test-stand profile's rails. Configuration.
DEFAULT_RAILS = (
    RailSpec("rail_5v", nominal_v=5.0, depends_on=("POWER/battery",)),
    RailSpec("rail_3v3", nominal_v=3.3, depends_on=("POWER/rail_5v",)),
)


class PowerAssuranceDomain(AssuranceDomain):
    """Power source, rails and distribution, kept structurally distinct."""

    domain_id = DOMAIN
    schema_version = "2.0.0"
    required_inputs = ("POWER/<battery>/voltage_v",
                       "POWER/<battery>/current_a")
    optional_inputs = ("power_w", "voltage_reference_v", "cell_voltages",
                       "temperature_c", "POWER/<rail>/voltage_v",
                       "POWER/<load>/demand_frac")
    relations = ("power.source_health", "power.p_equals_vi",
                 "power.droop_vs_current", "power.cell_balance",
                 "power.rail_tolerance", "power.load_current_response")
    reason_codes = REASON_CODES

    def __init__(self, rails=DEFAULT_RAILS, battery=BatterySpec(),
                 loads=(), affected_functions=("PROPULSION", "SENSING",
                                               "COMPUTE_AVAILABILITY")):
        self.rails = tuple(rails)
        self.battery = battery
        self.loads = tuple(loads)
        self.affected_functions = tuple(affected_functions)

    # ------------------------------------------------------------------
    def _fns(self, spec) -> tuple:
        return tuple(spec.affected_functions) or self.affected_functions

    # ------------------------------------------------------------------
    def evaluate(self, snapshot: Snapshot) -> DomainResult:
        records, unevaluated = [], {}
        bat = self.battery
        bat_fns = self._fns(bat)
        sig = snapshot.component(DOMAIN, bat.name)

        v = _f(sig.get("voltage_v"))
        i = _f(sig.get("current_a"))
        battery_adverse = False

        if v is None or i is None:
            records.append(self._record(
                component=bat.name, relation="power.source_health",
                observation_state=ObservationState.UNAVAILABLE,
                applicability=Applicability.INPUTS_MISSING,
                affected_functions=bat_fns,
                reason_codes=(POWER_TELEMETRY_MISSING,),
                timestamp_processed=snapshot.t,
                expected_relation="battery voltage and current present",
                detail={"voltage_v": v, "current_a": i}))
            unevaluated[bat.name] = "voltage_v and/or current_a absent"
            battery_adverse = True          # cannot exonerate what we cannot see
        else:
            records.append(self._record(
                component=bat.name, relation="power.source_health",
                observation_state=ObservationState.NOMINAL,
                applicability=Applicability.APPLICABLE,
                affected_functions=bat_fns,
                measured_value=v, timestamp_processed=snapshot.t,
                expected_relation="battery telemetry present and readable",
                detail={"current_a": i}))

            # -- P = V*I ------------------------------------------------
            p = _f(sig.get("power_w"))
            if p is None:
                unevaluated[f"{bat.name}.power_w"] = (
                    "platform reports no independent power measurement")
            else:
                expected = v * i
                tol = max(bat.power_tolerance_floor_w,
                          abs(expected) * bat.power_tolerance_frac)
                resid = p - expected
                bad = abs(resid) > tol
                records.append(self._record(
                    component=bat.name, relation="power.p_equals_vi",
                    observation_state=(ObservationState.DEGRADED if bad
                                       else ObservationState.NOMINAL),
                    applicability=Applicability.APPLICABLE,
                    affected_functions=(),
                    reason_codes=((POWER_BALANCE_INCONSISTENT,) if bad
                                  else ()),
                    measured_value=p, expected_value=expected, residual=resid,
                    timestamp_processed=snapshot.t,
                    expected_relation="P = V * I",
                    detail={"tolerance_w": tol}))
                battery_adverse = battery_adverse or bad

            # -- droop vs current ---------------------------------------
            ref = _f(sig.get("voltage_reference_v"))
            if bat.esr_ohm is None or ref is None or bat.droop_fail_v is None:
                unevaluated[f"{bat.name}.droop"] = (
                    "needs esr_ohm, droop limits and a voltage_reference_v "
                    "signal; not declared")
            else:
                expected = ref - i * bat.esr_ohm
                resid = v - expected             # negative == sagging further
                warn = bat.droop_warn_v if bat.droop_warn_v is not None \
                    else bat.droop_fail_v
                state = ObservationState.NOMINAL
                codes = ()
                if -resid > bat.droop_fail_v:
                    state, codes = (ObservationState.VIOLATED,
                                    (POWER_EXCESS_DROOP,))
                elif -resid > warn:
                    state, codes = (ObservationState.DEGRADED,
                                    (POWER_EXCESS_DROOP,))
                records.append(self._record(
                    component=bat.name, relation="power.droop_vs_current",
                    observation_state=state,
                    applicability=Applicability.APPLICABLE,
                    affected_functions=bat_fns
                    if state is not ObservationState.NOMINAL else (),
                    reason_codes=codes,
                    measured_value=v, expected_value=expected, residual=resid,
                    timestamp_processed=snapshot.t,
                    expected_relation="V = V_ref - I * ESR",
                    detail={"esr_ohm": bat.esr_ohm, "current_a": i,
                            "warn_v": warn, "fail_v": bat.droop_fail_v}))
                battery_adverse = (battery_adverse
                                   or state is not ObservationState.NOMINAL)

            # -- cell balance -------------------------------------------
            cells = sig.get("cell_voltages")
            if not cells or bat.cell_spread_fail_v is None:
                unevaluated[f"{bat.name}.cells"] = (
                    "no per-cell telemetry or no declared spread limit")
            else:
                cells = [float(c) for c in cells]
                spread = max(cells) - min(cells)
                warn = (bat.cell_spread_warn_v
                        if bat.cell_spread_warn_v is not None
                        else bat.cell_spread_fail_v)
                state, codes = ObservationState.NOMINAL, ()
                if spread > bat.cell_spread_fail_v:
                    state, codes = (ObservationState.VIOLATED,
                                    (POWER_CELL_IMBALANCE,))
                elif spread > warn:
                    state, codes = (ObservationState.DEGRADED,
                                    (POWER_CELL_IMBALANCE,))
                records.append(self._record(
                    component=bat.name, relation="power.cell_balance",
                    observation_state=state,
                    applicability=Applicability.APPLICABLE,
                    affected_functions=bat_fns
                    if state is not ObservationState.NOMINAL else (),
                    reason_codes=codes, measured_value=spread,
                    timestamp_processed=snapshot.t,
                    expected_relation="max(cell) - min(cell) within limit",
                    detail={"cells": len(cells), "warn_v": warn,
                            "fail_v": bat.cell_spread_fail_v}))
                battery_adverse = (battery_adverse
                                   or state is not ObservationState.NOMINAL)

        # -- rails -------------------------------------------------------
        failing_rails = []
        for rail in self.rails:
            rail_fns = self._fns(rail)
            rv = _f(snapshot.get(DOMAIN, rail.name, "voltage_v"))
            if rv is None:
                records.append(self._record(
                    component=rail.name, relation="power.rail_tolerance",
                    observation_state=ObservationState.UNAVAILABLE,
                    applicability=Applicability.INPUTS_MISSING,
                    affected_functions=rail_fns,
                    reason_codes=(POWER_RAIL_UNAVAILABLE,),
                    timestamp_processed=snapshot.t,
                    expected_value=rail.nominal_v,
                    expected_relation=f"{rail.name} within declared band",
                    dependencies=rail.depends_on))
                unevaluated[rail.name] = "declared rail reported no voltage"
                failing_rails.append(rail.name)
                continue

            dev = abs(rv - rail.nominal_v) / rail.nominal_v
            state, codes = ObservationState.NOMINAL, ()
            if dev > rail.fail_frac:
                state, codes = (ObservationState.VIOLATED,
                                (POWER_RAIL_OUT_OF_TOLERANCE,))
            elif dev > rail.warn_frac:
                state, codes = (ObservationState.DEGRADED,
                                (POWER_RAIL_MARGINAL,))
            if state is not ObservationState.NOMINAL:
                failing_rails.append(rail.name)
            records.append(self._record(
                component=rail.name, relation="power.rail_tolerance",
                observation_state=state,
                applicability=Applicability.APPLICABLE,
                affected_functions=rail_fns,
                reason_codes=codes,
                measured_value=rv, expected_value=rail.nominal_v,
                residual=rv - rail.nominal_v,
                timestamp_processed=snapshot.t,
                expected_relation=f"|V - {rail.nominal_v}| / "
                                  f"{rail.nominal_v} <= {rail.fail_frac}",
                dependencies=rail.depends_on,
                detail={"deviation_frac": round(dev, 6),
                        "warn_frac": rail.warn_frac,
                        "fail_frac": rail.fail_frac}))

        # -- declared load / current response ----------------------------
        for load in self.loads:
            demand = _f(snapshot.get(DOMAIN, load.component,
                                     load.demand_signal))
            i_load = _f(snapshot.get(DOMAIN, load.component, "current_a"))
            if i_load is None:
                i_load = i
            if demand is None or i_load is None or load.full_load_current_a \
                    <= 0:
                unevaluated[f"{load.component}.load"] = (
                    "needs a demand fraction, a current and a declared "
                    "full-load current")
                continue
            if demand < load.min_demand_frac:
                records.append(self._record(
                    component=load.component,
                    relation="power.load_current_response",
                    observation_state=ObservationState.NOT_APPLICABLE,
                    applicability=Applicability.NOT_APPLICABLE,
                    affected_functions=(),
                    measured_value=i_load, timestamp_processed=snapshot.t,
                    expected_relation="demand below the floor at which an "
                                      "expected current is distinguishable",
                    detail={"demand_frac": demand,
                            "min_demand_frac": load.min_demand_frac}))
                continue
            expected = demand * load.full_load_current_a
            resid = i_load - expected
            # One-sided on purpose: MORE current than expected is an actuation
            # or mechanical finding (§8), not a power-path one, and claiming
            # it here would double-count it against the wrong domain.
            short = -resid > expected * load.tolerance_frac
            records.append(self._record(
                component=load.component,
                relation="power.load_current_response",
                observation_state=(ObservationState.DEGRADED if short
                                   else ObservationState.NOMINAL),
                applicability=Applicability.APPLICABLE,
                affected_functions=self.affected_functions if short else (),
                reason_codes=(POWER_LOAD_WITHOUT_CURRENT,) if short else (),
                measured_value=i_load, expected_value=expected,
                residual=resid, timestamp_processed=snapshot.t,
                expected_relation="I >= demand * full_load_current * "
                                  "(1 - tolerance)",
                detail={"demand_frac": demand,
                        "tolerance_frac": load.tolerance_frac,
                        "one_sided": "over-current is an ACTUATION finding"}))

        # -- §28/B: the exoneration, stated explicitly -------------------
        # A failing rail with an affirmatively healthy source is a
        # DISTRIBUTION finding. It is written onto the rail record rather than
        # invented as a separate `distribution` component, because a component
        # that emits no telemetry of its own would enter attribution as a
        # candidate on nothing but our say-so.
        if failing_rails and not battery_adverse and v is not None:
            records = tuple(
                _mark_distribution(r, failing_rails, bat.name)
                for r in records)

        return DomainResult(domain=DOMAIN, records=tuple(records),
                            unevaluated=unevaluated)

    def declaration(self) -> dict:
        d = super().declaration()
        covered = set(self.affected_functions)
        covered.update(self._fns(self.battery))
        for r in self.rails:
            covered.update(self._fns(r))
        d["affected_functions"] = sorted(covered)
        d["rails"] = [{"name": r.name, "nominal_v": r.nominal_v,
                       "warn_frac": r.warn_frac, "fail_frac": r.fail_frac,
                       "depends_on": list(r.depends_on),
                       "affected_functions": list(self._fns(r))}
                      for r in self.rails]
        d["battery"] = self.battery.name
        return d


def _mark_distribution(record, failing_rails, battery_name):
    """Add the battery-exonerated finding to a failing rail's record."""
    if record.relation != "power.rail_tolerance" or not record.is_adverse:
        return record
    if record.observation_state is ObservationState.UNAVAILABLE:
        return record
    detail = dict(record.detail)
    detail["source_exonerated"] = battery_name
    detail["finding"] = ("source healthy and this rail is not: the "
                         "regulator/distribution path is the candidate, "
                         "not the battery")
    return replace(
        record,
        reason_codes=tuple(record.reason_codes) + (POWER_DISTRIBUTION_SUSPECT,),
        detail=detail)


def _f(x):
    """float or None. A non-numeric reading is missing, not zero."""
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
