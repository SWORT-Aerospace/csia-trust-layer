# Do the Phase-I mechanisms replicate on the current stack?

**The peer-review objection this answers:** *"The paper's headline mechanisms
were demonstrated only in the 2015 ArduCopter 3.3 campaign."*

Two mechanisms, two current autopilots, two different answers.

| mechanism | ArduCopter 3.3 | ArduPilot 4.8 | PX4 SIH |
|---|---|---|---|
| **A** — fix-loss self-occlusion (W-1) | YES | **YES** | **YES** |
| **B** — history-dominated threshold crossing (W-4) | YES | **DOES NOT REPLICATE** | **DOES NOT REPLICATE** |

**Combined verdict: `MECHANISM_B_DOES_NOT_REPLICATE`.**

Nothing was tuned to reach that. No `rho`, threshold, evidence weight or
scenario amplitude was adjusted, and the frozen core is untouched —
`tests/test_v1_frozen.py` passes and no `FROZEN_PATHS` file is in the diff.

Machine-readable: `research/v1_1/results/current_stack_replication.json`,
generated from the per-platform result files rather than transcribed.

---

## 0. What "does not replicate" means here, precisely

It does **not** mean the trust recursion is wrong. The recursion was
reconstructed independently on every one of the 18 flights and reproduced the
runtime to **`max_k |T̂(k) − T_runtime(k)| ≤ 6.3 × 10⁻¹⁰`** — worst case across
all 18, 18,018 engine steps. That is the round-off floor set by the trace
storing 9 decimals, not a modelling difference. The preregistered tolerance was
0.02; the result is seven orders of magnitude inside it.

It means something narrower and more useful: **the preregistered intervention
did not produce a sustained evidence collapse on either current platform, so
the threshold was never approached and the crossing W-4 describes was never
exercised.** Sections 5 and 6 say why, mechanistically, with source citations —
and the reason turns out to be a structural property of the frozen core that
was not previously written down.

The honest one-line summary: **the recursion transfers; the fault model does
not.**

---

## 1. Mechanism A — replicates, and is reported in full elsewhere

`docs/v1_1/MECHANISM_A_MODERN_REPLICATION.md`. Summarised only:

Fix loss still removes the evidence required to attribute `gps_fault`. The GPS
gate weight sum goes to **exactly 0.0** on both platforms, GPS trust does not
fall but *rises slightly*, `gps_fault` never reaches rank 1, and the assurance
layer escalates on the freshness path instead. Both trials valid: 450 and 448
`NO_3D_FIX` ticks against clean controls.

That document also states, in its §6, that fix loss **cannot** test Mechanism B
— self-occlusion removes the evidence, so the node never moves and there is no
crossing to time. Mechanism B therefore required a different injection, and the
preregistration was written before one was chosen.

## 2. Mechanism B — the design

**Preregistered in `research/v1_1/MECHANISM_B_PREREGISTRATION.md`, committed at
`5f052dd`, before any trial ran.** The grid, endpoints, tolerances and
classification rule are fixed in that commit; `git log` on the file against
this one is the audit trail.

**The claim (W-4).** `S(k) = ρ(k)·S(k−1) + 1`;
`T(k) = (ρ(k)·S(k−1)·T(k−1) + e(k)) / S(k)`. Banked evidence sits in front of
new evidence, so a node whose evidence collapses *walks* to the new level over
a number of ticks set by `S` and `ρ`. W-4 reports `N* = 93.31` ticks.

**The intervention.** `mag_emi` — a constant hard-iron offset added to the
published magnetometer field, equal on all three body axes, mid-flight. Chosen
because it is the one injection available on both current simulators that is
**evidence-preserving**: the channel keeps arriving, every mag gate stays open,
and the residuals move rather than disappearing.

