# CSIA Semantic Core 2.1: promotion-candidate revision report

**2026-10-01.**
- **The decision is in `PROMOTION_REVIEW.md`.**
- **The revisions themselves:** `R1_FAULT_POLICY_B.md`,
  `R2_PACING_STARVATION.md` and `R3_CONFIGURATION_EPOCH.md`.
- **The worse-answer search:** `WORSE_ANSWER_SEARCH.md`.
- **Frozen v2.0 remained authoritative throughout.** 2.1 has no control
  authority, and nothing here gives it any.

## 1. What was implemented, and how it is versioned

**The three approved items:**
- **R-1:** dependency-sensitive predicate-fault policy B.
- **R-2:** starvation from pacing inputs, not from the closure.
- **R-3:** configuration-epoch invalidation.

**How they are versioned:**
- **Each is its own switch** in `Corrections`: `fault_policy_b`,
  `pacing_inputs`, `config_epoch`.
- **All three are off by default**, so `Corrections()` and every existing
  caller still get 2.1.0. `Corrections.revised()` turns everything on.
- **A result reports semantics 2.1.1 and schema `csia.semantic_core/2.1.1`**
  whenever a revision is on. `SEMANTICS_VERSION` stays "2.1.0".

**What is new beside the switches:**
- the successor profile **r2**: r1 unchanged, plus one pacing declaration;
- validator rule **PV9**;
- `EpochContext`;
- epoch pass-through in the shadow runner.

**Nothing else was built:**
- no producer registry, admissibility engine, provenance graph or general
  dependency graph;
- no correlation-aware fusion, CUSUM or EKF2 adapter, or profile compiler;
- no FORGE, RTA or active diagnosis;
- no C port, and nothing toward 2.2.

**One dependency was found and stopped at, not built:** pacing that follows
the configuration epoch (`R2_PACING_STARVATION.md` §8).

**Code changed** (all in `csia_semantic_core/`, outside `csia/`):

| file | change |
|---|---|
| `admission.py` | new: the epoch rule |
| `core.py` | the three switches, `revised()`, the 2.1.1 version and schema, `reason(records, epochs)`, `pacing=` |
| `localization.py` | `fault_impact`; WITHHELD_PREDICATE_FAULT |
| `predicates.py` | PACING_INPUTS_NOMINAL; OUTPUT_MISSING's starvation hypothesis under R-2 |
| `index.py` | `note_conflict` (trace only) |
| `profile_overlay.py` | pacing declarations, `pacing_map()`; r1's digest unchanged |
| `profile_validator.py` | PV9 |
| `shadow.py` | pacing from the overlay; epochs passed through; 2.1.1 fields in the log |
| `successor_profiles/aircraft_successor_r2.json` | new |

## 2. Phase 0: the starting state, locked first

`verify_baseline.py` wrote `BASELINE_LOCK.json` (`BASELINE_AS_EXPECTED: true`)
**before any revision code existed**, committed as `dd655a8`.

**What it verified:**
- frozen v2's reasoning files against the Phase A lock, and no csia/v2 change;
- the semantic audit's results hash;
- XSYS-001: the result manifest against its seal, every file it lists, the
  protocol chain (XSYS-001, A1, A2), Stage 1 against its seal;
- the Phase C freeze record and the three sealed-phase manifests;
- both promotion tokens: READY_FOR_SHADOW and REQUIRES_REVISION;
- the successor r1 digest;
- the shadow package unchanged since `9a09674`;
- the ledger hash and the seven held entries;
- 50 of 50 and 51 of 51 tests passing.

**The three blockers reproduced exactly:**

| blocker | reproduced |
|---|---|
| B1 | policy A: 168 fault-created wrong SUPPORTED. The whole reference table (policies A to D) matched the shadow package with 0 differences |
| B2 | W7 with R5, R5a or R5b: SUPPORTED COMPUTE/process_stall |
| B3 | E1 without validity management: 9 stale POSITION_UNAVAILABLE ticks (25-33) |

