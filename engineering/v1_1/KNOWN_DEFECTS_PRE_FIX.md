# KNOWN DEFECTS — PRE-FIX

Item 4: *reproduce every defect BEFORE fixing it; freeze pre-fix fixtures and
hashes.* This is that record. It was produced by
`engineering/v1_1/reproduce_defects.py --out pre`, run against unmodified v1
ingestion, **before any fix was applied**.

    sha256(cases) = 7fdd3d65e1b9c7633255989ec16f10c58e288bae2d024825e1e53fbd57d59d9d

Machine-readable: `KNOWN_DEFECTS_PRE_FIX.json`.

The script records what each path **does**. It asserts nothing about what is
correct; `CANONICAL_INGEST_SPEC.md` says that.

---

## D1 — battery current sentinel, ArduPilot adapter

**Raw condition.** `BATTERY_STATUS.current_battery = -1` arriving 20 ms after
a real 5.00 A reading. MAVLink declares the sentinel machine-readably:
`<field type="int16_t" name="current_battery" units="cA" invalid="-1">`.

**Observed pre-fix.**

```json
{"present": true, "value": 5.0, "missing_reason": null,
 "quality": "INFORMATIVE", "note": ""}
```

`sentinel_counts` = `{"battery.current": 1}`.

**What that means.** The sentinel was counted. It was recorded in
`_sentinel_at`. And it made no difference: `_channel_value` consults
`_latest` first, `_reject_sentinel` never cleared `_latest`, so the retained
5.00 A was served as **present and INFORMATIVE** — admissible, fresh-looking,
and wrong. When it eventually aged out it did so as **STALE**, attributing the
absence to the link rather than to the producer's own disavowal.

**Severity.** The highest of the four. A trust layer told that current is
5.00 A when the vehicle has said it is not measuring current has been handed a
fabricated measurement, not a degraded one.

---

## D2 — magnetometer all-zero triple, ArduPilot adapter

**Raw condition.** `RAW_IMU` with `xmag = ymag = zmag = 0` arriving 20 ms
after a real field. A real magnetometer never reads exactly zero on all three
axes; the adapter's own comment says so.

**Observed pre-fix.**

```json
{"present": true, "value": [20.0, -10.0, -40.0], "missing_reason": null,
 "quality": "INFORMATIVE", "note": ""}
```

`sentinel_counts` = `{}` — **empty**.

**What that means.** The guard `if any(mag) and all(finite(x) for x in mag)`
was correct and had no `else`. The all-zero case was recognised and then
dropped: nothing emitted, nothing recorded, not even a count. The previous
field stayed in `_latest` and was served as current.

This is the quieter defect of the two, and the worse-behaved one: D1 at least
left a counter behind.

---

## D3 — battery current, PX4 ULog path

**Raw condition.** `battery_status.current_a == -1.0`. PX4 declares the
sentinel in its own message definition,
`msg/versioned/BatteryStatus.msg:14`:

```
float32 current_a # [A] [@invalid -1] Battery current
```

**Observed pre-fix.**

```json
{"voltage": 12.0, "current": -1.0, "valid": 1.0}
```

**What that means.** `valid: True` was unconditional, so a current of **−1 A**
— physically impossible for a discharging pack, and declared invalid by the
producer's own schema — reached the trust layer as a valid physical
measurement.

**Not an edge case.** The measured PX4 log in this repository carries 216
battery samples and every one of them is `-1.0`.

---

## D4 — battery current, plugins decode path

**Raw condition.** The same MAVLink `current_battery == -1`.

**Observed pre-fix.**

```json
{"voltage": 12.0, "current": 0.0, "valid": 1.0}
```

**What that means.** `max(msg.current_battery, 0) / 100.0` clamps −1 to 0. The
producer said "I am not measuring current"; the decoder said "the current is
zero amps". Those are different claims — one about the sensor, one about the
aircraft — and the clamp silently replaced the second with the first.

**Three decoders, one raw condition, three answers: 5.00 A, 0.00 A, −1.00 A.**
That is the v1 finding the evidence-semantics package recorded, reproduced
here executably.

---

## D5 — GNSS no-fix, ArduPilot adapter *(CONTROL, not a defect)*

**Raw condition.** `GPS_RAW_INT.fix_type = 1` arriving 20 ms after a 3D fix.

**Observed pre-fix.**

```json
{"present": false, "value": null, "missing_reason": "NO_3D_FIX",
 "quality": "UNAVAILABLE",
 "note": "producer arrived carrying the documented not-measured sentinel: ..."}
```

**Correct already, and included deliberately.** The GNSS path pops `_latest`
itself before calling `_reject_sentinel` (`ardupilot.py:232-233`), which is
exactly the step D1 and D2 were missing. That local workaround is why one
channel behaved correctly while the others did not, and it is the shape the
Phase 1 fix generalises.

Its role in this file is as a **control**: if D5 changes between pre-fix and
post-fix, the v1.1 edit broke something that already worked.
