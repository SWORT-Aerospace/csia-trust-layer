# Simulation contract (S1)

**A scenario is not a result until the chain closes.**

Phase-II permanent rule 1: **COMMAND ISSUED != FAULT INJECTED.** Setting
`SIM_GPS1_GLITCH_X` and observing nothing is not a negative result. It is an
unproven intervention, and scoring it as a miss manufactures evidence that a
detector failed when the fault may never have existed.

We have paid for this. The E1 run-1 displacement instrument measured injected
offset and airframe motion together and read 38.89 m on a **zero-injection**
arm. Every number from that campaign had to be discarded and re-flown.

---

## 1. The six stages

Each is a boolean **plus the measured intermediate that justifies it**. A
stage is not satisfied by an assertion; it is satisfied by a number.

| stage | question | typical evidence |
|---|---|---|
| `COMMAND_ISSUED` | did the parameter write succeed? | `PARAM_VALUE` echo matches what was set |
| `SIMULATOR_STATE_CHANGED` | did the simulator's own state move? | `SIMSTATE` / `SIM_STATE` delta |
| `SENSOR_OUTPUT_CHANGED` | did the sensor downstream move? | `GPS_RAW_INT` separation from `SIMSTATE` |
| `AUTOPILOT_RECEIVED_CHANGE` | did the estimator see it? | `EKF_STATUS_REPORT.pos_horiz_variance` |
| `CSIA_RECEIVED_CHANGE` | did the canonical sample carry it? | the channel is `usable` and its value moved |
| `GROUND_TRUTH_MATCHES_EXPECTATION` | does magnitude match the order? | measured offset vs commanded, within tolerance |

`TrialContract.first_break` names where the chain broke, which is far more
useful than knowing only that it did.

---

## 2. Three verdicts, and the third is the point

```
VALID              chain closed; the trial may be scored
INVALID_SCENARIO   intervention unproven -- NOT a fail, NOT a pass
INSTRUMENT_DEAD    the null control moved; nothing is concludable
```

**Collapsing `INVALID_SCENARIO` to FAIL is how a broken injection becomes a
published detector weakness.** `TrialContract.require_valid()` raises, so
campaign code cannot compute a metric from an unscorable trial by forgetting
to check.

---

## 3. RULE A — every instrument needs a null control

An intervention instrument that has never been shown to read *zero* when
nothing is injected cannot be trusted to read *something* when something is.

`NullControl.tolerance` is the **measured noise ceiling of the control**, not
a number chosen to make a trial pass. Raising it requires control data.

This rule applies to our own tooling, and it caught a defect while this
package was being written. `tools/simulation/qualify_platform.py` measures
whether a channel varies, to separate real signals from stubs. Run against a
**stationary disarmed** ArduCopter, nine channels read perfectly constant --
battery voltage (no load), GNSS position (not moving), barometric altitude (on
the ground), armed flag (false) -- and the tool called them stubs.

They are not stubs. Nothing was happening.

The fix was a **positive control**: the probe now arms and climbs, and records
`armed` and `climbed_m` as evidence that the control fired. If the airframe
did not move, the run is `INVALID_PROBE` and **no channel verdict is issued at
all**. An informativeness measurement without motion is not a weak
measurement; it is not a measurement.

---

## 4. RULE B — no mechanism attribution without the intermediate

If a trial claims "the spoof broke the `heading_course` edge, so the
magnetometer took the blame", then the edge consistency at that tick must be
in `mechanism_intermediates`. Claiming a mechanism whose intermediate was
never observed is how a battery-voltage residual once got blamed for a fault
driven by an entirely different edge — the arithmetic fit, and it was wrong.

---

## 5. Scenario families and their INVALID modes

| family | injection | classic INVALID cause |
|---|---|---|
| clean | none | — (this is the null control for everything else) |
| GNSS spoof / offset | `SIM_GPS1_GLITCH_*` | old `SIM_GPS_*` name silently ignored on 4.x |
| GNSS loss | `SIM_GPS1_DISABLE` | fix_type stays 3; denial never reached the receiver |
| IMU bias / drift | `SIM_ACC1_BIAS_*` | bias below the noise floor of the chosen profile |
| magnetic interference | `SIM_MAG1_OFS_*` | offsets absorbed by in-flight compass learning |
| power disturbance | `SIM_BATT_VOLTAGE` | ESC half of the fault does not exist in SITL (W-5) |
| vibration | `SIM_VIB_MOT_MAX` **and** `SIM_ACC*_RND` | setting only `SIM_VIB_MOT_MAX`; amplitude comes from `accel_noise` |
| dual-IMU degradation | `SIM_ACC2_BIAS_*` | both SITL IMUs share one dynamics source |

The vibration row cost two probes before the cause was found. A campaign that
sets only one of the two parameters produces an `INVALID_SCENARIO`, not a
negative result.

---

## 6. Profiles (S4)

Every simulated result must name the profile that produced it.

| profile | basis | representative? |
|---|---|---|
| `IDEAL_SIM` | simulator defaults | **no** — not evidence about an aircraft |
| `REALISTIC_SIM` | engineering judgement | **no** — labelled as judgement |
| `FIELD_DERIVED_NOISE` | 26-log public corpus | **no** — 26 logs are not a fleet |

**None is claimed to be statistically representative.** From an unannotated
corpus we take only what is estimable without labels: marginal noise, jitter,
dropout frequency, dispersion, regime occupancy. We take **no**
fault-conditioned quantity, because you cannot condition on a label that does
not exist.

The reason this matters is measured: IMU-bias detection is present at `sim`
noise and **absent** at `field` noise (min trust 0.99, no detection). The
detection was a property of the noise model.
