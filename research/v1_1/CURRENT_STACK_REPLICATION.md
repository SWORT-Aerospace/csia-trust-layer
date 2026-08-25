# CURRENT_STACK_REPLICATION — PREREGISTRATION

**Mechanism B: history-dominated trust-threshold crossing.**

**Status: RUN. ArduPilot 4.8 REPLICATED; PX4 SIH INAPPLICABLE.**
The preregistration below is unchanged from the commit that preceded the
first trial (blob `0e186117e2dcc014862872934768e06e0a195592`); results are
appended in section 10 and section 9's table is completed. Originally:
**PREREGISTERED, NOT RUN.** This document is written and frozen before
any current-stack trial. It must be committed before the first run so that the
campaign cannot be widened after seeing results.

Run by: an agent with repository and simulator access.
Not run by: the manuscript session, which has neither.

> **Agent note on the two cells this document delegates.** §2 leaves the PX4
> parameter and §3 leaves the offset magnitudes to be recorded by the running
> agent at preregistration time. Both are filled in below, from simulator and
> core source, **before** any trial. Nothing else in this document has been
> altered. A separate, earlier `mag_emi` probe at `T* = 0.60` exists in this
> repository (`research/v1_1/MECHANISM_B_MAG_EMI_PROBE.md`); it is **not** a
> run of this preregistration and is filed apart so the two cannot be confused.

---

## 1. The scientific question, predeclared

For a fault whose relevant evidence **remains applicable**, does the frozen CSIA
trust recursion on ArduPilot 4.8 and PX4 SIH:

1. receive adverse evidence;
2. retain a measurable banked healthy state $S_0$;
3. evolve according to the source recursion;
4. cross $T^* = 0.75$ at a time predicted by the **measured** state trajectory?

This is a replication of a *mechanism*, not of a *number*.

> **Critical design point.** Do **not** test whether the crossing occurs at 93.31
> ticks. That value is specific to the Phase-I banked state
> $S_0 = 475.6775$, which depends on the length and quality of the preceding calm
> period on ArduCopter 3.3. A different platform will bank a different $S_0$ and
> should therefore cross at a different tick. Testing against 93.31 would produce
> a false non-replication. The test is whether the recursion, given the
> *measured* $S_0$ and the *measured* per-tick $e_k$ and $\rho_k$ on that
> platform, predicts that platform's own observed crossing.

---

## 2. Intervention selection

### Why not fix loss

Fix loss closes the validity gate, which removes the GPS physics residual. With
the evidence removed there is no adverse evidence stream to drive the recursion,
so Mechanism B cannot be exercised. Reusing it would test Mechanism A again.

### Selected intervention: fix-preserving position glitch

Phase-I already contains a characterized evidence-preserving arm. From the
exposure results, the `glitch` arm records $T_{NA} = 0.0$ and $T_{SOFH} = 0.0$
on all three status channels, which is the direct measurement that **the target
hypothesis remained applicable at every tick**. That is exactly the precondition
this test requires, and it is the reason to prefer this arm over inventing a new
one.

| Field | Value |
|---|---|
| Intervention | fix-preserving GNSS position offset |
| Family | Phase-I `glitch` arm and the step/ramp sweep of Section 8 |
| Parameter, ArduPilot 4.8 | **`SIM_GPS1_GLTCH_X`** (REAL32, degrees of latitude). `SIM_GPS.cpp:70-75` `AP_GROUPINFO("GLTCH", 6, GPSParms, glitch, 0)`, a Vector3f in the **per-instance** `GPSParms` group. Applied at `SIM_GPS.cpp:581-583`: `d.latitude += glitch_offsets.x`, `d.longitude += .y`, `d.altitude += .z`. **Not** `SIM_GPS_*`: `SITL.cpp:681` records `// 6 was GPS_GLITCH`, i.e. the old name was removed and writes to it land nowhere |
| Parameter, PX4 SIH | **none exists — recorded at preregistration time, see §2.1.** PX4 is therefore declared **INAPPLICABLE** in advance for the parameter-based form, with a preregistered escape clause in §2.2 |
| Type | configured receiver-side position offset, not a commanded airframe displacement |
| Readback | parameter readback must be captured and must match the request |
| Expected downstream observable | receiver reports the offset position while fix type and satellite count are unchanged from the control |
| Validity condition | `gvalid` remains 1 for the whole scored window. **If the gate closes, the trial is void**, because the intervention has become a Mechanism A trial |
| Null control | identical flight, same window, no parameter applied |
| Fault truth | the injection schedule, never the layer |

