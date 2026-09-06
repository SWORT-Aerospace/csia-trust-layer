# ArduPilot Mechanism A — reconciliation of the original n=1 against the repeats

**Question this file answers:** for every headline quantity the ArduPilot
Mechanism A result rests on, does the original single trial agree with the two
repeated campaigns, and if not, why not?

**Three sources, all committed:**

| | what it is | n | trust captured |
|---|---|---|---|
| **ORIGINAL** | `research/v1_1/results/mechanism_a_ardupilot.json`, flown 2026-08-25 | 1 + 1 | in the flight log, **not** in the artifact |
| **A1** | `research/physical_validation/results/mechanism_a_repeat_ardupilot.json` | 20 + 20 | **NOT_CAPTURED** — `--trust-trace` was not passed (FL-014) |
| **A2** | `research/physical_validation/results/mechanism_a_a2_trust_ardupilot.json` | 20 + 20 | captured, 40/40, 753 rows each |

**The headline conclusion of this document is a discrepancy, and it has a
measured root cause.** The original trial and both repeat campaigns did **not
run the same runtime watchdog**. Section 4 identifies the exact constant,
section 5 says what it does and does not cost.

---

## 1. Reconciliation table

`✓` = the original value falls inside the repeated range.
`✗` = it does not. `—` = the campaign does not measure this quantity.

| # | headline quantity | ORIGINAL | A1 support? | A2 support? | consistent? |
|---|---|---|---|---|---|
| 1 | `first_t`, `gnss.position` MISSING with `NO_3D_FIX` | **12.043901 s** | ✓ 12.0399–12.0827, median 12.0432 | ✓ same logs | **YES** |
| 2 | `gnss.position` MISSING tick count | **450** | ✓ 449–450, median 450 | ✓ | **YES** |
| 3 | `gps_gate_weight_sum`, FAULT arm | **3.0 → 0.0** | ✓ 20/20 | ✓ 20/20 | **YES** |
| 4 | `gps_gate_weight_sum`, CONTROL arm | **3.0 → 3.0** | ✓ 20/20 | ✓ 20/20 | **YES** |
| 5 | nominal hypothesis rank, pre and post | **1 → 1** | ✓ 20/20 | ✓ 20/20 | **YES** |
| 6 | `gps_fault` rank, pre and post | **2 → 2** | ✓ 20/20 | ✓ 20/20 | **YES** |
| 7 | failsafe level, FAULT arm | **NORMAL → CAUTION** | ✓ | ✓ 20/20 | **YES** |
| 8 | failsafe level, CONTROL arm | **NORMAL → NORMAL** | ✓ | ✓ 20/20 | **YES** |
| 9 | **gate-collapse latency** (channel loss → gate zero) | **0.4788 s** | ✗ 0.9930–1.0066 | ✗ 1.04–1.08 from onset | **NO — §4** |
| 10 | **GPS trust across the fault, FAULT arm** | **+0.008656** | — NOT_CAPTURED | ✗ +0.006996 … +0.007146 | **NO — §4** |
| 11 | **GPS trust across the fault, CONTROL arm** | **+0.014020** | — NOT_CAPTURED | ~ +0.020572 … +0.020804 | **§3** |
| 12 | direction of the trust change under fault | **rises** | — | ✓ **20/20 rise** | **YES** |

Rows 1–8 and 12 reproduce. Rows 9–11 do not, and rows 9 and 10 are the same
fact seen twice.

## 2. What A1 could and could not settle

A1 was run **without `--trust-trace`** and therefore has no trust series at
all. Its trust fields read `NOT_CAPTURED`, with the reason, in every one of its
40 trial records.

`NOT_CAPTURED` is **not** `FAIL`, **not** `ZERO`, **not** `UNCHANGED` and
**not** `INCONCLUSIVE`. It means the instrument was not switched on. A1 is
sealed at `campaigns/physical_validation/mechanism_a_repeat_ap/_CAMPAIGN_A1.yaml`
and was not re-run into, amended or regenerated; A2 is a separate campaign with
its own preregistration.

A1 does settle rows 1–8: those are read from the flight log, which A1 captured
in full.

## 3. The control arm was never compared, and it moves more than the fault arm

**A2, at the trial level, both arms n = 20:**

| | trust PRE | trust POST | Δ median | Δ range |
|---|---|---|---|---|
| FAULT | 0.924816 | 0.931823 | **+0.007007** | +0.006996 … +0.007145 |
| CONTROL | 0.924813 | 0.945407 | **+0.020594** | +0.020572 … +0.020804 |

The ranges are **completely disjoint**: the largest fault delta (+0.007145) is
below the smallest control delta (+0.020572). The control arm rises about
**three times more**.

**This was already in the original artifact and was not reported.** The frozen
`mechanism_a_ardupilot.json` carries four snapshots per arm, including the
control arm's:

| original, single-tick snapshots | pre (t≈10.00) | post (t≈14.00) | late (t≈22.00) |
|---|---|---|---|
| FAULT | 0.9212973 | 0.9299535 | 0.9299535 |
| CONTROL | 0.9213146 | 0.9353348 | **0.9595470** |

