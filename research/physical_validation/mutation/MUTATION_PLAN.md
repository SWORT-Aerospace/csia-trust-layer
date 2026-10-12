# Mutation plan — does the test suite notice when the science changes?

**Program:** CSIA paper evidence extension — physical validation, P11.
**Runner:** `tools/mutation/run_mutations.py`
**Target:** `make verify-paper-mutations`
**Results:** `research/physical_validation/mutation/MUTATION_RESULTS.json`
**Survivors:** `research/physical_validation/mutation/MUTATION_SURVIVORS.md`

---

## 1. The question

A green test suite proves the tests pass. It does not prove they would notice
if a diagnostic decision changed. Every claim in both manuscripts rests on the
second property, and nothing in this repository had measured it.

Mutation testing asks it directly: **break one diagnostic decision on purpose,
and see whether anything fails.**

**A survivor is the interesting result.** It means a line of the scientific
core can be changed without a single test objecting, which means no claim in
either manuscript is pinned to that line. That is a finding about the
**evidence**, not a bug to be patched by adding a test that happens to catch
that particular mutant.

## 2. What is deliberately NOT the goal

* **Not a coverage percentage.** A mutation score is a number that invites
  being improved, and the way to improve it cheaply is to write tests aimed at
  the mutants. That would raise the score and establish nothing.
* **Not a reason to change the core.** No mutant is a proposed edit. The core
  is frozen and stays frozen; the sandbox exists so that mutating it cannot
  touch the repository.
* **Not a claim about the whole suite.** The selection (§5) is the diagnostic
  subset. A survivor means "nothing in the science tests noticed", not
  "nothing in 1787 tests noticed".

## 3. Two passes, and why the second one is the real measurement

The first campaign reported 23 of 24 mutants killed. Eleven of those were
killed by exactly one test:
`test_v1_frozen.py::test_diagnostic_core_is_unchanged_since_the_freeze`, which
diffs the frozen core against its tag.

**That test would fire identically on a reformatted comment.** A mutant it
kills has not been shown to change any observable behaviour. Reporting those
eleven as "killed" would overstate what the suite establishes about the
science, so the campaign runs twice:

| pass | integrity guards | answers |
|---|---|---|
| 1 | included | *would this change reach a commit?* Reassuring, and about process |
| 2 | deselected | *does any test assert the behaviour this line produces?* This is the one the papers depend on |

A mutant that pass 1 kills and pass 2 does not is recorded as
**`KILLED_BY_INTEGRITY_ONLY`** and counted as a survivor for the purpose of
"what do the tests establish". The guards deselected in pass 2 are listed in
the results file, not chosen at read time.

## 4. Verdict vocabulary

| verdict | meaning | who decides |
|---|---|---|
| `KILLED` | a behavioural test failed with integrity guards deselected | the runner |
| `KILLED_BY_INTEGRITY_ONLY` | only a file-hash or tag diff objected. The change cannot reach a commit; no test asserts the behaviour | the runner |
| `SURVIVED` | no test failed at all | the runner |
| `INVALID_MUTANT` | the mutated program does not run — collection error, or a pytest usage exit. Says nothing about the suite | the runner |
| `EQUIVALENT` | the mutant computes the same function as the original, so no test *could* kill it | **the author**, argued in §7 |
| `OUT_OF_SCOPE` | the mutated line is outside the science under test | **the author**, argued in §7 |

`EQUIVALENT` and `OUT_OF_SCOPE` are never inferred by the script. A program
cannot decide that two programs compute the same function, and letting it
guess is how a survivor gets explained away instead of recorded.

## 5. Test selection

Recorded in every results file so a `SURVIVED` verdict can be read against
what it was measured against.

```
tests/test_diagnosis.py            tests/test_v1_frozen.py
tests/test_hypothesis.py           tests/test_v1_1_golden.py
tests/test_causal.py               tests/test_v1_1_support.py
tests/test_engine.py               tests/test_v1_1_staleness.py
tests/test_runtime.py              tests/test_phase_c_freeze.py
tests/test_comparator.py           tests/test_prose_numeric_bindings.py
tests/test_determinism.py          tests/test_systems_paper_numeric_claims.py
```

