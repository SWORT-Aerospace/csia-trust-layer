"""A fault parameter that the sensor does not read is a fault that did not vary.

WHY THIS EXISTS
---------------
`Fault` validates its KIND against `KNOWN_KINDS` and raises on a typo, because
"a typo'd kind would otherwise be silently ignored by every sensor". Its
PARAMETERS get no such check. Each sensor model reads the keys it knows with
`f.params.get(name, default)` and silently substitutes its default for
anything else, so:

    Fault("power_sag", "battery", 20, 30, {"depth": 0.25})

is not an error, is not a warning, and is not a 0.25 V sag. It is the
battery's default 1.0 V sag, applied identically no matter what number you
write. A magnitude sweep built on that name sweeps nothing while producing a
perfectly plausible curve.

THAT HAPPENED, TWICE, IN ONE DAY (MX-030, MX-031). Three grids in the
predictor study named `depth`, `amp` and `rate` where the sensors read
`depth_v`, `amplitude` and `drift`; the config sweep repeated two of them.
The correct names were already written down correctly in
`csia_stress/falsify.py`, in a file I had read the same session. I wrote the
new grids from memory instead of from the authority.

THE CHECK IS BEHAVIOURAL, NOT A TABLE
--------------------------------------
`effective_params` samples the sensor twice with two different values of each
named parameter and reports which ones actually moved the output. A lookup
table would be a second copy of the sensor models, free to drift from them;
this cannot drift, because it asks the model itself.

`assert_effective` raises on any parameter that did not move anything, and
names the parameters that DID work on that sensor and kind, so the caller
gets the correction rather than just the complaint.
"""

from __future__ import annotations

import numpy as np

from csia.sensors import generate_flight
from csia.sensors.faults import Fault

#: Long enough that a fault window exists inside it and every sensor has
#: produced samples; short enough to run in a fraction of a second.
_PROBE_SECONDS = 8.0
_PROBE_START, _PROBE_LEN = 2.0, 5.0

#: Two values far enough apart that any parameter with an effect shows one.
#: Both are finite and positive so they are legal for every parameter shape
#: currently in use; vector-valued parameters are handled separately.
_LOW, _HIGH = 0.01, 50.0

#: Parameters whose value is a vector rather than a scalar. Probing these
#: with a scalar would raise inside the sensor rather than report a missing
#: parameter, which is a different failure and must not be confused with one.
_VECTOR_PARAMS = {"drift"}

#: Parameters that select rather than scale -- an axis index, a channel name.
#: A magnitude probe on them is meaningless, so they are checked for
#: EFFECT at two legal values of their own kind instead of at _LOW/_HIGH.
_CHOICE_PARAMS = {"axis": (0, 2), "channel": ("accel", "gyro")}


def _make_sensor(name: str, seed: int = 0):
    from csia.sensors.barometer import Barometer
    from csia.sensors.battery import Battery
    from csia.sensors.gps import GPS
    from csia.sensors.imu import IMU
    from csia.sensors.magnetometer import Magnetometer
    from csia.sensors.motor import MotorESC
    from csia.sensors.vibration import VibrationSensor
    ctor = {"imu0": lambda: IMU("imu0", seed=seed),
            "imu1": lambda: IMU("imu1", seed=seed),
            "baro": lambda: Barometer(seed=seed),
            "mag": lambda: Magnetometer(seed=seed),
            "gps": lambda: GPS(seed=seed),
            "motor_esc": lambda: MotorESC(seed=seed),
            "battery": lambda: Battery(seed=seed),
            "vibration": lambda: VibrationSensor(seed=seed)}.get(name)
    if ctor is None:
        raise ValueError(f"unknown sensor {name!r}")
    return ctor()


def _probe_values(param: str):
    if param in _CHOICE_PARAMS:
        return _CHOICE_PARAMS[param]
    if param in _VECTOR_PARAMS:
        return ((_LOW, 0.0, 0.0), (_HIGH, 0.0, 0.0))
    return (_LOW, _HIGH)