The control arm's post delta (+0.014020) already exceeded the fault arm's
(+0.008656) by 62%, and by the late snapshot by 4.4×. The published headline
`0.9213 → 0.9300` is **the fault arm alone**, and the arm-to-arm comparison —
the only comparison a control exists to license — was not made.

**Consequence for the claim.** "Trust rises across a gate collapse" is *true*
(A2: 20/20) and *misleading stated alone*. What is measured is:

> Trust rises in **both** arms as evidence accumulates over the flight. Under
> the fault it rises **less**, because the gate closes and the node stops
> receiving evidence, freezing the coefficient at whatever it had reached. The
> fault **suppresses** an ongoing rise; it does not cause one.

The freeze is visible per tick: in every A2 fault trial the gps trust is
constant from the gate collapse to the end of the flight, and the POST and LATE
window medians are bit-identical.

**What survives.** The DEA profile (§`DEA_PROFILE.md`) uses this result to
justify **not** standardising "gate closure shall lower trust". That
justification survives intact and is in fact strengthened: trust does not fall
under gate closure in any of the 20 repeats. What does **not** survive is any
phrasing implying the fault *drove* trust up.

## 4. Root cause of rows 9 and 10: the runtime watchdog differs

This was not left as "the numbers differ". It is measured end to end.

### 4.1 Where the two runs agree

Under the original's own single-tick reduction, applied to the A2 traces:

| | original | A2 range (n=20) | inside? |
|---|---|---|---|
| FAULT trust at t ≈ 12.0036 (just before the effect) | 0.9282432 | 0.9282022 … 0.9282913 | **YES** |
| CONTROL Δ pre→post | +0.0140202 | +0.0139690 … +0.0142469 | **YES** |
| CONTROL Δ pre→late | +0.0382324 | +0.0381646 … +0.0385415 | **YES** |
| FAULT Δ pre→post | +0.0086563 | +0.0104528 … +0.0106045 | **NO** |

Pre-fault behaviour reproduces. The **whole control arm** reproduces. The
divergence is confined to the FAULT arm, after onset.

### 4.2 The divergence is one second wide

Per-tick, from the committed logs:

| | channel MISSING at | gate reaches 0.0 at | **dwell** |
|---|---|---|---|
| ORIGINAL FAULT | 12.043819 s | 12.522596 s | **0.478777 s** |
| A2 FAULT (n=20) | ~12.048 s | ~13.042 s | **0.999657 s** (0.993018 … 1.006609) |

The channel dies at the same moment in both. The **gate** then holds for
**0.48 s** in the original and **1.00 s** in every repeat. Trust accrues while
the gate is open and freezes when it shuts, so the repeats accrue for twice as
long and freeze higher — 0.931820 against 0.929954.

That single 0.52 s difference accounts for **all** of row 10.

### 4.3 The constant

| | `gps` stale timeout | source |
|---|---|---|
| frozen core default | **0.5 s** | `csia/runtime/online.py:STALE_TIMEOUT_S["gps"]` |
| derived runtime value | **1.0 s** | `csia/v1_1/staleness.py:build_runtime_stale_timeouts("ardupilot")["gps"]` |

`= MAX_AGE_MARGIN (5.0) / gnss declared rate (5.0 Hz) = 1.0 s`, over the gps
node's required channels `gnss.position` and `gnss.velocity`.

The measured dwells match their respective constants to within one tick period
(0.04 s): 0.4788 against 0.5, and 0.9997 against 1.0.

### 4.4 Why the two runs had different constants

* the ORIGINAL trial ran at CSIA commit `9241766`;
* A1 and A2 ran at `ceeaf4a`;
* **the frozen core is byte-identical between them** — `git diff` over all six
  `FROZEN_PATHS` is empty. The core was not touched;
* what changed is `csia/deploy/shadow.py`, which at `ceeaf4a` passes
  `stale_timeout_s=build_runtime_stale_timeouts(platform)` into the core.
  That is **Phase 4.5 Gate B**, a deliberate, documented and separately
  validated change: the frozen table bakes in a producer rate, the adapter
  derives `MaxAge` from the channel contract, six of eight nodes disagreed, and
  a `baro` stream at its declared rate false-staled 2.8–3.7% of ticks. The core
  already accepted the argument; the driver started supplying it.

**So the discrepancy is not a defect in either run, and neither is wrong.** It
is that **the "repeat" repeated a different deployment configuration from the
original**, and neither the A1 nor the A2 preregistration named the watchdog as
a pinned environment field. That omission is the finding (FL-017).

### 4.5 The dwell is a deterministic function of the watchdog, checked four ways

§4.3 says the dwells "match their respective constants to within one tick".
They match something sharper than that, and it is worth stating because it
turns §4 from *the watchdog differs* into *the dwell is predictable from the
watchdog*.

The watchdog measures from the last time the `gps` node was **emitted**, not
from the tick that first reports the channel MISSING. Those differ by whatever
age the channel had already accumulated. So:

> **dwell ≈ watchdog − (channel age at the last usable tick)**

