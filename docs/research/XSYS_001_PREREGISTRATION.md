# XSYS-001 — preregistration of the first confirmatory cross-system experiment

**Status: PREREGISTERED, NOT RUN.** No confirmatory flight exists at the
freeze. This document, the configuration, the trial matrix, the execution
order, the thresholds and every script that will produce or score the data
are frozen together by SHA-256.

| | |
|---|---|
| experiment | XSYS-001: physical actuator degradation against matched RPM telemetry corruption, PX4 SIH |
| freeze manifest | `research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.json` |
| manifest SHA-256 | in `research/xsys_confirmatory_001/prereg/FREEZE_MANIFEST.sha256` and in `tests/test_xsys_001_preregistration.py`. It cannot appear here, because this file is one of the files it hashes |
| machine-readable protocol | `research/xsys_confirmatory_001/prereg/PREREG_CONFIG.json` |
| authorization | `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md` §8: preregistration authorized; the confirmatory run is **not** authorized |
| apparatus | `docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md` (APPARATUS_VALIDATED_WITH_LIMITATIONS, accepted) |

Every number below carries one label:

- **APPARATUS** for exploratory characterization data, already examined (59
  logs, `research/px4_actuator_effectiveness/`);
- **PILOT** for the nominal-only nuisance pilot flown for this design (8 logs,
  `research/xsys_confirmatory_001/apparatus_pilot/`);
- **PREDICTED** for a value derived from apparatus data for a condition not
  yet flown;
- **FROZEN** for a rule or value the confirmatory analysis must use unchanged.

The apparatus and pilot data informed this design. The confirmatory data
must not exist before the freeze and do not.

Under the quarantine of the research exception (§6 there), this whole
document is **PROPOSED**: a protocol, not a result. Its APPARATUS and PILOT
figures are **EXPERIMENTAL** research-only evidence, not validated results or
paper claims.

---

## 1. Scientific question

> Can temporally conditioned cross-domain evidence increase the ability to
> distinguish PHYSICAL ACTUATOR DEGRADATION from RPM/ESC TELEMETRY
> CORRUPTION when both cases produce matched local RPM symptoms?

| | case A — physical actuator degradation | case B — RPM telemetry corruption |
|---|---|---|
| controller command | nominal, then compensating | nominal |
| physical rotor | effectiveness η < 1 (`SIH_MOT_EFF1`) | nominal |
| true RPM, thrust, torque | reduced | nominal |
| rigid-body dynamics | transient disturbance | nominal |
| controller | compensates (motor-0 command rises) | nothing to compensate |
| **observed RPM of motor 0** | reduced, ratio ρ_A(t) | **reduced by construction to the same ratio ρ_A(t)** |

The local RPM symptom is identical in A and B by construction (§5). The
experiment asks whether evidence from other domains, each read only in the
time window where physics says it exists, separates the two causes that the
shared symptom cannot.

## 2. Apparatus findings: consistency check

The request listed twelve accepted apparatus findings and asked for any
discrepancy with the repository to be named. Each was checked against
`docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md` and its data.

| # | finding as stated | repository evidence | verdict |
|---|---|---|---|
| 1 | patch nominally equivalent at η = 1 | equivalence gate, two batches | consistent |
| 2 | apparatus separates command, rotor, RPM, dynamics, estimator | §D causal separation table | consistent |
| 3 | dynamics separation strongest in the first ~150–200 ms | onset → peak body rate 0.148–0.176 s at η 0.9–0.5 | consistent |
| 4 | compensation persists after the transient | steady κ − 1 matches 1/η − 1 within 0.0015 at every controllable level | consistent |
| 5 | RPM is a deliberately shared symptom | case-B construction matches ρ exactly | consistent |
| 6 | navigation EKF contributed little or nothing | no fault-attributable EKF response at any level | consistent, with one nuance: the **hover-thrust estimator** test ratio does respond at η ≤ 0.6 (0.14–0.32 against a pre-fault maximum of 0.09). It is an estimator, not the navigation EKF, and is kept exploratory (§7.4) |
| 7 | controllable regime above the boundary near η ≈ 0.5 | η = 0.5 compensated at the limit (saturated 90% of the compensation phase); η = 0.4 loses altitude | consistent |
| 8 | η ≤ 0.4 tends to loss of control | 0.40 altitude, 0.25 yaw, 0.00 attitude lost | consistent |
| 9 | identical repeats are not independent | bit-identical pre-arm noise across runs | consistent; the pilot adds that **heading does not select the realization** (§4.3) |
| 10 | ~4 ms resolution, ~1-step command/rotor alignment | 92.2% one step; ±1 step in 7.7% | consistent |
| 11 | EKF innovations need sample-time alignment | stamped at the delayed horizon, 152–156 ms | consistent; the pipeline aligns on `timestamp_sample` |
| 12 | allocator "torque achieved" witness withdrawn | §K of the validation document | consistent; not used anywhere here |

**No discrepancy requires stopping.** One earlier discrepancy is already
closed: the preflight estimated a 100 Hz EKF update, and the apparatus
measured 125 Hz. The validation document records the correction, and no
statement above depends on the rate.

## 3. Hypotheses

The request forbids preregistering a hypothesis that the apparatus data
already answer, unless it is needed as a manipulation check. The apparatus
measured **physical magnitudes** at η = 0.9 … 0.5, with three noise
realizations, at one heading, and **ran no CSIA version**. It did not test
the three things this experiment does:

- **frozen three-valued witnesses:** thresholds, detectability gates,
  "not measurable" outcomes;
- **CSIA v2 set elimination** over those witnesses;
- **new conditions:** five η levels none of which was flown, and eleven
  nuisance conditions none of which was flown.

Where an apparatus result predicts an outcome, the prediction is stated
beside the hypothesis. That way a confirmation is not mistaken for a
discovery.

### H_PRIMARY — resolving power beyond the local symptom

> Temporally conditioned cross-domain evidence provides additional resolving
> power for distinguishing physical actuator degradation from matched RPM
> telemetry corruption beyond the local RPM symptom alone.

**Operationalization (FROZEN).**

- **Local evidence alone.** V0 gives v2 only the RPM deficit; dynamics and
  compensation are withheld. It leaves every symptomatic trial AMBIGUOUS
  between the two causes. This is structural: the shared symptom confirms
  both hypotheses (§8).
- **The measure.** The additional resolving power is the **pair resolution
  rate (PRR)**: the fraction of eligible matched pairs in which **both** the A
  trial and the B trial are UNIQUE_CORRECT. It is taken under V3_TEMPORAL at
  checkpoint C3 (§10).
