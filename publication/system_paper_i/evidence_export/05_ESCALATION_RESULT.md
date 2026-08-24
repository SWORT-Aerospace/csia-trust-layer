# 05 — Duration-limited escalation

**Artifacts:**
`research/wp_c8/results/escalation_algebra.json` (SHA256 `89c0324517c0cbd26e80bccdcb56350aeeef5b19b82a5f355b8239457e22b1de`)
`research/wp_c8/results/response_surface.json` (SHA256 `510274c9113ec903e56a4d0987bb3c8b877806b34080a7763c74f4061afc42e8`)
`research/wp_c7/results/glitch_mechanism.json` (SHA256 `69e650f5f7c4abe11fadb95477fe4f96103eec21c7f0158515f21e02c42f2ef3`)

**Scripts / commits:** `research/wp_c8/escalation_algebra.py` `83b7f62708567bb58029a67e359c613a50e2c997` ·
`research/wp_c8/response_surface.py` `1ad2513d071830a906555193829cf2b8dbcf5980` ·
`research/wp_c7/glitch_mechanism.py` `57c7c13daa5fa7899f183319c2ce95ad6ad8a955`

`characterisation_only = True` ·
`no_fix_implemented = True`

---

## 1. Step sweep

**The exact maximum tested displacement is 5566.0 m.** Write `5566.0 m`, not
"about 5.6 km". The value is `position_error_m` in the last row below.

| requested/realized position error (m) | implied peak (m/s) | measured floor ticks | measured min trust | predicted floor ticks | predicted min trust | floor tick error | trust error | escalates |
|---|---|---|---|---|---|---|---|---|
| 5.6 | 28.0 | 26 | 0.9237 | 0.0 | 0.9998 | -26.0 | 0.0761 | no |
| 22.3 | 111.5 | 32 | 0.9089 | 5.3 | 0.9959 | -26.7 | 0.087 | no |
| 55.7 | 278.5 | 33 | 0.9063 | 10.9 | 0.9906 | -22.1 | 0.0843 | no |
| 222.6 | 1113.0 | 33 | 0.9061 | 19.4 | 0.9797 | -13.6 | 0.0736 | no |
| 1113.2 | 5566.0 | 33 | 0.9061 | 29.3 | 0.9613 | -3.7 | 0.0552 | no |
| 5566.0 | 27830.0 | 40 | 0.8881 | 39.2 | 0.9356 | -0.8 | 0.0475 | no |

**"Realized" versus "requested".** This artifact records a single
`position_error_m` per row and does not separate commanded from realized.
Separate fields: **UNRECOVERABLE**. The Phase-I harness did verify the injection
reached the receiver (see `07`), but the realized displacement was not stored
as its own field.

**Raw residual response.** The `measured_floor_ticks` column is the count of
ticks with the GPS physics residual at its saturation floor. It is non-zero at
every magnitude including the smallest: the detector fires everywhere and the
loss is downstream.

---

## 2. Ramp contrast, and the classification table

Nine runs flown **before** the derivation existed.
`separates_every_wp_c7_run = True` ·
`n_misclassified = 0` ·
boundary `N* = 93.31` ticks.

| run | measured floor ticks | escalated | predicted | verdict |
|---|---|---|---|---|
| `step 5.6 m` | 26 | no | no | correct |
| `step 22.3 m` | 32 | no | no | correct |
| `step 55.7 m` | 33 | no | no | correct |
| `step 222.6 m` | 33 | no | no | correct |
| `step 1113.2 m` | 33 | no | no | correct |
| `step 5566.0 m` | 40 | no | no | correct |
| `ramp 5 s` | 104 | yes | yes | correct |
| `ramp 20 s` | 168 | yes | yes | correct |
| `ramp 60 s` | 139 | yes | yes | correct |

**What differs.** Steps reach the floor for
26
to 40
ticks and none escalate. Ramps reach it for
104
to 168
ticks and all do. `N* = 93.31` lies in the gap.

Verbatim from the artifact: *the nine runs were flown before the derivation existed and the boundary has no free parameters: N* comes from the fusion weights, the forgetting bounds and the threshold, all read from source. Steps range 26 to 40 floor ticks and none escalated; ramps range 104 to 168 and all did; N* = 93 lies in the gap.*

