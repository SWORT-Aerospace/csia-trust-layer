# The V6 instrument defect, and why it mattered

**Status:** found, diagnosed, corrected, grid re-flown.
**Consequence:** the E1 verdict changed from `REFUTED` to `SURVIVES_BOUNDED`.
**Artifacts:** `results/e1_modern_run1_defective_instrument.json` (unaltered),
`results/v6_diagnosis.json` (the diagnosis), `results/e1_modern.json` (run 2).

This document exists because the correction moved the result in the direction
that favours the research programme. That demands a fuller account than a
correction that had gone the other way, so the whole chain is written down
here: what was measured, what it should have measured, how it was caught, what
was re-run, and what could still be wrong.

---

## 1. What run 1 reported

E1 flew its precommitted grid — amplitudes 55.7 m and 556.6 m, slews 20, 60,
120, 240 s — on ArduCopter 4.8. It reported **3 of 8 trials INVALID**, all
three failing the same check:

```
V6_truth_matches_schedule   realized displacement within 25% of requested
```

| cell | requested | run-1 "realized" | ratio |
|---|---|---|---|
| a55.7_s60  | 55.7 m | 39.28 m | 0.705 |
| a55.7_s120 | 55.7 m | 39.86 m | 0.716 |
| a55.7_s240 | 55.7 m | 38.61 m | 0.693 |

With those three excluded, no validated significant cell was missed by both
monitors, and the precommitted rule returned
`F3 = REFUTED_AS_TESTED_SAFETY_RELEVANT_PHENOMENON`.

The three excluded cells were the slow, small-amplitude ones — precisely the
sub-region most likely to hold a joint miss. Excluding exactly the cells that
decide the question is the shape of a measurement problem, and it is why this
was investigated before the verdict was written up rather than after.

---

## 2. What the estimator actually measured

Run 1 estimated realized displacement as

```
max over the post-injection window of  sep( GPS_RAW_INT(t), GPS_RAW_INT(t_inject) )
```

the reported position's motion away from a fixed pre-injection mark.

ArduPilot's simulated receiver adds the glitch to the vehicle's **true**
position, after the receiver delay buffer
(`libraries/SITL/SIM_GPS.cpp:581`):

```cpp
d.latitude  += glitch_offsets.x + degrees(lat_wander_m * earth_rad_inv);
```

so

```
reported(t) = truth(t) + glitch(t)

sep( reported(t), reported(t_inject) )
    = | glitch(t) + ( truth(t) - truth(t_inject) ) |
```

The second term is the airframe's own motion. The vehicle in these trials
flies a velocity-commanded square pattern, so that term is never zero, and it
is of the same order as the 55.7 m signal.

**The control measurement.** `results/v6_diagnosis.json` flies a nominal arm
with **no injection at all**. Run 1's estimator reads **38.89 m** on it. A
validity instrument that reads 38.89 m when nothing is injected cannot certify
that an injection happened. That is the defect, stated in one number.

---

## 3. The correct instrument

By the line of `SIM_GPS.cpp` above, the injected offset is exactly the
separation between the reported position and the simulator's own truth, which
`SIMSTATE` publishes and which is present on this build:

```
injected_offset(t) = sep( GPS_RAW_INT(t), SIMSTATE(t) )
```

Measured side by side on the same flights (`results/v6_diagnosis.json`):

| arm | requested | corrected instrument | ratio | run-1 estimator | ratio |
|---|---|---|---|---|---|
| a55.7_s60 (was INVALID) | 55.7 m | **56.92 m** | 1.022 | 39.71 m | 0.713 |
| a55.7_s20 (was VALID)   | 55.7 m | **56.49 m** | 1.014 | 59.88 m | 1.075 |
| nominal (no injection)  | — | **1.21 m** | — | 38.89 m | — |

The injections in the three rejected cells were correct to within 2.2%. They
were rejected by the measuring device, not by the autopilot.

---

## 4. What was changed, and what deliberately was not

**Unchanged.** The grid. The 25% V6 tolerance. The 48 m significance
threshold. The V4 factor. The F3 decision rule, which was written before the
first flight and is quoted verbatim in `e1_modern.py`. No cell was added,
dropped or re-weighted.

**Changed.** One thing: the estimator that V3 and V6 consume is now
`max_injected_sensor_offset_m`. Run 1's quantity is still recorded on every
trial as `max_reported_position_change_m` so the two can be compared directly,
and it is no longer consumed by any validity check.

**All eight cells were re-flown.** Repairing only the three failures would
have judged some cells by one instrument and some by another. Run 2 is a
complete re-fly under a single instrument.

**Two guards were added**, both of which can only make the contract stricter:

- `V3_MIN_POSITION_CHANGE_M` raised from the precommitted 1.0 m to **2.0 m**,
  because the corrected instrument's measured noise ceiling on the control arm
  is 1.21 m and a 1.0 m floor would sit beneath it. Raising a validity floor
  can only remove trials from the metric set, never add one, so it cannot
  manufacture a favourable result. It is non-binding in any case: V6 requires
  agreement within 25% of a request of at least 48 m.
