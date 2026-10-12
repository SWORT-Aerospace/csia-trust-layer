# CSIA Reality Bridge 001 (RB-001): does the evidence survive contact with reality?

**2026-10-02. NON-CONFIRMATORY.**

**Boundary:**
- **OFFBOARD, OBSERVATIONAL, ZERO CONTROL AUTHORITY;**
- NO FORGE;
- no autonomous recovery;
- nothing here commands an actuator or changes flight-controller
  behaviour.

**The mission (the brief).** Determine whether the evidence relationships
that made CSIA work in PX4 simulation survive:
- real sensors and real actuators;
- real timing and real noise;
- real vibration;
- real hardware variability.

The aim is not a new version or new architecture.

**Decision: `RB001_BLOCKED_ON_PHYSICAL_DATA`** (`REVIEW_AND_DECISION.md`).

**Why it is blocked:**
- this environment has no hardware path;
- its network policy refuses every source of real flight logs;
- so the question is unanswered.

**Everything that does not need hardware is done,** and the minimum
physical experiment is defined.

## The answer so far, in five lines

1. **On real logs from four boards, the product first crashed (RR-01), now
   degrades honestly.** It observes 0-1 of 29 records on other PX4
   versions and says why.
2. **Real timing and noise break two 2.3 rules:**
   - the gap rule's reference interval (RR-04/05);
   - the peak-rate steadiness condition (RR-06).

   The fixes are specified and gated on the first real propulsion log, not
   applied.
3. **Loosening the steadiness gate brings false symptoms back:** 163 on
   13 new SITL flights. It does not move to hardware.
4. **A control-conditioned residual (B3) found 7 of 7 SITL losses,
   including 6 during maneuvering, with 0 false and 0 wrong-motor
   symptoms.** It goes forward to the RB5 design as a candidate, not into
   the product. In SIH its model is the plant, so this is the easy case.
5. **The cheapest step that would change the answer is real data.**
   - With no hardware at all: the owner's own ULogs with ESC telemetry, or
     RflyMAD's real flights.
   - Otherwise: RB2, one motor on a thrust stand.

## Read in this order

| # | document | brief parts |
|---|---|---|
| 1 | `REVIEW_AND_DECISION.md` | decision, governance, next actions |
| 2 | `REALITY_RECEIPTS.md` | 27: what was actually observed to differ |
| 3 | `RB0_REAL_LOGS.md` | RB0: real logs, RR-01 |
| 4 | `MANEUVER_STUDY.md` | 3-6: B0-B4, as-run and post-hoc |
| 5 | `MANEUVER_FLIGHTS_DESIGN.md`, `MANEUVER_PREREGISTRATION.md` | 5-6, committed before the flights they govern |
| 6 | `MINIMUM_PHYSICAL_EXPERIMENT.md` | 8-14: the RB2 bench |
| 7 | `HARDWARE_INVENTORY.md` | 7 and the environment |
| 8 | `FALSE_ALARM_BUDGET.md` | 15 |
| 9 | `TRANSFER_CLASSIFICATION.md` | 28 |
| 10 | `REALITY_GAP_AUDIT.md` | 1 |
| 11 | `LITERATURE.md` | 2 |
| 12 | `LOG_COMPLETENESS.md` | 18 |
| 13 | `HARDWARE_EVIDENCE_PLANS.md` | 16, 17, 19, 20, 21 |
| 14 | `HIL_AND_LANE_SWITCH.md` | 22-23 |
| 15 | `PHYSICAL_EVIDENCE_CASES.md` | 24-26 |
| 16 | `DECISION_QUALITY.md` | 29 |
| 17 | `RESEARCH_AND_PRODUCT.md` | 30-31 |
| 18 | `HOLDS_AND_GATES.md` | 32-35 |

## Reproduce

**Raw ULogs are not committed.** Their SHA-256 values are in the result
files. They live under `/home/user/rb001_raw/`.

```
.venv/bin/python research/rb001_reality_bridge/verify_rb001_baseline.py [--final]
.venv/bin/python research/rb001_reality_bridge/sitl_maneuver_runs.py --runs CAL1,...   # needs the XSYS-001 SITL build
PYTHONPATH=. .venv/bin/python research/rb001_reality_bridge/calibrate_maneuver.py
PYTHONPATH=. .venv/bin/python research/rb001_reality_bridge/evaluate_maneuver.py --set dev|eval
.venv/bin/python research/rb001_reality_bridge/as_run_verdict.py
PYTHONPATH=. .venv/bin/python research/rb001_reality_bridge/posthoc_maneuver.py     # POST-HOC
PYTHONPATH=. .venv/bin/python research/rb001_reality_bridge/rb0_real_logs.py            # reads /home/user/rb001_raw/github/*.ulg
PYTHONPATH=. .venv/bin/python research/rb001_reality_bridge/log_completeness_stress.py
.venv/bin/python research/rb001_reality_bridge/reality_gap_audit.py
.venv/bin/python research/rb001_reality_bridge/receipts_and_transfer.py
.venv/bin/python -m pytest -q tests/test_rb001_reality_bridge.py
```

## Files

| kind | files |
|---|---|
| as-run data and results | `MANEUVER_CALIBRATION.json`, `MANEUVER_RESULTS_DEV.json` (development, already seen), `MANEUVER_RESULTS_EVAL.json`, `MANEUVER_VERDICT_EVAL.json`, `RB0_REAL_LOGS.json`, `LOG_COMPLETENESS_STRESS.json` |
| post-hoc | `MANEUVER_POSTHOC.json` |
| tables | `REALITY_GAP_AUDIT.json`, `REALITY_RECEIPTS.json`, `TRANSFER_CLASSIFICATION.json` |
| state | `BASELINE_RB001.json`, `FINAL_STATE_RB001.json` |
| tests | `tests/test_rb001_reality_bridge.py` |
