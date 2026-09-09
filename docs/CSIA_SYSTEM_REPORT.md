# CSIA — full system report

**Purpose of this document.** Complete context for an agent or engineer
arriving with no history. What CSIA is, the mathematics, the layer stack, the
software and cyber posture, the simulation apparatus, what has actually been
measured, what has NOT, and where it goes next. Read §0 and §12 if you read
nothing else: §0 is what the system is, §12 is what it is not.

Status: 2026-09-09. Branch `claude/code-reviewer-repo-export-zicovg`.
Ledger: 73 entries. Tests: 153 files. Frozen core: byte-identical to
`csia-v1.0-research-final`.

---

## 0. What CSIA is, in one page

**CSIA (Cross-Sensor Integrity Assessment) is a read-only observer that
maintains a continuous, per-sensor *trust coefficient* on a flying vehicle,
diagnoses the likely cause when trust falls, and declares which mission
capabilities the surviving evidence still supports.**

It does not fly the aircraft. It has **no command path in any mode**. Both
modes (`SHADOW`, `ADVISORY`) report `may_command = False`; there is
deliberately no `ACTIVE` member of that enum. The read-only connection denies
21 send-capable attribute names, the receive wire into the flight controller
is physically cut on the validation rig, and a preflight tool proves both on
every build.

Two consequences to design around:

1. **CSIA will never save an aircraft.** If it says EMERGENCY, a human or the
   autopilot's own failsafe must act.
2. **CSIA failing does nothing to the aircraft.** Kill the process mid-flight
   and the vehicle does not notice. That is the point.

The distinguishing idea, stated without novelty claim (see §12): sensor
cross-consistency is treated as *Bayesian evidence for a per-sensor
reliability belief*, propagated over a graph whose edges are **physical
relationships**, rather than as a threshold-based fault detector. What the
system produces is not "sensor X failed" but "the evidence supports these
capabilities and not those".

---

## 1. The mathematics

### 1.1 Trust coefficient — recursive Bayesian, Beta-conjugate

Each sensor node *i* carries a Beta belief over its own reliability:

```
    T_i ~ Beta(α_i, β_i)          T_i = α_i / (α_i + β_i)  ∈ [0,1]
```

`T_i` is the posterior mean and is what the rest of the system consumes.

**Per-tick update with adaptive forgetting:**

```
    α_i ← ρ_i · α_i + E_i
    β_i ← ρ_i · β_i + (1 − E_i)
```

`E_i[k] ∈ [0,1]` is the fused evidence for tick *k*. `ρ_i` is an adaptive
forgetting factor with effective memory ≈ `1/(1−ρ)` ticks.

**Declared constants** (`csia/trust_engine/engine.py`, frozen):

| constant | value | meaning |
|---|---|---|
| `alpha0, beta0` | 8.0, 2.0 | prior, so `T(0) = 0.8` — mildly optimistic |
| `rho_max` | 0.998 | ≈500 ticks ≈ 20 s memory when predictors agree |
| `rho_min` | 0.95 | ≈20 ticks ≈ 0.8 s memory under disagreement |
| `w_nbr` | 0.35 | neighbour-consistency weight |
| `w_phys` | 0.30 | physics self-consistency |
| `w_temp` | 0.20 | temporal stability |
| `w_stat` | 0.15 | statistical confidence |

Because evidence keeps flowing after a transient ends, **trust recovers
naturally**. Degradation is graceful and reversible — never a latched flag.

### 1.2 The four evidence channels

`E_i` fuses four sub-scores under the weights above:

- **C_nbr** — physical consistency with graph neighbours: a trust-weighted
  mean of edge consistencies `c_ij`, weighted by the edge gate **and by the
  neighbour's own current trust**. This is the trust-propagation term: a
  distrusted neighbour cannot drag a healthy sensor down, and a gated-out
  edge contributes nothing rather than false-alarming.
- **C_phys** — internal physics self-consistency, gated identically.
- **C_temp** — agreement with a Holt (double-exponential) predictor.
- **C_stat** — innovation-whiteness via a variance-ratio test.

