"""One residual per catalogued relation, computed from telemetry.

WHAT A RESIDUAL FUNCTION HERE RETURNS
--------------------------------------
`(residual, gate)` over a window.

    residual  the signed or unsigned quantity the relation says must be
              near zero when everything it spans is healthy
    gate      1.0 when the relation's declared gate is met, 0.0 when it is
              not. NEVER a soft weight: an unexcited or inapplicable check
              must contribute nothing at all, or absence of evidence becomes
              evidence of health.

The caller turns `residual` into the frozen core's `lam` with
`combined.normalised_residual(residual, scale)`. THE SCALE IS THE PART THAT
DOES NOT TRANSFER. Each function documents the scale that follows from the
simulator's declared measurement noise; on a real platform it has to be
measured from clean runs, and using the number from here would be using one
vehicle's noise floor on another.

THIS MODULE DOES NOT IMPORT THE SIMULATOR'S PLANT CONSTANTS WHERE IT CAN
AVOID IT. Where a relation genuinely needs a nominal -- the quiescent draw,
the loop period, the specified clock drift -- it is passed in by the caller
as a configuration value, because on a real vehicle it comes from a
datasheet or a commissioning run and not from the thing being checked.
"""

from __future__ import annotations

import numpy as np


def _win(tel, lo, hi):
    t = tel.array("t")
    return (t >= lo) & (t <= hi)


# --- CONSERVATION ----------------------------------------------------------

def power_balance(tel, lo, hi, quiescent_a: float):
    """Pack current against the sum of branch currents plus quiescent draw.

    Kirchhoff. Scale: the combined noise of the channels differenced, which
    for one pack sensor and four branch sensors is
    sqrt(sigma_pack^2 + 4 * sigma_branch^2).
    """
    w = _win(tel, lo, hi)
    pack = tel.array("pack_current")[w]
    branch = np.asarray(tel.branch_current, dtype=float)[w]
    resid = pack - (branch.sum(axis=1) + quiescent_a)
    return float(np.mean(resid)), 1.0


def source_impedance(tel, lo, hi, r_nominal: float,
                     min_current_sd: float = 0.25):
    """Terminal voltage against drawn current: the slope is -R.

    GATED ON CURRENT VARIATION. A constant load cannot identify an
    impedance -- the regression is then fitting noise against noise and
    returns a number with no meaning. `catalog.py` declares that gate and
    this is it.
    """
    w = _win(tel, lo, hi)
    i = tel.array("pack_current")[w]
    v = tel.array("pack_voltage")[w]
    if i.size < 10 or float(np.std(i)) < min_current_sd:
        return 0.0, 0.0
    slope = float(np.polyfit(i, v, 1)[0])
    return (-slope) - r_nominal, 1.0


def charge_accounting(tel, lo, hi, capacity_ah: float):
    """Integrated current against the reported state-of-charge delta."""
    w = _win(tel, lo, hi)
    coul = tel.array("coulombs")[w]
    soc = tel.array("soc")[w]
    if coul.size < 2:
        return 0.0, 0.0
    integrated = float(coul[-1] - coul[0])
    reported = float(soc[0] - soc[-1]) * capacity_ah * 3600.0
    return integrated - reported, 1.0


# --- ACTUATION and EFFORT --------------------------------------------------

def actuator_response(tel, lo, hi, k_thrust: float, mass_kg: float,
                      g: float = 9.80665):
    """Commanded thrust against observed acceleration.

    THE RELATION `catalog.py` PREDICTS WILL BE MASKED. The controller holds
    the setpoint, so the plant output carries no error even while the plant
    is degrading. Included precisely so the prediction can be tested rather
    than asserted.
    """
    w = _win(tel, lo, hi)
    rpm = np.asarray(tel.rpm, dtype=float)[w]
    vz = tel.array("vz")[w]
    t = tel.array("t")[w]
    if t.size < 10:
        return 0.0, 0.0
    predicted_accel = (k_thrust * (rpm ** 2).sum(axis=1)
                       - mass_kg * g) / mass_kg
    observed_accel = np.gradient(vz, t)
    return float(np.mean(predicted_accel - observed_accel)), 1.0


def actuator_agreement(tel, lo, hi, max_duty_spread: float = 1e-6):
    """Branch currents across a symmetrically commanded actuator group.

    GATED ON THE COMMAND BEING SYMMETRIC. During a deliberate asymmetric
    manoeuvre the constraint does not hold and the edge must contribute
    nothing.
    """
    w = _win(tel, lo, hi)
    duty = np.asarray(tel.duty, dtype=float)[w]
    branch = np.asarray(tel.branch_current, dtype=float)[w]
    if duty.size == 0:
        return 0.0, 0.0
    spread = float(np.mean(duty.max(axis=1) - duty.min(axis=1)))
    if spread > max_duty_spread:
        return 0.0, 0.0
    per_motor = branch.mean(axis=0)
    return float(per_motor.max() - per_motor.min()), 1.0


