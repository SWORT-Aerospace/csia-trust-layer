# CURRENT PROGRAM STATE

```
CURRENT PRIORITY:
DUAL PAPER COMPLETION

PRODUCT DEVELOPMENT:
FROZEN AT V2 PHASE C

FORGE:
DOCUMENTATION / PRIOR ART ONLY

HARDWARE:
NOT CURRENT GATE
```

**Any agent starting work in this repository reads this file first.** It is
discoverable from the repository alone and does not depend on chat history. If
another document disagrees with this one about what is authorised, this one
governs.

`RESEARCH_STATE.md` remains authoritative for *what is scientifically
established*. This file is authoritative for *what may be worked on*.

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

## 2. Frozen points

| what | at | enforced by |
|---|---|---|
| CSIA v1 | `csia-v1.0-research-final` @ `ec5acd189295dab9259d4989657d42184d6142a3` — **zero diff** | `tests/test_v1_frozen.py` (git diff + SHA-256) |
| CSIA v1.1 | output schema `1.1.0`, unchanged | schema + golden corpus |
| CSIA v2 Phase C | `50c5d3576e9084e7c2789167628392c5de992b6f`, local tag proposal `csia-v2-phasec-frozen` (**not pushed**) | `engineering/v2/V2_PHASEC_FREEZE.md` |
| Systems Paper I baseline | `main @ 848f556` | `tools/publication/phase_guard.py` |

## 3. Submission gate — SYSTEMS PAPER

| # | gate | status |
|---|---|---|
| 1 | all claims traceable | **PASS** — `research/systems-paper/CLAIMS.csv`, 25 rows, no empty field; `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` binds every figure, table and headline scalar |
| 2 | source versions exact | **PASS** — Phase-I at `848f556` / ArduCopter 3.3 SITL; new artifacts record their own commit and are marked NOT Phase-I |
| 2b | current-stack replication | **PASS for Mechanism B** — preregistered campaign `research/v1_1/CURRENT_STACK_REPLICATION.md`: ArduPilot 4.8 `REPLICATED` (20/20, 0-tick crossing error), PX4 SIH `INAPPLICABLE` with the reason recorded. **Mechanism A has no current-stack replication** (`SC-23`, `PROVISIONAL`) |
| 3 | all figures regenerated | **PASS** — `make figures` |
| 4 | all tables regenerated | **PASS** |
| 5 | real-log study reproducible | **BLOCKED** — not run. `review.px4.io`, `logs.px4.io` denied by egress policy (403). Plan committed: `research/systems-paper/PUBLIC_LOG_STUDY_PLAN.md`. Claim `SC-22` is `PROVISIONAL` |
| 6 | independent checker agrees | **PASS** — 378,000 / 378,000, 0 real disagreements, 0 degenerate cases. `research/systems-paper/results/checker_agreement.json` |
| 7 | bibliography verified | **BLOCKED** — 11 of 11 entries unverified, 37 markers. `api.crossref.org`, `doi.org`, `dblp.org` all denied. `make bib-guard` fails, correctly |
| 8 | no unresolved TODO citation | **BLOCKED** — same as 7 |
| 9 | reviewer red team answered | **PASS** — `research/systems-paper/REVIEWER_RED_TEAM.md`, 4 reviewers, 11 objections, 4 recorded as **not adequately answered** |
| 10 | PDF builds clean | **PASS** — `make paper-systems` |

**SYSTEMS PAPER: BLOCKED.** Blockers: gate 7/8 (bibliography — needs a human
with publisher access) and gate 5 (public-log study — needs a host with egress
to `review.px4.io`). Neither is a research problem.

## 4. Submission gate — MATHEMATICAL PAPER

| # | gate | status |
|---|---|---|
| 1 | all propositions proven | **PASS** — P1–P6, C2, C3 in `research/math-paper/FORMAL_CORE.md`; symbolic (sympy, n=4) and numeric (20 000 instances) in `results/proof_audit.json` |
| 2 | all counterexamples checked | **PASS** — `FORMAL_CORE.md` §11; P4's 6,877 audited instances where the argmax moved with the condition violated |
| 3 | prior-art matrix complete | **PARTIAL** — `research/math-paper/PRIOR_ART_MATRIX.csv`, 12 rows. Every row is `WEB_SEARCH_ONLY`; one row is `NOT_FOUND_NEEDS_HUMAN` |
| 4 | novelty language audited | **PASS** — `research/math-paper/NOVELTY_AUDIT.md`; every proposition labelled **KNOWN**; forbidden phrases enforced by test |
| 5 | notation internally consistent | **PASS** — one symbol table in `FORMAL_CORE.md` §1 |
| 6 | proof reviewer simulation complete | **PASS** — `REVIEWER_RED_TEAM.md` Reviewer 3 (statistical) and Reviewer 4 (hostile on novelty) |
| 7 | PDF builds clean | **PASS for the scaffold. THE MANUSCRIPT DOES NOT EXIST** — `papers/gate_conditioning/main.tex` is a build scaffold and says so |

**MATHEMATICAL PAPER: BLOCKED.** Blockers: gate 7 (no manuscript;
`GATE_PAPER_ARTIFACT_MAP.yaml` `OI-M2`) and gate 3 (prior art unverifiable
from here).

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

## 8. Known blockers nobody in this environment can clear

| blocker | needs |
|---|---|
| bibliography verification | a host with access to `api.crossref.org` or a publisher, plus a human to read each diff |
| public PX4 log study | a host with access to `review.px4.io` |
| the gate-conditioning manuscript | a manuscript author |
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
