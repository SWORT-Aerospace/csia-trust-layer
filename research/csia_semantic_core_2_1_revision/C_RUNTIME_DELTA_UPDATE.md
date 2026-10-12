# C runtime delta, updated for R-1, R-2 and R-3 (Phase 17)

**2026-10-01. Nothing is ported.** This updates
`research/csia_semantic_core_2_1_shadow/C_RUNTIME_DELTA.md`, which is not
edited. Its finding stands:
- the native core (`csia/native/csia_core.c`) holds only the v1 trust kernel
  and the legacy softmax diagnosis;
- it has no v2.0 reasoning;
- so the delta against 2.1.1 is the whole v2.0 model, plus the 2.1
  corrections, plus the three revisions below.

## 1. The three revisions, row by row

| Python feature (2.1.1) | what it does | category | notes for C |
|---|---|---|---|
| R-1 `fault_impact` and WITHHELD_PREDICATE_FAULT | per failed predicate and hypothesis: role, materiality, action; a SUPPORTED whose refuter (or sole confirmer) failed is withheld | **small extension** | C4 in C already returns a status per predicate (the shadow study's plan). R-1 is: `if (verdict == SUPPORTED && (fault_mask & refuter_mask[h])) outcome = WITHHELD_PREDICATE_FAULT`. Materiality for the onboard trail is a 2-bit code per (fault, hypothesis). The full `fault_impact` list is rebuilt on the ground by replay |
| R-2 `PACING_INPUTS_NOMINAL` | Kleene ALL/ANY over a subject's declared pacing inputs | **small extension** | one predicate function; the pacing declarations become a compiled table from successor profile r2 (component id, mode, ≤ 4 node ids). The OUTPUT_MISSING hypothesis table points input_starvation at it |
| R-2 PV9 | a pacing input must be a declared dependency | **not onboard** | build time, with PV1-PV8: refuse to build on ERROR |
| R-2 successor profile r2 | r1 + one pacing declaration | **not onboard** | resolved at build time into the flat profile blob; its digest and the pacing digest are compiled in |
| R-3 `admission.admit` | equal-epoch admission; superseded records dropped; others made UNAVAILABLE with content cleared | **small extension** | the record struct gains a key index (u8) and an epoch (u32, or two u32 for a composite). The context is a ≤ 16-entry array of the current epochs, refreshed from uORB each tick. One pass marks each record admitted / stale / ahead / malformed and finds keys whose context is behind; a second pass drops superseded records or sets state UNAVAILABLE **in place** and clears the reason bitmask. No allocation, no history |
| R-3 admission report | the trace of what was not admitted and why | **onboard: a fixed ring** | about 16 entries × (record index, reason code, evidence epoch, current epoch) ≈ 256 B; the transition-event text stays on the ground |
| `Corrections` switches and the 2.1.1 version tag | which revisions are on | **build time** | compile-time flags; the semantics version is a constant in the output header |

The shadow study planned a "configuration epoch (future)" row as **small
extension, once designed**. It is now designed, and it is that.

## 2. Size, ESTIMATED

The shadow study's estimates, with the revisions added. Details are in
`H743_UPDATE.md` §2.

| quantity | shadow estimate (2.1.0) | 2.1.1 |
|---|---|---|
| RAM | about 12-13 KB | about 13-15 KB |
| flash | about 20-40 KB (code 15-30, tables 4-8) | about 22-44 KB |
| per-tick operations at the 128-record cap | about 5,000-10,000 | about 5,000-12,000 |
| loops | all bounded by a validated count | unchanged: R-3 adds two passes over at most 128 records; R-2 a scan over at most 4 inputs |

## 3. The port plan, with the revisions placed

This is **not authorized**. Each step has its own parity gate against Python.

1. **Structures and ingest.** The record struct now includes the R-3 key
   index and epoch. Parity: identical index contents on dataset A.
2. **R-3 admission**, right after ingest and before indexing. Parity:
   identical admission reports on E1 and the 14 epoch variants
   (`EPOCH_ADVERSARIAL_RESULTS.json`).
3. **Predicates with K3 (C2) and fault status (C4), including
   PACING_INPUTS_NOMINAL (R-2).** Parity: identical predicate values, and
   identical fault records under dataset D's injections (71,280 under 2.1.1
   + r2).
4. **Scope precomputation (C3)** from the build-time blob (r2).
5. **Localization with C5 labels and R-1.** Parity: identical 2.0-view
   localization and outcomes (including WITHHELD_PREDICATE_FAULT) on 2,640
   ticks and on dataset D.
6. **C6, then attribution with C1 and F2.** Parity: dataset A attribution,
   and XSYS-001's 3,872 slots.
7. **The onboard trail and the ground replay tool.** The trail gains the R-1
   materiality codes and the R-3 ring.
8. **The target build and the first measurement** (WCET, stack high-water,
   RAM and flash from the link map).

**The prerequisite is unchanged, and R-3 sharpens it.** The evidence and its
context must exist on the flight controller:
- adapters from uORB topics to records;
- for R-3, an adapter that publishes the epoch context from
  `estimator_selector_status`, unwrapping narrow counters.

## 4. What was deliberately not designed

Each of these would extend beyond R-1, R-2 and R-3, so each is recorded and
not built:
- **Pacing per configuration epoch** (`R2_PACING_STARVATION.md` §8).
- **A symptom-level "not evaluated" flag** (`WORSE_ANSWER_SEARCH.md` §2.1).
- **The adapters themselves.**
