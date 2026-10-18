# CSIA Semantic Core 2.1: shadow validation report

**2026-09-30. Parts 1-3, 21, 22, 25, 26, 45 and 46 of the brief.**
- **The decision is in `PROMOTION_REVIEW.md`:** SEMANTIC_2_1_REQUIRES_REVISION.
- **Frozen v2.0 was authoritative throughout.** 2.1 observed only.

## 1. State before any work (Part 1)

`verify_state.py` wrote `STATE_VERIFICATION.json` with `STATE_AS_EXPECTED:
true`. It was re-run at the end of the phase with the same result.

**What it checks:**
- the Phase A lock hashes of the four frozen reasoning files;
- no change to `csia/v2` since the lock. The only commit after the freeze is
  `f00d315`, lint-only, which predates 2.1;
- the semantic audit results hash;
- the XSYS-001, A1 and A2 protocol manifests;
- the XSYS result manifest against its seal, and the Stage 1 seal;
- the Phase C freeze record and the three sealed-phase manifests;
- the promotion token (SEMANTIC_2_1_READY_FOR_SHADOW);
- the failure ledger against its pinned hash, and the seven held entries.

**The fast 2.1 validation** (`tests/test_semantic_core_2_1.py`) passes 50 of
50.

## 2. The shadow runner (Part 2)

**Where it lives:** `csia_semantic_core/shadow.py`.

**How it keeps 2.1 without authority:**
- `ShadowRunner.evaluate` calls the frozen engine and returns exactly its
  output. This is tested on 60 of 60 ticks against an independent engine.
- 2.1 then runs on the same records, behind an exception barrier: a failure
  inside the shadow becomes `shadow_fault` and cannot reach the authoritative
  path.

**What each tick's record holds:**
- the input hash, not the evidence;
- the v2.0 and 2.1 localization and attribution;
- per-unit differences: verdict change, candidates added and removed, and the
  2.1 reasons;
- predicate faults, unknown-evidence effects and profile-gap effects;
- label changes;
- runtime for both;
- the successor-profile digest when one is applied.

**Size.** The compact per-tick log (`SHADOW_LOG.jsonl`) is about 750 bytes per
tick. The full comparison record is a median of 722 bytes as JSON.

## 3. Differences and their classification (Part 3, dataset A)

**Where the numbers come from:**
- **Harness:** `shadow_validation.py`.
- **Ground truth:** `ground_truth.py`, taken from each scenario's own
  description and expectation.
- **The table's rows:** `SHADOW_DIFFERENCES.csv`, one row per differing unit,
  with the basis of its category.

**How it was classified.** The classifier grades against ground truth and
the declared scope, never by the name of the correction that caused the
difference. A unit is one symptom-subject localization or one tick's
attribution.

| | count |
|---|---|
| ticks | 2,640 |
| ticks differing | 945 |
| ticks differing only in a label (SEMANTIC_CLARIFICATION: UNSUPPORTED renamed NO_CONSISTENT / INSUFFICIENT) | 68 |
| trace-only ticks | 0 |
| shadow faults | 0 |
| **differing units** | **1,275** |
| CORRECTNESS_FIX | **273**: 84 wrong-cause UNIQUE withheld (MS_B5, MS_TS_B5); 189 false navigation symptoms from unrelated components removed (MS_B1, NETWORK_LATENCY) |
| CONSERVATIVE_WITHHOLD | **197**: correct UNIQUE withheld by F2 (`WEAKENED_UNIQUE_REVIEW.md`) |
| PROFILE_GAP | **805**: 601 on COARSE_NAVIGATION (G-1: 481 not raised, 120 weakened); 123 OUTPUT_MISSING on the estimator (G-2); 81 UNIQUE withheld through G-2 |
| POSSIBLE_REGRESSION | **0** |
| UNKNOWN | **0** |

**Under the accepted successor profile r1:**
- the 601 G-1 units return to v2.0;
- what still differs: FIX 273, WITHHOLD 197 and the 204 G-2 units, which are
  explicitly blocked;
- nothing new differs (`PROFILE_COUNTERFACTUAL_RESULTS.md`).

## 4. Datasets (Part 21)

