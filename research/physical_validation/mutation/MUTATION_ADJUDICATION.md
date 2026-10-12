# Adjudication of the six unresolved mutants

**What this file is.** `MUTATION_SURVIVORS.md` reported five mutants killed
only by a file hash, plus one that would not run. This file adjudicates all
six, one by one, at a later HEAD, and says for each what its verdict is worth.

| | |
|---|---|
| original campaign | 24 mutants at HEAD `33d3d61` — `MUTATION_RESULTS.json` |
| re-adjudication | 6 mutants at HEAD `63af8c2` — `MUTATION_READJUDICATION.json` |
| runner | `tools/mutation/run_mutations.py` |
| canary | `PRIOR_NOMINAL = 0` → **KILLED**, so the sandbox is not resolving `import csia` to the unmutated tree |

| verdict, re-adjudication | count | was |
|---|---|---|
| `KILLED` | **4** | 0 |
| `KILLED_BY_INTEGRITY_ONLY` | **1** | 5 |
| `INVALID_MUTANT` | **1** | 1 |

**A raw count of 4/5 newly killed is not the finding, and reading it that way
would be the exact failure this campaign exists to detect.** Two of the four
were killed by a test that already existed and was missing from a hand-picked
selection; two were killed by tests written this session, after the mutants
were known. Section 2's classes exist to keep those apart.

---

## 1. The classes

**These five classes are defined here, by me.** They are not inherited from the
mutation runner, whose vocabulary has only `KILLED` / `KILLED_BY_INTEGRITY_ONLY`
/ `SURVIVED` / `INVALID_MUTANT` / `EQUIVALENT` / `OUT_OF_SCOPE`. That vocabulary
cannot distinguish a blind kill from a kill by a test written after seeing the
mutant, and that distinction is the whole value of the exercise.

| class | meaning | what the verdict is worth |
|---|---|---|
| **A** | killed by a test that **already existed** and was simply absent from the selection | full value. The suite did pin this; the campaign did not look |
| **B** | killed by a test **written this session**, with the mutant already known | reduced. Records that the gap is closed; does **not** measure the suite as it stood |
| **C** | **integrity-only.** The only objection is a file hash or tag diff, which fires identically on a reformatted comment | none, for the science. The change cannot reach a commit and no test asserts the behaviour |
| **D** | **self-refuting.** The mutated program refuses to run | stronger than any test, and says nothing about the suite |
| **E** | **unresolved.** Adjudication needs work or a decision not taken here | none yet |

A mutant can only be class A if the killing test predates knowledge of the
mutant. Where both an old and a new test kill it, it is class A, and the new
test is noted rather than credited.

---

## 2. The six

### `EVIDENCE-05` — class **B**

`csia/trust_engine/engine.py` · `alpha0: float = 8.0` → `800.0`

| | |
|---|---|
| was | `KILLED_BY_INTEGRITY_ONLY` |
| now | **`KILLED`** |
| killed by | `tests/test_scalar_rederivation.py` — four tests: `test_s0_rederives_from_the_frozen_engine`, `test_t0_rederives_from_the_frozen_engine`, `test_the_mass_term_rederives_to_the_published_118_82`, `test_s0_is_not_settled_at_the_published_horizon` |

**Class B, and the reason must not be softened.** `MUTATION_SURVIVORS.md`
identified the exact remedy — "a check that re-derives `settled_mass_S0` from
the live `TrustCore`" — and then explicitly declined to write it, on the
grounds that "a mutant killed by a test written after seeing it measures
nothing". That test was written this session. **This kill therefore measures
that the gap is closed, and does not measure the suite as it stood.**

What makes it worth something anyway is that the test was written for an
independent, separately-specified reason: `S_0` was `ARTIFACT_SUMMARY_ONLY` in
the scalar-provenance work, and the oracle re-derives `475.6775112557788` and
`0.9997912967043575` from the frozen engine. Its sensitivity was **measured,
not assumed**: `alpha0` at 8 → 80 → 800 gives `S_0` 475.6775 → 479.2514 →
514.9906. An oracle that could not move would have been a second copy of the
number.