## 3. Phase 1: every test and property, re-run

**How (`property_rerun.py`).** Each 2.1 test file was run twice, in separate
processes: once as committed, and once with a research plugin that makes
`Corrections()` mean `Corrections.revised()`.

| file | as committed | with 2.1.1 as the default | what fails under 2.1.1, and why |
|---|---|---|---|
| `test_semantic_core_2_1.py` | 50 / 50 | 47 / 50 | (1) the version test pins `Corrections().ids()`; (2) R9B pins policy A; (3) **P5**: see below |
| `test_semantic_core_2_1_shadow.py` | 51 / 51 | 47 / 51 | (1-3) R5/R5a/R5b pin the wrong process_stall that R-2 removes; (4) the policy-A pin R-1 changes |
| `test_semantic_core_2_1_revision.py` (new) | 75 / 75 | 67 / 75 | each failing test uses `Corrections()` as its 2.1.0 control |

**What the failures are.** Each pins either a 2.1.0 version, or a 2.1.0
decision the owner approved changing. None is unexpected.

**P5 is a property, and its decision clause is superseded by R-1 by
definition.**
- **Why:** a faulted refuter now withholds, while an unmeasured one does not.
- **The replacement, P5':** a fault is reported wherever it is evaluated, and
  never decides anything more certain than None.
- **Checked over P5's own 1,144 injections:**
  - 376 of 376 faults reported;
  - 5 differences, each a withheld SUPPORTED naming the fault;
  - 0 more certain;
  - 0 attribution differences.
- `R1_FAULT_POLICY_B.md` §4.

**Every other property test (P1-P4, P6-P19) passes under 2.1.1 unchanged.**

## 4. Phase 2: small-state enumeration, three ways

**How (`enumeration_three_way.py`).** The 2.1 package's own harness (audit
probe, section D, R21) was run as committed (2.1.0), and again with every core
it builds made 2.1.1.

| | result |
|---|---|
| section D under 2.1.0 | identical to the accepted section D |
| section D under 2.1.1 | **identical to the accepted section D**: 29 of 29 measures unchanged (18 FIXED, 10 NOT_APPLICABLE, 1 INTENTIONALLY_DEFERRED; with the 4 unmeasured deferrals, the 5 INTENTIONALLY_DEFERRED of the counts) |
| new violations | **0** |
| removed | **R9B** ("a raising refuter creates SUPPORTED") moves from deferred to **FIXED**: the synthetic case now ends WITHHELD_PREDICATE_FAULT, AMBIGUOUS in the 2.0 view, with a MATERIAL / SUPPORTED_WITHHELD entry |
| unchanged and still deferred | P17 (uniform exception handling), P18 (source identity), P20 (C8): outside R-1, R-2 and R-3 |
| audit probe sections | R differs from the audit only in the fault-record format, as the 2.1 package already recorded |

**One more difference: the audit's SH section.** It runs each correction
ALONE, and under the 2.1.1 binding each single-correction run also carries
R-2.
- **Where it shows:** 27 paths, only in the three OUTPUT_MISSING scenarios
  (MS_A4, MS_D2, PROCESS_STALL).
- **Why:** with C3 off, 2.1.0 reads the frozen, unscoped link predicate, while
  R-2 without a pacing map answers None.
- **What it is not:** a change to 2.1.1 with all corrections on, where section
  D is identical.

## 5. Phase 4: the 44 scenarios, 2,640 ticks, three ways

**Source:** `dataset_a_three_way.py`, `DATASET_A_THREE_WAY.json` and
`REVISION_DIFFERENCES.csv`.

**Pre-revision against revised.** The cause of each difference is found by
ablation (the revised core with one revision off).

