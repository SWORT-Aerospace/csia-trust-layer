# FUNCTION ELIGIBILITY SPEC — Phase 4 §§6–13

The question this layer answers is not *"is the GPS healthy"*. It is
**"is this particular vehicle function still justifiable on the evidence that
exists?"**

Implementation: `csia/v1_1/eligibility.py`. Requirements:
`FUNCTION_REQUIREMENTS.yaml`. Codes: `REASON_CODES.yaml`.

---

## 1. PREREGISTRATION — §12, GATE C

`FUNCTION_REQUIREMENTS.yaml` was written and hashed **before any mechanism was
evaluated**.

    sha256  62d9f1f35ce414de57a7dd3d48b2983828de03b408537858ccfde836f4382962

That hash is a constant in `engineering/v1_1/phase4/run_p4b.py`. The runner
**refuses to run** if the file no longer matches, and a test asserts the same.
Adjusting a requirement after seeing an outcome therefore requires reissuing
the hash in a commit that says why — it cannot be done quietly.

## 2. THERE IS NOT ONE NEW THRESHOLD

Every trust requirement names a field of the **frozen** `FailsafeConfig` and
inherits its value:

| requirement | inherits | value |
|---|---|---:|
| GNSS position quality | `nav_caution` | 0.75 |
| heading quality | `heading_caution` | 0.60 |
| attitude, on `max(imu0, imu1)` | `att_caution` | 0.82 |
| attitude, last-resort | `att_emergency` | 0.70 |
| escalation dwell | `dwell_up` | 1.0 s |
| relaxation dwell | `dwell_down` | 5.0 s |

Inheritance is **by name, resolved at construction** — `_Threshold.resolve`
looks the attribute up on `FailsafeConfig` and raises if it does not exist. No
value is copied, so the two cannot drift, and a test asserts every `inherits`
in the YAML resolves.

§12 permits a threshold only when it "already comes from a declared
engineering requirement". These are the v1 safety path's own thresholds,
already frozen and already carrying the failsafe state machine.

**Where no declared threshold exists, none is invented.**
`INERTIAL_CONTINUATION` requires barometer *freshness* and states explicitly
that it gates on no barometer trust value, because `FailsafeConfig` declares
no barometer threshold and making one up is the forbidden tuned number.

## 3. THE FUNCTION SET — FIVE SPECIFIED, ONE OMITTED

| function | needs | support policy | assurance boundary |
|---|---|---|---|
| `COARSE_NAVIGATION` | gps | TOLERATE_AMBIGUITY | CRITICAL |
| `POSITION_HOLD` | gps, baro, one IMU | TOLERATE_AMBIGUITY | CRITICAL |
| `PRECISION_NAVIGATION` | gps, mag, one IMU | **REQUIRE_IDENTIFIABLE** | CAUTION |
| `GEOFENCE_SUPPORT` | gps | **REQUIRE_IDENTIFIABLE** | CRITICAL |
| `INERTIAL_CONTINUATION` | baro, one IMU — **no GNSS** | TOLERATE_AMBIGUITY | EMERGENCY |

**`PRECISION_LANDING` is omitted**, per §6's instruction to omit rather than
invent. It requires a landing-reference sensor — rangefinder, optical flow or
beacon — and none exists in the node set, in the 11 relations, or in any
adapter channel. A requirement written from the available signals would
describe a different function and label it precision landing.

`GEOFENCE_SUPPORT` is deliberately **stricter than `COARSE_NAVIGATION` on the
same inputs**: a boundary decision made on a spoofed position is worse than no
boundary decision, because it reports "inside" with authority while the
vehicle leaves.

## 4. INPUTS — §9, ENFORCED BY THE TYPE

`Observation` is a frozen dataclass whose fields are exactly §9's permitted
inputs: `t`, `trust`, `fresh`, `observable`, `relation_gates`,
`sequential_alarms`, `leader`, `posterior`, `support_state`,
`leader_identifiable`, `non_identifiable_against`, `prior_sensitive`,
`neutral_leader`, `active_evidence_count`, `discriminating_evidence`,
`assurance_level`, `missing_reason`.

