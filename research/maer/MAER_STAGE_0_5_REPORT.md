# MAER Stage 0.5 — Receiver-Health Candidate Validation

## 1. FINAL VERDICT

**`RECEIVER_HEALTH_STRONG_CANDIDATE`** — on ArduPilot under `SIM_GPS1_JAM=1`
only. **Every PX4 candidate is `REJECT`.**

The PX4 result from the previous stage does not survive source inspection. All
six PX4 fields are hard-coded constants assigned in the *same if/else branch as
`fix_type`*, so they are the validity bit re-encoded as floats. My previous
"live" verdict was produced by the wrong test: I checked that the *record* was
live (`time_usec` advancing) rather than that the *field* was live, and every
candidate field had `distinct = 1` throughout the window — data I had already
collected and misread.

ArduPilot's jamming model is structurally different: `h_acc`, `v_acc` and
`vel_acc` are drawn from continuous distributions independently of lock state.
All four candidate × gate state combinations occur, so the candidate is not a
gate duplicate.

Two limits stated up front: the five JAM runs are **byte-identical replays of
one realisation** (SITL does not expose the RNG seed), and the measured lead
time is **negative** — no pre-loss warning was observed, and none is claimed.

---

## 2. PX4 SOURCE PROVENANCE

`PX4-Autopilot@547e2ca`,
`src/modules/simulation/sensor_gps_sim/SensorGpsSim.cpp:155-172`:

```cpp
if (_sim_gps_used.get() >= 4) {
    sensor_gps.fix_type = 3;   sensor_gps.eph = 0.9f;   sensor_gps.epv = 1.78f;
    sensor_gps.hdop = 0.7f;    sensor_gps.vdop = 1.1f;  sensor_gps.s_variance_m_s = 0.4f;
} else {
    sensor_gps.fix_type = 0;   sensor_gps.eph = 100.f;  sensor_gps.epv = 100.f;
    sensor_gps.hdop = 100.f;   sensor_gps.vdop = 100.f; sensor_gps.s_variance_m_s = 100.f;
}
...
sensor_gps.satellites_used = _sim_gps_used.get();          // line 199
```

Wire mapping, `src/modules/mavlink/streams/GPS_RAW_INT.hpp:92-107`:

```
msg.eph                = gps.hdop * 100          ->  70    / 10000
msg.h_acc              = gps.eph  * 1e3          ->  900   / 100000  mm
msg.vel_acc            = gps.s_variance_m_s*1e3  ->  400   / 100000
msg.satellites_visible = gps.satellites_used     ->  the injected parameter
```

Every value measured in Stage 0.4 is reproduced exactly by these constants. The
chain is `SIM_GPS_USED → one if/else → sensor_gps → GPS_RAW_INT`, with no
intervening receiver process.

## 3. CANDIDATE ORACLE CLASSIFICATION

Classes were defined before results were examined.

| field | PX4 | ArduPilot (JAM) |
|---|---|---|
| `satellites_visible` | **DIRECT_ORACLE** — literally `_sim_gps_used.get()` | MODEL_GENERATED_HEALTH — `2 + get_random16()%15`, decoupled from `have_lock` |
| `eph` | **DIRECT_ORACLE** — same branch as `fix_type` | MODEL_GENERATED_HEALTH but **not driven** by jamming (constant 121) |
| `epv` | **DIRECT_ORACLE** | as `eph` |
| `h_acc` | **DIRECT_ORACLE** | **MODEL_GENERATED_HEALTH** — `fabsf(rand_float())*300` at ~3 Hz |
| `v_acc` | **DIRECT_ORACLE** | MODEL_GENERATED_HEALTH |
| `vel_acc` | **DIRECT_ORACLE** | MODEL_GENERATED_HEALTH |

Every PX4 field is additionally **GATE_DUPLICATE**: assigned by the same
predicate that sets `fix_type`.

ArduPilot, `libraries/SITL/SIM_GPS.cpp:288-345`:

