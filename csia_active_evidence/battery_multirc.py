"""A multi-RC pack with hysteresis. The plant that was predicted to break it.

WHY THIS EXISTS
---------------
`MODEL_VALIDITY_ENVELOPE.md` listed multi-RC dynamics, hysteresis and cell
imbalance as excluded, and recorded that the clean-data residual ratio on the
one-RC pack was already 2.17 against a tolerance of 3.0. The prediction was
that a richer pack would trip `UNKNOWN_OR_MODEL_MISMATCH` on healthy data and
the open-set detector would have to be re-derived rather than re-tuned.

This module is the test of that prediction. It is a PLANT and nothing else,
and it imports nothing from the estimator or the certificate.

WHAT IT ADDS OVER `battery_1rc`
---------------------------------
    V = OCV(z,T) + M h - R0(T) I - sum_j V_j

  * N polarization branches, not one, with separate time constants. A real
    pack has a fast charge-transfer branch and a slow diffusion branch, and
    they alias differently into a fitted slope;
  * VOLTAGE HYSTERESIS. The open-circuit voltage depends on whether the pack
    was last charged or discharged, through a state that relaxes with
    throughput rather than with time:

        dh/dt = -(gamma |I| / Q) (h - sign(I)),   h in [-1, 1]
        contribution = M h

    This is the part with no linear-in-current representation at all. A
    symmetric probe drives `h` toward zero on one half cycle and away on the
    other, and the resulting voltage term is a nonlinear function of the
    current's RECENT SIGN HISTORY, which the estimator's `V = E - I R` has no
    term for and cannot acquire one for;
  * CELL IMBALANCE, as a per-branch scale on `R0` with one weak cell.

EVERY PARAMETER IS SYNTHETIC
-----------------------------
There is no real cell data in this repository and none is obtainable from
this host. `SYNTHETIC_MULTIRC` is a plausible pack in consistent SI units and
IT IS NOT A MEASUREMENT OF ANY CHEMISTRY. The hysteresis magnitude and the
branch time constants are declared numbers chosen to span a plausible range,
not fitted to anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Callable, Optional, Tuple

import numpy as np

from .battery_1rc import Loop, Sensing, Trace, SYNTHETIC_LOOP, SYNTHETIC_SENSING

SCHEMA = "csia.active_evidence.battery_multirc/1"

#: SYNTHETIC. NOT A MEASUREMENT OF ANY CHEMISTRY.
SYNTHETIC_MULTIRC = dict(
    ocv_full=16.8,
    ocv_empty=14.0,
    ocv_curvature=0.45,
    r0=0.040,
    r0_temp_coeff=-3.0e-4,
    # fast charge-transfer branch and slow diffusion branch
    branches=((0.010, 100.0),      # (R_j ohm, C_j farad) -> tau = 1.0 s
              (0.008, 4000.0)),    # tau = 32 s
    capacity_ah=4.0,
    t_ambient_c=22.0,
    thermal_rise_per_amp2=0.004,
    hysteresis_v=0.035,            # M, volts of open-circuit offset
    hysteresis_gamma=60.0,         # throughput constant, dimensionless
    weak_cell_scale=1.0,           # >1 puts extra series resistance in one cell
)


@dataclass(frozen=True)
class MultiRCPack:
    ocv_full: float
    ocv_empty: float
    ocv_curvature: float
    r0: float
    r0_temp_coeff: float
    branches: Tuple[Tuple[float, float], ...]
    capacity_ah: float
    t_ambient_c: float
    thermal_rise_per_amp2: float
    hysteresis_v: float
    hysteresis_gamma: float
    weak_cell_scale: float

    def ocv(self, z: float, t_c: float) -> float:
        z = min(max(z, 0.0), 1.0)
        linear = self.ocv_empty + (self.ocv_full - self.ocv_empty) * z
        return linear - self.ocv_curvature * z * (1.0 - z) * 4.0

    def r0_at(self, t_c: float) -> float:
        return (self.r0 * self.weak_cell_scale
                + self.r0_temp_coeff * (t_c - self.t_ambient_c))

    @property
    def taus(self) -> Tuple[float, ...]:
        return tuple(r * c for r, c in self.branches)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["branches"] = [list(b) for b in self.branches]
        out["taus_s"] = list(self.taus)
        return out


def _streams(seed: int):
    ss = np.random.SeedSequence(seed)
    names = ("process", "voltage_sensor", "current_sensor", "controller",
             "environment", "telemetry")
    return {n: np.random.default_rng(c)
            for n, c in zip(names, ss.spawn(len(names)))}


def simulate(command: Callable[[float], float], *, duration: float,
             seed: int = 0, pack: Optional[MultiRCPack] = None,
             sensing: Optional[Sensing] = None,
             loop: Optional[Loop] = None,
             r0_delta: float = 0.0, ocv_offset: float = 0.0,
             ocv_drift_v_per_s: float = 0.0,
             hysteresis_scale: float = 1.0,
             branch_scale: float = 1.0,
             observer: Optional[Callable[[float, float, float], None]] = None
             ) -> Trace:
    """Run the multi-RC pack. Same interface and Trace type as `battery_1rc`.

    `hysteresis_scale` and `branch_scale` switch the new mechanisms off, so a
    control can confirm that with both at zero this plant reproduces
    one-RC-like behaviour and that any certificate change is attributable to
    the mechanisms rather than to a different implementation.
    """
    pack = pack or MultiRCPack(**SYNTHETIC_MULTIRC)
    sensing = sensing or Sensing(**SYNTHETIC_SENSING)
    loop = loop or Loop(**SYNTHETIC_LOOP)
    rng = _streams(seed)

    dt = 1.0 / loop.hz
    n = max(int(round(duration * loop.hz)), 8)
    t = np.arange(n, dtype=float) * dt
    alpha = dt / max(loop.lag_s, dt) if loop.lag_s > 0 else 1.0

    z = 1.0 - 0.15
    temp = pack.t_ambient_c
    i_real = loop.base_current
    h = 1.0                      # the pack has been discharging
    vj = [0.0] * len(pack.branches)
    q_coulomb = pack.capacity_ah * 3600.0

    i_true = np.empty(n); v_true = np.empty(n); i_cmd = np.empty(n)
    zs = np.empty(n); temps = np.empty(n); sat = np.zeros(n, dtype=bool)
    i_meas = np.empty(n); v_meas = np.empty(n)

    i_noise = rng["current_sensor"].normal(0.0, sensing.sigma_i, n)
    v_noise = rng["voltage_sensor"].normal(0.0, sensing.sigma_v, n)
    shift = int(round(sensing.delay_s * loop.hz))

    for k in range(n):
        demand = loop.base_current + float(command(t[k]))
        demand += rng["controller"].normal(0.0, 0.01)
        i_cmd[k] = demand
        i_real += alpha * (demand - i_real)
        if abs(i_real) > loop.saturation_a:
            i_real = math.copysign(loop.saturation_a, i_real)
            sat[k] = True
        i_real += rng["process"].normal(0.0, 0.01)

        for j, (rj, cj) in enumerate(pack.branches):
            rj = rj * branch_scale
            tau = max(rj * cj, dt)
            vj[j] += dt * (-vj[j] / tau + i_real * rj / tau)

        # Hysteresis relaxes with CHARGE THROUGHPUT, not with time.
        sgn = 1.0 if i_real >= 0 else -1.0
        h += dt * (-(pack.hysteresis_gamma * abs(i_real) / q_coulomb)
                   * (h - sgn))
        h = min(max(h, -1.0), 1.0)

        z -= i_real * dt / q_coulomb
        temp += dt * (pack.thermal_rise_per_amp2 * (i_real ** 2) / 200.0
                      - (temp - pack.t_ambient_c) / 60.0)

        ocv = (pack.ocv(z, temp) + ocv_offset - ocv_drift_v_per_s * t[k]
               + hysteresis_scale * pack.hysteresis_v * h)
        v = ocv - (pack.r0_at(temp) + r0_delta) * i_real - sum(vj)

        i_true[k] = i_real; v_true[k] = v; zs[k] = z; temps[k] = temp

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
        i_meas[k] = ik; v_meas[k] = vk
        if observer is not None:
            observer(float(t[k]), float(ik), float(vk))

    valid = np.ones(n, dtype=bool)
    if sensing.dropout > 0:
        valid = rng["telemetry"].random(n) >= sensing.dropout

    return Trace(t=t, i_meas=i_meas, v_meas=v_meas, i_true=i_true,
                 v_true=v_true, i_command=i_cmd, z=zs, temp_c=temps,
                 saturated=sat, valid=valid)
