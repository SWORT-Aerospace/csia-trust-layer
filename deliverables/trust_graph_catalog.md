# CSIA Dynamic Trust Graph — complete catalog (SOW001 quad profile)

Complete enumeration of the existing UAV profile, from `csia/trust_graph/`
and `csia/prediction/comparator.py`. This is the reference the
`interceptor_seeker` extension mirrors.

Consistency convention (all edges/physics): a residual `r` is normalized to
`λ = (r/σ)² / df`, exponentially smoothed (α = 0.15), and mapped to a
consistency score `c = exp(−max(0, λ−1)/2) ∈ (0,1]`. λ ≈ 1 is the
chi-square nominal; only the excess over 1 penalizes trust. `field_mode`
adds per-check adaptive normalization for real-world data.

## Nodes (8)

| Node | Sensor | Physical quantity |
|---|---|---|
| imu0 | ICM-42688-P #0 | body specific force (m/s²) + angular rate (rad/s) |
| imu1 | ICM-42688-P #1 | body specific force + angular rate (redundant) |
| baro | MS5611 | barometric altitude (m), die temperature (°C) |
| mag | RM3100 | magnetic field vector (µT) → tilt-comp heading |
| gps | GPS receiver | position (m, local), velocity/Doppler (m/s), fix validity |
| motor_esc | 4× ESC telemetry | per-motor RPM, per-motor current (A) |
| battery | pack monitor | terminal voltage (V), pack current (A) |
| vibration | structural accel | broadband vibration RMS envelope (m/s²) |

## Edges (11) — cross-sensor physical relationships

| Edge relation | Nodes | Physical check | σ (df) | Regime gate |
|---|---|---|---|---|
| redundant_imu | imu0–imu1 | ‖accel₀ − accel₁‖ ≈ 0 | 0.09 (3) | always |
| accel_motor_current | imu0–motor_esc | accel_z ≈ Σ(k·(I/I_hover)^{2/3})/m | 0.45 (1) | armed ramp (t>5 s) |
| accel_esc_rpm | imu1–motor_esc | accel_z ≈ Σ(T_hov·(rpm/rpm_hov)²)/m | 0.45 (1) | armed ramp (t>5 s) |
| altitude_baro | baro–gps | baro_alt − gps_alt ≈ 0 | 2.2 (1) | GPS fix valid |
| velocity_gps_doppler | imu0–gps | ‖∫accel_world − d(gps_vel)/dt‖ ≈ 0 | 1.6 (3) | GPS fix valid |
| velocity_gps_doppler | imu1–gps | same, redundant pair | 1.6 (3) | GPS fix valid |
| attitude_gravity_mag | imu0–mag | wrap(mag_heading − IMU yaw) ≈ 0 | 5° (1) | always |
| heading_course | mag–gps | wrap(mag_heading − GPS course) ≈ 0 | 10° (1) | **speed gate 2→3 m/s** × fix valid |
| power_thrust | motor_esc–battery | pack_I − ΣESC_I − I_avionics ≈ 0 | 0.5 (1) | always |
| vibration_prop_freq | vibration–motor_esc | vib_RMS ≈ envelope(mean RPM) | 0.035 (1) | always |
| temp_bias_drift | baro–battery | d(baro_temp)/dt plausibility | 0.5 (1) | annotation (0.2 weight) |

The speed gate on `heading_course` is the canonical regime-gate the seeker
Edge A (bearing SNR gate) and Edge B (closing-phase gate) mirror: a physical
relationship contributes evidence only inside its domain of validity.

## Per-node physics self-models

| Node | Self-model equation | σ (df) | Gate |
|---|---|---|---|
| gps | ‖d(pos)/dt − Doppler_vel‖ (matched detector: residual vector EW-smoothed before norm) | 0.45 (3) | fix valid ∧ t>3 s |
| battery | V_term ≈ V_ocv(est) − I·R_internal | 0.06 (1) | always |
| motor_esc | mean‖I − I_hover·(rpm/rpm_hov)³‖ ≈ 0 | 0.2 (1) | always |
| mag | ‖field‖ ≈ ‖B_local‖ (field-magnitude constancy) | 0.6 (1) | always |
| baro | (‖d(alt)/dt‖ − 8) climb-rate envelope | 3.0 (1) | always |
| vibration | vib_RMS ≈ own expected RPM envelope | 0.05 (1) | always |
| imu0 / imu1 | **none, by design** — ‖f‖=g cannot separate a slow accel bias from a slow climb, so IMU health is judged only through graph edges | — | — |

The deliberate *absence* of an IMU self-model is the design lesson the seeker
reuses inversely: the IR node **requires** a self-model (`phys_ir`, 1/R²
irradiance) so it is not falsely implicated when the shared bearing edge
drops during RF jamming.
