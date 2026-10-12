# Battery: retained invalid current

Item 13. **A separate implementation defect.** It is not evidence that dual
admissibility generalises, and it is not part of the A/D result.

## Source path

```
BATTERY_STATUS.current_battery == -1   ("not measured", MAVLink convention)
        │
        ▼
csia/aircraft/adapters/ardupilot.py:176-181   (px4.py:169-174 identical)
        │
        ├─ _put("battery.current", ...)   NOT taken
        └─ _reject_sentinel("battery.current")    <-- default reason SENTINEL
        │
        ▼
_latest["battery.current"] is LEFT IN PLACE
        │
        ▼
_channel_value(): entry is not None, so the SENTINEL branch is never reached;
the retained value is served until `age > max_age`
```

## Exact invalidity semantics

```python
cur = g("current_battery", CURRENT_NOT_MEASURED)
if cur is not None and cur != CURRENT_NOT_MEASURED and finite(cur):
    self._put("battery.current", float(cur) / 100.0, t_source=t_src, unit="A")
else:
    self._reject_sentinel("battery.current")
```

Compare the GNSS handling, which additionally **deletes** the retained value:

```python
self._latest.pop("gnss.position", None)      # ardupilot.py:232
self._latest.pop("gnss.velocity", None)      # ardupilot.py:233
self._reject_sentinel("gnss.position", "gnss.velocity",
                      reason=MissingReason.NO_3D_FIX)
```

Two differences, both material:

1. **No `pop`.** The disowned current stays in `_latest` and keeps being
   served as a current value.
2. **No specific reason.** GNSS passes `NO_3D_FIX`; battery takes the default
   `SENTINEL`, so the flight log records less about why.

A third, separate gap: **`battery.voltage` has no invalid path at all.**
`if volts:` simply does not `_put` when the voltage list is empty — nothing
recorded, no sentinel counted, no reason attached.

## Retained value and downstream consequence

`_channel_value` reaches the sentinel branch only when `entry is None`
(`base.py:199-208`). Because the entry survives, the sentinel is recorded but
never consulted, and the stale current is returned as usable until it ages
out against `max_age`.

Downstream: `to_core_samples` emits the `battery` sensor while both channels
are usable, so `slot.last_t` keeps advancing on a value the producer has
disowned, `fresh["battery"]` stays true, and `P["battery"]`'s physics check
scores a current the vehicle is no longer reporting. `FailsafePolicy` reads
`T["battery"] < power_critical and fresh.get("battery")` (`failsafe.py:155`)
and can raise **CRITICAL** — a more severe operational consequence than the
GNSS path's CAUTION.

## Smallest counterexample

Two `BATTERY_STATUS` messages, `Δt` under `max_age`:

```
t = 0.00   voltages = [12000, ...], current_battery = 500     -> 5.00 A stored
t = 0.10   voltages = [12000, ...], current_battery = -1      -> sentinel counted,
                                                                 5.00 A RETAINED
```

**Executed against the committed adapter**, not inferred:

```
max_age["battery.current"] = 0.5 s
sentinel_counts()          = {'battery.current': 1}

  t = 0.11   usable=True    value=5.0    missing=None
  t = 0.30   usable=True    value=5.0    missing=None
  t = 0.60   usable=False   value=None   missing=MissingReason.STALE
  t = 1.20   usable=False   value=None   missing=MissingReason.STALE
```

So for **0.5 s** after the producer says "not measured", the adapter reports
`5.00 A` as a usable current while simultaneously counting a sentinel for that
channel. The two statements contradict each other and only the first reaches
the core.

A third finding falls out of the same trace: when the value finally does go
away, the reason is **`STALE`, not `SENTINEL`**. The specific fact that the
producer disowned the reading is recorded in a counter and never delivered —
which is precisely the failure `_reject_sentinel`'s own docstring was written
to fix for the GNSS case.

The GNSS equivalent of the same trace reports the channel absent immediately.

## Classification

**`IMPLEMENTATION DEFECT`.** Note that it is the *opposite* defect from the
GNSS one:

| | GNSS | Battery |
|---|---|---|
| On explicit invalidity | `OBSERVED_INVALID → NOT_OBSERVED` | `OBSERVED_INVALID → RETAINED_AS_IF_CURRENT` |
| Core sees | absence | a stale value presented as current |
| Which is worse | loses the reason | asserts something false |

Because the two defects differ in kind, a battery arm would **not** be a
replication of the GNSS experiment, and running it as one would conflate them.
That is why item 29 of Stage 2 deferred it and why this document keeps it
separate.

## Fix, independent of all research questions

Add the deletion and a specific reason, mirroring GNSS:

```python
else:
    self._latest.pop("battery.current", None)
    self._reject_sentinel("battery.current",
                          reason=MissingReason.SENTINEL)
```

and give `battery.voltage` an explicit rejection path. Neither change depends
on the A/D question and both should be made regardless of its outcome.