| dataset | result |
|---|---|
| A: 44 scenarios, 2,640 ticks | as §3 |
| B: XSYS-001, 3,872 sealed slots | 0 decision, 0 outcome and 0 full-view differences; primary 55/55, lower bound 0.7616; hard gate PASS |
| C: small-state enumeration | identical to the accepted section D |
| D: 68,640 predicate-fault injections | `PREDICATE_FAULT_POLICY.md` |
| E: configuration transition E1 (frozen design), plus the XSYS-001 exploratory reanalysis | `CONFIGURATION_TRANSITION_STUDY.md`, `XSYS_STATE_CONDITIONED_EXPLORATION.md` |

## 5. Trying to break 2.1 (Part 22)

Source: `WORSE_ANSWER_SEARCH.json` and the harnesses named.

| looked for | found |
|---|---|
| wrong UNIQUE introduced | **0**; 3 wrong UNIQUE shared with v2.0 (L16) |
| true hypothesis eliminated | **0 introduced**; 121 unit-ticks eliminated identically by v2.0 and 2.1, at fault onsets (ACTUATOR_NO_RESPONSE, CPU_OVERLOAD, MS_C2, SHARED_SOURCE, STALLED_ACTUATOR, TS_STALLED), all in the effect-before-cause pattern of L16 |
| wrong SUPPORTED introduced | **0** in dataset A |
| relevant evidence ignored | none that decides an answer. GPS source health in MS_D1 lies outside the navigation functions' declared scope (180 unit-ticks). The answer there is still right, because the v1.1 eligibility record carries it; it becomes in scope only with R5a, which waits on R-2 |
| profile error amplified | 2.1 is more sensitive to profile errors than v2.0, mostly as underconfidence. Over-connection (M2) makes it raise 126 unit-ticks of false symptoms. **v2.0 was overconfident on one mutation (81), 2.1 on none** (`PROFILE_VALIDATOR_SPEC.md`) |
| predicate fault mishandled | **yes, under 2.1's current policy A:** one failing predicate creates 168 wrong SUPPORTED unit-ticks. Policy B removes them (revision R-1) |
| profile repair restores a wrong answer | **yes, constructed:** any GNSS-input declaration for the estimator restores v2.0's wrong SUPPORTED process_stall when the IMU dies (W7; L17; revision R-2) |
| conflict / replay mishandled | 5 scenarios × 4 replay variants: 0 wrong answers in 2.1. A replayed record beside the current one makes the key unread. A replay that **replaces** the current record is admitted, undetected (L8) |
| stale evidence mishandled | **yes, shared with v2.0:** 9 ticks of false SUPPORTED after a lane switch (E1; revision R-3) |
| latency unacceptable | no: desktop median 547 µs (trace off), p99 1.09 ms, max 1.55 ms per tick |

## 6. Reason-trace quality (Part 25)

Across the 1,275 differing units, the trace answers the brief's six questions
like this:

| question | does the 2.1 trace answer it? |
|---|---|
| why UNIQUE was refused | **yes, for all 362 withheld UNIQUE units**: `withheld_unique_because` names the gate |
| what alternative remained | **yes**: `localization_disagreement` lists the retained hypotheses per symptom |
| what evidence was missing | **yes, for localizations that exist**: `evidence_unavailable`, `unknown_inputs`, `scope_gaps` (NO_DECLARED_LINK and the like) |
| what evidence was irrelevant | **yes**: `other_nominal` marks records as NOT_A_DECLARED_ALTERNATIVE, and `ignored` lists records outside scope |
| did a predicate fail | **yes**: 15,118 of 15,118 evaluated injected faults visible |
| did a profile gap matter | **yes, where a localization exists**: 243 units carry `scope_gaps` |