| platform | parameters | type | unit | Δ for `u` µT | source |
|---|---|---|---|---|---|
| ArduPilot | `SIM_MAG1_OFS_X/Y/Z` | REAL32 | mGauss | `current − 10·u` | `SITL.cpp:779`; **subtracted** at `AP_Compass_SITL.cpp:124`; compensating `COMPASS_OFS` written once at construction (`:30-32`) and never re-synced |
| PX4 | `SIM_MAG_OFFSET_X/Y/Z` | REAL32 | Gauss | `current + u/100` | `SensorMagSim.cpp:153-155`, **added**; `ParamFloat`, no `reboot_required`; `updateParams()` on `parameter_update` (`:113-118`) |

Both deltas are chosen so the **published field moves identically**: `+u` µT
per FRD axis, accounting for the adapters' `×0.1` (mgauss→µT,
`ardupilot.py:148`) and `×100` (gauss→µT, `px4.py:126`). Writes are relative to
the current value, so `u = 0` is a genuine no-op — ArduPilot's boot default is
`(5, 13, −18)`, not zero.

**The grid**, per platform, frozen in advance: `CLEAN` (u = 0, null control),
`SUB` (u = 0.5, expected non-crossing), `CROSS` (u = 15.0, expected crossing);
**3 repetitions each, 18 flights total**; 40 s window, injection at t = 15 s,
1001 ticks per flight.

**The endpoint** is `T_mag(k) ≤ 0.60`, the `heading_caution` constant in
`csia/runtime/failsafe.py` — **threshold crossing, not escalation**, because
escalation additionally requires 1.0 s of continuous dwell and node freshness,
and `docs/v1_1/PX4_CLEAN_ESCALATION_DIAGNOSIS.md` showed the dwell is what
decides the outcome on PX4.

## 3. Trial validity, and what the controls caught

Every arm carries a per-tick trust trace (one row per **engine step**; the
flight log keeps only the last step of each shadow tick and cannot reconstruct
a recursion). Command authority was `NO_COMMAND_PATH_REACHABLE` on all 18
flights.

**RULE B — the parameter write is not the measurement.** The declared
downstream observable is the `mag.field_ut` mean vector shift across the
injection instant, which is exactly `u·√3` µT and attitude-independent because
the offset is a constant body-frame vector.

| platform | arm | expected shift | observed | valid |
|---|---|---|---|---|
| ArduPilot | CLEAN | 0 | 0.006, 0.010, 0.007 µT | ✅ 3/3 |
| ArduPilot | SUB | 0.866 µT | 0.897, 0.890, 0.880 | ✅ 3/3 |
| ArduPilot | CROSS | 25.98 µT | 25.52, 25.54, 25.55 | ✅ 3/3 |
| PX4 | CLEAN | 0 | 0.823, 0.532, 0.490 µT | ✅ 3/3 |
| PX4 | SUB | 0.866 µT | 1.747, 1.284, 1.543 | ❌ **0/3** |
| PX4 | CROSS | 25.98 µT | 25.91, 26.05, 26.61 | ✅ 3/3 |

**PX4's `SUB` arm is not a result — it is a failed trial, all three
repetitions.** `SensorMagSim.cpp:152` adds `noiseGauss3f(0.02, 0.02, 0.03)`
gauss, i.e. **2–3 µT per sample**. A 0.5 µT injection is well inside that noise
floor, and the measured "shift" of 1.3–1.7 µT is the noise, not the offset.
PX4's own `CLEAN` arms show the same thing from the other side: 0.5–0.8 µT of
apparent shift with nothing injected at all.

The preregistered ±40 % validity condition caught this without anyone having to
decide after the fact. It contributes nothing to the verdict in either
direction.

Two of the 18 flights — `px4_CLEAN_2` and `px4_CROSS_2` — exited with the
harness's `INDETERMINATE` R13 code, meaning the constant-work null control went
over budget on the same host. No R13 verdict from this container is admissible
(`csia/simulation/host_noise.py`), and none is claimed; it is unrelated to the
trial and neither flight's trace is affected.

### 3.1 The injection path cost two defects to get right

Both were found by **harness verification runs**, and both would have been read
as findings about the mechanism.

