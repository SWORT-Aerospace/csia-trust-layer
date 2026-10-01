# The Flight Assurance Analyzer MVP (Phases 12, 13, 14, 20, 22)

**2026-10-01. OFFBOARD. NO FLIGHT-CONTROL AUTHORITY.**

**Code:** `csia_evidence_assurance/__main__.py`, `report.py`.
**Tests:** `tests/test_csia_2_2_pilot.py`.

**Version stamps:**
- analyzer 2.2.1;
- report schema `csia.flight_assurance_report/3`;
- manifest schema `csia.analysis_manifest/1`;
- semantics 2.1.1, unchanged.

## 1. One command (Phase 12)

```
python -m csia_evidence_assurance analyze INPUT [--out DIR] [--tick S] [--variant V] [--ulog LOG]
```

| INPUT | what runs |
|---|---|
| a PX4 `.ulg` | the PX4 EKF2 adapter over the whole log, every `--tick` (0.1 s) |
| an estimator extract `.npz` | the same, from the extract (run S1 is committed this way) |
| a frozen v2 scenario name | the six v2 domain plugins through the legacy adapters |
| a frozen v1 scenario name | the frozen CUSUM |
| an XSYS-001 analysis id | the trial's witnesses at C1 and C3; with `--ulog`, its flight's estimator joins on the same time axis |

**Outputs:**

| file | what it is |
|---|---|
| `report.json` | the machine report: deterministic bytes |
| `report.txt` | the engineer's report |
| `manifest.json` | what is needed to reproduce the report |

**What the command does not have:**
- no GUI;
- no cloud;
- no network;
- no database;
- no flight-control output.

**`analyze-many DIR_OR_LIST --out DIR`** (Phase 22):
- runs `analyze` once per input, each in its own process;
- a failed input is recorded, and the batch continues;
- writes `batch_index.json`, `batch_summary.txt`,
  `coverage_matrix.{json,txt}` and `batch_metrics.json`;
- `batch_metrics.json` holds wall time and peak memory per input. It is the
  only file whose bytes vary between runs.

There are no fleet analytics: no trends, no ranking, no aggregate score.

## 2. The input manifest (Phase 13)

**Every report carries a manifest with:**

| field | example (U1) |
|---|---|
| input files and their SHA-256 | `XS1A1-C00-A-E055.ulg` 3ddc2507…; stage-1 features ccbc10f5… |
| semantic version | 2.1.1 |
| analyzer version, report schema | 2.2.1, `/3` |
| profile: name, version, digest, gate status | `xsys001_research_spec`, NOT_APPLICABLE |
| every producer's version and contract digest | `px4:ekf2.estimator_status` 547e2ca, `px4-ekf2-status-1`, 0d262894… |
| analysis configuration | variant V3_TEMPORAL, onset in the log 154.752 s, tick |
| code digests | `csia_evidence_assurance` and `csia_semantic_core`, over every `.py` and `.json` |
| the report's own SHA-256 | b417b645… |

**The manifest has no absolute path, no host name and no time.**
`test_manifest_is_reproducible_and_path_free` pins this.

**What the manifest does not record:**
- the Python version and library versions (numpy, pyulog);
- the PX4 build. The PX4 version is the producer version only.

`PRODUCT_GAP_ANALYSIS.md` lists both.

## 3. Timeline quality: the WHEN questions (Phase 14)

**Before the pilot,** the timeline answered "what was the state over
[t0, t1]". It did not answer the questions an engineer asks first.

**The report now computes the KEY MOMENTS once over the run**, in time
order:

| question | key moment | example |
|---|---|---|
| when did anything first look abnormal, and to whom? | `first_abnormal` | U1: 0.200 s, COMMAND_NO_RESPONSE\|motor_0, observed by W_DYN and W_RPM |
| when did each producer first say something adverse? | `first_observation_by_producer` | U1: W_CTRL only at 15.0 s (its T3 window) |
| when did adverse evidence appear and clear? | `adverse_evidence_changes` | U5: vibration alarm from 35.36 s to 39.64 s |
| when did the explanation change? | `candidate_changes` | U7: attribution AMBIGUOUS → UNIQUE SENSOR/source.imu0 at 1.25 s |
| when did CSIA become certain, and lose it? | `certainty` | U7: three SUPPORTED localizations certain at 1.0 s, lost at 1.25 s |
| when did evidence stop counting, and why? | `evidence_invalidated` | U3: W_DYN REGIME_INVALID at 15.0 s (outside its validated window) |
| when did a producer change health? | `producer_health_changes` | U4: EKF2 UNAVAILABLE at 0.6 s → VALID at 2.7 s |
| when did the configuration change, in PX4's terms? | `configuration_changes` | U4: "hdg aiding fused: 3-axis magnetometer -> none" at 75.5 s |
| when did a predicate fail? | `predicate_faults` | U8: CHANNEL_LINK_NOMINAL raised at 0.9 s |

