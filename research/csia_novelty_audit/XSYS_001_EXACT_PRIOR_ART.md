# XSYS-001: exact prior art for the matched-set question (stage 2, pre-result)

This file is part of the second-stage novelty verification, written on
2026-09-27 and 2026-09-28. It adds to `research/csia_novelty_audit/XSYS_001_NOVELTY_AUDIT.md`
and does not replace it. Source ids are listed in
`research/csia_novelty_audit/BIBLIOGRAPHY.md`.

## Independence

This file draws on:

- the frozen preregistration, `docs/research/XSYS_001_PREREGISTRATION.md`;
- the two amendments, `docs/research/XSYS_001_A1_NUISANCE_INDEPENDENCE.md` and
  `docs/research/XSYS_001_A2_C4_CORRECTION.md`;
- the literature, open-source autopilot code and patents.

**No confirmatory log, stage output, completion record or result was opened.**
Nothing here depends on whether XSYS-001 succeeds or fails. Its outcome can
strengthen or weaken the **evidence for** the instance. It cannot change what
the prior art already contains.

## 1. The exact conceptual experiment

| element | brief's wording | frozen XSYS-001 form (prereg §§1, 7, 10) |
|---|---|---|
| case A | controller commands actuator; physical effectiveness degrades; dynamics change; controller compensates | rotor 0 effectiveness η < 1 in PX4 SIH at t0; attitude control and the allocator compensate |
| case B | physical actuator nominal; RPM/actuator telemetry corrupted to give a similar local symptom | nominal flight; rotor 0's RPM telemetry scaled offline to **replay case A's observed ratio**, so the local symptom is identical by construction |
| local evidence | local RPM behaviour | W_RPM: the implied fractional thrust deficit from the RPM ratio |
| transient evidence | vehicle dynamics during the transient | W_DYN: mean body-rate deviation along rotor 0's loss axis over T1 = [0, 0.2) s; "Valid in T1 only" |
| persistent evidence | persistent controller compensation | W_CTRL: rotor 0's allocator command over the mean of the others, over T3 = [10, 15) s, against T0; "Valid in T3 only" |
| decision | distinguish the root cause | CSIA v2 set elimination. UNIQUE only if the rival is refuted and the cause confirmed; otherwise AMBIGUOUS. Zero-WRONG is part of the primary rule |

**One structural fact matters for the prior-art comparison.** In PX4 the
motor RPM telemetry is a **monitoring** channel. The attitude loop does not use
it as feedback. So in case B the corruption never reaches the controller:

- no compensation occurs;
- no body-rate transient occurs.

The problem therefore differs from the classic closed-loop case (B117, B118),
where the faulty sensor **is** the feedback signal and the loop acts on the
false value. It is closer to checking a monitoring channel by analytical
redundancy (B05) against two physical references, each valid in one phase.

## 2. Dedicated searches (the brief's twelve topics)

