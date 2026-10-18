# Phase 6 — Cross-architecture audit (H5)

**Evidence level: `SOURCE_ANALYSIS`, for every finding. Nothing was executed.**
No autopilot ran, no SITL was started, no vehicle was armed, no hardware was
touched. The preregistration's H5 vocabulary contains `RUNTIME_REPRODUCED` and
`RUNTIME_NOT_REPRODUCED`; neither appears below, because reaching them requires
running the relevant autopilot path.

Generated artifact: `research/consequence/results/CROSSARCH_AUDIT.json`
Source of the findings: `research/consequence/crossarch_audit.py`
Tests: `tests/test_consequence_crossarch.py`

| tree | commit | read at |
|---|---|---|
| PX4-Autopilot | `547e2caa9883bc1609325f02b4914b4e2482fe62` | `/home/user/px4` |
| ArduPilot | `01a504b472259602e13df4cf07df7c0cdbb35993` | `/home/user/ardupilot/ardupilot` |

---

## First: a correction to this phase's own status file

`PHASE_STATUS.md` recorded phase 6 as `BLOCKED_BY_SOURCE_ACCESS`, on the
grounds that "No PX4 or ArduPilot source tree exists in this environment".

**That was false.** Both trees were in the container the whole time, outside
the CSIA repository. The check that produced the claim ran `find` **over the
repository**, found only prior audit documents, and reported the absence as if
the search had covered the environment. The scope of the search was narrower
than the scope of the conclusion.

That is the same failure this phase exists to study, committed by the phase.
It is left in the record rather than edited out of it.

## Second: the finding that cuts against novelty

ArduPilot states the mechanism in its own source, in
`libraries/AP_Airspeed/AP_Airspeed.cpp:739`:

> The EKF3 innovation check only applies to the active sensor so a bad sensor
> will appear good after some time because the EKF is no longer using the
> sensor so cannot provide feedback.

The comment explains why ArduPilot re-selects the user's primary airspeed
sensor whenever the vehicle is disarmed. It is a deliberate workaround for a
known effect.

**So this is not a discovery.** At least one autopilot community has the
mechanism written down and has engineered around a case of it. Any claim that
this phase *found* the pattern would be false, and this document is the
citation that makes it false. What the audit adds is the enumeration and the
vocabulary, not the observation.

---

## Findings

Twelve paths, one subsystem family (airspeed, and the wind and sideslip
relations that constrain it), two stacks. Every one classifies
`STRUCTURALLY_PRESENT`. **That uniformity is a consequence of where the audit
looked, not a measurement of anything.** The paths were selected *because* they
looked like candidates; a hit rate over a hand-picked set is not a rate.

### The gating variable matters more than the classification

| gate variable kind | count | what it means |
|---|---|---|
| `VEHICLE_STATE` | 8 | the gate closes on where the aircraft is, not on how the data looks |
| `SELF_REFERENTIAL` | 3 | the gate closes on the very signal whose health is in question |
| `DATA_HEALTH` | 1 | the gate closes on a genuine data-quality condition |

The three `SELF_REFERENTIAL` cases are the ones that cannot, even in
principle, report their own failure.

### ArduPilot

**AP-1 — `AP_Airspeed_Health.cpp:38`**

```cpp
    if (state[i].airspeed <= 0) {
        // invalid estimate
        return;
    }
```

The sharpest case in the audit. A fully blocked or disconnected pitot reports
approximately zero airspeed, and approximately zero airspeed is the condition
under which the periodic health check declines to run. `test_ratio`,
`speed_diff` and `health_probability` are all skipped; no counter moves in
either direction; the driver still reports the sensor `healthy`; the data is
fresh. The guard reads as input hygiene and is almost certainly meant as such.

**AP-2 — `AP_Airspeed_Health.cpp:60`** — when the AHRS has no recent airspeed
innovation, `test_ratio` is set to `0.0f`: the most consistent value there is.
`data_is_inconsistent` is then false, and `health_probability` grows by the
0.98 coefficient. This is the repository's own evidence-semantics finding 2 —
an absence collapsing into a usable value — in another codebase. Coverage
verdict `REACTS`, not `NONE_FOUND`: the `wind_max` plausibility term still runs
on GPS speed, so the sensor can still be condemned.