### 2.1 PX4: the parameter search, recorded before the campaign

Four candidate routes were read out of PX4 source at `547e2ca`. **None applies a
fix-preserving position offset to the primary GNSS solution**, which is what
CSIA consumes: the PX4 adapter takes `gnss.position` from `GPS_RAW_INT`
(`csia/aircraft/adapters/px4.py:159,239`), i.e. the published
`vehicle_gps_position`.

| candidate | what it actually does | why it is not the intervention |
|---|---|---|
| `SIM_GPS_USED` | satellite count; `SensorGpsSim.cpp:155-167` sets `fix_type = 0` below 4 | fix loss — this is Mechanism A, excluded by §2 |
| `SENS_GPS1_OFFX/OFFY` | `SensorGpsSim.cpp:203-217` builds a **second** receiver instance at an offset and publishes it to `_sensor_gps_pub2`; the primary is published unmodified at `:201` | does not move the primary fix |
| `SENS_GPS0_OFF{X,Y,Z}` | `VehicleGPSPosition.cpp:106-115, 173, 197-200` — the antenna lever arm is passed through as `antenna_offset_x/y/z` **metadata** for the estimator | lat/lon are never modified |
| `failure_injection::process_gnss` | `Off` (suppress), `Stuck` (replay the last fix), `Wrong` (force `fix_type = 2D` + jamming state) | `Off`/`Wrong` close the validity gate; `Stuck` is a frozen-position fault, a different family, and §3 forbids substituting |

`SIH_LOC_LAT0/LON0` is the simulated world origin, not a receiver error, and
moving it would be a commanded displacement — excluded by the Type row above.

### 2.2 Preregistered escape clause for PX4

PX4 can be made to take its GNSS from MAVLink `GPS_INPUT` instead of
`sensor_gps_sim`, which would permit a rig-injected fix-preserving offset. That
route is **attempted only if** it can be shown valid by the same downstream
observable as ArduPilot — reported position offset by the commanded amount with
fix type and satellite count unchanged, `gvalid` = 1 throughout. If that
demonstration fails, PX4 is recorded **INAPPLICABLE** and no substitute
intervention is run. This rule is fixed now, before any attempt.

### Step and ramp contrast

Retain it. It is valid, it is the Phase-I contrast, and it gives the expected
non-crossing and expected crossing conditions §3 requires without adding a new
scenario family.

---

## 3. Frozen campaign

Per platform, per condition, **5 repetitions**, declared now and not revisable.

| Condition | Magnitude (declared below) | Expectation | Purpose |
|---|---|---|---|
| clean control | — | no adverse evidence, no crossing | establishes that $S_0$ banks up on this platform |
| step offset, small | +5 m north, instantaneous | no crossing | expected non-crossing condition |
| step offset, large | +50 m north, instantaneous | no crossing | tests whether magnitude alone crosses |
| ramp, 20 s | 0 → +50 m north, linear over 20 s | crossing | expected crossing condition |

Total: 4 conditions x 5 repetitions x 2 platforms = **40 trials**.

Do not widen this grid after seeing results. If a condition is invalid on a
platform, mark it INAPPLICABLE and say why; do not substitute another.

### 3.1 Magnitudes, and why these — recorded before the campaign

The offset is applied to **latitude only** (`SIM_GPS1_GLTCH_X`), converted with
the authalic Earth radius ArduPilot itself uses in this file
(`SIM_GPS.cpp:548`, `earth_rad_inv = 1.569612305760477e-7`, R = 6 371 000 m), so
**1° latitude = 111 194.9 m** and the write is `metres / 111194.9`.

The magnitudes are chosen from the **core's own residual definition**, not by
eye. `csia/runtime/online.py:562-573`:

