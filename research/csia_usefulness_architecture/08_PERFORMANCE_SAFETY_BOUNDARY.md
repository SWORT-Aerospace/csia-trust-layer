# Performance, safety boundary, FORGE boundary and robustness (Phases 15, 16, 37, 45, 46)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

## 1. Phase 15: what to profile, and what already exists

### 1.1 Existing measurements

All of these were taken on a host. None was taken on target hardware.

| component | figure | class | source |
|---|---|---|---|
| v1 trust kernel (C) | about 247 ns per tick | host benchmark, x86-64 `-O2` | S020 |
| v1 diagnosis (C) | about 427 ns per tick | host benchmark | S020 |
| v1 trust core (Python, the implementation that runs) | about 85 µs per tick | host benchmark | S020 |
| v2 six domains (Python) | median 747 µs per tick | host benchmark | S012 |
| v2 localization alone | 45.8 µs per tick (9 symptoms) | host benchmark | S012 |
| v2 attribution | median 91.6 µs per tick | host benchmark | S012 |
| v2 explanation | median 87.3 µs per tick | host benchmark | S012 |
| v2 ledger | median 14.1 µs per tick | host benchmark | S012 |
| v2 API build and serialise | about 1-3 ms per tick | host benchmark | S012 |
| STM32H743 | **no build, no measurement** | — | S020 |

### 1.2 What must be benchmarked for the new layer

| operation | proposed structure | what to measure |
|---|---|---|
| evidence creation (envelope) | fixed-size struct in a slot table; id = 64-bit hash of a canonical tuple | per-envelope cost; hash collisions over a campaign |
| admissibility check | precompiled contract masks (`03_EVIDENCE_ADMISSIBILITY.md` §3.4) | per-envelope cost; worst case over all contracts |
| dependency invalidation | per-dimension and per-tag slot bitmaps (`04_CONFIGURATION_TRANSITIONS.md` §3) | worst-case transition with all N slots dependent |
| localization | unchanged algorithm; per-hypothesis suspect masks for refutation independence | added cost of the independence ANDs |
| attribution | unchanged grouping; relevance check against declared discriminators | added cost |
| disagreement analysis | reads the predicate values localization already computes | per-symptom cost |
| trace and ledger | hash chain; compact event | bytes per tick; ledger growth per hour |

**Techniques and when to use them.**

- **Bitsets** are adopted for masks and indices.
- **Sparse graphs:** the derivation DAG only, with bounded depth.
- **Incremental updates:** a later optimisation. Recompute only symptoms whose
  predicate inputs changed (dirty flags), and only if profiling shows
  localization dominates. It does not at 45.8 µs host time.
- **Cached validity:** admissibility is recomputed when the context epoch or
  time crosses a record's bound. It is not recomputed every tick for every
  record.
- **Precompiled contracts:** adopted.
- **Dependency indexing:** adopted.

**Correctness before optimisation.** Every optimised structure must agree
with a straightforward reference implementation on the replay corpus.
Parity-to-reference is how the C core was validated against Python (S020).

## 2. Phases 16 and 37: the safety and FORGE boundaries

| layer | question it answers | owns | must not |
|---|---|---|---|
| **CSIA** | what does the admissible evidence support, and what can it not decide? | evidence admissibility, hypothesis bookkeeping, disagreement, information need, justification trace | command actuators; select adaptations; decide safety |
| **FORGE** (future; documentation only today, S041) | which adaptation to attempt | adaptation selection | treat a CSIA verdict as a command; bypass the RTA |
| **RTA / safety layer** (S075) | what action remains safe | the safety envelope and switching | depend on CSIA for its own guarantees |
| **flight controller** | how to execute | control | take inputs from CSIA |

### 2.1 What crosses each boundary

**From CSIA to FORGE**

- **What:** the assurance state (`09_DOWNSTREAM_AND_PRODUCT.md` §2), read-only.
- **Includes:** the per-function state with reason codes; per-symptom states;
  `implicated_without_evidence`; disagreements; information need; age;
  configuration hash.
- **Semantics:** "justified by admissible evidence" or "not justified". It is
  never "do X".

**From FORGE to CSIA**

- Nothing at run time.
- At design time: declarations and contracts, generated from engineering
  models (S041).
- CSIA outputs never re-enter CSIA as evidence (FM-24).

**From CSIA to the RTA**

