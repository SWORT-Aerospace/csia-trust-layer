# CSIA — the implemented system

Recovered at `bc3ed977e14d6eb6c5dc3a8b771b2349337de91a`. Every equation carries
a source reference. Where the implementation contradicts prior informal
descriptions, the implementation is authoritative and the divergence is stated.

---

## 4. Active runtime call graph

The conceptual path in README:88-90 was checked against the code. **It matches
in order, with three structural corrections.**

```
csia run                                          cli.py:292 (subparser) → cli.py:138-176 (_run)
  └─ get_profile(name)                            profiles.py:91
  └─ SourcePlugin.samples()  [generator]          plugins.py:27-31 (ABC), :54 Simulated, :250 Mavlink
       │   yields Sample(t, sensor, channels)
       ▼
  └─ OnlineTrustLayer.push(sample)                online.py:277-301
       ├─ slot update (_SensorSlot)               online.py:130-145, 199
       ├─ armed-flag channel (not a trust node)   online.py:277-287
       └─ while next_tick < t:  _tick(next_tick)  online.py:281-283, 299-301
              │                                   ── scheduler: fixed dt=1/tick_hz
              ├─ comparator/residual generation   online.py:460-560 (inline edge library)
              │     edge λ, gates (armed/speed/gvalid)
              ├─ TrustCore.step(edges, phys,      engine.py:101-155
              │                 hist, var_ratio, fresh)
              ├─ DiagnosisCore.step(features)     bayes.py:96-114
              └─ → TrustState                     online.py:112-127
       ▼
  └─ FailsafePolicy.update(state) → [Action]      failsafe.py:177-241
       ▼
  └─ Actuator                                     service.py (LoggingActuator | MavlinkActuator)
       ▼
  └─ state log (JSONL, one line per tick)         cli.py --log ; service.py:232 push()
```

**Correction 1 — there is no separate comparator object on the runtime path.**
README:88 shows `OnlineTrustLayer → comparator`. In the code the residual/edge
library is **inlined** in `OnlineTrustLayer._tick` (`online.py:460-560`).
`csia/prediction/comparator.py` is the **batch** path only
(`TrustEngine.run` ← `td` from the comparator). The two implement the same
physics but are separate code, which is precisely why C-08 (online vs batch)
cannot be exact.

**Correction 2 — the tick is a resampler, not a sensor-driven loop.** Samples
arrive asynchronously at native rates; `push()` advances a fixed-step clock and
emits *zero or more* ticks per sample (`online.py:281-283`). Held values are
used between arrivals; freshness is what bounds the holding.

**Correction 3 — `TrustState` carries `fresh` and `armed`,** which the README's
diagram omits, and both are load-bearing for the failsafe (§8).

| Element | Location |
|---|---|
| CLI entrypoint | `cli.py:280 main()`, `run` subparser `cli.py:292` |
| Runtime entrypoint | `cli.py:138 _run()`; service path `service.py:110 run()` |
| Tick function | `online.py:460 _tick(tau)` |
| Source-plugin interface | `plugins.py:27 SourcePlugin` (ABC, single method `samples()`) |
| Sample buffer | `_SensorSlot` `online.py:130-145` (latest value + Holt + EW state) |
| Timing scheduler | `online.py:197-198 dt_tick/next_tick`, advanced `:281-283` |
| OnlineTrustLayer state | `online.py:195-245` (see §5) |
| Comparator state | inlined: `_lam`, `_fw_s`, `_dvel_s`, `_rgps_s`, `_ocv`, `_alt_s`, `_temp_s` `online.py:226-236` |
| Trust-engine state | `TrustCore.alpha/beta/trust` `engine.py:96-99` |
| Diagnosis state | `DiagnosisCore._smoothed` `bayes.py:94` (persistent EW) |
| Failsafe state | `failsafe.py:86-92` |
| Actuator boundary | `service.py` — `LoggingActuator` default, `MavlinkActuator` opt-in |
| Log writer | `cli.py --log run.jsonl`; `service.py:232 push()` |

---

## 5. Complete state vector

The system is a **switched** discrete-time system, not one smooth map:

  x_{k+1} = F_{σ_k}(x_k, u_k, θ),   y_k = G_{σ_k}(x_k, u_k, θ)

with σ_k the discrete mode (§9). Forcing it into a single map would erase the
gates, which are exactly where the identifiability failures live (§10).

### Trust subsystem — `TrustCore` (`engine.py:96-99, 147-154`)