```cpp
d.num_sats = 2 + (get_random16() % 15);
if (d.num_sats >= 4) {
    if (get_random16() % 2 == 0) d.have_lock = false;
    else                         d.have_lock = true;   // INDEPENDENT coin flip
} else d.have_lock = false;
...
d.horizontal_acc = fabsf(rand_float())*300;            // NOT conditioned on have_lock
```

`SIM_GPS_UBLOX.cpp:305`: `pvt.h_acc = d->horizontal_acc * 1000`. Nominal is
`SIM_GPS1_ACC * 1000 = 300 mm`.

No field is classified `INDEPENDENT_RECEIVER_OBSERVABLE`; nothing in either
simulator justifies that wording.

## 4. PX4 TEMPORAL RESULTS

356 messages, injection at t = 20.064 s, 198 at `fix_type < 3`.

| field | clean | fault | distinct while gate closed | lead time |
|---|---|---|---|---|
| `h_acc` | [900, 900] | [100000, 100000] | **1** | **0.0 s** |
| `eph` | [70, 70] | [10000, 10000] | 1 | 0.0 s |
| `satellites_visible` | [10, 10] | [0, 0] | 1 | 0.0 s |

State combinations for `h_acc`: `degraded_gate_closed` = 198, and **all three
other combinations = 0**. Lead time is exactly zero because both fields change
in the same publication cycle, which the source guarantees.

`MAER_PX4_RECEIVER_HEALTH_TIMING.csv`.

## 5. ARDUPILOT JAM RESULTS

Five runs, 201 clean + 600 jam messages each, 210 at `fix_type < 3` per run.

| field | clean envelope | jam range | distinct while gate closed | verdict |
|---|---|---|---|---|
| `h_acc` | [0, 300] | [150, 299486] | **49** | STRONG |
| `v_acc` | [0, 300] | [300, 299542] | 49 | STRONG |
| `vel_acc` | [0, 0] | [0, 4984] | 47 | STRONG |
| `satellites_visible` | [0, 10] | [3, 16] | **1** (frozen at 3) | REJECT |
| `eph` | [121, 65535] | [121, 121] | 1 | REJECT |
| `epv` | — | constant | 1 | REJECT |

**Seed control failed.** All five runs produced identical
`(fix_type, satellites_visible, h_acc)` sequences — one distinct SHA-256 across
five runs. SITL seeds its RNG the same way each boot and does not expose it, so
this is **N = 1 realisation replayed five times**, not five independent samples.
Recorded as a limitation; the brief asked for five independent realisations and
they are not available by this route.

`MAER_ARDUPILOT_JAM_SUMMARY.csv`, raw in `MAER_ARDUPILOT_JAM_RAW/`.

## 6. INVALID-FIX + LIVE-HEALTH WINDOWS

The state the whole stage exists to find.

| | PX4 | ArduPilot JAM |
|---|---|---|
| messages at `fix_type < 3` | 198 | 210 |
| `h_acc` distinct values there | **1** | **49** |
| duration | 19.8 s | ~21 s |

On ArduPilot, `h_acc` takes 49 distinct values across 210 messages while the
navigation solution is invalid — **invalid navigation solution with live
receiver health**, which is the condition a structural rescue needs. On PX4 the
same window yields a single constant.

## 7. PRE-FIX HEALTH-DEGRADATION WINDOWS

**None observed, and no early-warning claim is made.**

Measured lead time on ArduPilot: `t_first_invalid_fix = 20.216 s`,
`t_first_material_change = 21.616 s`, so **lead = −1.4 s**. Health degradation
*followed* fix loss in this realisation, because `simulate_jamming()` opens with
a total-loss period (`num_sats = 0; have_lock = false`) during which
`horizontal_acc` is not touched.

What *was* observed is the decoupling that matters:
**184 messages with `h_acc` materially degraded while `fix_type >= 3`** — the
gate open. That establishes non-degeneracy without any prediction claim.

## 8. CROSS-MODEL COMPARISON

State combinations for `h_acc`:

| combination | PX4 `SIM_GPS_USED=0` | ArduPilot `SIM_GPS1_JAM=1` |
|---|---|---|
| degraded, gate **open** | 0 | **184** |
| nominal, gate open | 0 | 206 |
| degraded, gate closed | 198 | 96 |
| nominal, gate closed | 0 | 114 |
| all four seen | **NO** | **YES** |