### 1.3 The trust graph — edges are physics, not correlations

Eight nodes: `imu0, imu1, baro, mag, gps, motor_esc, battery, vibration`.
Eleven edges, each a *physical relationship* with a residual that can be
computed and compared:

| edge | spans | the physics |
|---|---|---|
| `redundant_imu` | imu0–imu1 | identical quantities, independent noise/bias |
| `accel_motor_current` | imu0–motor_esc | thrust accelerating the airframe must draw current |
| `accel_esc_rpm` | imu1–motor_esc | vertical accel tracks total prop speed squared |
| `altitude_baro` | baro–gps | baro altitude vs GPS vertical channel |
| `velocity_gps_doppler` | imu0–gps, imu1–gps | integrated accel vs Doppler velocity (spoof detector) |
| `attitude_gravity_mag` | imu0–mag | accel-derived tilt feeds mag tilt compensation |
| `heading_course` | mag–gps | mag heading vs GPS course over ground |
| `power_thrust` | motor_esc–battery | summed motor current must match pack current |
| `vibration_prop_freq` | vibration–motor_esc | dominant vibration line tracks RPM/60 |
| `temp_bias_drift` | battery–baro | shared thermal environment drives bias |

**Edge weighting** (`csia/runtime/online.py:610`) is the single most
load-bearing line in the runtime:

```
    weight(edge) = gate × fresh[endpoint_a] × fresh[endpoint_b]
```

Every edge requires **both** endpoints alive. A missing, stale or absent
sensor contributes no evidence anywhere — its trust simply holds at the
prior. This is also why a zero weight is *ambiguous*: it is equally
consistent with either endpoint being stale, both, or the gate being closed
(HF-014, §7.2).

`fresh[n] = valid ∧ seen ∧ (τ − last_t) ≤ stale_timeout[n]`.

### 1.4 Diagnosis — Bayesian posterior over causes

`csia/diagnosis/` maintains a posterior over hypothesis classes: `nominal`,
`gps_fault`, `imu0_bias_drift`, `imu1_bias_drift`, `mag_interference`,
`power_fault`, `vibration_anomaly`, plus an `unknown` catch-all.
`PRIOR_NOMINAL = 0.86`, remaining mass split evenly. Two implementations
exist: `DiagnosisCore` (likelihood-based) and `CausalDiagnosis`
(structure-aware).

The `unknown` class is not decoration — it is the mechanism by which the
system declines to name a cause it cannot support.

### 1.5 Failsafe — six thresholds, dwell, arming

`csia/runtime/failsafe.py` (frozen) maps trust to a level in
`NORMAL < CAUTION < CRITICAL < EMERGENCY`:

| threshold | value | rule |
|---|---|---|
| `nav_caution` | 0.75 | GPS/navigation trust |
| `heading_caution` | 0.60 | magnetometer |
| `struct_critical` | 0.60 | vibration |
| `power_critical` | 0.70 | battery |
| `att_caution` | 0.82 | attitude |
| `att_emergency` | 0.70 | attitude reference lost |

Timing: `arm_time = 10.0 s` (no action before), `dwell_up = 1.0 s` (escalate),
`dwell_down = 5.0 s` (de-escalate). `descent_rate = 1.5 m/s`.

**`baro` and `motor_esc` appear ZERO times in the frozen `_conditions`.** Two
of eight nodes have no failsafe rule of any kind. That gap is SR-001/SR-006
and is covered by an overlay (§3.3), not by editing the frozen file.

### 1.6 The escalation-delay model

For a fault that destroys only the physics residual at the GPS node, evidence
floors at `e_f = w_nbr + w_temp + w_stat = 0.70` against a 0.75 threshold, so
trust cannot fall below 0.70 however large the error. Ticks to cross:

```
    N* = ln[ M(T*−e_f) / (S₀(T₀−T*) + M(T*−e_f)) ] / ln ρ  ≈ 93 ticks = 3.7 s
```

