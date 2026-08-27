# Third case — magnetometer all-zero triple

## Why this case, chosen before any downstream outcome was inspected

Item 17 offers the magnetometer or the estimator-health signal, and requires
the choice and its rationale to be recorded in advance. The rationale, from
`authorities.py:THIRD_CASE_RATIONALE`, committed with the artifact:

> The estimator-health channel is absent from `CORE_MAP` entirely
> (`research/evidence_semantics/CROSS_SENSOR_AUDIT.csv`), so it cannot cross
> the core boundary and its downstream consequence is known to be empty
> BEFORE any measurement. Choosing it would guarantee a null result by
> construction and would test nothing about authority conflict. The
> magnetometer does cross the boundary, so its downstream consequence is an
> open question at the time of choosing.

## The authority table

| authority | interpretation | citation |
|---|---|---|
| `C_spec` | **`SILENT`** | `common.xml:SCALED_IMU.xmag` — no `invalid=` attribute, no clause about an all-zero triple |
| `C_consumer_A` | `TREAT_AS_ABSENT_SILENTLY` | `ardupilot.py:146` — `if any(mag) and …`, with **no else branch at all** |
| `C_consumer_B` | `TREAT_AS_ABSENT_SILENTLY` | `plugins.py:140` — same test, same silence |
| `C_consumer_C` | `LITERAL_ZERO_FIELD` | `ulog_source.py:162-163` — emits the zero vector with `valid: True` |

Two consumers agree; the third does not. The spec is silent, so this is
`UNDERSPECIFICATION` (3 pairs) plus one genuine `CROSS_CONSUMER` conflict
(2 pairs).

Worth stating: consumers A and B treat the triple as absence on the strength
of nothing but their own judgement — the adapter's own comment says "A real
magnetometer never reads exactly zero on all three axes" — and neither
records a reason when they do it. That reading may well be right. It is not
in the standard.

## Decision sensitivity

| level | distinct outcomes | verdict |
|---|---|---|
| VALUE | 2 | CONFOUNDED_BY_CONTROL |
| STATE | 2 | SEMANTICALLY_AMBIGUOUS |
| EVIDENCE | 2 | SEMANTICALLY_AMBIGUOUS |
| DIAGNOSIS | 3 | CONFOUNDED_BY_CONTROL |
| ASSURANCE | 1 | **ROBUST** |
| ACTION | 1 | **ROBUST** |

The disagreement dies at EVIDENCE. It never reaches the failsafe at all.

## Baselines

* **B0 SPEC_FIRST** — `SILENT`. Cannot resolve.
* **B1 IMPLEMENTATION_FIRST** — `SILENT`. There is no producer-side authority
  either: MAVLink has no convention here and ArduPilot writes whatever the
  compass driver last had.
* **B2 OBSERVATION_FIRST** — SELF_INCONSISTENT.
* **B3 SET_VALUED** — ambiguity at STATE and EVIDENCE, and nowhere else.

**This is the only case where no precedence rule applies at all**, because
no authority above the consumer speaks. It is also the case with the
shallowest consequence.
