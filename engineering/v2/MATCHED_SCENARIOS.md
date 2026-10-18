# MATCHED SCENARIO SETS

Phase C §§7–10, 39, 42. Definitions: `csia/v2/profiles/matched_scenarios.py`.
Results: `LOCALIZATION_RESULTS.csv`, `V2_PHASEC_GATE.json`.

A matched set is several scenarios that **produce the same symptom from
different causes**. It is the only construction that tests localization rather
than detection: if every member produced a different symptom, recognising the
symptom would be the whole answer.

§8's rule governs all of them:

> Do NOT include evidence you do not actually model.

Nothing below is confirmed by a predicate that was added to make a scenario
come out right. Where a set does not resolve, it is reported as not resolving.

---

## SET A — stale output, four causes (§7)

Symptom `OUTPUT_STALE` on channel `nav_solution`, total latency 88 ms in every
member. Four candidate domains initially; every member reduces to one.

| scenario | injected | result |
|---|---|---|
| `MS_A1_SENSOR_DELAY` | the source samples late | `SENSOR/source_slow` |
| `MS_A2_COMMUNICATION_DELAY` | the link delivers late | `COMMUNICATION/transport_delay` |
| `MS_A3_COMPUTE_DELAY` | the producer runs long | `COMPUTE/processing_delay` |
| `MS_A4_PROCESS_STALL` | the producer stops | `COMPUTE/process_stall` |

**4 members → 4 distinct hypotheses. The set qualifies under §42.**

A1 and A2 are the case the Final Rule is about. Both put their delay in the
same interval — between validity and arrival — and **no timestamp arithmetic
can separate them**. What separates them is the COMMUNICATION plugin's own
link evidence: `CHANNEL_LINK_NOMINAL` is `True` in A1 and refutes the
transport hypothesis, and `False` in A2 where it confirms it. The separation
is cross-domain by construction, not a smarter reading of one domain's data.

A3 and A4 are separated by `PRODUCER_PROCESS_HEALTHY`, which is a COMPUTE
observation about the producer reached through the channel's declared
dependency. A channel that declared no producer would leave the pair
ambiguous, and would say so.

## SET B — no actuator response, five causes (§8)

Symptom `COMMAND_NO_RESPONSE` on `motor_0`.

| scenario | injected | supported | verdict |
|---|---|---|---|
| `MS_B1_COMMAND_LOST` | command never delivered | `COMMUNICATION/command_not_delivered` | AMBIGUOUS |
| `MS_B2_POWER_PATH` | actuator rail out of tolerance | `POWER/path_unavailable` | AMBIGUOUS |
| `MS_B3_DRIVE_NO_CURRENT` | drive passes no current | `ACTUATION/drive_no_current` | AMBIGUOUS |
| `MS_B4_MECHANICAL` | shaft jammed | `ACTUATION/mechanical` **and** `SENSOR/response_sensor` | AMBIGUOUS |
| `MS_B5_RESPONSE_SENSOR` | speed channel dead | `ACTUATION/mechanical` **and** `SENSOR/response_sensor` | AMBIGUOUS |

**The set does not qualify. No member reaches `SUPPORTED`, and that is the
correct answer for this platform.**

Every member carries `SENSOR/response_sensor` as a live alternative because
the multirotor has **no independent physical channel** on the shaft. There is
no measurement that could refute it, so it can never be eliminated, and the
candidate set has an honest floor of two.

B4 and B5 are the sharpest case. Their evidence is identical — current
present, no measured motion — so the framework returns the identical result,
and both hypotheses are **equally supported**. The first implementation gave
the confirming predicate only to `ACTUATION/mechanical`, which made B5's own
cause read as "unresolved" while its rival read "supported" off the same
observation. That asymmetry was an artifact of which hypothesis I had written
a `confirmed_by` for, not a fact about the vehicle.

## SET B (BENCH) — the same five causes, instrumented (§8, §37)

The electric motor test stand runs the **same framework and the same symptom
spec** with one addition: an independent torque channel.

| scenario | supported | verdict |
|---|---|---|
| `MS_TS_B4_MECHANICAL` | `ACTUATION/mechanical` | SUPPORTED |
| `MS_TS_B5_RESPONSE_SENSOR` | `SENSOR/response_sensor` | SUPPORTED |

**2 members → 2 distinct hypotheses. The set qualifies under §42.**

