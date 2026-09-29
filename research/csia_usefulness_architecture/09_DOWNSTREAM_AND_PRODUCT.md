# Downstream output and product value (Phases 17, 18, 36, 38)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

**Method caveat.** No customer, operator or maintainer was interviewed. The
consumer needs below are derived from:

- the repository's own recorded failures (for example SR-004 and SR-005:
  an alarm that reached nothing; S018);
- the role separation in `08_PERFORMANCE_SAFETY_BOUNDARY.md` §2;
- what each consumer can act on.

They are hypotheses about need, to be tested with real users (Horizon 2 in
`15_IMPROVEMENTS_AND_ROADMAP.md`).

## 1. Phase 17: what each consumer can use

| consumer | what it can act on | what it must not receive | minimal content |
|---|---|---|---|
| flight controller | nothing: it must not consume CSIA (§2 of the boundary file) | anything | none |
| mission manager | whether a function is justified, why not, and whether waiting helps | raw evidence | per-function state, reason code, information need, age |
| RTA / safety layer | whether an assumption it relies on is supported by admissible evidence, failing closed | ranked causes | per-assumption supported / not supported / UNKNOWN |
| ground operator | what is wrong, what is ambiguous, where the evidence disagrees, what to check | internal ids without meaning | per-symptom state, candidates, disagreement explanation, plain-language render |
| maintenance | which components carry latched adverse findings, and which producers are unhealthy | per-tick churn | latched findings, producer health history, candidate components with evidence |
| engineering logs / research | everything, replayably | nothing withheld | full envelopes, admissibility decisions, context transitions, traces, ledger |

## 2. Phase 36: the assurance state (schema 2.1.0, additive)

A compact core. It is additive to the v2 `2.0.0` document (S005), which stays
unchanged and is produced by a compatibility view.

```
assurance_state (2.1.0)
  schema_version        "2.1.0"
  t                     vehicle time
  config_hash           configuration the state holds under
  context_epoch         epoch vector reference
  system                NORMAL | DEGRADED | RESTRICTED | UNAVAILABLE     (unchanged, S005)
  functions             { name: { state, limiting_domain, reason_code } } (unchanged states, S008)
  findings              [ { symptom, subject,
                            status: SUPPORTED | AMBIGUOUS | INSUFFICIENT_EVIDENCE |
                                    NO_CONSISTENT_HYPOTHESIS | EVIDENCE_DISAGREEMENT | NO_EVIDENCE,
                            supported[], unresolved[], disagreement_id?, age_s } ]
  implicated_without_evidence  [ component ids ]
  inadmissible_summary  { STALE: n, NOT_APPLICABLE: n, INVALIDATED: n,
                          PRODUCER_NOT_VALID: n, UNKNOWN: n }
  information_need      [ { needed_for: symptom/hypotheses, relation, blocked_by: status } ]
  producer_health       { producer_id: VALID | NOT_VALID(reason) }   (only non-VALID listed)
  trace_ref             hash of the decision trace (12_TARGET_ARCHITECTURE.md section 7)
```

**What is left out.**

- There is no score, percentage or confidence number. That is v2's rule, and
  it is kept (S005).
- There is no command.
- There is no internal predicate code in the onboard view.

**The four views.**

| view | includes | target size |
|---|---|---|
| ONBOARD | `system`, `functions`, `findings` (status and ids only), `information_need`, `config_hash`, `trace_ref` | ≤ 1 KB per update (target, to be measured) |
| GROUND OPERATOR | onboard + disagreement explanations + a plain-language render (the existing `render()`, S002) | as needed |
| MAINTENANCE | + latched findings, producer health history, `implicated_without_evidence` | per flight |
| RESEARCH / AUDIT | + full envelopes, admissibility decisions, context transitions, full traces | per flight |

## 3. Phase 18: use cases

Each use case is scored 0-5; higher is better on every column. For
implementation cost, 5 = cheapest.

