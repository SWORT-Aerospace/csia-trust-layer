# Mechanism A — fix-loss self-occlusion, replicated on the current stack

**The peer-review objection this answers:** *"The paper's headline
self-occlusion and threshold-crossing mechanisms were demonstrated only in the
old ArduCopter 3.3 campaign."*

Half of that objection is now answered. **Self-occlusion replicates on
ArduPilot 4.8 and on PX4 SIH.** The threshold-crossing half is **not** answered
here, and section 6 says exactly why rather than gesturing at it.

This is a small confirmatory replication — two arms per platform, one
intervention — not a new characterisation programme.

> **HISTORICAL, and deliberately not updated.** This records what the n = 1
> trials of 2026-08-25 measured, and the tables below are left exactly as they
> were. Two campaigns have since repeated it — ArduPilot 20+20 twice (A1, A2)
> and PX4 20+20 — and **the GPS trust rows below do not reproduce**: those
> trials ran a 0.5 s runtime stale timeout and the repeats ran 1.0 s, so the
> gate held twice as long and trust froze higher. Every other row here does
> reproduce. Correcting a frozen measurement to match a later one is the defect
> this programme exists to prevent, so the numbers stay and the reconciliation
> lives in
> `research/physical_validation/ARDUPILOT_REPEAT_RECONCILIATION.md`.

---

## 1. The claim under test

`docs/v1/V1_FINAL_RESEARCH_VERDICT.md` W-1:

> `SOI(gps_fault) = 1.0`. Every feature that would name a GPS fault is gated by
> a gate a GPS fault closes.

Question: **does fix loss still remove the evidence required to attribute
`gps_fault`?**

## 2. Design

| arm | intervention |
|---|---|
| **CONTROL** | fix preserved — the null control (RULE A) |
| **FAULT** | fix removed at t + 12.0 s, sent on the **rig's** link |

Four runs: ArduPilot CONTROL/FAULT, PX4 CONTROL/FAULT. 30 s shadow window,
751 ticks each, clean climb before the window in every arm.

**The interventions were read out of simulator source before use.**

| platform | parameter | why |
|---|---|---|
| ArduPilot | `SIM_GPS1_ENABLE = 0` (REAL32) | `SIM_GPS.cpp:42`, `AP_PARAM_FLAG_ENABLE`, runtime-settable |
| PX4 | `SIM_GPS_USED = 0` (**INT32**) | `SensorGpsSim.cpp:155-167`: `fix_type = 3` only when `_sim_gps_used >= 4`, else `0`. `SENS_EN_GPSSIM` is `reboot_required` and therefore useless in flight |

**RULE B — the parameter write is not the measurement.** The intermediate
quantity is `gnss.position` going MISSING with `NO_3D_FIX`, recorded per tick
in the S9 log. An arm that does not show it is a failed trial, not a result.

### 2.1 The first PX4 arm was a failed trial, and it looked like a finding

The first PX4 FAULT run showed **0 `NO_3D_FIX` ticks** and no escalation. Read
carelessly that says "PX4 does not exhibit the mechanism". It says nothing of
the kind: the intervention never reached the vehicle.

A parameter readback found PX4 echoing `SIM_GPS_USED =
1.401298464324817e-44` — the float32 reinterpretation of the **integer 10** —
and `SENS_EN_GPSSIM = 1.401298464324817e-45`, integer **1**. Both are INT32
parameters, and the injection had sent REAL32, so PX4 ignored the write.

That is the same parameter-type defect fixed in `_fly_px4` earlier the same
day, reintroduced in new code with the sign reversed. The injection now
carries its own readback and prints `CONFIRMED` / `NOT CONFIRMED`; the trial
above reports `readback=0.0 -> CONFIRMED`.

**Trial validity is asserted from the intermediate quantity, never from the
command having been sent.**

## 3. Trial validity

| platform | CONTROL clean (0 `NO_3D_FIX`) | FAULT effective | verdict |
|---|---|---|---|
| ArduPilot | yes, levels `[NORMAL]` only | 450 `NO_3D_FIX` ticks from t = 12.04 s | **VALID** |
| PX4 | yes, levels `[NORMAL]` only | 448 `NO_3D_FIX` ticks from t = 12.12 s | **VALID** |

## 4. Result — the mechanism replicates on both

Snapshots at t = inject − 2 s (**pre**), + 2 s (**post**), + 10 s (**late**).

### ArduPilot 4.8

| quantity | pre | post | late |
|---|---|---|---|
| `gnss.position` usable | True | **False** | False |
| **GPS gate weight sum** | **3.0** | **0.0** | **0.0** |
| GPS trust | 0.9213 | **0.9300** | 0.9300 |
| P(`gps_fault`) | 0.0001 | 0.0131 | 0.0227 |
| rank(`gps_fault`) | 2 | 2 | 2 |
| P(`nominal`) | 0.9997 | 0.9867 | **0.9771** |
| rank(`nominal`) | 1 | 1 | **1** |
| recommendation | NORMAL | **CAUTION** | CAUTION |

