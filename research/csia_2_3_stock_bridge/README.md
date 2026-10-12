# CSIA 2.3: stock PX4 evidence bridge, automatic event discovery, multirotor profile, Flight Assurance Analyzer

**2026-10-02. NON-CONFIRMATORY. Offboard only.**

**Boundary:**
- CSIA 2.3, like 2.2, is **OFFBOARD, OBSERVATIONAL, ZERO CONTROL
  AUTHORITY**;
- no FORGE;
- no automatic recovery.

**The question:** can CSIA take an ordinary PX4 ULog, with no onset, no
labels, no research features and no witness files, and build an honest
assurance analysis from what the flight stack already logs?

**Decision: `CSIA_2_3_STOCK_BRIDGE_DEMONSTRATED_NARROW`**
(`REVIEW_AND_DECISION.md`).

## Run it

```
.venv/bin/python -m csia_evidence_assurance analyze flight.ulg --out DIR
.venv/bin/python -m csia_evidence_assurance analyze flight.ulg --estimator-only   # the 2.2 path
.venv/bin/python -m csia_evidence_assurance analyze-many <dir | list.txt> --out DIR
```

`report.txt` opens with the engineer's questions (`REPORT_PRODUCT.md`):
- WHAT HAPPENED?
- WHEN?
- WHAT DID CSIA OBSERVE?
- WHAT COULD IT NOT OBSERVE?
- WHAT EXPLANATIONS REMAIN?
- WHAT WAS ELIMINATED, AND WHY?
- WHICH MONITORS AGREED?
- WERE THEY INDEPENDENT?
- WHAT WOULD RESOLVE THE AMBIGUITY?
- IS ATTRIBUTION JUSTIFIED?

## Read in this order

| # | document | phases |
|---|---|---|
| 1 | `REVIEW_AND_DECISION.md` | decision, governance, every phase |
| 2 | `ORDINARY_ULOG.md` | 20, the product test |
| 3 | `VALIDATION_FLIGHTS_DESIGN.md`, `VALIDATION_FLIGHTS_DESIGN_2.md`, `VALIDATION_FLIGHTS.md` | 17, 20, 25, 26: designs committed before flying, results |
| 4 | `FALSE_POSITIVES.md` | 26 |
| 5 | `TOPIC_INVENTORY.md` | 1 |
| 6 | `CLAIM_REGISTER.md` | 2-7 |
| 7 | `STOCK_PRODUCERS.md` | 8, 9 |
| 8 | `MULTIROTOR_PROFILE.md` | 10 |
| 9 | `SCALE.md` | 11 |
| 10 | `EVENT_DISCOVERY.md` | 12, 14 |
| 11 | `CUSUM_TRIGGER.md` | 13 |
| 12 | `UNKNOWN_ONSET.md` | 15, 16 |
| 13 | `LOCALIZATION.md` | 17 |
| 14 | `MOTOR_VS_TELEMETRY.md` | 18 |
| 15 | `DISCIPLINE.md` | 19 |
| 16 | `REPORT_PRODUCT.md` | 21-24 |
| 17 | `VALIDATION_SET.md` | 25 |

## Code

**Product** (`csia_evidence_assurance/`, offboard):

| file | what |
|---|---|
| `stock_log.py` | stock topics, default-rate decimation, dropouts |
| `stock_stats.py` | the statistics, defined once |
| `adapters/px4_stock.py` | the five stock producers |
| `contracts/stock_*.json` | their contracts |
| `events.py` | event discovery and clustering |
| `profiles/multirotor_quad.py` | the quad profile r1 |
| `diagnosability.py` | the structural probe |
| `stock_report.py` | schema 4 |
| `stock_calibration.json` | revision 3 |
| `runs.stock_flight`, `__main__.py` | the stock path is the default for `.ulg` |

**Research** (this directory):

| file | what |
|---|---|
| `verify_2_3_baseline.py` | Phase 0 and the final state |
| `topic_inventory.py`, `extract_stock.py`, `investigate_stock.py` | inventory, extracts, investigation |
| `calibrate_23.py`, `calibrate_steady.py` | calibration |
| `blind_onset_replay.py` | the XSYS-001 replay |
| `scale_test.py` | scale |
| `cusum_trigger_study.py` | the frozen CUSUM as a trigger |
| `sitl_validation_runs.py`, `validation_analysis.py` | the validation flights |
| `false_positive_search.py` | false events |
| `validation_set.py`, `synthetic_stock.py` | the validation set and its synthetic logs |

**Tests:** `tests/test_csia_2_3_stock_bridge.py`.

## Data

**Machine-readable results**, committed:

| file | what |
|---|---|
| `BASELINE_2_3.json`, `FINAL_STATE_2_3.json` | baseline and final state |
| `TOPIC_INVENTORY.json`, `TOPIC_COVERAGE_MATRIX.csv` | topic inventory |
| `CLAIMS.json` | the claim register |
| `STOCK_EVIDENCE_INVESTIGATION.json` | the stock investigation |
| `CALIBRATION_2_3.json`, with the r1 and r2 versions kept | calibration |
| `ONSET_TRUTH.json` | scoring only |
| `BLIND_ONSET_REPLAY.json` | the XSYS-001 replay |
| `SCALE_2_3.json` | scale |
| `CUSUM_TRIGGER_STUDY.json` | the frozen CUSUM as a trigger |
| `VALIDATION_RESULTS.json`, `VALIDATION_RESULTS_AS_FLOWN.json` | the validation flights |
| `FALSE_POSITIVE_SEARCH.json`, `FALSE_POSITIVE_SEARCH_r2_as_found.json` | false events |
| `VALIDATION_SET.json` | the validation set |

**Per validation flight:** `reports/V*/report.txt` and `manifest.json`.
`report.json` regenerates byte for byte; its hash is in the manifest.

**Raw logs are not committed:**
- `/home/user/csia_2_3_raw/`: the 13 validation ULogs, the stock
  extracts and the apparatus logs;
- their SHA-256 values are in the results.
