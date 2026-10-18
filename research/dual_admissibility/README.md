# Dual-channel admissibility

**Question.** Should operational admissibility (`A`) and diagnostic evidential
admissibility (`D`) be represented as distinct state variables?

**Answer.** `PROMISING_BUT_CONFOUNDED`. They *are* the same variable here —
`fresh[]` is both gates, source-verified. Decoupling them recovers attribution
under **sustained** invalidity, where the matched coupled controls gain exactly
nothing. But on the one real recording the effect is detector-dominant
(+0.138 from the evidence term under coupling, +0.002 from the split), and the
operational half of the story changed no recommendation at all.

Read [`CHATGPT_REVIEW_REPORT.md`](CHATGPT_REVIEW_REPORT.md) first — §8 and §13
are the ones that argue against the result.

```
make dual-admissibility     # everything, about four minutes
make dual-reproduce         # just the item-8 gate: does S0/S1 still reproduce?
```

## What is here

| Document | |
|---|---|
| `CHATGPT_REVIEW_REPORT.md` | **start here** — 32 sections, hostile review A–J, verdict |
| `SOURCE_VALIDITY_ROLE_AUDIT.md` | where one value does both jobs |
| `SEMANTIC_STATE_MODEL.md` | the state space the source actually supports |
| `FORMAL_RESULTS.md` | T1–T5, validated to 1 × 10⁻⁵ |
| `MINIMAL_COUNTEREXAMPLE.md` | two hypotheses, two features, closed form |
| `CLAIM_LEDGER.json` | 20 claims with evidence class and forbidden wording |
| `PHYSICAL_HIL_VALIDATION_PLAN.md` | three levels, criteria stated in advance |
| `DUAL_ADMISSIBILITY_PREREGISTRATION_DRAFT.md` | **draft, not frozen, not run** |

| Script | Produces |
|---|---|
| `source_validity_role_audit.py` | 16 gates, each pinned and re-verified |
| `reproduce_s0_s1.py` | the item-8 hard stop; exit 2 means stop |
| `three_arm_experiment.py` | M1 results, clean controls, Pareto |
| `pattern_and_transport.py` | eight temporal patterns, transport control, aliasing |
| `formal_analysis.py` | theorems, counterexample, information loss, compute |
| `semantic_search.py` | ingest-path equivalence, automatic collapse search |
| `cross_sensor_audit.py` | which families could even exhibit this |
| `dual_arms.py`, `dual_replay.py` | the ten arms and the replay loop |

Tests: `tests/test_dual_admissibility.py` (26).

## The ten arms

Every split arm has a **matched coupled control carrying identical evidence
terms and differing in one boolean** — that pairing is what turns "did the
split help?" into a number instead of an opinion.

| | policy | status | h_acc | D gating | h_acc freshness |
|---|---|---|---|---|---|
| `S0` | drop invalid | – | – | – | – |
| `S1` | propagate | – | – | – | – |
| `S1Da` | propagate | ✓ | – | **D = A** | message |
| `S1Db` | propagate | – | ✓ | **D = A** | message |
| `S1D` | propagate | ✓ | ✓ | **D = A** | message |
| `S2a` | propagate | ✓ | – | independent | message |
| `S2b` | propagate | – | ✓ | independent | message |
| `S2c` | propagate | ✓ | ✓ | independent | message |
| `S2b2` | propagate | – | ✓ | independent | valid_hacc † |
| `S2c2` | propagate | ✓ | ✓ | independent | valid_hacc † |

† POST-HOC instrument fix, found by looking at a result. It does not change the
M1 numbers, so it cannot be accused of rescuing them.

## Evidence classes

* **Source-verified.** `source_validity_role_audit.py` — 16 patterns, each
  required to occur exactly once, resolved to a line, re-read to confirm the
  number. It fails rather than drifts.
* **Real recording, N = 1.** `NON_SCORED_TEST_FIXTURE_M1`, an ArduPilot
  `SIM_GPS1_JAM` episode already committed. Every trust and posterior number
  attributed to real data comes from here.
* **Synthetic validity schedule.** The pattern and search fixtures program the
  GNSS stream over that recording's real non-GNSS carrier. They measure the
  gate and the status/h_acc terms; they report no physics-derived numbers.
* **Closed form.** Derived from frozen constants, then checked against the
  replays — the theory predicts the experiment, not the other way round.

## The frozen core is untouched

`csia/` is not modified. The research objects are `DiagArm` (a wrapper on
`layer.diag` around a stock `DiagnosisCore` with an extended hypothesis map)
and `PropagateInvalidAdapter` from the committed invalidity-masking harness.
`tests/test_dual_admissibility.py` asserts the arms differ by exactly one field
from their controls, that no arm can readmit an invalid navigation value, and
that no scenario or fault label reaches runtime logic.