| Symbol | Code | Type/shape | Range | Init | Update | Reset | Affects |
|---|---|---|---|---|---|---|---|
| α_i | `self.alpha[n]` | float × 8 | (0, ~500] | `alpha0=8.0` `:61` | `α←ρα+E` `:147` | on layer reset | trust |
| β_i | `self.beta[n]` | float × 8 | (0, ~500] | `beta0=2.0` `:62` | `β←ρβ+(1−E)` `:148` | on layer reset | trust |
| T_i | `self.trust[n]` | float × 8 | (0,1) | 0.8 `:98` | `α/(α+β)` `:149` | — | trust, diag input, failsafe |

Concentration is **not explicitly clipped**. It is bounded implicitly: the fixed
point of `α←ρα+E` is `α*=E/(1−ρ)`, so with `ρ≤0.998`, `α+β ≤ 1/0.002 = 500`.
There is no `c_max` parameter in source.

### Per-sensor slot — `_SensorSlot` (`online.py:130-145`)
`latest` (dict), `valid` (bool), `seen` (bool), `last_t` (float, init −1e9),
`holt` (per-channel level+trend), `lam_hist` (`_EW(0.15)`),
`var_ratio` (`_EW(0.05)`), `hist_val`, `vr_val`, `base_buf` (list).

### Comparator/predictor state (`online.py:212-236`)
`_imu_buf`, `_imu_bias`, `_att` (`_AttFilter` × 2, complementary), `_att_val`,
`_gps_prev`, `_gps_fd_vel`, `_gps_fd_dvel`, `_gps_step_peak`, `_mag_heading`,
`_lam` (per edge/phys `_EW(0.15)`), `_fw_s`, `_dvel_s`, `_rgps_s`, `_ocv`
(`_EW(0.01)`), `_alt_s`, `_temp_s`, `_alt_s_prev`, `_temp_s_prev`,
`_mag_cal_buf`.

### Mode/gating state
`_armed` (bool|None `:256`), `_armed_since` (`:257`), `_stale` (dict `:238`),
`next_tick` (`:198`), `_bad_samples` (`:237`).

### Diagnosis state
`DiagnosisCore._smoothed` — EW log-likelihood vector, length 8, `bayes.py:94`,
init `None`→first `ll` (`:105-106`), update `:108-109`. **Persistent across
ticks**, so the posterior is path-dependent.

### Failsafe state (`failsafe.py:86-92`)
`level` (IntEnum 0-3), `transitions` (list), `_cond_since` (dict cond→onset),
`_issued` (set), `_below_since` (float|None), `_selected_imu` (str|None),
`_ever_fresh` (set). `reset_timers()` (`:243-250`) clears the first three on
disarm and on source time discontinuity; **`level` deliberately persists**.

---

## 7. The exact trust recursion

All from `engine.py`.

**Prior** (`:96-99`): α_i(0)=8.0, β_i(0)=2.0 ⟹ T_i(0)=0.8.

**Sub-scores** — one shared kernel `c(λ) = exp(−½·max(0, λ−1))` (`:78`, and
inlined identically at `:116, :124, :127, :129`). Only the χ² **excess** over
the per-df mean of 1 counts against a sensor.

- Neighbour (`:108-118`): `c_nbr = Σ_j w_ij c(λ_ij) / Σ_j w_ij`,
  `w_ij = gate_ij · T_j` (previous-tick trust), edges with `w ≤ 1e-6` skipped;
  `c_nbr = None` if `Σw ≤ 1e-6`.
- Physics (`:120-124`): `c_phys = c(λ_p)` if `gate_p > 1e-6` else `None`.
- Temporal (`:126-127`), Statistical (`:128-129`): `c(λ)` or `None`.

**Fusion** (`:131-140`): over available sub-scores only, weights renormalised:
`E_i = Σ w·c / Σ w`, else `E_i = 0.5` placeholder.

**Adaptive forgetting** (`:143-144`): `d = max(scores) − min(scores)` (0 if <2
available); `ρ = ρ_max − (ρ_max − ρ_min)·d`, ρ_max=0.998, ρ_min=0.95.

**Update** (`:146-149`), guarded:
```
if avail and fresh[i]:   α_i ← ρ·α_i + E_i ;  β_i ← ρ·β_i + (1 − E_i)
T_i ← α_i / (α_i + β_i)
```
**Synchronous** (`:153-154`): all nodes read tick k−1 trust; `self.trust` is
replaced only after the loop.

**Guards:** `den > 1e-6` (neighbour), `gate > 1e-6` (physics), `wsum` guarded by
the `avail` test. **No clipping of α, β or T; no explicit concentration cap.**

### The informal weight rule — **ABSENT**

