# CSIA Metric Definitions

**Status:** normative. Where this document and a docstring disagree, this
document wins and the code is wrong.
**Implementation:** `csia/metrics/` · **Tests:** `tests/test_metrics_events.py`

This file exists because the repository previously computed "false alarms"
three different ways and published the loosest of the three
(audit finding F-01, `docs/audit/CSIA_REPOSITORY_AUDIT.md`).

---

## 1. Alert counting

### 1.1 The three quantities

| Term | Definition | Use |
|---|---|---|
| **Transition** | Any `FailsafePolicy` state-machine edge, escalation **or** recovery. | Debugging and backward comparison only. **Never** an operator alert. |
| **Alert event** | A transition that *increases* severity (`level > previous`). | Detector sensitivity analysis. Over-counts operator burden, because one incident can escalate twice. |
| **Alert episode** | A contiguous non-NORMAL period: opens on the first escalation out of `NORMAL`, closes on return to `NORMAL`. Escalations *within* it do not open a new episode. Episodes separated by less than `merge_s` of recovered posture are merged. | **The operator-facing unit. This is the number to publish.** |

### 1.2 Why recoveries are not alarms

`FailsafePolicy._transition` appends on both escalation and de-escalation, so
`NORMAL → CAUTION → NORMAL` produces **two** `Transition` records for **one**
incident. The second issues `RESUME_NORMAL` — it tells the operator the
problem is over. Counting it as an alarm inflates the rate.

Measured on the committed 26-flight corpus (`data/real_logs_report.json`):

| Definition | Count | Rate (0.663 h) |
|---|---|---|
| transitions (previously published) | 3 | 4.52 / h |
| alert events | 2 | 3.02 / h |
| **alert episodes** | **2** | **3.02 / h** |

The previously published figure over-counted by **1.50×**. It erred
*pessimistically* — CSIA looked worse than it is — but it was still wrong.

### 1.3 Episode merging (`merge_s`)

Default **10.0 s**, chosen to exceed `FailsafeConfig.dwell_down` (5.0 s) so a
condition that satisfies de-escalation hysteresis and immediately re-trips
reads as one incident rather than two. `merge_s` is a reported parameter: any
episode count is meaningless without it, and it appears in every
`alert_summary()` output.

### 1.4 Open episodes

An episode still active when the log ends is **counted**, with `end=None`.
The operator saw the alert; the recording merely stopped first. Discarding
these would bias the rate downward on short logs — relevant here, because one
corpus flight is 35.4 s long and its CAUTION never clears.

---

## 2. Rate reporting

Rates are events per flight-hour with an **exact (Garwood) Poisson 95 %
interval**. At the current corpus size (2 events / 0.663 h) the interval spans
roughly 0.4–11 /h. **A point estimate from fewer than ~5 events must not be
quoted without its interval** — `csia analyze-logs` prints a warning below
that threshold.

---

## 3. Latency metrics

**Implementation:** `csia/metrics/latency.py` — the single owner. Latency logic
must not be duplicated in CLI commands, validation scripts, Monte Carlo tooling,
report generation, or scenario tests.

**The term "detection latency" is retired.** It conflated stages that differ by
1.9×–2.7× in measurement, and in one scenario differed between "13 seconds" and
"never". Each stage below names itself and its threshold.

### 3.1 Fault onset — four distinct timestamps

They are **not** assumed equal. `OnsetBasis` carries all four; every result
records which one it used in `onset_basis`.

| Basis | Definition | Status |
|---|---|---|
| `configured` | The injection/annotation start time (`Fault.start`). | Always available. Default. |
| `first_corrupted_sample` | First sample that differs from a clean reference run. | Available only when a clean reference is supplied. |
| `first_observable_effect` | First sample where the corruption is visible in any comparator residual. | Not implemented — reported `None`. |
| `first_theoretically_detectable_effect` | First point where the corruption exceeds the noise floor of some check. | Not implemented — requires a per-check detectability model CSIA does not have. Estimating it would fabricate precision. |

### 3.2 Time to trust threshold — **ANALYSIS ONLY**

Onset → target source's trust first crosses a named analysis threshold.
**Must always name the threshold**, e.g. `time_to_trust_threshold_0_85`.

**This is not operator-facing detection latency and must never be labelled as
such.** The analysis threshold has no operational effect: no `FailsafeConfig`
field equals it and no condition compares trust against it to raise a level.

> A numerically identical literal `0.85` *does* appear operationally at
> `csia/runtime/failsafe.py:130`, as a guard inside the `imu_isolated`
> condition. The two are equal by coincidence and semantically unrelated. The
> production literal remains un-named and is tracked as an open item
> (`docs/audit/CSIA_LATENCY_PATH_AUDIT.md` §2).

### 3.3 Time to alert event

Onset → first qualifying **non-recovery** operator-facing alert event. The
event must satisfy *all* of: the per-class production threshold, `arm_time`,
`dwell_up`, the failsafe-policy conditions, and the suppression rules
(disarmed hold, `reset_timers()`). This is the number comparable to a
PX4/ArduPilot health flag.

