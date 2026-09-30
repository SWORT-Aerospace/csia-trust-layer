# Promotion review

**2026-09-30. Parts 32, 33 and 56 of the shadow-validation brief.**
- **Gate entering this phase:** SEMANTIC_2_1_READY_FOR_SHADOW.
- **Frozen v2.0 remains authoritative.** 2.1 has no control authority, and
  this review gives it none.

**The question** is whether 2.1 is actually a better semantic baseline. It is
not whether 2.1 can be made to look better.

## 1. What 2.1 was measured against

| dataset | what | source |
|---|---|---|
| A | 44 shipped scenarios, 2,640 ticks, classified against ground truth | `SHADOW_RESULTS.json`, `SHADOW_DIFFERENCES.csv` |
| B | XSYS-001: 3,872 sealed slots, re-executed | `SHADOW_RESULTS.json` B_xsys |
| C | the small-state enumeration and property measures, re-executed | `DATASET_C_RESULTS.json` |
| D | 68,640 single-predicate fault injections | `PREDICATE_FAULT_RESULTS.json` |
| E | configuration transition E1 (design frozen first), plus XSYS-001 state-conditioned reanalysis (exploratory) | `TRANSITION_RESULTS.json`, `XSYS_STATE_CONDITIONED_RESULTS.json` |
| + | adversarial profile mutations, worse-answer search, IMU dependency preview, runtime | the respective JSON files |

## 2. The sixteen criteria

| # | criterion | result | evidence |
|---|---|---|---|
| 1 | XSYS-001 remains unchanged | **PASS** | re-executed this phase: 3,872 slots; 0 decision, 0 outcome and 0 full-view differences against the sealed run; primary 55/55, lower bound 0.7616, hard gate PASS. The sealed result manifest and Stage 1 match their seals (`STATE_VERIFICATION.json`) |
| 2 | Phase C headline remains intact | **PASS** | frozen `decision_gate` over 2.1: CROSS_DOMAIN_ASSURANCE_FUNCTIONAL, the same qualifying sets and the same six answers, under 2.1 alone and under every one of 16 profile configurations |
| 3 | no unexplained wrong UNIQUE is introduced | **PASS** | dataset A: 0 wrong UNIQUE introduced. The 3 that remain (TS_CPU_OVERLOAD 26-28) are identical in v2.0 and explained (effect visible before cause, L16). Dataset D: 0 new wrong UNIQUE under every policy. Mutations: 0 overconfident. E1: 0 wrong UNIQUE |
| 4 | wrong-UNIQUE corrections remain corrected | **PASS** | MS_B5 and MS_TS_B5: 0 of 42 wrong ticks under 2.1 with no profile, with successor r1, and with every candidate declaration (R1-R6, R5a, R5b, R-BAD). There are 24 pinned regression cases |
| 5 | all seven weakened-correct scenarios are explained | **PASS** | `WEAKENED_UNIQUE_REVIEW.md`: every withhold is F2; v2.0 was right for the wrong reason in all seven (category B); 2 NECESSARY, 5 ARTIFICIAL, 0 REGRESSION; TS_STALLED's onset is TEMPORARY |
| 6 | G-1 resolved or explicitly blocked | **PASS (resolved)** | versioned successor profile r1 (R2 + R3), digest `c7541cab…`: all 601 G-1 units restored, 0 new incorrect, 0 new wrong UNIQUE, XSYS and Phase C unchanged. Not applied by default |
| 7 | G-2 resolved or explicitly blocked | **PASS (explicitly blocked)** | no profile repair is safe. Each candidate that restores the 204 G-2 units (R5, R5a, R5b) brings back v2.0's wrong reason in the IMU pacing-loss counterfactual. The cause is a 2.1 predicate-scope defect (L17), not profile data. Unblocking is revision R-2 below |
| 8 | predicate-fault policy selected and validated | **PASS (in shadow)** | policy B selected and validated on dataset D: 168 → 0 fault-created wrong SUPPORTED, 42 of 42,770 correct SUPPORTED lost, attribution unaffected. **2.1 still implements policy A**; adopting B is revision R-1 below |
| 9 | profile repairs do not restore semantic defects | **PASS** | the accepted repair (r1) restores none: 0 wrong UNIQUE, and MS_B1's false symptoms stay removed. The candidates that would restore a defect (R5, R5a, R5b; R-BAD restores 126 false symptoms) are rejected or deferred for that reason |
| 10 | property tests remain green | **PASS** | `tests/test_semantic_core_2_1.py`: 50 passed, including the Hypothesis property tests |
| 11 | small-state enumeration remains green | **PASS** | section D re-executed: identical to the accepted result (18 FIXED, 5 INTENTIONALLY_DEFERRED, 10 NOT_APPLICABLE). The audit probe's R section differs from the audit only in the fault-record format, as the 2.1 package already recorded |
| 12 | realistic configuration transitions show no unsafe semantic behaviour | **FAIL** | E1: after an estimator lane switch, 2.1 without validity management SUPPORTS a false POSITION_UNAVAILABLE (COMPUTE/estimator_stale) on two navigation functions for 9 ticks, as long as a latched producer holds old-lane content. Frozen v2.0 does exactly the same, so this is **not a regression**, but it is confidently wrong semantic behaviour in a realistic transition. The configuration-epoch rule removes it (0 stale ticks, 0 valid records discarded). This is revision R-3 below |
| 13 | runtime complexity remains bounded | **PASS** | no subset search, no retained state; per-tick work linear in the records' declared structure. Record-padding slope 1.31 (2.1, trace off) against 1.44 (v2.0). Desktop median 547 µs against 210 µs, 2.6× (trace off). Shadow overhead is 12.5× and is ground-only |
| 14 | frozen v2 remains reproducible | **PASS** | Phase A lock hashes of the four frozen reasoning files match; no change to `csia/v2` since the lock; the shadow runner returns the frozen engine's output identically on 60 of 60 ticks (test) |
| 15 | historical manifests remain valid | **PASS** | the three sealed-phase manifests, the Phase C freeze record, the XSYS protocol chain (XSYS-001, A1, A2), the XSYS result manifest and the Stage 1 seal all match (`verify_state.py`); the failure ledger matches its pinned hash |
| 16 | no downstream control authority uses 2.1 yet | **PASS** | nothing under `csia/` imports `csia_semantic_core` (test); the shadow runner returns the frozen output and logs 2.1 only |

