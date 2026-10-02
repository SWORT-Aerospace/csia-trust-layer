# RB0: offline real sensor data (RB-001)

**2026-10-02.**

- **Script:** `rb0_real_logs.py`.
- **Output:** `RB0_REAL_LOGS.json`.

## 1. What real data was reachable

**The session's network policy refuses** every host that serves real PX4
flight logs or real fault datasets:
- PX4 Flight Review;
- Zenodo, which serves RflyMAD's 497 real flights;
- Figshare, which serves ALFA;
- Hugging Face, Kaggle, IEEE DataPort.

**Reachable:** raw GitHub files. The only real PX4 logs found there are the
test logs of PX4's own `pyulog` repository, six files:

| log | board | PX4 | real? | flew? |
|---|---|---|---|---|
| `sample.ulg` | AUAV X2.1 | 2017-era (fd483321) | real board | **no**: disarmed throughout, motors at 900 µs |
| `sample_appended.ulg` | Pixracer (FMUv4) | 1.6 (f54a6c29) | real board | no: disarmed, landed |
| `sample_appended_multiple.ulg` | Pixhawk 4 Pro (FMUv4 Pro) | 1.6 | real board | no |
| `sample_log_small.ulg` | CubeOrange (VTOL airframe 13014) | 1.11 (8583f1da) | real board | **barely**: armed 5.6 s, airborne 1.1 s at about 1 m; a reduced logging profile |
| `sample_logging_tagged_and_default_params.ulg` | — | 1.13 | **SITL** | no |
| `sample_px4_events.ulg` | — | 1.14 | **SITL** | 11 s |

**This is RB0 in name only.** There is real sensor and timing data, but
there is no real propulsion data:
- no real flight of any length;
- no `actuator_motors` or `esc_status` on any real board;
- no fault.

**Nothing is calibrated on it.**

## 2. What it shows

**The product crashed on all six (RR-01).**
- **What happened:** `analyze flight.ulg` raised `KeyError` in the 2.2
  estimator reader, which requires PX4 547e2ca's `estimator_status`
  fields.
- **Why:** older PX4 versions name or omit them (`accel_device_id`,
  `hdg_test_ratio`).
- **Why it matters:** an analyzer that crashes cannot say what it could not
  observe.
- **The fix, narrow:** a schema mismatch is now a coverage notice and the
  estimator producer is not run. Logs with the fields take exactly the old
  path; the 2.2 and 2.3 reports reproduce byte for byte.
- **The test:** `tests/test_rb001_reality_bridge.py`.

**After the fix, the product says the honest thing on each.** It observed
0 or 1 of the profile's 29 records, and named why:
- `actuator_motors` and `esc_status` are absent (pre-control-allocation
  PX4);
- no battery current;
- the estimator schema mismatch;
- the frozen CUSUM has no input.

There were no events and no symptoms.

**Real timing** (`timing` per log):

| quantity | real boards | SITL |
|---|---|---|
| sensor_combined interval jitter (std) at 4 ms | 0.21-0.67 ms | 0 |
| actuator_outputs jitter (std) at 100 ms | 1.4-15.9 ms | 0-9 ms |
| largest gap in a high-rate topic | 33-164 ms | 4-16 ms |
| publish minus sample (vehicle_angular_velocity) | 0.40 ms median (CubeOrange) | 0 |
| logger dropouts | **3 of 4 real logs: 4 (119 ms), 1 (10 ms), 1 (30 ms)** | 0 in 79 SITL flights |

**Log completeness on real dropouts.** StockLog reads all 6 real dropouts,
and its gap check flags a window around every one (6/6).

**Gyro at rest** (disarmed or barely flown):
- **5 s peak body rate:**
  - median 0.006-0.25 rad/s across boards;
  - maximum 3.29 rad/s on the AUAV board, which was evidently moved by
    hand.
- **Windows over 2.3's theta_steady (0.0989 rad/s):** 2 of 13, 2 of 22, and
  1 of 1.
- **The CubeOrange's yaw rate at rest carries a 0.067 rad/s bias.**

**What that means for the steadiness rule.** A peak statistic picks up
handling, noise and uncorrected bias. Its SIH threshold is far too tight
for real boards, even at rest.

**Topic rates differ by version.** The newer SITL log (PX4 1.14 era) logs
`esc_status` at 248 ms by default, against 100 ms in 547e2ca. The stock
bridge's emulated rates are one version's, not PX4's in general.

## 3. Receipts produced

RR-01, RR-02, RR-03, RR-05 and RR-06 in `REALITY_RECEIPTS.json` /
`REALITY_RECEIPTS.md`.

## 4. The RB0 that is still needed

**Real flights with propulsion telemetry, nominal and faulted.** Two sources
would answer it without any hardware:
1. **The owner's own ULogs**, if any, with DShot or CAN ESC telemetry.
2. **RflyMAD's real subset:** 497 real multicopter flights with labelled
   faults, as ULogs (Le et al. 2023).

**Either can be placed under `/home/user/rb001_raw/`.** The RB0 script reads
any directory of ULogs. The maneuver-study harness reads any ULog that has
the stock topics.
