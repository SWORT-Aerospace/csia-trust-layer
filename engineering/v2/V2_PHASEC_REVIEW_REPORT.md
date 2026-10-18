# CSIA v2 PHASE C — CROSS-DOMAIN CAUSAL LOCALIZATION: ENGINEERING REVIEW REPORT

Engineering only. **No novelty is claimed.** Deterministic set elimination
over declared hypotheses is ordinary diagnostic engineering; research novelty
remains a separate workstream and nothing here contributes to it.

§45's twenty-four items are §§1–24 below.

| | |
|---|---|
| frozen v1 | `csia-v1.0-research-final` @ `ec5acd189295dab9259d4989657d42184d6142a3` — **zero diff, verified** |
| v1.1 | unchanged; output schema `1.1.0` unchanged |
| branch | `claude/code-reviewer-repo-export-zicovg` |
| C1 | `933247d` two interfaces; the 28 ms turns out to have been a defect |
| C2 | `1d405d7` cross-domain localization by deterministic set elimination |
| C3 | `d75cc2d` plugin isolation, watchdog, §11 redundancy/fallback, second profile |
| C4 | `5bb6a34` §41 properties, and three answers that were confident and wrong |
| tests | 1,388 → **1,512** (124 new) |
| new domains | **none** — §0 and §44 forbid it until localization works |

---

## 1. WHAT PHASE C ADDED

Three things, in the order the Final Rule demands.

**A decision layer above the six domains.** Phase B produced six independent
opinions and no decision. `csia/v2/localization.py` turns a symptom several
domains could produce into a statement of which one the evidence supports,
which were refuted and by what, and which nobody could rule out.

**Function dependency assurance.** §11's four dependency kinds — REQUIRED,
REDUNDANT one-of-N, FALLBACK requirement sets, OPTIONAL — and §1's explanation
object per function.

**An internal interface that is ~2400× faster than the one Phase B measured**,
because the Phase B figure was a defect.

No estimator, firmware, thermal, security or storage domain was added. §44 is
explicit and the gate it names has only just been passed.

## 2. THE ANSWER TO §42's GATE

**`CROSS_DOMAIN_ASSURANCE_FUNCTIONAL`, on two qualifying sets.**

Criterion, read strictly: at least two matched sets where multiple domains
could explain the symptom initially and evidence reduced **each** member to a
**different** supported hypothesis, with no ground-truth access. "Each" is
injective — a set where two members land on the same hypothesis has not
discriminated those two.

| set | members | reduced | distinct | qualifies |
|---|---|---|---|---|
| A_STALE_OUTPUT | 4 | 4 | 4 | **yes** |
| B_ACTUATOR_RESPONSE | 5 | 0 | 0 | no |
| B_ACTUATOR_RESPONSE_BENCH | 2 | 2 | 2 | **yes** |
| C_MULTI_SENSOR | 4 | 0 | 0 | no |
| D_POSITION_FUNCTION | 4 | 4 | 3 | no |

