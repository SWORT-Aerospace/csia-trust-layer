# C runtime against 2.1 semantics: the delta and a port plan

**2026-09-30. Parts 27 and 51 of the shadow-validation brief. Nothing is
ported.**

**Sources.**
- `csia/native/csia_core.c`, 175 lines, read in full (V4).
- `docs/embedded/NATIVE_RUNTIME_STATUS.md` (V4).
- Operation counts from `SHADOW_RUNTIME.json` (`shadow_runtime.py`).

## 1. What the C runtime actually contains

The whole native core is two functions:
- **`csia_trust_step`:** the v1 per-node trust recursion over a trust graph.
- **`csia_diag_step`:** the legacy 1-of-K softmax diagnosis over a flat
  matrix.

It has no evidence records, no symptom table, no predicates, no localization,
no attribution and no function graph. The v1 core is sound (V4):
- no allocation, recursion or global state;
- validated counts, with rejection before any state mutation;
- fixed caps (64 nodes, 32 causes, 512 edges).

**No STM32H743 build, toolchain or target measurement exists**
(NATIVE_RUNTIME_STATUS.md, "open gaps" 1-2).

**So the delta against 2.1 is not "the 2.1 additions".** It is the frozen
v2.0 reasoning model, **plus** the 2.1 corrections. The comparison with v2.0
below is for scale only: v2.0 has no C implementation either.

## 2. Feature-by-feature delta

**Categories:**
- **existing:** already in `csia_core.c`;
- **small extension:** a few dozen lines on top of a structure the port needs
  anyway;
- **new structure:** a new data structure;
- **new algorithm:** a new algorithm;
- **not onboard:** belongs on the ground or at build time.

| Python feature | what it does | category | notes for C |
|---|---|---|---|
| `EvidenceRecord` (v2.0) | one categorical claim about one relation of one component | **new structure** | fixed struct, about 64 bytes: domain u8, component u16, relation u16, state u8, applicability u8, reason bitmask u32, function bitmask u32, up to 4 dependency ids, 3 timestamps, 3 numerics, attributable flag. 2.1 later adds content_time and epoch |
| `EvidenceIndex` (v2.0) | lookup by relation and component | **new structure** | a per-relation index array built each tick, O(n) |
| symptom detectors (v2.0) | which symptoms are present, on which subjects | **new algorithm** | table-driven; 9 symptoms for the aircraft |
| 26 predicates (v2.0) | three-valued facts from records | **new algorithm** | one C function each, returning a 2-bit value |
| `localize` (v2.0) | set elimination over a symptom's hypotheses | **new algorithm** | bitsets: at most 5 hypotheses and 8 predicates per hypothesis |
| `attribute` (v2.0) | adverse candidates, common cause, discriminators | **new algorithm** | candidate bitset; ancestor walk over depends_on |
| function graph (v2.0) | per-function eligibility | **new algorithm** | table-driven. Needed only if an onboard consumer reads function states |
| C2 Kleene aggregation | "could not look" is never "fine" | **small extension** | 2-bit AND/OR tables; removes, rather than adds, special cases |
| C3 subject scope | predicates read only the declared scope | **small extension** | **precompute** a scope bitset per subject when the profile loads, and recompute on an epoch change. Nothing per tick |
| C4 predicate faults | a raising predicate is recorded, not silent | **small extension** | C has no exceptions: each predicate returns a status code plus a value, and faults go to a fixed ring |
| C6 duplicates and conflicts | exact duplicates count once; conflicting keys are read by nobody | **new algorithm** | sort the record indices by (relation, component), then one linear pass; at most 128 records |
| C1 declared alternatives | UNIQUE needs every declared alternative affirmatively nominal | **small extension** | the ancestor bitset plus relation implicates, one pass |
| F2 localization agreement | withhold UNIQUE while a localization keeps another domain | **small extension** | one comparison per localization on the candidate's component |
| C5 outcome labels | NO_CONSISTENT / INSUFFICIENT / … | **small extension** | an enum |
| C7 decision trace | why, evidence used, unknown inputs, scope gaps | **not onboard in full** | onboard: a fixed trail per localization (reason code, retained-hypothesis bitmask, 2-bit predicate values, error bits). The full trace is rebuilt on the ground by deterministic replay of the logged inputs |
| predicate-fault policy B (selected, not yet in 2.1) | withhold SUPPORTED over a failed refuter | **small extension** | a bitmask AND per supported hypothesis |
| successor profile overlay | extra declarations with a digest | **not onboard** | resolved at build time into one flat profile blob; the digest is compiled in |
| static profile validator | PV1-PV8 | **not onboard** | build time: refuse to build on ERROR |
| shadow runner | v2.0 and 2.1 side by side | **not onboard** | SITL and replay only |
| configuration epoch (future) | admissibility across lane switches and resets | **small extension**, once designed | an epoch id per record, plus a per-producer invalidation mask |

