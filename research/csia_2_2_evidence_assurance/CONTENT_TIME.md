# Content time and processing time (Phase 5)

**2026-10-01.**

| time | meaning | used for |
|---|---|---|
| `content_time` | when the observed quantity was true | staleness (`max_content_age_s`), event windows, the evidence id |
| `produced_time` | when the producer emitted the output | impossible-metadata checks only (content after production; production in the future) |

**Freshness is always decided on content time.** Processing latency is
never read as freshness.

## 1. PX4: the two times differ by the fusion horizon

**Measurement.** XSYS-001 flight `XS1A1-C00-A-E055.ulg`, 17,172
`estimator_status` messages, V4 (measured here):

| quantity | value |
|---|---|
| `timestamp - timestamp_sample` | 0.152 s (min), 0.152 s (median), 0.156 s (p99 and max) |
| publication period | 0.004-0.020 s, median 0.008 s |
| `EKF2_DELAY_MAX` | 200 ms |

**Why** (PX4 547e2ca, V4): `EKF2::PublishStatus` sets `timestamp_sample` to
`_ekf.time_delayed_us()`, the delayed fusion horizon (`EKF2.cpp` line 1946).
An estimator output read at publication time is therefore already about
0.15 s old.

**What the contract does.** `px4_ekf2_estimator_status.json` sets
`max_content_age_s = 0.4`:
- the 0.2 s horizon bound;
- plus a 0.1 s analysis tick;
- plus 0.1 s.

An estimator that stops publishing is STALE within 0.4 s. An estimator that
publishes normally never is (0 STALE over the whole flight,
`datasets/H_full_flight_estimator`).

## 2. The 372-difference lesson

**The first replay of the v2 corpus through 2.2 had 372 decision
differences.**

**The cause.** The legacy adapter mapped a record's `timestamp_processed` to
the envelope's `produced_time`. Five scenarios were affected: CLOCK_DRIFT,
CPU_OVERLOAD, ESTIMATOR_LATE, MS_A2 and MS_A3.

**What their TIMING records describe:**
- a channel whose processing timestamp lies after the tick (a late value:
  PRODUCED_IN_THE_FUTURE);
- under CLOCK_DRIFT, one before its own validity timestamp (a drifting
  clock: PRODUCED_BEFORE_ITS_CONTENT).

Those timestamps are the claim (what the timing monitor observed), not the
monitor's own metadata. Read as envelope metadata they looked impossible, and
the producer was marked FAULTED for the tick. Reproduced with the old
mapping, the five scenarios give 759 impossible-metadata findings and 1,543
outputs withheld as PRODUCER_FAULTED_THIS_TICK.

**The fix.**
- The envelope's `produced_time` is when the producer emitted the output: the
  tick, for an in-process plugin.
- The record's own timestamps stay inside the record, as evidence.

After the fix: 0 rejections and 0 differences over 2,640 ticks
(`REPLAY_2_2_RESULTS.json`).

**The general rule.** Envelope times describe the output. Times inside the
record describe the world.

## 3. Event windows

**XSYS-001's witnesses carry a content time at the end of the window their
statistic covers:**
- T1 → 0.2 s;
- T3 → 15 s after onset.

**The validity is the window, not an age.** A T1 dynamics result held to C3
is 14.8 s old and still valid. The same statistic computed over T3 is
REGIME_INVALID (`ADAPTERS.md` §3).
