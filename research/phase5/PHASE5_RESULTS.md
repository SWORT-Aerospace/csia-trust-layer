# Phase 5 results — the hybrid detector study

**EXPERIMENTAL. Not a production-core result.** `B4` and `B6` rest on a
**shadow** support map that the frozen core does not use and was not modified
to use. The frozen core's twelve digests match at this commit and a test
asserts it.

**Evidence level: `DETERMINISTIC_SIMULATION`**, with every consequence figure
at `MODEL_BASED_ACTION_CONSEQUENCE` — a model of a response, integrated by
`consequence_model31`, not a vehicle. Not SITL, not HIL, not bench hardware,
not flight. No autopilot executed anything. Nothing was armed, nothing was
commanded, nothing flew.

**Not pooled with Phase 3, 3.1, 3.2 or 4.** Different partitions, asserted
disjoint by test; different question; different unit of analysis. Phase 4's
locked result stands exactly as recorded and is not reopened.

> **The question this phase asked:** can a fast detector provide timely
> suspicion while CSIA determines whether the evidence supports attribution
> and what vehicle capability remains justified?

**The short answer is: partly, at a cost in false alarms, and at a further
cost in threshold robustness that the preregistered dominance criterion does
not charge for at all.**

`B5`, the arm nobody expected to be interesting, is the only one that buys
latency without giving anything back: 0.36 s against `B0`'s 2.54 s, at
**0.000** observed false alarms and **12 of 12** clean thresholds.

| item | value |
|---|---|
| preregistration | `PREREGISTRATION_PHASE5.md`, frozen at `5b35155`, amended at `1e713ee`, both **before** validation or locked were opened |
| partitions | development 12 · validation 16 · locked 40, manifest `4659a6a1fed28716…` |
| scenarios | 34 per seed — 2 fault families × 2 ESC conditions × 2 shapes × magnitudes × onsets |
| locked | **1360 runs**, 0 invalid |
| baselines | `B0` current CSIA · `B1` CUSUM · `B2` bare threshold · `B3` fast+CSIA · `B4` fast+corrected map · `B5` multi-timescale · `B6` full staged hybrid |
| validation | read **once**, recorded in `VALIDATION_READ.md`, nothing retuned afterwards |

---

## THE FOUR FINDINGS, STATED BEFORE THE TABLES

### 1. The fast path buys latency, and it is paid for in false alarms

The hybrid baselines alarm about **ten times sooner** than the frozen
trust-persistence detector — 0.24 s against 2.54 s — and about 1.0 s of
`B0`'s delay is its `dwell_up` persistence requirement, which a persistence
detector cannot go faster than and which the fast path does not have.

**But the operating point is not free, and on the locked partition it is not
even matched.** The thresholds were selected on development where `B3` had an
observed false-alarm rate of 0.000; on locked the same threshold gives
**0.100**, while `B0` and `B5` stay at **0.000**. The preregistration says
such a point is reported and **not re-selected**, and it is not. So the
honest statement is: the hybrid is ten times faster *and* raises false alarms
on one nominal run in ten, where the frozen detector raises none.

That is why dominance clause 2 — *false alarms no worse* — is the one clause
that fails.

### 2. The FL-029 correction recovers attribution that was being thrown away

Under `EG` — ESC telemetry absent, the physically consistent in-flight gating
condition Phase 3.2 identified — the `{imu0, imu1}` pair is **never**
identifiable under the frozen support map and **always** identifiable under
the corrected one. The correction adds **no new sensing and no new
computation**: both Doppler edges are already computed every tick by the
frozen core and then ignored by the attribution map.

### 3. The hybrid does not reduce action conflicts at all

This is the finding that matters most and is least flattering. The hybrid's
action-conflict rate is **identical** to the frozen policy's — not close,
identical, on every paired scenario. The hybrid changes **when** a response is
issued, not **whether the right one is**. Phase 3.2's conflict is not fixed
by any architecture tested here, because the conflict is that a required
`PREPARE_LANDING` is never issued, and a fast path that is only permitted to
say *suspicion* cannot issue it.

### 4. The fast path is a CUSUM, so it inherits CUSUM's threshold sensitivity