The dominant term is `S₀(T₀−T*) = 118.82` against `M(T*−e_f) = 1.0`: **the
delay is set by how much agreement the calm period banked, not by how bad the
fault is.** Adding the failsafe's 1 s dwell gives ≈118 ticks at the floor,
which classifies 19 of 21 sweep cells correctly.

---

## 2. Layer stack

```
   VEHICLE  (autopilot, sensors — MAVLink telemetry, read-only)
      │
   EVIDENCE (csia/sensors, csia/aircraft — adapters, canonical AircraftSample)
      │
 ┌────▼──────────────────────────────────────────────┐
 │  FROZEN CORE  — csia-v1.0-research-final          │
 │  trust_engine · diagnosis · runtime/online.py     │
 │  runtime/failsafe.py · scenarios.py · profiles.py │
 └────┬──────────────────────────────────────────────┘
      │                          ▲
      │              csia_supervision (overlay: may only RAISE)
      │
   csia_assurance   (firewall, witness, config_gate — output discipline)
      │
   csia_mission     (capability, product, planner, recovery — XR-1 layer)

   csia_stress      (measures all of the above; never part of the product)
```

**FROZEN_PATHS — six, byte-identical to the tag, never edited:**
`csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`,
`csia/runtime/failsafe.py`, `csia/scenarios.py`, `csia/profiles.py`.

**NOT frozen:** `csia/deploy/`, `csia/sensors/`, `csia/runtime/plugins.py`,
`csia/aircraft/`, and every `csia_*` package above.

The freeze tag is **LOCAL ONLY** — pushing it was refused (403). Identity is
therefore established two independent ways: tag comparison where available,
and source digests, which reproduce anywhere.

Sizes: `csia` 138 modules, `csia_mission` 16, `csia_stress` 8,
`csia_assurance` 4, `csia_supervision` 4.

---

## 3. The layers above the core

### 3.1 `csia_assurance` — output discipline
Firewall, witness and config gate. Nothing leaves the system without a
support verdict; a claim with no witness does not get published.

### 3.2 `csia_mission` — capability, not fault
Consumes `EvidenceStatus` and evaluates `CapabilityContract`s to one of five
states: `SUPPORTED`, `DEGRADED_SUPPORTED`, `NOT_SUPPORTED`, `UNKNOWN`,
`NOT_EVALUABLE`.

**UNKNOWN IS NEVER PROMOTED TO SUPPORTED** — not by a default, not by an
absence. `usable` is written as explicit membership in `(SUPPORTED,
DEGRADED_SUPPORTED)` rather than `!= NOT_SUPPORTED`, because the negative
form quietly makes UNKNOWN usable.

The XR-1 contract set declares 18 evidence ids and 13 capabilities
(`timing`, `attitude_hold`, `altitude_hold`, `airspeed_regulation`,
`stable_flight`, `relative_navigation`, `absolute_navigation`,
`controlled_glide`, `RGB_capture`, `thermal_capture`, `local_mapping`,
`global_mapping`, `telemetry_downlink`). Contracts state `does_not_require`
explicitly and it is checked — a capability that quietly acquires a
dependency it documented itself as not having is the drift that field
catches.

### 3.3 `csia_supervision` — the overlay, and its one rule
The frozen failsafe supervises *degradation* well and *absence* badly. Two
gaps, two rules:

- **`dataloss.py` (SR-001)** — a sensor stops delivering. Levels are
  **derived** from the severity the frozen config already assigns that
  sensor (`ANCHORED`), except `baro` and `motor_esc` which have nothing to
  derive from and are labelled `UNANCHORED_THIS_IS_A_CHOICE`.
- **`lowtrust.py` (SR-006/SR-008)** — a sensor keeps delivering data the
  trust engine does not believe. Covers exactly the two sensors the frozen
  policy judges nowhere; **refuses at import** to carry a rule for any sensor
  the frozen policy already thresholds, because that would be retuning the
  frozen core through the back door.