The rule `w_{i←ij} = (1−τ_i) / ((1−τ_i) + (1−τ_j))` **does not exist in this
implementation**, in any guarded or approximate form. Classification: **absent**.

The implemented weight is `w_ij = gate_ij · T_j` (`:113`) — proportional to the
**neighbour's trust**, with no dependence on the receiving node's own trust
τ_i and no normalisation by a sum of distrusts. Behaviourally they differ:
the informal rule allocates *responsibility* between two endpoints of a
disagreeing edge (a distrusted node absorbs blame); the implemented rule
*discounts the informant* (a distrusted neighbour's opinion is down-weighted
for everyone). Note also that no responsibility allocation exists at all —
both endpoints of a low-consistency edge receive the same `c(λ_ij)`.

Likewise **λ, g⁺, g⁻, c_max do not appear in source.** The parameter set is
`{w_nbr, w_phys, w_temp, w_stat, ρ_min, ρ_max, α₀, β₀}` (`:55-62`).

---

## 8. Five semantics, kept separate

The GPS-dropout path is where the README's apparently contradictory statements
resolve. They are not contradictory because they live in **different
subsystems**.

Let `fresh_i(k) = (t_k − last_t_i) ≤ STALE_TIMEOUT_S[i]` (`online.py:47-50`)
and `mon_i = i ∈ _ever_fresh` (`failsafe.py:188-190`).

| # | Subsystem | GPS-absent behaviour | Source |
|---|---|---|---|
| 1 | Measurement validity | `fresh_gps → False` after 0.5 s | `online.py:47-50` |
| 2 | Evidence production | GPS edges gate to 0 (`gvalid`); `phys_gps` gate 0 | `comparator.py:144,155,168,199` |
| 3 | Trust evolution | **belief frozen**: `if avail and fresh[n]` fails ⟹ no α/β update ⟹ T_gps **holds** | `engine.py:146` |
| 4 | Cause diagnosis | gated features **skipped** ⟹ no evidence for or against `gps_fault` ⟹ posterior stays `nominal` | `bayes.py:99-100` |
| 5 | Failsafe action | **fires anyway** via the freshness branch | `failsafe.py:144-153` |

The failsafe condition, verbatim (`failsafe.py:144-145`):
```python
if (T["gps"] < cfg.nav_caution and fresh.get("gps")) or \
        (not fresh.get("gps", True) and gps_was_monitored):
```
Two disjuncts, two different meanings:
- **inconsistency**: data present *and* trust low → `nav_degraded`;
- **absence**: data missing *and* the sensor was previously monitored →
  `nav_degraded`.

Piecewise, for the GPS node:

```
σ = FRESH_TRUSTED     : fresh ∧ T>0.75   → α,β update; diag active; failsafe NORMAL
σ = FRESH_DISTRUSTED  : fresh ∧ T≤0.75   → α,β update; diag active; failsafe CAUTION after dwell_up
σ = STALE_MONITORED   : ¬fresh ∧ mon     → α,β HELD; diag no-evidence; failsafe CAUTION after dwell_up
σ = STALE_NEVER_SEEN  : ¬fresh ∧ ¬mon    → α,β HELD; diag no-evidence; failsafe NORMAL
```

So: *absence of data is not evidence of a sensor fault* (rows 3 and 4 — the
belief and the diagnosis are untouched), while *the failsafe still responds to
unavailable data* (row 5 — because a navigation capability is genuinely gone
whether or not the GPS unit is broken). The fourth mode is the one that keeps a
never-installed sensor from raising alarms.

**Absence, inconsistency and fault are three distinct conditions here and are
never merged.**

---

## 9. Switching / hybrid behaviour

**Execution model: multi-rate asynchronous arrival resampled onto a fixed
synchronous tick, with held samples.** Not sensor-driven, not free-running.
`push()` advances `next_tick` by `dt_tick` and can emit 0..n ticks per sample
(`online.py:281-283`). Between arrivals the last value is held; `fresh` bounds
how long holding is legitimate.

Discrete mode components σ_k:

| Component | Values | Source |
|---|---|---|
| armed | `True / False / None` | `online.py:256, 284-287` |
| arming ramp | `armed_gate ∈ [0,1]`, 1 s ramp | `online.py:491-496` |
| pre-arm proxy | `clip((τ−5)/1, 0, 1)` when armed is None | `online.py:492` |
| failsafe arm window | `t < arm_time (10 s)` → no actions | `failsafe.py:198-199` |
| speed gate | `clip((v−2)/(3−2),0,1)` on `heading_course` | `comparator.py:33-34,112` |
| GPS fix validity | `gvalid ∈ {0,1}` on baro/doppler/heading/phys_gps | `comparator.py:115,144,155,168,199` |
| quasi-static | accel correction gated in `_AttFilter` | `online.py:105-109` |
| motor-edge activation | `armed_gate` | `online.py:487-496` |
| freshness | per sensor, 8 booleans | `online.py:47-50` |
| field mode | `field_mode=True/False` | `online.py:180+` |
| profile | 3 profiles (25/25/100 Hz) | `profiles.py:88-89` |
| failsafe level | 4 levels | `failsafe.py:36-40` |
| enable_commands | bool | `service.py` |

