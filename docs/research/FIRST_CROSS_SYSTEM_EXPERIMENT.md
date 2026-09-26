# First cross-system experiment — Set B plus dynamics

**Status: PROPOSED design. Not preregistered, not built, not run.** Written
under `docs/research/CROSS_SYSTEM_RESEARCH_EXCEPTION.md`. SITL execution waits
on the owner's review of this document and on the gating source read in
`docs/research/SITL_FEASIBILITY_MATRIX.md` §4.

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
| per-motor command | ULog `actuator_motors` / `actuator_outputs` | LIKELY |
| RPM telemetry | `esc_status` (MAVLink ~0.97 Hz; ULog rate G3) | UNKNOWN whether it measures the rotor (G1) |
| body accel and rates | ULog `sensor_combined` / `vehicle_imu` | CONFIRMED |
| attitude | ULog `vehicle_attitude` | CONFIRMED |
| allocation achievement | ULog `control_allocator_status.torque_setpoint_achieved` | LIKELY |
| estimator innovations | ULog `estimator_innovations`, test ratios | LIKELY |
| ground truth | SIH truth, as compared in `docs/simulation/PX4_CURRENT.md` §2 | CONFIRMED |
| injected fault state and onset | the injection command and its log record | UNKNOWN (never done for motors) |

---

## 6. Local evidence and the proposed cross-system witnesses

### Local evidence (single domain)

- **L-RPM:** RPM telemetry against command. The residual an ESC monitor would
  compute.
- **L-IMU:** IMU consistency residuals, of the kind v1 already forms.
- **L-CUSUM:** a sequential detector on each residual. This is a **baseline**,
  and it is not placed inside CSIA. `research/phase5/PHASE5_RESULTS.md` records
  that λ-based fast paths lose threshold robustness (H5 killed).

### Cross-system witnesses (PROPOSED)

Each witness is a **three-valued predicate** — true, false, or **not
measurable** — which is the contract `csia/v2/localization.py` already uses.
"Not measurable" eliminates nothing.

| id | predicate | confirms | refutes | not measurable when |
|---|---|---|---|---|
| W1 | the allocator reports the demanded torque **not** achieved, sustained | A | B | topic absent, or before onset has settled |
| W2 | one motor's command is persistently elevated against the symmetric hover expectation | A (compensating lost thrust) | B | during manoeuvres that break symmetry |
| W3 | an angular-acceleration or attitude transient at onset outside the nominal envelope | A | B | the envelope is not yet characterised on the control arm |
| W4 | RPM telemetry disagrees with command | B; A only if RPM measures the rotor (G1) | — | RPM channel stale (~1 Hz) |

**Localization rule: v2's, unchanged.** A hypothesis is `SUPPORTED` only when
it is the last one standing **and** something affirmatively confirms it
(`csia/v2/localization.py`, `csia/v2/attribution.py`). No scoring, no priors,
and no inference from time order. The witnesses are new **evidence**; the
elimination semantics and the certificate semantics are not touched. They are
applied by a research adapter that reads v2's hypothesis and predicate
definitions and never modifies `csia/v2/`.

### Expected signatures (PREDICTED — the thing the experiment checks)

| member | W1 allocation | W2 command asymmetry | W3 dynamics transient | W4 RPM vs command | predicted v2 result |
|---|---|---|---|---|---|
| A | true | true | true | depends on G1 | `ACTUATION/mechanical` SUPPORTED |
| B | false | false | false | true | `SENSOR/response_sensor` SUPPORTED |
| C | true | true | true | depends on G1 | AMBIGUOUS {A-like, C} (H2 boundary) |
| N | false | false | false | false | no fault SUPPORTED |

**If A and B produce the same W1–W3 values, H1 is falsified.**

---

## 7. If G1 shows PX4's RPM echoes the command

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
| **T** | v2 localization **plus** W1–W4 | the treatment |

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
| F1 | W1–W3 take the same values in A and B | dynamics carry no discriminating information here |
| F2 | W1–W3 fire in nominal trials | the witness is a noise detector, and any "resolution" is spurious |
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
3. A **preregistration** fixing members, counts, thresholds and falsifiers,
   frozen before the first trial.
4. Build PX4 SIH pinned at `547e2ca`, with the dependencies in the
   feasibility matrix §5.
5. The adapter and witnesses, outside `csia/` and `csia/v2/`, with tests
   proving they cannot change any frozen output.
6. Development partition; then the locked partition, once.
