# The 2.1 decision trace (Phase J)

**2026-09-30.**

## What this trace is, and is not

It is a **semantic** trace: enough to answer why a decision came out as it
did. It is **not** a provenance architecture:
- no producer registry;
- no lineage beyond one tick;
- no correlation model;
- no persistence.

Worked examples are in `SEMANTIC_CORE_2_1_RESULTS.json` under
`J.examples`.

## Where each question is answered

| question | localization (`LocalizationResult.to_dict()`) | attribution (`AttributionResult.to_dict()`) |
|---|---|---|
| **why UNIQUE?** | — | `trace.why = EVERY_DECLARED_ALTERNATIVE_AFFIRMATIVELY_NOMINAL`. `trace.declared_alternatives` lists what could have explained it, and `trace.relevant_discriminators` lists the records that excluded each one |
| **why AMBIGUOUS?** | `trace.why`: `SEVERAL_SURVIVORS_SOME_CONFIRMED` or `SEVERAL_SURVIVORS_NONE_CONFIRMED`; `supported`, `unresolved` | `trace.why = UNIQUE_WITHHELD`, with `withheld_unique_because` (the C1 or F2 reason codes), `unexcluded_alternatives` and `localization_disagreement`. Or `SEVERAL_CANDIDATES`, or `SINGLE_CANDIDATE_NOTHING_NOMINAL_IN_ANOTHER_DOMAIN` |
| **why no consistent hypothesis / unsupported?** | outcome `NO_CONSISTENT_HYPOTHESIS`, with `trace.why = EVERY_DECLARED_HYPOTHESIS_REJECTED` and `rejected` (hypothesis, refuting predicate). Or `INSUFFICIENT_EVIDENCE` with reason `UNCONFIRMED_SURVIVOR` or `UNMODELLED` | `trace.why = NOTHING_ADVERSE`; `components_not_observed` |
| **which evidence was used?** | `trace.evidence_used`: every record read by a predicate that returned True or False. Per predicate, `trace.predicates[pid].read` | `candidates`, and `relevant_discriminators` |
| **which evidence was ignored, and why?** | `trace.ignored` maps each record to its reason: `OUT_OF_DECLARED_SCOPE` (C3) or `DECLARED_NOT_APPLICABLE`. `trace.unknown_inputs` lists records read only by predicates that could not decide. `trace.conflicts_not_read` lists keys where two records disagree (C6) | `trace.other_nominal` maps to `NOT_A_DECLARED_ALTERNATIVE`; `trace.non_attributable_ignored` lists derived records that are never candidates |
| **did a predicate error occur?** | `evaluation = PREDICATE_FAULT`. `predicate_errors` gives, per fault: `predicate`, `evaluated_as`, `subject`, `error_class` (`RAISED:<class>` or `NON_BOOL:<module.type>`) and `context` (symptom, hypotheses touched). There is never a traceback or a message | — |
| **was the evidence there at all?** | `evaluation = EVIDENCE_UNAVAILABLE`, with `evidence_unavailable`, which excludes faulted ids | `implicated_unavailable`, `implicated_unobserved` |
| **what did the scope rule do?** | `trace.scope_gaps`: `NO_DECLARED_PROCESS`, `NO_DECLARED_TIMING_CHANNEL`, `NO_DECLARED_LINK` or `NO_DECLARED_RESOURCE` | — |
| **was a hypothesis both confirmed and refuted?** (C7) | `trace.confirmed_and_refuted`: hypothesis, refuter, specific and shared confirmers | — |
| **does SUPPORTED rest on refuters that could not look?** (C7) | `trace.supported_with_unmeasured_refuters` | — |

At tick level, `evidence_handling.duplicates_collapsed` and
`evidence_handling.conflicting_keys_not_read` record what C6 did.

## A worked example: MS_B5_RESPONSE_SENSOR, final tick

The injected cause is the response sensor.

| | value |
|---|---|
| 2.0.0 | UNIQUE `ACTUATION/motor_0` |
| 2.1 `verdict` | AMBIGUOUS, candidates `ACTUATION/motor_0` |
| `withheld_unique_because` | `SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN` |
| `trace.localization_disagreement` | COMMAND_NO_RESPONSE and HIGH_CURRENT_LOW_RPM on motor_0 both retain `SENSOR/response_sensor` |
| `trace.declared_alternatives` | `COMMUNICATION/esc_can`, `POWER/battery` |
| `trace.other_nominal` | the gnss_serial and telemetry_radio link records, CPU, logger and csia process records, and the others. Each is marked `NOT_A_DECLARED_ALTERNATIVE`: these are the records 2.0.0 used to "exclude" SENSOR |
| `implicated_nominal` | `POWER/battery` |

## Cost

- **Size.** The full trace roughly doubles the JSON document per tick: mean
  7.7 KB against 4.0 KB. With `trace=False` the size is the same as 2.0.0.
- **What `trace=False` keeps.** The C7 entries, the outcome, the evaluation
  status and the fault list stay on.
- **What it drops.** The per-predicate read log goes (`PERFORMANCE.md`).
