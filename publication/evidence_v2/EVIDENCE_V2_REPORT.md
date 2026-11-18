# Evidence v2: CSIA core engine, UAV domain

2026-11-18. Analysis, plotting and re-measurement only.

- **No engine logic changed.** No trust or diagnosis algorithm, threshold or
  sigma was modified.
- **interceptor_seeker** was not modified, extended, tuned or run.
- **What this change touches:** `publication/evidence_v2/`, one test
  (`tests/test_evidence_v2.py`), two Makefile targets and the document index.

**Regenerate:** `make evidence-v2`. It rebuilds every figure, table, stamp and
the numbers table below from committed inputs. It fails unless every output
matches `MANIFEST.sha256` byte for byte. The two measurements that depend on
the host and the wall clock (the soak and ArduPilot SITL) cannot be
bit-for-bit, so they sit behind `make evidence-v2-measure`. Their committed
outputs under `data/` are what `make evidence-v2` plots.

**Stamps.** Every output has a sidecar `<output>.stamp.json` holding:
- the git commit;
- dataset ids and log UUIDs;
- config files with SHA-256;
- seeds;
- the script and its hash;
- a run timestamp.

Bit-for-bit regeneration forces two conventions:
- **commit:** the last commit that changed the script, `_common.py` or any
  declared input or config;
- **run timestamp:** that commit's committer time (the SOURCE_DATE_EPOCH
  convention).

Wall-clock measurement times are in the measurement data, and stamps quote
them as `measured_at_utc`.

**Definitions.** `publication/system_paper_i/evidence_export/02_FROZEN_DEFINITIONS.md`
freezes only T_NA, T_UH, T_FH, T_SOFH and SOI. Where it is silent, the owner
decided on 2026-11-18 that two repo-normative sources may be used, each cited
verbatim:
- `docs/validation/METRIC_DEFINITIONS.md`;
- the Phase 5 preregistration, `research/phase5/PREREGISTRATION_PHASE5.md`.

Anything defined in none of these was not produced; it is listed in
section 6.

## 1. Status of the seven deliverables

| item | status | outputs | in one line |
|---|---|---|---|
| D1 calibration (reliability diagram, ECE) | BLOCKED | none | No repository source defines trust as a probability of channel health, a channel-health label per tick, a binning or an ECE. Systems Paper I says no calibration is claimed. The 26 logs have no ground truth. |
| D2 alert rate on the 26 real logs | PARTIAL | `tables/d2_alert_episode_rate_checkpoint.csv` | The 3.859 per monitored hour checkpoint and its Garwood interval reproduce exactly. The operating curve is BLOCKED: no definition, and no per-tick data reachable. |
| D3 latency per UAV fault mode | PRODUCED, with deviations | `figures/d3_latency_ecdf.png`, `tables/d3_latency_stages.csv`, `data/d3_mc_runs.json` | Named stages, not "detection latency". GPS dropout is not a harness class and is reported as one catalogue run. |
| D4 soak | PRODUCED | `figures/d4_soak.png`, `tables/d4_soak_summary.csv`, `data/soak_*` | A fresh 277,500-tick measurement on this host; 0 errors, no memory growth. |
| D5 SITL refresh | PRODUCED for ArduPilot; PX4 SIH INAPPLICABLE | `tables/d5_sitl_before_after.csv`, `data/d5_sitl_ardupilot.json` | The mission row reproduces. The glitch row PASSes only because the fix-kill raised the alert; the glitch itself left GPS trust at 0.99. |
| D6 flat-monitor ablation | PRODUCED from locked data | `figures/d6_flat_monitor.png`, `tables/d6_flat_monitor_locked.csv` | The brief's "B3" is this repository's `B2`. At zero observed false alarms, the flat threshold is faster (0.08 s against 2.54 s). |
| D7 EuRoC MAV replay | BLOCKED | none | The network policy refuses the ETH hosts. EuRoC also carries no GPS, baro, magnetometer or battery stream for the UAV graph. |

## 2. Results

### D2. The real-log checkpoint

The inputs are `datasets/reports/exposure_v2.json` and
`data/real_logs_report.json`. Recomputed from them:
- 2 alert episodes over 0.5183 monitored hours, summed per log as duration
  minus the 20 s arm time;
