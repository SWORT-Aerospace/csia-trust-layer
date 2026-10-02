# Maneuver study: can degradation be detected during maneuvering without restoring false symptoms? (RB-001 Parts 3-6)

**2026-10-02. SITL only (SIH). Nothing here is physical evidence.**

## 1. The problem and the rule

**The hole.** CSIA 2.3 refuses its compensation evidence when the vehicle
is not near-steady (NOT_STEADY_FLIGHT, peak body rate above
θ_steady = 0.0989 rad/s). That removed the false `COMMAND_NO_RESPONSE`
that maneuvers raised (2.3 V5, V6). But a motor losing effectiveness
during continuous maneuvering is then not confirmed (2.3 V13).

**The brief's rule:** do not loosen the steadiness threshold. Compare
baselines; SITL before hardware; and a candidate that brings back false
`COMMAND_NO_RESPONSE` does not move to hardware.

## 2. The five candidates (`maneuver.py`)

| id | what it is | statistic | validity regime |
|---|---|---|---|
| B0 | the 2.3 product as shipped | compensation C_m (change in motor m's command share) ≥ θ_ctrl | refused above θ_steady |
| B1 | the gate loosened (the brief's "looser threshold" baseline, run to show what it costs) | C_m ≥ θ_ctrl | refused above 2 × the calibration maximum of the peak rate |
| B2 | regime-conditioned thresholds | C_m ≥ θ_C(bin of the peak rate) | a bin with fewer than 20 calibration pseudo-onsets is refused |
| B3 | control-conditioned residual | the per-motor loss estimate δ_m from the torque residual: demanded torque (low-passed) minus the torque implied by measured angular acceleration, projected on each motor's signature, AFTER minus BEFORE | none |
| B4 | an established model-based test | Willsky-Jones GLR on the same residual, motor signatures u_m·b_m, heteroscedastic noise model | none |

**B3 and B4 are textbook forms** (parity-space residual and GLR; see
`LITERATURE.md`). They are what an engineer would try first. Neither is
offered as a new method.

**The model** (g, c, the allocator mixing, the noise) was fitted on the
calibration flights only: g ≈ [104.3, 104.6, 6.3] (rad/s² per unit
torque setpoint, roll, pitch, yaw).

## 3. Data separation

| set | flights | used for |
|---|---|---|
| development | 2.3 V1-V13 (already seen) | formulation choices only: the lag constant, roll-pitch for B3, B4's argmax among loss estimates; no threshold |
| calibration | CAL1-CAL5, nominal: 1,020 pseudo-onsets | every threshold, by one rule: 2 × the largest null value |
| evaluation | EN1-EN4, EF1-EF6, EH1, ET1, ET2 | flown after the preregistration was committed (9375920); scored once |

**Thresholds** (`MANEUVER_CALIBRATION.json`):
- θ_steady_B1 = 2.876 rad/s;
- θ_C by bin: 0.0061, not calibrated, 0.057, 0.320, 0.352;
- θ_δ = 0.0183 (null maximum 0.0092);
- h_GLR = 126.6 (null maximum 63.3).

**Development reference** (seen before the preregistration, not evidence):
B1 raised 42 false VIOLATED on V1-V13. B0 missed V13. B2, B3 and B4 raised
none and detected 6/6.

RESULTS_PLACEHOLDER
