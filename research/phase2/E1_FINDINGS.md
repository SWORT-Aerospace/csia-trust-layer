# E1 on the modern rig — findings

**Target:** ArduCopter V4.8.0-dev, built from source in this session.
**Baseline for comparison:** ArduCopter 3.3 SITL (2015 prebuilt), all Phase-I.
**Artifacts:** `results/e1_modern.json` (run 2, authoritative),
`results/e1_modern_run1_defective_instrument.json` (run 1, preserved),
`results/v6_diagnosis.json`, `results/r10_modern.json`.
**Production code changed:** none.

---

## 0. The three results, in order of how much they cost the programme

1. **F3 survives.** Three validated significant cells are missed by both
   monitors. E1's precommitted rule returns `SURVIVES_BOUNDED`.
2. **The frozen baseline B1 violates R10 on this build**, on every flight
   including all four nominal arms. The false-alert budget is a hard
   constraint in the evaluation contract, so this blocks candidate scoring
   until it is resolved.
3. **Run 1 of E1 was wrong**, and its instrument would have returned the
   opposite verdict. Documented in full in `V6_INSTRUMENT_DEFECT.md`.

Result 3 came first chronologically and is the reason 1 and 2 are trustworthy.

---

## 1. E1, as precommitted

Grid unchanged: amplitudes 55.7 m and 556.6 m, slews 20 / 60 / 120 / 240 s.
Decision rule unchanged, and written before the first flight.

**8 of 8 trials valid.** Injection confirmed at 56.4–56.5 m and 557.4 m
against requests of 55.7 m and 556.6 m. Instrument control passes: the
validity instrument reads 0.81–0.91 m on the four zero-injection arms.

| cell | rate | injected | EKF var | autopilot | CSIA (GPS) | coverage |
|---|---|---|---|---|---|---|
| a55.7_s20 | 2.79 m/s | 56.5 m | 6.249 | detects | no | AUTOPILOT_ONLY |
| a55.7_s60 | 0.93 m/s | 56.4 m | 0.525 | no | no | **JOINT_MISS** |
| a55.7_s120 | 0.46 m/s | 56.5 m | 0.262 | no | no | **JOINT_MISS** |
| a55.7_s240 | 0.23 m/s | 56.5 m | 0.139 | no | no | **JOINT_MISS** |
| a556.6_s20 | 27.83 m/s | 557.4 m | 59.309 | detects | yes | BOTH |
| a556.6_s60 | 9.28 m/s | 557.4 m | 19.776 | detects | no | AUTOPILOT_ONLY |
| a556.6_s120 | 4.64 m/s | 557.4 m | 9.893 | detects | no | AUTOPILOT_ONLY |
| a556.6_s240 | 2.32 m/s | 557.4 m | 5.296 | detects | no | AUTOPILOT_ONLY |

```
N_total 8   BOTH 1   AUTOPILOT_ONLY 4   CSIA_ONLY 0   JOINT_MISS 3
R_incremental_csia_only  0.000
R_autopilot_dependence   0.500
R_joint_miss             0.375
```

**`R_incremental_csia_only = 0`.** In eight validated significant cells there
is not one that CSIA escalates and the autopilot estimator misses. Whatever
E1 says about F3, it says nothing good about F2, which is unchanged: on this
fault class CSIA's escalation contributes no coverage the estimator does not
already provide.

### 1.1 Escalations that do not name GPS do not count

`a55.7_s20` and `a556.6_s240` both leave NORMAL after injection, on
*magnetometer* trust, not GPS. Counting those as coverage of a GPS fault would
be wrong isolation presented as detection, so `categorise()` requires the
escalation to name GPS. Both are recorded as AUTOPILOT_ONLY with
`wrong_isolation: true`.

---

## 2. The airframe consequence, which is the part that matters

The instrument defect in run 1 was caused by the vehicle's own motion
contaminating the displacement estimate. Separated out rather than folded in,
that motion is the most useful measurement in the campaign.

A slow GPS ramp presents to the estimator as a small constant velocity bias.
The velocity controller cancels the bias it believes in by flying the airframe
the other way. The vehicle physically goes where the ramp tells it to go.

Against a matched-window nominal control of 39.1–39.6 m:

| cell | rate | injected | true excursion | control | **excess** | detected |
|---|---|---|---|---|---|---|
| a55.7_s20 | 2.79 m/s | 56.5 m | 39.0 m | 39.2 m | **−0.2 m** | yes |
| a55.7_s60 | 0.93 m/s | 56.4 m | 87.9 m | 39.1 m | **+48.8 m** | no |
| a55.7_s120 | 0.46 m/s | 56.5 m | 88.0 m | 39.5 m | **+48.5 m** | no |
| a55.7_s240 | 0.23 m/s | 56.5 m | 87.6 m | 39.6 m | **+48.0 m** | no |
| a556.6_s20 | 27.83 m/s | 557.4 m | 38.9 m | 39.2 m | **−0.4 m** | yes |
| a556.6_s60 | 9.28 m/s | 557.4 m | 43.5 m | 39.1 m | +4.3 m | yes |
| a556.6_s120 | 4.64 m/s | 557.4 m | 47.7 m | 39.5 m | +8.2 m | yes |
| a556.6_s240 | 2.32 m/s | 557.4 m | 108.4 m | 39.6 m | **+68.8 m** | yes |