- `instrument_control()`, a campaign-level check that the validity instrument
  reads null on the nominal arms. This is the check whose absence let run 1
  through. Run 2 passes it at 0.81–0.91 m; run 1's estimator would have failed
  it at 38.8–39.6 m.

`V5_csia_ingested` is still computed against a pre-injection mark and so
carries the same contamination. It is retained unchanged, at its precommitted
floor, and flagged `V5_IS_COARSE`: V3 and V6 on the corrected instrument are
strictly stronger, so V5 never decides a trial here.

**No production code was touched.** All of this is under `research/phase2/`.

---

## 5. Run 2

All 8 trials valid. Injection confirmed at 56.4–56.5 m and 557.4 m.

```
cell             inject   excurs    ctrl   excess   ekfvar           cover
a55.7_s20          56.5     39.0    39.2     -0.2    6.249  AUTOPILOT_ONLY
a55.7_s60          56.4     87.9    39.1     48.8    0.525      JOINT_MISS
a55.7_s120         56.5     88.0    39.5     48.5    0.262      JOINT_MISS
a55.7_s240         56.5     87.6    39.6     48.0    0.139      JOINT_MISS
a556.6_s20        557.4     38.9    39.2     -0.4   59.309            BOTH
a556.6_s60        557.4     43.5    39.1      4.3   19.776  AUTOPILOT_ONLY
a556.6_s120       557.4     47.7    39.5      8.2    9.893  AUTOPILOT_ONLY
a556.6_s240       557.4    108.4    39.6     68.8    5.296  AUTOPILOT_ONLY

F3 VERDICT: SURVIVES_BOUNDED
  3 validated significant cells missed by both monitors:
  a55.7_s60, a55.7_s120, a55.7_s240
```

---

## 6. The airframe motion is not a nuisance term

The contamination that broke the instrument is itself the most useful
measurement in the campaign, once it is separated out rather than folded in.

A slow GPS ramp presents to the estimator as a small constant velocity bias.
The velocity controller cancels the bias it believes in by flying the airframe
the other way, so the vehicle physically goes where the ramp tells it to go.
Against a matched-window nominal control of ~39 m, the three joint-miss cells
put the airframe **48.0–48.8 m past its clean-flight envelope**, and neither
monitor said anything about GPS.

The ordering is the finding:

| | injected | excess airframe excursion | detected |
|---|---|---|---|
| a55.7_s20 (2.79 m/s) | 56.5 m | −0.2 m | yes, EKF var 6.25 |
| a55.7_s60 (0.93 m/s) | 56.4 m | **+48.8 m** | no, EKF var 0.53 |
| a55.7_s120 (0.46 m/s) | 56.5 m | **+48.5 m** | no, EKF var 0.26 |
| a55.7_s240 (0.23 m/s) | 56.5 m | **+48.0 m** | no, EKF var 0.14 |

The detected fault is the one the vehicle refuses to fly. The undetected ones
are the ones it flies. That inversion is not visible at all in run 1's
quantity, because run 1's quantity was the two effects added together.

One cell resists the pattern and is recorded rather than smoothed over:
**a556.6_s240** is detected (EKF variance 5.30, well past the 0.8 threshold)
and still produces a 68.8 m excess excursion. Detection there did not prevent
displacement. Whatever else follows, "the estimator caught it" is not the same
claim as "the airframe stayed put", and the two must be reported separately.

---

## 7. What could still be wrong

- `SIMSTATE` is the simulator's own truth. On hardware there is no such
  channel, and an equivalent bench would need an external reference. Nothing
  here transfers to a flight test without one.
- The excursion control is a **matched-window nominal arm**, not the same
  flight counterfactually un-injected. SITL is close to deterministic on a
  fixed seed and the four nominal arms agree to within 0.5 m (39.13–39.59 m),
  but this is a control, not a paired difference.
- Eight cells, one flight each. Rule 3 stands: **ticks are not independent
  replicates**, and neither are these cells. The joint-miss finding is three
  cells that share an amplitude, not a characterised region.
- The corrected instrument reads 1.014–1.022 on the a55.7 cells, i.e. about
  1.5–2% high. That is the receiver's own `noise_horizontal` wander, which is
  ~1.2 m and adds in quadrature. It is inside V6's tolerance and is not
  corrected for.
- **R10 is violated on every flight in run 2**, including all four nominal
  arms. The joint-miss result above is measured on a build where the frozen
  baseline is already raising an unrelated false alarm. The two are on
  different nodes (`gps` vs `battery`) and different windows (t≈60+ vs
  t≈46–57), so they do not overlap, but the R10 breach must be resolved before
  any candidate is scored. See `results/r10_modern.json`.

---

## 8. What this changes about how the rest of Phase II is run

Rule 1 of the permanent methodological rules is *command issued ≠ fault
injected*, and V1–V6 were written to enforce it. Run 1 shows the rule has a
second half that the contract did not cover: **a check is only as good as the
quantity it reads**. V6 was correctly specified, correctly evaluated, and
wrong, because its input was measuring two things at once.

The standing addition, applied from here on: **every validity instrument gets
a null control.** If the instrument does not read approximately zero on an arm
where nothing was injected, it is not measuring the injection. That check is
now in `modern_rig.instrument_control()` and runs on every campaign.
