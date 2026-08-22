# CSIA — the algorithm as it actually executes

**Baseline:** post-promotion (`attitude_gravity_mag` in `imu0_bias_drift`).
**Every statement carries a source reference.** Anything not derivable from
source is marked **`UNSOURCED`** rather than reconstructed.

Two execution paths exist and are not identical. **BATCH** (`csia build`,
`csia report`, dashboard replay) runs `PredictionComparator` →
`TrustEngine.run` → `CausalDiagnosis.run`. **ONLINE** (`csia run`,
`csia service`) runs `OnlineTrustLayer._tick` with its own inlined edge
library. Differences are flagged in §8.

---

## 1. One tick, in execution order

```
ONLINE  csia/runtime/online.py: OnlineTrustLayer._tick
────────────────────────────────────────────────────────────────────────────
 1  ingest              feed(topic, t, payload)          online.py:270-300
                        per-channel latest/valid/seen/last_t   :129-134
 2  freshness           fresh[n] = valid AND (t - last_t) <= STALE_TIMEOUT_S[n]
                                                          online.py:47-50
 3  armed state         from vehicle_status if supplied   online.py:285-287
 4  context             tau (time since start), vh (horizontal speed from GPS)
 5  GATES               armed_gate  = clip(tau - armed_since, 0, 1) if armed
                                      is True; clip((tau-5)/1, 0, 1) if the
                                      flag is None; 0.0 if armed is False
                                                          online.py:491-496
                        gvalid      = GPS fix validity    comparator.py:115
                        speed_gate  = clip((vh-2)/(3-2), 0, 1)
                                                          comparator.py:112-113
                        gps_warmup  = ticks > 3.0 s       comparator.py:199
 6  FEATURES            11 edges: lam = (r/sigma)^2 / df, EW-smoothed
                        6 physics self-models: phys_*
                        4 temporal: temp_*, gate = ones   bayes.py:135-136
 7  TRUST UPDATE        TrustCore.step(edges, phys, hist, var_ratio, fresh)
                                                          engine.py:101-157
 8  DIAGNOSIS           DiagnosisCore.step(features)      bayes.py:96-118
 9  FAILSAFE            FailsafePolicy.update(TrustState) failsafe.py:177-215
10  EMIT                TrustState(t, trust, evidence, components, posterior,
                        fresh, armed, edges, latency_us)  online.py:113-123
```

---

## 2. The equations as implemented

### 2.1 Consistency kernel

```
c = exp(-0.5 * max(0, lam - 1))                          engine.py:78
```

`lam` is a chi-square-normalised squared residual per degree of freedom. Only
the **excess over 1** penalises trust; `lam <= 1` gives `c = 1`.

### 2.2 Neighbour weighting — as implemented, not as documented

```
w_ij = gate_ij * T_j                                     engine.py:113
```

The weight discounts the **informant** `j`. It has **no dependence on the
receiving node's own trust**, and there is no responsibility allocation
between edge endpoints. The informal rule
`w = (1-tau_i)/((1-tau_i)+(1-tau_j))` is **absent from source** (WP1).

### 2.3 Fused evidence — renormalised, which creates a floor

```
evidence = sum(w * c for w, c in avail) / sum(w)   if avail else 0.5
                                                          engine.py:140
```

Renormalisation over *available* sub-scores only. Consequence, pinned by
`tests/test_formalization_lock.py`: when one sub-score collapses to 0 and
another is healthy, fused evidence floors at
`w_nbr/(w_nbr+w_phys) = 0.35/0.65 = 0.538`. A single collapsed sub-score
cannot by itself drive trust to zero.

**Measured caveat (WP-C4 2.1):** that floor holds only when a sub-score
*survives*. Collapse every available sub-score and fused evidence goes to
~0 and trust follows — measured floor **0.0068**.

### 2.4 Adaptive forgetting

```
d   = max(scores) - min(scores)  if len(scores) > 1 else 0.0
rho = rho_max - (rho_max - rho_min) * d                  engine.py:143-144
```

`rho_max = 0.998`, `rho_min = 0.95` (`engine.py:57-58`). Predictor
disagreement shortens the memory.

### 2.5 The Beta recursion, with its freshness guard

```
if avail and fresh.get(n, True):                         engine.py:146
    alpha[n] = rho * alpha[n] + evidence
    beta[n]  = rho * beta[n]  + (1 - evidence)
T[n] = alpha[n] / (alpha[n] + beta[n])                   engine.py:149
```