**Composition: `effective = max(frozen, supervisor)`.** The overlay can only
ever add urgency. A layer above the core that could de-escalate would be able
to overrule a frozen safety decision.

- **`capability_bridge.py` (SR-005)** — connects the two. A lost sensor
  withdraws the evidence riding on it. **Demote-only**: a lost sensor proves
  the evidence is not supportable; a *present* sensor proves nothing, because
  support is the firewall's verdict and delivering bytes is not a verdict.
  UNKNOWN is never resolved into a definite negative.

Note the symmetry: the failsafe overlay may only **raise**; the evidence
bridge may only **lower**. Both fail safe.

---

## 4. Cyber / safety posture

| property | how it is enforced | how it is proven |
|---|---|---|
| no command authority | `may_command=False` on every mode; no `ACTIVE` enum member | `check_no_command_authority()` probes 21 send-capable names, all DENIED or ABSENT |
| read-only link | `ReadOnlyMavlinkConnection` wrapper; write half closed (`CLOSED_ENOTCONN`) | recorded in every flight-log header |
| physical barrier | RX wire into the FC **cut** on the rig | E2 build packet §4.1 |
| frozen algorithm | six FROZEN_PATHS, tag + source digests | preflight, two independent methods |
| attributable runs | working-tree-clean check | preflight fails a dirty tree |
| no credential leakage | secrets scan, sanitization guard | `make check-blocking`, 85-file allowlist |
| export posture | `docs/compliance/EXPORT_CONTROL_REVIEW.md` | REVIEW status recorded per package |

**Explicitly out of scope, permanently:** RF jamming, GPS spoofing
*transmission*, counter-UAS behaviour, autonomous targeting, stealth or
evasion, weapons. GPS spoofing appears only as a *simulated stimulus* to test
detection, never as a transmitter.

Preflight (`tools/deploy/preflight.py`) runs 10 checks with three outcomes —
`READY`, `DO_NOT_FLY`, `INCONCLUSIVE` — and **INCONCLUSIVE is not a pass**.

---

## 5. Simulation apparatus

- **`csia/sensors/`** — physics-based sensor models and a fault model with
  six kinds: `dropout`, `bias_drift`, `emi_spike`, `gps_spoof`,
  `vibration_anomaly`, `power_sag`.
- **`csia/scenarios.py`** (frozen) — the scripted scenario catalogue.
- **`csia_stress/`** — the measurement layer:
  - `applicability.py` — a two-stage matrix asking *does this fault kind do
    anything to this sensor?* **18 live, 30 inert, 1 lost in transport.** An
    inert pair raises `VacuousFault` at construction, because a stimulus that
    reaches nothing produces a result indistinguishable from robustness.
  - `campaign.py` — 1000 randomised multi-fault (MSRD) variations, 2–4
    simultaneous faults on distinct sensors, bit-for-bit reproducible.
  - `detection_floor.py` — magnitude sweeps that publish where detection
    begins.
  - `low_trust_false_alarm.py` — false-alarm rate for the overlay rules.
  - `observables.py` — detection latency, recovery time, escalation,
    attribution.

**Flight profiles:** `hover_circle`, `fast_cruise`. Two profiles, one
simulator. See §12.

---

## 6. What has actually been measured

### 6.1 Supervision effect (1000 variations, seed 20260907)

| | frozen only | + data-loss overlay |
|---|---|---|
| detected | 783 / 1000 | **969 / 1000** |
| detections lost | — | **0** |
| still undetected | 217 | 31 |

Zero detections lost is structural, not luck: `max(frozen, supervisor)`
forbids it. Every one of the 186 newly-detected runs involved a `dropout` —
exactly the absence mechanism SR-001 named.

### 6.2 Detection floors (single fault, declared grid, nothing tuned)

