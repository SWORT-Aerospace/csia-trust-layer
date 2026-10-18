# GNSS — `fix_type < 3`

Item 16.

## Reproduction

| path | token at the core boundary |
|---|---|
| `v1_1_adapter` | nothing emitted |
| `plugins_py` | `I` |
| `ulog_source_py` | `I` |

Matches `research/evidence_semantics` at `2036a2a`.

## The authority table

| authority | aspect | interpretation | citation |
|---|---|---|---|
| `C_spec` | `fix_type` meaning | `NO_POSITION_INFORMATION` | `common.xml:GPS_RAW_INT.fix_type`, `enum="GPS_FIX_TYPE"`; entry 1 = "No position information, GPS is connected" |
| `C_spec_position_fields` | position fields | **`SILENT`** | `common.xml:GPS_RAW_INT.lat` — no `invalid=` attribute, no description clause covering the no-fix case |
| `C_producer` | position fields | `STALE_POSITION_WITH_HONEST_FIX_TYPE` | `AP_GPS.cpp:1399-1417` — `const Location &loc = location(0);` sent unconditionally alongside `(uint8_t)status(0)` |
| `C_producer_absence` | *different raw state* | `NO_MESSAGE_AT_ALL` | `AP_GPS.cpp:1394-1396` — `if (get_type(0) == GPS_TYPE_NONE) { return; }` |
| `C_consumer_A` | position fields | `DROP_AND_RECORD_REASON` | `ardupilot.py:232-235` |
| `C_consumer_B` | position fields | `SUBSTITUTE_ZERO_MARK_INVALID` | `plugins.py:157-159` |
| `C_consumer_C` | position fields | `PASS_THROUGH_MARK_INVALID` | `ulog_source.py:188-189` |

## The finding that matters

**The schema says nothing about what lat/lon/alt contain when `fix_type < 3`.**
No `invalid=` attribute on those fields, no description clause. The producer
fills them with the last known `Location` and relies on `fix_type` to carry
the warning — which the spec permits, because the spec did not speak.

So the three consumers are not violating a standard. They are each making a
different, **licensed** choice in a space the standard left open. That is
`UNDERSPECIFICATION`, not conflict, and it is a different problem with a
different fix: someone has to decide and write it down.

A second producer-side fact, worth recording: with no GPS configured the
message is **not sent at all**. So at the producer, "no fix" and "no message"
are genuinely distinct conditions — which is what makes the consumer-side
collapse of the two a loss rather than a convention.

## Decision sensitivity

| level | distinct outcomes | verdict |
|---|---|---|
| VALUE | 3 | CONFOUNDED_BY_CONTROL |
| STATE | 2 | SEMANTICALLY_AMBIGUOUS |
| EVIDENCE | 2 | SEMANTICALLY_AMBIGUOUS |
| DIAGNOSIS | 3 | CONFOUNDED_BY_CONTROL |
| ASSURANCE | 2 | SEMANTICALLY_AMBIGUOUS |
| ACTION | 1 | **ROBUST** |

**This is the only one of the three cases whose disagreement reaches
ASSURANCE.** The failsafe reaches its level at different times depending on
which consumer is used — the previous package measured that gap as 0.12–0.32 s
— but the level history and the issued action set are identical.

**No pair reaches ACTION.**

## Baselines

* **B0 SPEC_FIRST** — RESOLVES on `fix_type` meaning; **cannot resolve** the
  position-field question, because there the spec is `SILENT`.
* **B1 IMPLEMENTATION_FIRST** — RESOLVES to the producer's
  `STALE_POSITION_WITH_HONEST_FIX_TYPE`.
* **B2 OBSERVATION_FIRST** — SELF_INCONSISTENT.
* **B3 SET_VALUED** — ambiguity at STATE, EVIDENCE and ASSURANCE; not ACTION.

This is the case where spec precedence is genuinely insufficient — and the
reason is a gap in MAVLink, not a disagreement between authorities.
