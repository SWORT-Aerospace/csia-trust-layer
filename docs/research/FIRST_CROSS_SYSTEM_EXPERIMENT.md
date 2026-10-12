# First cross-system experiment — Set B plus dynamics

**Status: PROPOSED design, witnesses revised (§6). Not preregistered, not
run.** Written under `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`. The
gating source read is done
(`docs/research/PX4_SET_B_DYNAMICS_PREFLIGHT.md`), and the apparatus has been
validated without any CSIA run
(`docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md`). The final
campaign waits on the owner's review of the apparatus.

---

## 1. The question

> Can an independent physical consequence observed in another system domain
> increase the resolving power of CSIA's existing cross-domain localization?

This is a **matched-set discrimination** experiment, not an anomaly-detection
benchmark. Detecting that *something* is wrong with `motor_0` is not the
result. The result is whether the candidate set left by v2's localization
**shrinks**, correctly, when evidence from the rigid-body dynamics is admitted.

---

## 2. Where this starts: what Set B already established (HISTORICAL / SEALED)

`engineering/v2/MATCHED_SCENARIOS.md`, Set B, from v2 Phase C at `50c5d35`:

| member | injected | v2 result on the **multirotor** |
|---|---|---|
| `MS_B1_COMMAND_LOST` | command never delivered | AMBIGUOUS |
| `MS_B2_POWER_PATH` | actuator rail out of tolerance | AMBIGUOUS |
| `MS_B3_DRIVE_NO_CURRENT` | drive passes no current | AMBIGUOUS |
| `MS_B4_MECHANICAL` | shaft jammed | AMBIGUOUS: `ACTUATION/mechanical` **and** `SENSOR/response_sensor` |
| `MS_B5_RESPONSE_SENSOR` | speed channel dead | AMBIGUOUS: `ACTUATION/mechanical` **and** `SENSOR/response_sensor` |

The recorded reason is that the multirotor has **no independent physical
channel on the shaft**, so `SENSOR/response_sensor` can never be refuted and the
candidate set "has an honest floor of two". On the motor test stand, which has
a torque channel, B4 and B5 each resolve to `SUPPORTED`. The record concludes:
**"Resolving power is a property of the instrumentation, not of the
algorithm."**

**This experiment tests one specific challenge to the "no independent channel"
premise.** A motor that does not produce thrust changes the vehicle's motion. A
speed sensor that lies does not. The IMU and the attitude controller observe
the vehicle's motion, not the telemetry. If that consequence is observable in
time, the multirotor has an independent channel after all. It is simply in a
different domain.

---

## 3. Hypotheses

### Primary

**H1.** On a multirotor, evidence from the vehicle's dynamics refutes
`SENSOR/response_sensor` when the motor genuinely fails to produce thrust
(member A), and refutes `ACTUATION/mechanical` when only the speed telemetry
is wrong (member B). v2's candidate set therefore drops from two members to
one, and the survivor is the injected cause.

### Secondary — tested only if the platform supports them

| id | question | expected, and why (PREDICTED) |
|---|---|---|
| H2 | can dynamics separate **command-path failure (C)** from a mechanical failure (A)? | **No.** A command that never reaches the motor and a motor that cannot turn produce the same physical consequence: no thrust. Separating them needs a command-delivery witness, not a dynamics one. Predicted to remain AMBIGUOUS. **This is an observability boundary to confirm, not a result to hope against.** |
| H3 | can dynamics separate **power-path degradation (D)** from a mechanical failure (A)? | only with a current or voltage channel on the affected path. PX4 SIH has none (`battery.current` UNAVAILABLE); ArduPilot has battery current but a command-echo RPM. Not testable on the first platform. |
| H4 | can dynamics separate **drive/ESC degradation (E)** from a mechanical failure (A)? | only with an ESC current channel. It is a stub on both platforms. Predicted untestable. |

**Not assumed:** that all five are distinguishable. The purpose is to find
where the boundary actually lies. A result of "A and B separate; A, C and E do
not" is a complete and useful answer.

