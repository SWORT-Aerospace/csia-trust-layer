# CSIA Semantic Core 2.1

**Implemented and validated; not the default. 2026-09-30.**

This is the owner-approved successor to the frozen v2 reasoning semantics.
It corrects the defects the semantic correctness audit confirmed
(`research/csia_semantic_correctness/`), and nothing beyond them.

| | |
|---|---|
| code | `csia_semantic_core/`: a top-level package outside `csia/` that wraps frozen v2. Nothing in `csia/` imports it |
| semantics | historical **2.0.0** (frozen v2, the default) → successor **2.1.0** |
| corrections | C1, F2, C2, C3, C4, C6 change decisions. C5 and C7 are labels and trace only, and change none |
| XSYS-001 | **unchanged**: 3,872 slots, 0 decision and 0 outcome differences, primary 55/55. Hard gate PASS |
| Phase C gate | **unchanged**: same verdict, qualifying sets and answers |
| decision | **SEMANTIC_2_1_READY_FOR_SHADOW**. The shadow plan is prepared, not executed |

## Files, by phase

| phase | file |
|---|---|
| governance record | `OWNER_AUTHORIZATION.md` |
| A: characterization lock | `PHASE_A_CHARACTERIZATION_LOCK.json` |
| B: implementation | `csia_semantic_core/`: `index.py` (C6, read log), `predicates.py` (C2, C3, C4), `localization.py` (C5, C7, outcome states), `attribution.py` (C1, F2, C5), `core.py` (entry point, 2.0.0 view, historical adapter), `profile_check.py` (gap report) |
| C: properties and regression tests | `tests/test_semantic_core_2_1.py`; `VALIDATION_REPORT.md` |
| D, E, F: enumeration, historical replay, XSYS gate | `semantic_core_2_1_differential.py` → `SEMANTIC_CORE_2_1_RESULTS.json`, `PHASE_E_CHANGE_RECEIPTS.jsonl`; `VALIDATION_REPORT.md` |
| G: Phase C governance | `PHASE_C_GOVERNANCE_REPORT.md` (includes the erratum to the audit) |
| H: test migration | `TEST_MIGRATION.md`, `TEST_MIGRATION.csv`; `test_migration_probe.py` with `semantic_2_1_pytest_plugin.py` → `TEST_MIGRATION_PROBE.json` |
| I: performance | `PERFORMANCE.md`; `benchmark_2_1.py` → `PHASE_I_BENCHMARK.json` |
| J: decision trace | `DECISION_TRACE.md`; examples in `SEMANTIC_CORE_2_1_RESULTS.json` J |
| K: failure ledger | `PROPOSED_LEDGER_ENTRIES.md`: seven entries, FL-054 to FL-060, all RECORDED, none marked resolved. They are held out of the ledger because three sealed-phase manifests pin its hash and rule R8 reserves appends to the owner. The ledger is unchanged |
| L: documentation | `SEMANTIC_CORE_2_1.md` |
| decision and next step | `PROMOTION_DECISION.md`, `SHADOW_MODE_PLAN.md` |

## Deliverables

The brief's deliverables list was cut off after its heading. The set above
is inferred from the phases: one artifact or section per phase, plus the
governance record, the decision and the shadow plan.

## Reproducing

```
.venv/bin/python -m pytest -q tests/test_semantic_core_2_1.py
.venv/bin/python research/csia_semantic_core_2_1/semantic_core_2_1_differential.py
.venv/bin/python research/csia_semantic_core_2_1/test_migration_probe.py
.venv/bin/python research/csia_semantic_core_2_1/benchmark_2_1.py
```

| command | time | output |
|---|---|---|
| the differential | about 20 min | deterministic: no clock, sorted iteration, fixed seeds. It fails if any of the 22 protected files changes during the run |
| the benchmark | about 1 min | wall-clock timings; they vary between runs |

## Using the successor

```python
from csia_semantic_core import SemanticCore21, Corrections, reason_historical_tick

core = SemanticCore21.from_engine(engine)              # all corrections on
result = core.reason(records)                          # a TickResult
result.to_dict()                                       # schema csia.semantic_core/2.1.0
result.to_v2_0_view()                                  # the same decisions, 2.0.0 schema
reason_historical_tick(system_assurance, core)         # a recorded tick, unmodified
SemanticCore21.from_engine(engine, Corrections.none()) # == frozen v2
```