PX4 exhibits exactly one combination — the definition of a gate duplicate.
ArduPilot exhibits all four.

## 9. BEST CANDIDATE

**`h_acc` on ArduPilot under `SIM_GPS1_JAM=1`.**

- estimator-independent: sourced from the SITL GPS backend via the UBX driver,
  never from the EKF; the independence contract bars `estimator.variances`
  specifically and does not reach `GPS_RAW_INT`
- raw/protocol available, and currently discarded by the adapter's early return
  on `fix_type < 3`
- live while fix invalid: 49 distinct values over 210 messages
- not a validity duplicate: all four state combinations occur
- not a `DIRECT_ORACLE` under this model: drawn from a continuous distribution,
  not assigned from the intervention variable
- measurable clean behaviour: constant 300 mm (`SIM_GPS1_ACC * 1000`)

`v_acc` and `vel_acc` behave identically and are alternates, not additions —
**one scalar only**, per brief item 9.

## 10. CLEAN-ONLY TRANSFORM

Proposed, to be frozen in the preregistration and calibrated on clean data
only:

```
x_t = log(h_acc_t + 1)                         # h_acc is mm, spans 3 decades
z_t = (x_t - median_clean(x)) / MAD_clean(x)   # robust, clean-only
lambda_t = z_t^2                               # chi-square-like, matching the
                                               # existing _lam residual→evidence
                                               # convention in online.py
```

`median_clean` and `MAD_clean` come from clean flights only. Under a degenerate
clean envelope (SITL `h_acc` is constant) MAD is zero, so the preregistration
must fix a floor — `MAD_clean = max(MAD_clean, 1e-3)` — declared in advance
rather than chosen from fault separation. **No parameter is selected by looking
at fault traces.**

## 11. MATCHED GATED/UNGATED FEASIBILITY

**Feasible.** A research-only sidecar computes one scalar contribution:

| requirement | ARM A1 (ungated) | ARM A1G (gated control) |
|---|---|---|
| input | `h_acc` | `h_acc` — same samples |
| transform | as §10 | identical |
| clean calibration | same constants | same constants |
| evidence mapping | same `_lam` convention | identical |
| hypothesis association | `gps_fault` | identical |
| temporal filter | same EWMA | identical |
| normalization | same | identical |
| **gate** | `× 1` | `× gvalid` |

One multiplication is the only difference. The frozen core is untouched; the
field is ingested by the sidecar, since the adapter currently discards it.

## 12. REMAINING CONFOUNDS

1. **Single realisation.** Five identical replays, not five samples. The scored
   campaign needs a source of variation — different initial conditions, jam
   onset times, or a patched seed — declared in the preregistration.
2. **Simulator-model dependence.** `h_acc` under jamming is
   `|rand_float()| * 300`, a plausible but arbitrary distribution. Nothing here
   licenses a claim about physical receivers under real interference.
3. **Fault-model change.** JAM is not the fix-loss fault Mechanism A used.
   Conceded in full (Reviewer E): the two are different faults, and this stage
   tests whether the *candidate family* remains meaningful under a distinct
   degradation model, not that the physics match.
4. **Negative lead time.** No pre-loss warning in this realisation.
5. **Exploratory selection.** `h_acc` was chosen after seeing it move. This
   stage is explicitly exploratory and its selection is **not** preregistered.
6. **PX4 loses the structural arm entirely**, so the arm is ArduPilot-only and
   platform becomes a recorded factor rather than a replication.

## 13. HOSTILE REVIEW A–G

**A. "`h_acc` is just a hard-coded PX4 fault flag."**
**Conceded, and the candidate is rejected on PX4.** `SensorGpsSim.cpp:155-172`
assigns it as a literal constant in the same branch as `fix_type`. Every PX4
field is `DIRECT_ORACLE`. This objection is correct and cost the PX4 result.

**B. "The candidate changes at exactly the same instant as `fix_type`, so it is
the gate encoded as a float."**
**True on PX4** — lead time 0.0 s and exactly one state combination (198/0/0/0).
**False on ArduPilot** — all four combinations, including 184 messages degraded
with the gate open.