| # | use case | customer value | technical feasibility | competitive differentiation | implementation cost | regulatory value | total /25 | note |
|---|---|---|---|---|---|---|---|---|
| 1 | onboard autonomous UAV assurance | 4 | 2 | 2 | 1 | 3 | 12 | maturity M2, not flight software (S046); no target build (S020); onboard autopilot monitors already exist (S034) |
| 2 | post-flight engineering diagnosis | 4 | 4 | 3 | 4 | 2 | 17 | deterministic replay and ledger already exist (S009); ULog and MAVLink ingest exist |
| 3 | fleet health monitoring | 3 | 3 | 2 | 3 | 2 | 13 | needs many flights; the public-log study is blocked by egress (S029) |
| 4 | flight-test instrumentation | 4 | 4 | 3 | 3 | 3 | 17 | disagreement and invalidation are exactly what flight-test engineers chase after configuration changes |
| 5 | certification evidence generation | 3 | 2 | 2 | 2 | 4 | 13 | traces help; "certification" claims must not be made (§4 below) |
| 6 | maintenance troubleshooting | 3 | 3 | 2 | 3 | 2 | 13 | latched findings and candidates; needs OEM fault models |
| 7 | integration testing | 4 | 5 | 3 | 4 | 2 | 18 | contracts plus admissibility catch evidence used outside its conditions after a software or configuration change; runs on SITL |
| 8 | HIL validation | 4 | 4 | 3 | 3 | 3 | 17 | the same analyzer on HIL logs; the E2M bench exception exists but is not run (S029) |

**Onboard is not the most valuable first surface.** It scores lowest on
feasibility and cost today.

## 4. Phase 38: product surfaces

Scored 0-5 on eight columns, where higher is better:

- integration difficulty: 5 = easy;
- liability: 5 = low exposure;
- competition: 5 = little direct competition;
- time to MVP: 5 = fast.

| surface | customer pain | willingness to pay | integration difficulty | technical readiness | liability | competition | SWORT advantage | time to MVP | total /40 |
|---|---|---|---|---|---|---|---|---|---|
| A. onboard assurance runtime | 4 | 3 | 1 | 1 | 1 | 2 | 2 | 1 | 15 |
| B. flight-test assurance tool | 4 | 3 | 3 | 3 | 4 | 3 | 3 | 3 | 26 |
| C. HIL / SITL validation tool | 4 | 3 | 4 | 4 | 5 | 3 | 4 | 4 | 31 |
| D. post-flight evidence analyzer | 4 | 3 | 4 | 4 | 5 | 2 | 3 | 4 | 29 |
| E. fleet health / incident triage | 3 | 3 | 2 | 2 | 4 | 2 | 2 | 2 | 20 |
| F. integration-test tool | 4 | 3 | 4 | 4 | 5 | 3 | 4 | 4 | 31 |
| G. certification / assurance evidence tooling | 3 | 3 | 2 | 2 | 3 | 2 | 2 | 2 | 19 |

**Why C and F rank highest.**

- **Integration difficulty.** They run on logs and simulators the customer
  already has.
- **Technical readiness.** Deterministic replay, the ledger, ULog ingestion
  and the XSYS-001 apparatus exist.
- **Liability.** Nothing flies on their output.
- **SWORT advantage.** A built PX4 SIH apparatus with an actuator-effectiveness
  patch and a preregistered matched-set method, plus ArduPilot 4.8 SITL
  (S029, S014).
- **Competition.** Log viewers and autopilot analyzers exist. None that was
  found reports **evidence admissibility across configuration changes**.
  That is a weak differentiation claim, stated as such.

**The recommended first surface is one tool that serves C and F: a
"configuration-change evidence analyzer" for SITL, HIL and integration test
logs.**

It replays a log, or a pair of logs before and after a software or
configuration change, through the admissibility layer. It reports:

- which evidence was used outside its declared conditions;
- which disagreements appeared;
- what the decision trace was.

Surface D, the post-flight analyzer, is the same tool on flight logs. A
follows only after the ladder's HIL and flight levels
(`13_MIGRATION_AND_VALIDATION.md`).

**Novelty was not a criterion.** Certification tooling (G) is **not** first:
any output there would be read as a certification claim, which CSIA cannot
support (`10_KEEP_REPLACE_TABLE.md`, SupportCertificate row).
