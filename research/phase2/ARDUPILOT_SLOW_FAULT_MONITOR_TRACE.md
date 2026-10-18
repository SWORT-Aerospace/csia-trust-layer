# Does modern ArduPilot already own F3?

**Source-reading task. Nothing was implemented and nothing was changed.**
Target: ArduCopter V4.8.0-dev @ `01a504b`, the same tree E1 flew against.

**Answer: partly yes, and the part that would own F3 is switched off in
flight by an explicit gate.**

---

## 1. What F3 is, restated in ArduPilot's terms

E1's joint-miss regime is a GNSS position error that grows slowly enough that
the normalised innovation never crosses a threshold, but accumulates to an
operationally significant total displacement. Measured: 56.4–56.5 m of injected
offset at 0.23–0.93 m/s, with `pos_horiz_variance` peaking at 0.139–0.525
against the 0.8 default.

So the question is whether ArduPilot has anything that **integrates** a
sub-threshold error rather than thresholding its instantaneous value.

---

## 2. It does. `NavEKF3_core::calcGpsGoodToAlign`

`libraries/AP_NavEKF3/AP_NavEKF3_VehicleStatus.cpp:58-66`:

```cpp
gpsDriftNE += gpsloc_prev.get_distance(gpsloc);
gpsloc_prev = gpsloc;
// Decay distance moved exponentially to zero
gpsDriftNE *= (1.0f - deltaTime/posFiltTimeConst);
// Clamp the filter state to prevent excessive persistence of large transients
gpsDriftNE = MIN(gpsDriftNE,10.0f);
// Fail if more than 3 metres drift after filtering whilst on-ground
bool gpsDriftFail = (gpsDriftNE > 3.0f*checkScaler) && onGround
                    && (frontend->_gpsCheck & MASK_GPS_POS_DRIFT);
```

This is exactly the right shape of detector: a leaky integrator of GPS
position movement, clamped, compared against a fixed distance threshold. It is
enabled by default — `EK3_GPS_CHECK` defaults to `31`
(`AP_NavEKF3.cpp:429`), which sets `MASK_GPS_POS_DRIFT`.

**And it is gated on `onGround`.** It is a pre-arm and alignment check. Once
the vehicle is airborne the term is never evaluated, whatever the drift.

That single conjunct is why E1's regime is not owned by it.

**Is the threshold even relevant?** The check would fail above 3 m of filtered
drift. E1's injections realised 56 m. Had the gate not been there, the
magnitude is more than an order of magnitude past the trip point. So this is a
scope decision, not a sensitivity shortfall.

---

## 3. What runs in flight instead

### 3.1 `Copter::ekf_check` — duration-aware, but on an instantaneous statistic

`ArduCopter/ekf_check.cpp`:

```
EKF_CHECK_ITERATIONS_MAX = 10      // 1 second at 10 Hz of bad variances
```

`ekf_check` is genuinely duration-aware: `fail_count` must exceed 10
consecutive bad iterations before `bad_variance` is set. But the quantity it
counts is `ekf_over_threshold()`, which reads
`ahrs.get_variances(...)` and low-pass filters it
(`ekf_check.cpp:129-130`):

```cpp
position_var = pos_variance_filt.apply(position_var, dt);
vel_var      = vel_variance_filt.apply(vel_var, dt);
```

A low-pass filter of a signal that never exceeds the threshold also never
exceeds the threshold. **Duration-awareness applied to an instantaneous
normalised innovation is not integration of the error.** This is the same
structural point the Phase-I algebra made about CSIA's dwell: waiting longer
does not help when the statistic itself is bounded below the trip point.

It is also **stricter than the criterion this programme used for B0**
(`ekf_check.cpp:142-154`): it requires **two of three** variances over
threshold, or velocity variance at **twice** threshold. B0 as measured here
fires on any single channel exceeding `FS_EKF_THRESH`, so B0 is generous to the
autopilot rather than a strawman. E1's cells did not come close to either.

### 3.2 Innovation test ratios

`posTestRatio` and `velTestRatio` (`AP_NavEKF3_core.h:1173-1174`) are sums of
squared innovations divided by a fail threshold — normalised, instantaneous
consistency measures. They are what `EKF_STATUS_REPORT` publishes and what E1
measured. No accumulator.

### 3.3 Lane switching

E1 and the P1 suite both recorded `EKF3 lane switch` and
`EKF3 primary changed` STATUSTEXTs during GPS injections. Lane switching
compares core error scores and picks a better core; with a single simulated
GPS every core sees the same corrupted measurement, so it relocates the
problem rather than detecting it.

---

## 4. Answer to each question in the brief

| question | answer |
|---|---|
| Does modern ArduPilot implement a cumulative / drift / slow-error monitor relevant to E1? | **Yes.** `gpsDriftNE` in `calcGpsGoodToAlign` is a leaky-integrator GPS position-drift monitor with a 3 m trip point. |
| Is it enabled? | **Yes by default** (`EK3_GPS_CHECK = 31` includes `MASK_GPS_POS_DRIFT`) — but only where its gate permits. |
| What signals does it use? | Successive GPS horizontal positions, accumulated and exponentially decayed; the same raw receiver stream CSIA's `phys_gps` uses. |
| Why did it not activate in E1? | **`&& onGround`.** The vehicle was airborne for the entire injection. The check is scoped to pre-arm and alignment. |
| Is E1 therefore a configuration/tuning result? | **No — it is a scope result, which is a third thing.** No parameter available to an operator moves this: the `onGround` conjunct is compiled in, not a bitmask bit or a threshold. `EK3_GPS_CHECK` can only disable the check, never extend it to flight. Calling E1 "just tuning" would be wrong, and so would calling it "no such capability exists". |

---

## 5. What this does to the F3 claim

E1's result stands as measured and is unchanged. What changes is its
interpretation:

- The **capability** to detect an accumulated GNSS position drift exists in
  ArduPilot today, in the same estimator, on the same signal.
- It is **deliberately scoped to the ground**, where its meaning is "do not
  arm on a wandering fix".
- In flight nothing integrates the error, in either monitor. Both ArduPilot's
  `ekf_check` and CSIA's dwell are duration-aware wrappers around
  instantaneous statistics.

So the honest framing of F3 is **not** "nobody has built this detector". It is:
**the detector exists and is not applied to the flight phase where E1's regime
lives.** Any later claim about F3 must say that, and no invention argument may
be built on the premise that the mechanism is absent.

---

## 6. Limits of this trace

- Source reading only. Nothing here was compiled, instrumented or executed to
  confirm the `onGround` gate blocks the path at runtime; the conclusion rests
  on the conjunct being unconditional in the source and on E1's measured
  absence of any drift-related STATUSTEXT in flight.
- ArduCopter only. Plane and Rover share `AP_NavEKF3` but have their own
  failsafe layers, unexamined.
- No search was made for vendor or third-party GNSS spoofing monitors outside
  `AP_NavEKF3` and `ArduCopter/`.
