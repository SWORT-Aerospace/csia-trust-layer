# CANONICAL INGEST SPEC — v1.1

Items 3, 4, 5, 6. What the ingest layer is required to do. The defect records
say what the code *did*; this file says what is *correct*.

---

## 1. ONE CANONICAL REPRESENTATION — AND WHY NO NEW TYPE WAS ADDED

Item 3 asks for one internal representation and warns twice against ontology
inflation: *"Only include fields justified by existing code/use. Avoid
ontology inflation."*

**`ChannelValue` (`csia/aircraft/sample.py:84-110`) is that representation.**
It already carries:

| field | role |
|---|---|
| `channel` | identity |
| `value` | the measurement, or `None` |
| `unit`, `frame` | dimensional and geometric meaning |
| `quality` | semantic admissibility |
| `missing` | a `MissingReason`, set exactly when `value` is `None` |
| `t_source` | vehicle-reported time |
| `age_s` | age at sampling |
| `note` | why |

and `__post_init__` already enforces the invariant that makes the type worth
having: **exactly one of `value` / `missing` is set**, and a missing value can
never be `INFORMATIVE`.

The candidate structure item 3 sketches adds `observed`, `source_valid`,
`fresh`, `usable`, `provenance`, `producer`, `transport`, `receive_timestamp`.
Of those:

- `usable` exists as a property (`present AND admissible`);
- `fresh` is expressed by `age_s` against `MaxAge`, and duplicating it as a
  boolean would let the two disagree;
- `observed` and `source_valid` are the `missing` reason: `NOT_RECEIVED` vs
  `SENTINEL` vs `NO_3D_FIX` already distinguishes "never came", "came and
  declared no value", and "came and declared no fix";
- `provenance` / `producer` / `transport` are **genuinely absent** — and they
  belong to Phase 9, where item 32 says to log provenance and item 33 says not
  to compute anything from it. Inventing them in Phase 1 with no consumer
  would be inflation.

**So Phase 1 adds no type.** What was missing was not a field but a rule.

## 2. THE REQUIRED STATES

Item 3's minimum set, mapped to what the code produces:

| required state | representation | reached by |
|---|---|---|
| `OBSERVED_VALID` | `value` set, `quality` admissible | a real measurement |
| `OBSERVED_INVALID` | `missing = SENTINEL` | producer arrived carrying its declared not-measured value |
| `NOT_OBSERVED` | `missing = NOT_RECEIVED` | no message |
| `STALE` | `missing = STALE` | value older than `MaxAge` |
| `SENTINEL / NOT_MEASURED` | `missing = SENTINEL`, and `NO_3D_FIX` for the GNSS case | as above |
| `RETAINED` | **deliberately not represented** | see §3 |

`NO_3D_FIX` is kept distinct from `SENTINEL` rather than merged. "The receiver
has no fix" says something "this field is not measured" does not, and folding
them would replace one imprecision with another.

## 3. RETAINED IS NOT A STATE — IT IS THE DEFECT

Item 3 lists `RETAINED` "where those states actually exist". In v1 it existed
by accident, not by design: a value the producer had disowned kept being
served because nothing cleared it.

**v1.1 does not model retention. It removes it.**

> **RULE R1 (supersession).** A producer's most recent statement about a
> channel is the one that describes the present. A value supersedes an earlier
> sentinel; a sentinel supersedes an earlier value. Both directions, always.

v1 implemented only the first direction (`_put` cleared `_sentinel_at`). The
missing second direction is defects D1 and D2. R1 is now enforced in one
place, `_reject_sentinel`.

> **RULE R2 (reason fidelity).** When a channel is absent, the reason reported
> must be the reason it is absent. A disowned value reports `SENTINEL`, not
> `STALE`.

> **RULE R3 (no fabrication).** A sentinel is never converted into a number.
> Not by clamping (`max(-1, 0)`), not by passing it through (`-1.0 A`), not by
> substituting a default. If the producer declined to measure, the channel is
> absent.

> **RULE R4 (independent constituents).** Where a message carries several
> quantities with separate declared sentinels, each is judged on its own.
> `battery.voltage` survives an unmeasured `battery.current`.

> **RULE R5 (sentinels age).** A sentinel is a statement about a moment, not a
> permanent condition, and is aged against the same `MaxAge` as a value. A
> sentinel from a minute ago says nothing about now.

R5 was already implemented in v1 and is restated here because R1 makes it
load-bearing: without it, one sentinel would silence a channel for ever.

## 4. WHERE THE RULES COME FROM

Item 5: prefer authoritative existing metadata over hand-written duplication.
Every rule in `channel_semantics/canonical_channel_semantics.yaml` cites
either a **schema attribute**, a **producer source line**, or — where neither
exists — says so.

The distinction matters and is recorded honestly:

- `battery.current` rests on `invalid="-1"` in MAVLink **and**
  `[@invalid -1]` in PX4's own `BatteryStatus.msg`. Machine-readable, from
  both producers. Strong.
- `mag.field_ut` rests on a **consumer convention** — MAVLink carries no
  `invalid=` attribute on the `RAW_IMU` magnetometer fields. The rule is
  sound engineering (a real magnetometer never reads exactly zero on three
  axes) but it is not a producer declaration, and the YAML says so.

## 5. INGEST EQUIVALENCE (item 6)

> **Equivalent raw condition → equivalent canonical semantic state**, or a
> documented platform exception.

Phase 1 establishes this for the battery-current sentinel across all three
decode paths, which previously gave three different answers to one raw
condition (5.00 A / 0.00 A / −1.00 A). They now agree: absent, invalid.

**Not yet established** for the full five-path matrix item 6 asks for
(ArduPilot live adapter, PX4 live adapter, plugins, ULog, replay) across all
channels. That is remaining Phase 1 scope, recorded as not done rather than
claimed.

### Documented platform exceptions

| exception | reason |
|---|---|
| `gnss.velocity` vertical component | `GPS_RAW_INT` carries no vertical rate; the third component is padding and `vz_valid=False` says so. PX4's uORB path does carry `vel_d_m_s`. Not a defect — a real protocol difference |
| `MaxAge["gnss.position"] = 1.00 s` vs frozen core `STALE_TIMEOUT_S["gps"] = 0.5 s` | the two layers disagree about when a fix goes stale. **Left alone in Phase 1**: it is not an ingest sentinel defect, and changing a freshness limit changes admissibility for every downstream result. Banked |

## 6. WHAT THIS SPEC DOES NOT COVER

- Provenance, producer identity and transport — Phase 9.
- Support state, ambiguity, unknown — Phase 2.
- Any change to the frozen core. `FROZEN_PATHS` carries zero diff and Phase 1
  needed none: fixing what reaches the bridge did not require touching what is
  on the other side of it.
