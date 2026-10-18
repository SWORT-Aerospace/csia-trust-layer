# PX4 Mechanism A — reconciliation of the original n=1 against Campaign P1

**Companion to** `ARDUPILOT_REPEAT_RECONCILIATION.md`, same question, second
platform: for every headline quantity the PX4 Mechanism A result rests on, does
the original single trial agree with the repeat?

**The two platforms are reconciled separately and are never pooled.** They
differ structurally — PX4 SIH publishes no `SCALED_IMU2`, so `imu1` does not
exist at all — and averaging over that would describe neither.

| | what it is | n | trust captured |
|---|---|---|---|
| **ORIGINAL** | `research/v1_1/results/mechanism_a_px4.json`, flown 2026-08-25 | 1 + 1 | in the flight log, not in the artifact |
| **P1** | `research/physical_validation/results/mechanism_a_p1_trust_px4.json` | 20 + 20 | captured, 40/40, 753 rows each |

`planned 40 | attempted 40 | valid 40 | invalid 0 | not_attempted 0`

---

## 1. Reconciliation table

| # | headline quantity | ORIGINAL | P1 support? | consistent? |
|---|---|---|---|---|
| 1 | `first_t`, `gnss.position` MISSING | **12.121585 s** | ✓ inside 12.0005–12.1291, median 12.1219 | **YES** |
| 2 | MISSING tick count | **448** | ✓ 444–451, median 448 | **YES** |
| 3 | `gps_gate_weight_sum`, FAULT | **1.0 → 0.0** | ✓ 20/20 | **YES** |
| 4 | `gps_gate_weight_sum`, CONTROL | **1.0 → 1.0** | ✓ 20/20 | **YES** |
| 5 | **the §4 qualification: gate is 1.0, not 3.0** | **1.0** | ✓ 20/20 both arms | **YES** |
| 6 | nominal hypothesis rank | **1 → 1** | ✓ 40/40 | **YES** |
| 7 | `gps_fault` rank, pre | **4** | ✓ 4 in 18, 5 in 2 | **YES** |
| 8 | failsafe, FAULT arm | escalates past CAUTION | ✓ CRITICAL 19, CAUTION 1 | **YES** |
| 9 | failsafe, CONTROL arm | **NORMAL only** | ✓ 20/20 NORMAL | **YES** |
| 10 | **PRE-fault GPS trust** | **0.985624** | ✗ 0.949 – 0.953 | **NO — §3** |
| 11 | **trust delta across the fault** | **+0.001884** | ✗ +0.002269 … +0.003999 | **NO — §3** |
| 12 | direction of the trust change under fault | **rises** | ✓ **20/20 rise** | **YES** |

Ten reproduce. Two do not, and they are the same fact seen twice.

## 2. Both ArduPilot findings replicate here, independently

### FL-016 — the control arm rises more

| P1, n = 20 per arm | trust PRE | trust POST | Δ median | Δ range |
|---|---|---|---|---|
| FAULT | 0.952172 | 0.955534 | **+0.003513** | +0.002269 … +0.003999 |
| CONTROL | 0.952244 | 0.961753 | **+0.009499** | +0.009328 … +0.010729 |

Ranges **disjoint**: the largest fault delta (+0.003999) is below the smallest
control delta (+0.009328). The control arm rises about **2.7×** more.

**It was already in the frozen PX4 artifact too, and was never compared** —
exactly as on ArduPilot:

| original PX4, single-tick snapshots | pre | post | late |
|---|---|---|---|
| FAULT | 0.9856243 | 0.9875080 | 0.9875080 |
| CONTROL | 0.9856288 | 0.9889611 | **0.9927804** |

Control +0.003332 against fault +0.001884 at post, and +0.007152 against
+0.001884 by late — **3.8×**. Two platforms, two frozen artifacts, the same
un-made comparison.

### FL-017 — the original delta is outside the repeated range

+0.001884 against [+0.002269, +0.003999]. Same shape as ArduPilot's, same root
cause (§3), and reached from an independent campaign.

## 3. Root cause: the watchdog, established by a controlled replay

PX4 has the ArduPilot situation and **one more symptom**: its **PRE-fault**
trust does not reproduce either (row 10), where ArduPilot's did (0.924639
against 0.924816). Two campaigns disagreeing on one platform and agreeing on
the other is a fact; attributing it requires an experiment.

### 3.1 The experiment

`tools/csia_experiment/watchdog_replay.py` drives the **same committed flight
log** through the **same frozen core** twice. Log, tick rate, field mode and
core are identical. The only difference is the table passed as
`stale_timeout_s`:

