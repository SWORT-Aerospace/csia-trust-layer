# Promotion review: Semantic Core 2.1.1 as the semantic baseline for new work

**2026-10-01.**
- **Gate entering this phase:** SEMANTIC_2_1_REQUIRES_REVISION (shadow
  validation, `research/csia_semantic_core_2_1_shadow/PROMOTION_REVIEW.md`).
- **What the owner approved:** exactly three revisions, R-1, R-2 and R-3.
- **The question:** can 2.1, so revised, become the preferred semantic
  baseline for new CSIA work?
- **Frozen v2.0 remains the historical, authoritative implementation.** This
  review gives 2.1 no control authority.

**What "2.1.1" means here.** `Corrections.revised()` with successor profile
r2 and the epoch integration contract (`R3_CONFIGURATION_EPOCH.md` §6).
`Corrections()` is still 2.1.0, and every result says which version produced
it.

## 1. What it was measured against

| dataset | what | source |
|---|---|---|
| 0 | the starting state, locked before any code, and the three blockers reproduced | `BASELINE_LOCK.json` |
| A | 44 scenarios, 2,640 ticks; v2.0, 2.1.0, 2.1.0 + r1, 2.1.1, 2.1.1 + r2, and three ablations | `DATASET_A_THREE_WAY.json`, `REVISION_DIFFERENCES.csv` |
| B | XSYS-001: 3,872 sealed slots, under 2.1.0 and 2.1.1 | `GOVERNANCE_GATES.json` |
| C | the small-state enumeration and the 2.1 test suites, under 2.1.0 and 2.1.1 | `ENUMERATION_THREE_WAY.json`, `PROPERTY_RERUN.json` |
| D | 68,640 single-predicate injections (71,280 under 2.1.1 + r2) | `FAULT_REPLAY_RESULTS.json` |
| E | E1 replayed exactly; 14 adversarial epoch variants | `TRANSITION_REPLAY_RESULTS.json`, `EPOCH_ADVERSARIAL_RESULTS.json` |
| + | profile validation and mutations; worse-answer search; trace; runtime | the respective JSON files |
| final | the starting state re-verified at the end | `FINAL_STATE_CHECK.json` |

## 2. The sixteen criteria (the shadow review's, re-evaluated)