```python
r_raw   = self._gps_fd_vel - vel          # fd of REPORTED position, minus reported Doppler velocity
lam_gps = self._lam_upd("phys_gps", norm(r_gps), 0.45, ...)   # sigma 0.45 m/s
lam_step = (self._gps_step_peak / 20.0) ** 2                  # absolute step term, sigma 20 m/s
self._gps_step_peak *= 0.85                                   # decays ~0.85 per tick
P["gps"] = (max(lam_gps, lam_step), gvalid * (1.0 if tau > 3.0 else 0.0))
```

`_gps_fd_vel = (pos - ppos)/dt` (`online.py:364`) is differenced from the
**reported** position, while `vel` is the receiver's **Doppler** velocity, which
`SIM_GPS1_GLTCH` does not touch. So under a position glitch of rate $v$:

$$r_{raw} = (\text{true velocity} + v) - \text{true velocity} = v$$

**independently of what the airframe physically does.** That matters, because a
position glitch on a position-controlling vehicle provokes real motion as it
chases the offset; that motion cancels out of this residual exactly.

Hence the predeclared expectations:

* **A step** puts one sample of $D/\Delta t$ into `_gps_step_peak` and then
  returns $r_{raw}$ to zero. At the ArduPilot SITL default `SIM_GPS1_HZ = 5`
  (`SIM_GPS.cpp:81`), 5 m gives ≈ 25 m/s ($\lambda_{step} ≈ 1.6$) and 50 m gives
  ≈ 250 m/s ($\lambda_{step} ≈ 156$), both decaying at 0.85 per tick — a
  transient of order 1–2 s. **No sustained adverse evidence, so no crossing
  expected, at either magnitude.**
* **A 20 s ramp to 50 m** is $v = 2.5$ m/s held for 20 s, giving
  $\lambda_{gps} ≈ (2.5/0.45)^2 ≈ 31$ **sustained**, so $c_{phys} → 0$ while the
  channel keeps arriving and `gvalid` stays 1.

With $c_{phys} → 0$ and the other three components healthy, the fused evidence
floor is $e_f ≈ (0.35 + 0.20 + 0.15)/1.0 = 0.70$, which is **below**
$T^* = 0.75$ — so a crossing is predicted, and predicted to be strongly
history-dominated because $e_f$ sits only 0.05 under the threshold. That is
precisely the regime Mechanism B describes, and it is why the ramp is the
expected-crossing arm.

**Precondition to be checked first, on the control:** measure $S_0$ at the onset
instant. If a platform does not bank a substantial $S_0$ during its calm period,
Mechanism B has nothing to dominate with, and the correct finding is a
platform-level difference in the precondition rather than a failure of the
recursion. Record that separately; it is a real result.

### 3.2 Fixed flight parameters

Identical for every condition and repetition: 60 s shadow window at 25 Hz
(≈ 1500 ticks); arm and climb before the window; onset at **t = 20.0 s**,
leaving 40 s (1000 ticks) after onset — the ramp completes at t = 40 s and is
held to the end. `field_mode` on, profile `FIELD_DERIVED_NOISE`.

**Flight mode for the scored window: `ALT_HOLD`.** Amended here **before any
trial**, on harness evidence, and disclosed rather than quietly applied.

The first harness run flew the scored window in the mode `fly()` leaves the
vehicle in, which controls horizontal position from GNSS. A commanded 50 m
ramp then produced only **1.55 m** of reported offset: the airframe flew
roughly 48 m the other way chasing the glitch and cancelled it in the reported
frame. Two things are wrong with that, and neither is about the outcome:

1. It makes the intervention **an indirect commanded airframe displacement**,
   which the §2 Type row excludes by name.
2. It makes §2's declared downstream observable — *"receiver reports the offset
   position"* — **unmeasurable**, because the vehicle's response subtracts the
   thing that was supposed to be observed.

`ALT_HOLD` holds altitude and attitude and takes the airframe out of the GNSS
position loop. RC and GCS failsafes are already disabled by `fly()`
(`FS_THR_ENABLE`, `FS_GCS_ENABLE`, `FS_OPTIONS` = 0), so the mode change is
safe. Re-run on the same non-campaign harness configuration, the reported
offset then ramps **linearly to 50.57 m and holds there**, with `gvalid` = 1
throughout — §2's observable, literally.

