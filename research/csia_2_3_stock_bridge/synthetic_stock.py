"""SYNTHETIC stock logs for the CSIA 2.3 tests and validation set. RESEARCH ONLY.

Deterministic quad hovers at PX4's default logging intervals, with the
effect of a motor loss or a telemetry-only deficit written in from the SIH
model. They pin the product's logic; they say nothing about accuracy on
real flights. Every log they make is named `synthetic_*` and carries
sha256 "synthetic".
"""
from __future__ import annotations

import numpy as np

from csia_evidence_assurance.stock_log import StockLog

#: PX4 quad X rotor positions (CA_ROTORi_PX, CA_ROTORi_PY), metres.
ROTORS = ((0.15, 0.25), (-0.15, -0.25), (0.15, -0.25), (-0.15, 0.25))


def synth(kind: str = "nominal", motor: int = 0, eta: float = 0.6, t_on: float = 60.0,
          T: float = 100.0, esc: bool = True, battery_current: float = -1.0,
          battery_warning_at: float | None = None) -> StockLog:
    """A SYNTHETIC stock log of a quad hovering from 10 s, at PX4's default
    logging intervals. Deterministic (no noise).

    - kind "motor": motor `motor` loses thrust to `eta` at `t_on`; the loop
      raises its command by 1/eta, its rotor speed follows the effective
      thrust, and the body rates show a 0.3 s transient on its loss axis.
    - kind "telemetry": only the ESC's reported rotor speed on `motor`
      drops (to sqrt(eta)); command and body rates unchanged.
    - kind "esc_offline": from `t_on` ESC `motor` reports 0 RPM and its
      bit in `esc_online_flags` is cleared (PX4's ESC OFF injection).
    - kind "rpm_zero": from `t_on` ESC `motor` reports 0 RPM while online.
    - kind "nominal": nothing happens.
    """
    t_am = np.round(np.arange(0.0, T, 0.1), 6)
    t_es = np.round(np.arange(0.005, T, 0.1), 6)
    t_av = np.round(np.arange(0.0, T, 0.02), 6)
    t_slow = np.round(np.arange(0.0, T, 0.2), 6)
    c = np.full((len(t_am), 4), 0.5)
    eff = np.ones((len(t_es), 4))
    rpm_scale = np.ones((len(t_es), 4))
    if kind == "motor":
        c[t_am >= t_on, motor] = 0.5 / eta
        eff[t_es >= t_on, motor] = eta
    elif kind == "telemetry":
        rpm_scale[t_es >= t_on, motor] = np.sqrt(eta)
    elif kind in ("esc_offline", "rpm_zero"):
        rpm_scale[t_es >= t_on, motor] = 0.0
    c_at = c[np.clip(np.searchsorted(t_am, t_es, side="right") - 1, 0, None)]
    rpm = 1000.0 * np.sqrt(eff * c_at) * rpm_scale
    xyz = np.zeros((len(t_av), 3))
    if kind == "motor":
        px, py = ROTORS[motor]
        ax = np.array([py, -px]) / np.hypot(px, py)
        bump = (t_av >= t_on) & (t_av < t_on + 0.3)
        xyz[bump, 0:2] = 0.2 * ax
    topics = {
        "actuator_motors": {"t": t_am, **{f"control[{m}]": c[:, m] for m in range(4)}},
        "vehicle_angular_velocity": {"t": t_av, **{f"xyz[{i}]": xyz[:, i] for i in range(3)}},
        "battery_status": {"t": t_slow, "voltage_v": np.full(len(t_slow), 15.3),
                           "current_a": np.full(len(t_slow), battery_current),
                           "current_average_a": np.full(len(t_slow), battery_current),
                           "remaining": np.full(len(t_slow), 0.9),
                           "warning": (np.where(t_slow >= battery_warning_at, 2.0, 0.0)
                                       if battery_warning_at is not None else np.zeros(len(t_slow))),
                           "faults": np.zeros(len(t_slow)), "connected": np.ones(len(t_slow))},
        "control_allocator_status": {"t": t_slow,
                                     "torque_setpoint_achieved": np.ones(len(t_slow)),
                                     "thrust_setpoint_achieved": np.ones(len(t_slow)),
                                     **{f"actuator_saturation[{m}]": np.zeros(len(t_slow))
                                        for m in range(4)}},
        "vehicle_status": {"t": np.array([0.0, 5.0, T - 1.0]),
                           "arming_state": np.array([1.0, 2.0, 1.0]),
                           "failsafe": np.zeros(3), "nav_state": np.full(3, 4.0)},
        "vehicle_land_detected": {"t": np.array([0.0, 10.0, T - 2.0]),
                                  "landed": np.array([1.0, 0.0, 1.0])},
        "cpuload": {"t": t_slow, "load": np.full(len(t_slow), 0.2)},
    }
    if esc:
        online = np.full(len(t_es), 15.0)
        if kind == "esc_offline":
            online[t_es >= t_on] = 15.0 - 2 ** motor
        topics["esc_status"] = {"t": t_es, "esc_count": np.full(len(t_es), 4.0),
                                "esc_online_flags": online,
                                **{f"esc[{m}].esc_rpm": rpm[:, m] for m in range(4)},
                                **{f"esc[{m}].esc_current": np.zeros(len(t_es)) for m in range(4)}}
    params = {"CA_ROTOR_COUNT": 4, "THR_MDL_FAC": 0.0}
    for i, (px, py) in enumerate(ROTORS):
        params[f"CA_ROTOR{i}_PX"], params[f"CA_ROTOR{i}_PY"] = px, py
    return StockLog({"file": f"synthetic_{kind}.ulg", "sha256": "synthetic"}, 0, topics, params,
                    [], {k: "synthetic" for k in topics})