- 3.859 episodes per monitored hour;
- exact Garwood 95-percent interval [0.467, 13.939].

All of these equal the committed values. Raw hours recompute to 0.6628,
against 0.6627 in the artifact, because the per-flight durations are rounded
to 0.1 s.

This is **not a false-alarm rate**. The corpus is UNANNOTATED, and its
verified-healthy exposure is 0.0 h.

### D3. Latency by named stage

The source is the UAV fault-harness Monte Carlo, `csia mc`
(`csia.validation.monte_carlo`): 150 runs, seed 0, field_mode. Its stream is
replayed exactly, and re-aggregating the runs reproduces
`campaigns/monte_carlo.json` field for field (`IDENTICAL`).

Each run is scored by `csia.metrics.latency.measure`, with the
METRIC_DEFINITIONS.md stage names. "Detection latency" is a term that document
retires.

| fault class | runs | trust < 0.85 (analysis only) | first operator alert event | correct isolation (conf 0.90) |
|---|---|---|---|---|
| gps_spoof | 25 | 25: median 2.98 s, p95 9.11 s | **18**: median 5.16 s, p95 6.76 s | 0 |
| mag_emi | 25 | 25: median 1.94 s, p95 2.53 s | **0** | 0 |
| power_sag | 18 | 18: median 1.69 s, p95 2.58 s | **13**: median 3.92 s, p95 7.71 s | 0 |
| vibration | 23 | 23: median 2.02 s, p95 2.51 s | 23: median 5.25 s, p95 5.75 s | 23: median 0.75 s, p95 1.05 s |
| imu_bias | 9 | 0 | 0 | 0 |

Medians and p95 are order statistics over the runs that reached the stage
(numpy `inverted_cdf`). `campaigns/monte_carlo.json` computes its p95 as
`sorted[int(0.95 (n - 1))]`, which differs at these sample sizes: for
gps_spoof it gives 7.88 s, against 9.11 s here. Both are in the table.

The 50 clean runs raised 0 alert episodes in 0.83 h (Poisson 95-percent upper
bound 4.43 per hour, as committed).

**Conditioning.** Every run flies the same trajectory and the same sensor
noise: `make_sensors` in `csia/scenarios.py` fixes seeds 1 to 8. What varies is fault
class, amplitude scale in [0.5, 2.0), onset in [15, 35) s, and the
clean/faulted split. The distributions describe that variation and nothing
else.

**GPS dropout** has no harness class. The catalogue scenario `gps_dropout`
(onset 25 s, field_mode) was run once:
- GPS trust **held** (minimum 0.998);
- an alert episode, CAUTION "GPS data invalid", opened **1.04 s** after onset;
- the diagnosis stayed nominal.

The catalogue describes that scenario as "trust must HOLD, not false-alarm".

### D4. Soak

The runtime ran 185 passes of the `clean` scenario through the time-reset
path, 277,500 ticks, on a 4-vCPU Xeon container. Per-tick time is the engine's
own `latency_us`:

| median | p95 | p99 | p99.9 | max | mean |
|---|---|---|---|---|---|
| 289.7 µs | 451.0 µs | 567.9 µs | 1020.6 µs | 11,574 µs | 308.3 µs |

- **Errors:** 0 contained errors.
- **Memory:** peak RSS growth from pass 3 to pass 185 is 0.00 MB; current RSS
  growth is 0.05 MB.
- **Latency stability:** the last-pass mean is 0.96 times pass 3.
- **Verdict:** tools/soak.py criteria PASS.

These are host numbers, not on-target ones.

**An instrument pitfall, recorded so it is not repeated.** A first measurement
appended one tuple per tick to a list, and that list alone raised peak RSS by
35 MB. Read naively, that is a leak. The committed measurement uses buffers
allocated before the run.

### D5. ArduPilot SITL at HEAD

Setup:
- ArduCopter V4.8.0-dev @ `01a504b`, built here
  (`./waf configure --board sitl && ./waf copter`);
- `tools/sitl_validate.py`, unchanged since `758f4ae`, the commit that wrote
  the C13 row;
- three runs per mode.

