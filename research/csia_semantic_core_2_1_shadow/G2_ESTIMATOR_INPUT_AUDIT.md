# G-2: the estimator's inputs

**2026-09-30. Part 5 of the shadow-validation brief.**

**Sources.** Repository files and the PX4 tree at `547e2ca` were read at the
cited lines (V4). The IMU pacing-loss counterfactual is executed by
`worse_answer_search.py` (probe W7) and recorded in `WORSE_ANSWER_SEARCH.json`.

## 1. The gap

The frozen aircraft profile declares the estimator process like this:

```
state_estimator  depends_on = ("COMPUTE/cpu", "SENSOR/source.imu0")    aircraft.py line 245
```

- **No COMMUNICATION input is declared**, so under C3, FUNCTION_LINKS_NOMINAL
  on the estimator has no link to read.
- **The effect in OUTPUT_MISSING.** The estimator's hypothesis
  COMMUNICATION/input_starvation stays unresolved.
- **What that costs.** 123 OUTPUT_MISSING units are weakened (MS_A4, MS_D2
  and PROCESS_STALL). F2 then withholds 81 correct UNIQUE attributions in
  PROCESS_STALL and MS_D2.
- **How v2.0 refuted starvation.** It read *every* link in the tick. On those
  81 ticks it refuted starvation using the ESC CAN bus and the telemetry
  radio, neither of which feeds the estimator.

## 2. Which streams feed the estimator, at the code

This is PX4 EKF2 at `547e2ca` (V4).

| stream | how it reaches EKF2 | line |
|---|---|---|
| IMU (`vehicle_imu`, or `sensor_combined`) | **callback subscription: EKF2::Run is scheduled by it** | EKF2.hpp 431-432; EKF2.cpp 496-510 |
| GNSS (`vehicle_gps_position`) | polled inside the IMU-triggered run | EKF2.hpp 499; EKF2.cpp 811 (`UpdateGpsSample`, inside `if (imu_updated)`) |
| barometer (`vehicle_air_data`) | polled | EKF2.hpp 371 |
| magnetometer (`vehicle_magnetometer`) | polled | EKF2.hpp 322 |
| optical flow, range, external vision, airspeed | polled, if configured | EKF2.hpp 339-439 |

**Only the IMU paces the output.** EKF2 publishes only when a new IMU sample
has arrived (`EKF2.cpp` line 767, `if (imu_updated)`). A 100 ms backup
reschedule exists (line 890), but it publishes nothing without IMU data. So:

- **If the IMU stops, the estimator's output stops.** OUTPUT_MISSING is the
  result, and the process itself is not stalled.
- **If GNSS stops, the output continues.** The estimator dead-reckons: the
  position degrades and is eventually invalidated (POSITION_UNAVAILABLE), but
  it keeps being published. GNSS loss cannot starve the output.

**Which estimator outputs feed functions:** local and global position,
attitude and odometry (EKF2.hpp lines 476-479). Every navigation consumer
reads them (`G1_COARSE_NAVIGATION_AUDIT.md` §3).

## 3. Which links matter diagnostically

| input | diagnostically relevant to | in the frozen profile | assessment |
|---|---|---|---|
| IMU (source.imu0) | OUTPUT_MISSING (pacing), POSITION_UNAVAILABLE | declared as a SENSOR dependency | right as a dependency. No COMMUNICATION link is modelled for it (it is on-board SPI), so no link predicate can speak for it |
| GNSS source (source.gps) | POSITION_UNAVAILABLE, position accuracy | **not** declared for the estimator. It is declared for nav_solution only through gnss_serial | a real information dependency (R5a) |
| GNSS link (gnss_serial) | transport delay of the position (OUTPUT_STALE on nav_solution), POSITION_UNAVAILABLE | declared for nav_solution | right for nav_solution. **Not** a starvation path for the estimator's output (R5b) |
| barometer, magnetometer | height and heading aiding | not declared | intentionally abstracted away: no signature hypothesis reads them for the estimator (R6) |
| second IMU (source.imu1) | used only if multi-IMU / multi-EKF is configured, or after a failover | not declared | **CONDITIONAL on configuration** (see `CONFIGURATION_TRANSITION_STUDY.md`, E1) |

## 4. The candidates and what shadow found