The mode change is confirmed from `HEARTBEAT.custom_mode` before the window
opens; a flight that did not enter the mode raises rather than being scored,
because a trial flown in the wrong mode is not a trial.

**Amendment discipline.** This changes *how the declared intervention is
realised*, not what it is: the grid, the magnitudes, the threshold, the
tolerances and the classification rule are untouched, and no trial has been
run. Harness verification also confirmed the write path itself is sound —
40 of 40 ramp writes at 5 Hz were applied and acknowledged on schedule, so the
1.55 m was the airframe, not a dropped parameter.

---

## 4. Per-tick logging

Every tick, from 20 ticks before onset to 60 ticks past the observed crossing or
end of run:

```
tick, t_s, fault_truth, raw_residual, gate_applicable, e_k, rho_k, S_k, T_k,
T_le_0_75, failsafe_condition, dwell_state_if_available, assurance_level
```

No mechanism attribution without these intermediates. In particular $\rho_k$ must
be logged and not assumed: $\rho = 0.95$ is the lower bound reached under full
predictor disagreement, and an intervention that does not drive full
disagreement will run at a higher $\rho$ and a different trajectory. That is not
a failure, it is a measurement.

---

## 5. Independent reconstruction

From the **measured** $S_0$, $T_0$, and the **measured** per-tick $e_k$ and
$\rho_k$, step the source recursion tick by tick to obtain $\hat{S}(k)$ and
$\hat{T}(k)$. Do not use the closed form with a constant $\rho$: assuming
constant forgetting is the error that invalidated the first Phase-I derivation
and is recorded as correction 9.

Report per run:

- $\max_k |\hat{T}(k) - T_{\text{runtime}}(k)|$
- predicted crossing tick
- observed crossing tick
- crossing error in ticks

**No fitted parameters.** Every constant comes from source.

### Declared tolerances, fixed now

| Quantity | Tolerance for REPLICATED |
|---|---|
| $\max_k \|\hat{T}(k) - T_{\text{runtime}}(k)\|$ | $\le 10^{-6}$ |
| crossing error | $\le 2$ ticks |
| control crossings | 0 of 5 |
| expected-crossing condition | 5 of 5 cross |
| expected-non-crossing condition | 0 of 5 cross |

The trajectory tolerance is tight because Phase I achieved exactly 0.0 against
the same recursion; a larger error means the implementation differs, not that
the platform differs.

> **Agent note on trace precision.** The per-step trace is written by the
> shadow runner as JSON. It is stored at **15 significant figures** for this
> campaign so that storage rounding cannot consume the $10^{-6}$ budget; at the
> 9-decimal rounding used by the earlier `mag_emi` probe the reconstruction
> floor was ≈ 6 × 10⁻¹⁰, already inside tolerance, but the tighter storage
> removes the question entirely.

---

## 6. Platform classification

Exactly one per platform, using **threshold crossing only**. Escalation
completion is not a criterion, because Systems Paper I no longer claims it.

- **REPLICATED** — valid injection with readback, matched control, gate stayed
  open for the whole window, recursion reproduced the trajectory within
  tolerance, and predicted and observed crossings agree within tolerance.
- **PARTIALLY_REPLICATED** — recursion reproduces the trajectory but crossing
  outcomes differ from expectation, or one condition is invalid.
- **NOT_REPLICATED** — valid campaign, recursion does not reproduce the
  trajectory or crossings contradict prediction.
- **INAPPLICABLE** — the intervention cannot be made valid on this platform.
- **INCONCLUSIVE** — campaign ran but validity controls failed.

`NOT RUN` is not in this list and must not be recorded as `INCONCLUSIVE`.

---

## 7. Negative results

If Mechanism B does not transfer, keep the result. Do not adjust $\rho$,
thresholds, evidence scales or scenario amplitudes to recover it. A
non-replication is an external-validity finding about a mechanism derived from
one 2015-era autopilot, and it is publishable in exactly the same way the
positive result is.

---

## 8. Outputs

```
research/v1_1/CURRENT_STACK_REPLICATION.md          this file, plus results
research/v1_1/results/current_stack_replication.json
```