**Magnitude buys only logarithmic time:**
N_floor grows as ln(amplitude), and every tick of it is spent on a residual already saturated at zero, so it adds no further evidence. A detector that saturates while its decay runs cannot escalate on magnitude alone.
(`extra_ticks_per_1000x_amplitude` =
42.5)

---

## 3. The implemented recursion, from source

| constant | value | source |
|---|---|---|
| `w_nbr` | 0.35 | `csia/trust_engine/engine.py` |
| `w_phys` | 0.3 | `csia/trust_engine/engine.py` |
| `w_temp` | 0.2 | `csia/trust_engine/engine.py` |
| `w_stat` | 0.15 | `csia/trust_engine/engine.py` |
| `rho_max` | 0.998 | `csia/trust_engine/engine.py` |
| `rho_min` | 0.95 | `csia/trust_engine/engine.py` |
| `nav_caution` (threshold `T*`) | 0.75 | `csia/runtime/failsafe.py` |
| `tick_hz` | 25.0 | `research/wp_c6/q_gvalid_campaign.py` PREREG |
| `step_sigma_m_s` | 20.0 | `csia/runtime/online.py` |
| `step_decay_per_tick` | 0.85 | `csia/runtime/online.py` |

**State variable and mass recursion**, verbatim from the artifact:

> S_{k+1} = rho*S_k + 1 regardless of evidence, fixed point 1/(1-rho). The Beta denominator is constant once settled.

- **Forgetting factor** switches between `rho_max` and `rho_min`; under full
  predictor disagreement `rho = 0.95`.
- **Concentration cap** `1/(1 - rho_max)` =
  500.0.
- **Fault-phase mass** `M = 1/(1 - rho)` = 20.0.
- **Banked state at fault onset**, measured: `S_0` = 475.6775,
  `T_0` = 0.999791.
- **Dwell** 25 ticks
  (`csia/runtime/failsafe.py`).
- **Units**: `S` is Beta pseudo-count mass, dimensionless; `T` is a
  probability in [0,1]; `N` is ticks at 25.0 Hz.

**Clipping.** Not represented as a separate term in the closed form.
Per-tick clipping behaviour: **UNRECOVERABLE** from this artifact; read
`csia/trust_engine/engine.py` directly if the paper needs it.

---

## 4. Closed form, corrected

```
equation 1:  T_N = (x S_0 T_0 + (1-x) M e_f) / (x S_0 + (1-x) M), x = rho^N, M = 1/(1-rho)
equation 2:  N* = ln(M(T*-e_f) / (S_0(T_0-T*) + M(T*-e_f))) / ln(rho)
equation 3:  N_floor(peak) = ln(peak / (20*sqrt(1 - 2 ln f))) / ln(1/0.85)
```

**Evidence asymptote** `e_f` = 0.7.
Why: *a fault that destroys only the physics residual removes weight w_phys = 0.30 of a unit weight sum, so evidence cannot fall below 0.70 however bad the residual is. The nav_caution threshold is 0.75, leaving a margin of 0.05.*

**What dominates:** the accumulated mass term is two orders of magnitude larger than the evidence-margin term, so the escalation delay is set by how much agreement the calm period banked, not by how bad the fault is. Halving the concentration cap nearly halves the delay; doubling the threshold margin barely moves it.
mass term `S_0(T_0 - T*)` = 118.82,
margin term `M(T* - e_f)` = 1.0.

### Verification against the shipping TrustCore

| quantity | value |
|---|---|
| closed form matches shipping code | **True** |
| **maximum absolute error vs equation 1** | **0.0** |
| predicted crossing `N*` | **93.31** ticks = 3.732 s |
| **actual first tick at or below threshold** | **94** |
| evidence predicted / observed | 0.7 / 0.7 |
| rho observed | 0.95 |
| verification horizon | k = 1..200 ticks, 67 sampled points |
| escalation boundary incl. dwell | **118.31** ticks |

**Crossing-detector correction, verbatim:** *scanned over every tick, not over the sampled trace below. An earlier version scanned the sample and reported 100 because 94 was not in it.*

**The first derivation was wrong and is not current theory.** It is retained
in `10_CORRECTIONS_LEDGER.md`. Do not present it as the result.
