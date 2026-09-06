# P4–P7 status audit — measured by running the tests, not by looking at files

**Why this file exists.** `handoff/PROGRAM_STATUS_REPORT.md` §1 records P4, P6
and P7 as **DONE** and P5 as **PROTOCOL + SIMULATED BACKEND**. Those entries
were written from what had been built. A file existing is not evidence that it
works, so each part was re-audited by **executing its tests**, at HEAD
`100001d`, on 2026-09-06.

**Verdict vocabulary, fixed before running:**

| | |
|---|---|
| **PASS** | every test of the part runs and passes, and the tests exercise the thing the part claims to do |
| **PARTIAL** | the tests pass, but they do not reach some part of what is claimed — and the gap is named |
| **NOT_DONE** | the part does not exist, or its tests do not run |

A part whose tests pass but which was never exercised against the thing it
claims is **PARTIAL**, not PASS. "The tests are green" and "the part works" are
different statements.

---

## Summary

| part | claimed in the status report | **audited** |
|---|---|---|
| **P4** orchestrator + validity predicates | DONE | **PASS** |
| **P5** fault injector | PROTOCOL + SIMULATED BACKEND, no firmware | **PARTIAL — by design, and the design is the point** |
| **P6** end-to-end dry run + invalid-trial matrix | DONE | **PASS** |
| **P7** preregistration | DONE and frozen | **PASS** |

Nothing was found to be NOT_DONE. **P5's PARTIAL is not a regression against
the status report** — that report already said "no firmware"; this audit
confirms it by execution and says exactly what the simulated backend does and
does not license.

---

## P4 — campaign orchestrator and validity predicates · **PASS**

| | |
|---|---|
| tests run | `tests/test_experiment_orchestrator.py` — **29 passed** |
| | `tests/test_invalidity_masking.py` — **14 passed** |
| | `tests/test_campaign_tick_rate.py` — **3 passed** |
| source | `tools/csia_experiment/orchestrator.py`, `validity.py`, `manifest.py` |

**What the tests actually exercise, not just that they are green:**

* the **eight-state vocabulary** — `VALID`, `INVALID_SCENARIO`,
  `INSTRUMENT_DEAD`, `ABORTED_BY_OPERATOR`, `HARDWARE_FAULT`,
  `TIMING_INSUFFICIENT`, `PREREG_VIOLATION`, `NOT_ATTEMPTED`;
* the **arithmetic identity** `planned = valid + invalid + not_attempted`, and
  that a report which does not balance **raises** rather than reporting a
  smaller denominator;
* **RULE A** — a null control that moves invalidates *every* arm of the
  campaign, not just the trial it appeared in;
* content-hashed manifests that refuse to load after an edit.

**Exercised for real, not only in tests.** P4 drove Campaign A1 (40 trials) and
Campaign A2 (40 trials), both of which balanced: `planned 40 | attempted 40 |
valid 40 | invalid 0 | not_attempted 0`.

## P5 — fault injector · **PARTIAL, by design**

| | |
|---|---|
| tests run | `tests/test_fault_injector.py` — **12 passed** |
| source | `tools/csia_experiment/fault_injector.py` |

**What PASSES:** the **wire protocol** and the **simulated backend**. Command
framing, readback confirmation, and the rule that a readback not equal to the
written value is `INVALID_SCENARIO` and never a detector miss — the rule that
caught the PX4 `INT32`/`REAL32` trap, where `SIM_GPS_USED` sent as `REAL32`
landed as `1.401298464324817e-44` while the write reported success.

**Why PARTIAL:** `SerialInjector` — the real one — **refuses to construct**.
There is no board. It raises rather than returning plausible values.

**That refusal is the correct behaviour and the reason this is PARTIAL rather
than a problem.** A stub returning nominal values would produce E2 and E3
numbers out of nothing, indistinguishable downstream from measurements. The
part is complete up to the hardware boundary and stops there deliberately.

**What P5 therefore does not license:** anything at evidence tier E2 or above.
`COMMAND ISSUED ≠ FAULT INJECTED` is enforced against a **simulated** backend
only; it has never been enforced against a physical one.