The JSON must carry: preregistration hash, per-trial validity evidence including
parameter readback, per-trial reconstruction error, per-platform classification,
and the exact sentences Systems Paper I would be permitted to use under each
outcome.

---

## 9. Cross-platform table, to be completed

| Mechanism | ArduCopter 3.3 | ArduPilot 4.8 | PX4 SIH |
|---|---|---|---|
| fix-loss self-occlusion | YES | YES | YES |
| fix-preserving contrast | NO | NO | NO |
| history-dominated threshold crossing | YES | **YES** | **INAPPLICABLE** |

Do not pool platforms. Three columns, three answers.

---

## 10. Results

**ArduPilot 4.8: `REPLICATED`. PX4 SIH: `INAPPLICABLE`.**
20 of 20 ArduPilot trials valid. Every predeclared expectation met.

Machine-readable: `research/v1_1/results/current_stack_replication.json`.
Per-trial §4 tick logs: `research/v1_1/results/mechanism_b_gps/ticks/*.csv`.

### 10.1 The campaign

| condition | n | reported offset | S₀ measured | T₀ | T min after onset | crossed | expected |
|---|---|---|---|---|---|---|---|
| CLEAN | 5 | 0.000 m | 120.46–120.51 | 0.9541 | 0.9541 (unmoved) | **0/5** | no crossing ✅ |
| STEP_SMALL | 5 | 4.998–5.009 m | 133.7–135.3 | 0.960 | 0.862–0.870 | **0/5** | no crossing ✅ |
| STEP_LARGE | 5 | 50.049–50.061 m | 133.3–135.3 | 0.960 | 0.853–0.854 | **0/5** | no crossing ✅ |
| RAMP_20S | 5 | 46.997–47.056 m | 133.3–136.5 | 0.960 | 0.712–0.725 | **5/5** | crossing ✅ |

Validity, all 20: command authority `NO_COMMAND_PATH_REACHABLE`; `ALT_HOLD`
confirmed from `HEARTBEAT.custom_mode`; parameter readback CONFIRMED on every
injected trial (100 writes per ramp, 1 per step); **`gvalid` = 1.0 on every
tick of every scored window, 0 ticks closed**; **0 ticks with `NO_3D_FIX`**.

That last pair is the whole point of the intervention: the fix never dropped,
so the evidence stayed applicable and this is a Mechanism B trial rather than a
Mechanism A trial. Had the gate closed on a single tick the trial would have
been voided by §2.

### 10.2 Section 5 — the reconstruction

Stepped tick by tick from the **measured** S₀ and T₀ at onset with the
**measured** per-tick `e_k` and `ρ_k` re-derived from component scores. **The
constant-ρ closed form was not used anywhere.** No fitted parameters.

| quantity | tolerance | result |
|---|---|---|
| `max_k \|T̂(k) − T_runtime(k)\|` | ≤ 1e-6 | **1.0e-15 – 2.0e-15**, all 20 |
| crossing error | ≤ 2 ticks | **0 ticks**, all 5 ramps |
| control crossings | 0 of 5 | **0 of 5** |
| expected-crossing condition | 5 of 5 | **5 of 5** |
| expected-non-crossing conditions | 0 of 5 | **0 of 5** and **0 of 5** |

The trajectory agreement is at double-precision round-off — nine orders of
magnitude inside the declared tolerance.

### 10.3 What the zero crossing error does and does not show

**It is not an independent forecast, and must not be reported as one.** A
reconstruction driven by the runtime's own measured per-tick evidence will
track the runtime; predicted and observed crossings agreeing to 0 ticks is
close to guaranteed *if the published recursion is complete*. That is exactly
what it tests: whether the recursion as written in the paper is the whole of
the arithmetic the aircraft runs, with no hidden term.

It is a real test because it can fail, and the null controls show by how much.
Breaking one input at a time, on the five ramp trials:

| reconstruction variant | max \|T̂ − T\| | vs 1e-6 |
|---|---|---|
| **measured ρ per tick** (preregistered) | 1.0e-15 – 1.9e-15 | passes by 9 orders |
| ρ held at ρ_max = 0.998 | **0.122 – 0.133** | fails by 5 orders |
| ρ held at ρ_min = 0.95 | **0.047 – 0.049** | fails by 5 orders |
| update gate ignored | 1.0e-15 – 1.9e-15 | **uninformative here** |

