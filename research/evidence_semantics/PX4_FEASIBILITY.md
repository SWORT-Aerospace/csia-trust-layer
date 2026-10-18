# PX4 feasibility

Item 24. Three questions, answered by execution. Data:
`results/PX4_FEASIBILITY.json`, produced by `px4_probe.py`.

**Nothing is forced into identical semantics.** Where the two platforms
present genuinely different source interfaces, that is reported as a
difference and the comparison is not run.

---

## 1. The same contracts, run against `PX4Adapter`

`PX4Adapter` and `ArduPilotAdapter` both inherit `base.PlatformAdapter`, so
`T3`, `T4` and `T5` are the *same code*. Only the ingest branch differs. A
fourth path (`px4_adapter`) was installed into the probe and the gnss and
battery contracts were run against it unchanged.

| family | ArduPilot vocabulary | PX4 vocabulary | clause results identical? | first collapse identical? |
|---|---|---|---|---|
| gnss | `['V']` | `['V']` | yes | yes |
| battery | `['V']` | **`[]`** | yes | **no** |

**GNSS: identical in every respect.** `px4.py:220-227` is line-for-line the
same handling as `ardupilot.py:226-236` — pop both channels, record
`NO_3D_FIX`. So `I` collapses with `N` at `T5_core_bridge` on PX4 too, for
the same reason. The defect is not ArduPilot-specific; it belongs to the
shared bridge.

**Battery: PX4 emits nothing at all, and that is a fix rather than a
failure.** `docs/simulation/CHANNEL_SEMANTICS.yaml` carries a
`platform_qualification` override setting `battery.current` to `UNAVAILABLE`
for `px4`, with a measured justification recorded in the file:

> "PX4 SIH publishes BATTERY_STATUS at ~9.7 Hz with current_battery = -1, the
> documented 'not measured' sentinel. The stream is implemented and the
> measurement is absent: there is no simulated current sensor."
> — measured: "390 producer frames in 40 s (~9.8 Hz), every one carrying the
> -1 sentinel; 0 usable samples."

`contract.qualify` then refuses the channel regardless of what the adapter
put in `_latest`, so `battery.current` is never usable, `to_core_samples`
never emits the `battery` sensor, and the retained-value defect cannot occur.
`battery.voltage` is `INFORMATIVE` but the sensor needs both channels, so
nothing crosses.

The clause results are still `FAIL` on both platforms — `X` remains
unrepresentable — but on PX4 the reason is "the channel is closed" rather
than "a disowned value is served as current". Those are different failures
and the checker distinguishes them by the emitted vocabulary (`[]` vs
`['V']`).

## 2. PX4 source states with no ArduPilot equivalent

Two, both real and neither forced into the model:

**`fields_updated` bitmask on `HIGHRES_IMU`.** `px4.py:107-123` gates the
magnetometer on `fresh(FIELD_XMAG)` — a per-field validity bit carried in the
message. This is a genuine extra source state: *"this message arrived but
this field was not updated"*, which ArduPilot's `SCALED_IMU` has no way to
express. It is closer to ARINC 429's per-word SSM than anything on the
ArduPilot side.

**`ESTIMATOR_STATUS` ratios vs `EKF_STATUS_REPORT` variances.** PX4 reports
innovation *ratios* where ArduPilot reports *variances*, and `px4.py:196-200`
tags the record with `"_source": "ESTIMATOR_STATUS(ratios)"` rather than
conflating them. That is the correct handling of a genuine semantic
difference and is noted as such. Neither reaches the frozen core — see
`CROSS_SENSOR_AUDIT.csv`, `estimator.variances` is absent from `CORE_MAP`.

## 3. The magnetometer comparison was NOT run

Deliberately. PX4 reads the magnetometer from `HIGHRES_IMU` behind the
`fields_updated` bitmask; ArduPilot reads it from `SCALED_IMU` with no
bitmask. Driving the ArduPilot `{V, Z, N}` alphabet through the PX4 branch
would compare two different interfaces and report the difference as a
semantic one. Item 24 says not to force identical semantics, so the row is
`NOT RUN` with the reason recorded.

## 4. What the real PX4 log actually contains

The committed 9.6 MB log
(`research/v1_1/results/.px4_link_probe/passive/log/2026-08-25/22_13_43.ulg`),
read with `pyulog`:

| topic | samples | finding |
|---|---|---|
| `vehicle_gps_position` | 345 | `fix_type` histogram `{3: 345}` — **the invalid branch is NOT exercised** by this log |
| `battery_status` | 216 | `current_a` range `[-1.0, -1.0]` — **every sample carries −1.0** |

The battery row matters. It means the `ulog_source.py` finding is **not
synthetic**: `ulog_source.py:196-199` emits

```python
ev.append((float(t_s[i]), "battery", {
    "voltage": float(d["voltage_v"][i]),
    "current": float(d["current_a"][i]), "valid": True}))
```

with `valid: True` unconditionally and no branch that could read −1.0 as a
sentinel. On this real log it would feed **−1.00 A into the frozen core as a
usable battery current, 216 times**. The synthetic word `X` used elsewhere in
this package uses −1.0 precisely because the real log does.

The GNSS row cuts the other way and is stated as a limitation: no real log
available here exercises `fix_type < 3`, so every GNSS result in this package
comes from synthetic messages through real decoders.

## 5. Feasibility verdict

**Cross-platform extension is feasible and cheap for shared MAVLink
families** — the fourth path took one function and the contracts ran
unmodified. It is **not feasible without new contracts for PX4-specific
interfaces** (`fields_updated`, `ESTIMATOR_STATUS`), which would need their
own `accepted_input_states` and their own witnesses.

The result that generalises: the collapse is in `base.py`'s bridge, which
both platforms share, so it is a property of the CSIA architecture rather
than of either autopilot.

## Not done

* No PX4 SITL run. ArduPilot SITL is installed here
  (`/home/user/ardupilot/ardupilot` @ `01a504b`); PX4 SITL is not, and
  nothing in this package required it.
* No second ULog. One log is one log, and the `fix_type == 3` result says
  only that *this* flight held a fix throughout.