**C. "You picked `h_acc` because you saw it move by 111×."**
**Accepted as stated.** This stage is exploratory; the selection is not
preregistered and is not presented as such. The 111× figure was the PX4 oracle
and is now discarded. The final candidate, transform and hypotheses must be
frozen in a new preregistration before any scored trial.

**D. "The effect exists only because PX4's simulator manufactures the value."**
**Correct for PX4, and the reason cross-model qualification was required.**
ArduPilot's jamming model generates `h_acc` from a distribution rather than a
switch, so the candidate family survives on a second, structurally different
model. External interpretation remains simulation-bound.

**E. "Jamming and GPS disable are different faults."**
**Conceded without reservation.** No claim of identical physics. The purpose is
to test whether the candidate family is meaningful under a distinct GNSS
degradation model, and it is.

**F. "The new residual violates estimator independence."**
`GPS_RAW_INT` is receiver-side: ArduPilot fills it from the SITL GPS backend
through the UBX driver; PX4 from the `sensor_gps` uORB topic. Neither is EKF
output. The contract's exclusion names `estimator.variances` and its reason —
"CSIA must not consume the estimator it is meant to be independent of" — does
not reach the raw receiver message.

**G. "You designed the residual after seeing the fault."**
Acknowledged. Mitigations: the transform is calibrated on clean data only; the
material-change criterion was declared before evaluating any fault trace; and
the final form is frozen in a preregistration committed before scored trials.

## 14. PROPOSED REVISED MAER MATRIX

Draft only, in `MAER_REVISED_PREREGISTRATION_DRAFT.md`. Not run.

| | M0 CLEAN | M1 JAM / live-health | M2 PERSISTENCE RAMP | M3 TRANSPORT |
|---|---|---|---|---|
| A0 BASELINE | 5 | 5 | 5 | 5 |
| A1 RECEIVER_HEALTH_UNGATED | 5 | 5 | 5 | INAPPLICABLE |
| A1G RECEIVER_HEALTH_GATED | 5 | 5 | 5 | INAPPLICABLE |
| A2 CUSUM | 5 | 5 | 5 | 5 |
| A3 MECHANISM_AWARE_COMBINED | 5 | 5 | 5 | 5 |

The gate-event likelihood arm is **removed** from the primary campaign: two
fix-loss flights cannot support a calibration/test split, and forcing it in
would contaminate a clean experiment. A1/A1G × M3 are marked `INAPPLICABLE`
rather than manufactured — M3 runs on PX4, where the candidate is rejected.

## 15. SCIENTIFIC BLOCKERS

1. **No independent realisations available by the current route.** Must be
   resolved in the preregistration before scoring.
2. **The structural arm is ArduPilot-only.** PX4 cannot host it.
3. **M1 is a different fault from Mechanism A's fix loss.** The scored campaign
   tests jamming, and the relationship to the original self-occlusion result
   must be stated rather than assumed.
4. **No physical-receiver data.** Everything is simulation-bound.

## 16. RECOMMENDATION TO CHATGPT

Review two things specifically.

**First, the ArduPilot classification.** `h_acc` is
`fabsf(rand_float()) * 300`, refreshed at ~3 Hz, not conditioned on
`have_lock`. Is calling that `MODEL_GENERATED_HEALTH` rather than
`DIRECT_ORACLE` defensible, given the fault switch still ultimately turns it
on? My reasoning: the switch enables a *process*, and the field's value at any
instant is not recoverable from the switch — unlike PX4, where it is exactly
recoverable. If that distinction does not hold, the candidate is rejected and
MAER's structural arm fails again.

**Second, whether a single realisation is disqualifying.** The state-combination
evidence (184 degraded-gate-open messages) is a within-run structural fact and
does not obviously need repetition, but the scored campaign does. If the answer
is that a patched seed or varied initial conditions is mandatory before
preregistration, that is worth saying now.

The PX4 rejection needs no second opinion — the source is unambiguous, and it
corrects a claim I made one stage ago on evidence I had already collected and
misread.