1. **The first `PARAM_VALUE` to arrive is not the answer to your request.**
   Measured on live ArduPilot SITL: three `PARAM_SET` frames all applied
   correctly, and a readback matching the first arriving `PARAM_VALUE` per name
   reported the **old** values for two of them. ArduPilot broadcasts acks on a
   lag of over a second, interleaved with unrelated parameters
   (`INS_GYROFFS_*`, `ARMING_SKIPCHK`, `EK3_SRC1_POSXY`…). The failure
   direction is the dangerous one: a correctly applied injection reported as
   NOT CONFIRMED, i.e. a real effect discarded as a failed trial. Readback now
   drains, requests, takes the **last** value, and polls until the vehicle's
   report catches up.
2. **The three parameter reads inside the injection timer put the field step
   2.5 s after the commanded time.** `N_obs` is counted from the injection
   instant, so that would have entered E2 as a **62-tick error attributed to
   the mechanism**. Reads moved to setup; the timer now sends three frames and
   nothing else — write burst measured at 0.112–0.222 ms across all 18
   flights. The analysis takes the injection instant from the **observed field
   onset**, not the clock.

The Mechanism A readback had the same fragility as (1). Its published results
stand independently, because the intermediate quantity — 450 and 448
`NO_3D_FIX` ticks — confirmed the injection landed; the path is fixed so no
later run inherits it.

**Deviations from the preregistration: none.** The harness verification runs
used a 10–12 s window and a 4–5 s injection — deliberately *not* any
preregistered arm configuration — and are disclosed here rather than counted.
One of them showed a crossing; the grid was not changed after it, and could not
have been, being already committed at `5f052dd`.

## 4. Result — the recursion reconstructs exactly, and nothing crosses

**E1, recursion fidelity (primary endpoint).** `T̂` integrated forward from
`α₀ = 8, β₀ = 2` using only the observed `e(k)`, `ρ(k)` re-derived from the
component scores by the source formula, and the update gate. No runtime trust
enters the integration; nothing is fitted.

> **`max_k |T̂(k) − T_runtime(k)|` ranges 5.1 × 10⁻¹⁰ to 6.3 × 10⁻¹⁰ across
> all 18 flights**, against a preregistered tolerance of 0.02.

That residual is the trace's own 9-decimal storage rounding, not a difference
between the reconstruction and the engine: driven directly by the frozen
`TrustCore` with full-precision inputs the same code agrees to < 1e-12.

**The recursion in the paper is the recursion in the aircraft.** That is the
one unambiguous positive result here, and it is the precondition for every
other claim in this document: a reconstruction that did not match would make
the crossing analysis a statement about the reconstruction.

**The endpoint.** No arm crossed 0.60. Not one of 18.

| platform | arm | `T` at injection | `T` min after | crossed |
|---|---|---|---|---|
| ArduPilot | CLEAN | 0.9733 / 0.9731 / 0.9730 | **unchanged** | no |
| ArduPilot | SUB | 0.9735 / 0.9731 / 0.9734 | **unchanged** | no |
| ArduPilot | CROSS | 0.9698 / 0.9713 / 0.9714 | 0.771 / 0.777 / 0.772 | no |
| PX4 | CLEAN | 0.8719 / 0.8951 / 0.8902 | 0.755 / 0.692 / 0.703 | no |
| PX4 | CROSS | 0.9190 / 0.8939 / 0.8711 | 0.743 / 0.752 / 0.721 | no |

Two things in that table matter more than the verdict.

**On ArduPilot, the 0.5 µT `SUB` injection moved the trust by nothing at all.**
`T` min after injection equals `T` at injection to six decimals, and `e_f` is
exactly 1.0 with `ρ_f` at `rho_max`. The field genuinely moved (0.88–0.90 µT,
within tolerance) and the trust layer did not notice. `SUB` and `CLEAN` are
indistinguishable on this platform.

**On PX4, the null control does the entire job.** The `CROSS` arms' trust
excursion — 0.87–0.92 down to 0.72–0.75 — sits **inside the range the `CLEAN`
arms produce with nothing injected at all** (0.87–0.90 down to 0.69–0.75).
Without RULE A's null control, a 15 µT magnetometer fault driving trust from
0.89 to 0.72 would have looked like a clean detection. It is not distinguishable
from PX4's own baseline wander.

