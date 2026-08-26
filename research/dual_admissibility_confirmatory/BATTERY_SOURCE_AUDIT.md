# Battery: source audit only

Item 29. The cross-sensor audit in `b21b539` scored GNSS 4/4 and battery 3/4,
with every other family at 2/4 or below. Battery is therefore the only
plausible second modality. **Nothing here is implemented, and no
generalisation is claimed.** This audit exists so that the decision about a
second modality is made from source rather than from optimism.

## The four criteria, against battery

### 1. Explicit invalid state — **PARTIAL**

```python
# csia/aircraft/adapters/ardupilot.py:176-181 (px4.py:169-174 identical)
cur = g("current_battery", CURRENT_NOT_MEASURED)
if cur is not None and cur != CURRENT_NOT_MEASURED and finite(cur):
    self._put("battery.current", float(cur) / 100.0, t_source=t_src, unit="A")
else:
    self._reject_sentinel("battery.current")
```

`current_battery == -1` means "not measured", and the adapter rejects it. So
there **is** an explicit in-band invalid state — for one of the two channels.

Two qualifications that matter:

* **`battery.voltage` has no invalid path at all.** `if volts:` simply does
  not `_put` when the voltage list is empty; nothing is recorded, no sentinel
  is counted, and no reason is attached. Battery is half-instrumented.
* **The rejection carries the default reason**, `MissingReason.SENTINEL`, not
  a battery-specific one. Compare GNSS, which passes
  `reason=MissingReason.NO_3D_FIX`. So even the instrumented half says less
  about *why* than GNSS does.

### 2. Invalid becomes a no-update — **NO, and this is the blocker**

`_reject_sentinel` records the sentinel; it does **not** delete the retained
value. GNSS additionally pops the channels:

```python
# ardupilot.py:232-233 — GNSS only
self._latest.pop("gnss.position", None)
self._latest.pop("gnss.velocity", None)
```

There is no equivalent for `battery.current`. So a `-1` current leaves the
previous value in `_latest`, which then ages out through `max_age` on the
ordinary staleness path rather than being forgotten at the moment the producer
disowned it.

**Consequence:** battery exhibits a *different* defect from GNSS. Where GNSS
converts `OBSERVED_INVALID` into `NOT_OBSERVED` at the hand-off, battery
converts it into `RETAINED_AS_IF_CURRENT` for up to `max_age`. That is the
retained-state hazard from the invalidity-masking work package, in a second
place, and it is arguably worse: GNSS at least stops asserting a value.

This is worth fixing on its own merits, independently of anything to do with
the A/D question.

### 3. One gate controls both roles — **YES**

```python
# csia/runtime/failsafe.py:155
if T["battery"] < cfg.power_critical and fresh.get("battery"):
```

`fresh["battery"]` is the same dict entry that multiplies `P["battery"]`'s gate
(`online.py:613`) and gates the Beta update (`engine.py:146`). Same coupling as
GNSS: one value, both roles. `power_critical = 0.70`, and the condition raises
`CRITICAL`, which is a more severe operational consequence than GNSS's
`CAUTION`.

### 4. Health fields surviving value loss — **YES, and richer than GNSS**

`BATTERY_STATUS` carries, unused by this stack:

| Field | What it says when the current reading is unusable |
|---|---|
| `battery_remaining` | state of charge, %, `-1` when unknown |
| `charge_state` | `MAV_BATTERY_CHARGE_STATE`: OK / LOW / CRITICAL / EMERGENCY / FAILED / UNHEALTHY / CHARGING |
| `fault_bitmask` | `MAV_BATTERY_FAULT`: deep discharge, spikes, cell fail, over-current, over-temperature, under-temperature, incompatible voltage/firmware |
| `time_remaining` | seconds, `0` when unknown |
| `temperature` | pack temperature, `INT16_MAX` when unknown |

`charge_state` and `fault_bitmask` in particular are **exactly the
status-versus-value split this work package is about**, supplied by the
protocol and consumed by nothing. `charge_state == FAILED` or `UNHEALTHY` is a
statement about the battery that does not depend on any current reading being
usable.

## Is there a meaningful A/D analogue?

**Yes in principle, no as currently coded.** T3's necessary condition is
satisfied — there are observables (`charge_state`, `fault_bitmask`) outside the
value that discriminate a failed pack from a silent link. But criterion 2 fails
in a direction that changes the question: because the invalid current is
retained rather than dropped, battery's *first* problem is not that diagnosis
loses the information — it is that the operational gate keeps a disowned value
alive.

So the battery analogue would test something subtly different from the GNSS
case, and running it as though it were the same experiment would confuse two
defects.

## Recommendation

1. **Do not implement a battery arm.** The GNSS confirmatory result is not
   frozen yet, and item 29 forbids it until it is.
2. **File the retained-invalid-current behaviour as a defect in its own
   right.** It is a one-line difference from the GNSS handling
   (`_latest.pop("battery.current", None)` alongside the sentinel), it is
   independent of the A/D question, and it is the same class of bug the
   invalidity-masking package documented.
3. **If a second modality is ever run**, use `charge_state` /`fault_bitmask` —
   categorical, protocol-supplied, no magnitude — which fits the status-only
   ablation design far better than `h_acc` ever did.
4. **Note the asymmetry** before designing anything: battery's operational
   consequence is `CRITICAL`, not `CAUTION`, so a false positive costs more
   than it does for GNSS.

## Prior-art note

`MAV_BATTERY_FAULT` and `MAV_BATTERY_CHARGE_STATE` are, structurally, the same
device-status vocabulary as NAMUR NE 107's four status signals and ARINC 429's
SSM (`PRIOR_ART_MATRIX.md`). Their existence is further evidence that
separating status from value is standard practice, and that the finding here is
about a *consumer* discarding it.
