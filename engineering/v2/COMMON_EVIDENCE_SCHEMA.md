# COMMON EVIDENCE SCHEMA — v2 §3

The one object every domain emits. Implementation: `csia/v2/evidence.py`.

**No novelty is claimed here or anywhere in v2** (§39). This is product
architecture: a common record shape so heterogeneous domains can be compared
by the same machinery.

---

## 1. THE DESIGN CONSTRAINT THAT SHAPES EVERYTHING — §18

> **Do not force every domain to produce a fake "trust score."**

A CPU deadline is either met or missed. A firmware hash either matches the
qualified one or it does not. A CAN bus is either in bus-off or it is not.
Turning those into a number in [0, 1] would invent a precision that does not
exist and would make them silently comparable with a Beta-distributed sensor
trust that means something entirely different.

So `EvidenceRecord` carries a **categorical `observation_state`** as its
required verdict, and numeric fields — `measured_value`, `expected_value`,
`residual` — that are **optional**. A domain with a real residual reports it;
a domain without one does not manufacture one.

    NOMINAL         the relation holds
    DEGRADED        it holds worse than required, and the record says how
    VIOLATED        it does not hold
    UNAVAILABLE     the inputs to evaluate it did not arrive
    NOT_APPLICABLE  the relation does not apply in this configuration

`UNAVAILABLE` and `NOT_APPLICABLE` are deliberately distinct: "we could not
look" is not "there is nothing to look at", and collapsing them is how a
missing sensor becomes indistinguishable from a healthy one.

## 2. FIELDS

| field | required | meaning |
|---|---|---|
| `domain` | yes | the `AssuranceDomain` that produced it |
| `component` | yes | what inside the domain — `battery.pack`, `cpu.core`, `link.mavlink` |
| `relation` | yes | which check this is. Stable id, not prose |
| `source` | yes | where the inputs came from |
| `observation_state` | yes | the categorical verdict above |
| `applicability` | yes | `APPLICABLE` / `NOT_APPLICABLE` / `INPUTS_MISSING` |
| `timestamp_validity` | no | when the measurement was true |
| `timestamp_arrival` | no | when it reached this system |
| `timestamp_processed` | no | when this record was computed |
| `measured_value` | no | the quantity, when there is one |
| `expected_value` | no | what the relation predicted |
| `expected_relation` | no | the relation in words, for a human reading a ledger |
| `residual` | no | `measured − expected`, when both exist |
| `sequential_state` | no | detector state where a domain runs one |
| `provenance` | no | producer identity, firmware/config hash, message id |
| `dependencies` | no | other components this evidence depends on (§22) |
| `affected_functions` | yes | which system functions this bears on |
| `reason_codes` | yes | structured codes, never generated prose |

**Three timestamps, not one** (§6). `timestamp_validity` is when the world was
that way; `timestamp_arrival` is when we heard about it; `timestamp_processed`
is when we acted on it. The TIMING domain exists because the differences
between them are themselves evidence, and a single `timestamp` field would
have thrown that away before the domain could see it.

## 3. WHAT THE SCHEMA REFUSES TO DO

- **No universal score.** There is no `confidence`, no `health`, no `score`
  field. A consumer that wants to rank domains must say by what.
- **No prose as evidence.** `reason_codes` are structured codes from a
  registry; `expected_relation` is a human-readable string that a display may
  render and a decision may not read.
- **No silent absence.** A domain that cannot evaluate a relation emits a
  record with `applicability = INPUTS_MISSING`, rather than emitting nothing.
  Missing records and healthy records must not look the same.

## 4. WHY `dependencies` IS A LIST AND NOT A NUMBER — §22

§22 is explicit: store dependencies as explicit structure, do **not** compute
independence scores yet. So `dependencies` is a list of component ids and
nothing more.

This matters for the common-cause case (Scenario E): two sensors on a shared
5 V rail are not independent evidence, and the honest first step is to record
that they share `power.rail.5v` — not to invent a correlation coefficient for
it. A previous CSIA research candidate closed as
`PROVENANCE_METRIC_INSUFFICIENT` for attempting exactly that kind of number
prematurely, and that lesson is why this field is structural.

## 5. HETEROGENEITY IS THE POINT

The v1.1 diagnosis core stays what it is: an eight-hypothesis Bayesian
sensor-fault model over 21 features. **v2 does not extend it and does not feed
it** (§18). The navigation domain reports the v1.1 verdict as evidence; the
power domain reports `P = V·I` residuals; the compute domain reports deadline
misses as counts. They meet at `observation_state` and `affected_functions`,
which is the only place they need to be commensurable.