| topic | queries | what was found | level |
|---|---|---|---|
| actuator fault vs actuator-sensor fault | Q-series of stage 1; S2Q4, S2Q5, S2Q29, S2Q35, S2Q38 | EPOS family (P03–P05, P25); B117; P01; P02; steer-by-wire simultaneous actuator/sensor work | V0 |
| motor fault vs RPM-sensor fault | S2Q3, S2Q36 | **no multirotor study found**. Rotorcraft speed-sensing logic (P15); field reports of unreliable ESC RPM telemetry (B140, B146) | V0 |
| actuator effectiveness vs feedback-sensor failure | S2Q8, S2Q9, S2Q34 | B118: feedback removes the steady-state effect of actuator faults "except for the feedback sensor fault" | V0 |
| control effort for actuator diagnosis | S2Q2, S2Q30, S2Q37 | ArduPilot `thrust_balance` and yaw integrator (B130, **V4**); control-objective residuals (B145) | V4 / V0 |
| vehicle response validating actuator feedback | S2Q6, S2Q29 | commanded thrust against measured acceleration (B53); EPOS engine response | V0 |
| physical dynamics validating actuator telemetry | S2Q23, S2Q35 | EPOS (engine pressure differential); an INDI split of actuator dynamics from effectiveness using RPM (**source not attributed**) | V0 |
| UAV motor fault isolation using the IMU | S2Q6, S2Q30, S2Q32 | IMU observers for motor failure; ESC speed and current to separate motor failure from propeller damage (B141) | V0 |
| UAV actuator fault isolation using body rates | stage 1; S2Q6 | tracking-error ordering of faulty rotors (B50); body-rate LOE estimation (B48, B54, B125) | V0 |
| motor degradation diagnosis from the attitude response | stage 1; S2Q6 | B50, B51, B53 | V0 |
| control-allocation residuals | S2Q30 | allocation with unknown-input observers (B21); parity-space residuals with recursive least squares on a multirotor (B54) | V0 |
| closed-loop compensation signatures | S2Q8, S2Q11, S2Q34 | B118; B129 (masking lowers diagnosability); B127 | V0 |
| simultaneous actuator/sensor diagnosis | S2Q7 | B123 (IMM: LOE against IMU bias); B124 (flight tests) | V0 |

## 3. The closest sources, against the exact experiment

| source | pair | shared local symptom stated? | physical-response discriminator | compensation discriminator | phase windows | ambiguity output | matched by construction | level |
|---|---|---|---|---|---|---|---|---|
| EPOS family (P03–P05, P25) | actuator sensor vs actuator hardware (engine) | **yes**: "both … experience an inability of the minor loop … to keep an error … within required tolerance" | **yes**: "the engine response … is very different and distinguishable" (pressure differential) | partial: the direction of feedback drift against the request | UNCLEAR | UNCLEAR | UNCLEAR (patent text not read) | V0 (search-rendered text) |
| B118 | actuator vs feedback sensor (electro-hydraulic) | UNCLEAR | partial: steady-state loop variables | **yes in substance**: feedback removes the actuator fault's steady-state effect, not the sensor fault's | steady-state only, as shown | UNCLEAR | UNCLEAR | V0 |
| B117 | actuator vs sensor (SISO loop) | UNCLEAR | UNCLEAR | **yes**: residual from controller-demanded signals | partial: sensor fault masked "after a short time" | UNCLEAR | UNCLEAR | V0 |
| ArduPilot (B130) | which motor lost thrust; no telemetry case | n/a | **yes**: descent | **yes**: `thrust_balance`, yaw integrator | partial: context gates and a phase-conditioned suspension | no | no (code) | **V4** |
| PX4 (B131) | failed motor via ESC current | n/a | partial (imbalanced-prop metric) | no | partial: latch against post-action false exoneration | no | no (code) | **V4** |
| B123 / B124 | quadrotor actuator LOE vs **IMU** faults | UNCLEAR | yes | UNCLEAR | UNCLEAR | UNCLEAR | UNCLEAR | V0 |
| B125; INDI RPM split | per-actuator LOE from RPM + gyro + accelerometer; actuator dynamics vs effectiveness | UNCLEAR | yes | UNCLEAR | UNCLEAR | UNCLEAR | UNCLEAR | V0 |
| P15 | engine-speed sensor vs physical decoupling (rotorcraft) | UNCLEAR | yes (fuel flow as the second physical channel) | no | UNCLEAR | UNCLEAR | UNCLEAR | V0 |
| B147 | constructed corruption consistent with the physics (power systems) | constructed | n/a | n/a | n/a | n/a | **yes, by design, in security** | V0 |

## 4. Classification

**The underlying question is CLOSE_PRIOR_ART.**

The question is: can evidence beyond the local symptom separate a physical
actuator fault from a fault in that actuator's own sensor or telemetry, when
both show the same local symptom?

- **EPOS** states the pair, the shared local symptom and a
  physical-response discriminator (V0, patent text).
- **B118** states that closed-loop compensation treats the two faults
  differently, and uses that for isolation (V0).
