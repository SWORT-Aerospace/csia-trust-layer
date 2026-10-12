# Mechanism A, repeated on the current stack — preregistration

**Committed BEFORE any trial of this campaign is executed.** `git log` on this
file against the results commit is the audit trail. The grid, the endpoints,
the tolerances, the classification rule and the stopping rule are fixed here so
that a result cannot be rescued afterwards by widening any of them.

**Nothing in the frozen v1 core is modified by this work.** `FROZEN_PATHS` —
`csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`,
`csia/runtime/failsafe.py`, `csia/scenarios.py`, `csia/profiles.py` — are read,
run and replayed, never edited.

---

## 1. What is being repeated, and what is NOT

The existing Mechanism A result is **n = 1 fault trial plus one matched
fix-preserving control, per platform** (`research/v1_1/results/
mechanism_a_ardupilot.json`, `mechanism_a_px4.json`). One realisation is not a
distribution, and every latency and tick count derived from it is a single
observation.

This campaign runs **20 fault trials and 20 matched controls per platform** so
that the same quantities acquire a spread.

**It does not extend the evidence tier.** Both the original and this repeat are
**E1** — current-stack SITL/SIH. No claim about physical hardware, real
sensors, or flight becomes available because a simulation was repeated.

## 2. THE BUILD, AND A CORRECTION MADE BEFORE THIS FILE WAS FROZEN

**The original build IS identified, and this campaign runs on it.**

An earlier draft of this section asserted the opposite — that the build could
not be recovered — on the strength of the Mechanism A artifacts alone. Those
artifacts do record only `platform: "ardupilot"`; `mechanism_a_ardupilot.json`
and `research/v1_1/results/mechanism_a/ap_FAULT.json` carry no firmware field.
**The identification lives in sibling artifacts from the same campaign era**,
and it is unambiguous and repeated:

| artifact | records |
|---|---|
| `research/phase2/results/modern_replication.json` | `git_head: 01a504b`, `firmware_string: ArduCopter V4.8.0-dev` |
| `research/dual_admissibility_confirmatory/results/STAGE2_1_KILL_TEST.json` | `"simulator": "ArduPilot SITL @ 01a504b"` |
| `.../results/heldout_raw/CAPTURE_INDEX.json` | `"simulator": "ArduCopter V4.8.0-dev@01a504b"`, every capture |
| `.../HIL_CRITERION_0_PLAN.md` | *"the same commit the repository is verified against: `01a504b`"* |

The commit resolves and is fetchable:
`01a504b472259602e13df4cf07df7c0cdbb35993`, authored **2026-08-23**, two days
before the Mechanism A flight ids (`20260825T005244Z`, `20260825T005343Z`).

The correction is recorded as FL-013 in `FAILURE_LEDGER.yaml`. It is noted here
rather than quietly fixed because the earlier claim would have weakened this
campaign for no reason: a repeat on a *different* build cannot separate a build
difference from run-to-run variation, and this one does not have that problem.

**This campaign therefore IS a repeat of the original build**, and a difference
in its numbers is attributable to run-to-run variation rather than confounded
with a build change.

### 2.1 What is pinned

| item | value | how it was fixed |
|---|---|---|
| ArduPilot commit | `01a504b472259602e13df4cf07df7c0cdbb35993` (authored 2026-08-23) | the commit the existing modern-stack artifacts record; fetched by deepening a shallow clone, checked out and rebuilt from source |
| firmware string | `ArduCopter V4.8.0-dev` | reported by the built binary over MAVLink `AUTOPILOT_VERSION`, matching the string in the existing artifacts |
| injection parameter | `SIM_GPS1_GLTCH_X` | the per-instance `GPSParms` entry `CURRENT_STACK_REPLICATION.md` cites at `SIM_GPS.cpp`; `research/phase2/modern_replication.py` confirms `SIM_GPS1_ENABLE`, `SIM_GPS1_GLTCH_X` and `SIM_GPS1_NUMSATS` are all present and the pre-4.x names are all absent |
| CSIA frozen core | `csia-v1.0-research-final` | tag is LOCAL ONLY (USER_ACTION_REQUIRED.md §A); the hash-file check is authoritative here |
| tick rate | 25.0 Hz | `configs/vehicle/*.yaml` `csia.tick_hz`; a science-surface value under `csia.deployment/2` |
| noise-profile label | `FIELD_DERIVED_NOISE` | a provenance label only — it selects nothing at runtime (`shadow.py:285`) |

Every trial manifest records the pinned commit through
`tools/csia_experiment/manifest.py:provenance()`. A trial whose manifest does
not carry it is **INVALID_SCENARIO**, not a result.

## 3. Arms

| arm | n per platform | injection | what it is for |
|---|---|---|---|
| `FAULT` | 20 | GNSS fix loss | the mechanism under test |
| `CONTROL` | 20 | fix **preserved**, everything else identical | RULE A. If this arm shows the mechanism, the instrument is broken and **no arm may be read** |

Platforms: **ArduPilot** (the pinned commit above) and **PX4 SIH**. Each
platform is analysed separately and the two are never pooled: PX4 SIH publishes
no `SCALED_IMU2`, so `imu1` and the dual-IMU cross-check cannot be evaluated
there at all, and pooling would average over a structural difference.

