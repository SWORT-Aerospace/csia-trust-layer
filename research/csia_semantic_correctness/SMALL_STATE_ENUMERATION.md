# Exhaustive small-state enumeration (Part 14)

CSIA semantic correctness audit, 2026-09-29.

**This is analysis tooling, not production CSIA code.** Every table below
was produced by `semantic_probe.py` (section N), which calls the frozen
`localize()`, `attribute()` and `signatures.PREDICATES` unchanged. Results
are under `N` in `semantic_probe_results.json`.

**The state spaces are kept small enough to audit.** Every configuration is
enumerated, and nothing is sampled.

## 1. What is enumerated

| id | object | dimensions | configurations | what is checked in each |
|---|---|---|---|---|
| N1 | set elimination itself (`localize`) on two spec shapes | every True/False/None valuation of the base predicates; negations derived | 27 (XSYS shape) + 729 (three-hypothesis shape) | verdict census; UNSUPPORTED meanings; silent confirm-and-refute; every one-step refinement None→True/False (monotonicity) |
| N2 | `attribute()` | components A (D1, depends on B), B (D2), C (D3, unrelated); each absent, NOMINAL, DEGRADED, UNAVAILABLE or NOT_APPLICABLE | 125 | irrelevant C; UNAVAILABLE versus absent; **every permutation**; every single-record duplicate |
| N3 | COMMAND_NO_RESPONSE with the shipped predicates | command path, electrical, mechanical and physical response of motor_0; battery; ESC CAN link | 3,072 | reversed order; every duplicate; every UNAVAILABLE dimension against both completions |
| N4 | OUTPUT_STALE with the shipped predicates | GNSS link; producer process; transport, processing and source-rate segments; clock | 1,296 | as N3 |
| N5 | POSITION_UNAVAILABLE on PRECISION_NAVIGATION | **relevant:** v1.1 verdict, nav channel, GNSS link, estimator (96). **Irrelevant:** logger, telemetry radio, telemetry channel (48) | 96 × 48 | does any irrelevant variant change the result? |
| N6 | MULTIPLE_SENSORS_DEGRADED | two adverse sources declaring four shared nodes; each node absent, NOMINAL, VIOLATED or UNAVAILABLE | 256 | every absent or UNAVAILABLE node against both completions |

## 2. Results

### N1: set elimination

| | XSYS shape | three-hypothesis shape |
|---|---|---|
| valuations | 27 | 729 |
| verdicts | SUPPORTED 12, AMBIGUOUS 2, UNSUPPORTED 13 | SUPPORTED 54, AMBIGUOUS 540, UNSUPPORTED 135 |
| UNSUPPORTED = no consistent hypothesis / one unconfirmed survivor | 9 / 4 | 27 / 108 |
| valuations where a **specifically** confirmed hypothesis is rejected with no record | 6 | 217 |
| monotonicity violations (a confirmer added rejects; a refuter added supports) | **0** | **0** |
| SUPPORTED → UNSUPPORTED on adding one value | 8 | 27 |

**Findings.**

- **The elimination rule is monotone.** P14 passes.
- **The label UNSUPPORTED is split** between two meanings in both shapes
  (SC-09).
- **Refute-wins discards a specific confirmation silently** in 217 of 729
  valuations of the general shape (SC-16).
- **In the XSYS shape the 6 silent cases are witness disagreements.** DYN and
  CTRL disagree, and both hypotheses are rejected. The sealed XSYS-001 data
  contains **none** of them (`XSYS_001_COMPATIBILITY.md`).

### N2: attribution

| check | frozen | shadow |
|---|---|---|
| UNIQUE configurations | 21 | 4 |
| an unrelated NOMINAL C **creates** UNIQUE | **6** | 0 |
| UNAVAILABLE differs from absent | 0 | 0 |
| any permutation changes the full output | 0 | — |
| a duplicate changes the decision | 0 | — |
| a duplicate changes the trace (discriminator listed twice) | 27 | — |

