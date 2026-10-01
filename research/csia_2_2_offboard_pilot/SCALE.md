# Scale over the 66 XSYS-001 flight logs (Phase 21)

**2026-10-01.**

**Command:**

```
python -m csia_evidence_assurance analyze-many <66 flight logs> --out <dir>
```

**Machine:** 4 cores, one input at a time, each in its own process.

**Outputs in this package:** `batch/` holds:
- `batch_index.json`;
- `batch_metrics.json`;
- `batch_summary.txt`;
- `coverage_matrix.{json,txt}`.

The 66 per-flight report directories stay outside git (about 5 MB).

## 1. Results

**Batch:** 66 analysed, 0 failed, 3 min 6 s wall.

| measure, per flight | min | median | max | total over 66 |
|---|---|---|---|---|
| flight log size (MB) | 19.2 | 69.7 | 120.3 | 4,601 |
| analysis wall time, process start to exit (s) | 1.04 | 2.79 | 4.77 | 185.9 |
| peak memory, RSS (MB) | 72.0 | 118.1 | 168.1 | — |
| `report.json` (bytes) | 59,198 | 67,331 | 81,417 | 4.55 MB |
| of which the timeline (bytes) | 35,047 | 40,661 | 51,404 | — |
| `report.txt` (bytes) | 8,404 | 9,299 | 9,774 | — |
| ticks (0.1 s) | 468 | 1,718 | 2,968 | 113,385 |
| timeline intervals | 9 | 10 | 13 | 695 |
| evidence evaluations admitted (outputs × ticks) | 1,752 | 6,772 | 11,772 | 446,696 |
| evidence evaluations rejected | 88 | 96 | 116 | 6,580 |
| producers | 1 | 1 | 1 | — |

**Rate.** About 0.04 s per MB of log (median).

**Where the time goes,** for C00-A-E055 (in one process, after start-up):

| step | time |
|---|---|
| reading the log (pyulog) | 1.02 s |
| analysis: 1,718 ticks through admissibility and 2.1.1 | 1.18 s |
| machine report | 0.17 s |

**Rejections.** All 6,580 are PRODUCER_INVALID (PRODUCER_UNAVAILABLE),
before EKF2 alignment: the first 2.2-3.0 s of each flight.

## 2. The multi-producer campaign (`CAMPAIGN_REPLAY.md`)

| | |
|---|---|
| work | 121 trials (each with its flight's estimator), plus the 66 flight-level extractions |
| wall time | 425.5 s, one process |
| decisions | 55/55 A, 55/55 B, 11/11 N as XSYS-001 |

## 3. Determinism at scale (Phase 20)

**Method:** five flights were re-analysed in a separate process, with:
- a different `PYTHONHASHSEED` (777);
- a different working directory (`/tmp`).

**Flights:** C00-A-E055, C00-NB, C04-A-E055, C07-A-E095, C10-NB.

**Result:** every `report.json` was byte-identical to the batch's
(`report_sha256` in `batch/batch_index.json`).

## 4. What scale does not show

**Work per tick is small and constant.**
- One producer;
- four claims;
- 68 profile records, none of them observed.

**Not measured:** the multi-producer path over a whole flight. The
witnesses exist only at two checkpoints per trial.

**Memory** grows with the log, because pyulog loads the whole file. That
is the reader's cost, not 2.2's. A log of several hundred MB has not been
tried.

**Speed** needs no work for an offboard tool. A flight is analysed in less
time than it takes to copy its log.
