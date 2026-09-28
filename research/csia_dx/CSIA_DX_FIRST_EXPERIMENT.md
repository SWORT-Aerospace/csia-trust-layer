# CSIA-DX: smallest falsifiable first experiment (DESIGN ONLY; NOT RUN)

Part of the CSIA-DX review (2026-09-28). Source ids are listed in
`research/csia_dx/BIBLIOGRAPHY.md`.

**Status: design only.** Nothing is built, flown or simulated. Running it
needs:

- an authorization, which this phase does not give;
- a validated apparatus;
- a preregistration with frozen thresholds, in the manner of XSYS-001.

The design serves the **pivoted** question in
`research/csia_dx/CSIA_DX_REVIEW.md` §10. It is an engineering-value test of
a thin composition of known techniques. **It is not a test of novelty.** A
positive result could not raise the novelty status above N2.

## 1. Question

On a small multirotor propulsion model with five hypotheses (the toy in
`research/csia_dx/CSIA_DX_TOY_EXAMPLE_AND_FEASIBILITY.md` §2), does
precomputed, availability-indexed separability reasoning ("DX-lite")
satisfy all four of the following?

- (a) It never claims that a pair is separable when it is not.
- (b) It never executes a probe that is unsafe under the true hypothesis.
- (c) It never names a wrong cause.
- (d) It never takes an action unjustified under the true hypothesis.

And does it resolve the pairs that a safe probe can resolve? Each of these
is measured against baselines built from known techniques, at bounded
compute.

## 2. Apparatus (to be built and validated first)

- **The simulator.** A propulsion-electrical multirotor simulator with:
  - a Thevenin battery model (internal resistance, state of charge);
  - an ESC efficiency model;
  - a BLDC motor torque/current model;
  - rotor thrust;
  - a rigid-body hexacopter with closed-loop attitude control and
    allocation.

  PX4 SIH, as used in XSYS-001, models none of battery current, ESC current
  or motor current. It cannot host this experiment unchanged.
- **Sensors.** V_bat, I_bat, I_esc, RPM, CMD and IMU, with preregistered
  noise.
- **Faults.** H1–H4 as in the toy, each at 2–3 severities. H0 is nominal.
- **Sensor-loss switches.** Lose I_bat; lose ESC telemetry (I_esc and RPM).
- **Apparatus acceptance before any confirmatory run.** It follows
  XSYS-001's discipline:
  - each fault produces its modelled signature;
  - each loss removes exactly the intended channels;
  - noise and nuisance conditions are independent across conditions.

## 3. Conditions

| factor | levels |
|---|---|
| sensor set | FULL; −I_bat; −ESC telemetry |
| regime | low demand; high demand |
| safety state | margin OK; margin thin (collective and arm headroom < 5%, or state of charge within 5% of reserve) |
| true hypothesis | H0–H4 |
| nuisance condition (the independent unit) | ≥ 11 (wind, heading, onset time), preregistered |

## 4. Systems compared

| system | description | why it is included |
|---|---|---|
| **DX-lite** | three steps. **(1)** D_now from pair masks over W(t), with the six-state relation of the toy §1. **(2)** A missing witness with its reason tag. **(3)** The cheapest separating probe that is admissible under **every** hypothesis in H_active (offline, regime-indexed safety tables), and authority as the intersection of per-hypothesis acceptable actions. Built on CSIA v2 set elimination, which is unchanged | the candidate |
| B1 static FSM | full-sensor design-time signature matrix, not updated on loss | the brief's baseline. **Expected to overclaim after loss: a strawman, reported but not decisive** |
| B2 passive CSIA v2 | set elimination with three-valued predicates; AMBIGUOUS preserved; no probe; authority "land if AMBIGUOUS, else act on the cause" | shows what probes and authority add |
| B3 D-matrix reasoner + information-greedy probe, safety checked under the **most likely** hypothesis only | unavailable tests treated as unknown (the TEAMS-RT style, D27); the probe maximizing expected separation; admissibility checked under the MAP hypothesis | isolates the value of robust (all-candidate) probe admissibility, known in principle (D18, D20) |
| B4 belief-space safe active diagnosis (s-FEAST class, D20), **if an implementation can be obtained** | online tree search with chance constraints | the strongest known method. Tests whether the cheap deterministic scheme loses decisions, and at what compute ratio |

**The decisive comparison is DX-lite against B3 and B4, not against B1.**
If DX-lite only beats B1, the experiment shows nothing the literature does
not already predict.

## 5. Endpoints (to be frozen before any run)

**Primary: all four must hold.**

- **P1, no overclaim of knowability.** DX-lite never reports a pair
  SEPARABLE_NOW or SEPARABLE_BY_SAFE_PROBE when the empirical oracle finds
  it inseparable under that condition. Zero tolerance.
  - The oracle is fault-injection runs of both hypotheses under the
    condition.
  - A pair counts as separable if some **available** preregistered witness
    statistic separates the two distributions at the frozen margin.
  - The oracle is computed from data, not from DX-lite's signature table.
- **P2, no unsafe probe.** No executed probe drives the vehicle outside the
  preregistered safe set under the true hypothesis. Zero tolerance.
- **P3, no wrong cause.** No UNIQUE verdict names a cause other than the
  true one. Zero tolerance, as in XSYS-001.
- **P4, useful resolution.** Among (pair, condition) cells that the oracle
  marks resolvable by a probe that is safe under every candidate, DX-lite
  resolves a proportion whose cluster-conservative one-sided 95% lower bound
  exceeds a preregistered value.

**Secondary.**

- Unsafe-probe rate of B3 in the thin-margin cells, where the battery-load
  probe under a true battery fault is the designed trap.
- Resolution rate against B2.
- Unjustified irreversible actions per system: for example, isolating a
  healthy ESC under a true battery fault.
- Decision agreement with B4, and the compute ratio.
- The correctness of each missing-witness reason tag.
- VACUOUS hypotheses retired correctly after a telemetry loss.

## 6. Falsification

The candidate fails, and a pivot to KILL is recommended, if **any** of the
following happens:

- P1, P2 or P3 fails;
- P4 fails;
- DX-lite shows no advantage over B3 that is not simply the robust
  admissibility rule, which is known in principle (D18, D20);
- B4 matches DX-lite's decisions at comparable compute, so the deterministic
  scheme buys nothing.

## 7. Threats to validity, stated now

- **Signature circularity.** If the simulator is written from the same
  signature table DX-lite uses, P1 is trivially met. The oracle must
  therefore be empirical, and the simulator must be physics-based rather
  than signature-based.
- **The trap cell is designed.** B3's expected failure in the thin-margin
  battery cell is engineered. It demonstrates a known failure mode; it does
  not show that it is frequent.
- **The model is small.** Five hypotheses and one propulsor fault class. No
  claim transfers to larger systems without the scaling in the toy's §3.
- **Simulation only.** As with XSYS-001.

## 8. Relationship to XSYS-001

XSYS-001 is used only as an existing empirical primitive. One of its
findings was that the evidentiary value of physical dynamics expires once
the controller compensates. In this design, that becomes the
**applicability region** of a witness (OUT_OF_REGIME). Nothing in XSYS-001
is reinterpreted or re-used as evidence that DX-lite works.