| row | before (README prose, no artifact) | after, 3 of 3 runs at HEAD `66ec3e9` |
|---|---|---|
| C12 mission | PASS: 6 sensors, min trust 0.78, zero false alarms, landed (`f2786f6`) | PASS: 7 sensors, min trust 0.74 (battery), 0 non-NORMAL transitions, landed |
| C13 GPS glitch + fix-kill | PASS: both faults detected from the raw stream, GPS trust 0.99 to 0.70, nav CAUTION (`758f4ae`) | tool verdict PASS, but minimum GPS trust stayed **0.99**. The only alert is one CAUTION, "GPS data invalid (diagnosis nominal p=0.52)": the signature of the fix-kill, which the tool applies 12 s of wall time (about 48 s simulated at speedup 4) after the glitch. Every per-sensor minimum equals the no-injection runs. |

So at HEAD the **fix-kill** is caught, from freshness, and the **55 m glitch
is not reflected in any trust value**. The tool's verdict rule ("any non-NORMAL
transition whose reasons mention GPS") cannot tell the two apart. The tool
also never reads the glitch parameter back. The Mechanism B campaign on the
same build confirmed by readback that `SIM_GPS1_GLTCH_X` takes effect, but
under ALT_HOLD; this mission flies GUIDED.

**PX4 SIH: INAPPLICABLE.** PX4 SIH has no GPS-glitch parameter.
`research/v1_1/CURRENT_STACK_REPLICATION.md` declared this before any trial and
forbids a substitute.

### D6. CSIA against a flat per-sensor threshold, identical injections

These are the locked Phase 5 results, verified against their sealed SHA-256:
- 40 seeds, 1040 locked runs plus the IMU arm;
- one node (`vibration`);
- every series read by every detector.

The detectors are `B0` (CSIA: trust below theta for DWELL_TICKS) and `B2`
(the flat monitor: instantaneous lambda above tau).

| at zero observed false alarms (0 of 80 nominal runs) | detections | median delay |
|---|---|---|
| B0, theta 0.9 (its fastest setting) | 960 of 1280 | 2.54 s [2.40, 2.68] |
| B2, tau 0.1905 | 960 of 1280 | **0.08 s** [0.08, 0.08] |

The 320 undetected runs are the IMU arm, which neither vibration-node detector
can see. Both detectors catch every vibration-family run.

- **Robustness** goes the other way. B0 holds zero false alarms at all 9
  thresholds. B2 does so at 1 of 6. B2's development-selected threshold, tau
  0.1355, gave 12 of 80 on the locked partition.
- **Attribution accuracy is not compared.** B2 has no attribution by
  preregistration (section 3), and B0 is a detector, not a diagnosis.

## 3. Every number produced

Generated by `build_numbers_table.py` from the stamped tables; the full table
is also `tables/all_numbers.csv`.