### PX4 SIH

| quantity | pre | post | late |
|---|---|---|---|
| `gnss.position` usable | True | **False** | False |
| **GPS gate weight sum** | **1.0** | **0.0** | **0.0** |
| GPS trust | 0.9856 | **0.9875** | 0.9875 |
| P(`gps_fault`) | 0.0001 | 0.0128 | 0.0213 |
| rank(`gps_fault`) | 4 | 3 | 4 |
| P(`nominal`) | 0.9769 | 0.9640 | **0.9173** |
| rank(`nominal`) | 1 | 1 | **1** |
| recommendation | NORMAL | **CAUTION** | **CRITICAL** |

### What these numbers say

1. **The gate weight sum goes to exactly 0.0 on both platforms.** Every gate
   that could carry GPS evidence closes when the fix is lost. That is
   `SOI(gps_fault) = 1.0`, measured.
2. **GPS trust does not fall — it rises slightly on both.** The node cannot be
   discredited, because the evidence that would discredit it is gone. This is
   the self-occlusion, and it is the counter-intuitive half of the claim.
3. **`gps_fault` never reaches rank 1.** `nominal` stays rank 1 throughout, at
   P = 0.92–0.98, on both platforms.
4. **The assurance layer escalates anyway**, on the freshness path
   ("GPS data invalid"), not on attribution.

**Answer: yes.** Fix loss still removes the evidence required to attribute
`gps_fault`, on both current autopilots.

## 5. A second-order PX4 finding

PX4 escalates further than ArduPilot, and the log says why:

```
t=13.6s  NORMAL   -> CAUTION    GPS data invalid (diagnosis nominal p=0.97)
t=18.7s  CAUTION  -> CRITICAL   attitude confidence degraded (best 0.74;
                                diagnosis nominal p=0.91)
t=23.2s  CRITICAL -> EMERGENCY  attitude reference integrity lost
                                (imu0=0.66, imu1=0.80; diagnosis nominal p=0.88)
```

The failsafe computes `att` as the max over IMUs that are **fresh**
(`failsafe.py:106`). PX4 SIH publishes no second IMU, so that maximum is
`imu0` alone, and a GPS fault that degrades the estimator propagates
unchecked into an attitude EMERGENCY. On ArduPilot, `imu1` is present and
holds the maximum up.

**A GPS fault reaching an attitude EMERGENCY through a missing redundant
IMU is a platform-coupling result**, and it is the sharpest argument yet for
the per-platform contract rows: PX4's absent `imu1` is not a cosmetic gap.

At every step of that cascade the diagnosis reports `nominal` — p = 0.97,
0.91, 0.88. **The system reaches EMERGENCY while its own attribution layer
says nothing is wrong.** Assurance output ≠ diagnostic attribution, now
observed under a real injected fault on a current stack, matching what was
observed with no fault at all in `PX4_CLEAN_ESCALATION_DIAGNOSIS.md`.

## 6. What is NOT replicated here

**The history / threshold-crossing mechanism (W-4) is not tested by these
runs, and cannot be.** W-4's closed form (`N* = 93.31` ticks, crossing at tick
94) describes how long banked evidence delays a trust node crossing a
threshold. These runs cannot exercise it **because the occlusion prevents the
crossing from ever happening**: GPS trust does not move, so there is no
crossing whose timing could be compared against the recursion.

Testing W-4 needs a fault that leaves its own evidence intact — one where
`S₀, T₀, ρᵏ, eₖ, Tₖ` can all be observed while the node's trust actually
falls. That is a different injection and a separate preregistered trial. It is
named here so that no reader mistakes this document for having tested it.

| mechanism | ArduCopter 3.3 | ArduPilot 4.8 | PX4 SIH |
|---|---|---|---|
| Fix-loss self-occlusion | YES | **YES** | **YES** |
| Fix-preserved control | NO | **NO** | **NO** |
| History threshold (W-4) | YES | **not tested** | **not tested** |

## 7. Reproducing

```bash
python tools/deploy/shadow_sitl_check.py --platform ardupilot --fly --seconds 30 \
    --out research/v1_1/results/mechanism_a/ap_CONTROL.json
python tools/deploy/shadow_sitl_check.py --platform ardupilot --fly --seconds 30 \
    --inject gps_fix_loss --inject-at 12 \
    --out research/v1_1/results/mechanism_a/ap_FAULT.json
python tools/simulation/mechanism_a_report.py --platform ardupilot \
    --control research/v1_1/results/mechanism_a/ap_CONTROL.json \
    --fault   research/v1_1/results/mechanism_a/ap_FAULT.json
```

`mechanism_a_report.py` exits non-zero when a trial is invalid — the FAULT arm
failing to produce the intermediate quantity, or the CONTROL arm producing it.