This pair is the most useful result in Phase C. Nothing about the reasoning
changed between the aircraft and the bench — same hypotheses, same predicates,
same elimination. The bench resolves what the multirotor cannot **because it
is instrumented for it**. Resolving power is a property of the instrumentation,
not of the algorithm, and the two sets side by side are the evidence for that.

## SET C — multiple sensors degraded, four causes (§9, §13)

Symptom `MULTIPLE_SENSORS_DEGRADED`. The only real v1.1 payload with two
adverse sources has `battery` and `motor_esc`. They share a POWER node; the
battery declares no link, and neither declares a compute node.

| scenario | injected | supported | verdict |
|---|---|---|---|
| `MS_C1_INDEPENDENT` | nothing shared is adverse | — | AMBIGUOUS |
| `MS_C2_SHARED_POWER` | the shared power node sags | `POWER/shared_node` | AMBIGUOUS |
| `MS_C3_LINKS_DOWN_NOT_SHARED` | both links down, not shared | — | AMBIGUOUS |
| `MS_C4_CPU_SATURATED_NOT_SHARED` | CPU saturated, no declared dependency | — | AMBIGUOUS |

**The set does not qualify, and the reason is a model gap this run exposed.**

The first version of these four reported `SENSOR/independent_faults` as
`SUPPORTED` for C1, C3 and C4 — reading "no dependency recorded in this
domain" as "they do not share one here". That is a confident answer produced
from an absence, and it made C4 look like a pass when the framework had simply
not looked at the injected cause. The shared-dependency predicates now return
**not measurable** for a domain the model does not cover, and
`dependency_model_blind_to` in the results CSV names it: `COMMUNICATION`,
`COMPUTE`, `TIMING`.

C2 still isolates the common cause it *can* see, and refutes the independent
explanation by name. Everything else in the set is honestly unresolved.

Closing the gap is a **profile** change — declaring the real sampling and bus
dependencies of each source — not a framework change. The framework already
does the right thing with a complete dependency model, which C2 demonstrates.

## SET D — position function unavailable, four causes (§10)

Symptom `POSITION_UNAVAILABLE`, subject = the function. Three functions
exhibit it per scenario (`COARSE_NAVIGATION`, `POSITION_HOLD`,
`PRECISION_NAVIGATION`), all with the same result.

| scenario | injected | result |
|---|---|---|
| `MS_D1_NAV_SOURCE` | GNSS fix lost | `SENSOR/navigation_source_invalid` |
| `MS_D2_ESTIMATOR_STALE` | estimator stopped | `COMPUTE/estimator_stale` |
| `MS_D3_COMM_STARVATION` | GNSS link down | `COMMUNICATION/starvation` |
| `MS_D4_COMPUTE_DEADLINE` | estimator over its budget | `COMPUTE/estimator_stale` |

**4 members → 3 distinct hypotheses. The set does not qualify under the strict
reading of §42, because D2 and D4 were not discriminated from each other.**

That is a true property of the evidence rather than a defect to be tuned away:
a compute segment that blows its own budget **is** a stale estimator, and this
platform produces nothing that separates "stopped" from "too slow" at the
function level. D4 also demonstrates §27 — `TIMING/deadline_violation` is
refuted by `NO_TIMING_SEGMENT_OVER_BUDGET_FALSE` rather than co-reported, so
one overrun is not counted as two faults.

---

## §42 gate result

Criterion, read strictly: at least two matched sets where multiple domains
could explain the symptom initially and evidence reduced **each** member to a
**different** supported hypothesis, with no ground-truth access. "Each" is
injective over the whole set — a set where two members land on the same
hypothesis has not discriminated those two.

| set | members | reduced | distinct | qualifies |
|---|---|---|---|---|
| `A_STALE_OUTPUT` | 4 | 4 | 4 | **yes** |
| `B_ACTUATOR_RESPONSE` | 5 | 0 | 0 | no — no member reached SUPPORTED |
| `B_ACTUATOR_RESPONSE_BENCH` | 2 | 2 | 2 | **yes** |
| `C_MULTI_SENSOR` | 4 | 0 | 0 | no — the dependency model is blind to two of the four causes |
| `D_POSITION_FUNCTION` | 4 | 4 | 3 | no — D2 and D4 are the same hypothesis |

**Verdict: `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL`** on two qualifying sets.

## No ground truth reaches the decision

A test asserts that no scenario name, no identifying tag, and no distinctive
word of any expectation string appears anywhere in the evidence records, and
that `localize()` takes `(spec, index, subject, predicates)` and nothing else.
Without that, every table above would be a lookup wearing a diagnosis costume.