## 5. Why nothing crossed: the evidence recovers while the fault persists

**First, the fault does persist.** ArduPilot `CROSS_0`, field shift from the
pre-injection mean, sampled once per second:

```
t=14.00   0.02 uT      t=20.00  25.47 uT      t=30.00  25.31 uT
t=15.01   5.22 uT      t=22.00  25.41 uT      t=35.00  25.22 uT
t=16.00  25.94 uT      t=25.00  25.30 uT      t=40.00  25.05 uT
```

Twenty-five seconds after injection the offset is still 25 µT. The vehicle did
not re-absorb it, the parameters read back confirmed, and no compass
recalibration occurred. **The evidence recovers anyway.**

ArduPilot `CROSS_0`, the `mag` node's four evidence components:

| t | `c_nbr` | `c_phys` | `c_temp` | `c_stat` | `e` | `T` |
|---|---|---|---|---|---|---|
| 14.88 | 1.000 | 1.000 | 1.000 | 1.000 | 1.0000 | 0.9727 |
| **15.36** | **0.479** | 1.000 | **0.000** | **0.000** | **0.4677** | 0.9467 |
| 15.84 | 0.411 | 1.000 | 0.004 | 0.000 | 0.4449 | 0.8840 |
| 16.80 | 0.715 | 1.000 | 1.000 | 0.031 | 0.7550 | **0.7713** |
| 18.24 | 0.916 | 1.000 | 1.000 | 0.881 | 0.9527 | 0.8359 |
| **19.20** | **1.000** | 1.000 | 1.000 | 1.000 | **1.0000** | 0.8981 |
| 25.44 | 1.000 | 1.000 | 1.000 | 1.000 | 1.0000 | 0.9760 |

Every evidence source is back to healthy **4.1 s after the step**, and trust
climbs back to 0.976. The trust minimum, 0.7706, is reached at t ≈ 16.8 s and
is a *turning point*, not a plateau.

Component by component:

* **`c_temp` and `c_stat` collapse to 0.000 and recover within 1.4 s and
  3.4 s.** These are change detectors — a Holt predictor and a variance ratio.
  A step is one large innovation, then the predictor tracks the new level.
  Working as designed, and structurally incapable of seeing a constant offset.
* **`c_phys` never moves at all — 1.000 throughout.** `phys_mag` compares
  `|B|` against a reference (`online.py:582-585`). The injected offset — as
  published, `(+15.0, −15.1, −15.0)` µT — sits at about 103° to the local field
  `(22.3, −8.3, 52.8)` µT, so it **rotated** the vector instead of lengthening
  it: `|B|` went 57.89 → 57.4 µT. A hard-iron offset is visible to a magnitude
  check only when it points along the field, and its heading effect is largest
  exactly where its magnitude effect is smallest.
* **`c_nbr` drops to 0.411 and recovers to 1.000 over 3.4 s.** This is the one
  that matters, and §6 is about it.

## 6. The finding: the only weighted magnetometer cross-check is mag-slaved

Two edges can carry magnetometer evidence. Measured across every tick of every
flight in this campaign:

```
                         [consistency, gate weight]
attitude_gravity_mag     [1.000, 1.0]  ->  [0.411, 1.0]  ->  [1.000, 1.0]
heading_course           [0.073, 0.0]      [0.129, 0.0]      [0.501, 0.0]
                                    ^^^ gate weight 0.0, every tick
```

* `heading_course` compares the magnetometer heading against **GNSS course**
  — an independent reference. Its gate is `speed_gate * gvalid`
  (`online.py:542-545`), and in a hover it is **0.0 for the entire flight**.
  Its consistency value bounces between 0.07 and 1.0 at random, which is what
  a ground-track bearing does at zero ground speed. It contributes nothing.
