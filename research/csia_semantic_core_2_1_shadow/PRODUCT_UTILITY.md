# What 2.1 materially enables for SWORT

**2026-09-30. Part 52 of the shadow-validation brief.** Every row rests on a
measured case from this phase, not on the cleaner semantics alone. Where 2.1
costs the engineer something, the row says so.

## 1. By use

| use | what 2.1 does that frozen v2 cannot | would an engineer care? | would the reason trace save time? | would profile validation catch integration errors? | would explicit UNKNOWN prevent a false conclusion? |
|---|---|---|---|---|---|
| **flight-test debugging** | withholds a confident wrong cause, and says why. In MS_B5, v2.0 names the motor UNIQUE on 42 ticks when the RPM sensor is at fault; 2.1 withholds, keeps SENSOR/response_sensor, and names the reason (SAME_TICK_LOCALIZATION_RETAINS_ANOTHER_DOMAIN) | **yes**: the v2.0 answer sends the engineer to the wrong part | **yes**: the trace names the retained hypothesis and the unmeasurable refuter (`PHYSICAL_RESPONSE_NOMINAL_FALSE: None`), which is the probe to run next | partly: flight-test profiles are usually stable | **yes**: "could not look" (no shaft observation) is not reported as "nominal" |
| **SITL / HIL validation** | runs beside the frozen engine without authority (`ShadowRunner`), classifies every difference against ground truth, and records the profile digest per tick | **yes**, for anyone changing a profile or a producer: every change becomes a measured difference | **yes**: the difference record says which predicate changed, and which scope gap or fault caused it | **yes**: a misspelled function silently weakened 601 unit-ticks; the validator flags it before any run (PV7) | yes |
| **post-flight incident analysis** | replays a recorded v2.0 document under 2.1 without modifying it (`reason_historical_tick`), and splits "all refuted" from "one unconfirmed survivor" | yes, when an incident report must say what was and was not known | **yes**: the trace lists evidence used, evidence ignored as irrelevant, and conflicts not read | not relevant after the fact | **yes**: a missing telemetry channel is UNKNOWN, not "fine" (C2) |
| **onboard assurance** | **nothing yet.** 2.1 is not in C; admissibility does not exist, so stale evidence after a lane switch still produces a SUPPORTED false symptom (E1); and fault policy B is not adopted | not until those three close | — | the validator would gate the build | yes, once onboard |
| **maintenance troubleshooting** | the MS_B5 case again: v2.0's UNIQUE would replace a good motor. **The cost side:** in ACTUATOR_NO_RESPONSE and MS_B3, 2.1 keeps the RPM sensor open when physics (no current) already rules it out, so a technician might check a sensor needlessly (an ARTIFICIAL abstention until the signature gains that refuter) | yes, both ways | yes: the trace shows the retained hypothesis's refuter is unmeasurable, not refuted, which tells the technician how much weight to give it | — | yes |
| **integration testing** | the static validator: PV1-PV8, each backed by a failure it catches. On the shipped profiles it found 6 dead supporting-domain declarations and 7 declarations the function graph ignores | **yes**: this is the cheapest and most immediately usable piece of the phase | — | **yes**: 9 of 10 adversarial profile mutations caught. The one missed (a removed true edge) needs architecture extraction | — |

## 2. What 2.1 costs

- **About 2.6× the v2.0 reasoning step in desktop CPython** (trace off, median
  547 µs against 210 µs). It is irrelevant on the ground and unmeasured on a
  target.
- **More AMBIGUOUS answers.**
  - 278 correct UNIQUE ticks withheld across seven scenarios.
  - Two of those abstentions are necessary. **Five are artifacts of the
    declared model**, and cost an engineer's time until the profile or
    signature is fixed (`WEAKENED_UNIQUE_REVIEW.md`).
- **A dependence on a correct profile.**
  - 2.1 reasons from declared scope, so a wrong profile hurts it more than
    v2.0.
  - Mostly the hurt is underconfidence; over-connection causes false symptoms.
  - The validator is therefore not optional.

## 3. Verdict on usefulness

**2.1 is useful now, as a ground, SITL and replay tool:**
- it withholds the wrong answers v2.0 gives;
- it explains itself;
- it flags configuration errors.

**It is not yet useful onboard.**

**Two of its costs are fixable, and the fixes are known:**
- the five ARTIFICIAL abstentions: signature refuters and G-2;
- fault policy B.

That is what the next implementations target.