<!-- NUMBERS:BEGIN -->
| item | quantity | value | script | commit |
|---|---|---|---|---|
| D2 | logs | 26 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | alert_episodes | 2 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | raw_hours | 0.6628 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | monitored_hours | 0.5183 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | rate_per_monitored_hour | 3.859 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | garwood_95_lower | 0.467 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | garwood_95_upper | 13.939 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | rate_per_raw_hour | 3.018 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | garwood_95_lower_raw_basis | 0.365 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D2 | garwood_95_upper_raw_basis | 10.901 | `tab_d2_alert_rate_checkpoint.py` | `fce875955d2e` |
| D3 | gps_spoof time_to_trust_threshold_0_85 | 25/25 runs; median 2.984 s; p95 9.105 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | gps_spoof time_to_alert_event | 18/25 runs; median 5.164 s; p95 6.759 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | gps_spoof time_to_correct_isolation | 0/25 runs reached it | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | mag_emi time_to_trust_threshold_0_85 | 25/25 runs; median 1.943 s; p95 2.53 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | mag_emi time_to_alert_event | 0/25 runs reached it | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | mag_emi time_to_correct_isolation | 0/25 runs reached it | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | power_sag time_to_trust_threshold_0_85 | 18/18 runs; median 1.693 s; p95 2.58 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | power_sag time_to_alert_event | 13/18 runs; median 3.915 s; p95 7.708 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | power_sag time_to_correct_isolation | 0/18 runs reached it | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | vibration time_to_trust_threshold_0_85 | 23/23 runs; median 2.021 s; p95 2.511 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | vibration time_to_alert_event | 23/23 runs; median 5.249 s; p95 5.752 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | vibration time_to_correct_isolation | 23/23 runs; median 0.751 s; p95 1.047 s | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | imu_bias time_to_trust_threshold_0_85 | 0/9 runs reached it | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | imu_bias time_to_alert_event | 0/9 runs reached it | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D3 | imu_bias time_to_correct_isolation | 0/9 runs reached it | `fig_d3_latency_ecdf.py` | `ac5c2cfa20d7` |
| D4 | ticks | 277500 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | passes | 185 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | contained_errors | 0 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | tick_time_median_us | 289.7 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | tick_time_p95_us | 451.0 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | tick_time_p99_us | 567.9 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | tick_time_p99_9_us | 1020.6 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | tick_time_max_us | 11574.3 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | tick_time_mean_us | 308.3 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | pass_mean_ratio_last_over_pass3 | 0.9571 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | peak_rss_growth_mb_pass3_to_last | 0.0 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | current_rss_growth_mb_pass3_to_last | 0.05 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | soak_py_verdict | PASS | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | wall_seconds | 211.565 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | measured_at_utc | 2026-11-18T22:22:01Z | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | host_cpu | Intel(R) Xeon(R) Processor @ 2.10GHz | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | host_vcpu | 4 | `fig_d4_soak.py` | `fce875955d2e` |
| D4 | loadavg_before_1min | 0.36 | `fig_d4_soak.py` | `fce875955d2e` |
| D5 | before C12 (none), f2786f6 | PASS: 6 sensors monitored, min trust 0.78, zero false alarms, landed | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D5 | before C13 (gps_glitch), 758f4ae | PASS: both faults detected live from the RAW receiver stream (GPS trust 0.99 -> 0.70, nav CAUTION raised) | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D5 | after C12 (none) rep 1 | PASS — MAVLink mapping SITL-validated; sensors 7; min trust 0.74; min gps 0.99; non-NORMAL transitions 0 (0 citing GPS); landed yes | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D5 | after C12 (none) rep 2 | PASS — MAVLink mapping SITL-validated; sensors 7; min trust 0.74; min gps 0.99; non-NORMAL transitions 0 (0 citing GPS); landed yes | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D5 | after C12 (none) rep 3 | PASS — MAVLink mapping SITL-validated; sensors 7; min trust 0.74; min gps 0.99; non-NORMAL transitions 0 (0 citing GPS); landed yes | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D5 | after C13 (gps_glitch) rep 1 | PASS — injected GPS fault on a REAL autopilot detected live; sensors 7; min trust 0.74; min gps 0.99; non-NORMAL transitions 1 (1 citing GPS); landed not printed | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D5 | after C13 (gps_glitch) rep 2 | PASS — injected GPS fault on a REAL autopilot detected live; sensors 7; min trust 0.74; min gps 0.99; non-NORMAL transitions 1 (1 citing GPS); landed not printed | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D5 | after C13 (gps_glitch) rep 3 | PASS — injected GPS fault on a REAL autopilot detected live; sensors 7; min trust 0.74; min gps 0.99; non-NORMAL transitions 1 (1 citing GPS); landed not printed | `tab_d5_sitl_before_after.py` | `fce875955d2e` |
| D6 | B0 threshold 0.4 | detections 960/1280; false-alarm runs 0/80; median delay 7.36 s [7.24, 7.48] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.5 | detections 960/1280; false-alarm runs 0/80; median delay 6.6 s [6.36, 6.84] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.6 | detections 960/1280; false-alarm runs 0/80; median delay 6.02 s [5.8, 6.24] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.65 | detections 960/1280; false-alarm runs 0/80; median delay 5.72 s [5.48, 5.88] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.7 | detections 960/1280; false-alarm runs 0/80; median delay 5.2 s [5.16, 5.4] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.75 | detections 960/1280; false-alarm runs 0/80; median delay 4.32 s [4.32, 4.36] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.8 | detections 960/1280; false-alarm runs 0/80; median delay 3.8 s [3.8, 3.84] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.85 | detections 960/1280; false-alarm runs 0/80; median delay 3.12 s [3.12, 3.24] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B0 threshold 0.9 | detections 960/1280; false-alarm runs 0/80; median delay 2.54 s [2.4, 2.68] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B2 threshold 0.080450359 | detections 1260/1280; false-alarm runs 76/80; median delay 0.08 s [0.08, 0.08] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B2 threshold 0.094206102 | detections 1188/1280; false-alarm runs 66/80; median delay 0.08 s [0.08, 0.08] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B2 threshold 0.107961845 | detections 1072/1280; false-alarm runs 38/80; median delay 0.08 s [0.08, 0.08] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B2 threshold 0.13547333 | detections 984/1280; false-alarm runs 12/80; median delay 0.08 s [0.08, 0.08] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B2 threshold 0.162984816 | detections 968/1280; false-alarm runs 2/80; median delay 0.08 s [0.08, 0.08] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
| D6 | B2 threshold 0.190496302 | detections 960/1280; false-alarm runs 0/80; median delay 0.08 s [0.08, 0.08] | `fig_d6_flat_monitor.py` | `fce875955d2e` |
<!-- NUMBERS:END -->

