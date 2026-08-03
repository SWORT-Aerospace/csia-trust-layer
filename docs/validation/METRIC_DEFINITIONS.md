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

## 3. Detection metrics

> **Open gap (audit F-02).** Two distinct quantities are currently conflated
> and only the first is implemented. Published detection latencies
> (2.2 s / 13.0 s / 1.5 s) are **time-to-trust-threshold**, not time-to-alert.

| Metric | Definition | Status |
|---|---|---|
| **Time-to-trust-threshold** | First tick after fault onset where the target node's trust crosses a fixed value (currently hard-coded `0.85` in `validation.py:_detection` and `cli.py:_report`). | Implemented. Detector-internal; nothing in the system acts at 0.85. |
| **Time-to-alert** | Fault onset → first *alert episode* opening. Includes the per-class threshold, `dwell_up`, and `arm_time`. | **NOT YET IMPLEMENTED.** This is the number comparable to a PX4/ArduPilot health flag, and the one a baseline comparison requires. |

Until time-to-alert exists, every published latency must be labelled
*time-to-trust-threshold (0.85)*.

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
