# Phase 3 preregistration — closed-loop consequence measurement

**Written and committed before the `locked` partition is opened.** The design
below — scenarios, policies, action model, constants, outcome classes and kill
criteria — is frozen at this commit. Nothing in it may change after locked
results are inspected. If a defect is found afterwards it is recorded as a
defect and the locked result stands as what it is.

**Scope: deterministic simulation only.** No hardware, no RF, no armed
physical vehicle, no real actuator, no flight. See §8 for why this phase is
`MODEL_BASED_ACTION_CONSEQUENCE` and not `SITL_CLOSED_LOOP_EXECUTION`, and
what would change that.

---

## 1. Measured provenance of the starting state

Everything here was read from the repository at the commit named, not recalled.

| item | value |
|---|---|
| HEAD at Phase-3 start | `e5c58fadaaec4bae95758a38f42b9f6c754c7418` |
| working tree | clean (`git status --porcelain` empty) |
| frozen core | 12 of 12 files match `docs/v1/FROZEN_BASELINE.json`, 0 mismatches |
| frozen-core aggregate | `52683d62df3e31a3e44afc03719da0abf3dfca1548ff99e3df477880465fed32` |
| full suite | `PYTEST_EXIT=0` |
| blocking guards | `BLOCKING GUARDS: PASS`, `GUARDS_EXIT=0` |

The frozen-core aggregate is `sha256` over `"{path}:{sha256(bytes)}\n"` for the
twelve files in sorted path order. It is a convenience digest for this
document; the authoritative check is the twelve per-file comparisons, which
all matched.

## 2. Phase-2 inputs, frozen and hashed

| artifact | sha256 |
|---|---|
| `research/consequence/results/GATE_INVENTORY.json` | `fa09d82c321b31e3766e93534380de1d72bdc96a0bb426bc7633bc7254a85059` |
| `research/consequence/results/INDEPENDENT_GATE_EVALUATION.json` | `9dc8eb2e84d48aae30fc9e189ac889282149f1ac3185e3205f904d9328e9740c` |
| `csia_consequence/gates.py` | `b7d4c5ecddffdffb9c329a9e44b3494da2a9c2492a5f9d361ad22c655e217240` |
| `research/consequence/independent_gate_evaluator.py` | `404844ea5dbc79735838a59f35eeda0827b124134aced1e1830f989f3881b729` |

### 2.1 A count in the task brief disagrees with the artifact

The brief that commissioned this phase states **17 total gates**. The frozen
artifact states **18**:

```
gate_count                                18
uncovered_candidate_count                  8
uncovered_candidate_count_excluding_withdrawal   7
len(gates) == sum(len(v) for v in by_coupling.values()) == 18
```

The artifact is taken as authoritative because it is the thing that was
generated from source and is pinned by a committed test. **17 is not adopted,
and the disagreement is recorded rather than reconciled silently.** The other
three figures in the brief — 7 direct candidates, 1 `_hist_ok` withdrawal
path, 8 with the withdrawal included — match the artifact exactly.

### 2.2 The independent evaluator is corroboration, not blind validation

`independent_gate_evaluator.py` imports the standard library only and reaches
the same seven freshness-independent terms plus the withdrawal path. **The two
disagreed on the first run.** The evaluator mis-parsed four terms and missed
every `P[...]` term, and **those parse defects were repaired after the
disagreement was seen.**

The repairs are defensible in themselves — a term that does not parse is a bug
in the parser, not a finding about the code — but the sequence means the
agreement is **corroboration by a second derivation that was adjusted with
knowledge of the first**. This phase does not describe it as independent
validation. Wording that would be supported: *a second, standard-library-only
derivation, repaired after an initial disagreement, reaches the same set.*
Wording that would not: *independently validated.*

A blind re-run — a fresh evaluator written without sight of the inventory,
whose first output is the recorded one — has not been done, and until it is,
the stronger wording is unavailable.

## 3. Candidate scope, determined by experiment on development seeds