## 4. Validity — every trial is adjudicated, none is assumed

Each trial is adjudicated by `tools/csia_experiment/validity.py` into exactly
one of eight states before any metric is computed. **Only `VALID` trials
contribute to any number.**

The six-stage evidence chain of `csia/simulation/contract.py` must close:
`COMMAND_ISSUED` → `SIMULATOR_STATE_CHANGED` → `SENSOR_OUTPUT_CHANGED` →
`AUTOPILOT_RECEIVED_CHANGE` → `CSIA_RECEIVED_CHANGE` →
`GROUND_TRUTH_MATCHES_EXPECTATION`. A stage is satisfied by **a measured
number**, not by an assertion.

**COMMAND ISSUED ≠ FAULT INJECTED.** A trial where the parameter write returned
success and the sensor stream never moved is `INVALID_SCENARIO` — **not** a
detector miss. Scoring it as a miss manufactures evidence that a detector
failed to see a fault that may never have existed.

## 5. Preregistered quantities

Recorded per valid trial, and **nothing else may be reported as a result**:

1. `gps_gate_weight_sum` before and after onset;
2. the trust coefficient of `gps` before and after onset;
3. the rank of the nominal hypothesis, and of `gps_fault`, at onset and after;
4. RULE-B tick count — ticks over which the mechanism intermediate is observed;
5. `first_t` — the first tick at which the gate weight reaches zero;
6. the support/eligibility state, **if and only if** the run records one.

### 5.1 Item 6 exists because of a specific gap

The support state is **NOT RECORDED** in the existing Mechanism A artifacts —
grepping them for `support` and `eligib` returns nothing. The original campaign
therefore cannot say what the support engine concluded, and no writer may state
one. This campaign records it if the runtime emits it, and reports
`support_state: NOT_RECORDED` if it does not. **It will not be inferred.**

## 6. Analysis, fixed in advance

* **Per platform, per arm:** n, median, min, max, and the full ordered list of
  each quantity in §5. Ordered lists, not summaries alone — with n = 20 the
  reader should see the sample.
* **No p-values, no confidence intervals, no significance tests.** These are 20
  runs of a deterministic simulator differing only in seed and timing jitter.
  They are not draws from a population, and a confidence interval computed over
  them would describe the simulator's jitter while reading as a statement about
  vehicles.
* **The comparison of interest is qualitative and preregistered here:** does
  the gate-weight collapse occur in every valid FAULT trial and in no valid
  CONTROL trial? Any other pattern is reported as it is found.
* **`trust rises across the fault`** was observed on both platforms in the n = 1
  result (ArduPilot 0.9213 → 0.9300; PX4 0.9856 → 0.9875). This campaign
  reports whether that holds. **It is not required to hold**, and a repeat that
  contradicts it is a result, not a failure.

## 7. Stopping rule

The campaign stops at 20 + 20 per platform. It does not stop early because a
pattern has appeared, and it does not continue past 20 because one has not.

If trials are invalid, **they are recorded and the campaign does not backfill
to reach 20 valid**. The reported denominator is 20 planned per arm, and
`planned = valid + invalid + not_attempted` must balance
(`tools/csia_experiment/validity.py:reconcile`, which raises rather than
printing an open sum).

## 8. Prespecified failure conditions

Each of these is a **result**, recorded in `FAILURE_LEDGER.yaml` and reported:

| condition | verdict |
|---|---|
| any valid CONTROL trial shows the gate collapse | `INSTRUMENT_DEAD`. The whole campaign is unreadable, both arms, both platforms |
| fewer than 10 valid FAULT trials on a platform | the platform is reported as `UNDERPOWERED`; no distribution is quoted from it |
| the gate collapse appears in some FAULT trials and not others | reported as observed, with the count. **This would weaken the n = 1 claim and the paper claim changes, not the experiment** |
| the pinned build cannot be rebuilt | `PREREG_UNRUNNABLE`, recorded with the build error |

## 9. What this campaign CANNOT establish

Written here, before the data, so it cannot be softened afterwards:

* **Nothing about physical hardware.** E1 in, E1 out.
* **Nothing about PX4** unless the PX4 half runs. ArduPilot and PX4 are
  reported separately and never pooled (§3), so an ArduPilot-only campaign is
  an ArduPilot result and the PX4 row reads `NOT_RUN`, not `NO_DIFFERENCE`.
* **Nothing about the signature table.** No amount of repetition tests whether
  a relation behaves as its `LOW(h)` entry says; that needs physical evidence.
* **No frequency claim about deployed systems.** "20 of 20 valid trials" is a
  statement about 20 simulator runs on one pinned build, not about how often
  this occurs in the field.

## 10. Execution status

`P8` executes this preregistration. Its status at the time of writing, and the
measurements behind it, are recorded in
`research/physical_validation/prereg/MECHANISM_A_REPEATED_STATUS.md` — written
after this file and never edited into it. **This preregistration is not
amended by what happens when it runs.** If it turns out to be unrunnable as
written, that is recorded as `PREREG_UNRUNNABLE` in the failure ledger and a
NEW preregistration is written; this one stands.
