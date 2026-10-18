# CSIA 2.2: Evidence Assurance, and the CSIA Flight Assurance Analyzer

**2026-10-01. NON-CONFIRMATORY. Offboard only.**

> DETECTORS PRODUCE EVIDENCE. CSIA QUALIFIES AND REASONS ABOUT EVIDENCE.

**Starting point.** The owner approved Semantic Core 2.1.1 (revision package,
commit 2b2adcc) as the preferred semantic baseline for new work, under three
operating conditions:
1. pacing declarations grounded in the implementation;
2. valid configuration-epoch context;
3. successor profiles passing the static validator.

**What this package adds.** The minimum layer that lets CSIA:
- consume real monitor outputs safely;
- decide what is admissible;
- keep dependent monitors from posing as independent;
- track producer health and configuration;
- feed 2.1.1;
- say all of it in an auditable report.

**Decision: `CSIA_2_2_READY_FOR_OFFBOARD_PILOT`** (`REVIEW_AND_DECISION.md`).

## Run it

```
.venv/bin/python -m csia_evidence_assurance scenario PROCESS_STALL
.venv/bin/python -m csia_evidence_assurance cusum power_sag
.venv/bin/python -m csia_evidence_assurance xsys XS1A1-C00-A-E055 --ulog <flight.ulg> --out DIR
.venv/bin/python -m csia_evidence_assurance ulog <flight.ulg> --out DIR
```

## The pipeline

```
existing monitors -> adapter -> EvidenceEnvelope -> admissibility -> Semantic Core 2.1.1 -> AssuranceResult -> reports
 (CUSUM, PX4 EKF2,   (wraps,     (claim, record,     (one status;      (unchanged:            (what is abnormal,  (byte-stable JSON,
  XSYS witnesses,     never      lineage, content     rejected =        Corrections.revised,   explanations left   timeline, text)
  v2 plugins)         re-implements) time, epoch,     withheld as R-3   gated profile)         and eliminated,
                                  health)             withholds)                               evidence used and
                                                                                               rejected, producers,
                                                                                               configuration, lineage)
```

**Kept simple:**
- **No provenance database:** lineage is a set of at most 16 roots.
- **No second staleness system for configuration:** R-3 decides.
- **No catch-all status.**
- **No probabilities.**
- **No change to 2.1.1:** `csia_semantic_core/` is byte-identical to 2b2adcc.

## Code (`csia_evidence_assurance/`, outside `csia/`)

| module | phases |
|---|---|
| `envelope.py`, `health.py`, `contract.py`, `contracts/` | 3, 5, 6, 7, 8 |
| `lineage.py`, `dependence.py` | 4, 13, 14 |
| `admissibility.py` | 9, 10, 22 |
| `profile_gate.py`, `pacing_citations.json` | 11, 12 |
| `adapters/cusum.py`, `px4_estimator.py`, `xsys_witness.py`, `v2_domains.py` | 15-21 |
| `analyzer.py`, `report.py`, `runs.py`, `__main__.py` | 1, 2, 23-26 |

**Tests:** `tests/test_evidence_assurance_2_2.py`.

## Documents

| document | phases |
|---|---|
| `PRODUCT_QUESTION_AND_SURFACE.md` | 1, 2 |
| `EVIDENCE_ENVELOPE.md` | 3 |
| `CONTENT_TIME.md` | 5 (the 152 ms PX4 lag; the 372-difference lesson) |
| `LINEAGE_AND_DEPENDENCE.md` | 4, 13, 14 |
| `PRODUCER_HEALTH_AND_CONTRACTS.md` | 6, 7, 8 |
| `ADMISSIBILITY.md` | 9-12, 22 |
| `ADAPTERS.md` | 15-21 |
| `ASSURANCE_RESULT_AND_REPORTS.md` | 23-26 |
| `DATASETS.md` | 27 |
| `REPLAY_AND_RECEIPTS.md` | 28, 29 |
| `REVIEW_AND_DECISION.md` | review, governance, limitations, decision |

## Harnesses and results

| harness | writes |
|---|---|
| `verify_baseline_2_2.py` | `BASELINE_2_2.json` (Phase 0), `FINAL_STATE_2_2.json` (`--final`) |
| `e1_2_2.py` | `E1_2_2_RESULTS.json` |
| `replay_2_2.py` | `REPLAY_2_2_RESULTS.json`, `DIFFERENCE_RECEIPTS.json` |
| `datasets_2_2.py` | `DATASETS_2_2.json`, `datasets/*/report.json` and `report.txt` |

**Raw data.** The XSYS-001 flight logs are not in git. Dataset H reads them
from the raw-artifact location recorded in
`research/xsys_001_confirmatory_campaign/RAW_DATA_MANIFEST.json` (durable
copy: branch `claude/xsys-001-raw-data`). Everything else runs from the
repository.
