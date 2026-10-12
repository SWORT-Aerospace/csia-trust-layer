# Mutation survivors — what the test suite does not pin

**Campaign:** P11, run at HEAD `33d3d61`.
**Plan:** `MUTATION_PLAN.md` · **Raw:** `MUTATION_RESULTS.json`
**Runner:** `tools/mutation/run_mutations.py` · `make verify-paper-mutations`

| verdict | count |
|---|---|
| `KILLED` — a behavioural test failed | **18** |
| `KILLED_BY_INTEGRITY_ONLY` — only a file-hash or tag diff objected | **5** |
| `INVALID_MUTANT` — the mutated program does not run | **1** |
| `SURVIVED` — nothing failed at all | **0** |

**The five are the finding.** Every one can be changed without a single
behavioural assertion in the diagnostic test suite noticing. What stopped them
was `test_diagnostic_core_is_unchanged_since_the_freeze` and its four
siblings — checks that the *file* did not change, which would fire identically
on a reformatted comment.

That is a real and useful property: none of these changes can reach a commit.
It is not the property the manuscripts rest on. **No claim in either paper is
pinned to the behaviour of these five lines.**

---

## The five

### 1. `EVIDENCE-05` — the Beta prior mass
`csia/trust_engine/engine.py` · `alpha0: float = 8.0` → `800.0`

Multiplies the prior mass by 100. `alpha0`/`beta0` set `T(0) = 8/10 = 0.8` and
the banked mass the trust recursion carries.

**Why it matters more than the others.** `S_0 = 475.6775` — the measured
settled Beta mass in the 118.82 chain — is a *consequence* of this prior. The
systems paper's arithmetic `475.6775 × (0.999791 − 0.75) = 118.82` traces back
to it, and a test suite that does not notice a 100× change in the prior is not
pinning the quantity that chain starts from.

**IT IS A BINDING GAP, NOT A COVERAGE GAP — resolved, not left open.**

`S_0` *is* pinned, and pinned well:
`test_systems_paper_numeric_claims.py::test_the_mass_term_inputs_are_the_measured_ones`
asserts `s0 == 475.6775` and `t0 == 0.999791` as **factors**, precisely because
pinning the product 118.82 alone failed to catch two wrong published
explanations of where it came from.

But it reads both from a stored artifact —
`research/wp_c8/results/escalation_algebra.json` — and never runs the engine.
`research/wp_c8/escalation_algebra.py` *does* import `EngineConfig` and
`TrustCore` and derive `settled_mass_S0` from the shipping core, so the chain
**engine → S_0 → 118.82** exists. It is just not closed by anything that runs:

```
engine.py alpha0 ──(escalation_algebra.py, run by hand)──▶ escalation_algebra.json
                                                                   │
                                       (test reads the JSON) ──────┘
```

Change `alpha0` and the JSON keeps its old value until someone re-runs the
script. The test then passes, and it passes *because* the artifact is stale.

**The remedy is therefore not "add a test that reads alpha0".** It is to close
the loop — a check that re-derives `settled_mass_S0` from the live
`TrustCore` and compares it to the artifact, so a change to the engine
invalidates the artifact instead of being invisible to it. That check does not
exist and is **not written here**: writing it would kill this mutant, and a
mutant killed by a test written after seeing it measures nothing (see *What
must NOT be done with this file*). It is recorded for the user to schedule
deliberately.

### 2, 3, 4. The baseline detectors — `csia/diagnosis/baselines.py`
* `TIMING-04` · `DWELL_TICKS` → 0 — the detectors fire with no persistence
* `SUPPORT-04` · `D_MIN_SOURCES` → 1 — a single degraded source establishes a
  shared-resource verdict
* `DIAGNOSIS-04` · `VOTE_C` → 0 — the voting baseline detects at every tick

**Three of the five are the same file, and that is the pattern worth naming.**
These are the *baselines the Mechanism-B comparison is against*. The paper's
argument has the form "the trust path behaves thus, where the conventional
baselines behave so" — and the baselines can be made to fire instantly, on one
source, at every tick, with no behavioural test objecting.

If a referee asks *"how do we know the baselines are the baselines you
describe?"*, the current answer is: **a file hash**. That is weaker than the
question deserves, and it is weaker than the treatment the trust path itself
gets — the 18 behaviourally-killed mutants are almost all on the CSIA side.

### 5. `CONFIGURATION-02` — IMU isolation threshold
`csia/runtime/failsafe.py` · `imu_isolation_gap: float = 0.12` → `0.99`

Makes IMU isolation unreachable: a divergent dual-IMU pair is never resolved to
one unit. No behavioural test exercises the isolation path at a gap that
matters.

---

## What this does NOT say

* **Not that the five values are wrong.** A mutation campaign says nothing
  about whether a constant is correct. It says whether a test would notice it
  changing.
* **Not that the suite is weak.** 18 of 24 mutants died to behavioural
  assertions, including every GATING mutant — `GATING-04`, declaring GPS valid
  at every tick during injected fix loss, is the closest single-line analogue
  of the systems paper's headline mechanism, and it was killed by
  `test_the_fix_loss_case_is_reported_as_unsupported`.
* **Not a coverage measurement.** The selection is the diagnostic subset
  (`MUTATION_PLAN.md` §5), not all 1787 tests. A survivor means "nothing in the
  science tests noticed", not "nothing in the repository noticed".

## What must NOT be done with this file

**Do not write tests aimed at these five mutants.** That would move them to
`KILLED`, raise nothing, and destroy the measurement — the number would then
describe how many mutants somebody had seen, not what the suite establishes.

If the baselines deserve behavioural pinning — and §2–4 argues they do — the
test to write is one that asserts *what the baseline detectors do*, derived
from the Mechanism-B comparison the paper actually makes. That test would kill
these mutants incidentally. The distinction is the whole difference between
strengthening the evidence and gaming a metric.

## The one INVALID_MUTANT, and why it is a good sign

`SUPPORT-01` capped `MAX_SOURCES_PER_HYPOTHESIS` at 1. The result is not a
failing test — it is a program that **will not import**:

```
csia/diagnosis/hypothesis.py:141: in __post_init__
E   ValueError: H_SHARED_POWER_DEGRADATION: 2 sources exceeds
    MAX_SOURCES_PER_HYPOTHESIS=1
```

The frozen core validates its own hypothesis table at import and refuses to
exist in an inconsistent state. That is stronger than any test could be. It is
still recorded as `INVALID_MUTANT` rather than `KILLED`, because this campaign
measures the **test suite**, and this mutant never reached it.

## Open, and needed before this is quoted

1. **Are there other artifact-mediated bindings like `EVIDENCE-05`'s?** That
   one was found by a mutant. `research/*/results/*.json` files read by tests
   but regenerated only by hand are the same shape, and nobody has enumerated
   them. A survey would say how much of the manuscripts' numeric binding runs
   through stale-able artifacts.
2. **The five have not been re-run at a later HEAD.** They are a measurement at
   `33d3d61` and nowhere else.
3. **`KILLED_BY_INTEGRITY_ONLY` depends on the derived guard list** (11 node
   ids, in `MUTATION_RESULTS.json`). It is derived by AST from the selection's
   own sources — the first, hand-written version was wrong on its first run and
   missed two guards that then killed seven mutants each looking behavioural.
   A test that hashes a file but does not name it in a way the derivation
   recognises would still be miscounted.