**What the trace does not answer.**
- **Why a symptom was not raised.** 670 of 1,275 differences (53 %) are
  symptoms 2.1 did not raise. Because no localization exists for them, no
  trace exists either. The classifier had to recompute each subject's
  declared scope to explain them. A detector-level trace (subjects
  considered, and the scoped tests' values) is missing.
- **Why a refuter was unmeasurable.** A None is reported, but not the reason:
  for example, the clock inconsistency that makes CLOCK_DRIFT's segment
  latencies unmeasurable.
- **Which profile a result was reasoned against.** `TickResult` does not carry
  the profile digest; only the shadow record does.
- **Whether an abstention is NECESSARY or ARTIFICIAL.** That needs knowledge
  of the platform the trace does not have, and is recorded in the review.

**Measured by content, not length:**
- **With a localization, the trace answered all six questions.**
- **For the 53 % of differences without one, it answered none.**

## 7. Runtime (Part 26)

Desktop CPython, 2,640 ticks, three passes, per-tick medians. Source:
`SHADOW_RUNTIME.json`.

| | mean | median | p95 | p99 | max |
|---|---|---|---|---|---|
| v2.0 alone (reasoning) | 231 µs | 210 µs | 473 µs | 554 µs | 722 µs |
| 2.1 alone, trace on | 707 µs | 630 µs | 1,290 µs | 1,441 µs | 2,086 µs |
| 2.1 alone, trace off | 593 µs | 547 µs | 970 µs | 1,090 µs | 1,550 µs |
| shadow overhead (2.1 + comparison + hash) | 2,311 µs | 2,443 µs | 3,276 µs | 3,868 µs | 5,547 µs |
| v2.0 + shadow | 2,542 µs | 2,619 µs | 3,741 µs | 4,287 µs | 6,151 µs |

**Ratios and memory:**
- **Speed ratios, medians:** 2.1 against v2.0 is 3.0× with the trace and 2.6×
  without. v2.0 + shadow against v2.0 alone is 12.5×.
- **Memory, largest tick (68 records), peak traced:**
  - v2.0: 5.6 KB;
  - 2.1: 24 KB;
  - one shadow observation: 116 KB.
- **Retained state:** none between ticks.

**Record scaling.** The largest tick was padded with renamed copies of its
records, 68 to 2,176.
- **Log-log slopes:** 1.44 for v2.0, 1.31 for 2.1 (trace off).
- **The ratio falls with size:** 5.0× at 68 records, 3.7× at 2,176.

## 8. Decision quality, not maximum certainty (Parts 45 and 46)

**The principle for future work: more UNIQUE verdicts is not better; correct
certainty is.** Every future change should be reported on these rows, from
this phase's harnesses. The table gives the dataset A baseline:

| measure | frozen v2.0 | 2.1 | 2.1 + successor r1 |
|---|---|---|---|
| wrong UNIQUE (tick) | 87 (84 in MS_B5 and MS_TS_B5, plus 3 at L16 onset) | 3 (L16) | 3 (L16) |
| correct UNIQUE withheld against v2.0 | — | 278 | 278 |
| of those, NECESSARY / TEMPORARY / ARTIFICIAL / REGRESSION | — | 2 scenarios / 1 / 5 / 0 | same |
| false symptoms on unaffected functions (unit-ticks) | 189 | 0 | 0 |
| real symptoms not raised because of the profile | — | 481 | 0 |
| fault-created wrong SUPPORTED (dataset D) | not measured on v2.0 here (the audit measured 9 SUPPORTED created) | 168 (policy A) | 168; 0 with policy B |
| profile faults caught before running | — | — | 9 of 10 mutations (validator) |

**Rewarding guessing is avoided.** A UNIQUE is counted correct only when its
evidence could have excluded the alternative. MS_B4 and MS_B5 carry identical
evidence, so v2.0's UNIQUE on MS_B4 is counted as luck, not skill.

## 9. Deviations and disclosures

- **R5a and R5b** were added to the candidate list after the first
  counterfactual run showed R5 unsafe. The note in
  `profile_candidates.json` records this.
- **Ground truth changed twice during the phase, both times on stated
  grounds, not on results.**
  - **SHARED_RAIL is time-resolved.** The payload's own GPS fault is the only
    cause before the rail leaves tolerance.
  - **POSITION_UNAVAILABLE in MS_A1 and MS_A2 is "no declared hypothesis"**,
    from the hypothesis definitions.
  - The fault-created SUPPORTED count (168) is the same either way; only its
    grading changed.
- **The XSYS reanalysis was iterated after its first result.** Its document
  discloses how.
- **The configuration-transition experiment's design was committed before
  its runner existed** (`e0fc81a`).
