# Product gap analysis (Phase 24)

**2026-10-01.**

**What this lists:** what stands between the Analyzer MVP and a tool an
engineer outside this team would use on their own logs. Each gap names the
evidence that exposed it.

**Priority:**
- **P1:** blocks the value on a user's own log;
- **P2:** limits trust in the answer;
- **P3:** polish.

## 1. The gaps

| id | gap | evidence | priority | smallest next step |
|---|---|---|---|---|
| G1 | **No producer reads a stock PX4 log for anything the profile diagnoses.** EKF2's claims are context. On a stock log, 0 of 68 profile records are observed | `SCALE.md`, WA-3: 66/66 flights | P1 | a producer per record family, from topics the log already has: `esc_status` against `actuator_motors` (propulsion response), `battery_status` (power), `control_allocator_status` (saturation), `cpuload` (compute), `telemetry_status` (link). Each needs a contract, a validated window and a calibration from real data. None was built here: the brief excludes monitors made for the pilot |
| G2 | **The XSYS-001 witnesses need the onset time.** They are computed at onset-relative windows (T1, T3) from a known injection time. A real incident has no known onset | `runs.xsys_trial`; the stage-1 features | P1 | an onset detector with its own contract, validated on the 55 A flights; or witnesses defined on sliding windows, revalidated |
| G3 | **The aircraft profile models one motor.** Its records name `ACTUATION/motor_0` only; a quadrotor has four. The XSYS-001 specification has four, but no function table | the profile's record list (`profile_coverage`) | P1 | a successor profile with four motors through the gate (PV1-PV9, citations) and owner review |
| G4 | **One PX4 version, SITL only.** Every adapter reads PX4 547e2ca topic layouts. No hardware log has been analysed | `CAMPAIGN_REPLAY.md` §3 | P1 | a version check in each adapter that refuses an unknown layout; one real hardware log end to end |
| G5 | **No magnitudes in the report** (thrust or RPM deficit, innovation value) | `ENGINEER_USEFULNESS.md` question 15 | P2 | print each output's measured and expected value beside its id |
| G6 | **No declared diagnostic role per claim.** An uninformative claim prints NOMINAL beside an informative one (FV-2) | `FALSE_VALUE_SEARCH.md` §3 | P2 | a contract field: context or diagnostic, and the fault classes the claim is known blind to, each with its evidence |
| G7 | **Usefulness not measured with outside engineers** | `EXTERNAL_USER_TEST_PLAN.md` (not run) | P2 | run the plan with the nine cases |
| G8 | **Lineage ground truth comes from the team that wrote it** | `INDEPENDENCE_AND_CORROBORATION.md` §2 | P2 | an outside reviewer traces the four producers' sources blind, before seeing 2.2's lineage |
| G9 | **A real lane switch has not been analysed** | `SITL_SELECTOR_RUN.md`; `LANE_SWITCH_EXPERIMENT_DESIGN.md` | P2 | the frozen 3-IMU SIH design; it needs a simulator change and owner approval |
| G10 | **Estimator freshness cannot be used.** The profile's 0.10 s output-age limit is below EKF2's 0.15-0.2 s delayed horizon (EM-1) | `ESTIMATOR_CLAIM_MAPPING.md` §4 | P3 | a successor-profile change, with citations |
| G11 | **The manifest omits the Python and library versions** (numpy, pyulog) and the PX4 build | `ANALYZER_MVP.md` §2 | P3 | add them; they change no report byte |
| G12 | **The XSYS-001 input prints the stage-0 truth label** in the report and manifest | U1 inputs: `truth` | P3 | research input only. A product input kind must never carry truth |
| G13 | **Long final state** when many localizations share their refuters (U8: five) | `ENGINEER_USEFULNESS.md` §5 | P3 | group localizations with identical refuters |
| G14 | **Static profile warnings in every report** | `FALSE_VALUE_SEARCH.md` row 16 | P3 | one line pointing to the manifest |
| G15 | **The whole log is loaded into memory** (pyulog): peak 72-168 MB for logs of 19-120 MB | `SCALE.md` | P3 | read only the topics the adapters declare |
| G16 | **"NOTHING_ADVERSE" beside adverse outputs** (FV-3) | `FALSE_VALUE_SEARCH.md` §3 | P3 | a wording change in 2.1.1, through its own revision process, not in 2.2 |

## 2. What the gaps say together

**G1-G4 decide the product.**
- The Analyzer adds measured value when it has several real producers on
  one event (`BASELINE_COMPARISON.md`).
- Today it has them only in a research campaign:
  - the producers are computed from sealed features;
  - they need a known onset;
  - one SITL autopilot version;
  - a one-motor profile.

**Closing G1-G3 is monitor engineering, not 2.2 engineering.** 2.2's
contracts, admissibility, lineage and report are ready to take the
producers:
- the PX4 adapter;
- the XSYS adapters;
- 14 mutation probes;
- 242 faulted-producer injections.

**G5-G8 decide whether the answer is trusted.** None needs a new idea.

## 3. What is not a gap

| item | why not |
|---|---|
| speed | about 2.8 s per flight log (median), offboard |
| determinism | byte-identical across processes, seeds and directories; pinned |
| batch robustness | 66/66, with a failed input recorded rather than stopping the batch |
| semantic correctness on the cases run | 0 wrong UNIQUE or SUPPORTED on 3,872 slots; no 2.1.1 defect (`WRONG_ANSWER_SEARCH.md`) |