---

## 4. The matched set

Every member must produce the same symptom v2 already uses,
`COMMAND_NO_RESPONSE` on `motor_0`, or its partial-loss analogue, and must
differ only in cause.

| member | what physically happens | how it is produced | on PX4 SIH |
|---|---|---|---|
| **A** mechanical / thrust loss | the rotor does not deliver commanded thrust | the platform's own motor failure injection, the physics path | pending G2, G4 |
| **B** telemetry wrong | the rotor is fine; the speed report is wrong | corruption of the **recorded RPM telemetry** in the analysis adapter, with physics untouched | yes, if the RPM channel exists (G1, G3) |
| **C** command lost | the command never reaches the motor | not separately injectable from A in SITL without a command-delivery model | kept as the H2 boundary probe |
| **D** power path | the motor's supply degrades | not expressible on PX4 SIH | deferred to ArduPilot, or dropped |
| **E** drive degraded | the ESC delivers reduced current | no ESC current channel on either platform | dropped for this experiment |
| **N** nominal control | nothing | identical run with no fault | required |

**Why corrupting telemetry is legitimate for B, when corrupting observations
was ruled out for A.** Member B *is* a telemetry fault. The physical system is
healthy and only the report is wrong, so an observation-level corruption is the
correct physical model of B. Member A is a physical fault, and faking it at the
observation level is exactly what the owner prohibited and what the current
bench simulator does (`csia/sensors/motor.py`). A must come from the physics.

**Partial loss matters more than total loss.** A quadrotor with one motor fully
off typically loses attitude control, which tests recovery rather than
discrimination. A partial thrust loss that the controller *compensates for*
is the harder and more informative case. Once compensation settles, the
dynamics may look nominal again, so the observability window may close. G4
decides whether partial loss can be expressed.

---

## 5. Observables

All read from the platform's logs by an adapter **outside** the frozen
packages. Grades are from the feasibility matrix.

| observable | source on PX4 SIH | grade |
|---|---|---|
| per-motor command | ULog `actuator_motors`, `actuator_outputs_sim`, 250 Hz | CONFIRMED (apparatus) |
| RPM telemetry | ULog `esc_status`, 250 Hz. It reports the **physical rotor state**, not the command (preflight G1). MAVLink ESC_STATUS (~1 Hz) is not used | CONFIRMED (apparatus) |
| body accel and rates | ULog `sensor_combined`, ground truth, 250 Hz | CONFIRMED |
| attitude | ULog `vehicle_attitude`, ground truth | CONFIRMED |
| allocator saturation | ULog `control_allocator_status`, 125 Hz. **Demand evidence only**: the allocator's "torque achieved" is computed from its own model and never observes physical effectiveness (§6 revision) | CONFIRMED (apparatus) |
| estimator innovations | ULog `estimator_innovations`, test ratios, 125 Hz, stamped at the EKF's delayed horizon | CONFIRMED logged. The EKF aiding innovations show no fault-attributable response (apparatus) |
| ground truth | SIH truth, as compared in `docs/simulation/PX4_CURRENT.md` §2 | CONFIRMED |
| injected fault state and onset | `SIH_MOT_EFF1` change: `parameter_update` timestamp, applied at the next 4 ms SIH step | CONFIRMED (apparatus) |

Apparatus results: `docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md`.

---

## 6. Local evidence and the proposed cross-system witnesses

### Local evidence (single domain)

- **L-RPM:** RPM telemetry against command. The residual an ESC monitor would
  compute.
- **L-IMU:** IMU consistency residuals, of the kind v1 already forms.
- **L-CUSUM:** a sequential detector on each residual. This is a **baseline**,
  and it is not placed inside CSIA. `research/phase5/PHASE5_RESULTS.md` records
  that λ-based fast paths lose threshold robustness (H5 killed).

### Cross-system witnesses (REVISED before preregistration)

