# First experiment, baselines and metrics (Phases 42, 43, 44)

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

**Designed, not run.** Nothing here is preregistered yet. Gate C requires a
frozen preregistration before any data is collected.

## 1. Phase 42: choosing the transition

The preferred class is:

1. evidence is valid under context C0;
2. a configuration transition happens;
3. the same evidence is no longer admissible;
4. legacy reasoning keeps using it, while validity-aware CSIA invalidates it.

| candidate transition | realism | reproducibility | existing data | field relevance | minimal implementation cost | overall |
|---|---|---|---|---|---|---|
| **controller compensation onset, with controller gains varied** (PX4 SIH, XSYS-001 apparatus) | good: physical effectiveness loss plus PX4 rate-loop compensation; gains vary across airframes and autotunes | deterministic SIH (the XSYS-001 A1 independence audit characterised its randomness) | **high**: built apparatus, effectiveness patch, calibrated witnesses, pipeline, sealed XSYS-001 set for regression (S014) | high: autopilot masking is the CA006 / ATR pattern (closed-loop package) | **lowest**: new gain settings and a contract-driven adapter; no new witness | **chosen** |
| EKF lane switch (ArduPilot 4.8 SITL, IMU fault forcing a switch) | high: lane switches happen in the field | deterministic SITL | low: no lane-switch logs in the repository | high | medium: new producers (RA-2-like for ArduPilot) and an injection method | **second experiment** |
| sensor source change (IMU failover) | high | deterministic | low | high | medium | folded into the lane-switch campaign |
| control-allocation change (motor removal) | medium: needs motor-failure detection to trigger | deterministic | low | medium | high: allocator failure mode, detection and new witnesses | later |

**Why a fixed-gain replay of XSYS-001 is not enough.** In XSYS-001 the
controller was fixed, so "time since onset" was a valid proxy for "before
compensation". A time window already achieved zero wrong attributions (S014).

On that data the new architecture can at best **tie** the time window.
XSYS-001 is therefore the **regression and parity gate** (Level 4). It is not
the value experiment.

The value question is whether validity bounded by the observed **event**
(compensation becoming active) still holds when **timing changes**, where a
fixed window does not. That requires varying what sets the compensation
timing: the rate-loop gains.

## 2. The experiment (working name XSYS-002-ADM)

**Question.** When controller gains change compensation timing, does
event-bounded admissibility of the dynamics witness keep attribution correct
without per-configuration tuning, where a fixed time window either:

- uses the witness after compensation (wrong or ambiguous); or
- discards it before it has separated the causes (lost resolution)?

**Design.** It reuses the XSYS-001 matched-set method.

| element | specification |
|---|---|
| platform | the PX4 SIH apparatus with the effectiveness patch, the same build as XSYS-001 |
| arms | case A: physical rotor-effectiveness loss. Case B: matched RPM-telemetry corruption. N: nominal |
| factor | rate-loop integral and proportional gains at three settings: slow, default, fast. Exact values to be chosen on calibration flights so that the time to compensation brackets the 0.2 s window (below, about equal, above) |
| nuisance | the XSYS-001 nuisance design (headings), with the A1 independence caveat carried: nuisance conditions are not independent units |
| effectiveness levels | a subset of η ∈ {0.95, 0.85, 0.75, 0.65, 0.55}, chosen by power analysis at preregistration |
| evidence | W_RPM, W_DYN, W_CTRL as in XSYS-001; `compensation_active` produced by the W_CTRL-derived producer, with its own contract |
| ground truth for W_DYN validity | from twin runs (same seed, no fault): the interval in which the body-rate deviation exceeds nominal variability and command asymmetry has not yet reached its compensation threshold. The same "first physically observable deviation" definition as the latency analysis (S040) |

**What would falsify the value claim.** Any one of these:

1. Across the gain settings, compensation timing does not move enough for the
   fixed window to err in either direction. Then the time window suffices and
   the architecture adds nothing here.
2. `compensation_active` is detected late enough that W_DYN is still read
   inside the compensated period. The event-bounded arm then errs like the
   legacy arm.
3. The oracle-tuned window (B2 below) and the architecture tie, **and** the
   plant-model residual (B3) beats both. That would argue for
   REPLACE_WITH_EXISTING_METHOD for W_DYN, which is a useful negative
   result.

## 3. Phase 43: baselines

None is a straw man.

| arm | what it is | why it is included |
|---|---|---|
| **B0** current CSIA | the XSYS-001 adapter with no window: v2 reads whatever it is handed | the real current core behaviour. Known to fail at fixed gains (55/55 in the negative control). Included for honesty, not as the comparator |
| **B1** timestamp expiration | a fixed window T1 = [0, 0.2) s, exactly as preregistered in XSYS-001 | the method that already worked. **The primary comparator** |
| **B2** mode-specific manual rule | a window tuned **per gain setting** on calibration flights: an oracle for the configuration | the strongest simple engineering alternative. The architecture must match it **without** per-configuration tuning to be worth anything |
| **B3** established method | a plant-model residual driven by the actual motor commands (predicted body acceleration from commanded thrust with nominal effectiveness, minus measured). Closed-loop FDI practice; it needs no window, because compensation does not remove a command-conditioned residual | the literature-appropriate method (closed-loop package, P12). If it wins, the right decision is to adopt it |
| **N** admissibility architecture | the W_DYN contract with `end_on: compensation_active`, a 0.2 s fallback bound, and the other contract clauses | the arm under test |

## 4. Phase 44: metrics

Accuracy alone is not used.

| metric | definition | primary or secondary |
|---|---|---|
| wrong attributions | trials whose C1 or C3 verdict names the wrong cause (the XSYS-001 WRONG definition) | **primary**: must be 0 for N |
| resolving rate | matched pairs with both A and B UNIQUE_CORRECT at the checkpoint | **primary**: N must not fall below B2 by more than the preregistered margin |
| valid evidence incorrectly rejected | W_DYN evidence-seconds inside the ground-truth validity interval that were marked non-admissible | secondary |
| stale evidence incorrectly retained | W_DYN evidence-seconds outside the ground-truth interval that were used | secondary: 0 expected for N |
| time to invalidate | ground-truth end of validity to the admissibility change | secondary |
| decision latency | onset to the first SUPPORTED (C1 or C3) | secondary |
| runtime cost | per-envelope admissibility and per-transition invalidation, on the host (target later) | secondary |
| memory cost | live slots and bytes | secondary |
| audit completeness | fraction of decisions whose trace lists, for every used record, its contract, context epoch and admissibility decision | secondary: must be 1.0 |
| configuration-transition correctness | confusion matrix of invalidation events against ground-truth compensation onset | secondary |

## 5. Preregistration items still open (for Gate C)

- The exact gain values (from calibration flights).
- The η subset and the number of nuisance conditions (from power analysis).
  The XSYS-001 lesson is that 11 conditions bound the resolving rate at
  0.7616 at best (S014).
- The margin for the non-inferiority comparison against B2.
- The B3 residual's threshold, calibrated on nominal flights only.
- The zero-WRONG rule for N.
- The rule that results are reported for every arm, including any in which N
  loses.

**What the experiment establishes.** At most, that one contract mechanism
generalises across controller configurations in one simulator. It says
nothing about hardware or other transitions.

**The second experiment** is the ArduPilot lane-switch campaign. It tests
**targeted** invalidation against the global-flush baseline
(`04_CONFIGURATION_TRANSITIONS.md` §1): does keeping unaffected evidence
shorten the loss of diagnosability after a switch, with no increase in wrong
attributions?