| # | criterion | result | evidence |
|---|---|---|---|
| 1 | XSYS-001 remains unchanged | **PASS** | under 2.1.1: 3,872 slots; 0 decision, 0 scored-outcome and 0 full-view differences; primary 55/55, lower bound 0.7616, SUPPORTED; hard gate PASS. Sealed manifests match (`FINAL_STATE_CHECK.json`) |
| 2 | Phase C headline remains intact | **PASS** | CROSS_DOMAIN_ASSURANCE_FUNCTIONAL and the six answers, unchanged under 2.1.1 with and without r2 |
| 3 | no unexplained wrong UNIQUE is introduced | **PASS** | 0 against v2.0 and 0 against 2.1.0 + r1 on dataset A; 0 in dataset D; 0 in E1 and its variants. The 3 L16 onset UNIQUE are shared with v2.0 |
| 4 | wrong-UNIQUE corrections remain corrected | **PASS** | MS_B5 and MS_TS_B5: 0 wrong UNIQUE ticks under 13 profile variants of 2.1.1 |
| 5 | all seven weakened-correct scenarios are explained | **PASS** | PROCESS_STALL and MS_D2 restored, for the right reason; MS_B4 and STALLED_ACTUATOR NECESSARY; ACTUATOR_NO_RESPONSE, MS_B3 and CLOCK_DRIFT ARTIFICIAL (signature refuters, out of scope); TS_STALLED onset TEMPORARY |
| 6 | G-1 resolved or explicitly blocked | **PASS (resolved)** | r2 carries r1's declarations unchanged; 0 profile-gap units remain on COARSE_NAVIGATION |
| 7 | G-2 resolved or explicitly blocked | **PASS (resolved)** | R-2 + r2, with no GNSS edge: 204 units restored for the right reason, 0 new wrong. The rejected repairs cannot return (permanent tests) |
| 8 | predicate-fault policy selected and validated | **PASS (adopted)** | R-1 implemented: 168 → 0 fault-created SUPPORTED; equal to the reference policy B count for count; every fault visible |
| 9 | profile repairs do not restore semantic defects | **PASS** | r2 restores none. Under 2.1.1 even R5/R5a/R5b do not restore the wrong process_stall. Residual: a wrong pacing declaration on a real edge can (L24) |
| 10 | property tests remain green | **PASS, with P5 superseded** | under 2.1.1, every property test but P5 passes unchanged. P5's decision clause ("a fault decides what None decides") is what R-1 changes by definition. Its replacement P5' (a fault is never more certain than None) holds over P5's 1,144 injections and is pinned |
| 11 | small-state enumeration remains green | **PASS** | section D identical under 2.1.1 (29 of 29 measures); 0 new violations; R9B moves from deferred to fixed |
| 12 | realistic configuration transitions show no unsafe semantic behaviour | **PASS (under the stated contract)** | E1 replayed exactly: 9 stale ticks → 0, 0 valid records lost. Every adversarial variant that keeps the contract: 0 stale. A broken contract reproduces at most 2.1.0's behaviour. The two worst cases are a transition nobody reports (9) and counter-only stamps across a restart (6); the fail-closed cases instead withhold evidence |
| 13 | runtime complexity remains bounded | **PASS** | 1.13× 2.1.0 (median, trace off); record-scaling slope 1.09; admission linear; no retained state; fault policy free (0.99×) |
| 14 | frozen v2 remains reproducible | **PASS** | Phase A lock hashes match; no csia/v2 change since the lock (`FINAL_STATE_CHECK.json`) |
| 15 | historical manifests remain valid | **PASS** | XSYS chain and seals, Phase C freeze record, three sealed-phase manifests, ledger hash; shadow and 2.1 packages unchanged |
| 16 | no downstream control authority uses 2.1 yet | **PASS** | nothing under `csia/` imports `csia_semantic_core` (test); the shadow runner returns the frozen output |

**Tally: 16 PASS, 0 FAIL, 0 DEFERRED.** Criteria 10 and 12 pass with a stated
qualification, given in the row and not hidden in the tally.

**The brief's own acceptance checks for the three revisions:**

| check | result |
|---|---|
| R-1: an irrelevant failure does not destroy unrelated conclusions | 0 of 75,752 IRRELEVANT pairs lost anything |
| R-1: a material refuter failure does not create SUPPORTED | 168 → 0 |
| R-1: a material confirmer failure does not preserve certainty | no SUPPORTED rests on a failed confirmer (tests) |
| R-1: failures stay visible | 15,118 / 15,118; 17,400 / 17,400 |
| R-1: trace per affected conclusion | `fault_impact`: predicate, hypothesis, role, MATERIAL / NOT_MATERIAL, action, on 1,344 / 1,344 faulted localizations |
| R-2: cases A-E | all as required (`R2_PACING_STARVATION.md` §4) |
| R-2: G-1 kept separate; no R5/R5a; rejected repairs cannot return by another path | yes; permanent tests |
| R-3: tests 1-7 | all pass |
| R-3: trace (producer, evidence epoch, current epoch, transition event) | 269 / 269 inadmissible records complete |
| Phase 3: 0 fault-created SUPPORTED | 0 |
| Phase 4: no UNKNOWN | 0 UNKNOWN, 0 POSSIBLE_REGRESSION |
| Phase 6: MS_B5 / MS_TS_B5 wrong UNIQUE | 0 under every variant |
| Phase 7: E1, 0 stale ticks and 0 valid evidence discarded | 0 and 0 |
| Phase 9 / 10 hard gates | both PASS; no STOP token |

## 3. Is 2.1.1 the better semantic baseline?

**Measured, yes. On no dimension measured is 2.1.1 worse than 2.1.0 or than
frozen v2.0, when the profile is right and the epoch contract is kept.**

**Against 2.1.0:**
- it removes both specified defects (L17, L18);
- it closes the one failed criterion (12);
- it closes every remaining profile gap;
- it restores 204 correct conclusions, for the right reason;
- it adds no wrong answer anywhere.