| comparison | differing units | classification |
|---|---|---|
| 2.1.1 + r2 against 2.1.0 + r1 | **204** | **204 EXPECTED_R2, all CERTAINTY_RESTORED** (correct uncertain to correct certain): 123 OUTPUT_MISSING localizations (MS_A4 42, MS_D2 42, PROCESS_STALL 39); 81 attribution ticks (MS_D2 42, PROCESS_STALL 39) |
| 2.1.1 against 2.1.0, frozen profile | **0** | — |

**Revised against frozen v2.0**, with the shadow study's own classifier:

| | 2.1.0 (shadow study) | 2.1.1, frozen profile (re-run here) | 2.1.1 + r2 |
|---|---|---|---|
| ticks differing | 945 | 945 | **344** |
| differing units | 1,275 | 1,275 | **470** |
| CORRECTNESS_FIX | 273 | 273 | 273 |
| CONSERVATIVE_WITHHOLD | 197 | 197 | 197 |
| PROFILE_GAP | 805 | 805 | **0** |
| POSSIBLE_REGRESSION | 0 | 0 | **0** |
| UNKNOWN | 0 | 0 | **0** |

**Two notes on the table:**
- **2.1.1 on the frozen profile reproduces the shadow study's 2.1.0 figures
  exactly.** That is the "0 differences" row above.
- **Label-only ticks rise from 68 to 289.** These are restored localizations
  whose 2.0.0 verdict UNSUPPORTED now reads NO_CONSISTENT_HYPOTHESIS.

**The 805 profile-gap units are all closed:** 601 by r1 (G-1, kept unchanged
in r2) and 204 by R-2 (G-2). What remains against v2.0 is the 273
correctness fixes and the 197 conservative withholds. Each withhold is
explained (`R2_PACING_STARVATION.md` §7).

**Phase 5 and Phase 6** are in `R2_PACING_STARVATION.md` §7:
- PROCESS_STALL and MS_D2 are restored, for the right reason;
- MS_B4 and STALLED_ACTUATOR remain NECESSARY;
- ACTUATOR_NO_RESPONSE, MS_B3 and CLOCK_DRIFT remain ARTIFICIAL (signature
  refuters, out of scope);
- TS_STALLED's onset is unchanged;
- MS_B5 and MS_TS_B5: 0 wrong UNIQUE ticks under every one of 13 variants.

## 6. Phases 9 and 10: the hard gates

**Source:** `governance_gates.py`, `GOVERNANCE_GATES.json`.

| gate | 2.1.0 | 2.1.1 |
|---|---|---|
| XSYS-001 slots | 3,872 | **3,872** |
| decision differences against the sealed run | 0 | **0** |
| scored-outcome differences | 0 | **0** |
| full 2.0-view differences | 0 | **0** |
| primary | 55 / 55, lower bound 0.7616, SUPPORTED | **55 / 55, lower bound 0.7616, SUPPORTED** |
| XSYS hard gate | PASS | **PASS** |
| Phase C headline and six answers | unchanged (base, r1) | **unchanged (base, r2)**: CROSS_DOMAIN_ASSURANCE_FUNCTIONAL; A_STALE_OUTPUT 4 answers, B_ACTUATOR_RESPONSE_BENCH 2 |

**Neither STOP token applies:** SEMANTIC_2_1_XSYS_GOVERNANCE_BLOCK and
SEMANTIC_2_1_PHASE_C_GOVERNANCE_BLOCK are both clear.

## 7. Phase 13: decision quality, not maximum certainty

**Dataset A, 2,640 ticks, graded by `ground_truth.py`.** A UNIQUE is counted
correct only against the tick's attribution truth. MS_B4's UNIQUE in v2.0 is
counted correct here, but the shadow study showed it is luck: MS_B4 and MS_B5
carry identical evidence.