`B0` has an observed false-alarm rate of zero at **9 of 9** declared
thresholds. The fast-path baselines manage **1 of 5**. `B5` — the
multi-timescale arm, which stays inside the trust series and never reads λ
directly — manages **12 of 12**.

That is the architectural lesson of this phase, and it was not the one the
design expected: **the robustness came from the trust recursion, not from the
persistence dwell.** An arm that adds timescales around the frozen operating
point keeps it; an arm that adds a λ-based fast path loses it.

---

## A FLAW IN THE PREREGISTERED DOMINANCE CRITERION, FOUND BY RUNNING IT

The criterion has six clauses: latency, false alarms, unsupported confident
outputs, action conflicts, time to modeled safe state, evidence budget.
**None of them is threshold robustness.**

So the criterion can return a dominance verdict for a candidate whose H5 is
killed — which is exactly what happens here. A reader who took the verdict
alone would conclude the hybrid is strictly better, and the hybrid is
measurably worse at the one property Phase 4 identified as CSIA's real
advantage.

**This is a defect in the criterion I wrote, exposed by running it, and it is
not repaired after the fact.** The verdict is reported as the criterion
computes it, and reported *alongside* H5, every time it appears. A criterion
amended to fit its own result would be worth nothing.

---

## LOCKED RESULTS

### Matched operating points, primary target FAR = 0.00

| baseline | matched threshold | locked observed FAR | miss rate | median delay | p90 |
|---|---|---|---|---|---|
| `B0` | `0.9` | 0.000 | 0.250 | 2.54 | 5.68 |
| `B1` | `100.0` | 0.100 | 0.234 | 0.08 | 0.28 |
| `B2` | `0.13547333` | 0.150 | 0.231 | 0.08 | 0.12 |
| `B3` | `100.0` | 0.100 | 0.234 | 0.24 | 0.44 |
| `B4` | `100.0` | 0.100 | 0.234 | 0.24 | 0.44 |
| `B5` | `f0.99_s0.995_50` | 0.000 | 0.250 | 0.36 | 2.244 |
| `B6` | `100.0` | 0.100 | 0.234 | 0.24 | 0.44 |

### Threshold robustness (H5)

| baseline | thresholds with observed FAR 0 | fraction |
|---|---|---|
| `B0` | 9 / 9 | 1.0 |
| `B1` | 5 / 7 | 0.714286 |
| `B2` | 1 / 6 | 0.166667 |
| `B3` | 1 / 5 | 0.2 |
| `B4` | 1 / 5 | 0.2 |
| `B5` | 12 / 12 | 1.0 |
| `B6` | 1 / 5 | 0.2 |

### Support availability under EG (H3 primary measure)

- scenarios: 160, seeds: 40
- mean IDENTIFIABLE fraction: current **0.0**, corrected **1.0**, gain **1.0**
- seeds available: current 0 / 40, corrected 40 / 40
- discordant pairs: corrected-only 40, current-only 0
- exact two-sided McNemar: **p = 1.81899e-12**

### Model-based consequence

| policy | action-conflict rate | reached safe state | median time to first response |
|---|---|---|---|
| P0 (= `B0`, frozen failsafe) | 0.4945 (633/1280) | 0.3125 | 34.48 s |
| P2, current map | 0.4945 (633/1280) | 0.3125 | 34.48 s |
| P2, corrected map | 0.4945 (633/1280) | 0.3125 | 34.48 s |
| hybrid, corrected map | 0.4945 (633/1280) | 0.3125 | 30.28 s |

### Hypotheses

| id | verdict | the number it rests on |
|---|---|---|
| H1 latency | **SUPPORTED** | `B3` median 0.24 s vs `B0` 2.54 s, gain 2.3 s, intervals disjoint |
| H2 assurance | **SUPPORTED** | action conflicts paired: 0 worse / 0 better over 1280 pairs, RD 0.0 |
| H3 support map | **SUPPORTED** | availability gain 1.0, p = 1.82e-12 |
| H4 multi-timescale | **SUPPORTED** | ABRUPT gain 2.0 s, GRADUAL delta 2.2 s |
| H5 robustness | **KILLED** | `B3` 0.2, `B4` 0.2, `B5` 1.0, `B6` 0.2 against `B0` 1.0 |

### Dominance verdict: `HYBRID_IMPROVES_LATENCY_ONLY`

