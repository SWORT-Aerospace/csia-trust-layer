# CSIA-DX: formal objects, toy example and computational feasibility

Part of the CSIA-DX review (2026-09-28). Source ids are listed in
`research/csia_dx/BIBLIOGRAPHY.md`. **Illustrative only.**

- Nothing here is implemented in CSIA.
- Nothing here is an experimental result.
- The matrices were checked by hand and by a throwaway script. The script is
  not part of the repository.

## 1. Formal objects (written after the prior-art review)

These definitions are deliberately plain. The review in
`research/csia_dx/CSIA_DX_REVIEW.md` finds that each one restates an
established notion. The mapping is given beside each definition, so the
formalization cannot pass for a contribution by itself.

| symbol | meaning | established counterpart |
|---|---|---|
| H = {H0, H1, …, Hn} | hypotheses. H0 is nominal; single faults, optionally bounded multiple faults | fault modes (D01, D07) |
| S_all, S_t | installed sensors; sensors surviving at time t | sensor set / observable events (D04, D06) |
| A_all, A_t | installed actuators; actuators currently available for excitation | inputs / controllable events (D02, D16) |
| x_t, X | operating state or regime, and the regime space | mode (D42) |
| M | mission, environment and safety constraints | forbidden behaviour, state constraints (D03, D17, D18) |
| W | witnesses. Each w has a sensor requirement R_w ⊆ S_all, an actuation requirement Q_w ⊆ A_all (a **probe** if Q_w requires an injected input), an applicability region X_w ⊆ X, and a signature σ_w : H → {0, 1, ⊥}. Here 0 means consistent, 1 violated, ⊥ no prediction | analytical redundancy relation / residual / test with its fault signature (D07, D26); ⊥ is the three-valued "not measurable" status CSIA v2 already uses (D39) |
| E_t | evidence accumulated so far (the witness outcomes observed) | observations (D01, D25) |

**Witness availability.**
W(t) = { w ∈ W : R_w ⊆ S_t, Q_w ⊆ A_t, x_t ∈ X_w, w passive }.

**Separation.** w separates the pair (Hi, Hj) iff σ_w(Hi) and σ_w(Hj) are
both in {0, 1} and differ. This is the fault-signature notion of
isolability (D07, D26).

**The runtime relation D_ij(t)** takes one of six values:

| state | definition |
|---|---|
| SEPARABLE_NOW | some w ∈ W(t) separates (i, j) |
| SEPARABLE_BY_SAFE_PROBE | none does, but some probe p separates (i, j) and p ∈ P_safe(x_t, M, H_active) |
| PROBE_EXISTS_BUT_UNSAFE | some probe separates (i, j), but none is in P_safe |
| NOT_SEPARABLE_WITH_CURRENT_HARDWARE | some witness in W separates (i, j), but every such witness needs a lost sensor or actuator, or lies outside its applicability region |
| STRUCTURALLY_INSEPARABLE | no witness or probe in the design separates (i, j): a design-time ambiguity group |
| VACUOUS | one hypothesis concerns a channel that is itself lost (for example "RPM telemetry fault" after the telemetry disappears). It should be retired from H_active, not reported as ambiguity |

Established counterparts:

- a graded rather than binary relation is supported by conditional and
  unconditional isolability (D11) and by quantitative distinguishability
  (D09);
- STRUCTURALLY_INSEPARABLE is the testability ambiguity group (D26, D27,
  D28).

**Missing witness.** For an unresolved pair:

W_miss(i, j, t) = { w ∈ W \ W(t) : w separates (i, j) }.

Each element is tagged with its reason:

- SENSOR_LOST (R_w ⊄ S_t);
- ACTUATOR_LOST (Q_w ⊄ A_t);
- OUT_OF_REGIME (x_t ∉ X_w);
- PROBE_UNSAFE.

Structural isolability analysis names the same witnesses at design time
(D07, D08). CSIA's `competitors_without_witness` names them per competitor
(D39).

**Minimum additional evidence.**

e* = argmin_{e ⊆ W \ W(t)} C(e)
subject to: every target pair is separated by some witness in W(t) ∪ e.

This is weighted set cover:

- NP-hard in general;
- for a **single** pair, trivial: the cheapest single separating witness,
  O(|W|).

It is solved or approximated in sensor placement (D07, D08), test sequencing
(D26) and cost-aware active sensing (D24).

**Safe probe.** p ∈ P_safe(x, M, H_active) iff, for **every** H ∈ H_active,
the predicted state excursion of p under H stays inside the safe set of M.
Safety must hold under each candidate, not only under the most likely one.
This is the robust (or chance-constrained) condition of constrained active
diagnosis (D17, D18, D20, D21).

