# 07 — Harness contract

**Primary harness:** `research/wp_c6/q_gvalid_campaign.py`
**Commit:** `700e898b603b20d5c4b9aab244be768fadd3e949`
**Reused by:** `research/wp_c7/*.py` and `research/wp_c8/*.py`, which import
`ARMS`, `DEFAULT_BINARY`, `DEFAULT_EEPROM`, `FLIGHT_SPECS`, `PREREG`, `_Shim`,
`_pilot`, `_set`, `locate_sitl` from it.
**Release package description:** `research/wp_c8/HARNESS_RELEASE.md`
(status: PREPARED, NOT PUBLISHED; see `HARNESS_RELEASE_AUDIT.md` at the
repository root).

---

## 1. Recorded streams, per tick

From `research/wp_c8/HARNESS_RELEASE.md`, verbatim:

| Layer | Quantity |
|---|---|
| injected | commanded offset, applied schedule, slew rate, hold duration |
| receiver | `fix_type`, `satellites_visible`, raw position |
| estimator | EKF `pos_horiz_variance` (normalised innovation test ratio), status flags |
| estimator | fused position, and fused-minus-truth against `SIMSTATE` |
| diagnostic | per-component residuals `nbr`, `phys`, `temp`, `stat`, pre-smoothing |
| diagnostic | fused evidence, forgetting factor, trust pre- and post-recursion |
| gating | per-feature gate state, applicability `A_h` per hypothesis |
| verdict | failsafe level, transitions with reasons, posterior over causes |

**Units, rates and timestamp semantics.** The harness records on a single
timebase: the CSIA layer's own tick clock at
25.0 Hz,
derived from MAVLink message time via `csia/runtime/plugins.py:map_mavlink`.
Per-stream unit and rate metadata is **not** emitted as a machine-readable
schema by the Phase-I harness: **UNRECOVERABLE** as a single file. It is recoverable
by reading `csia/runtime/plugins.py`, whose `MAVLINK_MESSAGE_MAP` documents the
message-to-channel mapping and unit conversions.

**Two documented adaptations** (`_Shim`): ArduPilot publishes the primary IMU
as `RAW_IMU` rather than `SCALED_IMU`, in the same mG / mrad-s / mgauss units,
so the shim relabels it; and `GPS_RAW_INT.time_usec` is suppressed because on
3.3 it is last-fix time and freezes on fix loss.

---

## 2. Preregistered measurement contract, verbatim

```python
PREREG = {
    "tick_hz": 25.0,
    "arm_time_s": 20.0,
    "monitored_tick": "armed is True AND layer time >= arm_time_s",
    "conditioning_window_s": 25.0,
    "conditioning_window": (
        "[injection_time_s, injection_time_s + 25 s]. The hypothesis label is "
        "the injection state, so the window over which q_gvalid|h is "
        "estimated must be the window in which h holds. In the nominal arm "
        "the same instant passes with no parameter applied, so the window is "
        "[60 s, 85 s] in every arm and the design is matched. 25 s is chosen "
        "because ArduPilot's own EKF failsafe switches to LAND under GNSS "
        "loss and the vehicle eventually disarms; the window is sized to sit "
        "inside the armed segment that leaves, in every arm."),
    "min_window_coverage": 0.95,
    "gvalid_closed_at_tick": "TrustState.edges['altitude_baro'][1] == 0.0 "
                             "(online.py:517-518 gates that edge on gvalid "
                             "alone, so it is a direct readout of the gate)",
    "per_flight_statistic": "closed monitored ticks in the conditioning "
                            "window / monitored ticks in the conditioning "
                            "window",
    "secondary_statistic": "the same ratio over the whole monitored window, "
                           "which dilutes the fault arms with their own "
                           "pre-injection nominal segment and is reported "
                           "only for completeness",
    "arm_statistic": "mean over flights (flight is the independence unit, "
```

---

## 3. Permanent validity rule

> **COMMAND ISSUED != FAULT INJECTED.**

A parameter write that the autopilot silently ignores produces a clean flight
labelled as a fault arm. The Phase-I harness satisfies this by recording a
**downstream** observable for every arm: the gate state
(`TrustState.edges['altitude_baro'][1]`) is a direct readout of `gvalid`, and
`injection_effect` records the receiver-side change (satellite counts, fix
state). No Phase-I result rests on the command alone.

`min_window_coverage = 0.95` in `PREREG` is the coverage floor a flight must
meet for its window to count.

---

## 4. Reproducibility warning, DISCOVERED IN LATER WORK

**This is not Phase-I evidence and no Phase-I number depends on it.** It is
recorded here because anyone re-running the Phase-I harness on a modern
autopilot will hit it.

The SIM GPS parameters were renamed between ArduCopter 3.3 and 4.x:
`SIM_GPS_GLITCH_X`, `SIM_GPS_DISABLE`, `SIM_GPS_NUMSATS`, `SIM_GPS_BYTELOSS`
became `SIM_GPS1_GLTCH_X`, `SIM_GPS1_ENABLE`, `SIM_GPS1_NUMSATS`,
`SIM_GPS1_BYTELOSS`. **A `param_set` to a name that does not exist is a silent
no-op.** Running the Phase-I scripts unchanged against a 4.x build therefore
produces clean flights labelled as fault arms.

Source of this warning: Phase-II work under `research/phase2/`. It is a
methodology and reproducibility note only. **Phase-II numerical results are
excluded from this export.**