| id | declaration | kind | effect in dataset A | IMU pacing-loss counterfactual (W7) |
|---|---|---|---|---|
| R5 | estimator depends on gnss_serial and source.gps | DIRECT as information flow | restores all 204 G-2 units, including the 81 UNIQUE | **wrong**: OUTPUT_MISSING SUPPORTED process_stall |
| R5b | estimator depends on gnss_serial | the link is a real transport path for the GNSS measurement, but **NOT ACTUALLY VALID** as an input whose loss starves the output | restores the same 204 | **wrong**, as R5 |
| R5a | estimator depends on source.gps only | **DIRECT** | restores the same 204 | **wrong**, as R5. The reason is in §5 |
| R6 | estimator depends on imu1, baro and mag | DIRECT for baro and mag; CONDITIONAL for imu1 | none (inert) | not applicable |

**The W7 counterfactual.** Take PROCESS_STALL's final tick and make
`source.imu0` VIOLATED (stale). This is the estimator starved of its pacing
input: the process is not at fault.
- **v2.0:** OUTPUT_MISSING SUPPORTED COMPUTE/process_stall. **Wrong.**
- **2.1, no successor, and 2.1 with successor r1:** AMBIGUOUS, keeping
  COMMUNICATION/input_starvation open. The right answer on the declared model.
- **2.1 with R5, R5a or R5b:** SUPPORTED process_stall. **Wrong, as v2.0.**
- **Attribution in every variant:** AMBIGUOUS {state_estimator, source.imu0}.
  The wrong localization therefore does not become a wrong UNIQUE here. But
  F2 now agrees with a wrong localization instead of withholding on it.

## 5. Why a correct profile cannot fix G-2

R5a declares only the GPS *source*, which is physically true. It still
restores the wrong answer, through the closure:

1. The frozen profile declares that the GPS source depends on
   `COMMUNICATION/gnss_serial` (`SOURCE_DEPENDENCIES["gps"]`, aircraft.py
   line 189).
2. C3's scope is the transitive depends-on closure, so gnss_serial enters the
   estimator's scope through source.gps.
3. FUNCTION_LINKS_NOMINAL reads every link in the scope and returns True.
4. That True refutes COMMUNICATION/input_starvation.

**The defect is in the predicate's scope, not in the profile.** For a
starvation hypothesis, "the process's scope" is the wrong set. What can
starve a process is:

- the inputs that **pace** its output (for EKF2, the IMU), or
- at most its **direct** input links.

Every link reachable through any dependency is too wide. The closure is
right for "could this component affect the subject?". It is wrong for "could
this link have starved this process?".

**The defect is latent in 2.1 today.** The frozen profile declares no link
path to the estimator, so nothing triggers it. **Any correct completion of
the profile triggers it.**

## 6. Decision on G-2

**G-2 is EXPLICITLY BLOCKED on a signature/predicate change. It is not
resolved by profile data.**

| candidate | decision | reason |
|---|---|---|
| R5 | REJECT | restores certainty using evidence unrelated to the hypothesis it excludes (the brief's Part 7 test) |
| R5b | REJECT | NOT ACTUALLY VALID as a starvation input on PX4 |
| R5a | DEFER | physically right, but it must not enter a profile until the starvation predicate stops reading the closure |
| R6 | DEFER | baro and mag have no consumer. imu1 is configuration-dependent and belongs with the configuration-epoch work |

**What would unblock G-2.** A proposed, owner-governed change: evaluate
COMMUNICATION/input_starvation over the subject's **declared pacing inputs**
(or its direct input links), not its closure. For the estimator, add
`SENSOR/source.imu0` health as the refuter.
- **In the 81 PROCESS_STALL and MS_D2 ticks** that would refute starvation
  correctly: imu0 is fresh there, so the IMU is the reason starvation is
  ruled out.
- **In W7** it would keep starvation open, correctly.

This is a successor-semantics change, and it is not made here.

**What the weakened results are, therefore.** The 81 weakened UNIQUE ticks
and 123 weakened OUTPUT_MISSING units are ARTIFICIAL abstentions (Part 46):
the declared model cannot refute a hypothesis the evidence could refute.
They stay weakened. Restoring them through the profile would restore v2.0's
answer for v2.0's wrong reason.