Stale/sample-age rule: a sensor is fresh iff `t_tick − last_t ≤ timeout[i]`,
timeouts `{imu 0.05, baro/mag/esc 0.1, gps/battery/vibration 0.5}` s.

---

## 10. Diagnosis semantics

`p(h | e, g, c)` as implemented (`bayes.py:96-114`):

```
ℓ_h(k) = Σ_{f : g_f > 1e-9}  g_f · [ log(1 − c_f + ε)   if f ∈ LOW(h)
                                     log(c_f + ε)       otherwise ]      ε = 0.02
s_h(k) = (1−a)·s_h(k−1) + a·ℓ_h(k)                                        a = 0.06
p_h(k) = softmax( log π_h + m · s_h(k) )                                  m = 1.5
```
with π_nominal = 0.86 and π_h = 0.02 for each of the 7 fault hypotheses
(`:90-93`).

- **Hypothesis set** (8, `:44-56`): nominal, gps_fault, imu0_bias_drift,
  imu1_bias_drift, mag_interference, power_fault, vibration_anomaly,
  unexpected_maneuver.
- **Conditional independence:** total, across all features (sum of logs).
- **Gate handling:** `g ≤ 1e-9` → feature **skipped entirely**, not down-weighted.
- **Zero-likelihood protection:** ε = 0.02 bounds `log(1−c+ε)` and `log(c+ε)`.
- **Update frequency:** every tick; `_smoothed` persists ⟹ path-dependent.
- **Simultaneous faults:** no representation. Single flat softmax.
- **Confidence semantics:** a normalised posterior over a *closed, mutually
  exclusive* hypothesis set. It is **not** calibrated, and there is no
  "none of the above" outcome other than `nominal`.

Identifiability consequences are in `diagnostic_signature_matrix.md`.

---

## 11. Failsafe authorization semantics

q_{k+1} = Φ(q_k, y_k, t_k, θ_F), `failsafe.py:177-241`.

**Conditions → level** (`:96-173`), all on `TrustState.trust` and `.fresh`:

| Condition | Level | Predicate | Default |
|---|---|---|---|
| `attitude_lost` | EMERGENCY | `max(T_imu over fresh) < att_emergency` | 0.70 |
| `attitude_degraded` | CRITICAL | `< att_caution` | 0.82 |
| `power_fault` | CRITICAL | `T_batt < power_critical ∧ fresh` | 0.70 |
| `structural` | CRITICAL | `T_vib < struct_critical ∧ fresh` | 0.60 |
| `nav_degraded` | CAUTION | `(T_gps < nav_caution ∧ fresh) ∨ (¬fresh ∧ monitored)` | 0.75 |
| `heading_degraded` | CAUTION | `T_mag < heading_caution ∧ fresh` | 0.60 |
| `imu_isolated` | CAUTION | `|T0−T1| > 0.12 ∧ min < 0.85 ∧ selection changed` | 0.12 |

`att` is `max` over **fresh** IMUs, default 1.0 if none (`:105-106`) — a
deliberate fail-*open* on that predicate, worth noting.

**Transitions** (`:206-236`): escalate immediately once a condition has held
`dwell_up` (1.0 s); de-escalate only after `dwell_down` (5.0 s) of the lower
target holding. `level = max` over dwelled conditions. Actions issue once per
condition episode (`_issued`, `:211-215`).

**Guards:** `armed is False` → `reset_timers()`, return `[]` (`:191-197`);
`t < arm_time` → return `[]` (`:198-199`).

**Actuator boundary:** `LoggingActuator` by default (advisory, log only);
`MavlinkActuator` requires explicit `enable_commands=True`.

> **This is deterministic policy authorization, not a formal reachability
> guarantee.** The state machine is deterministic and auditable, and that is all
> that has been established. No bound has been proven on time-to-detect, no
> reachability or liveness property has been verified, no proof exists that
> EMERGENCY is reachable from every hazardous state, and the `att` fail-open
> default above is an unanalysed corner. Determinism is not safety.