| | `gps` | source |
|---|---|---|
| frozen | **0.5 s** | `csia/runtime/online.py:STALE_TIMEOUT_S` |
| derived | **1.0 s** | `csia/v1_1/staleness.py:build_runtime_stale_timeouts("px4")` |

### 3.2 The result

| log replayed | under frozen | under derived |
|---|---|---|
| the **original** n=1 FAULT log | **0.986420** | **0.952526** |
| a **P1 repeat** FAULT log | **0.985924** | **0.949056** |
| *measured, for comparison* | *artifact: **0.985624*** | *P1: **0.952172*** |

**Both logs reproduce both values.** The original's trust is recovered from a
repeat's log by using the old watchdog, and the repeat's trust is recovered
from the original's log by using the new one, each to within ~0.003. The
watchdog change accounts for the PX4 pre-fault difference; nothing else needs
to be invoked, and nothing else was.

### 3.3 What this replay does NOT establish, stated because it is load-bearing

**It is not a valid instrument on ArduPilot.** On the original ArduPilot log it
gives 0.979440 (frozen) and 0.941275 (derived) against a measured 0.924639 and
0.924816 — wrong by 0.055 and 0.017, and wrong in a direction the flights did
not show. The reconstruction detects a core hand-off by a *changed* channel
value, so two identical consecutive readings look like no new reading;
ArduPilot's higher channel rates make that under-count bias much larger. The
bias is documented where the reconstruction lives
(`tools/deploy/profile_core_from_log.py`).

**So: why ArduPilot's PRE-fault trust was stable across the same watchdog
change is UNRESOLVED.** The obvious guess — that ArduPilot's channels are
usable ~100% of the time so a longer timeout changes nothing, while PX4's baro
sits at ~50% and its battery and vibration at ~24%, so a longer timeout keeps
starved nodes alive — is consistent with everything measured and is **not
established here**. It is a hypothesis, recorded as one.

### 3.4 The link state itself did reproduce

Worth stating, because it rules out the other obvious explanation. Over the PRE
window, the original and a P1 repeat show the same channels usable at the same
shares (`baro.altitude` 0.50 vs 0.48, `battery.voltage` 0.24 vs 0.24,
`vibration.rms` 0.24 vs 0.24, GNSS/IMU/mag 1.00 in both), the same live
relation count (2), and the same gate set with the same weights. **The passive
link is not what differs between the two campaigns.**

## 4. Heterogeneity, recorded rather than smoothed

The gate collapse is 20/20 and 0/20 with no exceptions. Two quantities are not
uniform, and both are reported:

* **`failsafe_post` on the FAULT arm: CRITICAL in 19 trials, CAUTION in 1.**
  The original escalated to EMERGENCY within its 30 s. The escalation depth
  varies; the escalation itself does not.
* **`gps_fault_rank_pre`: 4 in 18 trials, 5 in 2.** Rank 4–5 pre-fault against
  ArduPilot's stable 2, which is the narrower live-relation pool, not a
  different behaviour.
* `nominal_weight_pre` reaches as low as 0.560 in some trials against a median
  0.949. The pre-fault posterior is less settled on PX4 than on ArduPilot.

## 5. Claim impact

| row | impact |
|---|---|
| 1–9, 12 | **UPGRADED from n=1 to n=1+20+20 on PX4.** The E1 asymmetry that held the ArduPilot results back is gone: both platforms now have a repeated campaign |
| 5 | the §4 qualification is now measured 40/40 rather than argued from one trial. **PX4's demonstration is narrower than ArduPilot's and that is a property of the passive link, not of PX4** |
| 10, 11 | **DO NOT QUOTE `0.9856 → 0.9875` AS A REPEATABLE VALUE.** It is a faithful record of one trial under a superseded 0.5 s watchdog. The repeated values are 0.952172 → 0.955534 (n=20) |
| §2 | "trust rises across a gate collapse" must be stated **with the control arm** on this platform too |

**No frozen artifact is edited.** `mechanism_a_px4.json` still reads 0.9856 →
0.9875, because that is what that trial measured.

## 6. What this does not establish

* **Still E1.** Simulation. Nothing about hardware, real sensors or flight.
* **No pooling with ArduPilot**, and no pooling of ORIGINAL with P1.
* **No p-values, no confidence intervals.** Deterministic simulator, seed and
  timing jitter, not draws from a population.
* **No prevalence claim.**
* **No timing claim.** PX4 SIH is real-time lockstep on a shared host; latency
  was recorded and deliberately not adjudicated. Its latency figures are less
  comparable to ArduPilot's than the shared host alone would make them.
* **Nothing about a driven-link PX4 configuration.** That is a separate
  experiment needing its own preregistration, and its result would not be
  comparable to this one.
* **§3.3.** Why ArduPilot's pre-fault trust was stable is unresolved.
