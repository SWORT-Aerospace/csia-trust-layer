# Topic inventory over the 66 XSYS-001 flight logs (Phase 1)

**2026-10-02.**

- **Scripts:** `topic_inventory.py`.
- **Machine-readable outputs:**
  - `TOPIC_INVENTORY.json`: per topic, per field;
  - `TOPIC_COVERAGE_MATRIX.csv`: topic by flight, logged rate in Hz.

## 1. What was measured

The 66 flights are 55 fault flights and 11 benign-onset flights, PX4
547e2ca SIH, 11,336 s of log in all. For every topic in each log the
inventory records:
- presence;
- instances;
- logged rate;
- the largest gap, and gaps longer than three logging intervals;
- for every field, whether it varies, is constant, is all zero or is all
  NaN;
- whether the topic exists only in simulation;
- the stock (default) logging interval PX4 547e2ca's `add_default_topics`
  gives it on a real board.

Logger dropouts and PX4 log messages are counted per level and module.

## 2. The answer for the brief's topics

| topic | present | logged rate (Hz) | stock interval (ms) | what carries information |
|---|---|---|---|---|
| `esc_status` | 66/66 | 250 | 100 | `esc_rpm`, counts and flags; **ESC current and voltage are zero in every flight** |
| `actuator_motors` | 66/66 | 250 | 100 | four commands |
| `actuator_outputs` | 66/66 | 10 | 100 | four outputs; the rest constant |
| `control_allocator_status` | 66/66 | 125 | 200 | unallocated torque and thrust, achieved flags, saturation |
| `battery_status` | 66/66 | 5 | 200 | voltage, remaining; **`current_a` is -1 (not measured) in every flight**; no cell voltages |
| `estimator_status` | 66/66 | 125 | 200 | test ratios, fault flags |
| `estimator_status_flags` | 66/66 | 1 | 10 | aiding and status flags |
| `vehicle_local_position`, `vehicle_global_position` | 66/66 | 125, 10 | 100, 200 | navigation output |
| `vehicle_attitude`, `vehicle_angular_velocity`, `vehicle_acceleration` | 66/66 | 250 | 50, 20, 50 | body states |
| `vehicle_status`, `vehicle_control_mode` | 66/66 | 2 | every publication | arming, mode, failsafe |
| `failure_detector_status` | 66/66 | 2 | 100 | **every flag zero in every flight** |
| `cpuload` | 66/66 | 2 | every publication | load (of the SITL host) |
| `sensor_selection` | 66/66 | once | every publication | no change in any flight |
| `sensor_gps`, `vehicle_air_data`, `vehicle_magnetometer` | 66/66 | 1, 19, 14 | 1000, 200, 200 | sensor outputs |
| `telemetry_status` | 66/66 | 0.8 | 1000 | four instances (MAVLink links) |

- **Logger dropouts:** none in any flight.
- **Log messages:**
  - only `INFO`, plus one `WARNING` per flight from
    `health_and_arming_checks` (pre-arm);
  - 19 `WARNING`s from the logger.

## 3. Three consequences that shape the bridge

**The logs are richer than an ordinary log.** XSYS-001 added a custom topic
list. It logs ESC status and motor commands at 250 Hz, where a default
board logs them at 10 Hz. Every 2.3 statistic is therefore computed after
decimating to the default intervals (`stock_log.StockLog.decimate`). The
product claims nothing that needs the research rates.

**The electrical side of the propulsion chain is not observed in SIH:**
- ESC current and voltage are zero;
- battery current is not measured.

So the 2.1.1 relations that need current cannot be evaluated:
- `actuation.electrical_response`;
- `actuation.mechanical_response`'s stall check;
- `power.droop_vs_current`.

That is a property of SIH. A real ESC with telemetry, or a power module,
changes it. `COVERAGE` in every report says which applies.

**PX4's own monitors were silent in every flight.**
- The failure detector raised no flag.
- The allocator never reported a missed setpoint.
- No battery warning was raised.

These monitors are still triggers in the product (`events.py`). They can
fire on other flights, and the validation flights exercise two of them.
But on XSYS-001 they added no information, which is why the propulsion
change detectors are needed at all.

## 4. Limits

- **One simulator, one build, one airframe.** A real flight log has noise,
  vibration, different topic rates and more instances (two IMUs, two
  magnetometers). The inventory says what this campaign contains, not what
  every PX4 log contains.
- **Topics outside the brief's list** are in the JSON but were not
  analysed.