**Action authority under ambiguity.**
A_allowed(H_active, x, M) = ∩_{H ∈ H_active} A_ok(H, x, M).
This is a minimax rule over the unresolved set. Runtime assurance,
contingency management and belief-space safe control generalize it (D30,
D31, D32, D38).

## 2. Toy propulsion example

**Hypotheses.**

- H0: nominal
- H1: BATTERY_DEGRADATION
- H2: ESC_DEGRADATION
- H3: MOTOR_DEGRADATION
- H4: RPM_TELEMETRY_FAULT

The degradations H2 and H3 are on propulsor arm *m*.

**Sensors.**

- V_bat: battery voltage
- I_bat: battery current
- I_esc: ESC telemetry current
- RPM: ESC telemetry eRPM
- CMD: motor command
- IMU: body rates and acceleration

**Passive witnesses.**

| witness | relation | needs | violated by |
|---|---|---|---|
| W1 | battery voltage–current consistency | V_bat, I_bat | H1 |
| W2 | ESC power balance (input against output) | I_bat, I_esc | H2 |
| W3 | motor electromechanical consistency (current against RPM against command) | I_esc, RPM, CMD | H3, H4 |
| W4 | RPM against body dynamics (the XSYS-001-style relation) | RPM, IMU, CMD | H4 |
| W5 | command-to-RPM tracking | CMD, RPM | H2, H4; **H1 too at high demand** (voltage headroom exhausted) |

**Probes (active witnesses).**

| probe | action | needs | violated by |
|---|---|---|---|
| W6 | +3% collective thrust for 120 ms; battery sag per unit of commanded load | V_bat, CMD, all motors | H1 |
| W7 | +3% differential step on arm *m* for 120 ms; body-rate response | CMD, IMU, arm *m* | H2, H3 |

### 2.1 All sensors: every pair separable

| | W1 | W2 | W3 | W4 | W5 (low demand) | W5 (high demand) |
|---|---|---|---|---|---|---|
| H0 | 0 | 0 | 0 | 0 | 0 | 0 |
| H1 | 1 | 0 | 0 | 0 | 0 | 1 |
| H2 | 0 | 1 | 0 | 0 | 1 | 1 |
| H3 | 0 | 0 | 1 | 0 | 0 | 0 |
| H4 | 0 | 0 | 1 | 1 | 1 | 1 |

The rows are pairwise distinct in both regimes, so every pair is
SEPARABLE_NOW.

### 2.2 Lose the battery-current sensor (I_bat)

W1 and W2 become unavailable; the reason is SENSOR_LOST.

| | W3 | W4 | W5 low | W5 high |
|---|---|---|---|---|
| H0 | 0 | 0 | 0 | 0 |
| H1 | 0 | 0 | 0 | **1** |
| H2 | 0 | 0 | 1 | **1** |
| H3 | 1 | 0 | 0 | 0 |
| H4 | 1 | 1 | 1 | 1 |

**Low demand.** H1 cannot be separated from H0: battery degradation is
undetectable passively.

- W_miss(H0, H1) = {W1 (SENSOR_LOST)}.
- Probe W6 would separate them.

**High demand.** H1 and H2 have identical rows (0, 0, 1). **BATTERY versus
ESC is not separable**, as the brief anticipated.

- W_miss(H1, H2) = {W1, W2}, both SENSOR_LOST: one sensor, I_bat, restores
  both.
- Either W6 or W7 would restore separation.

The other pairs stay separable:

- motor against RPM telemetry, by W4 and W5;
- motor against ESC, by W3 and W5.

**Safety of the probes (robust over H_active = {H1, H2}).**

| probe | admissible only if, under **both** H1 and H2 | typical refusal |
|---|---|---|
| W6 (collective +3%) | collective thrust margin ≥ 5% and state of charge ≥ reserve + 5%. Under H1, extra load deepens the sag and risks brownout | at high demand the margin is by definition thin, so W6 is refused exactly where it is needed. D_12 = PROBE_EXISTS_BUT_UNSAFE |
| W7 (arm *m* +3%) | arm *m* headroom ≥ 5% and attitude margin. Under H2, arm *m* headroom is reduced | refused if arm *m* is near saturation |

This is the useful illustration. The probe that tests the battery
hypothesis is least safe when that hypothesis is true. The admissibility
test therefore has to be evaluated under every hypothesis in the class, not
under the likeliest.

**Authority while {H1, H2} is unresolved** (both probes refused).

| action | under H1 (battery) | under H2 (ESC, arm *m*) | allowed? |
|---|---|---|---|
| reduce collective demand | helps | harmless | **yes** |
| return to base at reduced speed | acceptable | acceptable | **yes** |
| land now | acceptable | acceptable | **yes** |
| switch to a backup battery (if fitted) | helps | harmless | **yes** |
| isolate the ESC on arm *m* | removes a healthy propulsor when thrust margin is scarce | appropriate | **no** |
| continue the mission at full demand | brownout risk | degraded arm | **no** |