* `attitude_gravity_mag` compares the magnetometer heading against the
  **IMU attitude yaw**, `wrap_angle(mag_heading − att0[2])`, gate **1.0,
  unconditional** (`online.py:538-541`).

And that yaw is driven by the magnetometer. `online.py:351-355`:

```python
if self._mag_yaw_gain > 0.0 and self.slots["mag"].seen:
    f = self._att[sensor]
    err = float(wrap_angle(np.array([self._mag_heading - f.yaw]))[0])
    f.yaw += self._mag_yaw_gain * err
```

with field mode forcing the gain on (`online.py:246-248`:
`self._mag_yaw_gain = max(self._mag_yaw_gain, 0.005)`).

> **In a hover, the only magnetometer cross-check carrying any weight compares
> the magnetometer against a reference that the magnetometer itself steers.**
> A persistent magnetometer bias pulls its own reference along with it, and the
> disagreement decays to zero while the fault remains.

The arithmetic agrees with the observation. Mean-age estimation over the
1000 logged ticks puts ArduPilot's `imu0` stream at ≈ 93 Hz, so a first-order
slew at gain 0.005 per IMU sample has `τ = 1/(0.005 × 93.4) ≈ 2.1 s`. Decaying
an initial ~12° heading error below the 5° residual scale of
`attitude_gravity_mag` takes ≈ 1.8 τ ≈ 3.8 s. **Observed recovery: 3.4 s.**

This is a **second self-occlusion**, structurally distinct from Mechanism A's.
Mechanism A occludes by *removing* the evidence. This one occludes by having
the reference *follow the fault*. Both end with a faulty node that cannot be
discredited, and this one is arguably worse, because the evidence is still
flowing and looks healthy.

The mag-aided yaw is deliberate — `online.py:173` documents it as "mag-aided
yaw (drift immunity)". Its cost had not been written down. **It buys drift
immunity by giving the magnetometer partial immunity from its own cross-check.**

### 6.1 What this does *not* establish

`c_temp`/`c_stat` recovery and the mag-yaw slaving are **both** present and
both sufficient on their own timescales. This section attributes the `c_nbr`
recovery to the slaving on the strength of the edge trace, the source, and the
time-constant agreement — but the two were not separated experimentally. The
measurement that would separate them: rerun with `mag_yaw_gain = 0`, which is a
**core parameter change** and therefore outside this work by construction. It
is named as the next measurement, not performed.

## 7. E2, and why the closed form predicted a crossing that never came

On the three ArduPilot `CROSS` arms the W-4 closed form, fed the preregistered
fixed window (ticks inject+2 … inject+26) and `S₀` from the reconstruction,
predicted a crossing at **N\* = 60, 61, 61 ticks**. No crossing occurred.

This is not the recursion failing — E1 is exact. It is the closed form's
**constant-coefficient assumption** failing:

| quantity | value in the fixed window | value 4 s later |
|---|---|---|
| `e_f` | 0.4526 | **1.0000** |
| `ρ_f` | 0.9500 | **0.9980** |

The closed form assumes `e` and `ρ` hold at those values indefinitely, and
under that assumption `T → e_f = 0.45`, which is below 0.60, so a crossing
follows. The actual evidence recovered before tick 60. **A step fault in a
system with adaptive residuals violates the assumption the closed form is
built on**, and the preregistered 1.0 s window — chosen before any data existed
— sampled the transient rather than a steady state that never arrived.

On PX4 the closed form gave the right answer for the right reason: `e_f` came
out at 0.657, 0.658, 0.661, **above** the 0.60 threshold, so it predicted *no
crossing* and none occurred.

E2 is therefore reported as **not evaluable for its intended purpose** on this
campaign: it never got a genuine sustained evidence collapse to time. The
tolerance (±25 ticks) was never the binding issue.

## 8. Verdicts, applied mechanically

Per the preregistration §6, evaluated independently per platform. **Not
pooled.**

