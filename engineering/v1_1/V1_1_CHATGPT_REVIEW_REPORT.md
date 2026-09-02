# CSIA v1.1 — ENGINEERING REVIEW REPORT (PHASES 1–3)

Engineering only. FIXED / HARDENED / VALIDATED / SIMPLIFIED / IMPROVED.
No novelty language, and none is warranted (§31).

The 30 items §40 requires.

---

### 1. BASELINE / BRANCH / COMMITS

| | |
|---|---|
| frozen v1 | `csia-v1.0-research-final` @ `ec5acd189295dab9259d4989657d42184d6142a3` |
| engineering branch | `csia-v1.1-engineering` (local; pushes go to `claude/code-reviewer-repo-export-zicovg`) |
| Phase 1 | `e2160ca` canonical ingestion |
| Phase 2 | `95a95e1` support-aware diagnosis |
| Phase 3A | `1d79b40` GRAPH vs FLAT |
| Phase 3B gate | `8e5494b` B4 constant verification only |
| tests | 971 → **1022** |

**Frozen core: zero diff.** `csia/trust_engine`, `csia/diagnosis`,
`csia/runtime/online.py`, `csia/runtime/failsafe.py`, `csia/scenarios.py`,
`csia/profiles.py`. Phases 2 and 3 are entirely read-only over it.

### 2. PHASE 1 INTEGRITY

Intact. Four ingest defects reproduced-and-hashed before fixing
(`sha256 7fdd3d65…`), fixed, re-run with the same script (`sha256 7fff288a…`).
The GNSS control is byte-identical across the two records. Guards still pass.

### 3. DIAGNOSIS-SCORE DECOMPOSITION

`score[h] = log_prior[h] + EVIDENCE_MULT · smoothed[h]`, `posterior =
softmax(score)`, `contribution_j[h] = gate_j · (lo_j if j ∈ LOW[h] else hi_j)`.

Per-term contributions sum to the core's log-likelihood **exactly**
(`atol=0, rtol=0`). The reconstructed posterior matches production to
**9.437e-16** over all nine scenarios × 1500 ticks — one to four ULP, from
summation order, **not bit-identical**, and stated that way. Every constant is
*imported* from the frozen module, never copied.

### 4. SUPPORT-STATE DEFINITION

