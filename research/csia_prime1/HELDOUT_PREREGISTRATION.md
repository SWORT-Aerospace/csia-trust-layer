# Held-out event-discovery evaluation: preregistration (PRIME-1 Phases 9-12)

**2026-10-03. Committed, with the code it evaluates, before any held-out
flight is flown. EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY.**

## 1. Why new simulation, and why that is allowed here

The brief prefers real logs, then untouched simulation logs, then
prospectively generated SITL. On this machine:
- **real logs:** six, none with a propulsion event or a maneuvering multirotor
  flight (PRIME `REAL_DATA_ACQUISITION.md`). The network policy refuses
  every public real-log host;
- **untouched simulation logs:** none with maneuvering. Every earlier
  maneuvering flight was used to develop or choose a discovery rule:
  - 2.3 V1-V13 (2.3 validation, PRIME C3 development);
  - RB-001 CAL1-5 (calibration) and EN/EF/EH/ET (PRIME C3 evaluation);
  - and all of them in PRIME-1's own development checks (`DEV_CHECKS.json`).

So the promotion evidence is **prospectively generated SITL**. This
evaluation can only promote or reject the event-discovery **front end** in
simulation. It is not physical evidence, and no physical claim follows.

## 2. What is frozen (the successor, release `prime1`)

The code is in `csia_evidence_assurance/` at the commit carrying this file.
Every file is listed with its SHA-256 in `HELDOUT_FREEZE.json`, and
`heldout_eval.py` refuses to run if any differs.

| element | frozen as |
|---|---|
| algorithm | `events.discover_prime1`: one-sided CUSUM arms RPM_DEFICIT and RPM_EXCESS on the 2.3 telemetry statistic; the compensation CUSUM; PX4's monitors; an ESC-offline edge |
| telemetry gating | a telemetry alarm counts only while the channel's own trailing reference is within the declared band (q in [1/2, 2]) |
| compensation gating | an alarm counts only if its BEFORE and AFTER windows are steady (peak body rate <= theta_steady) and the heading changed by <= 15 degrees between them |
| thresholds | k_tel, h_tel, k_ctrl, h_ctrl, theta_steady: CSIA 2.3 calibration revision 3 (apparatus data only), unchanged. Two declared, uncalibrated constants: the band 2 and 15 degrees |
| calibration dataset | the 2.3 apparatus calibration. **No PRIME-1 threshold was fitted to any flight** |
| event merging | triggers within 3 s form one event (2.3); a re-raised identical PX4 condition within 60 s opens none (PRIME C3, RR-10) |
| hysteresis / debounce | none beyond CUSUM's own reset to zero and the merge above |
| test-harness records | PX4 `[failure_injection_manager]` messages are never triggers |
| timebase | canonical integer microseconds; the gate compares in integer ticks (D-PRIME-1) |

**Development history, stated:**
- the rule set was shaped on the development logs above (`DEV_CHECKS.json`:
  0 false events in 0.44 nominal hours; the telemetry matrix 30/30);
- two development-stage changes were made after looking at those logs:
  - **telemetry gating:** secondary deficit alarms on an x10-corrupted channel;
  - **compensation gating:** PRIME C3's E2 span dropped a hover loss's
    alarm, and heading reversals in wind opened events (EN4).

That is exactly why the held-out set below must be new.

**Candidates.** The baseline is release `2.3` (the product as validated).
The successor is release `prime1`.