**Against frozen v2.0, it keeps:**
- every correct SUPPORTED (2,285);
- every correct NO_CONSISTENT (285);
- no false symptom (189 → 0);
- 3 wrong UNIQUE instead of 87.

What it gives up is 197 UNIQUE ticks that v2.0 did not justify.

**Where it can be worse.** Only where a precondition is broken
(`WORSE_ANSWER_SEARCH.md`):
- **A wrong or incomplete pacing declaration (L24)** can restore a wrong
  process_stall.
- **A broken epoch contract (L25)** either fails closed, possibly hiding a
  symptom (L26), or behaves as 2.1.0 did.

Neither occurs with the shipped profile and a correct integration. Both are
documented with their mitigations.

## 4. What the baseline designation means, and does not

**It means:**
- **New CSIA semantic work builds on 2.1.1**, not on frozen v2.0 or on 2.1.0.
  That covers new profiles, new producers, SITL and replay tooling, and any
  future semantic change. Concretely: `Corrections.revised()`, successor
  profile r2 (or a reviewed successor of it), and an integration that
  supplies the epoch context.
- **Shadow observation continues,** now with 2.1.1 in the shadow slot.

**It does not mean:**
- **2.1.1 is not authoritative.** Frozen v2.0 remains the runtime default
  and the historical record. No consumer acts on 2.1.1. Giving it authority
  is a separate decision this review does not make.
- **The code default does not change.** `Corrections()` stays 2.1.0, as the
  brief's versioning rule requires. Changing the default would be an owner
  decision and a new version.
- **Nothing is onboard.** No C port exists. The H743 figures are estimates
  (`H743_UPDATE.md`).
- **No historical result changes.** Every frozen, sealed and shadow artifact
  is byte-identical (`FINAL_STATE_CHECK.json`).

**The conditions of the designation.** Each is a precondition the evidence
above rests on:
1. **Every pacing declaration cites the code that gates the output.** Use
   ANY over all IMUs on multi-IMU PX4 platforms (L24).
2. **The integration supplies the epoch context every tick:**
   - keyed on monotonic counters;
   - composite epochs across producer restarts;
   - narrow counters unwrapped;
   - UNKNOWN_EPOCH_KEY and MALFORMED_EPOCH treated as configuration errors
     (L25, L26).
3. **The static validator (PV1-PV9) gates every profile.**

## 5. What remains open

These are recorded, not authorized, and not started:
- **Pacing per configuration epoch** (L21): the dependency R-2 has on R-3.
- **A symptom-level "not evaluated" flag** (L26).
- **The three ARTIFICIAL abstentions:** signature refuters.
- **Correlated evidence, intake validation, producer contracts, the C port.**
- **The ledger.** FL-061 and FL-062 are drafted; FL-053 to FL-060 are still
  held. All of it waits on the owner.

## Decision

**SEMANTIC_2_1_READY_AS_BASELINE**

2.1.1, so defined, is ready to be the preferred semantic baseline for new
CSIA work, under the three conditions in §4.

**The designation does not change any of the following:**
- **Frozen v2.0 remains the authoritative runtime default.**
- **2.1 has zero control authority.**
- **The code default stays 2.1.0.**
- **No historical artifact changes.**

**What was not chosen, and why:**
- **Not REQUIRES_REVISION.**
  - The three required revisions are made and verified.
  - Every criterion passes.
  - The residuals (L24-L26, L21) are preconditions on profiles and
    integration, documented with mitigations. They are not defects in the
    revised semantics that a further change within the approved scope would
    fix.
- **Not KEEP_SHADOW.** That would say more observation is what is needed. The
  measurements answer the question asked. Shadow observation continues in
  any case.
- **Not GOVERNANCE_BLOCK.** No governance rule was broken:
  - no frozen, sealed or historical file changed;
  - nothing was appended to the ledger;
  - all new behaviour is versioned separately;
  - the E1 design was replayed as frozen;
  - neither hard gate tripped.

**A note on the brief.** It arrived truncated in Phase 18, so its own list of
decision tokens could not be read. The four tokens above are the ones the
shadow-validation brief defined for the same question. If the owner's
intended token set differs, the evidence in this package is unchanged, and
only the label needs mapping.