- **B117** uses controller-demanded signals against closed-loop masking (V0).

The ideas are there. The plant (engine or hydraulics rather than a
multirotor) and the channel (a feedback LVDT rather than monitoring-only RPM
telemetry) differ.

**The exact matched-set formulation is POSSIBLY_DISTINCT.** Its elements are:

- a multirotor;
- RPM telemetry corrupted to **replay the observed ratio** of a physical
  effectiveness loss;
- a transient body-rate witness and a post-compensation allocator witness,
  each **inapplicable outside its window** and detectability-gated;
- ambiguity-preserving elimination;
- zero-WRONG as part of the primary decision;
- the nuisance condition as the unit;
- an invalid-window negative control.

No directly matching work was identified in the searched sources.

**Why not KNOWN.** No source was found that runs this pair on a multirotor,
with these witnesses and windows.

**Why not APPARENTLY_DISTINCT_PENDING_VERIFICATION.** Three reasons:

1. The closest sources (EPOS, B118, B117, B123/B124, B125 and the INDI
   source) are all unread at V0. Any of them could contain the transient and
   compensation phases, or the RPM-sensor case.
2. The ESC-telemetry fault literature is poorly indexed. Stage 1 noted that
   GNSS and IMU spoofing results dominated the searches, and stage 2
   (S2Q22, S2Q36) found field reports but no study.
3. The matched-by-construction replay has a close analogue in constructed
   physically consistent corruption in security (B147).

**It is not called new.** Calling it new would require the P0 queue in
`research/csia_novelty_audit/CSIA_FULLTEXT_VERIFICATION_QUEUE.md` to be read
at V3 or better.

## 5. What each stage-1 answer becomes

| stage-1 question (`XSYS_001_NOVELTY_AUDIT.md` §2) | stage-1 status | stage-2 status | change |
|---|---|---|---|
| 1. this exact matched-set problem studied? | POSSIBLY_DISTINCT (instance) | POSSIBLY_DISTINCT (formulation); CLOSE_PRIOR_ART (question) | the EPOS text now shows the shared local symptom explicitly |
| 2. actuator vs actuator-sensor discrimination | KNOWN | KNOWN | unchanged |
| 3. rigid-body response validating actuator telemetry | LIKELY_KNOWN | LIKELY_KNOWN | EPOS does it with engine response; no multirotor ESC-RPM case found |
| 4. controller compensation as diagnostic evidence | KNOWN | **KNOWN, verified at V4** (ArduPilot) | the XSYS-001 allocator statistic is in the same family as ArduPilot's `thrust_balance` |
| 5. transient-to-compensation change in evidence utility formalized | CLOSE_PRIOR_ART | CLOSE_PRIOR_ART | added: B119 (mode-scoped validity), B142 (validity region), PX4 latch rationale and ArduPilot phase-conditioned suspension (V4) |
| 6. structural candidate-set diagnosis with temporal evidence | KNOWN (general) | KNOWN (general) | unchanged |
| 7. preregistered zero-WRONG evaluation | APPARENTLY_NOVEL (practice; LOW) | **N2 as part of MNC-2** (LOW) | downgraded. Its parts are known in other fields and in FDI theory (B122 false-isolation bound), and the matched construction has a security analogue (B147) |

## 6. What would move the classification

| finding | effect |
|---|---|
| B118 or EPOS full text uses transient-phase evidence together with compensation or loop behaviour | the formulation → CLOSE_PRIOR_ART, differing only in plant |
| B123/B124, B125 or the INDI source treats multirotor **RPM-sensor** faults against effectiveness loss using body rates | the formulation → CLOSE_PRIOR_ART or KNOWN |
| a PHM or UAV paper injects ESC/DShot telemetry corruption matched to a physical loss | the formulation → KNOWN |
| none of the above after V3 reading of the P0 queue | the formulation → APPARENTLY_DISTINCT_PENDING_VERIFICATION, still an instance of a known question |