**A separate correction found while writing it, and not folded away.** The
artifact field is named `settled_mass_S0`, and the mass is **not settled** at
n = 1500: 98.90 at n=100, 319.92 at n=500, 433.82 at n=1000, 475.68 at n=1500,
498.79 at n=3000, against a cap of 500. The *trust* is settled; the mass is
not. `S_0` is a function of the horizon and must be quoted with `n_steps`.
118.82 is unaffected and `escalation_algebra.json` was **not** rewritten.

### `TIMING-04` — class **A**

`csia/diagnosis/baselines.py` · `DWELL_TICKS` → `0 * DWELL_TICKS`

### `SUPPORT-04` — class **A**

`csia/diagnosis/baselines.py` · `D_MIN_SOURCES` → `1`

### `DIAGNOSIS-04` — class **A**

`csia/diagnosis/baselines.py` · `VOTE_C` → `0`

| | |
|---|---|
| were | `KILLED_BY_INTEGRITY_ONLY` ×3 |
| now | **`KILLED`** ×3 |
| killed by | `tests/test_shared_power_baselines.py::test_baseline_constants_match_protocol` (**pre-existing**) and `tests/test_baseline_rederivation.py::test_the_baseline_verdicts_rederive_from_the_frozen_campaign` (new). `DIAGNOSIS-04` additionally by `test_the_rederivation_is_sensitive_to_the_baseline_constants` |

**MY EARLIER FINDING WAS PARTLY WRONG, AND THIS IS THE CORRECTION.**

`MUTATION_SURVIVORS.md` §2–4 says of these three:

> the baselines can be made to fire instantly, on one source, at every tick,
> with no behavioural test objecting. If a referee asks *"how do we know the
> baselines are the baselines you describe?"*, the current answer is: **a file
> hash**.

That was **not true**. `tests/test_shared_power_baselines.py` existed, and
asserts `VOTE_C == 0.70`, `DWELL_TICKS == 25`, `D_MIN_SOURCES == 2`. The answer
to the referee was never "a file hash". **The file was absent from the
mutation campaign's hand-picked selection**, so the campaign could not see it.

That is a **measurement error in the campaign, not a coverage gap in the
suite**, and the two look identical in the output. Correcting the selection is
therefore not score-chasing, and the runner's `DEFAULT_SELECTION` now carries a
comment on each addition saying which it was.

**A qualification that keeps these at their true strength, not higher.**
`test_baseline_constants_match_protocol` is a **value assertion**, not a
behavioural one: it reads a constant and compares it to a literal. That is
meaningfully stronger than a file hash — it survives reformatting and it names
the value — but it does not exercise what the detector *does*. The mutation
runner's guard derivation classifies "not a source-integrity guard" as
behavioural, which over-credits it. Recorded so nobody reads these three as
behaviourally pinned by the old suite alone.

The genuinely behavioural killer is the **new** `test_baseline_rederivation.py`,
which drives the frozen baselines over a family-stratified subset of the 110
committed scenarios and compares six verdict fields. Its own sensitivity
control sets `B.VOTE_C = 0.0`, which is `DIAGNOSIS-04`'s mutation exactly — so
for that one mutant the new test is aimed, and is credited as class B evidence
inside a class A verdict, not as an independent kill.

**Measured while building that oracle:** the full 110-scenario re-derivation
(64 s) matched the committed artifact on **every verdict field**. Of the
differences, 723 were `tick_cost_us` and 6 were
`A_LEGACY_SINGLE_SOURCE.t_first_detection` in the `NEGATIVE_INDEPENDENT`
dual-IMU family, where the verdicts are identical. Neither excluded class is
load-bearing: no test and no manuscript binding references `t_first_detection`,
or this artifact at all.

### `CONFIGURATION-02` — class **C**, unchanged

`csia/runtime/failsafe.py` · `imu_isolation_gap: float = 0.12` → `0.99`

| | |
|---|---|
| was | `KILLED_BY_INTEGRITY_ONLY` |
| now | **`KILLED_BY_INTEGRITY_ONLY`** |
| objected | four hash/tag guards, and nothing else |