| measure | frozen v2.0 | 2.1.0 | 2.1.0 + r1 | 2.1.1 | **2.1.1 + r2** |
|---|---|---|---|---|---|
| correct UNIQUE | 802 | 524 | 524 | 524 | **605** |
| wrong UNIQUE | 87 | 3 | 3 | 3 | **3** (L16 onset, shared with v2.0) |
| correct SUPPORTED | 2,285 | 1,645 | 2,162 | 1,645 | **2,285** |
| wrong SUPPORTED | 7 | 7 | 7 | 7 | **7** (all shared with v2.0) |
| correct AMBIGUOUS (localization) | 735 | 978 | 858 | 978 | **735** |
| false AMBIGUOUS (localization; the true hypothesis rejected) | 50 | 50 | 50 | 50 | **50** (L16, shared) |
| attribution AMBIGUOUS containing the true domain | 721 | 999 | 999 | 999 | **918** |
| attribution AMBIGUOUS without the true domain | 128 | 212 | 212 | 212 | **212** (incl. the 84 wrong-cause UNIQUE now withheld) |
| NO_CONSISTENT (correct of them) | 457 (285) | 373 (201) | 457 (285) | 373 (201) | **457 (285)** |
| INSUFFICIENT_EVIDENCE | 29 | 29 | 29 | 29 | 29 |
| true hypothesis eliminated | 121 | 121 | 121 | 121 | **121** (L16, shared) |
| false symptoms on unaffected functions | 189 | 0 | 0 | 0 | **0** |
| real symptoms missed | 0 | 481 | 0 | 481 | **0** |
| units with a scope gap (PROFILE gap) | — | 243 | 123 | 243 | **0** |
| ungraded units (no ground truth: the "UNKNOWN" row) | 550 | 550 | 550 | 550 | 550 |
| PREDICATE_FAULT (dataset A has none; dataset D) | — | 168 fault-created SUPPORTED | | | **0** |
| STALE_EVIDENCE (E1, stale symptom ticks) | 9 | 9 | | | **0** |
| PROFILE_ERROR (validator ERROR findings, shipped profiles) | — | 0 | 0 | | **0** (r2 with pacing) |

**Justified certainty, against the two previous baselines:**
- **Against frozen v2.0,** 2.1.1 + r2 keeps every correct SUPPORTED and every
  correct NO_CONSISTENT. It removes 84 wrong UNIQUE and 189 false symptoms.
  It gives up 197 UNIQUE ticks that v2.0 did not justify.
- **Against 2.1.0 + r1,** it adds 81 correct UNIQUE and 123 correct SUPPORTED.
  It adds no wrong answer of any kind.

## 8. Phase 14: does the trace answer the questions?

**Source:** `trace_validation.py`, `TRACE_VALIDATION.json`. Measured by
content on real cases.

| question | measured on | answered |
|---|---|---|
| why was the verdict withheld? | 252 WITHHELD_PREDICATE_FAULT (MS_A1, MS_A2, 6 predicates failed); 281 withheld UNIQUE (dataset A) | **all**: `withheld_because` names the predicate, evaluated id, hypothesis and role; `withheld_unique_because` names the gate |
| which predicate failed, and did it matter? | 1,344 localizations with a fault | **all**: every failed id a hypothesis names has a `fault_impact` entry (1,932 MATERIAL, 840 NOT_MATERIAL, each with why) |
| why is a dependency pacing or not? | 123 OUTPUT_MISSING localizations under r2 | **all**: the pacing input read is named; every other declared dependency is listed DECLARED_DEPENDENCY_NOT_PACING; the result carries the pacing-declaration digest, whose declaration holds the EKF2 source |
| why was the evidence stale, which epoch, which is current? | 269 inadmissible records over E1 and the 14 variants | **all** carry producer, key, evidence epoch, current epoch, reason and action. The transition event appears on the 110 where the context named one; the other 159 are EPOCH_AHEAD, CONTEXT_BEHIND or MALFORMED, where no event exists |
| which alternative remained? | the same withheld cases | **all**: survivors kept on every withheld SUPPORTED; retained hypotheses or unexcluded alternatives on every withheld UNIQUE |