def effort_drift(tel, lo, hi, reference_effort: float,
                 max_setpoint_sd: float = 1e-6):
    """Control effort needed to hold a stationary operating point.

    THE RESIDUAL `catalog.py` ARGUES IS THE ONE THAT SURVIVES A CLOSED LOOP.
    Gated on the setpoint being stationary, because effort is supposed to
    change when the demand does.

    `reference_effort` is the effort this platform needs when healthy at
    this operating point. On a real vehicle that is a commissioning
    measurement; there is no way to derive it from the run being checked.
    """
    w = _win(tel, lo, hi)
    duty = np.asarray(tel.duty, dtype=float)[w]
    setpoint = tel.array("vz_setpoint")[w]
    if duty.size == 0 or float(np.std(setpoint)) > max_setpoint_sd:
        return 0.0, 0.0
    return float(np.mean(duty)) - reference_effort, 1.0


# --- TIMING ----------------------------------------------------------------

def loop_rate(tel, lo, hi, nominal_period: float):
    w = _win(tel, lo, hi)
    period = tel.array("loop_period")[w]
    if period.size == 0:
        return 0.0, 0.0
    return float(np.mean(period)) - nominal_period, 1.0


def bus_rate(tel, lo, hi, nominal_hz: float):
    """Delivered frames per second against the configured publish rate."""
    w = _win(tel, lo, hi)
    ok = tel.array("frames_ok")[w]
    t = tel.array("t")[w]
    if ok.size < 2 or t[-1] <= t[0]:
        return 0.0, 0.0
    observed = (ok[-1] - ok[0]) / (t[-1] - t[0])
    return float(observed - nominal_hz), 1.0


def clock_agreement(tel, lo, hi, specified_drift_rate: float):
    """Relative rate between two time sources against their specification."""
    w = _win(tel, lo, hi)
    a = tel.array("clock_a")[w]
    b = tel.array("clock_b")[w]
    if a.size < 10 or a[-1] <= a[0]:
        return 0.0, 0.0
    observed = ((b[-1] - b[0]) - (a[-1] - a[0])) / (a[-1] - a[0])
    return float(observed - specified_drift_rate), 1.0


# --- THERMAL ---------------------------------------------------------------

def thermal_rise(tel, lo, hi, thermal_k: float, esc_r: float, motor: int,
                 settle_s: float, fault_free_change_at=None):
    """Temperature rise above ambient against dissipated power.

    GATED ON THE THERMAL TIME CONSTANT HAVING ELAPSED since the last large
    power change. A step in power says nothing about the cooling path until
    the body has had time to respond, and scoring it immediately would
    report a healthy component as faulty for one time constant after every
    manoeuvre.
    """
    if fault_free_change_at is not None and lo < fault_free_change_at + settle_s:
        return 0.0, 0.0
    w = _win(tel, lo, hi)
    temp = np.asarray(tel.temperature, dtype=float)[w][:, motor]
    amb = tel.array("ambient")[w]
    branch = np.asarray(tel.branch_current, dtype=float)[w][:, motor]
    if temp.size == 0:
        return 0.0, 0.0
    dissipation = branch ** 2 * esc_r
    expected_rise = thermal_k * dissipation
    return float(np.mean((temp - amb) - expected_rise)), 1.0


# --- INTEGRITY -------------------------------------------------------------

def sequence_continuity(tel, lo, hi):
    """Gaps in the sequence field, as a fraction of frames expected."""
    w = _win(tel, lo, hi)
    seq = tel.array("seq")[w]
    ok = tel.array("frames_ok")[w]
    if seq.size < 2:
        return 0.0, 0.0
    expected = float(seq[-1] - seq[0])
    delivered = float(ok[-1] - ok[0])
    if expected <= 0:
        return 0.0, 0.0
    return (expected - delivered) / expected, 1.0


def error_rate(tel, lo, hi, baseline_rate: float):
    """Error counter rate against this installation's healthy baseline.

    GATED ON A BASELINE EXISTING. A fleet number is not a baseline for one
    vehicle, and without one this relation has nothing to compare against.
    """
    if baseline_rate is None:
        return 0.0, 0.0
    w = _win(tel, lo, hi)
    err = tel.array("frames_err")[w]
    t = tel.array("t")[w]
    if err.size < 2 or t[-1] <= t[0]:
        return 0.0, 0.0
    observed = (err[-1] - err[0]) / (t[-1] - t[0])
    return float(observed - baseline_rate), 1.0


#: relation key -> the function that computes its residual. Keys must match
#: `catalog.RELATIONS`; a test asserts the two agree, so a relation added to
#: the catalogue without a residual is a loud failure rather than a silent
#: gap in coverage.
RESIDUALS = {
    "power_balance": power_balance,
    "source_impedance": source_impedance,
    "charge_accounting": charge_accounting,
    "actuator_response": actuator_response,
    "actuator_agreement": actuator_agreement,
    "effort_drift": effort_drift,
    "loop_rate": loop_rate,
    "bus_rate": bus_rate,
    "clock_agreement": clock_agreement,
    "thermal_rise": thermal_rise,
    "sequence_continuity": sequence_continuity,
    "error_rate": error_rate,
}

#: Catalogued relations with NO residual here, and why. Listed rather than
#: omitted, so "12 of 14 validated" cannot be read as "14 of 14".
NOT_IMPLEMENTED = {
    "wheel_consistency": ("ground vehicles only; this simulator models a "
                          "rotor platform with no wheels or steering"),
    "odometry_inertial": ("needs an odometry channel this simulator does "
                          "not produce"),
}