| pair | floor | note |
|---|---|---|
| `bias_drift@imu1` | 0.02 units/s | |
| `bias_drift@imu0` | 0.05 | campaign range straddles it |
| `bias_drift@mag` | 0.30 | **entire campaign range [0.03,0.20] is below it** |
| `bias_drift@baro` | never escalates | trust falls to 0.231 — no rule names baro |
| `power_sag@battery` | 25 rpm | frozen `power_critical` working |
| `power_sag@motor_esc` | 2200 rpm | **3× the campaign maximum of 700** |

The `baro` result is the important one: the stimulus reaches the stream (a
**327 m** altitude error, verified against the unfaulted stream) and trust
collapses. The trust layer sees it perfectly; no failsafe rule names the
sensor. That is `TRUST_RESPONDS_BUT_NO_FAILSAFE_RULE`, a separate outcome
from "undetected", because calling it undetected blames the sensing and hides
a missing rule.

These floors *explain* the 31 misses: `mag` and `baro` are structurally out
of reach in the campaign's parameter range, and they dominate the miss
counts (mag 21, baro 18 of 67 involvements).

### 6.3 The low-trust rules now shipping

| | baro | motor_esc |
|---|---|---|
| threshold | 0.75 (borrowed `nav_caution`) | 0.70 (borrowed `power_critical`) |
| clean-flight min | 0.9930 | 0.9672 |
| worst with no own fault | 0.9930 | **0.7984** |
| margin | 0.243 | **0.098** |
| false alarms | 0 / 58 | 0 / 140 |
| detects from | drift 0.02 | 250 rpm |

Thresholds are **borrowed frozen constants**, provenance
`BORROWED_FROM_A_FROZEN_CONSTANT` — weaker than `ANCHORED`, stronger than a
free choice. The number is frozen; applying it to that sensor is a judgement.

**A judgement requires ≥2 live corroborating edge partners.** With one, a
disagreement cannot say *which end* is at fault. Cost, stated: a sensor down
to one live partner is never judged, so genuine degradation during a
multi-sensor failure is missed.

### 6.4 Quality

- Coverage (mission + assurance): **86.86 %**
- Mutation, frozen core, corrected 13-file subset: **0.5583 (67/120)** over
  244 sites. Per file: engine/failsafe/bayes **1.000**, profiles 0.500,
  causal 0.421, hypothesis 0.326, online 0.231.
- Mutation, mission layer: 0.6726 · assurance baseline: 0.6125
- Tests: 153 files, full suite green.

**Negative result worth carrying:** 22 tests written specifically to kill
`online.py` survivors moved line coverage and killed **zero** sampled
mutants. Coverage is not the lever.

---

## 7. Open problems

### 7.1 Decision replay is DIVERGENT on both platforms (HF-004, open)
Replay is the only mechanism that turns "the log says X" into "X is
reproducible by an independent path". Until it works, every result is
one-shot. The software-hardening gate does **not** count it as PASS.

### 7.2 The PX4 divergence — mechanism found, root cause not (HF-014)
All 144 divergences measured: every one is the replay seeing **more** live
edges, never fewer; 122 are exactly `altitude_baro`; every affected edge has
a weight that is a *product of freshness terms*, and residual values always
agreed. They form 10-tick runs recurring at ~1.0 s — the baro arrival
cadence.

The obvious explanation was **tested and ruled out**: no single staleness
timeout reproduces the recording (baro reads fresh at ages 0.044–0.125 s and
stale at 0.003–0.496 s; overlapping).

Root cause **undetermined and not claimed**. The logs record the adapter's
per-channel age (a different clock) and gate weights (products, not
factorable). The missing instrument is now built — logs carry the per-sensor
`fresh` map and the staleness config — but existing logs cannot be fixed.
**One SITL run closes this.**

### 7.3 Prose/artifact conflict awaiting a human (MX-024)
`main.tex:901` quotes an evidence-floor range of 0.678–0.700; the artifact's
`observed_range` is [0.6785, 0.9422]. Neither is wrong about a number — the
sentence describes a *selection* the artifact does not record. Three options
costed in `research/publication/DECISION_0700_EVIDENCE_FLOOR.md`. 15 of 19
ambiguous prose literals remain deliberately unresolved (MX-013 records a
tool getting two of five wrong).