The last two are what make this about the **manuscripts** rather than about
the code: they bind printed figures to what the code computes. A mutant that
survives even those has changed a diagnostic number that no paper claim
depends on.

The whole suite is not run per mutant. Most of it — packaging guards, markdown
paths, bibliography ledgers — cannot respond to a change in `bayes.py`, and a
full run per mutant would take hours without changing a verdict.

## 6. Families

| family | what it attacks | files |
|---|---|---|
| **GATING** | whether a relation contributes evidence at all | `csia/prediction/comparator.py` |
| **EVIDENCE** | the four documented departures from a Bayes posterior, and the trust update | `csia/diagnosis/bayes.py`, `csia/trust_engine/engine.py` |
| **TIMING** | staleness and dwell — how "no evidence" is kept distinct from "evidence of health" | `csia/runtime/online.py`, `csia/runtime/failsafe.py`, `csia/diagnosis/baselines.py` |
| **SUPPORT** | whether a hypothesis is entitled to be asserted at all | `csia/diagnosis/hypothesis.py`, `csia/diagnosis/baselines.py` |
| **CONFIGURATION** | deployment-visible thresholds — the values a wrong config could plausibly move | `csia/runtime/failsafe.py`, `csia/trust_engine/engine.py` |
| **DIAGNOSIS** | which cause is named, and how confidently | `csia/diagnosis/causal.py`, `csia/diagnosis/baselines.py` |

GATING is the family that matters most to the systems paper. Its subject is a
gate that **skipped** an inapplicable feature instead of marking it
unassessable, so `GATING-04` — declaring GPS valid at every tick, including
during injected fix loss — is the closest single-line analogue of the paper's
headline mechanism. It must not survive.

Every mutant carries a `breaks` field saying why the change is scientifically
meaningful. A mutant nobody can justify is a mutant whose survival means
nothing.

## 7. Author judgements

Recorded here rather than in the runner, and each must carry an argument, not
a label.

### `SUPPORT-01` — INVALID_MUTANT, and the reason is worth keeping

Capping `MAX_SOURCES_PER_HYPOTHESIS` at 1 does not produce a program that
fails a test. It produces a program that **will not import**:

```
csia/diagnosis/hypothesis.py:141: in __post_init__
E   ValueError: H_SHARED_POWER_DEGRADATION: 2 sources exceeds
    MAX_SOURCES_PER_HYPOTHESIS=1
```

The frozen core validates its own hypothesis table at import time and refuses
to exist in a state where a declared hypothesis violates the cap. That is a
real defensive property and it is stronger than any test could be — but it is
**not evidence about the test suite**, which is what this campaign measures, so
the verdict stays `INVALID_MUTANT`.

*(No `EQUIVALENT` or `OUT_OF_SCOPE` judgements have been made. If a survivor is
ever explained away with one, the argument goes here, signed and dated, and
`MUTATION_SURVIVORS.md` links to it.)*

## 8. Sandbox, and the trap it checks for

Mutating the frozen core means writing to `csia/diagnosis/bayes.py`. Doing that
in the working tree is unacceptable: a crash between "apply" and "revert"
leaves the scientific core silently modified and the next commit ships it. So
every mutant is applied in a `git worktree add --detach` checkout. **The
working tree is never written to.**

The development venv has CSIA installed editable, so `import csia` normally
resolves to the **original** repository even with pytest's cwd inside the
sandbox. A run that silently imports the unmutated core reports every mutant
`SURVIVED` and looks like a devastating finding.

Two checks run before any real mutant, and either failing aborts the campaign
rather than reporting:

1. `csia.__file__` as imported from the sandbox must be **inside** the sandbox;
2. a **canary** mutant (`PRIOR_NOMINAL = 0`) must be killed.

Both are recorded in the results file under `self_check`.

## 9. Reproducing

```
make verify-paper-mutations
```

or directly:

```
.venv/bin/python tools/mutation/run_mutations.py
.venv/bin/python tools/mutation/run_mutations.py --only GATING-04
```

The run takes roughly 15–25 minutes: killed mutants exit early under `-x`,
survivors run the full selection twice.