**What the trace still does not answer.** These are shared with 2.1.0, not
introduced:
- **Why a symptom was not raised.** When the only evidence for a symptom is
  made inadmissible (no context, a malformed stamp), the symptom is not
  raised. The tick's admission report names the record, but no localization
  exists to carry a "would have been raised" note.
- **Whether an abstention is necessary or artificial.**

**Size:** median per-tick `to_dict()` 6,278 bytes against 5,955 for 2.1.0
(+5 %); maximum 29,037 against 22,947.

## 9. Phase 15: runtime

**Desktop CPython, one container, not an embedded target.** Dataset A, three
passes, per-tick medians. Source: `RUNTIME_REVISION.json`.

| | mean | median | p95 | p99 | worst |
|---|---|---|---|---|---|
| frozen v2.0 | 209 µs | 191 µs | 442 µs | 522 µs | 796 µs |
| 2.1.0, trace off | 594 µs | 554 µs | 974 µs | 1,143 µs | 1,690 µs |
| 2.1.0, trace on | 668 µs | 596 µs | 1,246 µs | 1,450 µs | 1,896 µs |
| **2.1.1 + r2, trace off** | 660 µs | **626 µs** | 1,115 µs | 1,300 µs | 2,057 µs |
| **2.1.1 + r2, trace on** | 756 µs | **640 µs** | 1,465 µs | 1,722 µs | 2,533 µs |

**Ratios and memory:**
- **Ratios of medians:** 2.1.1 to 2.1.0 is 1.13× (trace off) and 1.07× (trace
  on). 2.1.1 to v2.0 is 3.28× (trace off); 2.1.0 to v2.0 was 2.91× in the same
  run.
- **Memory, the largest tick (68 records), tracemalloc peak:** v2.0 5.6 KB;
  2.1.0 24.0 KB; 2.1.1 26.1 KB.

| what was checked | result |
|---|---|
| retained state | **none**: the core's attributes are identical before and after 3 × 2,640 ticks; admission keeps no history |
| record scaling (largest tick padded to 2,176 records) | log-log slope 1.09 (2.1.1, trace off), 1.19 (trace on), 1.12 (2.1.0), 1.37 (v2.0). No new superlinear term |
| epoch admission cost against stamped records | linear: slope 1.03 (all current) and 1.06 (all stale). About 2.3 µs per stamped record to check, and about 9 µs more per record made UNAVAILABLE (a dataclass copy). No per-transition scan, because there is no history to scan |
| fault-policy cost | median 0.99× with R-1 on against off, on dataset A with one predicate failed |
| large allocations | the only new allocation is the copied UNAVAILABLE record, one per inadmissible record |

**Flagged for a port, not as a problem here.** Making a record UNAVAILABLE by
copying it is the dominant admission cost. In C it is a flag set in place
(`C_RUNTIME_DELTA_UPDATE.md`).

## 10. Disclosures

**Harness errors caught and corrected before any number was reported:**
- **`epoch_adversarial.py` first matched inadmissible records to records by
  key and position.** In LATE_OLD_EPOCH that charged the valid record for the
  dropped late one: it showed 3 stale and 3 withheld where there were none.
  It now matches by key and producer.
- **`worse_answer_revision.py` first compared the whole 2.0 view for order
  dependence.** It counted 464 changes, all of them the order in which frozen
  `attribute()` lists a candidate's relations, and 459 such cases occur in
  2.1.0 too. It now compares decisions canonically and reports
  presentation-only differences separately.

**No revision code changed after any phase's results were seen.** One
property of the E1 no-context run (fail-closed) was recorded as a finding,
not designed away.

**Truncation.** The brief arrived truncated part-way through Phase 18. This
package follows Phases 0-18 as written. Its deliverables, its 16-criterion
review and its decision tokens follow the shadow-validation brief's structure
(`PROMOTION_REVIEW.md`).
