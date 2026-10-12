# Maneuver study: SITL flights, designed before any of them is flown (RB-001 Parts 5-6)

**2026-10-02. Written and committed before any of these flights is flown.**

## 1. Purpose

**The coverage hole.** CSIA 2.3 refuses its compensation evidence when the
vehicle is not near-steady (NOT_STEADY_FLIGHT). That removed the false
`COMMAND_NO_RESPONSE` on maneuvering flights, but it left a hole: a motor
losing effectiveness during continuous maneuvering is not confirmed (2.3
validation flight V13).

**What these flights test.** Whether any of five candidates (`maneuver.py`,
B0-B4) closes that hole **without** restoring false symptoms on nominal
maneuvering. B0 is the current product.

**The sets are separate.** No flight is in two of them:

| set | flights | used for |
|---|---|---|
| development | 2.3 validation flights V1-V13 (already flown, already seen) | choosing the formulations, the lag constant and the window; nothing is calibrated on them |
| calibration | CAL1-CAL5 below, nominal only | the model (g, c, mixing, noise) and every threshold, by one fixed rule |
| evaluation | EN1-EN4, EF1-EF6, EH1, ET1, ET2 below | scoring only; flown **after** `MANEUVER_PREREGISTRATION.md` is committed |

## 2. Apparatus (unchanged from 2.3)

- **Build:** the XSYS-001 SITL build, PX4 547e2ca with the SIH_MOT_EFF1-4
  patch.
- **Logging:** PX4's default logging; no `logger_topics.txt`.
- **Faults:**
  - `SIH_MOT_EFFn` set over MAVLink (the simulator's motor effectiveness);
  - or PX4's stock failure injection (`MAV_CMD_INJECT_FAILURE`, ESC OFF or
    WRONG).
- **Maneuvers:** `MAV_CMD_DO_REPOSITION`, with north and east offsets in
  metres from the take-off point, an altitude offset from 10 m, and a
  heading.
- **Schedule:** arm at 20 s; times are seconds from boot.
- **Runner:** `sitl_maneuver_runs.py`. It imports the 2.3 runner's helpers
  without changing that file.
- **Flown once each.** A run that fails is recorded as failed, not re-flown.

## 3. Calibration set (nominal only)

| id | maneuvers | wind | end |
|---|---|---|---|
| CAL1 | none: hover | none | 120 s |
| CAL2 | repositions every 12 s from 40 s: 50 m legs, 90-degree heading steps | none | 150 s |
| CAL3 | every 8 s: 30 m legs, 180-degree heading changes | north 3 m/s | 150 s |
| CAL4 | every 10 s: 30 m legs with altitude changes of +5 / -3 m, heading fixed | east 4 m/s | 150 s |
| CAL5 | every 6 s: heading changes in place (90, 270, 45, 180 degrees) | none | 150 s |

## 4. Evaluation set (flown only after the preregistration is committed)

| id | maneuvers | wind | injection (s from boot) | end |
|---|---|---|---|---|
| EN1 | every 10 s: 45 m legs, 135-degree heading steps | north 2 | none | 160 |
| EN2 | every 7 s: 25 m legs with +4 / -2 m altitude changes, 90-degree steps | east 5 | none | 160 |
| EN3 | every 5 s: heading changes in place and 10 m moves | none | none | 160 |
| EN4 | every 15 s: 70 m legs, 180-degree turns | north 4 | none | 160 |
| EF1 | as EN1 | none | motor_0 (SIH_MOT_EFF1) = 0.6 at 83 s, mid-leg | 160 |
| EF2 | as EN2 | none | motor_1 = 0.75 at 91.5 s | 160 |
| EF3 | as EN4 | north 4 | motor_2 = 0.6 at 97 s | 160 |
| EF4 | as EN3 | none | motor_3 = 0.75 at 72.5 s | 160 |
| EF5 | as EN1 | none | motor_1 = 0.85 at 104 s (smaller loss) | 160 |
| EF6 | as EN3 | east 3 | motor_3 = 0.6 at 88 s | 160 |
| EH1 | none: hover | none | motor_0 = 0.8 at 60 s | 100 |
| ET1 | as EN1 | none | ESC 3 WRONG (motor_2 telemetry RPM x 10; motor healthy) at 85 s | 160 |
| ET2 | as EN2 | east 5 | ESC 1 OFF (motor_0 telemetry lost; motor healthy) at 85 s | 160 |

**How the evaluation set differs from the calibration set.** Its maneuver
patterns are new:
- 7 s and 5 s periods;
- 45 m and 70 m legs;
- 135-degree heading steps;
- winds of 2 and 5 m/s.

So the evaluation also tests whether a candidate generalises beyond the
regimes it was calibrated on.

**Why ET1 and ET2 are in the set.** They put a telemetry fault on a healthy
motor during maneuvering. A candidate that reads them as a physical loss
fails.

## 5. What is scored

**The success criteria are fixed in `MANEUVER_PREREGISTRATION.md`,**
committed after calibration and before any evaluation flight. The
thresholds come from CAL1-CAL5 by the rule stated there.

**Two kinds of analysis, kept apart:**
- the as-run result: the preregistered criteria, applied once;
- post-hoc analysis, labelled so.
