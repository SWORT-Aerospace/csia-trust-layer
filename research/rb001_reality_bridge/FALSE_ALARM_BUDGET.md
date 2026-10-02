# False-alarm budget (RB-001 Part 15)

**2026-10-02.** **Fixed before any physical fault evaluation.**

## 1. The intended use the numbers come from

CSIA is an **offboard analyzer**:
- an engineer runs it on flight logs after the fact, to find out what
  happened, what was and was not observed, and whether a cause is
  justified;
- it has no control authority, and nothing acts on its output in flight;
- **the cost of a false output is therefore engineering time and trust.**

The three outputs cost different amounts:

| output | what a false one costs the engineer | severity |
|---|---|---|
| candidate EVENT ("something may have started here") | a few seconds: read the line, see the analysis dismissed it | low; it erodes attention if there are many |
| SYMPTOM (e.g. COMMAND_NO_RESPONSE on motor 2) | an inspection of a healthy motor, ESC or wiring: tens of minutes to hours | high |
| ATTRIBUTION (a UNIQUE cause) | a wrong part replaced, or a real cause not looked for; it is also the gate to any future onboard use (FORGE, Part 34) | **critical** |

## 2. The budget

| output | target, per hour of in-flight log | reasoning | demonstrated so far |
|---|---|---|---|
| candidate events, dismissed | **≤ 6 / h** | one dismissed line per ten minutes of flight is reviewable; more trains the reader to skip the list | hover: 0 / h over 0.63 h (XSYS-001, 2.3 hold segments); **maneuvering: 287 / h** (2.3, `FALSE_POSITIVES.md`), **over budget by about 50x** |
| false symptoms | **≤ 0.1 / h** (one per ten flight-hours) | a false symptom costs an inspection; a fleet engineer reviewing a few hours of logs a week should see one a month at most | 0 over about 0.5 h of nominal and maneuvering SITL with the final 2.3 code. By the rule of three, 0 in T hours bounds the rate below 3 / T at 95 %, here below about 6 / h. **Not demonstrated.** |
| false attribution (wrong UNIQUE) | **0 known**, and ≤ 0.01 / h to be demonstrated before any onboard discussion | a wrong UNIQUE is the one output that can mislead decisively; Part 34's FORGE gate demands zero known | 0 ever (XSYS-001, 2.2, 2.3, RB-001 SITL). Stock evidence yields AMBIGUOUS, never UNIQUE, so the opportunity has been small. **Not demonstrated at 0.01 / h.** |

## 3. How much nominal data a demonstration needs

**The bound.** For a rate claim with zero observed events, the 95 % upper
bound is 3 / T, where T is the nominal hours. So:

| claim | nominal in-flight hours needed with zero events |
|---|---|
| events ≤ 6 / h | 0.5 h (and must actually observe ≤ 6 / h; a measured rate needs about 3 h to fix to ±30 %) |
| false symptoms ≤ 0.1 / h | **30 h** |
| wrong UNIQUE ≤ 0.01 / h | **300 h** |

**What follows.** Neither the symptom nor the attribution budget can be
demonstrated in SITL hours or on a bench. They need the RB5/RB6 nominal
corpus, or a fleet's logs. RB-001 states the targets now so that no later
result can be called "good enough" after the fact.

## 4. Rules that come with the budget

**Event rates are measured, not tuned, until the nominal corpus is
frozen.** The brief, Part 16: event-discovery tuning waits for a frozen real
nominal corpus, and then uses calibration flights, never evaluation ones.

**A symptom is counted at any tick, not at the end of the log.** 2.3's V5
and V6 showed that end-of-log results hide transient false symptoms.

**Counts are per in-flight hour,** armed and not landed, and per flight.

**A budget breach is a finding, not a tuning target.** The response is a
validity condition or a different statistic, chosen on development data and
tested on new data, as in the maneuver study.