## 4. Claims supported and not supported

**Supported.** Each holds within the scope stated beside it.

- The 26-log figure of 3.859 alert episodes per monitored hour, 95-percent CI
  0.467 to 13.939, is arithmetically reproduced from the committed counts. It
  is an alert-episode rate on unannotated replay, nothing more.
- In the field-mode fault harness, every fault class except imu_bias drives
  the target sensor's trust below 0.85, in a median of 1.7 to 3.0 s.
- In that harness, vibration faults are alerted (median 5.2 s) and correctly
  isolated (median 0.75 s) in 23 of 23 runs.
- The runtime ran 277,500 ticks without an error or memory growth on a desktop
  host.
- On ArduPilot 4.8 SITL at HEAD, a full mission flies and lands with seven
  sensors monitored and no alerts, three times out of three.
- A killed GPS fix is flagged within the run.
- With zero observed false alarms, CSIA's trust detector holds its false-alarm
  behaviour across every threshold tried (synthetic, one node).

**Not supported.**

- Any **calibration** statement about trust or hypothesis weights.
- A **false-alarm rate** from the 26 logs. No alert there can be called false.
- "**Detection** within about 2 s" for mag_emi, gps_spoof or power_sag, if
  detection means an operator alert. mag_emi raised no alert in 25 of 25
  field-mode runs; gps_spoof was alerted in 18 of 25 and power_sag in 13 of 18.
  The 2 s figures are the analysis-only trust crossing.
- **Attribution** of gps_spoof, mag_emi or power_sag faults. No run reached
  isolation confidence 0.90.
- **Detection of a GPS dropout as a fault.** By design trust holds, and the
  alert that does open comes from data freshness with a nominal diagnosis.
- "A 55 m GPS glitch caught from the raw stream" on current ArduPilot. GPS
  trust did not move.
- **PX4 GPS-glitch behaviour.** Not testable in SIH.
- "**CSIA detects faster than a simple threshold.**" On the only identical-
  injection comparison in the repository, the flat threshold was about 30
  times faster at the same zero observed false alarms.
- **EuRoC** behaviour. Not run.

## 5. Discrepancies found

Against the README:

1. `README.md:164` says the algorithm "is validated ... on real flight logs".
   The corpus is UNANNOTATED, and
   `publication/system_paper_i/evidence_export/08_REAL_LOG_RESULTS.md` prohibits
   describing it as validated.
2. The README's evidence table now lives in `docs/RUNTIME_AND_ARCHITECTURE.md`.
   Line 25 there gives the soak as 277,500 ticks, +0.0 MB, ratio 1.01x, with no
   committed artifact. `docs/evidence/evidence_matrix.md:35` (C15) gives a
   different soak: 21.2 h, +0.1 MB, 1.11x, also without an artifact. This
   re-measurement agrees on errors and memory; its ratio is 0.96.
