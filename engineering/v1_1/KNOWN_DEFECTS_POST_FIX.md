# KNOWN DEFECTS — POST-FIX

Produced by `engineering/v1_1/reproduce_defects.py --out post`, the **same
script** that produced the pre-fix record, run after the Phase 1 fixes.

    pre  sha256(cases) = 7fdd3d65e1b9c7633255989ec16f10c58e288bae2d024825e1e53fbd57d59d9d
    post sha256(cases) = 7fff288ac57f3d91e865ea59e1dfb8bb324628a3b7a918ac96019f1ad830687a

Machine-readable: `KNOWN_DEFECTS_POST_FIX.json`.

Gate C (item 46): **PASS.** All four defects are gone; the control is
unchanged.

---

## Summary

| case | pre-fix | post-fix | verdict |
|---|---|---|---|
| **D1** battery sentinel, ArduPilot adapter | `5.0 A`, present, INFORMATIVE | absent, `SENTINEL` | **FIXED** |
| **D2** magnetometer all-zero | stale field `[20.0, -10.0, -40.0]`, present | absent, `SENTINEL` | **FIXED** |
| **D3** battery current, ULog | `current: -1.0, valid: true` | `current: null, current_valid: false, valid: false` | **FIXED** |
| **D4** battery current, plugins | `current: 0.0, valid: true` | `current: null, current_valid: false, valid: false` | **FIXED** |
| **D5** GNSS no-fix *(control)* | absent, `NO_3D_FIX` | absent, `NO_3D_FIX` | **UNCHANGED — as required** |

---

## D1 — FIXED

```json
{"present": false, "value": null, "missing_reason": "SENTINEL",
 "quality": "UNAVAILABLE",
 "note": "producer arrived carrying the documented not-measured sentinel: ..."}
```

The producer's disavowal now reaches the channel, and it reaches it **as a
disavowal** — `SENTINEL`, not `STALE`. The distinction the `MissingReason`
enum exists to carry is finally carried end to end.

Fix: `csia/aircraft/adapters/base.py`, `_reject_sentinel` now clears
`_latest`, making it symmetric with `_put` clearing `_sentinel_at`.

## D2 — FIXED

```json
{"present": false, "value": null, "missing_reason": "SENTINEL", ...}
```

Fix: `csia/aircraft/adapters/ardupilot.py`, the all-zero branch now calls
`_reject_sentinel("mag.field_ut")` instead of falling through in silence.

## D3 — FIXED

```json
{"voltage": 12.0, "current": null, "current_valid": false, "valid": false}
```

Voltage survives with its own validity, judged against its own declared
sentinel (`[@invalid 0]`). A pack can report voltage with no current shunt
fitted, and discarding the voltage because the current is unmeasured would
have traded one false statement for another.

## D4 — FIXED

```json
{"voltage": 12.0, "current": null, "current_valid": false, "valid": false}
```

The clamp is gone. Both decode paths now give the same answer to the same raw
condition, which is item 6's goal: **equivalent raw condition → equivalent
canonical semantic state.**

## D5 — UNCHANGED

Byte-identical between the two records. The generalised sentinel rule did not
disturb the one path that already implemented it locally.

---

## What is NOT claimed

- **Not** that ingestion is now correct in general. Four defect cases on three
  paths were fixed. Item 6's full five-path equivalence matrix is not built.
- **Not** that any downstream result improved. Phase 1 changed what reaches
  the trust layer; whether that changes an assurance decision is a Phase 3
  measurement and has not been made.
- **Not** that the v1 research results were wrong. They were right about v1.
  `V1_1_ENGINEERING_MANIFEST.md` §5 lists which of them now require
  remeasurement for v1.1, and none of them was edited.

## New wire-format field

Both decode paths now emit **`current_valid`** in the `battery` dict, and
`current` may be `None`. Consumers reading `current` unconditionally will need
updating; the two in this repository were, and are listed in the manifest §6.
