# CSIA Reality Bridge 001: review and decision

**2026-10-02. NON-CONFIRMATORY. OFFBOARD only, ZERO CONTROL authority, NO
FORGE.**

## 1. Decision

**`RB001_BLOCKED_ON_PHYSICAL_DATA`**

**The brief names no decision tokens,** and its text ends inside Part 35.
These are the ones this review chose between:

| token | meaning | chosen? |
|---|---|---|
| `RB001_EVIDENCE_SURVIVES_PHYSICAL_CONTACT` | on physical data (RB2+), the 2.3 evidence relationships hold after recalibration only | no: there is no physical data |
| `RB001_EVIDENCE_NEEDS_PHYSICAL_REDEFINITION` | physical data shows that one or more relationships need a new validity condition or model | no: the predictions point this way (`TRANSFER_CLASSIFICATION.md`), but predictions are not physical data |
| `RB001_EVIDENCE_DOES_NOT_SURVIVE` | physical data shows the central relationships fail | no |
| `RB001_BLOCKED_ON_PHYSICAL_DATA` | no physical data reached the program, so the mission's question is unanswered; everything that can be done without hardware is done, and the minimum physical experiment is defined | **yes** |
| `RB001_SEMANTIC_CORE_DEFECT_STOP` | Semantic Core 2.1.1 fails on real data for a semantic reason (Part 35) | no: no semantic failure on any real data |
| `RB001_GOVERNANCE_BLOCK` | a governance rule could not be kept | no |

**Why "blocked" and not a finding.** The mission is to find out whether the
evidence relationships survive real sensors, actuators, timing, noise,
vibration and variability. Of those six, this program measured two on
real data: timing, and sensor noise at rest. It measured none of them on a
real propulsion event. No real propulsion event was reachable:
- this session has no USB bus and no instrument (`HARDWARE_INVENTORY.md`);
- the network policy refuses every host that serves real flight logs
  (`RB0_REAL_LOGS.md`).

## 2. What was found

**On real data (RB0: four real boards' logs, none flying a propulsion
event):**
- **RR-01, a crash:** the product crashed on every log from another PX4
  version (KeyError in the estimator reader). It was fixed narrowly, as a
  coverage notice; every historical report is byte-identical.
- **What the product then says on those logs:** it observed 0-1 of 29
  profile records, named why, and claimed nothing.
- **Real timing and real noise break two 2.3 rules:**
  - the gap rule's reference interval (RR-04, RR-05). It refuses a real
    loss when real jitter is applied to a SITL log;
  - the peak-rate steadiness condition (RR-06). Real boards at rest exceed
    θ_steady.
  - Both fixes are **specified, not applied.** Part 1 forbids changing
    evidence definitions yet, and no real propulsion log confirms either.
- **Real dropouts transfer:** 6 of 6 were flagged (RR-03).

**In SITL, the maneuver study** (`MANEUVER_STUDY.md`; designed, calibrated
and preregistered before 13 new flights):

| candidate | false symptoms | maneuvering losses found | wrong motor | verdict |
|---|---|---|---|---|
| B0, the product | 0 | 0 / 6 | 0 | FAIL: the hole stays |
| B1, loosened gate | **163** | 6 / 6 | 52 | **FAIL on S1: does not move to hardware** |
| B2, regime thresholds | 0 | 4 / 6 | 0 | FAIL |
| B3, control-conditioned residual | 0 | 6 / 6 (and EH1) | 0 | **PASS** |
| B4, GLR | 0 | 6 / 6 | 6 | FAIL |

**B3 goes forward to the RB5 design as a candidate. It does not enter the
product.**
- In SIH its estimate equals the lost fraction within 0.004. That is
  because SIH's plant is B3's model.
- On hardware the model must first be identified, and its null measured.
  Its transfer class is REQUIRES_NEW_MODEL.

**Under log stress** (`LOG_COMPLETENESS.md`): missing samples never became
healthy evidence.

## 3. What was built for the physical program, and not run