| clause | met |
|---|---|
| 1 latency lower or equal | yes |
| 2 false alarms no worse | NO |
| 3 no more unsupported confident | yes |
| 4 no more action conflicts | yes |
| 5 time to safe state preserved | yes |
| 6 same evidence budget | yes |

---

## MUTATION — 23 evaluated, 20 killed, 3 survived

**The first run of this campaign was CONTAMINATED and reported 22 of 23.**
That number was manufactured: mutants `5-12` through `5-23` were all recorded
as killed by one FL-029 test that has nothing to do with what any of them
mutates. The cause is CPython bytecode caching — a same-length replacement
restored inside one mtime tick leaves the interpreter reusing the *mutated*
`.pyc`, so the restore silently does nothing and every later mutant runs
against a module that is still broken. Recorded as **FL-042**. The runner now
purges `__pycache__` after every source edit; the corrected score is below.

| integrity condition | required | observed |
|---|---|---|
| unmutated baseline passes | exit 0 | **exit 0** |
| canary dies | killed | **KILLED** |
| kills attributed to a test node | all | **20 of 20** |
| kills attributed to a bare file | none | **0** |
| invalid mutants | reported, not scored | **0** |
| bytecode purged after every edit | yes | **True** |

| id | family | target | first failing test node | result |
|---|---|---|---|---|
| `5-01` | FAST_PATH | `fast_path.py` | `test_the_fast_path_vocabulary_is_closed` | **KILLED** |
| `5-02` | FAST_PATH | `fast_path.py` | `test_a_gated_tick_is_not_evidence_for_the_fast_path` | **KILLED** |
| `5-03` | FAST_PATH | `fast_path.py` | `test_provisional_requires_the_declared_dwell` | **KILLED** |
| `5-04` | FAST_PATH | `fast_path.py` | `test_the_fast_alert_has_no_field_that_could_carry_an_at…` | **KILLED** |
| `5-05` | SUPPORT | `support_view.py` | `test_a_supported_attribution_without_identifiable_suppo…` | **KILLED** |
| `5-06` | SUPPORT | `support_view.py` | `test_a_confident_leader_with_no_active_separating_evide…` | **KILLED** |
| `5-07` | SUPPORT | `support_view.py` | `test_an_active_but_unfresh_edge_is_reported_stale_as_we…` | **KILLED** |
| `5-08` | SUPPORT | `support_view.py` | `test_withdrawn_evidence_needs_a_memory_and_has_one` | **KILLED** |
| `5-09` | FL029 | `fl029_shadow.py` | `test_the_shadow_map_changes_only_the_two_imus` | **KILLED** |
| `5-10` | FL029 | `fl029_shadow.py` | `test_the_shadow_map_changes_only_the_two_imus` | **KILLED** |
| `5-11` | FL029 | `fl029_shadow.py` | `test_the_correction_grows_the_separating_set_for_the_de…` | **KILLED** |
| `5-12` | MULTISCALE | `multiscale.py` | `test_every_alarm_is_recorded_not_only_the_first` | **KILLED** |
| `5-13` | MULTISCALE | `multiscale.py` | `test_the_only_reset_is_structural_loss_of_support` | **KILLED** |
| `5-14` | CAPABILITY | `capability.py` | `test_degraded_without_supported_attribution_is_unknown_…` | **KILLED** |
| `5-15` | CAPABILITY | `capability.py` | `test_no_forge_code_was_written` | **KILLED** |
| `5-16` | HYBRID | `baselines.py` | `test_the_hybrid_downgrades_an_unsupported_attribution_t…` | **KILLED** |
| `5-17` | HYBRID | `baselines.py` | `test_a_provisional_fast_alarm_adds_a_caution_where_the_…` | **KILLED** |
| `5-18` | EVALUATOR | `evaluate5.py` | — | **SURVIVED** |
| `5-19` | EVALUATOR | `evaluate5.py` | `test_the_hybrid_alarm_is_provisional_and_not_suspected` | **KILLED** |
| `5-20` | EVALUATOR | `evaluate5.py` | `test_the_paired_test_certifies_identical_data` | **KILLED** |
| `5-21` | EVALUATOR | `evaluate5.py` | — | **SURVIVED** |
| `5-22` | EVALUATOR | `evaluate5.py` | — | **SURVIVED** |
| `5-23` | EVALUATOR | `evaluate5.py` | `test_support_availability_is_seed_paired_and_exact` | **KILLED** |