- **Decision rule.** H_PRIMARY is **SUPPORTED iff**
  1. the cluster-conservative one-sided 95% lower bound on the PRR exceeds
     0.5 (§12), **and**
  2. **no** A or B trial is WRONG at C3 under V3.

  Otherwise it is **NOT SUPPORTED**.
- **Why 0.5.** It is a substantive margin, fixed before data. A guesser that
  names a cause at random for each trial resolves a pair with probability
  0.25. A system that always names the same cause resolves none. Requiring
  more than half the pairs to be resolved is twice the chance level.

PREDICTED from apparatus magnitudes: SUPPORTED. This hypothesis is not a
restatement of an apparatus result, because the apparatus never computed a
verdict.

### H1 — early dynamics

> In T1 (0–200 ms after t0), physical degradation produces dynamics evidence
> that differs from the matched telemetry-only case.

**Operationalization.** For a pair, **separation** means that the frozen W_DYN
witness says "not nominal" (False) in A **and** "nominal" (True) in B. The
test is on the rate of separated pairs over eligible pairs, with the same
cluster-conservative bound against 0.5. It is Holm-adjusted within the
secondary family.

PREDICTED: SUPPORTED at η ≤ 0.85. At η = 0.95 the detectability gate that
lets B affirm "nominal" is predicted to pass by only 4.5% (§4.2). If it
fails, those B trials read "not measurable" and do not count as separated.

### H2 — persistent compensation

> After the dynamics transient decays, controller-compensation evidence in T3
> (10–15 s) preserves information about physical degradation that is absent
> in the telemetry-only case.

**Operationalization.** As H1, with the W_CTRL witness in T3.

PREDICTED: SUPPORTED. The expected compensation exceeds the threshold by at
least 24× at every level.

### H3 — temporal complementarity

> Using evidence according to its preregistered temporal validity provides
> greater resolving power than using the matched RPM symptom alone.

The comparison "more than the RPM symptom alone" is already the primary
endpoint, because V0 resolves nothing by construction. H3 is therefore
tightened to test the **temporal** part of the claim.

**SUPPORTED iff all three hold:**

- **(a) Combining windows loses nothing.** PRR(V3) ≥ max(PRR(V1),
  PRR(V2)). V3 is each category in its own window; V1 and V2 are each
  single-window category alone.
- **(b) Validity windows matter.** The same dynamics evidence read in T3,
  outside its valid window (V4_INVALID_WINDOW, the negative control), makes
  the architecture WRONG on case A. The WRONG rate among A trials has a
  cluster lower bound above 0.5, with Holm-adjusted p < 0.05.
- **(c) Correct use is safe.** V3 produces no WRONG.

Component (b) is predicted by apparatus finding 3: D_T3 = 0.0001–0.0023,
far below θ_dyn = 0.0246. It is kept as the **manipulation check of temporal
validity**, the exception the request allows. What it confirms is that the
frozen architecture turns out-of-window evidence into a wrong elimination,
which is why the windows are part of the method.

### H4 — generalization across degradation

> The resolving effect is not confined to a single actuator-effectiveness
> setting within the preregistered controllable regime.

**Operationalization.** For each of the five levels, the per-level PRR at
C3/V3 is tested against 0.5. Each level has 11 pairs, one per condition. The
five tests are Holm-adjusted inside the secondary family. H4 is SUPPORTED
iff **at least 3 of the 5 levels** pass.

### H5 — safe ambiguity

> When the available evidence does not uniquely distinguish the modelled
> causes, the assurance system remains AMBIGUOUS rather than emitting an
> unsupported UNIQUE attribution.

**SUPPORTED iff all three hold:**

1. Under V0, every symptomatic trial is AMBIGUOUS_CORRECT at C1 and at C3.
   This part is an implementation integrity check, because it follows from
   the spec.
2. **No valid configuration** yields WRONG on any A or B trial. The valid
   configurations are V0, V1, V2 and V3 at C1 and C3. V4 is excluded because
   it is the deliberate invalid-window control.
3. No nominal trial N receives a SUPPORTED cause in any valid configuration.

Parts 2 and 3 are empirical. A witness that cannot affirm (gate not met,
motion opposite to the loss axis, window not measurable) must leave the
verdict AMBIGUOUS, not unique.

### H6 — no wrong-cause improvement

> Any increase in UNIQUE classifications is not acceptable if it comes from
> increased WRONG attribution.

**Operationalization.** The WRONG count of A and B trials under V3 must be
≤ the count under V0 at **both** C1 and C3. V0's count is 0 by construction,
so this means **zero WRONG under V3 at C1 and C3**.

H6 is a zero-tolerance criterion, not a statistical test. The counts of
UNIQUE_CORRECT under V3 and V0 are reported beside it.

## 4. Design

### 4.1 Root causes and scope

| label | construction | v2 hypothesis |
|---|---|---|
| NOMINAL | NB flight, benign onset event, unmodified | none expected |
| PHYSICAL_ACTUATOR_DEGRADATION | A flight, `SIH_MOT_EFF1` = η at onset | ACTUATION/mechanical |
| RPM_TELEMETRY_CORRUPTION | NB flight, motor-0 RPM corrupted offline (§5) | SENSOR/response_sensor |

Only this pair is modelled; it is the smallest matched set that answers the
question. The other Set B causes (command path, drive/ESC, jammed shaft,
dead speed sensor) are out of scope for XSYS-001 and are later matched-set
expansions. The fault is always on motor 0 (SIH Motor1, CSIA `motor_0`);
motors 1–3 are analysed too, and any localization on them is reported as a
spurious symptom (§11).

### 4.2 Actuator-effectiveness set

**FROZEN: η ∈ {1.00 (NB), 0.95, 0.85, 0.75, 0.65, 0.55}.** This is the set
the request proposed. It was checked against the four criteria, not adopted
blindly, and is kept unchanged. The table uses apparatus data only.

| η | controllable for the analysis window (to +15 s) | above loss of control | meaningful but nontrivial | distinct from neighbours |
|---|---|---|---|---|
| 1.00 | nominal hover (APPARATUS) | yes | the null: NB source of B and N | — |
| 0.95 | yes: interpolated between measured 1.00 and 0.90, where tilt peaked at 1.5° | yes | PREDICTED peak body rate ≈ 0.075 rad/s, 4× the nominal peak; the **hardest** level (see note) | L_T1 0.039 vs 0.116 |
| 0.85 | yes: between 0.9 and 0.8 (tilt ≤ 3.3°) | yes | L_T1 ≈ 0.116, κ ≈ 1.18 | yes |
| 0.75 | yes: between 0.8 and 0.7 (tilt ≤ 5.6°) | yes | L_T1 ≈ 0.194, κ ≈ 1.33 | yes |
| 0.65 | yes: between 0.7 and 0.6 (tilt ≤ 8.2°) | yes | L_T1 ≈ 0.272, κ ≈ 1.54 | yes |
| 0.55 | yes: steady motor-0 command 0.489/0.55 = 0.889 < 1. Peak interpolated between 0.888 (η 0.6) and 1.000 (η 0.5), so it may touch the limit briefly | yes: margin 0.05 above η = 0.5, where saturation lasted 90% of compensation | L_T1 ≈ 0.349, κ ≈ 1.82 | yes |

