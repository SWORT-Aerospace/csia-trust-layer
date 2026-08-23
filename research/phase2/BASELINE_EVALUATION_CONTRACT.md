# P1 baseline evaluation contract

**Frozen before any candidate was measured.** The numbers this contract
produced are in `INCREMENTAL_COVERAGE.md`; nothing below was changed after
seeing them.

---

## 1. Rigs, which are two and are not interchangeable

| rig | definition | used for |
|---|---|---|
| **FULL_MODERN** | all modern ArduPilot telemetry exposed exactly as produced | compatibility / portability lane only. **Never used for algorithm scoring.** |
| **LEGACY_COMPAT_CONTROL** | `ESC_TELEMETRY_1_TO_4` suppressed at ingestion | all B0–B4 scoring |

Both results are permanent and neither replaces the other:

- **FULL_MODERN B1 violates R10** — one clean-flight failsafe transition on
  every flight — because the simulator publishes an ESC channel that is
  present, fresh, well-formed, correctly scaled and non-informative (P0.5).
- **LEGACY_COMPAT_CONTROL B1 satisfies R10** — zero transitions, at all three
  flight specs.

The suppression is an **experimental rig control, not a production fix**. It
exists so that a proven simulator placeholder does not contaminate a
comparison between diagnostic algorithms. It is not a proposal, and
`power_thrust` remains untested against data that could falsify it (claim
C14).

---

## 2. Hard constraints, not weighted terms

| constraint | budget | source | if a candidate fails |
|---|---|---|---|
| **R10** clean-nominal CSIA FailsafePolicy transitions | **0** | `docs/REQUIREMENTS.md` R10, asserted by `test_failsafe_clean_no_false_alarms` | fails outright, whatever it gains |
| **R13** trust-core latency | ≤ 2 ms/tick | `docs/REQUIREMENTS.md` R13 | fails outright |
| determinism | required | R3 | fails outright |
| causality | required, no future samples | R2 | fails outright |

**R10 is not weakened because a candidate fails it.** B3 failed it at every
setting tried and was refuted rather than accommodated. Rule 7.

R10 is measured on CSIA's own `FailsafePolicy` transitions, which is exactly
what its verification test asserts — not on internal trust degradation, not on
the autopilot's failsafe. See claim C16.

---

## 3. Two coverage ledgers, both mandatory

| ledger | question |
|---|---|
| **A — SAFETY-RESPONSE** | did the system produce the declared safety-relevant escalation? |
| **B — CORRECT-DIAGNOSTIC** | did it escalate *for* the injected fault, rather than because an unrelated subsystem alarmed? |

Recorded per trial: `autopilot_response`, `csia_response`,
`csia_target_hypothesis`, `csia_final_diagnosis`, `csia_wrong_isolation`,
`unrelated_alarm`, `safety_action`, `response_time`.

A candidate receives no credit for "detecting" a GNSS fault because a battery
artifact fired `LAND_NOW`. Raw detector TPR is never the score.

---

## 4. Candidates

| id | what | information used |
|---|---|---|
| **B0** | native autopilot only, no CSIA in the path | autopilot's own |
| **B1** | frozen CSIA v1 at `848f556`, **unmodified** | as shipped |
| **B2** | alarm when a node's physics consistency sits at or below `PHYS_FLOOR = 0.10` for `k` consecutive ticks | the same per-node residual CSIA computes |
| **B3** | cap accumulated Beta mass at `S_max = 1/(1−ρ_max)`, via `EngineConfig(rho_max=…)` | identical to B1 |
| **B4** | one-sided CUSUM on the standardised pre-transform residual | the same per-node residual CSIA computes |

**No candidate is given information B1 does not have.** No new MAVLink
message, no new sensor, no extra channel. Testing information *addition* is a
separate experiment and was not run.

**B1 is not modified.** B3 changes one existing configuration constant through
the public `EngineConfig`; no production file is edited.

### 4.1 B0 is deliberately generous

B0 responds if **any** of: an EKF variance exceeds `FS_EKF_THRESH` on the
family's channel, the autopilot changes to a failsafe mode, or a STATUSTEXT at
severity ≤ 4 is emitted. ArduCopter's own failsafe is **stricter** — it
requires two of three variances over threshold, or velocity variance at twice
threshold (`ArduCopter/ekf_check.cpp:142-154`). B0 as scored therefore
overstates the native monitor rather than understating it.

---

## 5. Parameter search rules

| candidate | parameter | rule |
|---|---|---|
| B2 | `k` | searched over a fixed grid `{5, 10, 25, 50, 100}` on the **development spec only**, selecting the value that maximises correct-diagnostic coverage subject to R10 = 0 |
| B3 | `ρ_max` | fixed grid `{0.99, 0.98, 0.96}`, development spec only |
| B4 | drift `k` | **by design**, 0.5 — half the one-sigma shift to detect (Page 1954) |
| B4 | decision `h` | fixed grid, smallest value for which the **clean nominal arm alone** produces zero alarms |

Both selection rules read the **clean nominal arm only** and never a fault
outcome. This is threshold-setting against a false-alarm requirement, which is
how detection thresholds are set; it is reported as a parameter, never as an
invention.

B4's in-control statistics `(µ₀, σ₀)` come from the clean nominal arm only.

---

## 6. Partition

Declared in `PARTITION_AUDIT.md` **before** any tuning:

- **DEVELOPMENT: flight spec 0.** All search here and nowhere else.
- **VALIDATION: flight specs 3 and 4.** Never flown on the modern target
  before P1. Touched with parameters already frozen; no parameter changed
  between touches.
- **RESERVED UNTOUCHED: flight specs 1, 2, 5.**

The originally declared protected partition was found **contaminated on the
slew axis** (60 s and 120 s already inspected in E1) and is not treated as
protected.

---

## 7. Metrics recorded for every candidate

nominal transitions · false diagnostic alerts · significant fault misses ·
correct attribution · wrong isolation · detection delay · BOTH ·
AUTOPILOT_ONLY · CSIA_ONLY (incremental) · JOINT_MISS · runtime µs/tick ·
state per node · additional sensor inputs · additional gates ·
implementation complexity.

---

## 8. Fault domain

The frozen catalogue in `csia/scenarios.py`, unchanged: six fault mechanisms
across seven scenarios. **No new fault modes were invented.** Each family has
a per-family validity contract that must pass before the trial contributes to
any metric, verified against the telemetry the family is supposed to corrupt.

`power_sag` is reproduced in part only — its ESC-rpm half cannot exist on this
build — and that is recorded on the trial.

---

## 9. What this contract deliberately excludes

| excluded | reason |
|---|---|
| any neural / GNN / transformer method | simpler baselines have not failed, and no measured reason exists that such a model is necessary |
| new sensor inputs (`satellites_used`, DOP, `noise_per_ms`) | these address F1, not coverage; mixing them in would confound the comparison |
| threshold retuning presented as a method | B2/B3/B4 parameters are reported as parameters |
| E2's replication criteria | frozen separately and **not** revised in light of P1 |