The middle two are **correction 9 measured rather than asserted**: on real
ArduPilot 4.8 data, assuming a constant forgetting factor — at either bound,
including the 0.95 a constant-ρ derivation would reach for — misses the
trajectory by five orders of magnitude. §4's insistence that ρ be logged and
not assumed is vindicated quantitatively.

The fourth control **could not have failed on these flights** and is reported
as such rather than counted: the `gps` node was fresh on every tick of every
scored window (`gate_closed_ticks_in_window = 0`), so ignoring the update gate
changes nothing here. It is retained because it *would* bite on a platform with
intermittent node freshness — PX4's magnetometer does exactly that in
`docs/v1_1/PX4_CLEAN_ESCALATION_DIAGNOSIS.md` — and a control that is silent
for a stated reason is more useful than one quietly dropped.

### 10.4 Section 3's precondition, and section 1's design point

**ArduPilot 4.8 banks S₀ ≈ 120–136**, against Phase-I's S₀ = 475.6775. The
platform does bank a substantial healthy state, so the precondition holds and
Mechanism B has something to dominate with — but it banks roughly a quarter of
what ArduCopter 3.3 banked.

This is precisely why §1 forbids testing against 93.31 ticks. A quarter of the
banked state is a materially different system, and the test performed was
whether the recursion given *this* platform's S₀ predicts *this* platform's
crossing. It does, to 0 ticks, five times out of five.

> **Incidental, and explicitly not the test.** The observed crossings fall at
> ticks 94, 95, 96, 98, 99 — near the Phase-I figure of 93.31. That proximity
> is a coincidence of a smaller S₀ meeting a different evidence level and a
> different ρ; it is recorded because a reader will notice it, and it carries
> no weight. Had it come out at tick 300 the verdict would be unchanged.

### 10.5 Why the steps did not cross and the ramp did

The contrast is the result, and it was predicted from source before the
campaign (§3.1). `phys_gps` differences the **reported** position and subtracts
the receiver's **Doppler** velocity, which the glitch does not touch, so the
residual equals the glitch *rate*:

* a **step** deposits one sample into `_gps_step_peak` and then returns the
  residual to zero. It decays at 0.85 per tick — a transient of order 1–2 s.
  50 m moved trust only from 0.960 to 0.854 and it recovered. **Magnitude alone
  does not cross**, which is what the STEP_LARGE condition existed to test.
* a **20 s ramp** holds 2.5 m/s of unexplained motion, so `c_phys` collapses
  and stays collapsed while the channel keeps arriving and `gvalid` stays 1.
  Trust walks down over ~96 ticks and crosses.

A 5 m step and a 50 m step differ by an order of magnitude in size and by
0.016 in the trust minimum they produce. Duration of adverse evidence, not
amplitude, is what moves this node — the mechanism's own claim, measured.

### 10.6 PX4 — INAPPLICABLE, and no substitute was run

No trials were flown. §2.1's parameter search found no fix-preserving position
offset on the primary GNSS solution, and §3 forbids substituting another
intervention. The escape clause of §2.2 (a MAVLink `GPS_INPUT` route) was not
exercised.

**`INAPPLICABLE` is not `INCONCLUSIVE` and not `NOT RUN`.** The intervention
cannot be made valid on this platform with what the platform provides; that is
a statement about PX4 SIH's fault-injection surface, not about CSIA and not
about the mechanism.

### 10.7 Sentences Systems Paper I is permitted to use

Carried in the JSON for every outcome, so the permitted claim was fixed by the
rule rather than written to fit the result. In force:

**ArduPilot 4.8 — REPLICATED:**

> The history-dominated threshold-crossing mechanism replicates on ArduPilot
> 4.8: given the platform's own measured banked state and its measured
> per-tick evidence and forgetting factor, the source recursion reproduces the
> runtime trust trajectory and predicts the observed threshold crossing.

> The crossing tick differs from the 2015 ArduCopter 3.3 figure because the
> banked state differs; the mechanism, not the number, is what replicates.

**PX4 SIH — INAPPLICABLE:**

