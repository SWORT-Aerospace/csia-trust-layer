# CURRENT PROGRAM STATE

```
CURRENT PRIORITY
----------------
DUAL PAPER FINALIZATION

ENGINEERING
-----------
FROZEN AT V2 PHASE C

SYSTEMS PAPER
-------------
FINALIZATION

MATHEMATICAL PAPER
------------------
FINALIZATION

FORGE
-----
DOCUMENTATION / PRIOR ART ONLY

HARDWARE
--------
NOT CURRENT GATE

NEXT PRODUCT PHASE
------------------
LOCKED UNTIL BOTH PAPER SUBMISSION-CANDIDATE TAGS EXIST
```

## Canonical tags and commits

| tag | commit | what it fixes |
|---|---|---|
| `csia-v1.0-research-final` | `ec5acd189295dab9259d4989657d42184d6142a3` | the v1 diagnostic core. **Zero diff**, enforced twice (git diff against the tag, and SHA-256 of every file) |
| `csia-v2-phasec-frozen` | `50c5d3576e9084e7c2789167628392c5de992b6f` | the v2 Phase C engineering state; artifact hashes recorded in `engineering/v2/V2_PHASEC_FREEZE.md` |
| `csia-dual-paper-evidence-freeze` | `eb2577d6830208b26d33facb283aa5be0ddf7c86` | the **scientific** state at paper finalization: algorithms, thresholds, scenarios, generated artifacts, headline results, proof outputs and claim state, immediately before the repository presentation cleanup |
| `v0.7.0`, `archive/handoff-source-of-record` | — | historical |

The two freezes answer different questions. `csia-v2-phasec-frozen` fixes what
the *software* does. `csia-dual-paper-evidence-freeze` fixes what the *papers
say*, and is the tag to cite. Anything after it that changes a number is a
defect, not a result.

**All three freeze tags are LOCAL ONLY.** Pushing them is refused by GitHub with
HTTP 403 — this session's credential may push the working branch but may not
create refs. The commits are all present on the remote branch, so nothing is
lost; only the tag refs are missing. Someone with tag-creation rights runs:

```sh
git push origin refs/tags/csia-v1.0-research-final
git push origin refs/tags/csia-v2-phasec-frozen
git push origin refs/tags/csia-dual-paper-evidence-freeze
```

Until then the commit SHAs above are the durable record. A tag can be moved; a
SHA cannot, which is why both are written here and why
`tests/test_program_state.py` asserts both.

## Test status

1683 tests collected, all passing. Guards that hold the freezes:

| guard | command |
|---|---|
| v1 core zero diff | `pytest tests/test_v1_frozen.py` |
| Phase C artifact hashes | `pytest tests/test_phase_c_freeze.py` |
| proof artifact reproduces from its script | `make proof-audit-check` |
| every blocking publication guard | `make check-blocking` |

## Known publication blockers

| # | blocker | affects | who can clear it |
|---|---|---|---|
| 1 | **bibliography verification.** 52 unresolved provenance markers; no entry verified. Six routes tested, all denied at the proxy: `api.crossref.org`, `doi.org`, `dblp.org`, `api.openalex.org`, `api.semanticscholar.org`, `export.arxiv.org` | both papers | a human with publisher access |
| 2 | **public-log study not run.** `review.px4.io` and `logs.px4.io` denied by egress policy. Plan committed; claim `SC-22` is `PROVISIONAL` | systems paper | a host with egress |
| 3 | **one prior-art reference not located** (`NOT_FOUND_NEEDS_HUMAN`); no sharpness may be claimed for the TV bound until closed | math paper | a human with library access |
| 4 | **one high-priority reference unread** (arXiv:2405.15141) | math paper | a human with access |

None is a research problem. All four need an outside source.

## Known technical limitations