---

## 8. The assurance apparatus — and why it is the real story

Three times in one session an instrument produced a clean, plausible,
**entirely fictional** result:

- **MX-020** — the quality ratchet compared committed files against a floor
  derived from those same files. It reported HOLDS every night of its life
  and *could not have reported anything else*.
- **MX-021** — the detection sweep asked for a field that does not exist; a
  broad `except` turned the AttributeError into "not detected", and the sweep
  announced a finding about the frozen core produced entirely by a typo.
- **SR-007** — the false-alarm measurement read a whole-run minimum spanning
  warm-up. It returned 0.8182 (= 9/11) in every run whatever was faulted, and
  that constant was reported as a physical mechanism that does not exist.

Each was caught by a human running a control on a hunch. **None was caught by
anything structural.** The repository tested the system thoroughly and the
apparatus almost not at all.

**MX-025 makes it structural.** `tools/assurance/instrument_controls.py`:

> An instrument may not emit an artifact until it has demonstrated, in the
> same run, that it still responds to a stimulus whose answer is known, and
> stays silent on a stimulus known to be null.

Both halves are required — an instrument stuck on "yes" passes every positive
control ever written, one stuck on "no" (MX-021) passes every negative one.
`guard()` raises; `stamp()` attaches the control evidence to the artifact it
licensed. Every `Control` carries a `basis` naming where its answer comes
from — never the instrument under test, or the control is circular.

**Nine instruments registered:** `quality_ratchet`, `mutation_probe`,
`stress_regression`, `preflight`, `decision_replay`,
`attribute_replay_divergence`, `detection_floor`, `low_trust_false_alarm`,
`campaign`. A test asserts every artifact-writing instrument is registered
and that each calls `guard` before it writes.

**The controls are proven able to fail:** the tests reintroduce all three real
defects verbatim and assert refusal, plus the three opposite failures.

### Other standing rules
- **INCONCLUSIVE / NOT_COMPARABLE is never PASS.** A check that could not run
  never reads as a check that succeeded.
- **Subset fingerprinting** — a mutation score is comparable only over the
  same targets *and* test subset (MX-015).
- **Source digests** — a score is comparable only while the code it was taken
  over is unchanged (MX-020).
- **The ledger** — 66 entries (19 FL, 14 HF, 25 MX, 8 SR), majority negative,
  several recording that the *instrument* was wrong rather than the system.

---

## 9. Where we are

**Working and measured:** trust engine, diagnosis, failsafe, adapters
(ArduPilot + PX4), shadow-mode deployment with proven no-command, flight
logging with full provenance, supervision overlay closing both frozen gaps,
capability bridge, 1000-variation MSRD campaign, detection floors,
instrument controls, quality ratchet with real comparisons.

**Open:** decision replay (HF-004), the PX4 root cause (HF-014), 15 prose
bindings, the 0.700 editorial decision, frozen-core mutation at 0.5583.

**Blocked in this environment:** HITL and E2 (no hardware),
cross-distribution portability (no Docker daemon), prior-art search (all
scholarly APIs 403).

**NOT blocked, contrary to what this report previously said (MX-028):**
ArduPilot SITL. The earlier claim rested on `firmware.ardupilot.org`
returning 403 — that is the BINARY server, and the source path was never
tested. `git ls-remote` against the GitHub repository succeeds, the
toolchain (gcc 13.3, g++, make, cmake) is present, passwordless sudo works,
apt resolves, and 19 GB of disk is free. SITL is therefore the highest-value
OPEN item rather than a blocked one, because one SITL run is what closes
HF-004/HF-014. Exact procedures: `docs/UNBLOCKING_THE_BLOCKED_WORK.md`.

---

## 10. Where it goes next — ranked by leverage

**Tier 1 — changes the character of the evidence**
1. ~~Instrument control pairs~~ — **done** (MX-025).
2. **Falsification search instead of random sampling.** SR-008 is the proof:
   140 random runs found zero false alarms; one *constructed* adversarial case
   found a real one immediately. Replace sampling with active counterexample
   search per claim.
