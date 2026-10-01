# CSIA 2.2 offboard pilot: real multi-producer validation and the Flight Assurance Analyzer MVP

**2026-10-01. NON-CONFIRMATORY. Offboard only.**

**Boundary:**
- CSIA 2.2 remains **OFFBOARD, OBSERVATIONAL, ZERO CONTROL AUTHORITY**;
- this pilot is not authorization for onboard authority, FORGE or
  autonomous recovery.

**The question:**

> When multiple real monitors observe the same real vehicle event, does
> CSIA 2.2 produce a more useful and more defensible engineering
> explanation than the monitors provide individually?

**Decision: `CSIA_2_2_PILOT_VALUE_DEMONSTRATED_NARROW`**
(`REVIEW_AND_DECISION.md`).

**What was found:**
- **Yes, on the one real multi-producer event available:** XSYS-001 motor
  thrust loss, 121 trials. The answer is narrow.
- **No, on a stock PX4 log:** 0 of 68 profile records are observed, and
  the report now says so.
- **The product boundary** is a SITL/HIL Validator.

## Run it

```
.venv/bin/python -m csia_evidence_assurance analyze <flight.ulg | extract.npz | scenario | XSYS id> --out DIR
.venv/bin/python -m csia_evidence_assurance analyze-many <dir | list.txt> --out DIR
```

**Each analysis writes:**
- `report.json`: deterministic;
- `report.txt`: for an engineer;
- `manifest.json`: for reproduction.

## Read in this order

| # | document | phases |
|---|---|---|
| 1 | `REVIEW_AND_DECISION.md` | decision, governance, every phase |
| 2 | `PRODUCT_QUESTION.md` | 1 |
| 3 | `MULTI_PRODUCER_EVENT_MATRIX.md` | 2, 3 |
| 4 | `INDEPENDENCE_AND_CORROBORATION.md` | 6, 7, 8 |
| 5 | `BASELINE_COMPARISON.md` | 16 |
| 6 | `FALSE_VALUE_SEARCH.md` | 17 |
| 7 | `WRONG_ANSWER_SEARCH.md` | 18 |
| 8 | `ENGINEER_USEFULNESS.md` | 15 |
| 9 | `CAMPAIGN_REPLAY.md` | 4, 10, 19 |
| 10 | `ESTIMATOR_CLAIM_MAPPING.md` | 5 |
| 11 | `COVERAGE.md` | 9, 23 |
| 12 | `SITL_SELECTOR_RUN_DESIGN.md`, `SITL_SELECTOR_RUN.md`, `LANE_SWITCH_EXPERIMENT_DESIGN.md` | 11 |
| 13 | `ANALYZER_MVP.md` | 12, 13, 14, 20, 22 |
| 14 | `SCALE.md` | 21 |
| 15 | `PRODUCT_GAP_ANALYSIS.md` | 24 |
| 16 | `PRODUCT_BOUNDARY.md` | 25 |
| 17 | `EXTERNAL_USER_TEST_PLAN.md` | 26 (plan; not run) |
| 18 | `ONBOARD_READINESS_AUDIT.md` | 27 (audit; nothing ported) |
| 19 | `RESEARCH_STATUS.md` | 28 |
| 20 | `NOVELTY_DISCIPLINE.md` | 29 |

## Data and harnesses

| file | what |
|---|---|
| `PILOT_BASELINE.json`, `PILOT_FINAL_STATE.json` | Phase 0 lock and the end-of-pilot re-verification (`verify_pilot_baseline.py [--final]`) |
| `S1_RESULTS.json`, `data/S1_estimator_extract.npz`, `research/csia_2_2_offboard_pilot/reports/S1/` | run S1: EKF2 selector on, magnetometer failed (`sitl_selector_run.py`, `analyze_s1.py`; `config/logger_topics_s1.txt`) |
| `CAMPAIGN_XSYS.json`, `CAMPAIGN_ANALYSIS.json` | the 66 flights and 121 trials through 2.2 (`campaign_xsys.py`, `analyze_campaign.py`) |
| `WRONG_ANSWER_SEARCH.json` | probes P1-P9 (`wrong_answer_search.py`) |
| `reports/U1…U8/`, `REPORT_HASHES.json` | the usefulness reports and their hashes (`usefulness_reports.py`) |
| `batch/` | `analyze-many` over the 66 flight logs: index, metrics, summary, coverage matrix |

**The raw logs are not committed:**
- the XSYS-001 logs and run S1's log stay outside git;
- every input is identified by SHA-256 in the manifests;
- the XSYS-001 logs are also identified in its `RAW_DATA_MANIFEST.json`.

## Tests

`tests/test_csia_2_2_pilot.py` pins:
- run S1;
- WA-1, WA-2 and WA-3;
- FV-1;
- the coverage states;
- the evidence basis;
- the key moments;
- the manifest;
- the commands;
- determinism across processes;
- the four reports that need no raw data, byte for byte;
- this package's documents and decision.