There is **no field** for a scenario name, an injected-fault label, ground
truth, a filename or a simulator parameter. A policy that tried to consult one
would not run, and a test asserts the field set.

Freshness is the **frozen layer's** view, per `STALENESS_LAYER_AUDIT.md` §5;
`missing_reason` only refines which `SOURCE_ABSENT_*` code is emitted.

## 5. THE RULES — DETERMINISTIC AND TOTAL

Every condition is evaluated, **all** fired codes are collected, and the state
is the most restrictive among them. Collecting rather than short-circuiting is
deliberate: §10 needs to show that the support rule fires *even when* a
freshness rule fires too.

    UNKNOWN     (3)  the policy cannot evaluate its own requirements
    INELIGIBLE  (2)  a stated requirement is not met
    DEGRADED    (1)  available, with a stated reduction in evidence
    ELIGIBLE    (0)  every stated requirement is met

| condition | code | state |
|---|---|---|
| a required node is absent from the input entirely | `REQUIRED_SOURCE_NOT_OBSERVABLE` | UNKNOWN |
| REQUIRE_IDENTIFIABLE and no active evidence terms at all | `SUPPORT_ANALYSIS_UNAVAILABLE` | UNKNOWN |
| a required source is not fresh | `REQUIRED_SOURCE_NOT_FRESH` (or a `SOURCE_ABSENT_*` refinement) | INELIGIBLE |
| no member of a redundant group is available | `REQUIRED_SOURCE_GROUP_EXHAUSTED` | INELIGIBLE |
| some member of a redundant group is unavailable | `REDUNDANT_SOURCE_UNAVAILABLE` | DEGRADED |
| none of the required relations is gated in | `REQUIRED_RELATION_NOT_APPLICABLE` | INELIGIBLE |
| trust below the inherited requirement | `TRUST_BELOW_INHERITED_REQUIREMENT` | INELIGIBLE |
| assurance beyond the declared boundary | `ASSURANCE_BEYOND_FUNCTION_BOUNDARY` | INELIGIBLE |
| a sensitive hypothesis cannot be ruled out | `SUPPORT_LOST_FOR_REQUIRED_INFORMATION` | **policy-dependent** |
| the leader **is** a sensitive hypothesis, and identified | `NAMED_CAUSE_AFFECTS_FUNCTION` | DEGRADED |
| the naming of a sensitive hypothesis is prior-driven | `PRIOR_SENSITIVE_LEADER` | DEGRADED |
| sequential alarm on a required source | `SEQUENTIAL_ALARM_ON_REQUIRED_SOURCE` | DEGRADED |
| nothing fired | `ALL_REQUIREMENTS_MET` | ELIGIBLE |

`SUPPORT_LOST_FOR_REQUIRED_INFORMATION` is **INELIGIBLE** for a
`REQUIRE_IDENTIFIABLE` function and **DEGRADED** for a `TOLERATE_AMBIGUITY`
one. The same evidence means different things to a function that assumes its
position is correct and one that does not.

**`NAMED_CAUSE_AFFECTS_FUNCTION` is DEGRADED, not INELIGIBLE, and that is the
point of §32.** A named, bounded fault with working redundancy is a different
situation from an unresolved one, and collapsing them would mark every
single-IMU issue as a navigation failure.

**A sequential alarm degrades and never attributes** (§11). The CUSUM says the
evidence changed; the diagnosis is the only thing permitted to say why. No
code path converts an alarm into a cause.

## 6. A RULE THAT WAS WRONG, AND WAS CHANGED AFTER SEEING RESULTS

Recorded rather than quietly fixed.

The first implementation fired `PRIOR_SENSITIVE_LEADER` whenever
`prior_sensitive` was true, for every `REQUIRE_IDENTIFIABLE` function. The
first evaluation showed it degrading `PRECISION_NAVIGATION` and
`GEOFENCE_SUPPORT` for 310 ticks of `IMU0_BIAS_DRIFT`, on a leader
(`imu0_bias_drift`) that neither function declares sensitive.

That is not what the requirement says. §7's wording is "no unresolved
ambiguity affecting **the required information**", and a prior-driven name for
a fault the function does not depend on does not affect it. The rule now fires
only when the leader **or** the uniform-prior leader is one of the function's
`sensitive_hypotheses`.