### 3.4 Time to alert episode

Onset → opening of the alert **episode** that owns the first event. Equal to
§3.3 when the episode opens with that event; they diverge only when an episode
is merged across a flap. `alert_escalations` reports further escalations inside
the episode (a `CAUTION→CRITICAL` step is a new *event*, not a new *episode*).

### 3.5 Time to classification

Onset → first tick where any non-`nominal` cause reaches the classification
confidence threshold. **Always report the threshold** —
`classification_confidence_threshold`, default 0.90.

### 3.6 Time to correct isolation

Onset → first tick where the *leading* cause accuses the faulted source at or
above the isolation confidence threshold (default 0.90). Cause→source mapping
is `CAUSE_TO_SOURCE`. Outcomes are mutually exclusive:

| Outcome | Meaning |
|---|---|
| `CORRECT` | Leading cause names the faulted source. |
| `INCORRECT` | Leading cause reached confidence but named a different source. |
| `AMBIGUOUS` | Confidence reached by a cause naming no single source (`unexpected_maneuver`). |
| `NONE` | No cause reached the threshold. |

*Common-cause* and *multiple-source* isolation are not yet representable: the
cause set is single-source by construction. Recorded as a gap, not simulated.

### 3.7 Time to arbitration recommendation

Onset → first bounded operational recommendation (`ARBITRATION_ACTIONS`:
`SWITCH_NAV_INERTIAL`, `INHIBIT_GPS_MODES`, `SELECT_IMU`, `HEADING_HOLD_GYRO`,
`LIMIT_THROTTLE`, `REDUCE_POWER`, `PREPARE_LANDING`, `LAND_SOON`, `LAND_NOW`,
`STABILIZE`, `CONTROLLED_DESCENT`, `BROADCAST_MAYDAY`, `LIMIT_MANEUVERS`).
`RESUME_NORMAL` is a recovery notice, **not** a recommendation.

Usually equal to §3.3, but not by definition: a second condition dwelling
inside an ongoing episode issues actions without a level change.

### 3.8 Time to applied mitigation — **UNAVAILABLE**

Onset → the receiving system confirms the recommendation was applied.
**Always `None`.** CSIA is advisory; no actuator reports back. Reported as
unavailable with a reason string, never simulated.

### 3.9 Time to recovery

Fault removal → posture leaves the degraded state (episode closes). `None` if
the episode never closed. Requires `dwell_down` of sustained health.

### 3.10 Time to trusted re-entry

Fault removal → the recovered source's trust returns to or above its production
threshold, i.e. it may contribute again.

**Recovery and trusted re-entry are not simultaneous and must not be assumed
so.** The Beta recursion recovers gradually (ρ ≤ 0.998), so posture can return
to NORMAL while the source is still below its re-trigger value.

### 3.11 Fault ↔ alert association

Deterministic, tested, and shared across tools (`associate_episode`):

1. Candidate episodes are those opening in `[onset, fault_end + grace_s]`
   (`grace_s` default 15 s, covering dwell plus trust-recovery lag).
   **An episode opening before onset is never attributed to the fault** — it is
   pre-existing state or a false alert.
2. Among candidates, the **earliest-opening** episode wins.

With overlapping faults, association is evaluated per fault: one episode may
legitimately be attributed to two faults, and that is *reported* rather than
arbitrated, because a single posture genuinely can be supported by both.
`unassociated_episodes()` returns episodes owned by no fault — the false-alert
set during healthy operation.

### 3.12 Measured stage gap (sim posture, onset 20 s, ×1.0)

| scenario | to trust<0.85 | to alert | ratio |
|---|---|---|---|
| gps_spoof | 2.16 s | 4.40 s | 2.0× |
| mag_emi | 1.52 s | 3.88 s | 2.6× |
| power_sag | 1.36 s | 3.40 s | 2.5× |
| vibration | 2.16 s | 5.76 s | 2.7× |
| imu_bias | 13.00 s | **no alert** | — |

The constant component is exactly `dwell_up + 1 tick` = 1.04 s; the variable
component is the distance from 0.85 down to the sensor's own threshold.

`imu_bias` raises **no operator alert at any time**: `max(imu0, imu1)` stays
above `att_caution` because `imu1` remains healthy. Redundancy behaving
correctly — but the previously published "13.0 s detection" described no
operator-visible event.

---

## 4. Reporting requirements

Every result that quotes a rate or a latency records: trial count, the
`merge_s` used, the threshold configuration, the random seed, and the
confidence interval. Excluded runs are reported with a count and a reason —
the corpus already excludes logs shorter than 30 s (`cli.py`), and that
exclusion is part of the metric.

---

## 5. Changelog

- **2026-08-03** — Initial version. Fixes F-01 by making *alert episode* the
  single published definition across `csia analyze-logs`, `csia bench`, and
  `csia mc`. Verified: `campaigns/bench.json` regenerates bit-identical, so
  no previously validated simulation result changed. Records F-02 as an
  explicit open gap rather than silently continuing to publish
  time-to-trust-threshold as "detection latency".