| limitation | where it is stated |
|---|---|
| the mathematical paper's baseline `q` is a counterfactual and, in the measured case, not evaluable at all | manuscript Remark, `FORMAL_CORE.md` §1.1 |
| no MAP-stability result exists for the pinned regime, and P8 proves there cannot be one of P4's form | `FORMAL_CORE.md` §9a |
| the implemented instance is **n = 1**: one deployed layer, prevalence not established | systems paper §Limitations |
| Mechanism A has no current-stack replication (`SC-23`, `PROVISIONAL`); the 4.8 result is a negative control, not a replication | `docs/CURRENT_PROGRAM_STATE.md` §3, gate 2b/6b |
| the checker's 378,000 agreements validate the *reading*, not the signature table | math paper §9 |
| reported scalars are model states, not calibrated probabilities | both papers §Limitations |
| the private username remains reachable in git history at `ac8d21d` / `bc3ed97`; purged at HEAD. Removing it needs a history rewrite that would invalidate every tag above | `docs/REPOSITORY_FINALIZATION_PRECHECK.md` |

**Any agent starting work in this repository reads this file first.** It is
discoverable from the repository alone and does not depend on chat history. If
another document disagrees with this one about what is authorised, this one
governs.

`RESEARCH_STATE.md` remains authoritative for *what is scientifically
established*. This file is authoritative for *what may be worked on*.

**Evaluating rather than developing?** Run
`python engineering/v2/quickstart.py` and read
`docs/product/CSIA_READINESS.md`. The short version: maturity **M2**,
simulation/research prototype, **not flight software**, and neither paper is
blocked by anything in the code.

---

## 1. What may be worked on

| | |
|---|---|
| **allowed** | anything that advances Systems Paper I or the mathematical paper toward submission-candidate state |
| **allowed** | documentation of future architecture (`docs/`, `forge/*.md`) |
| **allowed** | prior-art reduction |
| **allowed** | fixing a defect in what already exists, if it does not change frozen behaviour |
| **FORBIDDEN** | estimator domain, energy domain, thermal domain, security domain, firmware domain, storage domain |
| **FORBIDDEN** | Forge production code of any kind |
| **FORBIDDEN** | automatic reconfiguration, recovery planner |
| **FORBIDDEN** | ZETH integration, CSIA Edge |
| **FORBIDDEN** | new UAV features |

The freeze lifts when **both** tags exist: `systems-paper-submission-candidate`
and `math-paper-submission-candidate`. Not one. Both.

### 1a. Owner-authorized narrow exceptions

Recorded here as pointers. **Neither rewrites the table above, and the table
above governs where they disagree.** Each is a scoped permission on a research
branch, not a lifting of the freeze.

| exception | scope | state | record |
|---|---|---|---|
| energy-domain Active Evidence Acquisition | **simulator only**; no hardware operation | in force | `research/active_evidence/realized_current/OWNER_AUTHORIZATION.md` |
| E2M sensor-bus bench | unarmed, non-flight, low-voltage I²C bench: TCA9548A, low-power sensors, Arduino-class controller, USB host | **`AUTHORIZED_NOT_RUN`** — permission granted 2026-09-16, all four gates still open | `research/bus_provenance/OWNER_DECISION_E2M_2026-09-16.md`, gates in `E2M_GATE_STATUS.md` |
| cross-system research on v2 | research-only work **outside** the frozen v1/v2 implementation: post-hoc latency analysis, twin-run analysis, SITL experiment **design**, adapters that read frozen outputs. No frozen behaviour, threshold, certificate semantics or sealed artifact may change | **in force for documents and post-hoc analysis** — granted 2026-09-26; SITL execution held for owner review | `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md` |

The E2M exception moves exactly one boundary — sensor-bus preparation and
narrowly scoped bench operation. It does not authorize motors, propellers,
ESCs, servos, flight batteries, autopilot or MAVLink commands, actuator
control, armed aircraft, flight testing, or hardware access from inside
`csia_bus_provenance`. **HARDWARE — NOT CURRENT GATE still reads as written
above** for everything outside that one bench.

## 2. Frozen points

