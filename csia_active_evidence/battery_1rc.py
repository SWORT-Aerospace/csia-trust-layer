"""An independent one-RC Thevenin pack, written as a PLANT and nothing else.

WHY THIS FILE EXISTS SEPARATELY
--------------------------------
`identifiability.py` derives what a least-squares estimate of resistance
does under a model `V = E - I R`. Checking that against a simulator that
assumes the same thing tests arithmetic. This plant deliberately does NOT
satisfy the estimator's model: it has a polarization state the estimator
has no term for, an open-circuit voltage that curves with state of charge,
a temperature coefficient, and a current channel with scale error and delay
as well as offset and noise.

    THIS MODULE IMPORTS NOTHING FROM THE ESTIMATOR UNDER TEST.
    `tests/test_rcec.py` asserts that by parsing the imports.

If the certificate still behaves correctly here, that is evidence it is not
merely re-deriving its own assumptions. If it does not, the certificate is
wrong and the campaign says so.

EVERY PARAMETER IS SYNTHETIC AND NORMALIZED
--------------------------------------------
There is no real cell data in this repository and none is obtainable from
this host. `SYNTHETIC_PACK` is a plausible small-vehicle pack in consistent
SI units and IT IS NOT A MEASUREMENT OF ANY CHEMISTRY. Nothing derived from
it may be described as characterising lithium polymer, NMC, LFP or any other
real cell. The work order is explicit: do not pretend invented pack
parameters represent a real battery, and this file does not.

WHAT IT DOES MODEL
------------------
    dz/dt   = -I / Q                        state of charge
    dV1/dt  = -V1/(R1 C1) + I/C1            polarization
    V       = OCV(z,T) - R0(T) I - V1 + bV + noise
    Itilde  = (1+sI) I(t - tau) + bI + noise, quantized

plus a first-order command-to-current lag, so a commanded waveform is not
the realized one -- the effect AE-F5 measured and this campaign is about.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, replace
from typing import Callable, Optional, Tuple

import numpy as np

SCHEMA = "csia.active_evidence.battery_1rc/1"

#: A plausible small-vehicle pack in SI units. SYNTHETIC. NOT A MEASUREMENT.
#: Named so that no reader can mistake it for characterisation data.
SYNTHETIC_PACK = dict(
    ocv_full=16.8,        # V at z=1
    ocv_empty=14.0,       # V at z=0
    ocv_curvature=0.45,   # V, the sag of the curve away from a straight line
    r0=0.040,             # ohm
    r0_temp_coeff=-3.0e-4,   # ohm per kelvin, resistance falls as cells warm
    r1=0.015,             # ohm, polarization
    c1=900.0,             # farad, polarization time constant r1*c1 = 13.5 s
    capacity_ah=4.0,
    t_ambient_c=22.0,
    thermal_rise_per_amp2=0.004,   # K per A^2, a crude self-heating term
)

#: Measurement chain. Also synthetic.
SYNTHETIC_SENSING = dict(
    sigma_v=0.020,        # V
    sigma_i=0.080,        # A
    bias_v=0.0,           # V
    bias_i=0.0,           # A
    scale_i=0.0,          # fractional gain error on the current channel
    quantum_v=0.0,        # V, 0 disables
    quantum_i=0.0,        # A
    delay_s=0.0,          # s, current-channel transport delay
    dropout=0.0,          # fraction of samples lost
)

#: Closed loop. `lag_s` is the command-to-current time constant: the reason a
#: palindromic command is not a palindromic current.
SYNTHETIC_LOOP = dict(lag_s=0.25, hz=50.0, base_current=20.0,
                      saturation_a=60.0)


@dataclass(frozen=True)
class PackParams:
    ocv_full: float
    ocv_empty: float
    ocv_curvature: float
    r0: float
    r0_temp_coeff: float
    r1: float
    c1: float
    capacity_ah: float
    t_ambient_c: float
    thermal_rise_per_amp2: float

    def ocv(self, z: float, t_c: float) -> float:
        """A curved open-circuit characteristic. NOT a fitted cell curve."""
        z = min(max(z, 0.0), 1.0)
        linear = self.ocv_empty + (self.ocv_full - self.ocv_empty) * z
        return linear - self.ocv_curvature * z * (1.0 - z) * 4.0

    def r0_at(self, t_c: float) -> float:
        return self.r0 + self.r0_temp_coeff * (t_c - self.t_ambient_c)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Sensing:
    sigma_v: float
    sigma_i: float
    bias_v: float
    bias_i: float
    scale_i: float
    quantum_v: float
    quantum_i: float
    delay_s: float
    dropout: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Loop:
    lag_s: float
    hz: float
    base_current: float
    saturation_a: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Trace:
    """What a flight log would contain. True values are kept SEPARATELY.

    `i_true` and `v_true` exist so a control can ask what the plant actually
    did. NOTHING in the certificate path may read them -- `rcec.py` takes
    `i_meas` and `v_meas` only, and a test asserts the signature.
    """

    t: np.ndarray
    i_meas: np.ndarray
    v_meas: np.ndarray
    i_true: np.ndarray
    v_true: np.ndarray
    i_command: np.ndarray
    z: np.ndarray
    temp_c: np.ndarray
    saturated: np.ndarray
    valid: np.ndarray          # False where telemetry dropped

    def window(self, lo: float, hi: float) -> "Trace":
        m = (self.t >= lo) & (self.t <= hi) & self.valid
        return Trace(*[getattr(self, f)[m] for f in
                       ("t", "i_meas", "v_meas", "i_true", "v_true",
                        "i_command", "z", "temp_c", "saturated", "valid")])

    @property
    def n(self) -> int:
        return int(self.t.size)


def _streams(seed: int):
    """Independent named streams, one per physical subsystem.

    A conditional fault branch must not advance an unrelated stream. Drawing
    each subsystem from its own generator is what makes that structural
    rather than a convention -- the defect MX-036 had to fix in the
    component simulator.
    """
    ss = np.random.SeedSequence(seed)
    names = ("process", "voltage_sensor", "current_sensor", "controller",
             "environment", "telemetry")
    children = ss.spawn(len(names))
    return {n: np.random.default_rng(c) for n, c in zip(names, children)}


def simulate(command: Callable[[float], float], *, duration: float,
             seed: int = 0, pack: Optional[PackParams] = None,
             sensing: Optional[Sensing] = None,
             loop: Optional[Loop] = None,
             r0_delta: float = 0.0, ocv_offset: float = 0.0,
             ocv_drift_v_per_s: float = 0.0,
             r1_scale: float = 1.0,
             unmodelled_ringing: float = 0.0,
             observer: Optional[Callable[[float, float, float], None]] = None
             ) -> Trace:
    """Run the pack. `command` returns EXCESS current demand in amps.

    `r0_delta`, `ocv_offset`, `ocv_drift_v_per_s`, `r1_scale` and
    `unmodelled_ringing` are the fault injections. `unmodelled_ringing` adds
    a second-order oscillation the estimator has NO term for and is the
    open-set case: nothing in the hypothesis bank can explain it.

    `observer`, when given, is called as `observer(t_k, i_meas_k, v_meas_k)`
    AFTER sample k is measured and BEFORE sample k+1 is commanded. It exists
    so a feedback probe can react to realized current without ever seeing a
    future sample.

    THE MEASUREMENT CHAIN IS APPLIED INSIDE THE LOOP FOR EXACTLY THIS
    REASON. It was originally vectorised after the loop, which made a
    per-tick observer impossible; the feedback arm was wired up, never
    called, and ran as a relabelled copy of the open-loop arm for a whole
    pilot campaign. The noise arrays are still drawn in one block, from the
    same independent streams, so the restructure is byte-identical and
    `tests/test_rcec.py` asserts that.
    """
    pack = pack or PackParams(**SYNTHETIC_PACK)
    sensing = sensing or Sensing(**SYNTHETIC_SENSING)
    loop = loop or Loop(**SYNTHETIC_LOOP)
    rng = _streams(seed)

    dt = 1.0 / loop.hz
    n = max(int(round(duration * loop.hz)), 8)
    t = np.arange(n, dtype=float) * dt

    alpha = dt / max(loop.lag_s, dt) if loop.lag_s > 0 else 1.0
    z = 1.0 - 0.15
    v1 = 0.0
    temp = pack.t_ambient_c
    i_real = loop.base_current

    i_true = np.empty(n)
    v_true = np.empty(n)
    i_cmd = np.empty(n)
    zs = np.empty(n)
    temps = np.empty(n)
    sat = np.zeros(n, dtype=bool)

    r0 = pack.r0 + r0_delta
    r1 = pack.r1 * r1_scale
    tau1 = max(r1 * pack.c1, dt)

    i_meas = np.empty(n)
    v_meas = np.empty(n)

    # Drawn in one block before the loop. Each subsystem has its own
    # generator, so only the order WITHIN a stream matters, and moving these
    # ahead of the plant integration does not change it.
    i_noise = rng["current_sensor"].normal(0.0, sensing.sigma_i, n)
    v_noise = rng["voltage_sensor"].normal(0.0, sensing.sigma_v, n)
    shift = int(round(sensing.delay_s * loop.hz))

    for k in range(n):
        demand = loop.base_current + float(command(t[k]))
        demand += rng["controller"].normal(0.0, 0.01)
        i_cmd[k] = demand
        # first-order command-to-current lag: the realized current LAGS
        i_real += alpha * (demand - i_real)
        if abs(i_real) > loop.saturation_a:
            i_real = math.copysign(loop.saturation_a, i_real)
            sat[k] = True
        i_real += rng["process"].normal(0.0, 0.01)

        v1 += dt * (-v1 / tau1 + i_real * r1 / tau1)
        z -= i_real * dt / (pack.capacity_ah * 3600.0)
        temp += dt * (pack.thermal_rise_per_amp2 * (i_real ** 2) / 200.0
                      - (temp - pack.t_ambient_c) / 60.0)

        ocv = pack.ocv(z, temp) + ocv_offset - ocv_drift_v_per_s * t[k]
        v = ocv - pack.r0_at(temp) * i_real - r0_delta * i_real - v1
        if unmodelled_ringing:
            v += unmodelled_ringing * math.sin(2.0 * math.pi * 3.7 * t[k]) \
                * math.exp(-t[k] / 30.0)

        i_true[k] = i_real
        v_true[k] = v
        zs[k] = z
        temps[k] = temp

        # --- measurement chain, per sample and causal ----------------------
        if shift:
            delayed = i_true[k - shift] if k >= shift else i_true[0]
        else:
            delayed = i_real
        ik = (1.0 + sensing.scale_i) * delayed + sensing.bias_i + i_noise[k]
        vk = v + sensing.bias_v + v_noise[k]
        if sensing.quantum_i > 0:
            ik = round(ik / sensing.quantum_i) * sensing.quantum_i
        if sensing.quantum_v > 0:
            vk = round(vk / sensing.quantum_v) * sensing.quantum_v
        i_meas[k] = ik
        v_meas[k] = vk
        if observer is not None:
            observer(float(t[k]), float(ik), float(vk))

    valid = np.ones(n, dtype=bool)
    if sensing.dropout > 0:
        valid = rng["telemetry"].random(n) >= sensing.dropout

    return Trace(t=t, i_meas=i_meas, v_meas=v_meas, i_true=i_true,
                 v_true=v_true, i_command=i_cmd, z=zs, temp_c=temps,
                 saturated=sat, valid=valid)


def ocv_drift_rate(trace: Trace) -> float:
    """The realized open-circuit drift over a trace, for a bound on `d`.

    Uses the TRUE state, so it is available to a campaign reasoning about
    what the plant did, and NOT to the certificate, which never sees it.
    """
    if trace.n < 3:
        return 0.0
    pack = PackParams(**SYNTHETIC_PACK)
    ocv = np.array([pack.ocv(z, tc) for z, tc in zip(trace.z, trace.temp_c)])
    return float(-np.polyfit(trace.t, ocv, 1)[0])