Of the eight Phase-2 candidates, **three are drivable and observable** through
the frozen core's public interface. The determination was made by running the
real `OnlineTrustLayer` and reading `TrustState.edges`, not by reading source.

| candidate | in `TrustState.edges`? | gate range measured | in scope | why |
|---|---|---|---|---|
| `accel_motor_current` | yes | armed `0.0 → 1.0`, disarmed `0.0` flat | **YES** | closes hard on `armed=False` with data fresh |
| `accel_esc_rpm` | yes | armed `0.0 → 1.0`, disarmed `0.0` flat | **YES** | same |
| `heading_course` | yes | `0.0 → 1.0` in both arming states | **YES** | driven by `speed_gate * gvalid`, not by arming |
| `temp_bias_drift` | yes | constant `0.2000` in every condition | no | the gate never closes, so no B/C contrast exists |
| `phys_gps` | **no** | — | no | node term; not exposed |
| `phys_mag` | **no** | — | no | node term; not exposed |
| `phys_vibration` | **no** | — | no | node term; not exposed |
| `hist_vr_withdrawal` | **no** | — | no | withdrawal path; not exposed |

**Why the four node terms are out of scope.** `TrustState` exposes `edges`
(the `E` dict) and does not expose the `P` node gates or the `_hist_ok`
withdrawal. They exist only inside `_tick`'s local `feats`. Observing them
would require adding an accessor to `csia/runtime/online.py`, which is in the
frozen core. **Removal action:** a read-only accessor on `TrustState`, under
its own authorization and its own re-freeze, would bring four more candidates
into scope. Reconstructing the gates outside the frozen core was rejected: a
reconstruction that drifted from the original would silently produce wrong
gate states and there would be nothing to catch it.

So Phase 3 covers **3 of 8** candidates. Any result here is a statement about
those three.

## 4. The structural prediction being tested

From `csia.diagnosis.causal.SOURCE_INDICATORS`, the per-source indicator sets
are the LOW-sets over which attribution is decided. Two of them are:

```
imu0: {redundant_imu, accel_motor_current}
imu1: {redundant_imu, accel_esc_rpm}
```

Their symmetric difference is exactly `{accel_motor_current, accel_esc_rpm}` —
**the two gates that close together on `armed=False`**. `redundant_imu` is in
both and cancels in the log-likelihood ratio, so it can report that the two
IMUs disagree and cannot say which one is wrong.

So the preregistered prediction is: **while disarmed, imu0 and imu1 are
structurally inseparable, and any attribution to one of them is unsupported.**

The decision that depends on that attribution is real and lives in the frozen
core: `FailsafePolicy._conditions` issues
`Action("SELECT_IMU", ..., {"use": best_imu})` when the trust gap exceeds
`imu_isolation_gap = 0.12`, and `Action("STABILIZE", ..., {"source": best_imu})`
in `EMERGENCY`.

**The counter-consideration, stated before the result.** `FailsafePolicy.update`
begins:

```python
if getattr(state, "armed", None) is False:
    self.reset_timers()
    return []
```

The decision layer abstains under the *same* condition that closes the gate.
If that abstention fully covers the occlusion, **H2 is rejected for these two
gates by the kill criterion "correctly handled by an independent path"** — and
that is a publishable negative result, not a failure of the phase. The residual
case, and the one the campaign is built to measure, is the **arm transition**:
a fault present before arming, with `armed_gate` reopening on a one-second ramp
(`clip(tau - armed_since, 0, 1)`) while the vehicle is already leaving the
ground, and `dwell_up = 1.0 s` on top.

`heading_course` is predicted **non-consequential for identifiability**: no
pair of `SOURCE_INDICATORS` sets has `{heading_course}` as its sole symmetric
difference. It is carried through the campaign anyway, as the phase's internal
negative control.

## 5. Experimental conditions

For every in-scope gate, five matched scenarios per seed:

| id | condition |
|---|---|
| **A** | nominal control — no fault, same seed, same schedule |
| **B** | fault injected with the gate CLOSED and all data fresh |
| **C** | matched fault, same onset, with the gate OPEN |
| **D** | fault with the independent freshness path enabled (P1's rule active) |
| **E** | fault with support-aware output enabled (P2 active) |

Matched means: same seed, same truth trajectory, same fault parameters, same
onset time. Only the gate-determining variable differs between B and C.

Gate-determining variable per gate:

- `accel_motor_current`, `accel_esc_rpm`: the `vehicle_status.armed` schedule.
  B arms at `t_arm`; C is armed from `t = 0`.
- `heading_course`: the flight profile. B flies `hover_circle` (low ground
  speed, `speed_gate` closed); C flies `fast_cruise` (`speed_gate` open).

Order of execution: **development seeds first** (12 seeds, partition
`development`), design frozen and committed, then **locked** (24 seeds) once.
Scenarios are not selected after inspecting locked outcomes.

## 6. Seed partitions

`csia_consequence/phase3_partitions.py`, its own domain
`csia/consequence_closed_loop_phase3/2026-09-20`, disjoint by construction from
the phase-one, follow-up (including companion) and Phase-2 partitions.

| partition | seeds |
|---|---|
| `development` | 12 |
| `validation` | 16 |
| `locked` | 24 (sealed; the call site must say it is opening it) |

Manifest hash: `6fda17fac860a55cff5434af41e0c5f60045a7014ece1583951db06a871c8ecf`

## 7. Policies

All three consume the **same** `TrustState` stream from the real
`csia.runtime.online.OnlineTrustLayer`. None of them commands anything.

- **P0 — current CSIA behaviour.** `TrustState` → the frozen
  `csia.runtime.failsafe.FailsafePolicy`, unmodified. This is the repository's
  shipped behaviour and is the baseline.
- **P1 — freshness-only fallback.** P0, plus one rule: if any monitored sensor
  is not fresh, raise at least `CAUTION`. This is the strongest form of "the
  existing freshness logic already covers it", and it is implemented so that it
  can win.
- **P2 — support-aware.** P2 emits **only** a typed support state —
  `IDENTIFIABLE`, `AMBIGUOUS`, `NON_IDENTIFIABLE` — from
  `csia_consequence.support.classify` over the `SOURCE_INDICATORS` LOW-sets and
  the live gate weights. **P2 has no actuator authority and issues no action.**
  A separate deterministic adapter, `csia_consequence.action_adapter`, maps
  `(failsafe level, actions, support state)` to a response. The separation is
  structural, not stylistic: the adapter is the only module that names a
  response, and P2 cannot reach it except through the typed value.

## 8. Execution level

**`MODEL_BASED_ACTION_CONSEQUENCE`.**

The diagnosis half is *not* a model: `TrustState` comes from the real frozen
`OnlineTrustLayer`, fed by the real `csia.sensors` fault injector, and P0's
response comes from the real frozen `FailsafePolicy`. What is modelled is the
**vehicle's response to the response** — §9.

**SITL was available and was not used, and the reason is not its absence.**
Both binaries exist in this container:
`/home/user/px4/build/px4_sitl_default/bin/px4` and
`/home/user/ardupilot/ardupilot/build/sitl/bin/arducopter`. Reaching
`SITL_CLOSED_LOOP_EXECUTION` would require arming a simulated vehicle and
sending it mode commands so that the autopilot executes CSIA's recommendation.
Two things forbid that here:

1. The Phase preregistration's scope clause — "no vehicle is armed".
2. The architecture. CSIA holds zero actuator authority; the command path
   (`csia.runtime.service.MavlinkActuator`) is opt-in and out of scope for an
   advisory measurement.

**Removal action:** a separately authorized SITL campaign in which the action
adapter drives `MavlinkActuator` against a simulated airframe, with the arming
clause amended. That campaign would reach `SITL_CLOSED_LOOP_EXECUTION` for the
executed half and would leave the diagnosis half exactly where it already is.

No result in this phase may be described as the vehicle having behaved in any
way. Nothing flew.

## 9. The action-consequence model, with every constant fixed here

Deterministic, declared before any locked run, and **not tunable afterwards**.

The vehicle is modelled as a point mass following the scenario's truth
trajectory. A latent fault injects a drift whose rate depends on the fault, and
a response changes that rate and/or begins a descent.

| constant | value | meaning |
|---|---|---|
| `H_HOVER_M` | 30.0 | altitude at which the mission is flown |
| `DESCENT_RATE_MPS` | 1.5 | taken from `FailsafeConfig.descent_rate` |
| `REACT_DELAY_S` | 0.5 | actuation lag between a response and the vehicle changing behaviour |
| `GEOFENCE_R_M` | 120.0 | horizontal fence radius from the mission centre |
| `ENERGY_FULL_S` | 900.0 | modelled endurance at nominal demand |
| `DRIFT_IMU_MPS` | 1.20 | horizontal drift rate under an undetected IMU attitude bias |
| `DRIFT_MAG_MPS` | 0.65 | horizontal drift rate under an undetected heading fault |
| `DRIFT_ALT_MPS` | 0.25 | vertical error rate under an undetected attitude bias |
| `MITIGATED_FRACTION` | 0.25 | residual drift rate once the correct response is active |
| `WRONG_SOURCE_FACTOR` | 1.60 | drift multiplier when `SELECT_IMU` picks the faulty unit |
| `CAUTION_FRACTION` | 0.60 | residual drift under a merely-conservative response |
| `SAFE_STATE_ALT_M` | 0.5 | altitude at or below which the vehicle is "safe" |

Response → vehicle behaviour:

| response | behaviour |
|---|---|
| `NORMAL` (no action) | drift accumulates at the full fault rate; never reaches safe state |
| `CAUTION` generic | drift × `CAUTION_FRACTION`; no descent |
| `SELECT_IMU(correct unit)` | drift × `MITIGATED_FRACTION`; no descent |
| `SELECT_IMU(faulty unit)` | drift × `WRONG_SOURCE_FACTOR` — **worse than doing nothing** |
| `CRITICAL` / `PREPARE_LANDING` / `LAND_*` | drift × `CAUTION_FRACTION`, descent begins after `REACT_DELAY_S` |
| `EMERGENCY` / `CONTROLLED_DESCENT` | drift × `MITIGATED_FRACTION`, descent at `DESCENT_RATE_MPS` |
| `ABSTAIN` (P2 `AMBIGUOUS` / `NON_IDENTIFIABLE`) | treated as `CAUTION` generic — the adapter's conservative branch |

`WRONG_SOURCE_FACTOR > 1` is the modelling decision that makes H2 falsifiable
at all: it is what makes a confident wrong attribution materially different
from silence. It is declared here, before any locked run, and it is an
assumption, not a measurement. **A reader who rejects it should read every H2
result as conditional on it.**

## 10. Recorded fields

Per scenario, per policy, per tick where applicable: gate identifier, fault
identifier, latent truth, gate state, freshness state, active evidence set,
diagnostic hypothesis output, support state, freshness-path output, recommended
response, response executed in the model, correct response under latent truth,
safe-state definition, time to first response, time to correct response, time to
safe state, position error, altitude error, geofence margin, energy margin,
unsupported confident-attribution duration, ambiguity duration, outcome class.

## 11. Outcome classification

| class | definition |
|---|---|
| `CORRECT_ACTIONABLE` | the response matches the correct response under latent truth |
| `INCORRECT_ACTIONABLE` | a confident actionable response that differs materially from the correct one — including `SELECT_IMU` on the faulty unit |
| `UNSUPPORTED_CONFIDENCE` | a confident attribution issued while the separating evidence for it is entirely gated off |
| `ABSTENTION` | an explicit `AMBIGUOUS` or `NON_IDENTIFIABLE` output |
| `SAFE_FALLBACK` | a conservative response short of the correct one, not harmful |
| `MISSED_ESCALATION` | latent truth required escalation; none was issued |
| `FALSE_ESCALATION` | escalation issued while latent truth is nominal |

"Materially different" is decided by the **independent evaluator** (§12), from
the recorded response and the recorded latent truth, not by the policy code.

## 12. Independence requirement

`research/consequence/phase3/independent_consequence_evaluator.py` consumes
serialized scenario traces and ground-truth annotations and **imports none of**:
the CSIA diagnostic implementation, the support classifier, the policy
implementation, or the action adapter. Asserted in a fresh interpreter by
inspecting `sys.modules`.

It is tested against hand-constructed positive and negative controls — traces
built by hand with a known correct classification, including at least one of
each outcome class — so that an evaluator that classified everything the same
way would fail.

The same honesty note as §2.2 applies in advance: it is written by the same
author, so it is a second derivation, not a second party.

## 13. Kill criteria, restated and binding

**H2 is supported** only if at least one **locked** scenario produces a decision
conflict in which: the latent fault requires response A; the current diagnostic
output supports response B or an unsupported confidence; and the independent
evaluator establishes that A and B are materially different.

**H2 is rejected** if every candidate case is (a) correctly handled by an
independent path, (b) non-actionable, (c) resolved by existing freshness logic,
or (d) unable to produce a decision conflict.

**H3 is supported** only if the support-aware policy reduces incorrect
actionable decisions on locked scenarios. The cost is reported whatever the
result: reduced resolution coverage, increased ambiguity, increased latency,
increased abstention, and any false refusals.

**H3 is not a safety guarantee and will not be described as one.** Abstention
is not a solved safety problem; a policy that abstains more has moved the
problem, not removed it.

## 14. What this phase may not conclude

No hardware validation. No flight validation. No SITL closed-loop claim. No
statement that a vehicle behaved in any way. No safety guarantee. No universal
prevalence — three gates, one airframe profile, one simulator. No novelty. No
certification. No claim about the four candidates that are out of scope.

---

## Amendment 1 — conditions F and G, added during the development phase

**Made before the `locked` partition was opened, and recorded rather than
folded into §5.** Both additions came from running development seeds, which is
what the development partition is for. Neither changes a threshold, a constant,
a kill criterion or an outcome class.

### F — the occlusion forced into the decision window

§5's conditions A, B and C were not enough to make the phase's negative result
informative. On development seeds, `armed_gate_pair` measured **0.00 s of
overlap between the occlusion and airborne flight** in both B and C. A campaign
that reports "no consequence" from a design in which the occlusion never
reaches the decision window has not tested anything — it has only restated its
own setup. **A test that cannot fail proves nothing**, and that applies to a
campaign as much as to a unit test.

F therefore forces the overlap, and it is a different kind of thing in each
group, which is stated at the point of use and here:

- `heading_course` **F is physically consistent.** The vehicle is armed,
  airborne, past `arm_time`, and hovering, so `speed_gate` is zero while the
  failsafe is fully live. Nothing is faked; this is a flight regime the gate
  genuinely closes in. The mag fault runs inside the hover segment.
- `armed_gate_pair` **F is physically inconsistent and labelled as such.** The
  vehicle reports disarmed from t=12 while its own sensors show it flying. No
  multirotor does this. It also conflates two effects — `armed=False` switches
  the failsafe off wholesale as well as closing the gate — so it is read only
  as evidence that the measurement responds at all, never as a finding.

### G — F's matched control, and the confound that forced it

F's fault is 4 s long; B and C use a 25 s fault. On development seeds
`heading_course` F produced missed escalations, and **F alone cannot say
whether the cause was the closed gate or the shorter fault.** That is a
confound, it was found by looking at development results, and the fix is a
matched control rather than a caveat.

G runs the **same 4 s fault, on the same trajectory, at 25.0 s** — during the
circle, where `speed_gate` is open. F versus G isolates the gate. F versus B
does not, and no F-versus-B comparison is reported as isolating one.

### What Amendment 1 does not do

It does not change the kill criteria, the model constants, the outcome
classes, the materiality rule, the partitions, or the locked protocol. The
locked partition remains unopened at the time of this amendment.