Makes IMU isolation unreachable: a divergent dual-IMU pair is never resolved to
one unit. **No behavioural test exercises the isolation path at a gap that
matters, and none was written.**

**This one was deliberately left open.** Writing a test for it now would move
the count to 5/5 and measure nothing — precisely the move
`MUTATION_SURVIVORS.md` warns against. The honest state is that one of the five
is still pinned by a file hash alone, and the count is **4 of 5**, not 5 of 5.

What the remedy would look like, recorded so it can be scheduled rather than
improvised: a test that asserts *what isolation does* at a gap either side of
the threshold, derived from the failsafe behaviour the manuscripts describe —
not a test that asserts `imu_isolation_gap == 0.12`, which would be another
value assertion.

### `SUPPORT-01` — class **D**

`csia/diagnosis/hypothesis.py` · `MAX_SOURCES_PER_HYPOTHESIS = 8` → `1`

| | |
|---|---|
| was | `INVALID_MUTANT` |
| now | **`INVALID_MUTANT`**, and correctly so |

Reproduced directly in a detached worktree this session:

```
ValueError: H_SHARED_POWER_DEGRADATION: 2 sources exceeds
            MAX_SOURCES_PER_HYPOTHESIS=1
```

The frozen core validates its own hypothesis catalogue at **import**, in
`Hypothesis.__post_init__`, and refuses to exist in an inconsistent state. No
test runs, because there is no program.

**That is a stronger property than any test could give, and it is still not a
`KILLED`.** This campaign measures the test suite; this mutant never reached
it. Recording it as a kill would inflate the count with something the suite had
no part in — which is why class D exists rather than folding it into A or B.

---

## 3. What changed, and what did not

| mutant | before | after | class |
|---|---|---|---|
| `EVIDENCE-05` | integrity-only | **KILLED** | B |
| `TIMING-04` | integrity-only | **KILLED** | A |
| `SUPPORT-04` | integrity-only | **KILLED** | A |
| `DIAGNOSIS-04` | integrity-only | **KILLED** | A |
| `CONFIGURATION-02` | integrity-only | integrity-only | **C** |
| `SUPPORT-01` | invalid | invalid | D |

**The defensible summary, in one sentence:** of the five mutants no behavioural
test noticed, three were a selection error and were already pinned by a value
assertion, one is now pinned by a behavioural oracle written after the fact,
and **one is still pinned by nothing but a file hash**.

## 4. What this adjudication does not establish

* **Not that the mutated values are wrong.** A mutation campaign never says
  whether a constant is correct — only whether something would notice it
  changing.
* **Not a coverage measurement.** The selection is the diagnostic subset, not
  all 1787 tests. "Nothing noticed" means "nothing in the science tests
  noticed".
* **Not an independent result.** The agent chose the mutants, chose the
  selection, **got the selection wrong once**, and wrote the tests that killed
  two of them. A reviewer choosing their own mutants would be worth more than
  another campaign by the same author — recorded as C-3 in
  `USER_ACTION_REQUIRED.md`.
* **Not stable across HEAD.** The original campaign is a measurement at
  `33d3d61` and this re-adjudication at `63af8c2`. Neither is a property of the
  repository in general.
* **`KILLED_BY_INTEGRITY_ONLY` still depends on the derived guard list.** Eleven
  node ids, derived by AST from the selection's own sources. The first
  hand-written version was wrong and missed two guards that then killed seven
  mutants each looking behavioural. A test that hashes a file without naming it
  in a way the derivation recognises would still be miscounted.

## 5. Still open

1. **`CONFIGURATION-02` needs a behavioural test of the isolation path**,
   written from the failsafe behaviour the manuscripts describe rather than
   from the mutant. §2.
2. **The `EVIDENCE-05` shape has not been surveyed.** Artifact-mediated
   bindings — a `results/*.json` read by a test but regenerated only by hand —
   are invisible to exactly the same class of change. `EVIDENCE-05` was found
   by a mutant, not by looking. Nobody has enumerated the rest.
3. **The other 18 mutants have not been re-run** at any later HEAD.