| what | at | enforced by |
|---|---|---|
| CSIA v1 | `csia-v1.0-research-final` @ `ec5acd189295dab9259d4989657d42184d6142a3` — **zero diff** | `tests/test_v1_frozen.py` (git diff + SHA-256) |
| CSIA v1.1 | output schema `1.1.0`, unchanged | schema + golden corpus |
| CSIA v2 Phase C | `50c5d3576e9084e7c2789167628392c5de992b6f`, annotated tag `csia-v2-phasec-frozen` (**local only; remote tag push refused, see above**) | `engineering/v2/V2_PHASEC_FREEZE.md`, now **enforced** by `tests/test_phase_c_freeze.py`: the 8 reproducible artifact hashes, the recorded commit, and the record's headline verdict against the gate artifact |
| Systems Paper I baseline | `main @ 848f556` | `tools/publication/phase_guard.py` |

## 3. Submission gate — SYSTEMS PAPER

| # | gate | status |
|---|---|---|
| 1 | all claims traceable | **PASS** — `research/systems-paper/CLAIMS.csv`, 26 rows, no empty field; `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` binds every figure, table and headline scalar |
| 2 | source versions exact | **PASS** — Phase-I at `848f556` / ArduCopter 3.3 SITL; new artifacts record their own commit and are marked NOT Phase-I |
| 2b | current-stack replication | **PASS for Mechanism B** — preregistered campaign `research/v1_1/CURRENT_STACK_REPLICATION.md`: ArduPilot 4.8 `REPLICATED` (20/20, 0-tick crossing error), PX4 SIH `INAPPLICABLE` with the reason recorded. **Mechanism A has no current-stack replication** (`SC-23`, `PROVISIONAL`) |
| 3 | all figures regenerated | **PASS** — `make figures` |
| 4 | all tables regenerated | **PASS** |
| 5 | real-log study reproducible | **BLOCKED** — not run. `review.px4.io`, `logs.px4.io` denied by egress policy (403). Plan committed: `research/systems-paper/PUBLIC_LOG_STUDY_PLAN.md`. Claim `SC-22` is `PROVISIONAL` |
| 6 | independent checker agrees | **PASS** — 378,000 / 378,000, 0 real disagreements, 0 degenerate cases. `research/systems-paper/results/checker_agreement.json` |
| 6b | predicate tested on current-stack data | **PASS as a negative control** — 15,595 real ArduPilot 4.8 ticks, 0 collapses, on fix-preserving trials where a collapse would have falsified the account (`SC-26`). NOT a self-occlusion replication |
| 7 | bibliography verified | **BLOCKED** — 11 of 11 entries unverified, 37 markers. `api.crossref.org`, `doi.org`, `dblp.org` all denied. `make bib-guard` fails, correctly. A marker can no longer be silently deleted to make it pass: `papers/BIB_VERIFICATION_LEDGER.yaml` + `tests/test_bib_verification_ledger.py` |
| 8 | no unresolved TODO citation | **BLOCKED** — same as 7 |
| 9 | reviewer red team answered | **PASS** — 4 reviewers, 11 objections: **7 answered, 1 CLOSED by correction** (2.3, the CUSUM-vs-trust comparison — the objection was right, the dwell decomposition was computed, and the conclusion survived), **3 that cannot be answered from here and are now stated in the manuscript itself** rather than only in the red-team file |
| 10 | PDF builds clean | **PASS** — `make paper-systems` |

**SYSTEMS PAPER: BLOCKED.** Blockers: gate 7/8 (bibliography — needs a human
with publisher access) and gate 5 (public-log study — needs a host with egress
to `review.px4.io`). Neither is a research problem.

## 4. Submission gate — MATHEMATICAL PAPER