| platform | valid arms | valid CROSS | CROSS crossed | E1 all pass | CLEAN crossed | verdict |
|---|---|---|---|---|---|---|
| ArduPilot | 9/9 | 3 | **0** | ✅ | 0 | **DOES_NOT_REPLICATE** |
| PX4 | 6/9 | 3 | **0** | ✅ | 0 | **DOES_NOT_REPLICATE** |

> **`MECHANISM_B_DOES_NOT_REPLICATE`**

E3 (attribution) is **not** confounded on either platform: no `CLEAN` arm
crossed. The preregistration flagged this as a live risk for PX4, since
`PX4_CLEAN_ESCALATION_DIAGNOSIS.md` recorded mag trust reaching 0.554 with no
injected fault on 2 of 4 earlier clean flights. It did not recur across these
3 clean 40 s flights — `T` min 0.692–0.755. **n = 3 and no rate is claimed**;
the earlier observation is not retracted by this one.

## 9. What follows, and what does not

**Follows:**

1. The trust recursion transfers to both current autopilots. `T̂` reproduces
   `T_runtime` to within 6.3 × 10⁻¹⁰ across 18 flights and 18,018 engine
   steps — the storage round-off floor, against a 0.02 tolerance.
2. A constant hard-iron magnetometer offset — up to 26 µT, sustained 25 s,
   verified downstream — **does not produce a sustained trust response** in
   CSIA on either platform.
3. The reason is structural and is now located: in a hover, the sole weighted
   magnetometer cross-check is against a mag-slaved reference, and the two
   change-detector components cannot see a constant offset at all.
4. On PX4, a 15 µT magnetometer fault is not distinguishable from the
   platform's own clean baseline wander. The null control is what establishes
   that.

**Does not follow:**

* That W-4 is wrong. W-4 describes what the recursion does *given* an evidence
  collapse. This campaign did not produce one, so it did not test the delay.
  The 2015 result is not contradicted; it is not confirmed on current hardware
  either.
* That CSIA cannot detect magnetometer faults. It says a *constant* offset is
  the wrong fault model for this detector. A drifting or noise-injecting mag
  fault is a different injection and a separate preregistered trial.
* Anything about real aircraft. These are SITL flights; W-3 records that
  detection can be a property of the noise model rather than of the fault, and
  PX4's 2–3 µT simulated mag noise is exactly that hazard showing up.

**Nothing was tuned.** Per preregistration §7, a non-replication on a current
autopilot is an external-validity finding about a 2015-era characterisation,
and it is worth more than a replication manufactured by adjustment.

## 10. Reproducing

```bash
python tools/deploy/mechanism_b_campaign.py --platform ardupilot
python tools/deploy/mechanism_b_campaign.py --platform px4
python tools/simulation/mechanism_b_report.py --platform ardupilot \
    --arm CLEAN research/v1_1/results/mechanism_b/ardupilot_CLEAN_0.json \
    ...   # one --arm per flight
python tools/simulation/current_stack_replication.py
```

The campaign grid is a module constant, not a command-line option: a grid you
can widen from the shell is not a preregistered grid. `--platform` selects
which platform to fly and nothing else.

`logs/` is git-ignored, as it is for every other flight campaign here, so the
18 raw traces (19 MB) are not in the repository. **One is**, gzipped, so E1 can
be rechecked against real data rather than taken on trust:

```python
from mechanism_b_report import read_trace, reconstruct
h, s = read_trace(
    "research/v1_1/results/mechanism_b/ardupilot_CROSS_0.trace.jsonl.gz")
rows = reconstruct(s, "mag", h["engine_config"])
max(abs(r["T_hat"] - r["T_runtime"]) for r in rows)   # 5.18e-10
```

The engine constants come out of the trace header, written by the engine that
produced the run, so the reconstruction cannot be handed a different `α₀`,
`β₀`, `ρ_max` or `ρ_min` than the flight used.

`tests/test_mechanism_b_recursion.py` (18 tests) checks the reconstruction
against the frozen `TrustCore` itself and the closed form against a direct
numerical iteration of the same recursion, including a test that a
reconstruction ignoring the update gate would fail E1 — so the gate test cannot
pass for the wrong reason.