## P6 — end-to-end dry run and the invalid-trial matrix · **PASS**

| | |
|---|---|
| tests run | `tests/test_invalid_trial_matrix.py` — **26 passed** |
| source | `tools/csia_experiment/invalid_trial_matrix.py` |

**The number the programme asked for: 12 of 12 causes correctly classified,
with NO MANUAL ADJUDICATION.** Asserted by
`test_the_matrix_reports_its_own_score`, which recomputes it rather than
restating it.

Ten of the twelve are detected from the trial record alone. Two are caught
**earlier** than adjudication and are demonstrated against the component that
catches them — `ARTIFACT_TAMPER` by the manifest content hash at load, and
`PROFILE_DEPLOYMENT_CONFLICT` by `csia-edge validate` exiting 3. Those two are
**stronger** for being caught early: a tampered manifest never reaches the
adjudicator.

**Two controls that make the 12/12 mean something:**

* `test_a_clean_record_triggers_no_cause_and_is_valid` — without it, a detector
  that fired on everything would pass all twelve;
* `test_every_cause_is_undecidable_when_the_record_is_silent` — a bare record
  must return **UNDECIDABLE**, never `False`. Without this, a trial with no
  instrumentation at all would read as clean.

**Twelve causes map onto eight states** — a state is what a trial *is*, a cause
is what went wrong — so the counts differ by design, not by an error.

## P7 — preregistration · **PASS**

| | |
|---|---|
| audited by | git object identity, not by reading the documents |

| preregistration | frozen at | before |
|---|---|---|
| `MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md` (A1) | earlier session | the first A1 trial |
| `MECHANISM_A_ARDUPILOT_TRUST_COMPLETION_PREREG.md` (A2) | commit `ceeaf4a`, blob `2237b156e38294f68e2350e051e9846c9a3965a9` | the first A2 trial |
| `MECHANISM_A_PX4_REPEATED_PREREG.md` (P1) | commit `1968ffd` | the campaign, which is `NOT_RUN` |

Each was committed **before** the trials it governs, which is checkable from
git rather than from a claim in the document.

**And each is byte-identical to its freeze commit**, which is now a test:
`tests/test_prereg_freeze.py` compares the blob at HEAD against the blob at the
named commit, so a later edit fails loudly and names the file. That test states
its own limit rather than implying more: it proves the document has not
changed, **not** that the freeze commit predates the first trial in wall-clock
terms. The ordering is established by the campaign directories' own history.

| preregistration | blob |
|---|---|
| A2 | `2237b156e38294f68e2350e051e9846c9a3965a9` at `ceeaf4a` and at HEAD |
| P1 | `ca445079f9f0c68306c26701dff41c7c105c63cf` at `1968ffd` and at HEAD | The A2 preregistration in
particular fixes its four analysis windows — `PRE` [10,12), `AT` [12,13),
`POST` [14,20), `LATE` [20,end] — and states in §6 that success is **NOT**
"trust must rise". Both mattered: the campaign's headline result is that the
control arm rises about three times more than the fault arm, and a window moved
after seeing the traces would have made that adjustable.

**A1 is sealed and was not touched.**
`campaigns/physical_validation/mechanism_a_repeat_ap/_CAMPAIGN_A1.yaml` records
`TRUST_TRAJECTORY: NOT_CAPTURED` with `trust_trajectory_is_not: [FAIL, ZERO,
UNCHANGED, INCONCLUSIVE]`. A2 is a separate campaign with its own directory,
manifests and preregistration; nothing was re-run into A1, amended, or
regenerated in place.

---

## What this audit does not establish

* **Not that the parts are correct** — that their tests pass and exercise what
  they claim. A test suite written by the same agent that wrote the code is a
  self-assessment; C-2 in `USER_ACTION_REQUIRED.md` asks for independent
  replication for exactly this reason.
* **Nothing about hardware.** P5's PARTIAL is the visible edge of that: every
  part above is complete up to the point where a physical board would be
  required, and stops.
* **Not a coverage claim.** These are the tests belonging to each part, not all
  tests that touch it.