**Revision, approved by the owner before any preregistration.** The original
W1 ("the allocator reports the demanded torque not achieved") is **withdrawn
as a physical witness**. The allocator computes "achieved" from its own
effectiveness model, which never observes the physical actuator
effectiveness (`docs/research/PX4_SET_B_DYNAMICS_PREFLIGHT.md` §10, item 4).
On the apparatus it reports the torque achieved in every in-flight step while
motor 1 produces only 60% of its commanded thrust. Allocator saturation survives only as one W_CTRL
variable, as evidence of demand, never as evidence of physical torque. The
old W2, W3 and W4 are absorbed into the categories below.

Witnesses are grouped by **evidence category**, one per data category the
apparatus keeps apart. Each category holds evidence **variables**. The
three-valued predicates built from them (true, false, or **not measurable**,
the contract `csia/v2/localization.py` already uses) and every threshold are
fixed in the preregistration, **not here**. "Not measurable" eliminates
nothing. It is not assumed that all four categories will be needed.

| category | data category | evidence variables (ULog) | member A on the apparatus | member B on the apparatus | not measurable when |
|---|---|---|---|---|---|
| **W_CTRL** controller / allocator demand and compensation | COMMAND | motor-i command against the symmetric hover expectation, κ_i = c_i / mean(c_j, j≠i); rate-loop torque-setpoint offset; allocator saturation flag (demand only) | present 12–32 ms after onset and **persistent** in steady state while compensation is feasible: κ → 1/η | absent | manoeuvres that break hover symmetry; motor at its limit (κ saturates) |
| **W_RPM** rotor response against command | TELEMETRY (equal to PHYSICAL rotor state in SIH unless corrupted) | reported RPM against a healthy-rotor expectation from the command history (first-order lag τ); cross-motor RPM symmetry in steady hover | present | present, **matched by construction** | RPM channel absent or stale (the ~1 Hz MAVLink path) |
| **W_DYN** rigid-body consequence | VEHICLE RESPONSE | angular acceleration, body rates, tilt, specific-force change, altitude deviation, against the nominal envelope of the control arm | strong in the **onset transient** (peak 0.15–0.2 s after onset), weak during compensation, **absent in steady state** | absent | nominal envelope not characterised; manoeuvres |
| **W_EST** estimator consequence | ESTIMATED STATE | EKF aiding innovations and test ratios; hover-thrust estimator innovation and estimate | EKF aiding innovations: **no fault-attributable response**. Hover-thrust innovation: only at η ≤ 0.6. Hover-thrust estimate: slow steady offset at η ≤ 0.7 | absent | before the estimators converge |

**What each category can and cannot do.**

- **W_RPM defines the symptom** (COMMAND_NO_RESPONSE) that A and B share. It is
  how the matched set is built, not how it is resolved. The cross-motor
  symmetry variable is the exception: in A's steady hover every rotor reads
  the same, while in B the reported RPM sits below the others. That variable
  depends on a rotor-to-thrust model (T ∝ RPM² in SIH), which a preregistration
  must declare.
- **W_CTRL's persistent evidence is a command-side observation.** It shows the
  closed loop working harder on one motor, which confirms a loss of
  effectiveness somewhere downstream of the command. It does not separate A
  from C, where the command is lost before the motor, so the H2 boundary is
  unchanged.
- **W_DYN is transient.** Its evidence exists mainly before the controller has
  compensated. That is a timing requirement on any architecture that uses it.

**Localization rule: v2's, unchanged.** A hypothesis is `SUPPORTED` only when
it is the last one standing **and** something affirmatively confirms it
(`csia/v2/localization.py`, `csia/v2/attribution.py`). No scoring, no priors,
and no inference from time order. The witnesses are new **evidence**; the
elimination semantics and the certificate semantics are not touched. They are
applied by a research adapter that reads v2's hypothesis and predicate
definitions and never modifies `csia/v2/`.

### Expected signatures

The witness columns are MEASURED on the apparatus, as evidence magnitudes
without thresholds. The v2 column is PREDICTED; no CSIA version has been run.