### 2.3 Lose ESC telemetry (I_esc and RPM together: a common-cause loss)

W2, W3, W4 and W5 all become unavailable. Only W1 remains:

| | W1 |
|---|---|
| H0 | 0 |
| H1 | 1 |
| H2 | 0 |
| H3 | 0 |
| H4 | 0 |

- **H4 becomes VACUOUS.** Its channel is gone, so it should be retired.
  Reporting "H0 against H4 not separable" would be noise.
- **H2 against H3 is NOT_SEPARABLE_WITH_CURRENT_HARDWARE.** No available
  probe separates them either: W7 is violated by both. So it is
  effectively inseparable in flight, and the ambiguity must remain.
- H0 against H2, and H0 against H3, are SEPARABLE_BY_SAFE_PROBE via W7, when
  W7 is safe.
- **Authority still exists.** H2 and H3 both implicate the same propulsor.
  So "reallocate thrust away from arm *m*" is acceptable under both, and it
  is allowed without resolving the ambiguity. On a hexacopter, "shut
  propulsor *m* down" is acceptable under both. On a quadcopter it is not
  acceptable under either.

The same point is standard in testability: isolating to one replaceable unit
is sufficient even when the fault inside it is ambiguous (D26, D27).

### 2.4 What the toy shows, and what it does not

**Shows.**

- The relation changes with the sensor set and with the regime (W5's
  battery sensitivity).
- A missing witness can be named with a reason.
- One sensor can restore several pairs.
- A probe's safety must be robust over the unresolved class.
- Ambiguity blocks some actions and not others.

**Does not show.**

- That any of this is new. Section 1 maps every object to prior art.
- That deterministic signatures hold under noise. Separation that is
  structurally possible may still fail at the available signal-to-noise
  ratio. A quantitative measure such as D09 is then needed, and XSYS-001's
  detectability gate is the kind of rule that handles it.
- That the propulsion model is right. The signatures were chosen for
  illustration.

## 3. Computational feasibility

**Representation.**

- Index the P = |H|(|H|−1)/2 hypothesis pairs as bits.
- Each witness w carries a pair mask M_w: the bits of the pairs it
  separates. It also carries its requirement sets and its applicability
  region.
- D_now(t) = OR of M_w over w ∈ W(t).

| scale | hypotheses | pairs | 64-bit words per mask | masks for 256 witnesses |
|---|---|---|---|---|
| toy | 5 | 10 | 1 | 2 KB |
| single faults, 15 components | 16 | 120 | 2 | 4 KB |
| single faults, 63 components | 64 | 2 016 | 32 | 64 KB |
| single + double faults, 16 components | 137 | 9 316 | 146 | about 300 KB |

**What can be precomputed offline:**

- the witness library and signatures, from models, FMEA or the v2 signature
  matrix;
- the requirement sets and applicability regions;
- the pair masks and the inverted index from each pair to its witnesses;
- per regime cell × probe × hypothesis, a safe/unsafe flag or margin (from
  offline reachability analysis, as in D18 and D21);
- per hypothesis × action, an acceptability bitset.

**What must be done at runtime, and what it costs:**

| operation | cost |
|---|---|
| on each availability or regime change (rare, not every tick): recompute D_now | O(\|W\| · P / 64) word operations. At 256 witnesses and 146 words: about 3.7 × 10⁴, microseconds to a fraction of a millisecond on an embedded core |
| missing witness for a pair | an inverted-index lookup, O(k) |
| minimum evidence for one pair | the cheapest separating witness, O(k) |
| minimum evidence for several pairs | greedy weighted set cover (ln-factor approximation), or exact by enumeration when the unresolved set is small |
| probe admissibility | O(\|probes\| · \|H_active\|) table lookups |
| authority | AND of \|H_active\| action bitsets |

**The real limit is hypothesis growth.**

- Multiple faults grow as 2^F.
- Bounding fault cardinality (single plus selected double faults) keeps the
  tables in the sizes above.
- This is the same limit every consistency-based diagnoser has (D25, D33).

**Contrast with belief-space planning.**

- s-FEAST-class planners (D20) search trees over beliefs and observations
  online.
- That is richer and far costlier.
- Whether the cheap deterministic scheme loses safety-relevant decisions
  against them is an open, testable question. It is the question the pivot
  in `research/csia_dx/CSIA_DX_REVIEW.md` keeps.

**Verdict on feasibility.**

- **Plausible for embedded runtime** at single-fault and bounded
  double-fault scale.
- Compatible with CSIA's low-overhead, deterministic set elimination.
- Not compatible with online probabilistic planning on small
  microcontrollers.