`alpha0 = 8.0`, `beta0 = 2.0` → `T(0) = 0.8` (`engine.py:59-60`).

**Freshness blocks the NODE'S BELIEF UPDATE — it does not gate a named
feature.** This is the distinction most often confused. Stale data freezes
`alpha`/`beta`, so trust *holds* rather than falling: absence of evidence is
not evidence of fault. Separately, `failsafe.py:144-145` fires on its own
freshness disjunct, which is why the system still reacts to missing GPS.

Implicit concentration cap: `alpha + beta <= 1/(1 - rho_max) = 500`. There is
**no explicit cap in source**.

### 2.6 Diagnosis

```
per feature f with gate g and consistency c:
    if g <= 1e-9: continue                # SKIPPED ENTIRELY, not down-weighted
    lo = log(1 - c + EPS)                 # f in the hypothesis's LOW set
    hi = log(c + EPS)                     # otherwise
                                                          bayes.py:99-110
raw[h]    = sum over features
smooth[h] = (1-SMOOTH_ALPHA)*smooth[h] + SMOOTH_ALPHA*raw[h]   (persists)
score[h]  = EVIDENCE_MULT * smooth[h] + log(prior[h])
posterior = softmax(score)
```

`EPS = 0.02`, `SMOOTH_ALPHA = 0.06` (~15-tick window), `EVIDENCE_MULT = 1.5`,
`PRIOR_NOMINAL = 0.86` with the remaining 0.14 split across the 7 faults
(0.02 each) — `bayes.py:37-40`.

**`continue` is the load-bearing line.** A gated feature contributes nothing
to *any* hypothesis, so two hypotheses whose LOW sets coincide over the
surviving features receive identical likelihood forever and their posterior
ratio stays pinned at the prior ratio. That is indistinguishability, not weak
evidence.

---

## 3. State vector — everything that persists across ticks

| Variable | Type / dim | Range | Init | Reset | Source |
|---|---|---|---|---|---|
| `alpha[n]` | float × 8 | (0, ~500] | 8.0 | layer reset | `engine.py:59`, update `:147` |
| `beta[n]` | float × 8 | (0, ~500] | 2.0 | layer reset | `engine.py:60`, update `:148` |
| `trust[n]` | float × 8 | (0, 1) | 0.8 | layer reset | `engine.py:149` |
| `_smoothed[h]` | float × 8 | ℝ | 0.0 | never | `bayes.py:94` |
| EW smoothers (per edge/physics) | float | ℝ | first sample | layer reset | `comparator.py` `ew_smooth` |
| `_armed` | bool \| None | — | None | — | `online.py:256` |
| `_armed_since` | float \| None | s | None | on arm | `online.py:257, 285-287` |
| `_ever_fresh` | set | — | ∅ | layer reset | `failsafe.py:143` |
| `_selected_imu` | str \| None | — | None | — | `failsafe.py:130` |
| `level` | FailsafeLevel | 0–3 | NORMAL | — | `failsafe.py:86` |
| dwell counters | float | s | 0.0 | on transition | `failsafe.py:177-215` |
| per-channel `latest/valid/seen/last_t` | dict × 8 | — | —/False/False/−1e9 | — | `online.py:129-134` |

---

## 4. `S` and `S_eff` side by side

`gate(f)` from `research/wp_e1/gate_map.py`; `closes(h,g)` from
`research/wp_c3/effective_signature.py` — **91% derived from source**, the
three `UNKNOWN` cells all on `speed_gate` and none partition-changing.

| Hypothesis | LOW feature | Gated by | Does this hypothesis close that gate? | In `S_eff`? |
|---|---|---|---|---|
| `nominal` | — (empty by definition) | — | — | — |
| **`gps_fault`** | **`phys_gps`** | **`gvalid`, `gps_warmup`** | **YES — `gvalid`** | **NO** |
| `imu0_bias_drift` | `redundant_imu` | — | no | yes |
| | `accel_motor_current` | `armed_gate` | no | yes |
| | `attitude_gravity_mag` | — | no | yes |
| `imu1_bias_drift` | `redundant_imu` | — | no | yes |
| | `accel_esc_rpm` | `armed_gate` | no | yes |
| `mag_interference` | `attitude_gravity_mag` | — | no | yes |
| | `heading_course` | `gvalid`, `speed_gate` | no | yes |
| | `phys_mag`, `temp_mag` | — | no | yes |
| `power_fault` | `phys_battery`, `temp_battery`, `phys_motor_esc` | — | no | yes |
| | `accel_motor_current`, `accel_esc_rpm` | `armed_gate` | no | yes |
| `vibration_anomaly` | `phys_vibration`, `temp_vibration`, `vibration_prop_freq` | — | no | yes |
| `unexpected_maneuver` | `temp_gps` | — (ungated) | no | yes |