**Report defects found by reading the reports, all fixed:**
1. a configuration change named only "changed: epochs";
2. counters instead of PX4 terms;
3. truncated key-moment lines;
4. one refuter shown where two held;
5. no flag when the refuters share a source;
6. no statement of what a run did not observe (WA-3, §5).

Details are in `WRONG_ANSWER_SEARCH.md` §3 and §2.

## 4. Determinism (Phase 20)

| test | result |
|---|---|
| same input, two processes, different `PYTHONHASHSEED`, different working directory | identical bytes (`test_report_bytes_do_not_depend_on_process_or_directory`) |
| `analyze` against `analyze-many` on the same input | identical bytes (`test_analyze_and_analyze_many_commands`) |
| U4, U5, U6, U8 regenerated in the test suite | byte-identical to the pinned SHA-256 and the committed file (`test_pinned_reports_regenerate_byte_for_byte`) |
| U7 (E1) | pinned through the 2.2 E1 replay; its hash is in `REPORT_HASHES.json` |
| U1-U3 (need the raw XSYS-001 logs) | hashes in `REPORT_HASHES.json`; regenerated by `usefulness_reports.py` when the logs are present |
| 66 flights, `analyze` re-run on a sample | see `SCALE.md` §3 |

**Pinned SHA-256 of `report.json`:**

| case | SHA-256 |
|---|---|
| U4_s1_selector | 80035ab1256b72887ad5593f6eb99729c6ecd541ea607f091844baf201562566 |
| U5_cusum_power_sag | 92d88ae17f149cfdc385831c05abd215e2dff83cdf260e67ebce4a14176d825e |
| U6_cusum_imu0_drift | c8ca0bf203ec400885e5b8c1cb524257aae492bc1fda01e1e69abe5ca0a30927 |
| U8_predicate_fault | 9c86f295ce89b79ae602069692e28220cea8a072651fd97e653b0e5629ee780b |

**What makes the bytes stable:**
- sorted keys;
- floats rounded to 6 decimals;
- lists in analysis order or sorted;
- no wall clock, host name or absolute path.

## 5. Finding WA-3: a verdict without its scope (fixed)

| | |
|---|---|
| **found by** | reading the batch reports of the 66 XSYS-001 flight logs (`SCALE.md`) |
| **what the report said** | for XS1A1-C00-A-E055, a flight whose motor 0 lost 45 % of its thrust: "no symptom detected", "nothing abnormal at any tick". Nothing said that no producer observed the motors |
| **why** | a PX4 log alone gives the Analyzer one producer, EKF2, whose four claims are outside the profile (context, `ESTIMATOR_CLAIM_MAPPING.md`). 2.1.1 correctly found no symptom in what it was given. The report did not say it was given nothing about the motors |
| **class** | no coverage presented as a clean result (probe P6's wrong answer, in report form). The Semantic Core is not involved |
| **reproduction** | `analyze XS1A1-C00-A-E055.ulg` before the fix: no line names an unobserved record |
| **fix** | report schema 3. `profile_coverage` lists every record the profile defines as observed, held but never admitted, or with no producer output. The final state carries "scope: the run observed 0 of the profile's 68 records; nothing is concluded about the other 68" |
| **pinned** | `test_wa3_a_verdict_names_the_profile_records_nothing_observed` |
| **limit** | a profile with no record list (the XSYS-001 specification) is reported as not enumerable |

**Consequence for the product (`PRODUCT_GAP_ANALYSIS.md`).**
`analyze FLIGHT.ulg` on a stock PX4 log cannot diagnose anything today. What
it gives is the estimator's health and configuration history, with
the scope stated.
