# Phase 2: failure-mode analysis of CSIA itself

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`. The full table, 33 failure modes, is `CSIA_FMEA.csv`.

**Scope.** This treats CSIA as a component that can fail. It extends, and
does not replace, the v0.7 FMEA of the v1 monitor (`docs/FMEA.md`, F1-F10;
S019).

## 1. Scales

No probabilities are known, so none are invented. Every rating is
qualitative.

| column | values | meaning |
|---|---|---|
| SEVERITY | HIGH, MEDIUM, LOW | HIGH: a wrong cause, a wrong function state or a false exoneration can reach a consumer. MEDIUM: wrong or missing explanation, no wrong state. LOW: cost or clarity only |
| LIKELIHOOD | OBSERVED, PLAUSIBLE, REMOTE, UNKNOWN | OBSERVED: seen in this repository's own results, failure ledger or probes. PLAUSIBLE: the mechanism exists in current code but has not been exercised |
| DETECTABILITY | HIGH, MEDIUM, LOW | LOW means the failure is **silent**: nothing in current outputs distinguishes it from correct behaviour |
| TESTABILITY | UNIT, REPLAY, SITL, HIL, FLIGHT | the cheapest level at which the failure can be reproduced |

## 2. The failure modes that matter most

These are HIGH severity with LOW detectability, and each is either OBSERVED
or has its mechanism present in current code.

| id | failure mode | why it ranks here |
|---|---|---|
| FM-02 / FM-11 | evidence used after a configuration or controller transition changed its meaning | **observed**: 55/55 wrong in the XSYS-001 negative control (S014); v2 has no context at all (S004) |
| FM-04 / FM-08 | a producer used outside its assumptions or validated region | nothing declares the assumptions; the Trust Contract validity domain exists but is not wired in (S023) |
| FM-20 | an irrelevant nominal record licenses a unique attribution | **observed by probe** in this review (S044a); pinned by a current test (S037) |
| FM-06 / FM-19 | correlated or self-derived evidence eliminates the true hypothesis | no refutation-independence rule exists (S002) |
| FM-28 | absence of an alarm treated as affirmative health | the same mechanism as the XSYS-001 exoneration, generalised (S014) |
| FM-10 | an estimator reset or lane switch spans accumulated evidence | fielded autopilots already publish the reset provenance, and CSIA does not read it (S055, S056) |
| FM-33 | invalidation lifts a restriction without new evidence | a risk **created by** the architecture this review proposes; it must be designed out from the start |

## 3. What already mitigates, and should be kept

| mitigation | failure modes it covers | source |
|---|---|---|
| three-valued predicates: "not measurable" eliminates nothing | FM-09 partly; FM-21 in the fail-safe direction | S002 |
| categorical records, no fused score | FM-07, FM-14 partly | S001, S005 |
| plugin supervision: a failed plugin emits UNAVAILABLE | FM-15 partly | S007 |
| UNKNOWN outranks INELIGIBLE | FM-33 partly | S008 |
| overlay may only raise urgency | FM-33 pattern | S028 |
| ledger hash chain and deterministic replay | FM-16 partly; FM-32 partly | S009 |
| output firewall default-deny; advisory by default | FM-31 | S021, S022 |

## 4. Failure modes this review adds to the brief's list

These are FM-19 to FM-33. Each comes from a recorded failure in this
repository (S018), from the probe (S044) or from a mechanism read in code.

- FM-19: self-referential exoneration.
- FM-20: irrelevant discriminator.
- FM-21: predicate error hidden as not measurable.
- FM-22: overloaded verdict misread.
- FM-23: alarm and capability layers disagree.
- FM-24: a machine fed its own output.
- FM-25: a justification asserts properties it never checked.
- FM-26: negligible input licenses support.
- FM-27: declared but unimplemented contract clause.
- FM-28: absence-of-alarm treated as nominal.
- FM-29: invisible topology change.
- FM-30: invalidation storm.
- FM-31: actuation wiring.
- FM-32: replay divergence.
- FM-33: invalidation lifting a restriction.

## 5. How the FMEA drives the rest of the package

Every field proposed for the evidence record (`EVIDENCE_RECORD_V2_FIELDS.csv`)
and every improvement (`IMPROVEMENT_SCORES.csv`) must cite at least one FM id
here. A field or feature that prevents none is not proposed.