> The fix-preserving GNSS position offset required to exercise the
> history-dominated threshold-crossing mechanism cannot be applied on this
> platform, so the mechanism was not tested there.

> No substitute intervention was run, because substituting one would test a
> different fault.

### 10.8 Deviations from the preregistration

One, made **before any trial** and recorded in §3.2 in the commit that
preceded the campaign: the scored window is flown in `ALT_HOLD`. The first
harness run flew a GNSS-position-controlling mode, where a commanded 50 m ramp
produced 1.55 m of reported offset because the airframe flew ~48 m the other
way chasing it — an indirect commanded airframe displacement, which §2's Type
row excludes, and which makes §2's declared observable unmeasurable. Grid,
magnitudes, threshold, tolerances and classification rule are untouched.

Nothing else deviates. No ρ, threshold, evidence scale or scenario amplitude
was adjusted at any point, and the frozen core is untouched.

### 10.9 Limits

* **SITL, not hardware.** W-3 records that detection can be a property of the
  noise model rather than of the fault.
* **One node, one fault family.** `gps` under a position glitch. Nothing here
  says how the recursion behaves for a node whose evidence is intermittent.
* **`ALT_HOLD` is not how the aircraft flies.** The mode was chosen to isolate
  the receiver-side fault from the airframe's response to it. On a
  position-controlling vehicle the same glitch provokes real motion, and while
  that motion cancels out of `phys_gps` exactly (§3.1), it does not cancel out
  of everything else.
* **n = 5 per condition.** Enough to show the contrast is not noise; not a
  rate.

### 10.10 Reproducing

```bash
python tools/deploy/mechanism_b_campaign.py --platform ardupilot
python tools/simulation/current_stack_replication.py --platform ardupilot
```

The grid is a module constant, not a command-line option. `--platform px4`
refuses to fly and prints why.

---

## 11. Post-hoc addenda (NOT preregistered)

Both analyses below were written after the campaign, against traces already on
disk. No trial was re-run, no threshold moved, no parameter fitted. They are
reported as post-hoc mechanistic support and nothing stronger.

### 11.1 What the banked state buys

Holding the recorded per-tick `e(k)` and `rho(k)` streams exactly as measured
and varying only the initial banked state (`alpha0 = S0*T0`,
`beta0 = S0*(1-T0)`), at the preregistered `T* = 0.75`:

| initial banked state | crossing tick |
|---|---|
| S0 = 0 (no history) | 52 to 58 |
| 0.25 x S0 | 72 to 78 |
| 0.50 x S0 | 82 to 88 |
| S0 measured (133 to 136) | 94 to 99 |

Monotone in all five trials, and the unmodified fraction reproduces the runtime
crossing in all five (positive control). Banked history accounts for **44 %** of
the crossing delay at this threshold.

### 11.2 That share is threshold-dependent, and saying so matters

Sweeping `T*` over the same traces:

| `T*` | crossing ticks, S0 = 0 | crossing ticks, S0 measured | history share |
|---|---|---|---|
| 0.65 | none | none | not computable |
| 0.70 | none | none | not computable |
| **0.75 (preregistered)** | 52-58 | 94-99 | **0.440** |
| 0.80 | 33-37 | 71-74 | 0.520 |
| 0.85 | 23-25 | 55-58 | 0.566 |

**The share crosses 0.5 inside this range.** At the preregistered threshold
banked history is a large minority of the delay; at 0.80 and above it is a
majority. Any statement that history is "a minority contributor" is therefore
true *at `T* = 0.75`* and must carry that qualifier. The earlier wording in
this repository did not, and this section is the correction.

Two things follow, and they point the same way:

1. The section 10 naming decision stands, and is strengthened rather than
   weakened. Naming the current-stack result after "history dominance" would
   be less defensible once the attributable share is known to move with the
   threshold: the modern result is a **threshold-crossing persistence
   contrast**, and Phase-I keeps **history-dominated threshold crossing** as
   its own analytical result for its own parameter set.
2. Below `T* = 0.70` this fault produces no crossing at any banked state, so
   the mechanism is not merely delayed there, it is absent. That bound is a
   property of the injected evidence level, not of the recursion.
