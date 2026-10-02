# Real multi-producer, correlated evidence, and report quality on physical data (RB-001 Parts 24-26)

**2026-10-02.** **Parts 24 and 25 require a physical event. None could be
produced here** (`HARDWARE_INVENTORY.md`). This document fixes what the
first physical cases must show, and what is already known from simulation.
The simulation findings are labelled as such and are not counted as
physical.

## 1. Part 24: one physical event, two genuinely independent producer lineages

**The case (RB2-2, `MINIMUM_PHYSICAL_EXPERIMENT.md`).** A reversible
reduction of one motor's effect: software output scaling, or a known added
load. It is observed by:

| producer | physical lineage | expected |
|---|---|---|
| ESC telemetry (RPM) | the ESC MCU | RPM deficit |
| load-cell thrust (bench instrument, read into the same analysis as an external producer) | the load cell's own ADC and supply | thrust deficit |
| bus current (shunt) | the shunt and the logic analyzer / ADC | current change |

**What 2.2's lineage policy must do.** It counts independent lines as the
largest disjoint set of lineage roots. Here that is **3 lines**:
- RPM: root `sensor:esc.<n>`;
- thrust: root `sensor:loadcell.0`;
- current: root `sensor:shunt.0`.

They share no root.

**The test passes if** the report says 3 independent lines, with no shared
root listed, and the 2.1.1 result is unchanged by adding the external
producers. They only corroborate.

**What simulation already showed, not physical.** The 2.2 pilot's
XSYS-001 multi-producer case found 2 independent lines where 3 monitors
agreed. The pilot traced that ground truth (121/121): compensation and the
rate transient share the IMU, and the elimination rested twice on one IMU.
So the lineage policy does not over-count in SIH. The physical case tests
whether that holds when the lineage is real hardware.

## 2. Part 25: two apparently separate outputs that share one physical source

**Two physical cases, both at RB2:**

| apparently separate outputs | shared physical source | expected |
|---|---|---|
| ESC RPM and ESC current (two fields, two claims) | **one ESC MCU** | 1 lineage group; agreement between them is not corroboration |
| bus voltage and ESC voltage | **one power rail** | 1 group |

**The test passes if** the report lists them in one lineage group, gives 1
independent line, and names the shared root. The lineage roots must come
from the hardware map (`HARDWARE_EVIDENCE_PLANS.md`, Part 19), not from
topic names.

**Already shown in simulation:**
- 2.3 V1: the compensation and the telemetry outputs share the four motor
  commands. The report says "2 adverse outputs in 1 lineage group: 1
  independent line".
- The B3/B4 candidates share the IMU and the rate loop with the
  compensation. If either joined the product, it would corroborate the
  compensation only partly. Their lineage must name the IMU instance.

## 3. Part 26: report quality on physical data

**The rule: measured magnitudes with units, reference and threshold,** not
Booleans. The 2.3 report already does this for every stock output, and
RB-001 adds nothing that hides a magnitude.

**For physical data the report must carry:**

| quantity | unit | reference | threshold | source |
|---|---|---|---|---|
| RPM residual | fraction of commanded thrust implied by RPM (L) | the motor's own pre-event window, normalised by the other motors | recalibrated from the nominal corpus | 2.3 telemetry producer |
| command residual (compensation C) | change in the command ratio to the median motor; 1/eta - 1 for a compensated loss | pre-event window | recalibrated | 2.3 compensation producer |
| control-conditioned loss estimate (B3/B4, if adopted) | lost fraction of motor effect, 1 - eta | the demanded torque against the measured angular acceleration | from nominal maneuvering flights | maneuver study |
| current | A, ESC and bus | the same command before the event | recalibrated | ESC telemetry; shunt |
| voltage | V | — | PX4's battery thresholds | battery status |
| innovation ratio | EKF2 test ratio (dimensionless) | gate 1.0 | EKF2's own | 2.2 estimator producer |
| body rate | rad/s | pre-event window, on the motor's loss axis | recalibrated | rate transient (context) |
| thrust (bench only) | N | the same command, nominal runs | from the nominal corpus | load cell |

**Already true in SITL:** every stock output in `report.txt` shows value,
unit, threshold, window and sample count (2.3 `REPORT_PRODUCT.md`). The
maneuver-study outputs carry the estimated loss fraction, which reads
directly as "motor 2 produces about 60 % of its commanded effect".