| run | watchdog | age at last usable tick | predicted | **measured** | residual |
|---|---|---|---|---|---|
| ArduPilot ORIGINAL | 0.5 | 0.012817 | 0.487183 | **0.478777** | −0.008406 |
| PX4 ORIGINAL | 0.5 | 0.112200 | 0.387800 | **0.400208** | +0.012408 |
| ArduPilot A2, n=20 medians | 1.0 | 0.006286 | 0.993714 | **0.999657** | +0.005943 |
| PX4 validation pair | 1.0 | 0.092852 | 0.907148 | **0.919577** | +0.012429 |

Every residual is inside one tick period (0.04 s at 25 Hz), which is the
resolution the dwell can be observed at. The relation holds across **two
platforms and both watchdog values**, so it is not fitted to the case it
explains.

**It also explains why the two ORIGINAL trials have different dwells** (0.4788
against 0.4002) under the *same* 0.5 s watchdog: PX4's `gnss.position` arrives
more slowly on the passive link, so the channel is older when it is flagged.
That is the same passive-link starvation §4 of the PX4 preregistration retains,
showing up in a second quantity.

### 4.6 One further gap in the original's record

The original trial's flight-log header records `autopilot_version:
"ardupilot"` — a platform name, not a build. **The original n=1 trial cannot be
shown from its own record to have run the pinned ArduPilot build**
`01a504b472259602e13df4cf07df7c0cdbb35993`; A1 and A2 record
`ArduCopter V4.8.0-dev@01a504b`. This is not offered as the cause of anything —
§4.3 and §4.5 account for the discrepancy quantitatively — but it is an
unrecoverable field and is recorded rather than left to be rediscovered.
**The original PX4 trial has the identical gap**: its log records
`autopilot_version: "px4"`, while the repeat resolves
`PX4-Autopilot v1.18.0-beta1-395-g547e2caa98@547e2ca`.

## 5. Claim impact, per row

| row | claim as it stands | impact |
|---|---|---|
| 1–8, 12 | timing, gate collapse, ranks, failsafe, direction of trust | **UPGRADED from n=1 to n=1+20+20.** No change of wording needed |
| 9 | gate-collapse latency | **no claim was ever made from it.** It is now a measured quantity with a known dependence on the deployment watchdog, and must be quoted with that configuration |
| 10 | "0.9213 → 0.9300" | **DO NOT QUOTE AS A REPEATABLE VALUE.** It is a faithful record of one trial under a superseded watchdog. The repeated value under the current runtime is 0.924816 → 0.931823 (n=20) |
| 11 | — | a control-arm trust claim was never made and still cannot be made from the original; A2 licenses one |
| 3 (§3) | "trust rises across a gate collapse" | **must be stated with the control arm.** It rises in both, and less under fault |

**The frozen artifacts are not edited.** `mechanism_a_ardupilot.json` still
reads 0.9213 → 0.9300, because that is what that trial measured. Correcting a
frozen measurement to match a later one is exactly the failure this programme
exists to prevent. The reconciliation lives here.

## 6. What is now re-derivable that was not

`extract_mechanism_a.py`, the committed extractor, run against the **original
trial's own flight log** (`logs/shadow-sitl-ardupilot/20260825T005244Z-8c32ffe5.part000.jsonl`):

| quantity | artifact | re-derived | agrees? |
|---|---|---|---|
| `first_t` | 12.043901 | 12.043819 | **yes**, to a stated t₀ convention |
| MISSING tick count | 450 | 450 | exact |
| `gps_gate_weight_sum` | 3.0 → 0.0 | 3.0 → 0.0 | exact |
| ranks before/after | 1 / 2 | 1 / 2 | exact |

The 82 µs on `first_t` is not noise: the artifact measured from CSIA process
start, the extractor from the first tick, and the first tick is at
`t_mono = 8.2e-05`. `12.043901 − 0.000082 = 12.043819` exactly.

This closes the `SCALAR_DERIVATION_GRAPH.yaml` open item recorded as
"`mechanism_a_first_t_ardupilot` has no oracle against the ORIGINAL trial's own
log". It has one now, in `tests/test_ardupilot_repeat_reconciliation.py`.

## 7. What this reconciliation does **not** establish

* **Still E1.** Every number here is simulation. Nothing about hardware, real
  sensors, or flight.
* **No pooling.** ORIGINAL, A1 and A2 are reported separately throughout. The
  three were run under different instrumentation and, per §4, different
  watchdog configurations; they are not exchangeable and are not averaged.
* **No p-values, no confidence intervals.** These are runs of a deterministic
  simulator differing in seed and timing jitter. An interval over them would
  describe the simulator's jitter while reading as a statement about vehicles.
* **No prevalence claim.** Nothing here says how often GNSS fix loss occurs.
* **No timing claim.** Tick latency was recorded and not adjudicated in either
  campaign; the host is shared.
* **Nothing about PX4.** The PX4 repeat is preregistered and `NOT_RUN`.
* **The 0.52 s dwell difference is explained, not re-run.** The original trial
  has not been repeated under its own watchdog, and doing so would be a third
  campaign with its own preregistration, not a fix to this one.