Structural, no tuned threshold. A term is **discriminating** for a pair iff it
is gated in, the hypotheses disagree about it in `CAUSES`, and `c ≠ 0.5` (the
core's own likelihood indifference point). A leader is **identifiable** iff at
least one active discriminating term exists against **every** other modeled
hypothesis — no filtering by posterior mass, which would be circular.

Output is three independent booleans plus detail, not an overloaded enum,
because `PRIOR_SENSITIVE` and `NON_IDENTIFIABLE` are not mutually exclusive.
`PARTIALLY_IDENTIFIABLE` is **not** implemented: it needs a cut-off on how
many competitors may collapse, which is the forbidden threshold.

`TAU_NUM = 1e-12` is a float comparison tolerance; a test asserts the verdict
is identical across `[1e-15, 1e-9]`. A second test greps both modules for
threshold-shaped comparisons.

### 5. FIX-LOSS SUPPORT RESULT

**The point of Phase 2.** `gps_dropout`, 25–33 s: **200 of 201 ticks (99.5%)**
report the leader as non-identifiable. Worst case at t = 25.0 s:

    leader                              nominal
    posterior                           0.999822
    support_state                       NON_IDENTIFIABLE
    ambiguity                           AMBIGUOUS
    active evidence terms               16   (20.5 before the fault)
    discriminating terms vs gps_fault   0

Mechanism, from source: `CAUSES["nominal"] = []` and
`CAUSES["gps_fault"] = ["phys_gps"]`, symmetric difference exactly
`{phys_gps}` (asserted by test); `online.py:613` multiplies every physics gate
by its sensor's freshness. Lose the fix, lose the only term that could ever
separate the pair. Before the fault, 100% identifiable — the control.

### 6. AMBIGUITY DEFINITION

`UNIQUE` iff identifiable against every modeled competitor; `AMBIGUOUS`
otherwise. **Never a posterior margin** (§10). Proven by test: some
`AMBIGUOUS` ticks have a *larger* margin than some `UNIQUE` ticks, which no
margin rule could reproduce.

### 7. AMBIGUITY RESULTS

`AMBIGUITY_RESULTS.csv`. Every scenario including `clean` has **76**
non-identifiable ticks at startup, before GPS becomes fresh — initialisation,
not a fault, and reported as such. `gps_dropout` has **276**; the 200-tick
difference is the dropout. No two hypotheses share a `LOW` set, so every
verdict here is a runtime property rather than a design-time one.

### 8. PRIOR-SENSITIVITY RESULTS

Same evidence, uniform prior, leader compared. `PRIOR_SENSITIVE` ticks:
`imu0_bias_drift` 106, `dual_imu_failure` 90, `gps_spoof` 28, `power_sag` 11,
`vibration_anomaly` 10, `mag_emi` 6, and **0 on `clean`, `gps_dropout` and
`high_speed_dash`**. The prior it is detecting is worth 3.761 in log-odds, so
evidence must move the smoothed log-likelihood difference by 2.507 to overturn
it. A test asserts the analysis leaves the production posterior bit-identical.

### 9. UNKNOWN DECISION

    UNKNOWN / UNMODELED: NOT IMPLEMENTED — MODEL ADEQUACY TEST REQUIRED

Audited, not assumed. A threshold-free criterion was **built and measured**:
set-adequacy `F_low ⊆ LOW[h]` against the core's own indifference point.
0% on `clean`, 0% on `gps_dropout` and `imu0_bias_drift`, **39.9% on
`dual_imu_failure`** (arguably correct — single-fault model, two injected
faults), 8.3% on `gps_spoof`.

Not adopted for two reasons: containment is strict, so one noisy feature
outside every `LOW` set flips the system, and adding tolerance is the
forbidden threshold; and deciding whether the `gps_spoof` 8.3% is right needs
adjudication against fault labels, which is the circularity §11 forbids. The
audit script is retained as evidence, wired into nothing.

### 10. GRAPH BASELINE DEFINITION

Production as-is: `w = gate_e · self.trust[other]`. The neighbour's trust
weights each incident edge, so trust propagates between nodes.

### 11. FLAT BASELINE DEFINITION

`w = gate_e`. **`FlatTrustCore` subclasses the frozen `TrustCore` and calls
`super().step()` verbatim — no method is copied.** Every other line executes
identically. The edge topology is untouched: all 8 nodes, all 11 relations,
all gates present in both arms.

### 12. MATCHING PROOF

Both arms consume the **same `td` object in memory**. The GRAPH arm reproduces
the frozen pipeline exactly (`np.array_equal` against
`scenarios.run_pipeline`). A test proves the ablation is exactly the trust
factor: with neighbour trust already at 1.0, GRAPH and FLAT agree bit-for-bit.
A test greps `flat.py` for copied frozen body after stripping docstrings. A
test asserts the class swap is restored.

### 13. GRAPH-VS-FLAT RESULTS

**Structural first:** `csia/diagnosis/bayes.py` imports only `consistency`
from the trust engine and reads `td.hist`, never `TrustHistory.trust`. The
posterior is graph-independent, so **attribution, ambiguity and support cannot
differ.** Checked against imports and body.

| | |
|---|---|
| max abs Δtrust | **0.047** (worst, `vibration_anomaly`); 0.0014 on `clean` |
| assurance levels identical | **7 of 9** scenarios |
| transition count and actions | identical in **all 9** |

The two that differ move only in timing, **both in FLAT's favour**:

    mag_emi           CAUTION->NORMAL   40.08 GRAPH / 40.04 FLAT   (one tick)
    dual_imu_failure  NORMAL->CRITICAL  34.40 GRAPH / 34.12 FLAT   (0.28 s)
    dual_imu_failure  CRITICAL->EMERG   49.16 GRAPH / 48.56 FLAT   (0.60 s)

### 14. GRAPH COMPLEXITY

8 nodes, 11 edges. 22 dict lookups and one multiply per tick; 64 bytes of
inter-tick state. Compute over **7 paired runs with alternating order**:
paired diffs (G−F) = 8.65, 5.82, 3.60, 3.79, −4.40, −2.57, −5.94. **The sign
changes; the difference straddles zero.** Reported as no measurable
difference, not as a FLAT win.

The graph is **cheap**, and the spec says so plainly: a cheap component needs
less benefit to justify keeping, so the case rests on the benefit being
absent, not on the cost being high.

### 15. GRAPH VERDICT

    GRAPH_NO_MATERIAL_GAIN

`GRAPH_SIMPLIFICATION_PLAN.md` written. **Nothing removed** — §22 requires
review first. The plan is explicit that what is proposed for removal is the
neighbour-trust weighting alone, that the **edge topology stays**, and that a
reviewer who judges the change not worth touching a frozen core is reading the
same evidence defensibly.

### 16. CUSUM DEFINITION

`z_t = (lam_t − mu0)/sigma0` on the **pre-transform** smoothed chi-square;
`S_t = max(0, S_{t−1} + z_t − k)`; alarm when `S_t > h`. `k = 0.5`,
`h = 500`. The rejected invented form `z = max(0, 1−c)·10` is **not** used.
Gated-out samples do not enter the statistic.

§23's gate: mu0/sigma0 re-derived from the v1.1 clean arm, historical
selection rule re-applied.

    h        5    10    20    50   100   200   500   1000
    clean  2681  2067  1343   503   274   132     0      0

Smallest h with zero clean alarms: **500**, identical to the historical
selection. **VERDICT: REUSABLE.** The textbook `h = 5.0` fails again, harder,
and stays a committed negative result.

### 17. TRUST-ONLY RESULT

**NOT MEASURED.** T0/T1 not run.

### 18. SEQUENTIAL-ONLY RESULT

**NOT MEASURED** as an arm. The constant-verification gate did characterise
the single detector, and it found something that matters:

| scenario | node | first alarm | onset | latency |
|---|---|---:|---:|---:|
| `gps_spoof` | gps | 21.16 s | 20.0 | 1.16 s |
| `mag_emi` | mag | 25.08 s | 25.0 | 0.08 s |
| `power_sag` | motor_esc / battery | 30.12 / 30.20 s | 30.0 | 0.12 / 0.20 s |
| `vibration_anomaly` | vibration | 28.08 s | 28.0 | 0.08 s |
| `gps_dropout` | — | no alarm | — | correct: absence is gated out |
| `imu0_bias_drift` | — | **no alarm** | — | **structurally blind** |
| `dual_imu_failure` | — | **no alarm** | — | **structurally blind** |

There is no per-IMU physics chi-square in this construction.

### 19. COMBINED RESULTS

**NOT MEASURED.** T3/T4 not run.

### 20. MECHANISM-SPECIFIC RESULTS

Phase 2 covered nine scenarios; Phase 3A covered the same nine; the B4 gate
covered eight. §26's `STEP_SMALL`/`STEP_LARGE`/`INTERMITTENT` rows have no
scenario in the frozen catalogue and are recorded as such rather than
invented. Transport starvation, battery sentinel and mag sentinel reach
diagnosis only as `gate → 0`, the mechanism `gps_dropout` demonstrates.

### 21. CLEAN CONTROLS

`clean`: 0 assurance transitions in **both** arms; 1424/1500 ticks
`EVIDENCE_BACKED`; 0 prior-sensitive ticks; 0 CUSUM alarms at `h = 500`; 0
UNKNOWN under the audited criterion. **This is a deterministic replay control,
not a field false-alarm rate**, and it is not offered as one.

### 22. COMPUTE

GRAPH vs FLAT: no measurable difference (§14). B4: 0.16–0.70 µs/tick in the
historical record. No embedded or target-hardware figure exists and none is
claimed.

### 23. RECOMMENDED v1.1 ARCHITECTURE AFTER ABLATION

**No change yet.** The graph question is answered; the sequential and
combination questions are not. It is tempting to read "graph doesn't help" +
"CUSUM fires in 0.08 s" as `FLAT + SEQUENTIAL`, and **the evidence argues
against the simple version of that**: the sequential detector is structurally
blind to the IMU faults, which are where the trust arm does its escalation
work. Sequential cannot replace trust.

### 24. COMPONENTS RECOMMENDED FOR DELETION

One, subject to review: the **neighbour-trust weighting**,
`csia/trust_engine/engine.py:110`. Nothing else. Not the edge topology, which
was never ablated.

### 25. COMPONENTS RETAINED AND WHY

Everything else. The 11 relations and their gates are the evidence supply and
were never in question. The trust recursion is retained because the sequential
alternative cannot cover the IMU family. The diagnosis core is frozen and
unmodified.

### 26. G4 STATUS

**`VALIDATED_SITL`.** Blocker for higher: not replicated on HIL or real
flight; not re-run on a denser graph or a distrusted-hub topology (and §21
forbids inventing one now that the graph is losing).

### 27. G5 STATUS

**`VALIDATED_SITL`.** Blocker for higher: not exercised on real telemetry;
`UNKNOWN` deliberately not implemented.

### 28. EXACT NEXT PHASE

**Phase 3B proper**: build T0–T4, run §26's mechanism matrix, keep
right-censored no-response cases right-censored rather than converting them to
an artificial response time, and complete `ARCHITECTURE_DECISION.md`. Only
then Phase 5 (embedded), because §33 forbids porting an architecture that may
change.

### 29. BLOCKERS

1. **Phase 3B arms not run** — blocks the architecture decision, which blocks
   the C port.
2. **Research campaigns need remeasurement for v1.1** — Phase 1 changed
   ingestion; the v1 numbers stay labelled v1 and were not edited.
3. **No library access** — the sole blocker on G8.
4. **No hardware** — blocks G1, G2, G3.
5. **`current_valid` is an unversioned interface change** from Phase 1; the
   versioned schema is Phase 4.
6. **`MaxAge["gnss.position"] = 1.00 s` vs core `STALE_TIMEOUT_S["gps"] = 0.5 s`**
   — two layers disagree about staleness. Banked, not fixed.

### 30. PRODUCT MATURITY

**M2 — cross-platform simulation validated**, with the caveat stated rather
than hidden: ingestion is fixed and tested on the ArduPilot, PX4 and ULog
paths, but diagnosis and ablation are validated on the **deterministic
scenario catalogue only**.

No C port (M3), no hardware (M4), no aircraft (M5), **zero verified-clean
hours** (M6). Research maturity: **none established**.