**Read the collapse straight off the table.** `gps_fault` has exactly one
feature; that feature is gated by `gvalid`; a GPS fault closes `gvalid`. Its
`S_eff` column is therefore **empty — identical to `nominal`'s**.

κ(S) = 0.000 (8 classes) · κ(S_eff) = 0.1429 (7 classes) · **gap = 1/7**.
`SOI(gps_fault) = 1.0`; every other hypothesis 0.0.

---

## 5. Gate inventory — 14 total

**Actuating (4)** — vary with state and control a signature-referenced feature:

| Gate | Predicate | Controls | Closed by |
|---|---|---|---|
| `armed_gate` | arming state + 1 s ramp (`online.py:491-496`) | `accel_motor_current`, `accel_esc_rpm` | nothing |
| `gvalid` | GPS fix valid (`comparator.py:115`) | `altitude_baro`, `velocity_gps_doppler_0/_1`, `heading_course`, `phys_gps` | **`gps_fault`** |
| `speed_gate` | ground speed 2→3 m/s (`comparator.py:112-113`) | `heading_course` | UNKNOWN ×3 |
| `gps_warmup` | `ticks > 3.0` (`comparator.py:199`) | `phys_gps` | nothing |

**Constants (2)** — present but never actuate:

| Gate | Value | Note |
|---|---|---|
| `temp_bias_scale` | `0.2 * ones` (`comparator.py:182-183`) | controls `temp_bias_drift`, which is in **no** hypothesis's LOW set. WP-A2 E1 measured its effect as exactly 0.0 in every scenario; steady-state trust offset 1.8e-4 (baro), 6e-5 (battery). |
| `quasi_static` | — | modulates an attitude *estimate*, not a feature |

Four edges also carry a literal `ones` gate: `redundant_imu`,
`attitude_gravity_mag`, `power_thrust`, `vibration_prop_freq`. **A constant
gate is not a dead edge** — WP-A2 E1 showed removing `redundant_imu` makes
`imu0_bias_drift` never detected at all.

**Freshness (8)** — `STALE_TIMEOUT_S` (`online.py:47-50`): imu0/imu1 0.05 s,
baro/mag/motor_esc 0.1 s, gps/battery/vibration 0.5 s. **These block belief
updates (§2.5), not features.**

---

## 6. Failsafe automaton

Levels `NORMAL(0) → CAUTION(1) → CRITICAL(2) → EMERGENCY(3)`
(`failsafe.py:36-40`). Thresholds (`failsafe.py:51-72`): `nav_caution 0.75`,
`heading_caution 0.60`, `struct_critical 0.60`, `power_critical 0.70`,
`att_caution 0.82`, `att_emergency 0.70`, `imu_isolation_gap 0.12`.
Timing: `dwell_up 1.0 s`, `dwell_down 5.0 s`, `arm_time 10.0 s`
(20.0 s in the offline analysis posture), `descent_rate 1.5 m/s`.

| Condition | Level | Actions |
|---|---|---|
| `attitude_lost` | EMERGENCY | `STABILIZE`, `CONTROLLED_DESCENT`, `BROADCAST_MAYDAY` |
| `attitude_degraded` | CRITICAL | `PREPARE_LANDING`, `LIMIT_MANEUVERS` |
| `power_fault` | CRITICAL | `REDUCE_POWER`, `LAND_NOW` |
| `structural` | CRITICAL | `LIMIT_THROTTLE`, `LAND_SOON` |
| `imu_isolated` | CAUTION | `SELECT_IMU{use: best_imu}` |
| `nav_degraded` | CAUTION | `SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES` |
| `heading_degraded` | CAUTION | `HEADING_HOLD_GYRO` |