- The same read-only state.
- **An RTA that consumes it must treat `UNKNOWN`, `INSUFFICIENT_EVIDENCE`,
  `NO_CONSISTENT_HYPOTHESIS` and `EVIDENCE_DISAGREEMENT` as "not justified".**
  This is fail-closed, the same rule as v1.1's REQUIRE_IDENTIFIABLE
  eligibility (S021).

**From CSIA to the flight controller**

- **Nothing.**

### 2.2 The existing actuation path

The frozen v1 `MavlinkActuator` can call `set_mode` when opted in (S022).

- **It stays as frozen code.**
- **It is DEPRECATED for the target architecture.** Nothing in the new
  layers may import or call it.
- **The v1.1 default-deny output firewall stays in front of every
  transport** (S021).
- **Enforcement** would be by an import-graph test, in the same style as the
  existing v2 import guard (S005).

## 3. Phase 45: provisional budget

The target class is an STM32H743: Cortex-M7 at 480 MHz, with about 1 MB of
SRAM and 2 MB of flash. These are datasheet figures, not verified here.

Every figure below is a **target range to be benchmarked**. None is a
measurement or a claim.

| item | target range | basis for the range | to be benchmarked by |
|---|---|---|---|
| envelope size (onboard form) | 48-96 bytes | 64-bit id; producer and contract indices (16-bit); window (2 × 32-bit); context epoch (32-bit); tag mask (64-128 bit); state; reason; lifecycle state | a struct-size test |
| live evidence slots N | 128-256 | 68 records per tick in Phase C (S012), plus windowed and latched records | profiling of the replay corpus |
| RAM for the slot table plus indices | 16-40 KB | N × envelope + (16 + tags) × N/8 bitmaps | a static-size report |
| contracts (flash, compiled) | 64-256 bytes each; 50-150 contracts | masks plus scalars | a build report |
| code (flash) | 20-60 KB for admissibility, invalidation, lifecycle and trace | comparable to a small DEM-class module | a build report |
| admissibility check | a few hundred cycles per envelope; ≤ 2 µs target | mask ANDs plus two subtractions | a cycle counter on target |
| transition invalidation, worst case | ≤ 50 µs for N = 256 | N/32 word operations plus N marks | a cycle counter on target |
| ledger bytes per tick | ≤ 64 bytes onboard (hashes and counts); full detail post-flight only | compact event format | ledger growth over a 1 h replay |
| total added per tick at 25-50 Hz | ≤ 10 % of the existing CSIA budget (v1.1 requirement R13: under 2 ms per tick) | the new layer must not dominate | end-to-end on target |

**A measured result that exceeds these ranges is recorded as such.** The
design then changes. The target is not quietly moved.

## 4. Phase 46: security and robustness

**The principle.** Metadata is evidence too. None of it is trusted
blindly.

| surface | risk | mitigation |
|---|---|---|
| **spoofed configuration or context state** | context arrives over MAVLink, which is unauthenticated unless signing is on (v0.7 FMEA F7, S019) | context dimensions have freshness, plausibility checks (monotone reset counters; device ids consistent with SYS_STATUS) and stability checks. Any failure gives `UNKNOWN` admissibility for dependent evidence, fail-closed. MAVLink signing remains a deployment requirement |
| **incorrect source identity** | misattributed readings (S026); invisible topology changes (S025) | source binding is declared as `FIXED_DEVICE`, `SELECTED_DEVICE` or `UNKNOWN`. `UNKNOWN` binding means the record cannot serve as an independent refuter |
| **stale contract version** | a record produced under contract v1 read under v2 | the contract id and hash are in the envelope; a mismatch gives `UNKNOWN` (`CONTRACT_MISSING`) |
| **buggy or malicious producer** | a producer declares assumptions it does not meet, or claims validation | the assumptions are **checked by CSIA against context it reads independently**, not taken from the producer. Validation status comes from the registry (`06_PRODUCERS_REGISTRY_AND_ADAPTERS.md` §5). A producer can lower its own output to UNAVAILABLE but cannot raise its own standing |
| **dependency cycles** | invalidation that never terminates | cycles are a load-time error (as in FORGE-SEED, S042); derivation depth is bounded |
| **invalidation storms** | a flapping context blinds the layer | hysteresis plus `CONTEXT_UNSTABLE` (`04_CONFIGURATION_TRANSITIONS.md` §3.5) |
| **trace tampering** | an edited post-flight record | the existing hash chain detects gaps and reordering. It is not tamper-proof against a full rewrite (S009), and it is not presented as more |

This is not a cybersecurity project. The requirement is only that the new
metadata cannot silently promote anything.
