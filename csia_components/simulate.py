"""A component-level platform simulator, written from physics not from checks.

THE CIRCULARITY THIS IS BUILT TO AVOID, STATED FIRST
------------------------------------------------------
Validating a relation against a simulator written by the same person, in the
same week, is worth very little if the simulator is written FROM the relation.
"Detector finds the thing the generator generates" is self-consistency, not
evidence.

Three things are done about that, and none of them removes the limitation:

  1. THIS FILE IMPLEMENTS PHYSICS AND NEVER MENTIONS A RELATION. A pack has an
     open-circuit voltage and an internal resistance; a motor converts current
     to torque with a constant; a dissipating body warms toward an
     equilibrium with a time constant. The residuals live in `residuals.py`
     and this module does not import them.

  2. THE CLAIMS BEING TESTED WERE COMMITTED BEFORE THIS FILE EXISTED. Each
     relation in `catalog.py` already declares its gate, the nodes it blames,
     and WHAT IT IS BLIND TO, written on 2026-09-11 with no simulator in the
     repository. Testing them now is a prediction test: a relation that
     detects what it declared itself blind to, or misses what it claimed, is
     a falsification of something written down in advance.

  3. THE INTERESTING OUTPUTS ARE NOT "DOES IT FIRE". They are the DETECTION
     FLOOR against this platform's own noise, the FALSE-ALARM behaviour on
     clean runs, whether the GATE actually gates, and whether a fault in one
     component lights up relations that should not see it. None of those is
     settled by writing both halves.

WHAT REMAINS TRUE WHATEVER THIS PRODUCES: no number here is a measurement of
any real vehicle. A simulator's detection floor is a floor against simulated
noise, and the phenomena a simulator cannot produce are exactly the ones it
cannot warn you about.

THE PLATFORM
------------
A four-rotor electric vehicle, because it is what the rest of this repository
models and because it exercises power, actuation, timing, thermal and link
integrity at once. Nothing here is specific to flight: the same pack, ESCs,
loop and bus exist on a ground robot.

    pack ---> 4 x (esc -> motor -> rotor)      thrust -> vertical dynamics
     |                 |
     |                 +--> current, rpm, temperature
     +--> terminal voltage, pack current

    controller: holds a vertical-velocity setpoint by commanding duty
    cpu:        runs the controller on a nominal period
    canbus:     carries telemetry frames with sequence numbers

THE CONTROLLER IS THE POINT, NOT FURNITURE. It closes the loop, so a motor
that loses efficiency does NOT produce a velocity error -- the controller
commands more duty and holds the setpoint. That is the masking effect
`catalog.py` predicts, and without a real controller this simulator could not
test the prediction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# --- plant constants -------------------------------------------------------
#
# Rounded, plausible values for a small electric multirotor. They set the
# SCALE of every residual, so they are stated here once and never re-derived
# at a call site.

MASS_KG = 1.5
G = 9.80665
N_MOTORS = 4

#: Pack: 4-cell lithium. OCV falls roughly linearly with state of charge over
#: the usable band, and the internal resistance is the quantity a degrading
#: pack changes.
PACK_OCV_FULL = 16.8
PACK_OCV_EMPTY = 14.0
PACK_R_NOMINAL = 0.040          # ohm
PACK_CAPACITY_AH = 4.0

#: Motor: thrust proportional to rpm squared; current proportional to torque,
#: and torque to thrust. `K_THRUST` is set so four motors hover the mass.
HOVER_RPM = 6000.0
K_THRUST = (MASS_KG * G / N_MOTORS) / (HOVER_RPM ** 2)
#: Amps per newton of TORQUE-PRODUCING thrust. Set so four motors at hover
#: draw ~23 A from a 4S pack, which is the right order for a 1.5 kg vehicle.
K_CURRENT = 1.6
ESC_R = 0.030                   # ohm, ESC + winding, sets I^2R dissipation
QUIESCENT_A = 0.45              # avionics draw, not through the ESCs

#: Thermal: a body warming toward equilibrium. `THERMAL_K` is the rise per
#: watt at equilibrium and `THERMAL_TAU` how long it takes to get there.
AMBIENT_C = 22.0
THERMAL_K = 3.2                 # kelvin per watt
THERMAL_TAU = 25.0              # second

#: Compute and link.
LOOP_HZ = 50.0
BUS_HZ = 100.0

#: Measurement noise, one sigma. These set every detection floor in this
#: simulator, so a floor expressed in these units is meaningful and a floor
#: in absolute units is not transferable to a real vehicle.
SIGMA = {
    "pack_current": 0.08,       # A
    "pack_voltage": 0.020,      # V
    "branch_current": 0.05,     # A, per ESC
    "rpm": 25.0,                # rpm
    "temperature": 0.35,        # K
    "loop_period": 0.0006,      # s
    "vz": 0.05,                 # m/s
}

#: Fault kinds. Each is a PHYSICAL degradation, named for what breaks in the
#: hardware, not for the check that might find it.
FAULT_KINDS = (
    "esc_efficiency_loss",   # less thrust per amp: worn MOSFETs, demagnetised
    "bearing_friction",      # more current AND more heat for the same rpm
    "pack_impedance_rise",   # aged cells: same OCV, higher internal R
    "shunt_bias",            # a current SENSOR reads wrong; hardware is fine
    "thermal_path_loss",     # same dissipation, worse cooling
    "cpu_overrun",           # the control loop takes longer than its period
    "bus_drops",             # frames lost on the link
)


@dataclass
class Fault:
    kind: str
    target: str
    start: float
    duration: float
    #: Magnitude, in the units the kind's own physics uses. Documented per
    #: kind in `_apply_fault`; there is no shared scale and pretending there
    #: is one would invite comparing a resistance to a frame-loss rate.
    magnitude: float = 0.0

    def __post_init__(self):
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"unknown component fault {self.kind!r}; "
                             f"known: {sorted(FAULT_KINDS)}")

    def active(self, t: float) -> bool:
        return self.start <= t < self.start + self.duration


@dataclass
class Telemetry:
    """What the platform publishes. One row per control tick."""

    t: list = field(default_factory=list)
    pack_voltage: list = field(default_factory=list)
    pack_current: list = field(default_factory=list)
    branch_current: list = field(default_factory=list)     # per motor
    rpm: list = field(default_factory=list)
    temperature: list = field(default_factory=list)        # per motor
    ambient: list = field(default_factory=list)
    duty: list = field(default_factory=list)               # commanded, per motor
    vz: list = field(default_factory=list)
    vz_setpoint: list = field(default_factory=list)
    loop_period: list = field(default_factory=list)
    soc: list = field(default_factory=list)
    coulombs: list = field(default_factory=list)
    seq: list = field(default_factory=list)
    frames_ok: list = field(default_factory=list)
    frames_err: list = field(default_factory=list)
    clock_a: list = field(default_factory=list)
    clock_b: list = field(default_factory=list)

    def array(self, name: str) -> np.ndarray:
        return np.asarray(getattr(self, name), dtype=float)


def _ocv(soc: float) -> float:
    return PACK_OCV_EMPTY + (PACK_OCV_FULL - PACK_OCV_EMPTY) * max(
        0.0, min(1.0, soc))


class Platform:
    """The plant, its controller, and its telemetry.

    Deterministic given a seed, like the sensor simulator, so a campaign can
    run independent noise realisations by offsetting it.
    """

    def __init__(self, seed: int = 0, duration: float = 60.0,
                 setpoint=None):
        self.rng = np.random.default_rng(seed)
        self.duration = duration
        self.dt = 1.0 / LOOP_HZ
        #: Vertical-velocity demand. A CONSTANT setpoint is what makes
        #: `effort_drift` checkable: the relation is gated on a stationary
        #: operating point, so a campaign that manoeuvred throughout would
        #: gate it out everywhere and measure nothing.
        self.setpoint = setpoint or (lambda t: 0.0)

    def run(self, faults=()) -> Telemetry:
        tel = Telemetry()
        dt = self.dt
        n = int(self.duration / dt)

        soc = 0.95
        coulombs = 0.0
        temp = np.full(N_MOTORS, AMBIENT_C)
        vz = 0.0
        # Integral term: this is the memory that lets the controller
        # compensate a slow degradation, and therefore the thing that hides
        # it from the plant output.
        integral = 0.0
        seq = 0
        frames_ok = frames_err = 0
        clock_b_drift = 0.0
        elapsed = 0.0

        for i in range(n):
            t = i * dt
            active = [f for f in faults if f.active(t)]

            # ---- controller ------------------------------------------------
            target = float(self.setpoint(t))
            err = target - vz
            integral += err * dt
            # Hover duty plus a PI correction. Duty is the CONTROL EFFORT and
            # is what rises when the plant weakens.
            duty = np.full(N_MOTORS, 1.0 + 0.06 * err + 0.10 * integral)
            duty = np.clip(duty, 0.0, 2.0)

            # ---- plant -----------------------------------------------------
            eff = np.ones(N_MOTORS)          # thrust efficiency per motor
            friction = np.zeros(N_MOTORS)    # extra current, amps
            pack_r = PACK_R_NOMINAL
            shunt_gain = 1.0
            thermal_k = np.full(N_MOTORS, THERMAL_K)
            loop_stretch = 0.0
            drop_rate = 0.0

            for f in active:
                (eff, friction, pack_r, shunt_gain, thermal_k, loop_stretch,
                 drop_rate) = _apply_fault(
                    f, eff, friction, pack_r, shunt_gain, thermal_k,
                    loop_stretch, drop_rate)

            rpm = duty * HOVER_RPM
            # THE EFFICIENCY SPLIT IS THE WHOLE POINT OF THIS MODEL.
            # A motor draws current for the torque it produces. An
            # efficiency loss means that torque does NOT become thrust --
            # a damaged prop, a demagnetised rotor, a mistimed ESC. So
            # current tracks the IDEAL thrust and the airframe receives the
            # ACTUAL. Modelling current against actual thrust instead would
            # make an efficiency loss invisible in every electrical channel,
            # which is not what a worn motor does.
            thrust_ideal = K_THRUST * rpm ** 2
            thrust = eff * thrust_ideal
            branch_a = np.maximum(K_CURRENT * thrust_ideal + friction, 0.0)
            pack_a = float(branch_a.sum()) + QUIESCENT_A
            v_term = _ocv(soc) - pack_a * pack_r

            accel = (float(thrust.sum()) - MASS_KG * G) / MASS_KG
            vz += accel * dt

            dissipation = branch_a ** 2 * ESC_R
            equilibrium = AMBIENT_C + thermal_k * dissipation
            temp += (equilibrium - temp) * (dt / THERMAL_TAU)

            coulombs += pack_a * dt
            soc -= pack_a * dt / (PACK_CAPACITY_AH * 3600.0)

            period = dt + loop_stretch
            # ELAPSED TIME ADVANCES BY THE ACTUAL PERIOD, not the nominal.
            # `clock_a` previously used i*dt while the loop was stretched,
            # so a scheduling fault silently desynchronised the two clocks
            # and `clock_agreement` reported a 4e7-fold excursion on a fault
            # with no clock involvement. Caught by the cross-relation
            # matrix. A stretched loop makes wall time and tick count
            # diverge, and BOTH clocks must see the same wall time.
            elapsed += period
            clock_b_drift += period * 1.5e-6      # a real, specified drift

            # DRAW UNCONDITIONALLY. Drawing only when a drop is possible
            # made a bus_drops run consume a different number of random
            # numbers from a clean one, so every downstream noise sample
            # differed and unrelated residuals moved. The cross-relation
            # matrix caught it: `actuator_response` "detected" bus drops at
            # 1.3x the clean maximum, which no physics in this model
            # supports. Keeping the stream aligned makes a clean run and a
            # faulted run differ ONLY by the fault.
            roll = self.rng.random()
            if drop_rate > 0.0 and roll < drop_rate:
                frames_err += 1
                seq += 1                           # the frame existed, was lost
            else:
                frames_ok += 1
                seq += 1

            # ---- telemetry, with measurement noise -------------------------
            g = self.rng.normal
            tel.t.append(t)
            tel.pack_current.append(pack_a * shunt_gain
                                    + g(0, SIGMA["pack_current"]))
            tel.pack_voltage.append(v_term + g(0, SIGMA["pack_voltage"]))
            tel.branch_current.append(
                (branch_a + g(0, SIGMA["branch_current"], N_MOTORS)).tolist())
            tel.rpm.append((rpm + g(0, SIGMA["rpm"], N_MOTORS)).tolist())
            tel.temperature.append(
                (temp + g(0, SIGMA["temperature"], N_MOTORS)).tolist())
            tel.ambient.append(AMBIENT_C)
            tel.duty.append(duty.tolist())
            tel.vz.append(vz + g(0, SIGMA["vz"]))
            tel.vz_setpoint.append(target)
            tel.loop_period.append(period + g(0, SIGMA["loop_period"]))
            tel.soc.append(soc)
            tel.coulombs.append(coulombs)
            tel.seq.append(seq)
            tel.frames_ok.append(frames_ok)
            tel.frames_err.append(frames_err)
            tel.clock_a.append(elapsed)
            tel.clock_b.append(elapsed + clock_b_drift)

        return tel


def _apply_fault(f, eff, friction, pack_r, shunt_gain, thermal_k,
                 loop_stretch, drop_rate):
    """One fault's effect on the plant. MAGNITUDE UNITS ARE PER KIND.

    esc_efficiency_loss   fraction of thrust lost, 0..1, on motor `target`
    bearing_friction      extra amps drawn by motor `target`
    pack_impedance_rise   ohms added to the pack's internal resistance
    shunt_bias            multiplicative error on the PACK current SENSOR
    thermal_path_loss     fractional increase in kelvin-per-watt
    cpu_overrun           seconds added to the control period
    bus_drops             probability a frame is lost
    """
    idx = _motor_index(f.target)
    if f.kind == "esc_efficiency_loss":
        eff = eff.copy()
        eff[idx] *= max(0.0, 1.0 - f.magnitude)
    elif f.kind == "bearing_friction":
        friction = friction.copy()
        friction[idx] += f.magnitude
    elif f.kind == "pack_impedance_rise":
        pack_r = pack_r + f.magnitude
    elif f.kind == "shunt_bias":
        shunt_gain = shunt_gain * (1.0 + f.magnitude)
    elif f.kind == "thermal_path_loss":
        thermal_k = thermal_k.copy()
        thermal_k[idx] *= (1.0 + f.magnitude)
    elif f.kind == "cpu_overrun":
        loop_stretch = loop_stretch + f.magnitude
    elif f.kind == "bus_drops":
        drop_rate = max(drop_rate, f.magnitude)
    return (eff, friction, pack_r, shunt_gain, thermal_k, loop_stretch,
            drop_rate)


def _motor_index(target: str) -> int:
    """`esc0`..`esc3` select a motor; anything else is platform-wide.

    Returns 0 for a platform-wide target so the array operations stay valid;
    kinds that are platform-wide (`pack_impedance_rise`, `shunt_bias`,
    `cpu_overrun`, `bus_drops`) ignore the index entirely.
    """
    if target.startswith("esc") and target[3:].isdigit():
        i = int(target[3:])
        if not 0 <= i < N_MOTORS:
            raise ValueError(f"motor index out of range: {target!r}")
        return i
    return 0


#: Which fault kinds a given node can carry. Used by a campaign to avoid
#: constructing a fault the platform cannot express, the same role
#: `csia_stress.applicability` plays for the sensor side.
APPLICABLE = {
    "esc0": ("esc_efficiency_loss", "bearing_friction", "thermal_path_loss"),
    "esc1": ("esc_efficiency_loss", "bearing_friction", "thermal_path_loss"),
    "esc2": ("esc_efficiency_loss", "bearing_friction", "thermal_path_loss"),
    "esc3": ("esc_efficiency_loss", "bearing_friction", "thermal_path_loss"),
    "pack": ("pack_impedance_rise",),
    "current_sensing": ("shunt_bias",),
    "cpu": ("cpu_overrun",),
    "canbus": ("bus_drops",),
}


def applicable_faults() -> tuple:
    return tuple((node, kind) for node, kinds in sorted(APPLICABLE.items())
                 for kind in kinds)