**The detected fault is the one the vehicle refuses to fly. The undetected
ones are the ones it flies.** At 55.7 m the fast ramp is rejected by the
estimator's innovation test and produces no excursion at all; the three slow
ramps pass the test and displace the airframe by 48 m, which is itself above
the project's own 48 m significance threshold.

This is not visible in run 1's quantity, because run 1's quantity was the
injected offset and the excursion added together.

**The counterexample is recorded rather than smoothed over.** `a556.6_s240` is
detected — EKF variance 5.30, well past the 0.8 threshold — and still produces
a 68.8 m excess excursion, the largest in the grid. Detection did not prevent
displacement. "The estimator caught it" and "the airframe stayed put" are
different claims and must be reported separately.

---

## 3. Legacy versus modern, on the two cells that overlap

Phase I's grid (`research/wp_c8/results/response_surface.json`) and E1's share
exactly two cells. Both were flown on 3.3 there and 4.8 here.

| cell | build | autopilot | CSIA detects | CSIA escalates | coverage |
|---|---|---|---|---|---|
| a55.7_s20 | 3.3 | detects | **yes** | no | ekf_only |
| a55.7_s20 | 4.8 | detects | **no** | mag only | AUTOPILOT_ONLY |
| a556.6_s20 | 3.3 | detects | yes | yes (GPS) | both |
| a556.6_s20 | 4.8 | detects | yes | yes (GPS) | BOTH |

The 556.6 m cell replicates. The 55.7 m cell does not: **CSIA's GPS physics
residual saturates on 3.3 and does not on 4.8**, at the same injected
amplitude and the same slew.

The cause is not established. Two candidates, neither tested:

- The field-mode normaliser in `online.py:433` divides each residual by that
  airframe's own running level. On 4.8 two further nodes are live and the
  flight profile differs, so the level a GPS residual is measured against is
  not the same level.
- The flight profiles differ. Phase-I flew a cruise profile; the modern rig
  flies a velocity-commanded square pattern.

This is recorded as an open question. It is a **replication failure at the
component level inside a cell whose top-line coverage replicates**, which is
the kind of thing a coverage table alone would hide.

### 3.1 Are the Phase-I numbers affected by the run-1 instrument defect?

Phase I used the same contaminated estimator. Its reported displacements
nonetheless track the requested amplitudes closely (55.01 against 55.7,
556.60 against 556.6), and run 2 shows the contamination only bites at slews
of 60 s and above, which Phase I never ran. So there is **no evidence** the
Phase-I numbers are affected.

That is not the same as having checked. ArduCopter 3.3 does publish SIMSTATE,
so this is checkable, and it has not been checked. Recorded as open.

---

## 4. R10 is violated by the frozen baseline on this build

`docs/REQUIREMENTS.md` R10: *clean nominal flight shall produce zero failsafe
transitions.* `CANDIDATE_REGISTRY.yaml` makes it a hard constraint with a
budget of 0.

**Observed: 1 transition on every one of the four nominal arms, and on all
eight fault arms before injection.** Identical in form each time:

```
NORMAL -> CRITICAL @ t~46 s: power integrity fault (battery 0.62; diagnosis nominal p=0.98)
CRITICAL -> NORMAL @ t~57 s: all monitored conditions recovered
```

### 4.1 Mechanism, measured

The driver is the **`power_thrust` edge**, not any component of the battery
node. That edge (`online.py:546`) asserts a current balance between two
independent sources:

```
batt_i  -  sum(esc_i)  -  AVIONICS_CURRENT   ~   0        scale 0.5 A
```

Measured on this build: the pack reports **29.33 A**, the four ESCs report a
combined **3.20 A**. Residual **25.15 A = 50 sigma**. Edge consistency
collapses to 3.5e-07, `battery`'s neighbour evidence falls to 0.171, and the
failsafe's `power_critical = 0.70` does the rest.

It recovers after ~10 s only because field mode's adaptive normaliser
(`online.py:433`, tau ~90 s) raises the level until the residual is no longer
anomalous. **The layer adapts to the mismatch rather than resolving it.**

### 4.2 A wrong attribution, and how it was caught

The first pass of `r10_modern.py` blamed the `phys_battery` voltage residual.
The plant's pack resistance regresses to 0.0100 ohm against the compiled-in
0.0120; at 29.3 A that is 0.058 V against a 0.06 V scale — arithmetic that
fits the alarm almost too well.