| # | gate | status |
|---|---|---|
| 1 | all propositions proven | **PASS** — P1–P8, C2, C3 in `research/math-paper/FORMAL_CORE.md`; symbolic (sympy, n=4) and numeric (20 000 instances) in `research/math-paper/results/proof_audit.json`. P7/P7b/P7c and P8 were added by the red team pass and are numeric-only |
| 2 | all counterexamples checked | **PASS** — `FORMAL_CORE.md` §11; P4's 6,877 audited instances where the argmax moved with the condition violated |
| 3 | prior-art matrix complete | **COVERAGE COMPLETE, VERIFICATION BLOCKED** — 18 rows over all **10** topics the brief requires at minimum, asserted by `tests/test_math_paper_proofs.py`. Every row is still `WEB_SEARCH_ONLY`; one is `NOT_FOUND_NEEDS_HUMAN` and one is `NOT_READ_HIGH_PRIORITY` (arXiv:2405.15141, *Likelihood distortion and Bayesian local robustness* — the title alone makes it the most important unread reference in the matrix) |
| 4 | novelty language audited | **PASS** — `research/math-paper/NOVELTY_AUDIT.md`; every proposition labelled **KNOWN**; forbidden phrases enforced by test |
| 5 | notation internally consistent | **PASS** — one symbol table in `FORMAL_CORE.md` §1 |
| 6 | proof reviewer simulation complete | **PASS, and it found something** — `research/math-paper/REVIEWER_RED_TEAM_MATH.md`, 4 reviewers, 11 objections. **One defect found that would have been fatal in review**: §2's baseline definition made Propositions 1, 2, 5 and 6 vacuous for the paper's own worked example. Fixed with a new section, a new proposition (gated score) and a rewritten abstract. **One negative result about the paper's own P4** (P8: the MAP condition provably cannot certify a pinned pair). **One of our own supporting claims withdrawn** (`FORMAL_CORE.md` §4's "`w_a = w_b` by construction"). 6 open items listed and not closed |
| 7 | PDF builds clean | **PASS** — `make paper-math` builds a 10-page manuscript with **every citation resolved**. The scaffold is gone; `OI-M2` is CLOSED |
| 8 | bibliography verified | **BLOCKED (NEW)** — the manuscript cites 6 entries, all unverified, and the coarsening-at-random reference that makes Proposition 5 KNOWN is RECONSTRUCTED from search alone. `OI-M4` |

**MATHEMATICAL PAPER: BLOCKED.** Blocker: gate 8 — the bibliography. Gate 7 is
now PASS: the manuscript exists and builds clean.

**This is a net improvement that LOOKS like a new blocker, and it is worth
being explicit about why.** The scaffold cited nothing, so `make bib-guard`
passed trivially. A manuscript that labels every proposition KNOWN and cites
nothing would be claiming novelty by omission, so citations were added — and
they are unverifiable from here, exactly as the systems paper's are. The paper
went from *no manuscript* to *a manuscript with an honest, reported
bibliography blocker*.

## 5. Tags — DO NOT CREATE EARLY

| tag | create when | exists |
|---|---|---|
| `csia-v2-phasec-frozen` | now, **local only, push requires authorization** | **created locally, not pushed** |
| `systems-paper-submission-candidate` | every §3 gate PASS | no |
| `math-paper-submission-candidate` | every §4 gate PASS | no |

## 6. Result-recording rule

**No result may live only inside a chat transcript.** Every new result records:

| field | where |
|---|---|
| commit SHA | in the artifact's own header (`"commit"` field) |
| artifact SHA-256 | printed by the generating script; freeze records carry them |
| date | the commit date |
| claim impact | a row in `research/systems-paper/CLAIMS.csv` or `docs/math/PROOF_STATUS.md` or `research/math-paper/PRIOR_ART_MATRIX.csv` |
| every headline number it puts into prose | a row in `research/PROSE_NUMERIC_BINDINGS.yaml`, enforced by `tests/test_prose_numeric_bindings.py` |
| every bibliography entry, verified or not | a row in `papers/BIB_VERIFICATION_LEDGER.yaml`, enforced by `tests/test_bib_verification_ledger.py` |

## 7. Results added since the Phase C freeze