The strict reading was chosen deliberately. Under the looser one ("more than
one distinct answer"), four sets qualified. Tightening the criterion cost two
sets and the verdict survived, which is the only way a gate result is worth
anything.

## 3. THE THREE CONFIDENT WRONG ANSWERS THIS RUN EXPOSED

Running the artifacts for the first time found three places where the
framework emitted a unique, confident answer it had not earned. All three
fixes make the reported results **worse**.

**Absence of a declared dependency was reading as evidence of independence.**
`SHARED_ADVERSE_COMPUTE_DEPENDENCY` returned `False` when the adverse sources
declared no compute node at all, so `NO_SHARED_ADVERSE_DEPENDENCY` came back
`True` and `SENSOR/independent_faults` was reported `SUPPORTED` for C1, C3 and
C4 — including the scenario whose injected cause was a saturated CPU the model
could not see. The predicates now return **not measurable** for an uncovered
domain. All four C members are now `AMBIGUOUS`.

**The stall signature confirmed only one of two identical explanations.**
"Current present and no measured motion" is exactly what a dead speed channel
produces, so giving the confirming predicate only to `ACTUATION/mechanical`
made B5's own cause read `unresolved` while its rival read `supported` off
byte-identical evidence. Both are now confirmed by it.

**An `ELIGIBLE` function could carry a limiting domain.** A
`POSITION_UNAVAILABLE` localization about one function was attached to every
function sharing a domain with it, so `INERTIAL_CONTINUATION` came back
`ELIGIBLE` and limited by `SENSOR` in the same object.

## 4. SET A — THE RESULT THAT MATTERS MOST

Four causes of one 88 ms stale output, four distinct answers:
`SENSOR/source_slow`, `COMMUNICATION/transport_delay`,
`COMPUTE/processing_delay`, `COMPUTE/process_stall`.

A1 and A2 are the Final Rule's own test case. Both put their delay in the same
interval — validity to arrival — and **no timestamp arithmetic can separate
them**. `CHANNEL_LINK_NOMINAL`, which is the COMMUNICATION plugin's own
observation about its link, is what does. That is cross-system assurance
rather than six monitors, and it is the difference the whole phase is about.

## 5. SET B — WHERE IT HONESTLY CANNOT DECIDE

Five causes of `COMMAND_NO_RESPONSE`; **no member reaches `SUPPORTED`**. Every
one carries `SENSOR/response_sensor` as a live alternative because the
multirotor has no independent physical channel on the shaft. There is no
measurement that could refute it, so the candidate set has an honest floor of
two.

§39 says don't force unique localization, and this is what obeying it looks
like in a results table.

## 6. SET B (BENCH) — THE SAME FRAMEWORK, MORE INSTRUMENTS

The motor test stand runs the identical hypotheses and predicates with one
addition — a torque channel — and resolves B4 and B5 to different, correct,
`SUPPORTED` answers.

**Resolving power is a property of the instrumentation, not the algorithm.**
The two B sets side by side are the evidence for that claim, and it is the
most useful engineering output of Phase C: it says what to instrument, not
what to compute harder.

## 7. SET C — A MODEL GAP, NAMED

The only real v1.1 payload with two adverse sources has `battery` and
`motor_esc`. They share a POWER node; the battery declares no link and neither
declares a compute node. So the framework can measure a shared-power cause and
is **blind** to a shared link or process for that pair.

C2 still isolates the common cause it can see and refutes the independent
explanation by name. Everything else is unresolved, and
`dependency_model_blind_to` names the blind domains in the results CSV.

Closing this is a **profile** change — declaring the real dependencies — not a
framework change. C2 demonstrates the framework does the right thing when the
model is complete.

## 8. SET D — AND §27's LITERAL CASE

Three distinct answers from four scenarios. D2 and D4 both land on
`COMPUTE/estimator_stale`, and that is a true property of the evidence: a
compute segment that blows its own budget **is** a stale estimator.

D4 is §27 in operation. The channel misses its end-to-end deadline *because* a
segment is over budget, so `TIMING/deadline_violation` is **refuted** by
`NO_TIMING_SEGMENT_OVER_BUDGET_FALSE` rather than co-reported. One overrun is
one fault. `TIMING/deadline_violation` is reserved for a deadline missed with
every segment inside its budget — a composition fault in its own right.

## 9. THE SIGNATURE MATRIX

54 rows over 9 symptoms, generated from the same declarations the runtime
uses, so it cannot drift from behaviour.

| cell | rows |
|---|---|
| CAN_EXPLAIN | 22 |
| CANNOT_EXPLAIN | 28 |
| DEPENDS | 4 |

§4's rule is enforced: **every `CAN_EXPLAIN` names a mechanism and the
confirming evidence**, and a generated check asserts none is blank.

## 10. THREE-VALUED PREDICATES

`True` / `False` / `None`, where `None` is **not measurable** and eliminates
nothing. This is the load-bearing rule: a two-valued predicate silently turns
"I cannot see" into "it is not so". §3 above is what happens when it slips.

## 11. MINIMUM RESOLVING EVIDENCE (§6)

Exhaustive over subsets of the **measurable** predicates up to size 6.
Unmeasurable ones are excluded — a subset containing one would appear to
resolve something the predicates around it actually resolved.

| scenario | measurable | minimum | verdict |
|---|---|---|---|
| MS_A1_SENSOR_DELAY | 11 | 5 | SUPPORTED |
| MS_A4_PROCESS_STALL | 11 | 4 | SUPPORTED |
| MS_B4_MECHANICAL | 9 | 4 | AMBIGUOUS |
| MS_TS_B5_RESPONSE_SENSOR | 11 | 4 | SUPPORTED |
| MS_C4_CPU_SATURATED_NOT_SHARED | 2 | 1 | AMBIGUOUS |
| MS_D1_NAV_SOURCE | 9 | 4 | SUPPORTED |

The C rows are the useful ones: only two predicates are measurable at all,
which is the blind spot §7 describes, stated as a number.

## 12. THE 28 ms WAS A DEFECT

`jsonschema.validate()` re-checks and re-compiles the schema on every call.

| path | µs/tick |
|---|---|
| Phase B, uncached `jsonschema.validate` | 22130.0 |
| cached validator, same full validation | 673.6 |
| external full parse | 691.8 |
| external typed ingest | 644.0 |
| **internal typed ingest** | **9.2** |

These figures move by ±10% between runs on a shared machine. The
two-thousand-fold ratio is the claim; the third significant figure is not.

Two separate claims. Building the validator once is a pure defect fix — a test
asserts the replacement is byte-identical *including which error message
`best_match()` selects*. The typed path removes the schema walk and is
legitimate only under §20. **No target-hardware figure exists and none is
claimed.**

## 13. §20's CONDITIONS ARE ENFORCED, NOT DOCUMENTED

- **Same process** — a test asserts no JSON is produced anywhere on the
  internal path. No serialisation means no boundary was crossed.
- **Version-locked** — `SUPPORTED_MAJOR_MINOR = ("1.1",)`, checked in
  `__post_init__`, plus a check that the frozen CUSUM constants match, so a
  foreign detector producing v1.1-shaped output is refused.
- **Construction-controlled** — frozen dataclass, every mapping wrapped in
  `MappingProxyType`.

## 14. INTERNAL/EXTERNAL EQUIVALENCE

**13,500 payloads, 9 mechanisms, 0 mismatches, `identical: true`.** The
comparison is the full per-tick `SystemAssurance` document, not a summary.
Zero tolerance: one differing reason code is a failure.

Equality is structural rather than coincidental — both constructors converge
on the same typed object before any evidence exists, and a test parses the
AST of the navigation domain to assert there is exactly one record builder.

## 15. PLUGIN ISOLATION (§21)

12 injections, 2 modes × 6 domains:

| mode | state | healthy claim from the failed domain | other domains reporting |
|---|---|---|---|
| `raise` | `FAILED` × 6 | **False** × 6 | 5 of 5 × 6 |
| `silent` | `NOT_CONFIGURED` × 6 | **False** × 6 | 5 of 5 × 6 |

Blast radius varies correctly by declaration: POWER degrades 10 of 10
functions, ACTUATION 2 of 10. `NOT_CONFIGURED` is deliberately distinct from
both `FAILED` and healthy — a plugin that ran and said nothing has told you
something specific.

`BaseException` is caught around `domain.evaluate` **only**, so a bug in the
supervisor cannot hide behind a domain's failure state.

## 16. THE WATCHDOG, AND THE STOPWATCH THAT MUST NOT REACH THE LEDGER

`PluginStatus` has two serialisations. `to_dict()` carries execution times and
deadline-miss counts for observability; `deterministic_dict()` is what may
enter the per-tick document and the ledger, and the wall-clock figures are
absent from it.

This was found by the replay tests failing after the supervisor was wired in.
The fix was to split the serialisation, not to relax the replay test. A
further test asserts exactly one module imports `time` and that nothing it
measures reaches the document.

## 17. THE LOCALIZATION LEDGER (§31)

`LOCALIZATION_CHANGED` carries §32's full structure. Its emission rule differs
from a function state's on purpose: **a symptom appearing is itself the
event**, so a prior of `None` still emits. 19 scenarios, all chains verify.

## 18. §11's FOUR DEPENDENCY KINDS, AND WHAT THE SECOND PROFILE CHANGED

Redundancy had to move from **domains** to **components**. Two pumps are both
`ACTUATION`; a domain-level group cannot express "either pump will do". This
was found by building the pump skid, which is the entire value of a second
profile — neither the aircraft nor the bench has two interchangeable things in
one domain.

`REDUNDANCY_REDUCED` is emitted **alongside** `ALL_REQUIREMENTS_MET`, because
"eligible" and "eligible with no spare" are different operational facts.

## 19. GENERICITY, STILL TESTED THE ONLY WAY WORTH TESTING

Both the bench and the pump skid run in a **fresh interpreter** with a test
asserting neither `csia.v1_1` nor the aircraft profile ever appears in
`sys.modules`. Making that true required lazy PEP-562 `__getattr__` in the
profile and domain packages; the test failed first and the code was fixed.

A test parses the core modules' ASTs and asserts no platform noun appears in
any **identifier**. The first version matched source text and failed on
`description` (it contains "esc") — a test that fails on the wrong thing gets
weakened until it passes, so it now splits identifiers into words.

## 20. §41's THIRTEEN PROPERTIES

All thirteen are covered in `tests/test_v2_localization.py`. The one that
makes every other result mean anything is §41.4: no scenario name, no
identifying tag, and no distinctive word of any expectation string appears
anywhere in the evidence records, and `localize()` takes
`(spec, index, subject, predicates)` and nothing else — asserted by parsing
the AST, so no future edit can smuggle the scenario in.

## 21. COST (§43)

| phase | median µs/tick | max µs/tick |
|---|---|---|
| `api_build_and_evaluate` | 2745.4 | — |
| six domains through the supervisor | 747.1 | 982.4 |
| explanation | 87.3 | 167.2 |
| **localization** | **45.8** | — |
| ledger | 14.1 | 743.8 |
| internal typed ingest | 9.2 | — |

68 records and 9 symptoms per tick. The Final Rule's arithmetic: the decision
layer costs 46 µs against an interface that was costing 22 ms. Optimising the
decision first would have been optimising 0.2% of the problem.

## 22. THE AI SEAM IS DOCUMENTED AND NOT BUILT

No model is called and no code path in `csia/` reaches an AI system.
`AI_ANALYST_FUTURE_SPEC.md` records where such a component could attach and
the three things §34 forbids it: modifying function eligibility, issuing
control commands, and turning an unsupported hypothesis into a confirmed
cause. There is no back edge from the seam into the deterministic path, and
that is the whole safety argument.

## 23. WHAT IS STILL WRONG

1. **The dependency model is the ceiling on §13.** Two of set C's four causes
   are unreachable on this platform. The framework now says so instead of
   guessing, which is an improvement and not a fix.
2. **Hypothesis granularity is fixed by declaration.** `COMPUTE/estimator_
   stale` covers both "stopped" and "over budget", which is why D2 and D4
   collapse. Splitting them needs evidence that separates them, which does
   not exist here.
3. **No probability is attached to an ambiguous set.** Ranking survivors needs
   priors nobody has measured. §5 does not require it and none is invented.
4. **Three profiles, one author.** The genericity result is real but n=3 and
   all three were written by the person who wrote the framework — the same
   limitation Gate C had for the v1.1 consumer.
5. **Two synthetic profiles.** The bench and the pump skid contain invented
   numbers. No real bench or skid data exists in this repository.
6. **The matched sets are constructed, not observed.** A1–A4 are injections
   into a real v1.1 payload; the injections are mine. What is real is the
   v1.1 evidence they are injected into and the fact that no ground truth
   reaches the decision.
7. **No target-hardware measurement.** Every figure is CPython on a
   general-purpose host.
8. **Localization is per tick.** Onset order is in the ledger and unused,
   because using it needs state the domain contract forbids.

**Product maturity: M2, unchanged.** Phase C adds a decision layer and the
evidence that it decides honestly. It adds no evidence about a vehicle.

## 24. WHAT §44 PERMITS NEXT

The gate is passed, so the freeze on new domains lifts. The order that
follows from the results above is not "add five domains":

1. **Declare the real dependencies in the aircraft profile.** Set C's blind
   spot is a profile gap and it is the cheapest real improvement available.
2. **An estimator domain**, because set D's D2/D4 collapse is exactly the
   granularity an estimator domain would supply.
3. **Independent instrumentation before more inference.** Set B's floor of two
   is not solved by another domain; it is solved by a shaft observation. The
   bench already proves that.

---

## APPENDIX — PHASE C ARTIFACTS

| file | what it records |
|---|---|
| `CROSS_DOMAIN_SIGNATURE_MATRIX.csv` | 54 rows; every CAN_EXPLAIN names a mechanism and its evidence |
| `LOCALIZATION_RESULTS.csv` | every matched member, with subject, rejections and blind domains |
| `LOCALIZATION_LEDGER.json` | 19 scenarios' localization events, all chains verified |
| `EVIDENCE_SUBSET_RESULTS.csv` | §6's minimum resolving subsets, measurable predicates only |
| `PLUGIN_FAILURE_RESULTS.csv` | 12 injections; no healthy claim from any failed domain |
| `V2_PHASEC_COMPUTE.json` | per-phase cost and the ~2400× interface figure |
| `V2_PHASEC_GATE.json` | §42's verdict, with a reason for every non-qualifying set |
| `FUNCTION_REQUIREMENTS_V2.yaml` | §28's requirements as reviewable data, generated from the profiles |
| `INTERNAL_EXTERNAL_EQUIVALENCE.json` | 13,500 payloads, 0 mismatches |
| `DOMAIN_EVIDENCE_CONTRACTS/*.md` | six per-domain evidence contracts (§3) |
| `CROSS_DOMAIN_LOCALIZATION_SPEC.md` | §§2–6, 13, 26–27, 32, 39 |
| `FUNCTION_LOCALIZATION_SPEC.md` | §§1, 11–13, 28 |
| `MATCHED_SCENARIOS.md` | §§7–10 and the gate table |
| `INTERNAL_INTERFACE_SPEC.md` | §§15–20, 43 |
| `SECOND_GENERIC_PROFILE_SPEC.md` | §30 |
| `CONTROLLER_INTEGRATION_SPEC.md` | §§21–23, 31 |
| `AI_ANALYST_FUTURE_SPEC.md` | §§33–34, documented and not built |

All regenerated by `python engineering/v2/run_phase_c.py`.