The flight data refuted it. `components['battery']['phys']` reads **1.000 for
the entire flight**, because field-mode `_lam_upd` normalises by the running
level and anything below 1.0 maps to consistency exactly 1.0. That residual
never reaches the trust recursion.

The resistance mismatch is real and is retained as a secondary finding — a
latent near-miss sitting just under its threshold — but it is not the cause.
The script now logs every component individually instead of inferring one.

### 4.3 Why no Phase-I test could have found this

Two independent structural reasons:

- **The channels did not exist.** ArduCopter 3.3 emits neither
  `BATTERY_STATUS` nor `ESC_TELEMETRY_1_TO_4`, and `plugins.py` sources
  `battery` and `motor_esc` from exactly those two messages. Neither was ever
  fresh, so `online.py:613` gated both to zero availability and the
  `power_thrust` edge never evaluated. Both nodes were dead for the whole
  Phase-I campaign. They cast no phantom healthy vote — the freshness gate
  handles that correctly — they simply never voted.
- **The bench generates both sides of the balance from one equation.**
  `csia/sensors/truth.py:140` defines pack current as
  `motor_current.sum(axis=1) + AVIONICS_CURRENT`, which is the sum the edge
  checks. The edge is satisfied by construction. No bench test could fail it.

**R10 has only ever been verified where the plant is the monitor's own model,
or where the channels were absent.** This is the first time the requirement
has met an independent plant, and it fails within 47 s of every flight.

### 4.4 Is this a simulator artifact?

Open. Real ESC telemetry current is frequently a coarse per-ESC estimate that
does not sum to measured pack current, so the assumption may fail on hardware
as well. Nothing here settles it. What is settled is that the requirement's
verification evidence does not cover the case.

---

## 5. What this does to the Phase-II plan

**The invention gate stays CLOSED**, and for a new reason. It was gated on
B0–B4 being measured. B2, B3 and B4 are scored against a contract whose
binding constraint is R10, and the frozen baseline B1 does not satisfy R10 on
this build. Scoring candidates against a budget the baseline itself breaks
would be meaningless.

Sequence, in order:

1. **Resolve the R10 breach** on the modern rig. Not by moving the budget —
   section 6 of the brief fixes it — but by establishing whether the
   `power_thrust` assumption is wrong, the SITL ESC telemetry is wrong, or
   both, and recording the answer.
2. **Then** run B2/B3/B4 against B0/B1 on this rig.
3. Only then does the invention gate become answerable.

**F3's status changes from `REFUTED` to `SURVIVES_BOUNDED`,** with the bound
stated plainly: three cells, one amplitude, one flight each, one autopilot,
one flight profile. Rule 3 stands — these are not independent replicates of a
characterised region. What E1 licenses is "a joint miss exists in the tested
grid", not "a blind region has been mapped".

**No larger grid is launched to explore it.** The brief forbids widening the
grid to rescue F3 without a distinct preregistered hypothesis, and that
prohibition applies just as much now that the result came out favourably.

---

## 6. Standing report

**What was measured.** Eight fault cells and four nominal arms on ArduCopter
4.8, with injection verified against simulator truth on every trial; the
airframe's own displacement against a matched control; and the full component
decomposition of the battery node on a clean flight.

**What surprised me.** That the detected cells are the ones with no airframe
consequence and the undetected cells are the ones that displace the vehicle by
48 m. The response surface reads as a detection story and is a control story.

**What I got wrong, and how I found out.** Two things. Run 1's displacement
instrument measured the injected offset and the airframe's motion added
together; found by flying a nominal arm and seeing the instrument read 38.89 m
with nothing injected. And the first R10 attribution blamed the battery
voltage residual on arithmetic that fit; found by logging
`components['battery']['phys']` and seeing it sit at 1.000 throughout.

Both errors share a shape: a quantity was assumed to measure what its name
said. The standing correction is `instrument_control()` — every validity
instrument now gets a null control — and the rule that a mechanism is not
attributed until the intermediate quantity has been logged.

**What I could not determine.** Why CSIA's GPS physics residual saturates on
3.3 and not on 4.8 in the a55.7_s20 cell. Whether the ESC-versus-pack current
mismatch is a simulator artifact or a real-hardware condition. Whether the
Phase-I displacement numbers would survive re-measurement against 3.3's
SIMSTATE.

**What remains open, with an owner.**

| item | owner | blocks |
|---|---|---|
| R10 breach: `power_thrust` versus SITL ESC telemetry | this session | all candidate scoring |
| B2 / B3 / B4 measurement on the modern rig | this session | the invention gate |
| Component-level replication failure at a55.7_s20 | this session | confidence in cross-build comparison |
| Phase-I displacement re-measurement against 3.3 SIMSTATE | this session | nothing; it is a check, not a dependency |
| PX4 as a second independent stack | not started | external validity |
| `INFORMATION_ARCHITECTURE_DIFF.md`, `INDEPENDENT_COVERAGE.md` | not started | the Phase-II write-up |
