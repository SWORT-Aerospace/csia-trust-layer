# The assurance result, the reports and the timeline (Phases 23-26)

**2026-10-01. Code:** `csia_evidence_assurance/analyzer.py` (`AssuranceResult`),
`report.py`. **Tests:** `test_reports_are_byte_stable_and_carry_no_probabilities`,
`test_timeline_collapses_stable_intervals`.

## 1. One tick: `AssuranceResult` (Phase 23)

| brief field | result field | notes |
|---|---|---|
| event_time | `event_time` | analysis time |
| semantic_version | `semantic_version` | "2.1.1" from the core itself |
| profile_version | `profile`: name, version, base, digest, gate status, pacing digest | — |
| verdict | `state.headline`, `state.attribution`, `state.localization_outcomes` | the headline names each localization's outcome and its remaining explanations, then the attribution verdict. Under the XSYS-001 specification the attribution has no attributable records (NO_EVIDENCE) while the localization is SUPPORTED, so both are shown |
| candidate_hypotheses | per localization `candidates`; `attribution.candidates` | — |
| unique_attribution | `attribution.unique` | only when 2.1.1 says UNIQUE |
| supporting / refuting evidence | per localization `supporting_evidence`, `refuting_evidence` | the evidence ids behind the confirming and refuting predicates, from 2.1.1's trace |
| rejected evidence and reasons | `evidence.rejected` | — |
| producer_faults | `producers.by_producer[*].faults` | — |
| profile_warnings | `profile_warnings` | — |
| configuration_epoch | `configuration` | — |
| reason_trace | `reason_trace`, per localization `why` | 2.1.1's own |

**Added because the questions in `PRODUCT_QUESTION_AND_SURFACE.md` need
them:**
- `corroboration`: lineage;
- `evidence.admitted_with_warnings`;
- `producers.coverage_gaps`.

## 2. Machine report (Phase 25)

`report.machine_report(...)`, written by `report.dumps()`:
- **schema** `csia.flight_assurance_report/1`;
- **byte-stable:** sorted keys, floats rounded to 6 decimals, no NaN, no
  wall-clock time, host or absolute path.

**Evidence:**
- two runs of the same input give identical bytes (test);
- the `report_sha256` of every dataset is recorded in `DATASETS_2_2.json`;
- the dataset harness rewrites a report only if it changed.

## 3. Human report (Phase 24)

**Plain text, in fixed sections:**
- inputs;
- profile and findings;
- the timeline, one line per interval;
- the final state: what appears abnormal, each localization with remaining
  and eliminated explanations, supporting and refuting evidence, predicate
  faults and fault impact, withheld reasons, and attribution;
- rejected evidence with reasons;
- producers and coverage;
- dependence;
- configuration;
- profile warnings.

**No probabilities.** Nothing in 2.1.1 or 2.2 computes one, so the report
has none. A test checks for "%", "probab", "confiden" and "likel".

## 4. Event timeline (Phase 26)

**A new interval starts when any of these changes:**
- the verdict or the candidate set;
- a localization's outcome, candidates or eliminations;
- producer health;
- the profile state;
- a configuration epoch;
- the admissibility status of any held evidence (by producer, claim and
  record, not content time);
- the predicate faults;
- the adverse evidence.

**Everything else is collapsed.** Each interval keeps its first and last
time, its tick count, the list of what changed, and the full result at its
first tick.

| run | ticks | intervals |
|---|---|---|
| dataset A, NOMINAL | 60 | 1 |
| dataset B, PROCESS_STALL | 60 | 3 |
| E055 whole flight, estimator only | 1,718 | 10 |
| XSYS A trial with its flight's estimator | 161 | 3 |

(`DATASETS_2_2.json`.)
