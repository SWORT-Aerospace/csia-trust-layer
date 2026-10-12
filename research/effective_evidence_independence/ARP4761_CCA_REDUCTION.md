# REDUCTION TEST — ARP4761 COMMON-CAUSE / COMMON-MODE ANALYSIS

Item 15. **Verdict: UNRESOLVED. The standard was not obtained.**

---

## The question item 15 requires answering

> Does ARP4761 / ARP4761A require **runtime verification of realised
> independence**, or only **design-time demonstration that independence
> mechanisms are not defeated by identified common causes**?

## Decision rule, fixed in advance

| finding | consequence |
|---|---|
| ARP requires runtime verification of realised independence | `KILLED_BY_COMMON_CAUSE_ANALYSIS`. Stop |
| ARP is design-time only, **and** runtime evidence topology creates a class of dependence that a competent design-time CMA would not enumerate | candidate survives this test, provisionally |
| ARP is design-time only, **and** no such class can be exhibited | stop — item 15 |

## Status

The standard is paywalled and unreachable from this environment
(`REQUIRED_READING_MANIFEST.md` §0). The FAA cross-check material item 2 names
is on `faa.gov`, also unreachable.

**No verdict is recorded.** Item 30 forbids the sentence "we did not identify a
method that…" without a full-text audit, so it is not written here.

## What the source audit contributes to the eventual answer

This is evidence *for the second bullet of the decision rule*, and it is
deliberately stated as incomplete.

From `RUNTIME_TOPOLOGY_SOURCE_AUDIT.md`: ArduPilot's `VIBRATION` message
derives from `_first_usable_accel`, an index reassigned inside
`AP_InertialSensor::update()` every loop from `_accel_healthy[]`
(`AP_InertialSensor.cpp:2001-2006`), and the wire message carries no field
identifying the instance (`common.xml:6632-6641`).

A design-time CMA that enumerates "accel 0 and accel 1 fail from a common
cause" would be asking a different question from "the pair of channels a
consumer is comparing has silently become one channel". Whether ARP's
dependence diagrams already cover the second is exactly what cannot be answered
without the text.

**The counter-argument, which must be given equal weight:** the ArduPilot
switch happens *because* the autopilot declared accel 0 unhealthy. A design-time
CMA would list "loss of accel 0" as a condition and would require the
architecture to remain safe under it. If ARP's treatment of a redundancy
manager's reconfiguration already covers "the selector moved", then the
runtime observation adds nothing to the safety assessment and the candidate
reduces to CMA with a timestamp — which is precisely hostile Reviewer A's
objection, and it cannot be answered from here.

## What must be read

`REQUIRED_READING_MANIFEST.md` §1.1 — sections, and what each would decide.
