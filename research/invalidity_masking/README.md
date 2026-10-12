# Intermittent invalidity masking / validity-state persistence

**Question.** When invalid raw sensor observations are *rejected* by an adapter
rather than propagated as invalid state, can last-valid state retention mask
intermittent invalidity from a downstream validity gate?

**Answer.** Yes, on the deployed v1.1 path, and the boundary is exact: the gate
times out from the last **accepted** sample rather than from the last
**observation**, so any invalid interval bracketed by accepted fixes less than
`STALE_TIMEOUT_S["gps"] = 0.5` s apart is invisible to it — at any density.

**Verdict.** `KNOWN_BEHAVIOR_NEW_INSTANCE`, plus a separate
`USEFUL_IMPLEMENTATION_DEFECT` for three committed ingest paths implementing
three different semantics for the same raw condition. Novelty is
`NOT_ESTABLISHED`; no literature search was run. Read
[`CHATGPT_REVIEW_REPORT.md`](CHATGPT_REVIEW_REPORT.md) first — including §5,
which refutes the harm hypothesis the work package was framed around.

```
make invalidity-masking     # everything below, about a minute
make invalidity-trace       # just the source audit (seconds)
```

## What is here

| File | What it is |
|---|---|
| `CHATGPT_REVIEW_REPORT.md` | **start here** — findings, hostile review, verdict |
| `SOURCE_TO_GATE_TRACE.md` | the `fix_type` → `gvalid` chain, and the item-3 verdict |
| `RETAINED_STATE_MODEL.md` | the exact gate equation, derived and then validated |
| `CLAIM_LEDGER.json` | every claim with its evidence class, including what was refuted and what was superseded |
| `PRIOR_ART_SEARCH_TERMS.md` | search plan; no search was performed |

| Script | Produces |
|---|---|
| `source_to_gate_trace.py` | `results/SOURCE_TO_GATE_TRACE.json` — 28 source facts, each required to occur exactly once, each re-read to confirm its line number |
| `validity_semantics_matrix.py` | `results/VALIDITY_SEMANTICS_MATRIX.csv`, `results/INDISTINGUISHABILITY_CHECK.json` |
| `invalid_message_gate_trace.py` | `results/INVALID_MESSAGE_GATE_TRACE.csv`, `results/DROP_VS_PROPAGATE_INVALID.csv`, `results/DIAGNOSTIC_CONSEQUENCES.json` |
| `boundary_sweep.py` | `results/TEMPORAL_PATTERN_DEFINITIONS.json`, `results/BOUNDARY_SWEEP_RESULTS.csv`, `results/ARRANGEMENT_AT_FIXED_DENSITY.csv` |
| `masking_harness.py` | library: the three validity policies and the replay loop |

Tests: `tests/test_invalidity_masking.py` (14, including the null controls).

## Evidence classes, and which artifact is which

Nothing here launches a simulator, and no campaign was preregistered or run —
the brief asked for a feasibility-grade investigation and that is what this is.

* **Source-verified.** `source_to_gate_trace.py`. Static, exact, and it fails
  rather than drifts.
* **Real recording, N = 1.** `invalid_message_gate_trace.py` reanalyses
  `NON_SCORED_TEST_FIXTURE_M1`, an ArduPilot `SIM_GPS1_JAM` episode already
  committed for the stopped MAER campaign. One realisation. Every trust and
  posterior number in this package comes from here.
* **Synthetic validity schedule.** `boundary_sweep.py` and the
  indistinguishability check program the GPS validity schedule over that
  recording's *real* non-GPS telemetry, holding one real valid fix as the
  payload. Deterministic. Used to measure **the gate only** — the source trace
  shows the gate is a function of which samples are accepted and when, never of
  their values — so these runs report no trust or posterior figures.

## The frozen core is untouched

`csia/` is not modified by this work package. The one class that changes
committed behaviour, `PropagateInvalidAdapter`, lives in `masking_harness.py`,
subclasses `ArduPilotAdapter`, overrides three methods, and exists only to
provide the semantic control. `tests/test_invalidity_masking.py` asserts that
it differs from the stock adapter by exactly that much.
