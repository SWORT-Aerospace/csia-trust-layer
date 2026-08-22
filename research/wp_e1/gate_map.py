"""WP-E1 — the verified gate map: which gates control which diagnostic features.

Every entry below was read out of production source. Nothing is inferred and
nothing is modified. Line references are to the files as of this branch.

ACTUATING GATES (vary with vehicle state, and control at least one feature
that some hypothesis's LOW signature references):

  armed_gate    online.py:491-496 (runtime) / comparator.py:137 (batch proxy)
                -> accel_motor_current, accel_esc_rpm
  gvalid        comparator.py:115 — GPS fix validity
                -> altitude_baro, velocity_gps_doppler_0/_1, heading_course,
                   phys_gps
  speed_gate    comparator.py:112-113 — ground speed 2->3 m/s ramp
                -> heading_course
  gps_warmup    comparator.py:199 — ticks > 3.0 s
                -> phys_gps

NON-ACTUATING (present in the gate inventory, but structurally irrelevant):

  temp_bias_scale   comparator.py:182-183 — constant 0.2 * ones. Never opens,
                    never closes. Controls temp_bias_drift, which appears in
                    NO hypothesis LOW set, so it cannot affect the partition
                    even in principle. WP-A2 E1 measured its operational
                    effect as exactly 0.0 across all five scenarios.
  quasi_static      modulates an attitude ESTIMATE, not a diagnostic feature.

  8 freshness gates (online.py:47-50 STALE_TIMEOUT_S) block *belief updates*
  in the trust recursion (engine.py:146) and the failsafe freshness branch
  (failsafe.py:144-145). They do NOT gate diagnostic features:
  bayes.py:131-133 sets every temp_* gate to np.ones unconditionally.

UNGATED FEATURES (gate is literally `ones` in source, so they survive every
gate configuration): redundant_imu, attitude_gravity_mag, power_thrust,
vibration_prop_freq, phys_battery, phys_motor_esc, phys_mag, phys_baro,
phys_vibration, and all four temp_* features.

Structure note: `heading_course` is gated by `speed_gate * gvalid` and
`phys_gps` by `gvalid * (ticks > 3.0)`. Both are PRODUCTS of two gates. Gates
are shared — but because the composition is multiplicative, either gate alone
drives the feature to zero. That is an OR over closures, which makes the
marginals SUB-additive, not super-additive. See structural_map.py.
"""

# gate -> features it can drive to zero
GATE_FEATURES = {
    "armed_gate": ("accel_motor_current", "accel_esc_rpm"),
    "gvalid": ("altitude_baro", "velocity_gps_doppler_0",
               "velocity_gps_doppler_1", "heading_course", "phys_gps"),
    "speed_gate": ("heading_course",),
    "gps_warmup": ("phys_gps",),
}

# Features referenced by at least one hypothesis LOW signature. Only these can
# change the partition; the rest are inert for identifiability purposes.
DIAGNOSTIC_FEATURES = (
    "accel_esc_rpm", "accel_motor_current", "attitude_gravity_mag",
    "heading_course", "phys_battery", "phys_gps", "phys_mag",
    "phys_motor_esc", "phys_vibration", "redundant_imu", "temp_battery",
    "temp_gps", "temp_mag", "temp_vibration", "vibration_prop_freq",
)

NON_ACTUATING_GATES = {
    "temp_bias_scale": "constant 0.2 * ones; controls temp_bias_drift, which "
                       "is in no hypothesis LOW set",
    "quasi_static": "modulates an attitude estimate, not a feature",
}

# Runtime armed flag (online.py:256-257, 285-287, 491-496) vs the batch proxy
# (comparator.py:137). WP-E1 uses the RUNTIME FLAG as the reference semantics.
ARMED_SEMANTICS = {
    "runtime_unknown": "armed flag is None -> clip((tau - 5.0) / 1.0, 0, 1) "
                       "— identical to the batch proxy",
    "runtime_armed": "armed flag is True -> clip(tau - armed_since, 0, 1)",
    "runtime_disarmed": "armed flag is False -> hard 0.0",
    "batch": "comparator.py:137 -> clip((ticks - 5.0) / 1.0, 0, 1), "
             "unconditionally; the batch path has no armed flag at all",
    "source_of_truth": "csia/runtime/ulog_source.py:217-225 emits "
                       "vehicle_status arming_state == 2 (ARMING_STATE_ARMED) "
                       "when the topic is present in the log",
}


def features_lost(closed_gates):
    """Features driven to zero when every gate in `closed_gates` is closed."""
    lost = set()
    for gate in closed_gates:
        lost.update(GATE_FEATURES.get(gate, ()))
    return lost


def surviving(closed_gates):
    """Diagnostic features that remain observable."""
    return set(DIAGNOSTIC_FEATURES) - features_lost(closed_gates)