3. `docs/RUNTIME_AND_ARCHITECTURE.md:23` reports mag, power and vibration at
   "100" (a percentage) and quotes alert latencies from the scripted
   sim-posture scenarios. In the field-mode Monte
   Carlo, mag_emi never alerts, gps_spoof alerts in 18 of 25 runs and
   power_sag in 13 of 18.
4. `campaigns/monte_carlo.json` labels the trust < 0.85 crossing as `detected`
   and `latency_*`. METRIC_DEFINITIONS.md section 3.2 forbids presenting that
   stage as detection.
5. The `csia/validation.py:11` docstring says the campaign varies "noise
   seeds". Sensor noise seeds are fixed (`make_sensors` in `csia/scenarios.py`), so
   it does not.
6. The pre-hardening SITL rows C12 and C13 (`docs/evidence/evidence_matrix.md`,
   README at `f2786f6` and `758f4ae`) have no artifact (WP-A2 row A9). C13's
   "GPS trust 0.99 to 0.70" is not reproduced on ArduPilot 4.8 at HEAD.
7. `tools/sitl_validate.py`'s glitch verdict passes on the fix-kill alone, so a
   PASS does not show the glitch was detected.

Against other repository documents:

8. METRIC_DEFINITIONS.md sections 1.2 and 2 still quote the raw-hours basis:
   2 episodes over 0.663 h, 3.02 per hour, interval "roughly 0.4 to 11". The
   published figure uses monitored hours: 3.859, [0.467, 13.939].
9. `csia/scenarios.py:28` says `gps_dropout` must "not false-alarm". In field
   mode a CAUTION episode opens 1.04 s after onset, from freshness, with a
   nominal diagnosis. Whether that counts as a false alarm is not defined.

Against the brief itself:

10. The brief calls the 26 logs "nominal-only". The repository records them as
    UNANNOTATED, with 0.0 h of verified-healthy exposure, and prohibits
    calling them healthy.
11. "B3 flat-monitor": in Phase 5, `B3` is "fast + current CSIA". The flat
    monitor is `B2`.
12. "Detection latency" is retired by METRIC_DEFINITIONS.md section 3.

Against the white paper: `deliverables/HANDOFF_WHITEPAPER.md` concerns
interceptor_seeker only. It was not evaluated, and no UAV number in it was
found to compare.

Against Systems Paper I (`papers/csia_systems/main.tex`):

- **No conflict.** It claims no calibration (around line 1479), and it states
  that its SITL numbers come from ArduCopter 3.3 and must be repeated on
  current stacks (around line 1356). This change repeats the C12/C13 rows, not
  Paper I's own SITL campaigns.

## 6. Blocked metric definitions the owner could freeze

- **D1.** Any of these would unblock it:
  - a mapping from per-sensor trust to a probability of channel health;
  - a per-tick, per-sensor ground-truth health label for the harness (beyond
    the injection target);
  - a binning rule;
  - an ECE weighting;
  - a bootstrap unit (run or tick).
- **D2 operating curve.** It needs:
  - a definition of "alarm at threshold theta" for real-log replay. Production
    alerting uses several per-class thresholds, and the only normative alert
    unit is the production alert episode;
  - per-tick traces of the 26 logs. The raw logs are not in the repository,
    and `logs.px4.io` is refused by the network policy.

  Even with both, the curve would be an alert-episode rate, not a false-alarm
  rate.
- **D3 for GPS dropout.** It needs a definition of what "detecting" a dropout
  means, when the catalogue requires trust to hold.
- **D6 across the six UAV fault modes.** It needs a preregistered flat-monitor
  campaign beyond Phase 5's single node.
- **D7.** It needs network access to the EuRoC host, plus a decision on how an
  IMU-and-camera dataset maps onto the UAV graph.

## 7. Reproduce

```
make evidence-v2                                   # bit-for-bit, about 4 minutes
make evidence-v2-measure AP_ROOT=/path/to/ardupilot  # new soak + SITL, not bit-for-bit
```

ArduPilot: fetch `01a504b472259602e13df4cf07df7c0cdbb35993`, init the
`waf`, `mavlink` (recursive), `DroneCAN/*`, `littlefs`, `lwip` and `gtest`
submodules, use `empy==3.3.4`, then
`./waf configure --board sitl && ./waf copter`.