| part | document |
|---|---|
| 7 hardware inventory (nothing AVAILABLE; one owner-reported desktop unverified) | `HARDWARE_INVENTORY.md` |
| 8-14 the minimum experiment: RB2, one motor and ESC with telemetry on a load-cell stand, current-limited, propeller only inside a guard; observables ranked; independent ground truth; reversible faults; A vs B; nominal corpus; calibration | `MINIMUM_PHYSICAL_EXPERIMENT.md` |
| 15 false-alarm budget, from intended use: events ≤ 6/h, false symptoms ≤ 0.1/h, wrong UNIQUE 0 known and ≤ 0.01/h | `FALSE_ALARM_BUDGET.md` |
| 16-21 event discovery, timing, lineage, common-cause map, producer health on hardware | `HARDWARE_EVIDENCE_PLANS.md`, `LOG_COMPLETENESS.md` |
| 22-23 HIL; the lane switch with no fake multi-lane evidence | `HIL_AND_LANE_SWITCH.md` |
| 24-26 physical multi-producer and correlated cases; report quality | `PHYSICAL_EVIDENCE_CASES.md` |
| 27-28 receipts and transfer classes | `REALITY_RECEIPTS.md`, `TRANSFER_CLASSIFICATION.md` |
| 29 decision quality (physical column empty, and says so) | `DECISION_QUALITY.md` |
| 30-31 the research question (not asked yet) and the product question | `RESEARCH_AND_PRODUCT.md` |
| 32-35 external test (precondition not met), onboard hold, FORGE hold, stop conditions | `HOLDS_AND_GATES.md` |

## 4. Governance

**Unchanged** (verified by `verify_rb001_baseline.py --final` →
`FINAL_STATE_RB001.json`):
- Semantic Core 2.1.1 and frozen v2.0;
- XSYS-001 (55/55, LB 0.7616), XSYS-A1/A2, Phase C;
- the sealed manifests;
- every 2.2 and 2.3 result, test file and validation-flight outcome;
- the failure ledger (pinned SHA, no append).

**One product change: RR-01** (`csia_evidence_assurance/runs.py`). It turns
a crash into a coverage notice, and its test is in
`tests/test_rb001_reality_bridge.py`. The 2.3 test file is untouched. No
evidence definition changed.

**OFFBOARD, ZERO CONTROL authority.** CSIA observed, analyzed, logged,
reported and compared. It commanded nothing, changed no flight-controller
behaviour and recovered nothing. NO FORGE. The SITL flights' maneuvers and
injections were the experimenter's script, as in 2.3.

**Experiment discipline:**
- designs were committed before flights;
- calibration, development and evaluation sets are disjoint (tested);
- the preregistration was committed before the evaluation flights;
- the as-run result is kept apart from the POST-HOC analysis;
- one design deviation (ET2 flown without its wind) is reported, not
  re-flown;
- no SITL result changed the product.

**The safety ladder was kept:** RB0 and SITL only. No rung above RB0 was
attempted, and none could be.

**Part 35 is truncated** after "Semantic Core 2.1.1 fails on physical data
for a semantic reason / 2.2". The conservative reading was applied
(`HOLDS_AND_GATES.md`).

## 5. What the owner can do next

**Three actions, cheapest first:**
1. **Real logs, with no hardware at all.** Make real PX4 ULogs that carry
   `actuator_motors` and ESC telemetry reachable by a session. Either
   commit them to a separate data branch, as XSYS-001's raw data was, or
   allow Flight Review or Zenodo in the environment's network policy. The
   logs can be:
   - the owner's own flights;
   - or RflyMAD's real subset.

   RB0 then becomes real. It is the gate for RR-04/05 and the first real
   null for the event-rate budget.
2. **Say what hardware physically exists,** and fill
   `hardware/inventory/e2m_sensors.yaml`. Nothing is assumed.
3. **Authorize RB2 in writing,** stage by stage
   (`MINIMUM_PHYSICAL_EXPERIMENT.md` section 3):
   - one motor and ESC with telemetry;
   - a load cell, a shunt, a tachometer;
   - a current-limited bench supply;
   - the flight controller on USB to the desktop.

   It needs no flight and no battery.
