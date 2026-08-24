# 08 — Real-log results

**Artifact:** `datasets/reports/exposure_v2.json`
**SHA256 of that file:** `114e1f827328dedc5292b104e49a0da24ba1cfc5c4765a232b82c7af8ea9d714`
**Dataset aggregate hash (from the artifact):** `4c7a696981a4b8f19200e2a8d37ab147c18da08218d000801d634e8acd43e411`
**Deduplication report hash field:** `4c7a696981a4b8f19200e2a8d37ab147c18da08218d000801d634e8acd43e411`
**Commit:** `86b19f9a1d0feb54efcefa7f122a5b9fd0b63c84`
**Historical artifact retained unmodified:** `data/real_logs_report.json`

---

## 1. Verified values

| quantity | value | source |
|---|---|---|
| logs counted | **26** | `exposure.counted_logs` |
| raw hours | **0.6627** | `exposure.total_raw_hours` |
| **monitored hours** | **0.5183** | `exposure.total_monitored_hours` |
| unmonitored hours | 0.1444 | `exposure.unmonitored_hours` |
| `arm_time_s` excluded per log | 20.0 | `arm_time_s` |
| logs excluded | 0 | `exposure.excluded_logs` |
| duplicate hours excluded | 0.0 | `exposure.excluded_duplicate_hours` |
| **alert episodes** | **2** | `rates_by_health_category.UNANNOTATED.alert_episodes` |
| **rate** | **3.859** per monitored hour | `rates_by_health_category.UNANNOTATED.rate_per_hour` |
| exposure basis | monitored (0.5183 h) | same |
| flights with 0 / 1 / >1 episodes | 24 / 2 / 0 | same |
| interpretation, verbatim | 2 alert episode(s) in 0.518 h of UNANNOTATED replay; interval is wide at this count | same |
| **95% CI** | **[0.467, 13.939]** | `ci95_per_hour` |
| health annotation | `['UNANNOTATED']` | `exposure.by_health` |
| **VERIFIED_HEALTHY exposure** | **0.0 h**, 0 logs, rate `None` | `rates_by_health_category.VERIFIED_HEALTHY` |
| exact duplicates found | 0 | deduplication report |
| leakage / contamination | `[]` / `[]` | artifact |

**Historical figure retained:** `{"logs": 26, "note": "historical artifact retained unmodified", "raw_hours": 0.663, "source": "data/real_logs_report.json"}`
and `data/real_logs_report.json` reports
`total_hours = 0.663`, `total_transitions = 3`
over 26 flights.

**The exclusion arithmetic.** 0.6627 raw hours
minus 0.1444 unmonitored =
0.5183 monitored. The unmonitored part is
`arm_time` at 20.0 s per log across
26 logs = 520.0 s,
which `docs/audit/CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md` records as 520.0 s
= 21.8% of recorded time.

**Transitions versus episodes.** The historical artifact counts
3 raw transitions; the corrected artifact counts
2 alert **episodes**. The merging rule is not stated as a
machine-readable field in either artifact: **UNRECOVERABLE**. The paper must either
cite the audit prose or re-derive it. Do not present 3
and 2 as the same quantity.

## 2. Sensor-configuration distribution

| configuration | monitored hours |
|---|---|
| `baro+battery+gps+imu0+mag` | 0.2908 |
| `baro+battery+imu0` | 0.0782 |
| `baro+battery+imu0+mag` | 0.0513 |
| `baro+imu0` | 0.0434 |
| `battery+gps+imu0` | 0.0399 |
| `baro+battery+gps+imu0` | 0.0147 |

**Per-flight distribution:** `data/real_logs_report.json` carries a
per-flight list of 26 entries with `log`, `duration_s`,
`sensors` and per-flight trust minima.

## 3. Acquisition status

`datasets/reports/deduplication_report.json` records
`not_yet_acquired` for 26 log ids and
`verified` for 0. Note verbatim:
*nothing is deleted or auto-excluded; near-duplicates are review candidates only*
Fetch mechanism: `tools/fetch_real_logs.py` and
`tools/acquire_public_datasets.py`; acquisition is refused on this host by
`csia/data/paths.py`.

---

## 4. What these logs CANNOT establish

State all of these in the paper:

- **not** an operational false-alarm rate: the corpus is
  `['UNANNOTATED']`, so no alert can be scored as false;
- **not** fault recall: no fault is annotated, so there is no denominator;
- **not** `P(G = 0 | H_fault)`: that requires `F_h`, which does not exist here;
- **not** field validation: replay of unannotated logs is not a flight test,
  and the system has never flown in the loop;
- **not** fault-specific endogeneity: the coarsening measurable here is
  **exogenous** (a channel is absent from the record), not endogenous (a gate
  closed because of the fault). `docs/research/PAPER1_EMPIRICAL_SECTION.md`
  makes that distinction binding.

**Prohibited wording** for this section, per
`docs/audit/WP_A2_CLAIM_PROVENANCE_MATRIX.csv`: "flight-proven",
"flight-validated", and any description of the corpus as healthy or validated.