**Tally: 15 PASS, 1 FAIL, 0 DEFERRED.**

**The pass count overstates readiness.** Criteria 7 and 8 pass as the brief
words them ("explicitly blocked", "selected and validated"). Each still names
a change 2.1 has not made.

## 3. Is 2.1 a better semantic baseline than v2.0?

**Measured, yes. On no dimension measured in this phase is 2.1 worse than
v2.0:**
- 0 wrong UNIQUE introduced;
- 0 true hypotheses newly eliminated;
- 0 wrong SUPPORTED introduced;
- 0 overconfident results under profile mutations, against 81 for v2.0;
- the same behaviour under stale evidence;
- 273 correctness fixes;
- every withheld UNIQUE explained, none a regression.

**Is it ready to be the baseline for new work? No:**
- **criterion 12 is materially failed;**
- **2.1 carries two specified semantic defects**, fixable and small, that a
  baseline should not carry into new work:
  - **L18:** a failed refuter can leave a wrong SUPPORTED standing, 168
    unit-ticks in dataset D;
  - **L17:** a correct profile completion makes the starvation refuter read an
    unrelated link.

## 4. Revisions required before promotion can be reconsidered

| id | revision | closes | size | how to check it |
|---|---|---|---|---|
| R-1 | adopt predicate-fault policy B | criterion 8 fully; L18 | small: the reference implementation exists (`predicate_fault_study.apply_policy`) | dataset D: 0 fault-created SUPPORTED; the pinned test flips from policy A's SUPPORTED to WITHHELD |
| R-2 | refute COMMUNICATION/input_starvation from the subject's declared pacing inputs or direct input links, not its closure; then accept R5a into successor profile r2 | criterion 7 (resolved rather than blocked); L17; two ARTIFICIAL abstentions | small | W7 counterfactual stays AMBIGUOUS under r2; PROCESS_STALL and MS_D2 UNIQUE restored for the right reason |
| R-3 | configuration-epoch invalidation for configuration-derived records (the smallest admissibility piece) | criterion 12 | moderate | E1 re-run: 0 stale ticks; then transition B, once authorized |

Each of these changes decisions, so each needs the owner's approval, as C1 to
C6 did. After them, this shadow suite (datasets A-E, the worse-answer search,
the adversarial mutations) is re-run unchanged.

## Decision

**SEMANTIC_2_1_REQUIRES_REVISION**

**What this means:**
- 2.1 stays exactly where it is: shadow only, zero control authority, not the
  default. Frozen v2.0 stays authoritative.
- 2.1 is not promoted to baseline because criterion 12 fails and two
  specified 2.1 defects (L17, L18) remain. R-1, R-2 and R-3 are what must
  change before promotion is reconsidered.

**What it does not mean:**
- **It does not mean 2.1 is worse than v2.0.** On everything measured, it is
  not.
- **It does not mean the shadow deployment should stop.** Shadow
  observation continues, and the successor profile r1 can be used in shadow.

**What was not chosen, and why:**
- **Not KEEP_SHADOW.** That would say more observation is what is needed.
  This phase already identified the specific changes, and more shadow data
  without them would re-measure the same three gaps.
- **Not GOVERNANCE_BLOCK.** No governance rule was broken:
  - no sealed file, frozen file or historical result was edited;
  - the held ledger entries were not appended;
  - the successor profile is versioned separately;
  - the one new experiment's design was committed before it ran;
  - the XSYS reanalysis is labelled exploratory.