3. **Every gate proven able to fail** — inject a known regression, assert it
   fires. MX-020 sat green for its whole life.
4. **Close the replay loop** — one SITL run with the HF-014 instrumentation.

**Tier 2 — structural**
5. **Differential testing against an independent reimplementation** —
   catches shared assumptions no test encodes.
6. **Complete the provenance chain** — every published number → artifact →
   commit → input digest → instrument version.
7. **Raise frozen-core mutation** — ~44 % of sampled mutants survive; and
   coverage is demonstrably not the lever.

**Tier 3 — the real ceiling**
8. SITL (runnable HERE — see MX-028), then HITL, hardware,
   cross-distribution. Everything above still runs on one simulator, one
   host, one Python.

### Further out — the theoretical direction

These are **directions, not claims**, and none is evidenced yet:

- **Trust as a certificate, not a number.** Today `T_i` is a scalar. The
  natural extension is a *signed evidence certificate* — value, witness set,
  expiry, and the graph path that produced it — so a downstream consumer can
  verify support without trusting the producer. `csia_assurance/witness.py`
  is the seed.
- **Fleet-level trust.** The graph is currently intra-vehicle. Cross-vehicle
  edges (two aircraft observing the same environment) would extend the same
  mathematics to a fleet, with the same demote-only discipline. The hard part
  is not the maths but the trust model between platforms.
- **Online identification of the edge model.** Edge residual thresholds are
  fixed. Learning them per-airframe, with the frozen model as prior, would
  adapt to a specific vehicle — but requires a provenance story for a
  threshold that moves, which the whole freeze discipline currently forbids.
- **Formal capability semantics.** `bounded_verify.py` proves bounded
  properties. A full formalisation of the capability lattice — proving
  UNKNOWN can never be promoted under any input sequence — would convert a
  tested invariant into a theorem.
- **Evidence-gated autonomy.** The XR-1 end state: the aircraft continues the
  maximum useful benign mission subset that is both physically feasible and
  evidentially justified, never certifying a capability its surviving
  evidence cannot support. Every layer above the core exists to make that
  sentence checkable. **No stage may promote itself.**

---

## 11. How to work in this repository

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q          # full suite
make check-blocking                            # publication guards
.venv/bin/python tools/deploy/preflight.py --platform ardupilot
```

**Rules that are not negotiable:**
- Do not modify the six FROZEN_PATHS. Overlay instead.
- Do not retune a threshold, weight, prior, dwell or signature to rescue a
  result. If a result is bad, report it.
- `git add -A` *before* the verification run — the doc-count guard counts
  tracked files. And re-run tests that read a file **after** changing it.
- Every new measurement instrument needs a registered control pair.
- Record negative results. The ledger is the most valuable asset here.

---

## 12. What this system is NOT — read before making any claim

- **Not proven novel.** The prior-art search has *never run* — every
  scholarly source returns 403 in this environment, re-verified 2026-09-08.
  Four mechanisms could already be published: graph-structured sensor trust
  with physics edges; Beta trust from pairwise residuals; advisory monitors
  with technically-enforced no-command; evidence-gated capability
  declaration. The honest wording is **"not shown to be novel"**.
- **Not a certified safety artifact.** No DO-178C, no ARP4754A, no
  qualification evidence. Do not describe it as one.
- **Not validated on hardware.** Every number in §6 is simulated, on two
  flight profiles, one simulator, one host, one Python.
- **Not verified by replay.** Decision replay is DIVERGENT; results are
  one-shot until it works.
- **Not a fault detector that acts.** It is advisory in every mode, forever,
  by design.
- **Not a claim about embedded timing.** Latency figures are desktop Python.

**The standing principle:** a negative result is acceptable. A known theorem
is acceptable. An unresolved mechanism is acceptable *if labelled*. An
unsupported novelty claim is not.