def _differs(sensor_name: str, kind: str, param: str, truth) -> bool:
    """Does changing this one parameter change the sensor's output?"""
    lo, hi = _probe_values(param)
    outs = []
    for value in (lo, hi):
        fault = Fault(kind, sensor_name, _PROBE_START, _PROBE_LEN,
                      {param: value})
        # A FRESH SENSOR EACH TIME, at the same seed. Reusing one would
        # advance its generator between the two samples and report a
        # difference that is noise rather than the parameter.
        outs.append(_make_sensor(sensor_name).sample(truth, (fault,)))
    a, b = outs
    for key in a:
        if key in ("t", "valid") or key not in b:
            continue
        if not np.array_equal(np.asarray(a[key], dtype=float),
                              np.asarray(b[key], dtype=float)):
            return True
    return False


def effective_params(sensor: str, kind: str, params) -> dict:
    """param -> whether varying it changes what the sensor produces."""
    truth = generate_flight(duration=_PROBE_SECONDS, profile="hover_circle")
    return {p: _differs(sensor, kind, p, truth) for p in params}


def known_effective(sensor: str, kind: str, candidates=None) -> list:
    """Which parameter names this sensor actually reads for this kind.

    Used for the "did you mean" half of an error message. `candidates`
    defaults to every parameter name any sensor model reads, so a caller who
    guessed wrong is told what was available.
    """
    pool = candidates or ("rate", "rate_hz", "amplitude", "depth_v",
                          "rpm_loss", "gain", "drift", "axis", "channel",
                          "spoof_velocity")
    got = effective_params(sensor, kind, pool)
    return sorted(p for p, ok in got.items() if ok)


def assert_effective(sensor: str, kind: str, params) -> None:
    """Raise unless every named parameter actually reaches the sensor.

    NOT A WARNING. A sweep whose magnitude parameter is inert produces a
    curve that looks fine and means nothing, and a warning in a log is not
    what stops that from being published.
    """
    if not params:
        return
    got = effective_params(sensor, kind, params)
    dead = sorted(p for p, ok in got.items() if not ok)
    if not dead:
        return
    usable = known_effective(sensor, kind)
    raise ValueError(
        f"{sensor}/{kind}: parameter(s) {dead} do not change this sensor's "
        f"output, so every magnitude you set for them is the sensor's own "
        f"default and any sweep over them measures nothing. "
        f"Parameters this sensor DOES read for {kind!r}: {usable or 'none'}")


def assert_any_effective(sensor: str, kind: str, params) -> None:
    """Raise only if NONE of the named parameters reaches the sensor.

    THE WEAKER CHECK, AND IT IS THE RIGHT ONE FOR A SUPERSET.
    `falsify.WORST_PARAMS` holds one parameter dict PER KIND, applied to
    whichever sensor is being faulted, so it necessarily carries keys some
    targets do not read: `power_sag` names both `depth_v` (battery) and
    `rpm_loss` (motor), and `bias_drift` names `axis` and `channel`, which
    only the IMU reads. Demanding that every key bite on every target would
    fail that table for being correctly written.

    What actually matters there is that the magnitude is CONTROLLABLE on the
    target -- that at least one key reaches it -- because a target where none
    do is being faulted at its default while the table claims a worst case.

    Use `assert_effective` instead wherever a SPECIFIC named parameter is the
    swept axis; there, one dead key is a sweep that measures nothing.
    """
    if not params:
        return
    got = effective_params(sensor, kind, params)
    if any(got.values()):
        return
    usable = known_effective(sensor, kind)
    raise ValueError(
        f"{sensor}/{kind}: NONE of {sorted(params)} changes this sensor's "
        f"output, so this fault runs at the sensor's own default and any "
        f"claim that it is a worst case is unfounded. "
        f"Parameters this sensor DOES read for {kind!r}: {usable or 'none'}")


def assert_fault_effective(fault: Fault) -> None:
    """`assert_effective` for an already-built Fault."""
    assert_effective(fault.target, fault.kind, list(fault.params))