| member | W_CTRL | W_RPM | W_DYN | W_EST | predicted v2 result |
|---|---|---|---|---|---|
| A, compensated (η ≥ 0.5) | present, all phases | present | onset transient only | hover-thrust only at η ≤ 0.6; EKF aiding absent | `ACTUATION/mechanical` SUPPORTED |
| A, authority lost (η ≤ 0.4) | present, saturated | present | present until ground contact | hover-thrust present | `ACTUATION/mechanical` SUPPORTED |
| B | absent | present | absent | absent | `SENSOR/response_sensor` SUPPORTED |
| C | PREDICTED as A | PREDICTED as A | PREDICTED as A | PREDICTED as A | AMBIGUOUS {A-like, C} (H2 boundary) |
| N | absent | absent | absent | absent | no fault SUPPORTED |

**If A and B produce the same W_CTRL, W_DYN and W_EST values, H1 is
falsified.**

---

## 7. If G1 shows PX4's RPM echoes the command

**Resolved: it does not.** The preflight showed that SIH's RPM reports the
lagged rotor state. With the effectiveness patch it reports the physically
reduced rotor. The contingency below is kept for the record and does not apply
to PX4 SIH at `547e2ca`.

Then the RPM channel on PX4 SIH, like ArduPilot's, never reports the rotor. In
member A it keeps agreeing with the command while the rotor makes no thrust, a
telemetry picture that no real ESC would produce for a jammed shaft.

The design still runs, with a narrowed claim. B is still produced correctly,
because a telemetry fault is still a telemetry fault. A's dynamics still come
from the physics, because the witnesses read the IMU and allocator, not the
RPM. **What is lost is realism of A's telemetry.** The result would then say
"dynamics separate a genuine thrust loss from a telemetry fault", and must not
say anything about what a real ESC reports during a thrust loss. That
limitation would be printed with every result.

---

## 8. Baselines

What each architecture actually contributes, with **no** tuning of the
treatment against any of them.

| id | method | what it can conclude |
|---|---|---|
| BL-1 | local threshold on L-RPM | "RPM disagrees with command": no cause |
| BL-2 | CUSUM on L-RPM and L-IMU | the same, sooner; no cause |
| BL-3 | frozen v1, run on the same streams through an adapter | its eight hypotheses; `power_fault` is its only propulsion hypothesis |
| BL-4 | **v2 Set B as it is**: localization without the dynamics witnesses | the SEALED expectation, a floor of two |
| **T** | v2 localization **plus** the revised witnesses W_CTRL, W_RPM, W_DYN, W_EST (§6) | the treatment |

BL-4 against T is the comparison that answers the question. The others show
what each simpler architecture already provides, and are reported whether or
not they look good.

---

## 9. Success, failure, ambiguity, and falsification

Thresholds below are **proposals** to be fixed in a preregistration **before
any trial runs**, following this repository's practice. They are not tuned
here, and they must not be tuned after any result is seen.

**H1 is SUPPORTED only if all of:**

1. in member-A trials, T returns `ACTUATION/mechanical` SUPPORTED in at least
   the preregistered fraction;
2. in member-B trials, T returns `SENSOR/response_sensor` SUPPORTED in at least
   the preregistered fraction;
3. **zero** member-A trials return `SENSOR/response_sensor` SUPPORTED, and
   **zero** member-B trials return `ACTUATION/mechanical` SUPPORTED. A single
   confident wrong isolation is reported, not averaged away;
4. in nominal trials, no fault is SUPPORTED at a rate above the preregistered
   false-certificate bound;
5. BL-4 returns the Set B floor of two on the same trials. This is the
   positive control: if BL-4 already separates them, the witnesses are not
   what did it.

**What falsifies H1:**

| id | observation | meaning |
|---|---|---|
| F1 | W_CTRL, W_DYN and W_EST take the same values in A and B | cross-domain evidence carries no discriminating information here |
| F2 | W_CTRL, W_DYN or W_EST fire in nominal trials | the witness is a noise detector, and any "resolution" is spurious |
| F3 | A's dynamics signature settles back to nominal before any witness decides | the observability window closes under compensation; resolution is not available in time |
| F4 | T resolves A and B only when BL-4 already does | the witnesses add nothing |
| F5 | a confident wrong isolation occurs in any trial | the rule is unsafe as proposed, regardless of the average |