Effect, before → after:

| | before | after |
|---|---|---|
| transitions, all mechanisms | 90 | **83** |
| `IMU0_BIAS_DRIFT` → `PRECISION_NAVIGATION` | 310 DEGRADED | **0** |
| `IMU0_BIAS_DRIFT` → `GEOFENCE_SUPPORT` | 310 DEGRADED | **0** |
| `DUAL_IMU_FAILURE` → `PRECISION_NAVIGATION` | 119 DEGRADED | **0** |
| `DUAL_IMU_FAILURE` → `GEOFENCE_SUPPORT` | 182 DEGRADED | **0** |
| every other cell, all nine mechanisms | — | unchanged |

Nothing moved out of `INELIGIBLE` and nothing moved into `ELIGIBLE` that was
`INELIGIBLE`: every changed cell is a `DEGRADED` → `ELIGIBLE` reclassification
on an IMU mechanism, which is the only place the over-firing reached.

`FUNCTION_REQUIREMENTS.yaml` did **not** change: the sensitive-hypothesis
lists were always right, and the evaluation rule was reading past them. The
preregistration hash is therefore the original one, and this correction is a
change to the spec's rule table, disclosed here.

The honest reading is that this was found because a result looked wrong, which
is exactly the situation where a rule change needs disclosing rather than
absorbing.

## 7. DWELL — §30

Eligibility inherits the frozen failsafe hysteresis: escalation to a more
restrictive state requires `dwell_up` (1.0 s) of persistence; relaxation
requires `dwell_down` (5.0 s). Same declared numbers, same discipline as the
safety path, so a function cannot chatter on a threshold crossing.

The dwell is visible in the results and is the reason startup lasts 201 ticks
rather than 76 — see §8.

## 8. THE STARTUP WINDOW, EXACTLY EXPLAINED — §30

On **every** mechanism, the GNSS-dependent functions begin restricted and
settle at **t = 8.04 s**, after exactly **201 ticks**:

    76 ticks   genuine: before GPS is fresh the leader cannot be separated
               from `gps_fault`, so `SUPPORT_LOST_FOR_REQUIRED_INFORMATION`
               fires. This is the same 76-tick window Phase 2 measured on
               every scenario including `clean`.
    125 ticks  dwell_down (5.0 s at 25 Hz), the inherited relaxation delay.
    ---------
    201 ticks  = 8.04 s.  One transition per function. No oscillation.

`COARSE_NAVIGATION` spends those ticks DEGRADED rather than INELIGIBLE because
it is `TOLERATE_AMBIGUITY`. `INERTIAL_CONTINUATION` is unaffected — it does
not require GNSS, which is the whole point of it.

**This is initialisation, not a defect, and it is not a false alarm rate.**

## 9. WHAT A POLICY MAY NOT DO

- **Read a high posterior as eligibility.** §10, enforced by
  `SUPPORT_LOST_FOR_REQUIRED_INFORMATION` and by a regression test that holds
  GNSS *fresh and trusted* while support is lost, so the freshness rule cannot
  be what produces the result.
- **Read a sequential alarm as a cause.** §11.
- **Read `UNKNOWN` fault modelling.** Not implemented (§34). The eligibility
  state also spelled `UNKNOWN` is a different thing and never shares a field.
- **Learn anything.** Deterministic tables only.

## 10. LIMITS OF THIS EVALUATION

- **`REQUIRED_SOURCE_NOT_OBSERVABLE` never fires in the catalogue.** Every
  node is always present in the deterministic scenarios, so UNKNOWN is
  exercised by a unit test on a synthetic observation, not claimed as scenario
  coverage.
- **`SOURCE_ABSENT_*` refinements never fire in the catalogue.** The scenario
  path does not run the ingest layer, so `missing_reason` is empty and the
  generic `REQUIRED_SOURCE_NOT_FRESH` is emitted. The refinement is covered by
  a unit test and by the Phase 1 adapter regression (§33).
- **No GNSS step mechanism exists** (Phase 3B §32). The ramp results do not
  cover steps.
- **Deterministic simulation only.** No HIL, no flight, and the clean control
  is a replay control rather than a field false-alarm rate.