E3 and E5 (residual CUSUM and change-point segmentation on the
control-conditioned residual) are **not candidates** for the product: they
need a dynamics model identified per vehicle (B3's g, c and mixing). A
customer log comes with no identified model.

## 3. The held-out flights (`sitl_heldout_runs.py`)

**Same apparatus as RB-001:**
- PX4 547e2ca with the SIH_MOT_EFF patch;
- default logging;
- arm at 20 s, take-off to 10 m, forced disarm in flight at the end.

**New schedules, winds, onsets and targets.**

| id | purpose | schedule | wind | fault (onset s from boot) |
|---|---|---|---|---|
| HN1 | nominal hover | none, 150 s | none | none |
| HN2 | nominal maneuvering | P_A (9 s, 40 m legs, yaw 90/180/270/0) | N 3 m/s | none |
| HN3 | nominal maneuvering, altitude changes, then hold | P_B (6 s, 15 m, +4/-2 m, yaw 0/60/120) until 95 s | E 4 m/s | none |
| HN4 | nominal long legs, heading reversals | P_C (12 s, 60 m, yaw 180/0) | none | none |
| HN5 | nominal yaw-only spins | P_Y (5 s, yaw 60/240/120/300) | N 2 m/s | none |
| HN6 | configuration transition | P_A | none | magnetometer off at 90 s (EKF2 heading aiding changes; no propulsion fault) |
| HN7 | nominal mixed | P_D (8 s, 25 m, +3/-2 m, yaw 45/225) | E 2 m/s | none |
| HN8 | hover, then maneuvers from 70 s | P_L (8 s, 30 m) | N 5 m/s | none |
| HF1 | loss in hover | none | none | motor_1 at 70 % effect, 75 s |
| HF2 | loss in a hold after maneuvers | P_B until 95 s | none | motor_2 at 60 %, 112 s |
| HF3 | loss mid-maneuver | P_C | none | motor_0 at 65 %, 93.5 s |
| HF4 | loss mid-maneuver in wind | P_D | E 3 m/s | motor_3 at 75 %, 101 s |
| HT1 | RPM excess (PX4 ESC WRONG) on a healthy motor, maneuvering | P_A | none | ESC 2 (motor_1), 84 s |
| HT2 | ESC telemetry offline on a healthy motor, hover | none | none | ESC 4 (motor_3), 70 s |

**Every flight is flown once.** A flight that fails is recorded and not
re-flown to get a better one.

**Derived held-out cases** (offline, in `heldout_eval.py`):
- every nominal flight again with microsecond-grid timestamp jitter (std 20 %
  of each topic's logging interval, seed fixed);
- the telemetry matrix (`telemetry_matrix.py`: 15 kinds, expected outcomes
  written down in the script before any run) on HN1 (hover) and HN4
  (maneuvering).

## 4. What is analysed, and how it is scored

**Each flight's blinded copy:** PX4's injection message and the SIH parameter
change removed, as a real log would be. Both releases analyse the same
copy. `prime1` also analyses the raw copy.

| measure | definition |
|---|---|
| candidate events / flight hour | all events, all flights, per in-flight hour |
| false events / nominal hour | every event in HN1-HN8, per nominal in-flight hour |
| false telemetry events | events with an RPM trigger in HN1-HN8 |
| false symptoms | any symptom in HN1-HN8, HT1 or HT2 (healthy motors) |
| wrong attribution | a COMMAND_NO_RESPONSE symptom on a motor other than the lost one; any wrong UNIQUE |
| fault found | an event within [onset - 1, onset + 2] s. For HT1 it must carry RPM_EXCESS (2.3: its telemetry trigger). For HT2: ESC_OFFLINE or an RPM trigger |
| onset error | event time minus the injection's log time (read from the raw log, scoring only) |
| confirmations | losses confirmed as COMMAND_NO_RESPONSE on the right motor (reported; not a criterion: maneuvering losses are not expected to be confirmed) |

## 5. Success criteria (all must hold to PROMOTE)

| criterion | requirement |
|---|---|
| S1 safety | `prime1`: no false symptom, no wrong-motor symptom, no wrong UNIQUE, on the blinded and the jittered copies |
| S2 recall | `prime1` finds every held-out fault, and at least as many as `2.3` |
| S3 burden | `prime1` false events <= 6 per nominal in-flight hour (blinded and jittered), and at most half of `2.3`'s |
| S4 onset | median absolute onset error of `prime1`'s found faults <= 0.5 s |
| S5 telemetry matrix | every held-out matrix case as expected for `prime1` |
| S6 no simulation leak | `prime1` gives identical events, symptoms and attribution on the raw and the blinded copy of every flight |

**Verdict:**
- **PROMOTE:** the successor discovery becomes the commercial default (it
  already is in `assure`; a NOT_PROMOTED verdict reverts that default and is
  reported);
- **NOT_PROMOTED:** the failing criteria are reported as they are. Nothing
  is re-tuned on these flights.

**The statistical limit is stated, not hidden.** About 0.3 nominal hours
cannot show a rate below 6 per hour: zero events in H hours has a 95 % upper
bound of 3/H per hour.