**Ambiguity is a valid outcome.** If two hypotheses survive, or one survives
with nothing affirmatively confirming it, the result is AMBIGUOUS. If a
witness's input is not measurable, the result is UNRESOLVED, and it is
reported, not imputed. An AMBIGUOUS answer on C (H2) is the **predicted**
outcome and counts as a confirmed observability boundary, not a failure.

---

## 10. Metrics — kept separate, never collapsed into "accuracy"

Definitions are in `docs/research/LATENCY_PATH_ANALYSIS.md` §1.

| metric | here |
|---|---|
| detection latency | t2 − t1: first local indication after the first physical deviation |
| isolation latency | t4 − t1: first time the candidate set is a single hypothesis |
| certification latency | t5 − t1: first time that single hypothesis is SUPPORTED, i.e. affirmatively confirmed |
| action latency | t6 − t1: **not measured**. There is no FORGE implementation, and v1's policy action times are reported as a reference only |
| computational latency | per-evaluation wall time of the adapter and localization, reported separately |
| false alarms | BL-1/BL-2 alarms and any SUPPORTED fault in nominal trials |
| missed detection | fault trials with no local indication |
| incorrect isolation | a wrong hypothesis SUPPORTED: the most important count |
| unresolved / ambiguous | per member, reported with its reason |
| coverage | fraction of trials in which every witness was measurable |

t1 needs a **twin run**: the same flight with and without the fault, diffed
against SIH ground truth. Both platforms reproduce outcomes but not exact
timing, so t1 is estimated per pair and reported with its spread.

---

## 11. Repetition and determinism

Neither platform is shown to be bit-deterministic
(`docs/simulation/PX4_CURRENT.md` §2.4d; both repeat reconciliations). So every
member is flown **repeatedly**, and results are reported as distributions. The
per-member count is fixed in the preregistration; this repository's
current-stack campaigns used 20. A development partition is read freely; a
locked partition is opened once.

**Apparatus finding that constrains this section.** PX4 SIH is not
bit-deterministic, but it is **not independently random either**. SIH seeds
one process-wide `rand()` stream with a fixed seed, so repeats of an identical
protocol replay one of a few noise realizations. For example, three repeats of
a sweep level agreed to the step. Repeats are therefore **not independent
samples** of sensor noise. The preregistration must vary a declared nuisance
between repeats (for example onset time, arm time or wind) to obtain
independent realizations, and must not treat N identical repeats as N
samples. See `docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md` §E and §L.

---

## 12. What this experiment cannot show

- anything about hardware, a real ESC, or a real rotor;
- that the witnesses work on a platform other than PX4 SIH at `547e2ca`;
- prevalence, safety, or certification value;
- anything about power-path or ESC-current causes (D, E), which this platform
  cannot express.

---

## 13. Dependencies, in order

1. **Owner review of this document.** Nothing below starts before it.
2. **The gating source read, G1–G4**, at `547e2ca`
   (`docs/research/SITL_FEASIBILITY_MATRIX.md` §4). Its outcome may narrow
   this design (§7) or stop it (G2: no motor injection means no member A).
   *Done:* `docs/research/PX4_SET_B_DYNAMICS_PREFLIGHT.md`.
3. A **preregistration** fixing members, counts, thresholds and falsifiers,
   frozen before the first trial. *Not started; waits on the owner's review
   of the apparatus.*
4. Build PX4 SIH pinned at `547e2ca`, with the dependencies in the
   feasibility matrix §5. *Done for apparatus validation, with the SIH
   effectiveness patch:* `docs/research/PX4_ACTUATOR_EFFECTIVENESS_VALIDATION.md`.
5. The adapter and witnesses, outside `csia/` and `csia/v2/`, with tests
   proving they cannot change any frozen output.
6. Development partition; then the locked partition, once.
