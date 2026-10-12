# research/effective_evidence_independence — Candidate B, Stage 0A

**Prior-art closure and formal problem freeze. No implementation, no
experiment, no κ metric claim.**

Frontier-selection commit `65fa17e`. Canonical pre-frontier base `76eaa17`.

Nothing was executed. No κ computation code was written, no provenance-graph
tooling was built, no CSIA file was modified, no SITL injection was run, no
scored data was generated (item 34).

---

## Verdicts

| gate | verdict |
|---|---|
| **Prior art** (item 28) | **`INCONCLUSIVE_MISSING_FULLTEXT`** |
| **Scientific** (item 29) | **`PROVENANCE_METRIC_INSUFFICIENT`** |
| Runtime topology actually changes (item 16) | **YES** — proved from ArduPilot source |
| κ_prov valid as "independence" | **NO** |
| κ_prov valid as a structural provenance quantity | yes, but neither bounded nor sufficient |
| **Ready for Stage 0B** | **NO** |

No Stage 0B artifacts were written. Item 31 permits them only if every gate
passes; two did not.

---

## The three results that did not need a library

**1. The runtime topology genuinely changes, and it is invisible on the wire.**
In ArduPilot `01a504b`, the `VIBRATION` message derives from
`_first_usable_accel` (`GCS_Common.cpp:3075` → `AP_InertialSensor.h:312`), an
index reassigned every main-loop iteration from sensor health
(`AP_InertialSensor.cpp:2001-2006`). `RAW_IMU` and `SCALED_IMU2` are hardcoded
to instances 0 and 1. So the pair `(vibration.rms, imu1.accel)` — which CSIA
places in the same `"imu"` group — has two distinct sources when accel 0 is
healthy and **one** when it is not. The `VIBRATION` message carries no instance
field (`common.xml:6632-6641`). Item 16's gate passes.

**2. But the metric that was supposed to detect it does not work.** Item 11's
hostile null holds in both directions:

- shared source, different downstream transforms → residual still sensitive
  (worked on the audited pair itself: a step bias moves the low-passed
  accelerometer channel and not the high-passed vibration statistic);
- distinct sources, shared physical disturbance → residual blind, with no
  software edge to draw.

So κ_prov neither certifies nor refutes diagnostic diversity. Item 11 forbids
rescuing it by redefinition, and it is not rescued.

**3. The frontier report's bound direction was wrong.** Omitted edges make
κ_prov an **under**-estimate — an incomplete audit manufactures deficits that
do not exist. The frontier report asserted the opposite. Corrected in
`FORMAL_REDUCTION.md` §4; `research/frontier_selection/` is left byte-identical
per the v1.1 brief's instruction not to rewrite it.

**And one finding that cuts against the whole direction:** PX4 already
publishes the selection identity as `SensorSelection` on every change
(`voted_sensors_update.cpp:276`). What ArduPilot lacks is a field on the wire,
not a concept.

---

## Files

| file | contents |
|---|---|
| `REQUIRED_READING_MANIFEST.md` | **read first.** Access evidence, the six source groups needed, exact sections, and what each would decide |
| `FULLTEXT_READING_LOG.md` | zero full texts; what source code *was* read in full |
| `PRIOR_ART_PROBLEM_SEPARATION.csv` | 9 rows, 19 columns, `full_text_read=NO` throughout |
| `PRIOR_ART_REDUCTION.md` | P1–P4 and the proposed P5; what this stage settled without literature |
| `INDEPENDENCE_TAXONOMY.md` | failure vs statistical vs diagnostic-diversity independence, and why κ_prov is a fourth thing |
| `PROVISIONAL_GRAPH_MODEL.md` | terminology correction, node/edge rules, edge categories, bound direction |
| `FORMAL_REDUCTION.md` | objects, the language discipline on "power", why the permitted statement is tautological, the bound derivation |
| `MENGER_CLAIM_COUNTEREXAMPLES.md` | both counterexamples, and the exact condition under which blindness does follow |
| `ARP4761_CCA_REDUCTION.md` | item 15 |
| `COMMON_INFORMATION_REDUCTION.md` | items 12 and 2 |
| `META_DIAGNOSIS_REDUCTION.md` | item 13 — now the most serious threat |
| `DYNAMIC_FAULT_TREE_REDUCTION.md` | item 14 |
| `RUNTIME_TOPOLOGY_SOURCE_AUDIT.md` | items 16–19, every edge cited to `file:line` |
| `SELECTED_DYNAMIC_EXAMPLE.md` | item 17, with four caveats that are most of the finding |
| `CLAIM_LEDGER.json` | 9 claims, 4 refuted predictions kept |
| `STAGE0A_CHATGPT_REVIEW_REPORT.md` | the 30-section report |

Guards: `tests/test_effective_evidence_independence.py`
(`make evidence-independence-check`).

---

## Terminology

"Effective independence" is retired. A provenance graph min-cut is **not**
statistical independence and asserting the name asserted the result. In use
here: **κ_prov**, *structural evidence diversity*, *provenance cut
cardinality* — none of which is claimed to be a standard name. "Zero power" is
retired for "zero fault sensitivity"; test power has a precise statistical
meaning and no test is specified anywhere in this package.