**PREDICTED evidence and gate margins per level.** These come from the
apparatus relations L_T1 ≈ 0.776 (1 − η), L_T3 = 1 − η, D_T1 ≈ s_dyn L_T1
and C_T3 = 1/η − 1 (fit residual of D_T1: 0.0115 rms).

| η | L_T1 | D_T1 in A / θ_dyn | DYN gate s_dyn L_T1 / 2θ_dyn | C_T3 in A / θ_ctrl | CTRL gate (1/(1−L_T3) − 1) / 2θ_ctrl |
|---|---|---|---|---|---|
| 0.95 | 0.039 | 2.1 | **1.045** | 24 | 12 |
| 0.85 | 0.116 | 6.3 | 3.1 | 80 | 40 |
| 0.75 | 0.194 | 10.5 | 5.2 | 152 | 76 |
| 0.65 | 0.272 | 14.7 | 7.3 | 245 | 123 |
| 0.55 | 0.349 | 18.8 | 9.4 | 373 | 186 |

**Note on 0.95.** It is the level where the frozen dynamics gate is closest
to its limit. It was not chosen for that reason: it is the request's
proposed weakest level, and the apparatus shows it is detectable, since its
local deficit is 80× δ_rpm. The margin is disclosed here, before any data,
so that a failure of H1 at 0.95 cannot be explained away afterwards. The
primary endpoint does not depend on this gate, because the CTRL witness
alone resolves the pair with a 12× margin.

**Why these levels are none of the apparatus levels.** The confirmatory
levels interleave the calibration levels 0.9 … 0.5. The thresholds and s_dyn
were therefore never fitted at any level they are applied to.

### 4.3 Nuisance variation and the independent unit

**PILOT** (`research/xsys_confirmatory_001/validation/PILOT_ANALYSIS.json`,
nominal flights only):

- **Q1 — heading.** `SIH_LOC_YAW0` sets the true heading exactly at boot. It
  holds within 0.9° through hover at 15°, 105°, 195° and 285°.
- **Q2 — noise realization.** Heading does **not** select the noise
  realization.
  - Flights at different headings shared between 2% and 100% of their
    pre-arm accelerometer samples; 105° and 285° were bit-identical.
  - Repeated flights at the same heading shared 60–100%.
  - The realization is a thread-interleaving family of one seeded stream
    (`srand(1234)`), locked to simulated time.
  - The pilot also shows the realization branches between flights without
    any change of configuration: event and no-event flights diverged at
    0.3–10 s.
- **Q3 — benign onset event.** Setting `SDLOG_DIRS_MAX` to 8 publishes
  exactly one `parameter_update`, and t0 lands one step after it in all four
  flights. The same value 7 is already the default and publishes none. That
  is why the frozen benign value is 8.
- **Q4 — null excursions.** Over 1476 overlapping hover windows, the largest
  null excursion stayed below every frozen threshold:

  | statistic | largest null | frozen threshold | threshold / largest null |
  |---|---|---|---|
  | \|L_T1\| | 2.9e-4 | δ_rpm | 1.6× |
  | \|D_T1\| | 0.0139 | θ_dyn | 1.8× |
  | \|C_T3\| | 7.7e-4 | θ_ctrl | 2.9× |

**FROZEN nuisance design.**

- **Conditions.** Eleven nuisance conditions j = 0 … 10.
- **Heading.** Heading_j = 360 j / 11 degrees, to 0.001°: 0.000, 32.727, …,
  327.273.
- **Onset phase.** onset_j = 30.0 s + 0.5 s × rank_j, where rank_j is a
  permutation of 0 … 10 obtained by sorting j on
  SHA-256("XSYS-001/2026-09-26/offset/" + j).

Heading changes the initial conditions (world-frame attitude and the
magnetometer context) while leaving the fault's meaning unchanged. Because
it does not decorrelate the noise, the onset phase moves the fault to a
different point of whatever noise stream is realized. The 0.5 s step makes
the T1 windows of all conditions disjoint in simulated time.

All onsets (30.0–35.0 s) and flight ends (≤ 51 s) lie inside the hover span
the apparatus characterized: its sweep flights ran to 50 s, and its
thresholds came from hover windows from 27 s.

**The independent unit is the nuisance condition**, not the trial and not
the 250 Hz sample. Within a condition, the five A flights and the NB flight
share heading and onset phase. The five B trials also all reuse the one NB
flight. No identical rerun is ever counted: every flight in the matrix has a
distinct (condition, level) pair.

**How many conditions.** Eleven is the smallest count for which an
observed PRR of 0.80 still supports H_PRIMARY under the cluster-conservative
bound (`research/xsys_confirmatory_001/prereg/POWER.json`). The requirement
was fixed before the computation. A PRR of 0.80 is what remains when one
whole level of the five fails and the other four succeed. The primary result
therefore cannot hinge on any single level.

**No wind.** The first experiment stays a clean matched set:

- The apparatus never flew wind, so every threshold would have to be
  re-characterized.
- Wind adds an unmodelled disturbance to exactly the two categories under
  test, W_DYN and W_CTRL.
- The ecological gain does not justify a larger matrix before the clean
  question is answered.

Wind is a candidate for a later, separately preregistered expansion.

### 4.4 Flights, trials and pairs

| unit | per condition | total |
|---|---|---|
| A flights (one per η) | 5 | 55 |
| NB flights (η = 1.00, benign event) | 1 | 11 |
| **flights** | 6 | **66** |
| A analysis trials | 5 | 55 |
| B analysis trials (NB + matched A of the same level) | 5 | 55 |
| N analysis trials (NB unmodified) | 1 | 11 |
| **analysis trials** | 11 | **121** |
| **matched pairs** (A, B) | 5 | **55** |

**Flight profile (FROZEN, from the apparatus).**

- PX4 SIH quadcopter at `547e2ca` with the SIH effectiveness patch.
- Lockstep, `PX4_SIM_SPEED_FACTOR` 1.
- Logger topics at interval 0 from
  `research/px4_actuator_effectiveness/config/logger_topics.txt`.