## 3. Size and cost estimates

These are **ESTIMATED from the Python operation counts, not measured.**

**Workload, measured on dataset A with 2.1:**
- at most 68 records per tick;
- at most 5 localizations per tick;
- at most 39 predicate evaluations per tick, reading at most 64 evidence rows;
- 9 symptoms, at most 5 hypotheses each, 26 base predicates.

| quantity | estimate | basis |
|---|---|---|
| worst-case record count to design for | 128 per tick | 68 measured max, ×2 headroom. Enforce it as a hard cap with a rejection code, as the v1 core does |
| RAM: records | about 8 KB | 128 × about 64 B |
| RAM: index, scope bitsets, candidate and hypothesis bitsets | about 2 KB | 128 components → 16-byte bitsets; 32 subjects |
| RAM: onboard trail and fault ring | about 1 KB | 8 localizations × 64 B, plus a 32-entry fault ring |
| RAM: stack | about 1-2 KB | sort scratch of 128 × u16; no recursion |
| **RAM total** | **about 12-13 KB** | against about 1 MB SRAM (datasheet, V0) |
| flash: tables (symptoms, hypotheses, predicate ids, profile blob) | about 4-8 KB | table sizes above, plus about 200 component and relation entries |
| flash: code | **about 15-30 KB** | 26 predicates, localization, attribution, C6, C1, F2, detectors, function graph. A comparable small module (the architecture phase estimated 20-60 KB for admissibility plus lifecycle) |
| per-tick operations | about 5,000-10,000 simple operations | C6 sort about 1k; index about 0.5k; predicates up to 39 × their rows; localization about 200; attribution about 68 records × up to 16 alternatives |
| branch complexity | moderate | every loop bounded by a validated count; no search over subsets (2.1 adds none, and v2.0's `minimum_resolving_subsets` is not needed onboard) |

## 4. Port plan

This is ordered, and it is **not authorized**. Each step has its own parity
gate against Python.

1. **Structures and ingest.** EvidenceRecord, index, a hard record cap and
   rejection codes. Parity: identical index contents on dataset A.
2. **Predicates with K3 (C2) and fault status (C4).** Parity: identical
   predicate values, and identical fault records under dataset D's
   injections.
3. **Scope precomputation (C3), from a build-time profile blob.** Parity:
   identical scopes for every subject under the frozen profile and under
   successor r1.
4. **Localization, including C5 labels.** Parity: identical 2.0.0-view
   localization on 2,640 ticks.
5. **C6**, then **attribution with C1 and F2**. Parity: identical attribution
   on 2,640 ticks, and XSYS-001's 3,872 slots.
6. **Policy B**, if the owner adopts it.
7. **The onboard trail, and a ground replay tool that rebuilds the full
   trace.**
8. **The target build.** The first hardware measurement is WCET, stack
   high-water, RAM and flash from the link map. This is the step that turns
   the estimates in `H743_FEASIBILITY.md` into measurements.

**The prerequisite that decides whether any of this is worth doing** is
upstream of the port. The evidence the core consumes has to exist on the
flight controller: adapters from PX4 topics to records
(`ESTIMATOR_INTEGRATION_EXAMPLE.md`). Today the aircraft profile's evidence
comes from a synthetic harness and a companion-computer payload.
