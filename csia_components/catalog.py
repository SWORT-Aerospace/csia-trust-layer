"""What can be cross-checked on an autonomous platform BESIDES its sensors.

STATUS: SPECIFICATION AND REFERENCE IMPLEMENTATION. NOT VALIDATED.
-------------------------------------------------------------------
Nothing here has been run against a real vehicle, a real actuator, or a real
power bus. There is no component-fault simulator in this repository and no
recorded component-fault data of any kind. Every number a consumer of this
module produces today comes from synthetic telemetry written to exercise the
code. Read `UNVALIDATED_CLAIMS` at the bottom before quoting any of it.

WHY THE EXTENSION IS EVEN POSSIBLE, AND IT IS ONE MEASURED FACT
----------------------------------------------------------------
`csia/trust_engine/engine.py` -- the frozen core -- is NODE-AGNOSTIC. It has
no concept of a sensor. `TrustCore(names, cfg).step(edges, phys, hist, vr,
fresh)` takes arbitrary node names and arbitrary edges carrying a residual
and a gate, and runs the Beta recursion over whatever it is given. Driving it
over nodes called `esc_fl`, `pack` and `cpu` works today and changes nothing.

So extending CSIA past its sensors needs NO frozen change. It needs two
things the frozen core does not supply: the RELATIONS that must hold between
component observables, and the GATES that say when each relation is
observable at all.

THE ABSTRACTION, STATED ONCE
-----------------------------
A CSIA edge is not "two sensors". It is:

    a constraint that must hold between observable quantities whenever the
    components it spans are healthy, plus a gate saying when the constraint
    is checkable.

Sensor edges are one family of that: two independent measurements of one
physical quantity. The families below are the others, and they are what every
automated vehicle has regardless of what it is -- an aircraft, a ground
vehicle, a surface vessel, a fixed robot.

THE TWO PROBLEMS THAT MAKE THIS HARDER THAN THE SENSOR CASE
------------------------------------------------------------
These are not caveats appended to a working design. They are the reasons a
naive port of the sensor graph to actuators would produce a confident,
useless instrument.

**1. CLOSED-LOOP MASKING, AND IT INVERTS THE OBVIOUS EDGE.**
The intuitive actuator check is "commanded versus achieved". On any vehicle
with a controller that is the WRONG residual, because the controller exists
precisely to drive it to zero. A motor losing thrust authority does not show
up as a velocity error; it shows up as the controller quietly commanding more
throttle to hold the same velocity. The fault hides in the plant output and
appears in the CONTROL EFFORT.

So the informative residual is usually on the command side: effort rising
while output holds nominal. `EFFORT_DRIFT` below is that relation, and it is
the one most likely to matter on a real vehicle. This is the same shape as
the finding that a better predictor can track a fault and hide it (MX-030) --
a compensating element upstream of the residual destroys the residual.

**2. BLAME IS AMBIGUOUS IN A WAY IT IS NOT BETWEEN TWO IMUs.**
Two IMUs measuring the same acceleration are PEERS: if they disagree, one of
them is wrong and nothing else is implicated. A command and its effect are
not peers. If commanded thrust and measured acceleration disagree, the fault
may be the ESC, the motor, the propeller, the airframe, or the accelerometer
that measured the effect -- and the last of those is a SENSOR node that the
existing graph already scores.

The frozen core's trust-weighted averaging handles part of this: a partner
already distrusted contributes less. It does NOT encode causal direction, so
an actuator edge cannot by itself say which end failed. Every relation below
therefore records `blames`, the set of nodes a violation implicates, and a
consumer that reads a two-node edge as naming one culprit is reading it
wrong.

**3. AND MOST COMPONENT CHECKS NEED EXCITATION.**
A stuck servo and a healthy servo nobody asked to move produce identical
telemetry. A brake that will not engage is invisible until it is asked to.
Sensor cross-checks are passive; most of these are not. Each relation
carries `gate`, the condition under which it carries information at all, and
outside that condition the edge weight is ZERO -- absence of evidence, held
at the prior, never scored as agreement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Constraint families. The family decides what kind of residual is formed
#: and how a violation should be read, so it is carried explicitly rather
#: than inferred from a relation's name.
REDUNDANCY = "REDUNDANCY"        # two observations of one quantity (sensors)
CONSERVATION = "CONSERVATION"    # a physical identity that must balance
ACTUATION = "ACTUATION"          # a command and its observed effect
EFFORT = "EFFORT"                # control effort required to hold an output
TIMING = "TIMING"                # a nominal rate or deadline vs the observed
THERMAL = "THERMAL"              # dissipated power vs temperature rise
INTEGRITY = "INTEGRITY"          # sequence, checksum, error-rate accounting
KINEMATIC = "KINEMATIC"          # geometry constraints among motion channels

FAMILIES = (REDUNDANCY, CONSERVATION, ACTUATION, EFFORT, TIMING, THERMAL,
            INTEGRITY, KINEMATIC)


@dataclass(frozen=True)
class Relation:
    """One checkable constraint between component observables."""

    key: str
    family: str
    #: The nodes the constraint spans. Two for an edge the frozen core can
    #: consume directly; more for a constraint that must first be reduced
    #: to pairwise form (`reduces_to`).
    nodes: tuple
    #: What must hold when everything involved is healthy, in words. Not a
    #: formula, because the formula is platform-specific and inventing one
    #: here would be inventing a number.
    holds_when: str
    #: The observables each side needs. A platform that does not publish
    #: them cannot run this relation, and saying so is the point.
    requires: tuple
    #: WHEN IT CARRIES INFORMATION. Outside this the edge weight is zero.
    gate: str
    #: Which nodes a violation implicates. Never one, for anything but
    #: REDUNDANCY.
    blames: tuple
    #: What this relation CANNOT see, stated because a relation whose blind
    #: spot is undocumented will be read as covering it.
    blind_to: str
    #: Platforms this applies to. "all" means every powered, actuated,
    #: computer-controlled vehicle.
    platforms: str = "all"
    reduces_to: tuple = field(default_factory=tuple)


#: THE CATALOGUE.
#:
#: Ordered by how universal the relation is, not by how interesting. The
#: first four exist on every automated platform that has a battery, an
#: actuator, a processor and a bus -- which is all of them.
RELATIONS = (
    # ---------------------------------------------------------- CONSERVATION
    Relation(
        key="power_balance",
        family=CONSERVATION,
        nodes=("power_source", "power_loads"),
        holds_when=("current drawn from the source equals the sum of branch "
                    "currents plus quiescent draw, within measurement error"),
        requires=("source current", "per-branch or per-load current"),
        gate="both currents fresh; source not in a charging or regen state",
        blames=("power_source", "power_loads", "the current sensing itself"),
        blind_to=("a fault that draws NORMAL current -- a motor turning at "
                  "the right speed against the wrong load looks identical "
                  "until something else disagrees"),
    ),
    Relation(
        key="source_impedance",
        family=CONSERVATION,
        nodes=("power_source", "power_loads"),
        holds_when=("terminal voltage sags with drawn current along the "
                    "source's own internal resistance"),
        requires=("terminal voltage", "drawn current"),
        gate=("current varying enough to separate the slope from noise -- a "
              "constant load cannot identify an impedance"),
        # The slope is measured FROM the voltage and current channels, so a
        # bad shunt or a bad voltage reference moves it exactly as a
        # degrading source does. Naming only the source would point at the
        # one node this relation cannot actually distinguish from the other
        # two.
        blames=("power_source", "voltage_sensing", "current_sensing"),
        blind_to=("a source whose impedance has risen uniformly and whose "
                  "nominal impedance is unknown; this measures a CHANGE "
                  "against a reference, not an absolute health"),
    ),
    Relation(
        key="charge_accounting",
        family=CONSERVATION,
        nodes=("power_source", "energy_estimator"),
        holds_when=("integrated current matches the reported state of charge "
                    "delta over the same window"),
        requires=("current", "reported state of charge"),
        gate="window long enough that integration error is below the delta",
        blames=("power_source", "energy_estimator"),
        blind_to="a coulomb counter and a fuel gauge that share one bad shunt",
    ),
    # ------------------------------------------------------------- ACTUATION
    Relation(
        key="actuator_response",
        family=ACTUATION,
        nodes=("actuator", "motion_sensor"),
        holds_when=("the observed effect follows the commanded input through "
                    "the platform's own plant model, within its lag"),
        requires=("the command as issued", "an observable effect"),
        gate=("the command is EXCITING -- outside a commanded change, a "
              "stuck actuator and a healthy idle one are identical"),
        blames=("actuator", "the plant", "motion_sensor"),
        blind_to=("anything the controller has already compensated; see "
                  "`effort_drift`, which is the residual that survives a "
                  "closed loop"),
    ),
    Relation(
        key="actuator_agreement",
        family=REDUNDANCY,
        nodes=("actuator_a", "actuator_b"),
        holds_when=("actuators in a symmetric group draw symmetric effort "
                    "for a symmetric command"),
        requires=("per-actuator effort or feedback", "the commanded set"),
        gate=("the commanded set IS symmetric -- during a deliberate "
              "asymmetric manoeuvre the constraint does not hold"),
        blames=("actuator_a", "actuator_b"),
        blind_to=("a common-mode degradation across the whole group, which "
                  "is exactly what wear, temperature and a low bus voltage "
                  "produce"),
    ),
    # ---------------------------------------------------------------- EFFORT
    Relation(
        key="effort_drift",
        family=EFFORT,
        nodes=("controller", "actuator"),
        holds_when=("the control effort needed to hold a given output stays "
                    "stationary while the operating point does"),
        requires=("commanded effort", "the output being held",
                  "enough of the operating point to normalise by"),
        gate=("the operating point is STATIONARY -- effort is supposed to "
              "change when the demand does, and this relation says nothing "
              "during a manoeuvre"),
        blames=("actuator", "the plant", "controller"),
        blind_to=("a fault that appears and saturates faster than the "
                  "stationarity window; this is a SLOW-degradation "
                  "detector by construction"),
    ),
    # ---------------------------------------------------------------- TIMING
    Relation(
        key="loop_rate",
        family=TIMING,
        nodes=("compute", "scheduler"),
        holds_when="the observed period of a periodic task matches its nominal",
        requires=("per-task timestamps or a period measurement",
                  "the configured nominal"),
        gate="the task is supposed to be running in the current mode",
        blames=("compute", "scheduler", "whatever the task waits on"),
        blind_to=("a task that runs on time and computes the wrong answer; "
                  "this is a liveness check and not a correctness one"),
    ),
    Relation(
        key="bus_rate",
        family=TIMING,
        nodes=("bus", "endpoint"),
        holds_when=("frames from an endpoint arrive at the rate that "
                    "endpoint is configured to publish"),
        requires=("arrival timestamps per source", "the configured rate"),
        gate="the endpoint is powered and expected to be publishing",
        blames=("bus", "endpoint", "the receiving stack"),
        blind_to=("an endpoint publishing at the right rate with stale "
                  "content, which is what a frozen driver looks like"),
    ),
    Relation(
        key="clock_agreement",
        family=REDUNDANCY,
        nodes=("clock_a", "clock_b"),
        holds_when=("two independent time sources advance at the same rate, "
                    "within their combined specified drift"),
        requires=("two clocks readable in one operation",),
        gate="both clocks readable; neither mid-step from an external sync",
        blames=("clock_a", "clock_b"),
        blind_to=("both clocks derived from one oscillator, which is the "
                  "usual case on a single board and makes this relation "
                  "INAPPLICABLE rather than passing"),
    ),
    # --------------------------------------------------------------- THERMAL
    Relation(
        key="thermal_rise",
        family=THERMAL,
        nodes=("dissipator", "temperature"),
        holds_when=("temperature rise above ambient tracks dissipated power "
                    "through the component's own thermal time constant"),
        requires=("a power or current proxy", "a temperature", "an ambient"),
        gate=("the thermal time constant has elapsed since the last large "
              "power change; a step in power says nothing immediately"),
        blames=("dissipator", "the cooling path", "temperature"),
        blind_to=("a fault with no thermal signature at all -- a control "
                  "error, a software fault, a sensor bias"),
    ),
    # ------------------------------------------------------------- INTEGRITY
    Relation(
        key="sequence_continuity",
        family=INTEGRITY,
        nodes=("link", "endpoint"),
        holds_when="sequence numbers advance by one per delivered frame",
        requires=("a sequence field",),
        gate="the link is up and the endpoint is transmitting",
        blames=("link", "endpoint"),
        blind_to=("corruption that preserves the sequence field, and any "
                  "link that carries no sequence number at all"),
    ),
    Relation(
        key="error_rate",
        family=INTEGRITY,
        nodes=("link", "link_statistics"),
        holds_when=("checksum failures, retransmits and corrected errors "
                    "stay at the rate this installation established when "
                    "healthy"),
        requires=("error counters", "a healthy-baseline rate"),
        gate=("a baseline exists for THIS installation -- a fleet number is "
              "not a baseline for one vehicle"),
        # A rate is counter over window. A stuck or miscounting counter, and
        # a baseline taken while the link was ALREADY degraded, both move
        # the comparison without the link changing at all.
        blames=("link", "link_statistics", "the baseline itself"),
        blind_to="an error mechanism the counters do not count",
    ),
    # ------------------------------------------------------------- KINEMATIC
    Relation(
        key="wheel_consistency",
        family=KINEMATIC,
        nodes=("wheel_group", "steering"),
        holds_when=("individual wheel speeds satisfy the vehicle's steering "
                    "geometry for the commanded steering angle"),
        requires=("per-wheel speed", "steering angle"),
        gate="no wheel slipping; vehicle actually moving",
        blames=("wheel_group", "steering", "the speed pickups"),
        blind_to="a uniform scale error across every wheel",
        platforms="ground vehicles with two or more driven wheels",
    ),
    Relation(
        key="odometry_inertial",
        family=REDUNDANCY,
        nodes=("odometry", "inertial"),
        holds_when=("distance from wheel or propeller odometry matches the "
                    "double-integrated inertial estimate over a short "
                    "window"),
        requires=("an odometry channel", "an inertial channel"),
        gate=("window short enough that inertial integration drift stays "
              "below the comparison"),
        blames=("odometry", "inertial"),
        blind_to="slip, current, and anything that moves the vehicle without "
                 "turning the wheels",
        platforms="any platform with both odometry and inertial sensing",
    ),
)


def by_family(family: str) -> tuple:
    return tuple(r for r in RELATIONS if r.family == family)


def universal() -> tuple:
    """The relations that apply to every automated platform."""
    return tuple(r for r in RELATIONS if r.platforms == "all")


#: WHAT IS NOT ESTABLISHED, IN ONE PLACE SO IT CANNOT BE SKIPPED.
UNVALIDATED_CLAIMS = (
    "NO RELATION IN THIS CATALOGUE HAS BEEN MEASURED ON A REAL PLATFORM. "
    "There is no component-fault simulator in this repository and no "
    "recorded component-fault data, so no detection floor, no false-alarm "
    "rate and no latency is known for any of them. The sensor side of CSIA "
    "has a simulator with six fault kinds and a documented list of the "
    "phenomena that simulator CANNOT produce; the component side has "
    "neither, and is therefore in a strictly weaker evidential position "
    "than the sensor side, which is itself not validated on hardware.",

    "THE THRESHOLDS DO NOT EXIST. Every relation says what must hold and "
    "none says how far is too far, because that number is a property of a "
    "specific platform's noise and cannot be chosen from a desk. The "
    "procedure the supervision layer used for its own thresholds -- measure "
    "the clean-run minimum, place the threshold strictly below it with "
    "margin, and take an EXISTING constant rather than inventing a float -- "
    "is the procedure to follow, and it requires clean runs that do not "
    "exist yet.",

    "CLOSED-LOOP MASKING IS ARGUED, NOT MEASURED. The claim that "
    "commanded-versus-achieved is the wrong residual under a compensating "
    "controller follows from what a controller does, and the same shape was "
    "MEASURED on the predictor side (MX-030), but it has not been measured "
    "here. Until it is, `effort_drift` is a hypothesis about where the "
    "signal lives.",

    "BLAME ASSIGNMENT IS NOT SOLVED. Every non-REDUNDANCY relation "
    "implicates more than one node and the frozen core encodes no causal "
    "direction, so a component edge narrows a fault to a set and does not "
    "name a culprit. A consumer reading a two-node edge as naming one is "
    "reading it wrong.",

    "NO NOVELTY IS CLAIMED. Cross-checking actuators against plant models, "
    "power against conservation, and tasks against deadlines are standard "
    "practice in fault detection and isolation, and no prior-art search has "
    "been run -- every scholarly source has returned 403 from this "
    "environment. What is specific here is reusing ONE trust recursion "
    "across both kinds of node, and that is an engineering choice, not a "
    "result.",
)
