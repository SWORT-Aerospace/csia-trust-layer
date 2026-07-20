# CSIA interceptor_seeker — consolidated white-paper handoff

**SYNTHETIC first-pass results.** Every number below is copied verbatim from the repo deliverables (no recomputation, no re-rounding). All runs are seeded and reproducible bit-for-bit. Source of record: SWORT-Aerospace/csia-trust-layer @ commit 329bc93.

## ===== SECTION: FLAGS (read first) =====

Ambiguities / gaps in the source deliverables, surfaced not resolved:

- **Exonerated-channel aggregated min-trust is NOT tabulated** in any source deliverable. The Monte Carlo JSON records `min_trust_others` per run but the summary does not aggregate it across the 50-run batch. Representative single-run values from SUMMARY.md are noted in HEADLINE_NUMBERS; the aggregate is intentionally left blank rather than recomputed here (per the no-recomputation rule).
- **clean false-alarm rate is 1/50 (0.02)**, not 0/50. The 0/50 figure that appeared in an earlier draft came from non-reproducible hash-based seeding (fixed in commit 329bc93). The reproducible number is 1/50 — a single brief endgame CAUTION (see LIMITATIONS_AND_FINDINGS #7).
- **Latency values are the corrected reproducible set** (ir_decoy mean 0.436 s, rf_jam mean 0.242 s). Any earlier draft citing 0.43/0.23 predates the seed fix.

## ===== SECTION: HEADLINE_NUMBERS =====

Tick rate 100 Hz. 50 seeded runs per scenario. All synthetic. Detection rate, latency (mean/median/p95), attribution accuracy, and faulted-channel min-trust are verbatim from montecarlo_results.md; clean false alarms too. Exonerated-channel aggregate min-trust: NOT in deliverables (see FLAGS); representative single-run (seed 0) values from SUMMARY.md — ir_decoy: INS >0.80 (exonerated), RF sags via shared bearing edge; rf_jam: INS stays high, IR sags to ~0.27 via shared bearing edge (documented coupling).

## Detection & attribution (50 runs each)

| scenario | detection rate | latency mean / median / p95 (s) | attribution acc | mean min-trust (faulted) |
|---|---|---|---|---|
| ir_decoy | 1.00 (50/50) | 0.436 / 0.44 / 0.49 | 1.00 | 0.26 |
| rf_jam | 1.00 (50/50) | 0.242 / 0.24 / 0.351 | 1.00 | 0.04 |

**clean_engagement:** 1/50 runs raised any alarm (false-alarm rate 0.02).

## ===== SECTION: DETECTION_FLOOR =====

## ir_decoy magnitude sweep (20 runs/magnitude) — detection floor

| decoy offset | detection rate | mean latency (s) |
|---|---|---|
| 0.1deg | 0.00 (0/20) | — |
| 0.2deg | 0.50 (10/20) | 5.072 |
| 0.35deg | 1.00 (20/20) | 2.616 |
| 0.6deg | 1.00 (20/20) | 1.419 |
| 1.5deg | 1.00 (20/20) | 0.789 |
| 4.0deg | 1.00 (20/20) | 0.499 |

The detection floor is the smallest offset with a detection rate below 1.0; below it the decoy is within the combined bearing noise budget and is (correctly) not separable from noise.

## ===== SECTION: TRUST_GRAPH_CATALOG =====

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

## Seeker profile catalog (interceptor_seeker) — 3 nodes

Structural description authored from csia/seeker/runtime.py (design, not a
measured result). Same consistency convention as the quad: lam = (r/sigma)^2
per df, EW-smoothed (alpha 0.15); c = exp(-max(0, lam-1)/2); gate in [0,1].

Nodes: ir_seeker (LOS azimuth/elevation + intensity), rf_seeker (range,
closing velocity, azimuth, lock), ins (own-ship position/velocity + drift).

| Edge / physics | Nodes | Check | sigma (df) | Gate |
|---|---|---|---|---|
| A: bearing_agreement | ir_seeker-rf_seeker | wrap(IR az - RF az) ~ 0 | hypot(2 mrad, 6 mrad) = 6.3 mrad (1) | RF lock AND IR SNR proxy (intensity 1.5->2.5) |
| B: rangerate_ins | rf_seeker-ins | RF closing - (v_i_ins - v_t_known).LOS(RF az) ~ 0 | 2.5 m/s (1) | closing phase (RF closing > 50 m/s) |
| phys_rf_seeker | rf_seeker | RF closing vs -d/dt(range) over 0.5 s window | 6.0 m/s (1) | after 0.5 s window fills |
| phys_ir_seeker | ir_seeker | IR intensity vs IR_K/range^2 (RF range) | 0.05 frac (1) | RF lock |
| phys_ins | ins | |INS vel| vs windowed |d(pos)/dt| | 1.5 m/s (1) | after 0.5 s window fills |

Diagnosis causes: nominal []; ir_decoy [bearing_agreement]; rf_jam
[bearing_agreement, rangerate_ins, phys_rf_seeker]. Escalation ladder
(SeekerPolicy): NORMAL/CAUTION (channel < 0.75)/CRITICAL (targeting channel
< 0.55), dwell_up 0.25 s, dwell_down 1.0 s, arm_time 2.5 s (warmup excluded).

## ===== SECTION: FAILSAFE_TRANSITIONS =====

# interceptor_seeker — Failsafe / escalation transitions (SYNTHETIC)

One representative run (seed 0, 100 Hz) per scenario. The escalation
ladder reuses the CSIA FailsafeLevel enum (NORMAL/CAUTION/CRITICAL);
conditions and actions are seeker-specific (csia/seeker/runtime.py:
SeekerPolicy). This is the 'engagement-confidence signal' the white
paper maps to fire-control gating. Advisory only.

## clean_engagement
*Full closing engagement, no faults* — engagement 13.1 s.

No escalation transitions (remained NORMAL).

## ir_decoy
*IR decoy: bearing pulled 6 deg from t=8 s* — engagement 13.1 s.

| t (s) | from | to | trigger | actions |
|---|---|---|---|---|
| 8.8 | NORMAL | CAUTION | ir_seeker trust 0.59 degraded | DEWEIGHT_CHANNEL{'channel': 'ir_seeker'} |
| 9.14 | CAUTION | CRITICAL | ir_seeker trust 0.49 < 0.55 — targeting channel unreliable | INHIBIT_TERMINAL_COMMIT{'channel': 'ir_seeker'}; HANDOVER_TO_ALT_SEEKER{'prefer': 'rf_seeker'} |

## rf_jam
*RF jam: 4 deg az bias + 40 m/s range-rate bias from t=8 s* — engagement 13.1 s.

| t (s) | from | to | trigger | actions |
|---|---|---|---|---|
| 8.63 | NORMAL | CAUTION | ir_seeker trust 0.58 degraded | DEWEIGHT_CHANNEL{'channel': 'ir_seeker'} |
| 8.88 | CAUTION | CRITICAL | rf_seeker trust 0.41 < 0.55 — targeting channel unreliable | INHIBIT_TERMINAL_COMMIT{'channel': 'rf_seeker'}; HANDOVER_TO_ALT_SEEKER{'prefer': 'ir_seeker'} |

## multipath_glitch
*RF multipath: 2-tick range/az spike at t=10 s* — engagement 13.1 s.

| t (s) | from | to | trigger | actions |
|---|---|---|---|---|
| 10.99 | NORMAL | CAUTION | rf_seeker trust 0.75 degraded | DEWEIGHT_CHANNEL{'channel': 'rf_seeker'} |
| 12.0 | CAUTION | NORMAL | conditions cleared | — |

## ===== SECTION: LICENSE_AUDIT =====

# CSIA — Dependency License Audit

Runtime + optional-extra dependencies (measured from the installed
environment via `pip-licenses`). Reviewed for copyleft encumbrance on
proprietary distribution.

| Package | Version | License | Extra | Encumbrance |
|---|---|---|---|---|
| numpy | 2.5.1 | BSD-3-Clause (+ 0BSD/MIT/Zlib/CC0) | core | None (permissive) |
| scipy | 1.18.0 | BSD-3-Clause | core | None |
| networkx | 3.6.1 | BSD-3-Clause | core | None |
| matplotlib | 3.11.0 | PSF (BSD-compatible) | core | None |
| pyulog | 1.2.3 | BSD-3-Clause | `[logs]` | None |
| pymavlink | 2.4.49 | **LGPL-3.0** | `[mavlink]` | **FLAG — see below** |
| pytest | 9.1.1 | MIT | `[dev]` | None (dev-only) |

## Findings

**No GPL / AGPL / SSPL** in the dependency set — nothing forces disclosure
of proprietary source.

**pymavlink is LGPL-3.0 — flagged for review.** LGPL permits proprietary use
when the library is **dynamically linked** and the end user can replace it.
- In this project pymavlink is a pure-Python package imported at runtime
  (dynamic linking by construction) and is an **optional** extra (`[mavlink]`);
  the core trust layer and the entire `interceptor_seeker` profile do **not**
  depend on it.
- Recommended posture: keep pymavlink an optional, dynamically-imported,
  unmodified dependency; do not vendor or statically bundle it; if the
  binary is ever frozen (PyInstaller etc.), preserve the LGPL relink path or
  ship it as a separable shared component. If any pymavlink source is
  modified, those modifications must be offered under LGPL.
- For a fully permissive posture, pymavlink can be replaced by a MAVLink
  parser under a permissive license, or the MAVLink dialect can be code-
  generated and the generated code (MIT-licensed generator output) used
  directly.

**The `interceptor_seeker` deliverable has zero copyleft exposure** — it uses
only numpy/scipy (permissive).

## ===== SECTION: LIMITATIONS_AND_FINDINGS =====

Verbatim from SUMMARY.md (not softened):


1. **IR is dragged down under RF jam** (min-trust ≈ 0.27) via the *shared*
   bearing edge, even though IR is truthful. Diagnosis still attributes
   `rf_jam` at 100% (the RF-specific edge B + phys_rf discriminate), but the
   IR *trust value* is coupled. A third independent bearing reference (or an
   RF-independent IR check) would decouple this. Documented, not hidden.
2. **`phys_ir` is necessary, not optional** (contrary to the task's "Edge C
   only if time"): without an RF-independent IR self-model, the IR node has
   only the shared bearing edge and is both falsely implicated under RF jam
   and at risk of empty evidence. It was implemented for correctness.
3. **First-pass calibration bug found and fixed honestly:** single-tick
   differencing of range/position at 100 Hz amplified sensor noise ~100×,
   collapsing `phys_rf`/`phys_ins` in *clean* flight. Fixed with windowed
   (0.5 s) rate estimation, not by inflating σ to mask it.
4. **Warmup (2.5 s) is excluded from metrics**, identical methodology to the
   quad profile's prior-convergence exclusion. During warmup the rate
   windows fill and the Beta prior settles; trust transiently dips then
   recovers. The escalation ladder arms only after warmup.
5. **multipath_glitch** (2-tick RF spike) produced one brief CAUTION rather
   than full suppression — the EW smoothing + Beta integrator spread the
   spike beyond the dwell window. A transient result, reported as-is.
6. **"INS-derived closing velocity" uses the known target velocity**, valid
   in this synthetic setup; on a real system that term comes from a track
   filter. This is the single biggest fidelity gap vs a real deployment.
7. **1/50 clean runs (seed 3038) raised a brief CAUTION** near intercept
   (t≈10–13 s), where the closing geometry becomes extreme; channels dipped
   to ~0.70 (never reaching the 0.55 CRITICAL threshold) and self-cleared.
   Reported as-is: false-alarm rate 0.02, all CAUTION-level, all in the
   terminal endgame. Not tuned away.
8. **Reproducibility bug found and fixed during the sanity re-run:** the
   Monte Carlo previously seeded from `hash(scenario_name)`, which Python
   randomizes per process — so numbers were not bit-reproducible across runs.
   Replaced with fixed per-scenario seed bases; two consecutive runs are now
   byte-identical. (The earlier "0/50 clean" figure was an artifact of the
   non-reproducible seeding; the reproducible figure is 1/50.)

## ===== SECTION: REPRODUCTION =====

```sh
pip install -e ".[dev,logs]"                 # from repo root, py3.11+
python -m pytest                             # full suite (48; 2 native tests
                                             # skip unless csia/native built)
python tools/interceptor_montecarlo.py       # -> montecarlo_results.{md,json}
python tools/interceptor_plots.py            # -> the 3 PNG plots
python -m pytest tests/scenarios/test_seeker_scenarios.py   # seeker scenarios
python tools/video_demo.py --auto            # live-demo (scripted) sanity
```
Deterministic seed bases: ir_decoy 1000+i, rf_jam 2000+i, clean 3000+i,
magnitude sweep 50000+int(mag*100)+i. Two consecutive Monte Carlo runs are
byte-identical (verified via fresh-clone sanity re-run).

## ===== SECTION: PLOT_INVENTORY =====

PNGs live in deliverables/ (upload separately):

| file | description | x-axis | y-axis |
|---|---|---|---|
| plot_trust_vs_time_ir_decoy.png | Representative ir_decoy run (seed 0, 100 Hz): 3 channel trust vs time; fault-onset line; actionable-threshold line; escalation transitions marked | time (s) | Trust Coefficient (0-1) |
| plot_trust_vs_time_rf_jam.png | Same for rf_jam | time (s) | Trust Coefficient (0-1) |
| plot_latency_vs_magnitude.png | Detection latency (mean) and detection rate vs IR decoy magnitude, from the 20-run/pt sweep; bearing-noise floor marked | IR decoy bearing offset (deg) | left: mean detection latency (s); right: detection rate (0-1) |