| artifact | commit | claim impact |
|---|---|---|
| `research/systems-paper/results/active_sets.json` | this commit | input to `SC-03`–`SC-06` |
| `research/systems-paper/results/checker_verdicts.json` | this commit | `SC-04`, `SC-05`, `SC-06` — new |
| `research/systems-paper/results/checker_agreement.json` | this commit | `SC-03` — new, **PROVED**, satisfies systems gate 6 |
| `research/systems-paper/results/mechanism_b.json` | this commit | `SC-07`–`SC-09` — new |
| `research/math-paper/results/proof_audit.json` | this commit | `SC-02` **PROVED**; math gates 1 and 2 |
| `research/math-paper/PRIOR_ART_MATRIX.csv` | this commit | **narrows C2 to KNOWN**; opens `NOT_FOUND_NEEDS_HUMAN` |
| `papers/csia_systems/BIB_VERIFICATION_CANDIDATES.md` | this commit | finds `kang2024gnss` is probably filed under the wrong subject |
| `research/systems-paper/CURRENT_STACK_BLOCKERS.md` | this commit | **corrects an earlier draft of itself**: Mechanism B IS replicated on ArduPilot 4.8. New rows `SC-24` (REPLICATED) and `SC-25` (PX4 INAPPLICABLE) |
| `research/systems-paper/results/current_stack_structural.json` | this commit | `SC-26` — new. 15,595 real ArduPilot 4.8 ticks, 0 collapses |
| `papers/gate_conditioning/main.tex` | this commit | **math gate 7 BLOCKED → PASS.** The manuscript exists |
| `papers/gate_conditioning/refs.bib` | this commit | **opens math gate 8**: 6 entries, all unverified |

## 7b. What can no longer be defeated by deletion

Three failure modes were reachable by editing one file and are now not. Each
guard was verified by breaking it and confirming the break is caught.

| the shortcut | what stops it |
|---|---|
| delete a bibliography marker to make `bib-guard` pass | `tests/test_bib_verification_ledger.py` — an entry with no marker must have a `VERIFIED` ledger row naming an **accepted route**, a checker and a date. `WEB_SEARCH` is a named `rejected_route`, so claiming it is a visible act |
| regenerate a frozen Phase C artifact | `tests/test_phase_c_freeze.py` — the 8 reproducible hashes in the freeze record must still match, and the exclusion for the one wall-clock artifact is asserted by name so it cannot be widened |
| let prose drift from the artifact it quotes | `tests/test_prose_numeric_bindings.py` — 25 numbers bound to an artifact and a JSON pointer, checked in both directions |

None of these can tell whether a human who wrote `VERIFIED` actually read the
publisher record. Nothing can. What they do is force the falsification to be
**written down** rather than performed by deletion.

## 8. Known blockers nobody in this environment can clear

| blocker | needs |
|---|---|
| bibliography verification | a host with access to `api.crossref.org` or a publisher, plus a human to read each diff |
| public PX4 log study | a host with access to `review.px4.io` |
| the gate-conditioning manuscript | **CLEARED.** It exists and builds clean |
| the gate-conditioning bibliography | a host with publisher access; the coarsening-at-random entry is the critical one |
| PX4 Mechanism B replication | **not a blocker: recorded INAPPLICABLE.** No fix-preserving GNSS offset exists on PX4 SIH; four source routes checked; substitution is forbidden by the preregistration |
| Mechanism A current-stack replication | an ArduPilot/PX4 SITL environment; `SC-23` is PROVISIONAL |
| EAR/ITAR classification (`ECCN_PENDING`) | counsel |

## 9. Conventions that must not be broken

1. **Negative results are permanent.** Withdrawn claims, defective-run
   artifacts and refuted theorem records stay committed.
2. **A Phase-I number may not move.** Re-freezing is explicit and recorded.
3. **No citation is invented to make a guard pass.** A web search result is
   not a publisher record.
4. **Test counts in prose are scoped or derived**
   (`tests/test_doc_counts.py`).
5. **Production behaviour is not changed by a hygiene pass.**
6. **Do not modify frozen historical evidence to make a paper cleaner.**