- Schedule: arm at 10 s, take off to 10 m, one parameter change at onset_j,
  end at onset_j + 16 s.

### 4.5 Trial matrix and execution order

`research/xsys_confirmatory_001/prereg/generate_matrix.py` generated the
complete matrix before anything was run. Its output files:

| file | rows | SHA-256 |
|---|---|---|
| `research/xsys_confirmatory_001/prereg/FLIGHT_MATRIX.csv` | 66 | `34ce235f8c9342a8260fd0df80c46b750abb2ffbd8819ae2c3e70290203e6864` |
| `research/xsys_confirmatory_001/prereg/ANALYSIS_MATRIX.csv` | 121 | `611e914262d298c1e4ef38f1228f9162dd1a349b2503c4e1013fc673d26d1adb` |
| `research/xsys_confirmatory_001/prereg/EXECUTION_ORDER.csv` | 66 | `9b26fd4a802ace2ed7f1de15bd5ffb1d88d3fc881f31d333c19c24024cd2f8d6` |

**Flight matrix.** Every row has:

- the flight id (`XS1-Cjj-NB`, `XS1-Cjj-A-E095` …);
- the condition (A/NB), η, the onset parameter and value;
- the nuisance id, heading and onset offset;
- arm, onset and end times;
- the expected absolute T0–T3 windows;
- the logger configuration.

**Analysis matrix.** Every row has the analysis id, the kind (A/B/N), the
source flight, the matched A flight for B, the pair id (`XS1-Cjj-P-E0xx`),
η and the nuisance id.

**Execution order.**

- **Algorithm.** All 66 flight ids are sorted on
  SHA-256("XSYS-001/2026-09-26/order/" + flight_id). The seed is the string
  "XSYS-001/2026-09-26".
- **Result.** The order interleaves levels and conditions:
  - it starts 0.85, 0.55, 0.65, 0.85, 0.75, 0.65, 0.95 …;
  - it runs neither from easiest to hardest nor by condition.
- **Enforcement.** The executor flies this order and no other. The guard
  test re-derives the order and the matrices byte for byte.

## 5. Matched-pair construction (case B)

FROZEN, implemented only in stage 0
(`research/xsys_confirmatory_001/pipeline/stage0_prepare.py`, `build_b`).

| question | answer |
|---|---|
| **channel modified** | motor 0's `esc_rpm` in `esc_status` (SIH Motor1 = CSIA `motor_0`), in the **analysis copy only**. Motors 1–3 and every other channel are byte-identical to the NB flight; a stage-0 check verifies this per trial |
| **use of the A trajectory** | only its RPM **ratio** ρ_A(k) = rpm_obs / rpm_healthy, where rpm_healthy is what a healthy rotor would show for A's own command. A's absolute RPM, its command and its dynamics are never copied |
| **the rule** | rpm_B(k) = round(rpm_expB(k) · ρ_A(k)) for t_rel ≥ 0, where rpm_expB is the healthy-rotor RPM for **B's own** command. Before t0 nothing changes. B's ratio, and so its local symptom L_W, equals A's; stage 0 requires \|ρ_B − ρ_A\| ≤ 5e-4 at every step |
| **timestamp alignment** | by step index from each flight's own t0, both on the 4 ms SIH grid. Each flight's t0 comes from its own logged event (§6) |
| **interpolation** | none. A step missing in A is held from A's previous step (zero-order hold) |
| **missing samples** | a step missing in NB is simply absent in B. Coverage limits are part of the logging checks (§13) |
| **measurement noise** | SIH RPM telemetry carries no noise beyond integer rounding. The corrupted value is rounded to an integer like the original. The rest of B's noise is NB's own |
| **truth retention** | NB's true motor-0 RPM stays in the stage-0 QC record (T3 mean per B trial) and in the NB log, which B never overwrites. PX4's telemetry-failure injection is **not** used; it would destroy that record |
| **label leakage** | (i) B's corrupted RPM is computed from A's ratio, so the local channel carries no label information. (ii) B and N trials built from one NB flight share identical non-RPM signals, so a human could group them. This is why stage 1 is fully automatic and frozen: no analyst choice exists for the grouping to influence. (iii) Opaque ids are salted with a random value that only stage 0 and stage 2 see. (iv) Stage 1 receives no parameters, file names or events |

## 6. Time zero

**FROZEN definition.** t0 is the first `esc_status` step strictly after the
`parameter_update` stamp caused by the trial's single onset parameter
change:

- in A flights, `SIH_MOT_EFF1`;
- in NB flights, the benign `SDLOG_DIRS_MAX` change, so A and B share one
  procedure.

**Why this event.** SIH reloads parameters at the start of a step, before the
rotor update, so at t0 the new effectiveness is already in the rotor
equation. Wall-clock time, command-send time and MAVLink receipt time are
never used.

**Maximum onset uncertainty.**

- APPARATUS: the physical onset is **exactly one step (4 ms)** after the
  `parameter_update` stamp in 24 of 24 sweep trials with a change.
- PILOT: t0 − update = 4 ms in 4 of 4 flights.
- The stated bound is **one SIH step, 4 ms**.
- A trial with t0 − update > 8 ms (two steps) fails check
  Q_onset_uncertainty and is excluded.

## 7. Evidence categories and temporal validity

All statistics are defined once, in
`research/xsys_confirmatory_001/pipeline/xsys_features.py`. The calibration,
stage 0 and stage 1 all import that file.

### 7.1 Temporal regions (FROZEN, from apparatus data only)

Windows are half-open, in seconds of t_rel = t − t0.

| region | window | chosen from |
|---|---|---|
| T0 pre-fault baseline | [−5, 0) | 5 s of settled hover precede every onset; the baseline for D and C |
| T1 early physical transient | [0, 0.2) | onset → peak body rate took 0.148–0.176 s at η 0.9–0.5 (0.188 s at 0.4). 200 ms contains the peak at every controllable level without reaching into T2 |
| T2 compensation transition | [0.2, 2.0) | descriptive only; no decision uses it. Settle times were noise-floor limited (apparatus revision R2) |
| T3 post-compensation | [10, 15) | the fixed steady window of apparatus revision R2. The start is fixed at 10 s, not detected. The end at 15 s leaves 1 s before the flight ends |

These boundaries will not move. The request's example ("240 ms looks better")
is exactly what the freeze exists to prevent. Any other window is a
POST-HOC / EXPLORATORY analysis and is reported separately (§17).

### 7.2 Definitions

For motor m, with the command SIH received c_sim, the allocator command
c_alloc and the measured body rates ω from `sensor_combined`:

**W_RPM — the shared local symptom.**