**The 4 UNIQUE the shadow keeps are all the same case:** A adverse and its
declared alternative B affirmatively NOMINAL. The other 17 frozen UNIQUE
verdicts rest on a discriminator that is not a declared alternative. That
includes UNIQUE for **B** because its dependent **A** is NOMINAL, and UNIQUE
for C, which nothing is connected to.

**Attribution treats UNAVAILABLE and absent identically.** The defect is that
**both** still permit UNIQUE (R2, R3).

### N3 and N4: localization with the shipped predicates

| | N3 COMMAND_NO_RESPONSE | N4 OUTPUT_STALE |
|---|---|---|
| configurations | 3,072 | 1,296 |
| with at least one UNAVAILABLE record | 2,343 | 567 |
| frozen: rejects a hypothesis on an unknown | **1,208** | **486** |
| frozen: SUPPORTED resting on an unknown | **211** | **38** |
| frozen: confirms on an unknown | 0 | 0 |
| shadow: any of the three | **0** | **0** |
| reversed order changes the result | 0 | 0 |
| duplicating one record changes the result | 0 | 0 |
| frozen verdicts | AMBIGUOUS 1,848, SUPPORTED 256, UNSUPPORTED 104, no symptom 864 | AMBIGUOUS 1,144, SUPPORTED 76, UNSUPPORTED 76 |
| shadow verdicts | AMBIGUOUS 2,132, SUPPORTED 45, UNSUPPORTED 31, no symptom 864 | AMBIGUOUS 1,218, SUPPORTED 39, UNSUPPORTED 39 |

**The successor issues fewer SUPPORTED verdicts: 256 → 45 and 76 → 39.** Every
one it drops rested on reading an UNAVAILABLE record as healthy.

**Order and exact duplication have no effect here**, for two reasons:

- no configuration has two records for one (relation, component);
- the only counting threshold is in MULTIPLE_SENSORS_DEGRADED, which these
  symptoms do not use.

### N5: irrelevant evidence, POSITION_UNAVAILABLE

| | frozen | shadow |
|---|---|---|
| relevant configurations changed by some irrelevant variant | **94 of 96** | 0 |
| irrelevant variants that **create** a SUPPORTED verdict | **572** | 0 |

**Example.** v1.1 says PRECISION_NAVIGATION is eligible, and nothing else
about navigation is reported. The telemetry channel then goes late. Frozen v2
emits POSITION_UNAVAILABLE on PRECISION_NAVIGATION, with TIMING/deadline_violation
supported (N.N5.examples).

### N6: shared nodes nobody reported

| | frozen | shadow |
|---|---|---|
| configurations with an absent or UNAVAILABLE node | 240 | 240 |
| rejects a shared-node hypothesis on an unknown | **224** | 0 |
| confirms "independent faults" on an unknown | **80** | 0 |
| SUPPORTED resting on an unknown | **176** | 0 |
| SUPPORTED SENSOR/independent_faults | **81** | 1 (all four nodes reported NOMINAL) |

## 3. Automatic searches the brief asked for

| search | result |
|---|---|
| irrelevant evidence changing a verdict | **found:** N2 (6), N5 (94 configurations) |
| order dependence | **none within these tables.** Found by construction in R6 (conflicting records for one key) |
| duplicate dependence | **none in N2-N4.** Found in R7B (the multi-source count) and in 3 shipped cases (P4) |
| semantic contradictions | a hypothesis both specifically confirmed and refuted, silently: N1 (6 + 217). SUPPORTED resting on an unknown: N3 (211), N4 (38), N6 (176) |
| unreachable states | attribution verdict UNSUPPORTED (no caller; 0 of 2,640 shipped ticks); localization UNSUPPORTED with an `unmodelled` survivor (no shipped hypothesis is unmodelled) |
| undocumented transitions | SUPPORTED → UNSUPPORTED on adding one refuter of a specifically confirmed hypothesis (N1). Missing telemetry turning SUPPORTED into a **different** SUPPORTED (engine-level V_MIS_2) |