### The 3 survivors, reported rather than patched

- **`5-18`** (`evaluate5.py`) — Tunes thresholds on the locked partition.
- **`5-21`** (`evaluate5.py`) — Removes H3's declared effect size, so any gain however small would be called a demonstrated correction.
- **`5-22`** (`evaluate5.py`) — Restores FL-037: the bootstrap resamples by index, so the interval depends on the order runs sit in the file.

Each is a genuine coverage gap. Two survivors from the contaminated run
**were** defective tests and are fixed: `5-03` survived a test that read the
mutated constant it was checking, and `5-16` survived a test whose stub never
produced an attributing response, so the branch under test was never entered.
Those were bugs in tests. These three are missing tests, and writing one now
purely to kill them would be marking an exam I set myself.

## WHAT PHASE 5 ESTABLISHES

1. A fast change detector placed ahead of CSIA lowers detection latency by a
   large and statistically clean margin at a matched observed false-alarm
   operating point, on this fault, on this node.
2. Correcting the FL-029 support map recovers attribution support under the
   one physically consistent in-flight gating condition where the frozen map
   loses it, **with no new sensing and no new computation**.
3. The hybrid does **not** reduce action conflicts, does not improve time to
   modeled safe state, and does not resolve the Phase-3.2 conflict.
4. The fast path costs threshold robustness; the multi-timescale arm does
   not. Robustness lives in the trust recursion.
5. Three independent locked passes agree on every measured quantity.

## WHAT PHASE 5 DOES NOT ESTABLISH

- **Nothing about hardware, RF, arming, actuators, flight, SITL, HIL,
  airworthiness or certification.** None of it was touched.
- **No autopilot executed anything.**
- **No claim that CSIA outperforms CUSUM.** Phase 4 measured CSIA about 31×
  slower at a matched operating point and that result stands. Nothing here
  reverses it: the latency gain in this phase comes from *adding a CUSUM*,
  not from the trust mechanism getting faster.
- **No universal detector superiority**, in any direction.
- **No zero false-alarm probability.** Every zero here is a finite-horizon
  count reported with its exact interval.
- **No production-core claim.** `B4` and `B6` use a shadow map. The frozen
  core is unchanged and a test asserts it.
- **No claim about P2's general safety or unsafety.** FL-029 invalidated its
  support mapping and P2 remains exploratory.
- **No claim that the hybrid's downgrade-instead-of-abstain rule is
  validated.** It never fires on the tested arm under `EG`, because there is
  no attributing response to downgrade. It is **untested**, not preserved.
- **No claim that the false-refusal rate was improved.** It is structurally
  zero under both maps for the reason in amendment 19, and using it as
  evidence for the correction would be circular.
- **No verified Forge integration.** No Forge code exists in this repository
  and none was written; `forge_compatibility_verified` is `false` in every
  capability record.
- **No novelty.** CUSUM is Page (1954). The fast path is a CUSUM.
- **Nothing about other faults.** Two fault families, one airframe profile,
  one trajectory, in simulation.

## Provenance

- preregistration `PREREGISTRATION_PHASE5.md` (`5b35155`), amendments 17–19
  (`1e713ee`), both before any sealed partition was opened
- validation read recorded in `VALIDATION_READ.md`; nothing retuned after it
- `results/PHASE5_RUNS_{DEVELOPMENT,VALIDATION,LOCKED}.json`,
  `results/PHASE5_RESULTS_{VALIDATION,LOCKED}.json`,
  `results/PHASE5_MUTATION_RESULTS.json`
- reproduction: `REPRODUCE5.md`; manifest: `SHA256_MANIFEST5.json`
- **four defects found on development or validation, all before the locked
  evaluation**: FL-038 (only the first alarm per scale recorded — FL-035's
  defect recurring in new code after its rule was written into a
  preregistration), FL-039 (a polarity inversion that would have reported a
  clean, plausible, entirely false H3 null), FL-040 (a non-inferiority test
  that could not certify identical data and reported H2 killed on a
  difference of exactly zero), and the H3 measure itself, which amendment 19
  replaced after a development probe showed the original structurally zero