- ρ(k) = rpm_obs(k) / rpm_healthy(k). rpm_healthy is the SIH first-order lag
  (α = 0.08) run on c_sim from the observed state at the first sample.
- L_W = mean over W of (1 − ρ²), the implied fractional thrust deficit.
- **Valid in** T1 (at checkpoint C1) and T3 (at C3).
- **Not measurable** if the window has no samples or the mean command is
  below 0.15 (v2's `min_command`).

**W_DYN — physical dynamics.**

- D_T1 = mean over T1 of (ω_xy − mean_T0 ω_xy) · e.
- e = normalize(p_y, −p_x) is the roll/pitch direction a thrust **loss** on
  the rotor at (p_x, p_y) produces. The rotor geometry comes from
  `CA_ROTORn_PX/PY`.
- One scalar, the smallest robust definition. Body rate is what the gyro
  measures, and its mean deviation over T1 already integrates the angular
  acceleration. Angular acceleration separated more strongly in the
  apparatus (15–76× against 7–42× for body rate), but it would have to be
  obtained by differentiating the gyro, which amplifies noise. Specific
  force separated least (1.4–6.5×).
- **Valid in T1 only.**

**W_CTRL — controller compensation.**

- κ = c_alloc,m / mean of c_alloc over the other three motors.
- C_T3 = mean_T3 κ − mean_T0 κ.
- One scalar. Under a compensated loss with effectiveness η, κ → 1/η. In
  the apparatus, C_T3 matched 1/η − 1 within 0.0015 at η 0.9–0.5.
- **Valid in T3 only.**

### 7.3 Witnesses: from statistic to three-valued evidence

Each statistic becomes True / False / None, and the value drives a v2
`EvidenceRecord`. None means "not measurable": the record is NOT_APPLICABLE
and the predicate is None, **never False**.

| witness | True | False | None |
|---|---|---|---|
| LOCAL_RPM_DEFICIT (W) | L_W ≥ δ_rpm | L_W < δ_rpm | not measurable |
| DYN_T1_NOMINAL | \|D_T1\| < θ_dyn **and** s_dyn L_T1 ≥ 2 θ_dyn | D_T1 ≥ θ_dyn (motion along the loss axis) | D_T1 ≤ −θ_dyn (motion opposite the loss axis: explained by neither cause), the gate not met, or not measurable |
| CTRL_T3_NOMINAL | \|C_T3\| < θ_ctrl **and** 1/(1 − L_T3) − 1 ≥ 2 θ_ctrl | C_T3 ≥ θ_ctrl | C_T3 ≤ −θ_ctrl, the gate not met, or not measurable |

**The gates.** A witness may affirm "nominal" only if the local symptom
implies a response that a genuine loss would make detectable, at twice the
threshold. Without the gates, a tiny symptom with no measurable consequence
would be read as proof of telemetry corruption.

**Calibration (FROZEN).** Values are in
`research/xsys_confirmatory_001/calibration/CALIBRATION.json`, computed by
`research/xsys_confirmatory_001/calibration/calibrate_from_apparatus.py`
from the apparatus logs only. The script checks each input's SHA-256 against
the apparatus `SHA256SUMS`.

**Rule, fixed before any value was computed:** every threshold = 2 × the
largest |value| of the same statistic under the null, over pseudo-onsets
every 0.5 s in the hover of the 32 nominal flights and 3 η = 1.00 controls.

| value | frozen | null max | null windows |
|---|---|---|---|
| δ_rpm | 4.7135e-4 | 2.357e-4 (L_T1) | 1267 |
| θ_dyn | 0.024564 | 0.012282 | 1267 |
| θ_ctrl | 0.0021945 | 0.0010972 | 217 |
| s_dyn | 1.32346 | LS slope through the origin of D_T1 on L_T1, 15 apparatus fault trials, η 0.9–0.5; used only in the gate, never as a decision threshold | — |

### 7.4 W_EST — exploratory only

The maxima of |EKF aiding test ratio| and |hover-thrust test ratio| in T1
and T2 are computed and reported, aligned on `timestamp_sample`. They enter
**no** decision rule, variant or endpoint.

Reasons:

- the apparatus showed no fault-attributable response in the navigation
  EKF;
- the hover-thrust response appears only at η ≤ 0.6 and lags by 36–212 ms.

Any statement about W_EST from the confirmatory data is EXPLORATORY.

## 8. Mapping into CSIA v2 without modifying it

`research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py` imports
`csia/v2/localization.py` and `csia/v2/evidence.py` unchanged, and both are
in the freeze manifest. v2's `localize()` is a pure function of the spec,
records and predicates it is given; nothing is registered with v2.

The research spec mirrors v2's frozen COMMAND_NO_RESPONSE pair in
`csia/v2/signatures.py`, with two substitutions the platform forces.

**Substitution 1: the local symptom.** v2's STALL_SIGNATURE needs a current
channel, and SIH has none. It is replaced by the local RPM deficit.

**Substitution 2: the independent physical channel.** v2's
PHYSICAL_RESPONSE_NOMINAL becomes two temporally conditioned channels, one
per window.

| hypothesis | confirmed by (any) | refuted by (any True) |
|---|---|---|
| ACTUATION/mechanical | LOCAL_RPM_DEFICIT | LOCAL_RPM_DEFICIT_FALSE, DYN_T1_NOMINAL, CTRL_T3_NOMINAL |
| SENSOR/response_sensor | LOCAL_RPM_DEFICIT, DYN_T1_NOMINAL, CTRL_T3_NOMINAL | DYN_T1_NOMINAL_FALSE, CTRL_T3_NOMINAL_FALSE |

The resulting verdicts for motor 0 with the local symptom present were
checked exhaustively. This is the complete truth table:

| DYN \ CTRL | True | False | None |
|---|---|---|---|
| **True** | SUPPORTED sensor | UNSUPPORTED (both rejected) | SUPPORTED sensor |
| **False** | UNSUPPORTED (both rejected) | SUPPORTED mechanical | SUPPORTED mechanical |
| **None** | SUPPORTED sensor | SUPPORTED mechanical | AMBIGUOUS {both} |

Without the local symptom, no localization is made (NO_EVIDENCE).

## 9. Outcome taxonomy (FROZEN)

**Symptomatic trials (A, B).** The outcome is taken from the v2 localization
of `motor_0`, with c the true cause.

| v2 result | outcome |
|---|---|
| SUPPORTED, supported == (c) | **UNIQUE_CORRECT** |
| SUPPORTED, another cause | **WRONG** |
| AMBIGUOUS, c not rejected | **AMBIGUOUS_CORRECT** |
| UNSUPPORTED, c not rejected | **UNSUPPORTED** (unreachable in this spec; kept for completeness) |
| any verdict with c rejected | **WRONG** |
| no localization of `motor_0` | **NO_EVIDENCE** |

**Why UNSUPPORTED is scored WRONG here.** In this spec the local symptom
confirms both hypotheses whenever `motor_0` is localized. v2 UNSUPPORTED can
therefore arise only from conflicting evidence that **eliminates both
causes**, including the true one. Eliminating the true cause is a false
claim, so it is scored WRONG. The raw v2 verdict of every trial is reported
beside the taxonomy, so every WRONG can be traced to its verdict.

AMBIGUOUS is never WRONG, and UNIQUE counts only when correct.

**Nominal trials (N).**

| result | outcome |
|---|---|
| no localization on any motor | CORRECT_NO_EVIDENCE |
| a localization without a SUPPORTED cause | FALSE_ALARM |
| any SUPPORTED cause on any motor | WRONG |

## 10. Variants and checkpoints

Stage 1 evaluates every trial under five variants at two checkpoints.

| variant | evidence given to v2 | C1 (t0 + 0.2 s; RPM from T1) | C3 (t0 + 15 s; RPM from T3) |
|---|---|---|---|
| V0_LOCAL_ONLY | RPM deficit; dynamics and compensation withheld | yes | yes |
| V1_DYN_ONLY | + DYN from T1 | yes | yes |
| V2_CTRL_ONLY | + CTRL from T3 | — (T3 not yet observed) | yes |
| **V3_TEMPORAL** | + DYN from T1 + CTRL from T3 | yes (DYN only) | **yes (PRIMARY)** |
| V4_INVALID_WINDOW | + DYN computed over T3, outside its valid window (negative control) | — | yes |

## 11. Endpoints

**Primary (one).** PRR at C3 under V3 (§3), with its decision rule.

- **Denominator:** every eligible pair, meaning both trials passed stage 0.
- A pair that is not AMBIGUOUS under V0 counts as **not** resolved. The
  number of V0-ambiguous pairs is reported.

**Secondary.** H1, H2, H3, H4, H5 and H6 as defined in §3.

**Descriptive** (no decision attached):

- the PRR under every variant at C3;
- outcome tallies per variant, checkpoint and kind;
- raw v2 verdict tallies;
- the pair-level interval that assumes independence (§12);
- latencies (§11.1);
- spurious localizations on motors 1–3 under C3/V3;
- W_EST.

### 11.1 Latency definitions (kept separate)

| latency | definition here | status |
|---|---|---|
| **detection** | from t0 to the first step with 1 − ρ² ≥ δ_rpm on motor 0 | secondary, measured per trial |
| **isolation** | until the true cause is the only survivor | collapses into certification in this spec (the local symptom confirms both causes, so elimination implies support); measured at checkpoint resolution |
| **certification** | until the architecture's evidence requirements justify the attribution: 0.2 s if UNIQUE_CORRECT at C1/V3, 15 s if first at C3/V3, none otherwise | secondary, checkpoint resolution only. The time is set by the evidence windows (evidence accumulation), not by computation |
| **action** | until a downstream action could be authorized | **not measurable**: this experiment has no downstream action |
| **computational** | stage-1 wall time per trial, offline, on the analysis host | secondary; not an onboard figure and never reported as a latency of the fault response |

## 12. Statistical plan

**Unit.** The nuisance condition: 11 conditions, each holding 5 pairs. The
250 Hz samples only form the per-window statistics. No test treats samples,
or pairs within a condition, as independent.

**Primary statistic.** PRR, pooled over eligible pairs.

**Interval.** The cluster-conservative one-sided 95% Clopper–Pearson bound:

- lower95 = BetaInv(0.05; r n, n − r n + 1), where r is the PRR and n the
  number of conditions with at least one eligible pair.
- It treats all pairs of a condition as one perfectly correlated
  observation, so it is valid however strong the within-condition
  correlation is.

**Test.** One-sided, against 0.5: p = I_0.5(r n, n − r n + 1). This equals
the exact binomial tail when r n is an integer. α = 0.05 one-sided. The
primary decision uses the bound; the bound and the test agree.

**Multiplicity.**

- The primary hypothesis is tested alone at α = 0.05.
- The eight secondary tests form **one Holm family** at 0.05: H1, H2, H3(b),
  and H4 at each of the five levels. A level whose pairs were all excluded
  enters the family with p = 1.
- **Gatekeeping (fixed sequence).** Secondary results are interpreted as
  confirmatory **only if H_PRIMARY is SUPPORTED**. Otherwise they are
  reported as DESCRIPTIVE ONLY. The label is written into the results file.
- H5 and H6 are zero-tolerance criteria and involve no test.

**Sensitivity (reported, never decisive).** The ordinary pair-level
Clopper–Pearson bound. It is labelled ASSUMES INDEPENDENCE.

**Power** (`research/xsys_confirmatory_001/prereg/POWER.json`, no data used):

| true per-pair resolution probability | power, pairs fully correlated within a condition | power, pairs independent |
|---|---|---|
| 1.00 | 1.000 | 1.000 |
| 0.95 | 0.985 | 1.000 |
| 0.90 | 0.910 | 0.993 |
| 0.85 | 0.779 | 0.887 |
| 0.80 | 0.617 | 0.580 |

With 11 conditions, the smallest observed PRR that supports H_PRIMARY is
0.80 (44 of 55 pairs). The lower bound at PRR = 1 is 0.762.

For H4, a level passes the worst-case Holm step with 10 of 11 pairs.

**Excluded pairs.** They leave the denominator and are listed in the results,
with the reason inherited from stage 0. They are never replaced or re-flown
(§14).

## 13. Manipulation and logging checks (FROZEN tolerances)

Computed in stage 0 from the log and the ground truth, per flight and per
analysis trial. A failed check excludes the trial and records why (§14).

**Logging and integrity (every flight).**

| check | rule |
|---|---|
| Q_log_readable | ULog opens; the onset event is found |
| Q_dropouts | logger dropouts = 0 |
| Q_span_covered | the ULog covers t_rel ∈ [−5, 15) |
| Q_max_gap | no gap longer than 2 steps on the step grid |
| Q_missing_frac | ≤ 0.5% of steps missing in the span |
| Q_onset_uncertainty | t0 − parameter_update ≤ 8 ms |
| Q_build_hash | the trial used the campaign's verified PX4 binary |
| Q_logger_config_hash | the logger topics file equals the frozen one |
| Q_manifest | the trial record carries this freeze manifest's SHA-256 |
| Q_heading, Q_onset_value | the flown heading and onset value equal the matrix row |
| MC_heading_applied | the true heading over T0 is within 5° of the matrix heading |
| MC_eta_nominal_before_onset | η identified from the rotor equation over T0 is 1 ± 0.002 |

**Case A.**

| check | rule |
|---|---|
| MC_onset_event | `SIH_MOT_EFF1` changed to the matrix η |
| MC_eta_reached | η identified from the rotor equation over [0.2, 15) s is within 0.01 of the matrix η |
| MC_command_independent | the logged command drives the rotor equation with the matrix η, rms residual ≤ 1e-3: the command SIH received is the controller's, untouched by the injection |
| MC_controllable | from t0 on: truth altitude ≥ 5 m; truth tilt ≤ 30°; mean \|true yaw rate\| over T3 ≤ 0.5 rad/s |

**NB flights (source of B and N).**

| check | rule |
|---|---|
| MC_onset_event | the benign `SDLOG_DIRS_MAX` change occurred |
| MC_rotor_nominal | η identified after onset is 1 ± 0.002 |
| MC_dynamics_nominal | from t0 on: truth tilt ≤ 5°; altitude within 1 m of its T0 mean and ≥ 5 m |

**B construction (per B trial).**

| check | rule |
|---|---|
| MC_B_ratio_matched | \|ρ_B − ρ_A\| ≤ 5e-4 at every post-onset step |
| MC_B_only_motor0_rpm_changed | every other channel, and motors 1–3, byte-identical to NB |

**Dependence.** A trial depends on its source flight; a B trial also depends
on its matched A flight. If either is excluded, the trial is excluded with
the reason "depends on excluded flight".

## 14. Exclusion, retry and stopping rules

**Legitimate exclusions** are exactly the failed checks of §13 and the
technical failures below. They cover:

- logger dropout;
- failed arming or takeoff, which leaves no onset or no span;
- an injection that did not occur or did not reach η;
- ground contact or loss of control before the analysis window ends;
- a corrupted or incomplete ULog;
- time-zero uncertainty beyond two steps.

**Never a reason to exclude:**

- CSIA was wrong;
- the trial is an outlier;
- the effect is weak;
- a hypothesis failed;
- a trial lowers significance.

No stage-0 check reads a stage-1 or stage-2 output, and stage 0 runs before
stage 1 exists.

**Records.** Every excluded flight and trial stays in the stage-0 QC record
and in the results. Each entry has:

- the trial id;
- the reason (the names of the failed checks);
- the evidence (every check value);
- the decision.

Excluded pairs are listed by id.

**Retry.** A technical failure is a driver exit ≠ 0 or no ULog. The executor
retries it once, with the identical configuration, and logs both attempts.
A flight that flew but failed a check is **not** re-flown.

**Stopping.**

- **N is fixed:** 66 flights, flown in the frozen order, once each.
- There is no interim analysis. Stage 0 refuses to run until every flight
  has a ULog or two failed attempts.
- Nothing in the executor reads an outcome, so it cannot stop on
  significance or continue because significance was missed.

**Apparatus-integrity termination** (separate from results). The campaign
stops if:

- three consecutive technical failures occur;
- the source verification fails: the PX4 tree is not `547e2ca` plus exactly
  the frozen patch;
- any frozen file differs from the manifest;
- the campaign's binary changes (CAMPAIGN.json mismatch).

**After termination.** The campaign may resume under the same manifest after
a purely technical repair. If it cannot be completed, stage 0 runs with
`--declare-campaign-terminated "<reason>"`. Every unflown flight is then
excluded with that reason, and the primary analysis runs on what exists.

## 15. Blinding — two-stage workflow (implemented)

| stage | sees | produces |
|---|---|---|
| **0 custodian** (`research/xsys_confirmatory_001/pipeline/stage0_prepare.py`) | raw ULogs, matrix, labels, truth | blinded inputs (on-board signals only, opaque salted ids), the KEY, the QC record, case B |
| **1 blinded evidence** (`research/xsys_confirmatory_001/pipeline/stage1_evidence.py`) | blinded inputs, calibration | witnesses and v2 verdicts per opaque id. Output **sealed** with SHA-256 before any label is joined |
| **2 scoring** (`research/xsys_confirmatory_001/pipeline/stage2_score.py`) | the seal, the stage-1 output, KEY, QC, analysis matrix | outcomes, endpoints, decisions. **Refuses** to score if the seal does not match |

**What the blinding protects.** Stage 1 never opens the key or the QC
record. The guard test checks that stage 1 and every module it imports name
no label source.

**What it does not protect.** Grouping by shared NB signals (§5) remains
possible. Because stage 1 is automatic and frozen, no analyst decision exists
for that grouping to influence.

**Checks tied to the manifest.**

- Stages 0, 1 and 2 re-verify the freeze manifest in confirmatory mode.
- Stage 2 requires stage 0 and stage 1 to have run under the same manifest.

## 16. Validation performed before the freeze (NOT CONFIRMATORY)

**Dry run on apparatus data** (`research/xsys_confirmatory_001/validation/run_dry_run.sh`;
summary in `research/xsys_confirmatory_001/validation/DRY_RUN_RESULTS.json`).

- **Data.** The apparatus sweep at η 0.9–0.5 × 3 repeats plus the 3 η = 1.00
  controls: 18 flights, 33 analysis trials, 15 pairs.
- **Label.** The thresholds were calibrated on these data, so the result is
  **IN-SAMPLE FOR THE CALIBRATION**. It tests the pipeline, not a
  hypothesis.

Outcomes:

- **Stage 0.**
  - All 18 flights and 33 trials passed.
  - Manipulation-check values: η identified within 1.3e-5 of the set value;
    rotor-equation residual ≤ 5.7e-5; B ratio match ≤ 7.2e-5; heading error
    ≤ 0.75°; t0 − update = 4 ms everywhere.
- **Outcomes at C3.**
  - V0: all 30 symptomatic trials AMBIGUOUS_CORRECT.
  - V1, V2 and V3: all 30 UNIQUE_CORRECT.
  - V4: all 15 A trials WRONG (v2 SUPPORTED sensor); B correct.
  - N trials: CORRECT_NO_EVIDENCE.
- **At C1.** V3 was UNIQUE_CORRECT on all 30, so the certification latency
  was 0.2 s. The detection latency was 0 s: the first step after t0.
- **The rule withholds support on too few units.** H_PRIMARY came out NOT
  SUPPORTED although every pair was resolved: with 3 conditions, the lower
  bound is 0.368. This shows the conservative unit working, not a finding.
- **Exclusion path.** Withholding one A flight excluded it (reason
  recorded), its two dependent trials and its pair (listed by id). The
  denominator fell from 15 to 14.
- **Seal path.** One changed byte in the stage-1 output made stage 2 refuse
  to score.

**Design changes made after the first dry run.** The dry run was repeated
after each change. None of these changes altered a statistic, threshold,
gate, window, level, variant or the primary rule:

- **Stage 2 counts pairs from the frozen matrix.** An excluded pair can no
  longer vanish from the count.
- **The executor verifies the PX4 source, not a binary hash.** A rebuilt
  binary differs byte for byte.
- **The secondary tests became one Holm family of eight, with
  gatekeeping.** Previously there were two families and no gate.
- **H5 and H6 were broadened.** H5 now covers every valid configuration at
  both checkpoints, and H6 covers both checkpoints.
- **Raw v2 verdicts and the V0-ambiguous pair count are reported.**
- **The heading check, the campaign-completeness gate and manifest
  verification in every stage were added.**
- **The condition count went from 12 to 11,** after the exact power
  computation replaced an estimate.

The dry-run outcomes were uniform throughout: every valid variant resolved
every pair, and V4 was WRONG on every A trial. No change could have been
chosen to favour an outcome.

**Pilot.** §4.3.

**Executor.** The dry-run mode verifies the manifest, the PX4 source and
the binary, then prints the 66 commands in order without flying. Its
post-freeze result is recorded in
`research/xsys_confirmatory_001/validation/POST_FREEZE_CHECK.json`, which
is not part of the freeze.

## 17. After the freeze: what may and may not change

**May not change** without a new, separately frozen preregistration, whose
results are reported under its own id:

- any hypothesis, rule, threshold, gate, window, level, condition, seed or
  order;
- the taxonomy, a tolerance, or the matrix;
- any frozen script;
- the PX4 source or patch;
- the logger configuration;
- the two v2 modules.

**Post-hoc analyses** (other windows, statistics, thresholds or W_EST rules)
are allowed only as extra sections labelled **POST-HOC / EXPLORATORY**. They
never replace a preregistered result, and a preregistered result that fails
is reported as failed.

**A defect found after data exist.** It is reported, not silently fixed. A
corrected analysis may be added as POST-HOC beside the preregistered one.

## 18. Procedure for the confirmatory run (future session, not authorized yet)

1. `python3 research/xsys_confirmatory_001/prereg/freeze.py verify` must
   pass. Separately, `tests/test_xsys_001_preregistration.py` must pass.
2. Build PX4 at `547e2ca` plus the frozen patch, committed. Then run the
   executor:
   `research/xsys_confirmatory_001/execution/run_confirmatory.py --px4-src <tree> --build <tree>/build/px4_sitl_default --out <flights> --work <tmp>`.
   - It verifies the source and the manifest and records the binary once
     (CAMPAIGN.json).
   - It flies the 66 flights in the frozen order, retries technical failures
     once, and resumes if interrupted.
3. Stage 0: `stage0_prepare.py --mode confirmatory --freeze-manifest … --flight-matrix`
   (frozen) `--analysis-matrix` (frozen) `--flights <flights> …`.
4. Stage 1: `stage1_evidence.py --freeze-manifest … --blind … --calibration`
   (frozen) `--out STAGE1.json`, which writes the seal.
5. Stage 2: `stage2_score.py --freeze-manifest … --stage1 STAGE1.json --key … --qc … --analysis-matrix`
   (frozen) `--out RESULTS.json`.
6. Archive the ULogs and records (xz + `SHA256SUMS`, as for the apparatus)
   and report the primary result first. Every secondary result carries its
   gatekeeping label.

## 19. Limitations

- **Simulation.** SIH is a simplified multirotor. Nothing here speaks to a
  real ESC, a real rotor or real sensor noise.
- **Case B is constructed offline.** The corruption is a multiplicative
  replay of A's ratio. It is the strongest matched test of the local channel,
  but not a model of any specific telemetry failure mode.
- **Noise independence is by design, not verified.** Conditions differ in
  heading and onset phase. The T1 windows are disjoint in simulated time, but
  the T0 and T3 windows of conditions less than 5 s apart overlap. If two
  conditions replay the same noise family, their T3 noise partly coincides.
  The bound's unit is the condition. It does not protect against correlation
  **between** conditions; the pilot's 2.9× threshold margin for C_T3 limits
  the practical effect.
- **The η = 0.95 dynamics gate is marginal** (1.045×). This is disclosed in
  §4.2.
- **One motor, one fault direction.** Only motor 0 and only thrust loss are
  tested. The loss-axis sign is part of the witness.
- **Calibration variability.** The calibration used the apparatus flights'
  noise families. The factor 2 is the only allowance for conditions they did
  not include.
- **Environment.** The reference Python, numpy, scipy and pyulog versions are
  recorded in the manifest for information. A different version in the
  future run is recorded, not prevented.

## 20. Note on the instruction text

The request that authorized this preregistration was cut off mid-sentence
in the statistical plan: "Specify: primary statistic, confidence interval
method, hypothesis test if appropriate, alpha if significance testing is
used, multiple". This plan assumes the remainder asked for:

- multiple-comparison control (§12);
- power and sample size (§4.3, §12);
- the deliverables;
- the instruction to freeze, validate, report and stop.

Any part of the missing text that asked for something else is not addressed
here.

## 21. Files

| role | path |
|---|---|
| machine-readable protocol | `research/xsys_confirmatory_001/prereg/PREREG_CONFIG.json` |
| matrix generator | `research/xsys_confirmatory_001/prereg/generate_matrix.py` |
| power analysis | `research/xsys_confirmatory_001/prereg/power_analysis.py` |
| freeze / verify | `research/xsys_confirmatory_001/prereg/freeze.py` |
| evidence definitions | `research/xsys_confirmatory_001/pipeline/xsys_features.py` |
| ULog extraction, t0 | `research/xsys_confirmatory_001/pipeline/xsys_extract.py` |
| v2 adapter | `research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py` |
| freeze check used by the stages | `research/xsys_confirmatory_001/pipeline/xsys_freeze_check.py` |
| executor, trial driver | `research/xsys_confirmatory_001/execution/run_confirmatory.py`, `research/xsys_confirmatory_001/execution/xsys_run_trial.py` |
| pilot logs and analysis | `research/xsys_confirmatory_001/apparatus_pilot/`, `research/xsys_confirmatory_001/validation/pilot_analysis.py` |
| dry run | `research/xsys_confirmatory_001/validation/run_dry_run.sh`, `research/xsys_confirmatory_001/validation/summarize_dry_run.py`, `research/xsys_confirmatory_001/pipeline/dry_run_matrix.py` |
| freeze guard | `tests/test_xsys_001_preregistration.py` |