**AP-3 — `AP_NavEKF3_Control.cpp:62`** and **AP-4 — `AP_NavEKF3_AirDataFusion.cpp:195`**
— `canEstimateWind` requires `!onGround`, and when it is false
`inhibitWindStates` is set. Both air-data relations, airspeed and synthetic
sideslip, hang off that one flag. AP-2's missing innovation is missing
*because* of AP-3, so the health check and the estimator are not independent
paths: coverage verdict `ALSO_GATED`.

### PX4

**PX4-1 … PX4-4 — `AirspeedValidator.cpp:228, 213, 279, 296`** — all four
validator checks are gated on `_in_fixed_wing_flight`:

- innovation check: `_innovations_check_failed = false` — *assigned* false,
  which is the value meaning "passed", not left unknown;
- stuck-data check: `... && _in_fixed_wing_flight` — a frozen reading cannot be
  declared stuck on the ground;
- load-factor check: the ratio is reset to `0.5f`, below the 1.1 threshold,
  and `_load_factor_check_failed` is not touched at all — so it is sticky
  across a flight, which is safer, but sits at its default `false` on a
  vehicle that has not yet flown;
- first-principle check: early `return`.

**PX4-5 — `AirspeedValidator.cpp:348`** — the consequence of the four together.
With every check gated off, all four flags are false, the `else` branch runs,
and `_time_checks_passed` is stamped with the current time. *No check failed*
is recorded as *all checks passed*. The four inputs are not independent of one
another; they share one gate.

**PX4-6 — `airspeed_fusion.cpp:102`**

```cpp
const bool is_airspeed_significant = airspeed_sample.true_airspeed > _params.ekf2_arsp_thr;
```

Self-referential in the same way as AP-1: a blocked pitot reads low, and
reading low is what suspends fusion; after ten seconds of not fusing,
`_control_status.flags.fuse_aspd` clears. Coverage verdict `REACTS` **in the
in-flight regime only** — `check_first_principle` uses throttle, pitch and the
IAS derivative, not the EKF, so it is genuinely independent there. On the
ground it is PX4-4. The classification is per (path, regime), not per file.

**PX4-7 — `airspeed_fusion.cpp:98`** — `continuing_conditions_passing` requires
`in_air`. Worth stating precisely: `updateAirspeed()` is still called each
cycle *before* this branch, so the innovation is still computed and published
in `estimator_aid_src_airspeed`. What disappears is the effect on the estimate
and the status flag, not the number in the log. **A consumer reading the
innovation directly is not occluded; one reading the status flag is.** That
distinction is the difference between this being a logging problem and a
diagnosis problem, and it belongs in any write-up of PX4-7.

---

## H5 outcome

H5 predicted that each audited path would be classifiable, and predicted
nothing about prevalence. Paths were classifiable, so **H5 is not killed**. No
prevalence is reported and none may be inferred.

## What this audit may not be used to say

- Not a prevalence measurement. Twelve hand-picked paths are not a sample.
- Not a universality claim. The preregistration forbids it explicitly, at any
  number of audited paths.
- Not a bug report, and not a safety judgement about PX4 or ArduPilot. Several
  of these gates have good reasons — fusing airspeed below 2 m/s would inject
  noise, and a load-factor check on the ground would be meaningless.
- Not a novelty claim. See AP-COMMENT above.
- Not RAIM. RAIM may be cited as a design analogy for availability/integrity
  reporting; it is not evidence that this mechanism matters, and the two are
  not claimed to solve the same problem.
- Nothing about runtime. No autopilot executed any of this.

## Removal action for the runtime classifications

`RUNTIME_REPRODUCED` / `RUNTIME_NOT_REPRODUCED` need a SITL run that drives the
relevant path — for AP-1, an airspeed sensor forced to zero differential
pressure in a SITL plane, with `AP_Airspeed` health logged across the ground
and in-flight regimes. That run is not in this phase and would move those
findings to `SITL`, not beyond it.