**`D_critical` = 27 of 28 pairs.** The only response-equivalent pair is
`nominal` ≡ `unexpected_maneuver` (both command nothing). `imu0` and `imu1`
bias drift raise the same *condition* but `SELECT_IMU` carries `{use: ...}`,
so their responses differ and the pair **is** critical.

Note `failsafe.py:106`: `att = max((T[n] for n in imus), default=1.0)` — an
unanalysed **fail-open** on the EMERGENCY predicate when no IMU is fresh.

---

## 7. Worked numerical trace

`gps_spoof` at t = 20.0 s, `hover_circle`, real run.

| t (s) | λ(phys_gps) | gate | c | evidence | ρ | T(gps) | P(gps_fault) | P(nominal) |
|---|---|---|---|---|---|---|---|---|
| 19.60 | 1.0064 | 1.00 | 0.9968 | 0.9990 | 0.9978 | 0.9864 | 0.0001 | 0.9998 |
| 19.88 | 1.4971 | 1.00 | 0.7799 | 0.9340 | 0.9874 | 0.9854 | 0.0003 | 0.9996 |
| **20.00** | 1.5961 | 1.00 | 0.7423 | 0.9227 | 0.9856 | 0.9845 | 0.0005 | 0.9994 |
| 20.16 | 1.2955 | 1.00 | 0.8626 | 0.9588 | 0.9914 | 0.9837 | 0.0007 | 0.9992 |
| 20.28 | 2.0387 | 1.00 | 0.5949 | 0.8785 | 0.9786 | 0.9826 | 0.0010 | 0.9989 |
| 20.36 | 3.0650 | 1.00 | 0.3561 | 0.8068 | 0.9671 | 0.9810 | 0.0016 | 0.9983 |

Every column is a real quantity from the run: λ rises as the spoof walks
position away from Doppler, `c` falls through the kernel, fused evidence
follows, `ρ` drops as predictors disagree (shortening memory), trust decays,
and the posterior begins to move. First `gps_fault` lead at **+1.44 s**;
trust minimum **0.5905**.

---

## 8. Discrepancy table

| # | Discrepancy | Status |
|---|---|---|
| D-1 | `engine.py:104` comment says "12 edges"; production is **11** | Stale comment. Open. |
| D-2 | `armed_gate`: batch assumes arming at t = 5 s (`comparator.py:137`); online uses the real flag (`online.py:491-496`) | Recorded WP-E1. Divergence window [0, 6) s = 6.54% of raw corpus exposure, **0% of monitored** — inside the arm exclusion. |
| D-3 | WP1 recorded `gps_fault ≡ nominal ≡ unexpected_maneuver`; source gives a **two-way** collision | **Corrected** in WP-C3. `temp_gps` is ungated (`bayes.py:135-136`) so no gate can close it. |
| D-4 | `speed_gate` is the canonical "regime gate" in external documents | **κ = 0.000** — structurally inert for identifiability. Confirmed independently by Birnbaum importance = 0.0000. |
| D-5 | `temp_bias_drift` presented as an active annotation edge | Inert both ways: constant 0.2 gate, in no hypothesis's LOW set, measured effect exactly 0.0. |
| D-6 | "Online and batch are exact" | `test_runtime.py:42-43` asserts `<0.07` warm-up / `<0.01` converged divergence, not equality. |
| D-7 | Fused-evidence floor cited as 0.538 unconditionally | **NEW (WP-C4).** Holds only when a sub-score survives. Collapse all and trust reaches **0.0068**. |
| D-8 | `DiagnosisCore` has no input validation on `consistency` | **NEW (WP-C4).** NaN or out-of-`(0,1]` input yields a **NaN posterior**, no exception. `TrustCore` handles the same abuse correctly. Not reachable from production upstreams (`consistency()` maps into range), but the asymmetry is real. |
| D-9 | `failsafe.py:106` `att` defaults to 1.0 when no IMU is fresh | Fail-open on the EMERGENCY predicate. Unanalysed. |
| D-10 | Native C core described as the runtime | It is **not on any production execution path**; the Python runtime executes. |

---

## 9. `UNSOURCED`

- The ≈45:1 endogeneity ratio for `gvalid`. **No emission table, closure-
  probability model, or equivalent exists anywhere in this repository.**
- `674 ns/tick` native timing: no generating command, no committed artifact.
- Any STM32H743 microsecond or CPU-percentage figure: projection only.
