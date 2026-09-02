# CSIA v1.1 — ENGINEERING REVIEW REPORT (PHASES 1–3B)

Engineering only. FIXED / HARDENED / VALIDATED / SIMPLIFIED / IMPROVED.
No novelty language, and none is warranted (§31).

Items 1–30 are the Phases 1–3A report. Items **31–52** are the Phase 3B
additions required by §38 of the Phase 3B brief. Where a Phase 1–3A item was
written while Phase 3B was still unrun, it has been **updated in place and the
update is marked**, not silently rewritten.

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
| Phase 3B | `35409bd` five-arm architecture selection (T0–T4) |
| tests | 971 → **1040** |

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

~~**NOT MEASURED.** T0/T1 not run.~~ **Superseded by §41** — T0 and T1 have
since been run over the full mechanism matrix.

### 18. SEQUENTIAL-ONLY RESULT

~~**NOT MEASURED** as an arm.~~ **Superseded by §42.** What follows is the
constant-verification gate's characterisation of the single detector, written
before T2 existed; it is retained because it is what licensed the arm, and it
found something that matters:

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

~~**NOT MEASURED.** T3/T4 not run.~~ **Superseded by §43 and §44.**

### 20. MECHANISM-SPECIFIC RESULTS

Phase 2 covered nine scenarios; Phase 3A covered the same nine; the B4 gate
covered eight. §26's `STEP_SMALL`/`STEP_LARGE`/`INTERMITTENT` rows have no
scenario in the frozen catalogue and are recorded as such rather than
invented. Transport starvation, battery sentinel and mag sentinel reach
diagnosis only as `gate → 0`, the mechanism `gps_dropout` demonstrates.

**Phase 3B addition:** the same judgement was re-made formally over §26's full
mechanism list and written to `MECHANISM_COVERAGE_MATRIX.csv` — 15 rows, **9
APPLICABLE and 6 INAPPLICABLE with a stated reason on each**. See §32.

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

~~**No change yet.**~~ **Superseded by §48**, which records the decision
`E: TRUST_FLAT_PLUS_SEQUENTIAL`.

The caution written here before the arms were run **survived the measurement
and is now part of the decision**: the sequential detector is structurally
blind to the IMU faults, so `FLAT + SEQUENTIAL` was adopted as a *combination*,
never as sequential replacing trust.

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

~~**Phase 3B proper**~~ — **done.** Superseded by §52.

### 29. BLOCKERS

1. ~~**Phase 3B arms not run**~~ — **cleared.** The architecture decision is
   complete, so §33 no longer blocks the C port.
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

---

# PHASE 3B ADDITIONS (§38, items 31–52)

Everything below is measured by `engineering/v1_1/ablation/run_phase3b.py`
(`make v1-1-phase3b`) and guarded by `tests/test_v1_1_phase3b.py` (18 tests,
`make v1-1-phase3b-check`). Raw data: `PHASE3B_ARCHITECTURE_RESULTS.csv`,
`PHASE3B_PAIRED_DIFFERENCES.csv`, `PHASE3B_SUMMARY.json`.

**Reading convention, used everywhere below.** `censored` means *no response*.
It is recorded as `None` with `detection_censored = True` and is **never**
converted into a latency equal to the window end (§8). A test enforces it.

### 31. PHASE 3B ARM DEFINITIONS

Five arms over the **same** trace, same tick loop, same frozen diagnosis.

| arm | trust weighting | sequential | detection response |
|---|---|---|---|
| **T0** `TRUST_FLAT` | `w = gate_e` | none | first failsafe-level change at/after onset |
| **T1** `TRUST_GRAPH` | `w = gate_e · trust[other]` (production) | none | same |
| **T2** `SEQUENTIAL_ONLY` | not consulted for the endpoint | CUSUM bank | first CUSUM crossing |
| **T3** `TRUST_FLAT_PLUS_SEQ` | `w = gate_e` | CUSUM bank | **earliest of the two** |
| **T4** `TRUST_GRAPH_PLUS_SEQ` | production | CUSUM bank | **earliest of the two** |

The flat arms use `FlatTrustCore`, which **subclasses the frozen `TrustCore`,
sets `self.trust` to 1.0 and calls `super().step()` verbatim**. No frozen
method is copied; a test greps for a copied body after stripping docstrings and
comments. The ablation is therefore exactly one factor — `trust[other]` — and
nothing else.

The CUSUM is the Phase 3B gate's frozen definition, unchanged: `k = 0.5`,
`h = 500`, on the pre-transform smoothed chi-square, gated samples excluded
(§16, `SEQUENTIAL_DETECTOR_SPEC.md`). **Page's 1954 CUSUM. No algorithmic
novelty is claimed and none exists.**

T3 and T4 combine by taking the earliest response. They do **not** feed the
CUSUM output into the diagnosis — see §33 and the identifiability result in
§37.

### 32. MECHANISM COVERAGE

`MECHANISM_COVERAGE_MATRIX.csv` — 15 rows, decided **before** results and
recorded with a reason on every exclusion.

**9 APPLICABLE:** `CLEAN`, `GNSS_RAMP_SLOW`, `GNSS_RAMP_FAST`,
`GNSS_FIX_LOSS`, `IMU0_BIAS_DRIFT`, `DUAL_IMU_FAILURE`, `MAG_DEGRADED`,
`POWER_SAG`, `VIBRATION_ANOMALY`.

**6 INAPPLICABLE, each with a stated reason:**

| row | reason |
|---|---|
| `GNSS_STEP_SMALL` / `GNSS_STEP_LARGE` | **no step/offset injector exists.** `KNOWN_KINDS = {bias_drift, dropout, emi_spike, gps_spoof, vibration_anomaly, power_sag}`; `gps_spoof` takes a drift velocity and is therefore a ramp. §5/§28 forbid building injection machinery in this phase |
| `GNSS_TRANSPORT_STARVATION` | in this simulator `dropout` **is** transport starvation at the CSIA boundary — the same injection as `GNSS_FIX_LOSS`. Counting it twice would inflate the matrix |
| `MAG_INVALID` | the all-zero magnetometer sentinel is an **ingest-layer** condition, fixed and regression-tested in Phase 1 |
| `BATTERY_SENTINEL` | as `MAG_INVALID`: ingest-layer, Phase 1. Reaches diagnosis only as `gate → 0` |
| `BARO_FAULT` | no baro fault kind in `KNOWN_KINDS`, and `baro`'s clean-arm σ₀ is degenerate, so it carries no sequential residual either |

A test asserts every arm appears for every APPLICABLE mechanism. **No mechanism
was excluded after seeing a result** — the matrix is derived from
`KNOWN_KINDS` and the B4 in-control node list, both of which predate the run.

### 33. MATCHING PROOF

§4 requires that arms differ **only** in the component under test. Three
hashes are computed per mechanism and compared across all five arms:

| hash | over |
|---|---|
| `raw_trace_sha256` | `td.t` and every relation's raw residual series |
| `canonical_input_sha256` | every node's freshness series and every physics λ series |
| `relation_bank_sha256` | every relation's residual **and** its gate |

`test_all_arms_share_the_three_matching_hashes` asserts each hash has exactly
one distinct value per mechanism across the five arms. It holds on all nine.
**If it ever fails the comparison is invalid, not merely noisy.**

Stronger, and worth stating: all five arms consume the **same `td` object in
memory**. The arms are post-hoc readings of one pipeline run, so there is no
opportunity for the inputs to drift. The hashes are the check that this is
actually what the code does.

`test_support_metadata_is_identical_across_arms` adds the diagnosis side:
`correct_unique`, `safe_ambiguity`, `wrong_unique`, `unsupported_unique` and
`unavailable` have one distinct value per mechanism across all five arms.

### 34. CLEAN CONTROLS

| | |
|---|---|
| CUSUM alarms on clean at `h = 500` | **0** |
| detection response, every arm | **censored** — no assurance transition |
| `WRONG_UNIQUE` ticks, every arm | **0** |
| `SAFE_AMBIGUITY` ticks | 76 — the startup window before GPS becomes fresh |
| flat vs graph assurance transitions | identical |

The 76 ambiguous ticks are **initialisation, not a defect**: before GPS is
fresh the leader cannot be separated from `gps_fault`, and v1.1 says so where
v1 would have reported an ordinary unique diagnosis.

**This is a deterministic replay control, not a field false-alarm rate**, and
it is not offered as one. `PHASE3B_CLEAN_RESULTS.json` says so in the artifact
itself.

One label needs explaining rather than defending: on `CLEAN` the T2 row reads
`NO_SEQUENTIAL_COVERAGE`, because the coverage flag is "did any node alarm".
On the clean arm zero alarms is the **desired** outcome, so that label here
means "correctly silent", not "gap". On `GNSS_FIX_LOSS`, `IMU0_BIAS_DRIFT` and
`DUAL_IMU_FAILURE` the same label does mean a real gap.

### 35. GNSS STEP RESULTS

**NOT MEASURED. No step injector exists.**

`KNOWN_KINDS` in `csia/sensors/faults.py` contains no step or offset kind, and
`gps_spoof` is parameterised by a drift **velocity**, which makes it a ramp.
Building one would be new injection machinery, which §5 and §28 forbid in this
phase.

**The ramp results in §36 must not be read as covering steps.** A step is the
easier detection problem for a CUSUM and the harder one for a slowly-adapting
trust recursion, so the untested case is the one where the two arms would most
plausibly diverge. Recorded as a known gap in `ARCHITECTURE_DECISION.md` §7.2
and in the graduation matrix, not glossed.

### 36. GNSS RAMP RESULTS

Onset 20.0 s in both.

| | T0 flat | T1 graph | T2 seq | T3 flat+seq | T4 graph+seq | diagnosis |
|---|---:|---:|---:|---:|---:|---|
| `GNSS_RAMP_SLOW` | 32.48 s | 32.48 s | **24.40 s** | **24.40 s** | **24.40 s** | **never attributes** — 0 correct-unique ticks |
| `GNSS_RAMP_FAST` | 24.36 s | 24.36 s | **21.16 s** | **21.16 s** | **21.16 s** | 340 correct-unique, first at 21.44 s |

`GNSS_RAMP_SLOW` is the single strongest result for the sequential channel and
it is **not** just an 8.08 s latency win: the frozen diagnosis produces **zero**
correct-unique ticks on a slow drift, so without the CUSUM the mechanism is
covered only by a late trust transition and is never named at all.

`GNSS_RAMP_SLOW` is a declared **parameter variation** of the frozen
`gps_spoof` kind (slower drift), not a new fault type. `GNSS_RAMP_FAST` is the
catalogue scenario as-is.

### 37. FIX-LOSS RESULTS

The mechanism that decides the architecture.

| | |
|---|---|
| T0 / T1 / T3 / T4 detection | **26.00 s** |
| T2 sequential | **censored** — `NO_SEQUENTIAL_COVERAGE` |
| support response | **25.00 s** — support correctly reports loss of identifiability at onset |
| `SAFE_AMBIGUITY` ticks | **200** in every arm |
| `CORRECT_UNIQUE` ticks | **0** in every arm |

A dropout is **absence of evidence**. The gate goes to zero, the residual stops
existing, and a CUSUM on a stream that has stopped cannot fire — **correctly**.
This is not a detector miss and is not scored as one.

§11 is satisfied by construction and confirmed by measurement: the leader
remains `NON_IDENTIFIABLE / AMBIGUOUS` for 200 of 201 ticks in **every arm,
including the two carrying a sequential channel**. `test_a_sequential_alarm_
never_promotes_an_unidentifiable_cause` enforces it. The CUSUM output never
enters the diagnosis, so an alarm cannot manufacture an attribution — and the
200 ambiguous ticks are exactly what v1 would have presented as an ordinary
unique diagnosis at posterior 0.9998.

### 38. IMU RESULTS

| | T0 flat | T1 graph | T2 seq | T3 | T4 | diagnosis |
|---|---:|---:|---:|---:|---:|---|
| `IMU0_BIAS_DRIFT` | censored | censored | **censored** | censored | censored | **104 correct-unique**, first at 33.04 s |
| `DUAL_IMU_FAILURE` | **34.12 s** | 34.40 s | **censored** | **34.12 s** | 34.40 s | no correct hypothesis exists |

**The sequential bank has no per-IMU residual at all.** In-control statistics
exist for `gps`, `mag`, `battery`, `motor_esc`, `vibration` — five nodes.
`baro` is degenerate. There is no IMU physics chi-square in this construction,
so `sequential_covered = False` on both rows and
`test_the_imu_mechanisms_have_no_sequential_coverage` pins it.

**This is the fact that stops a misleading "sequential wins" conclusion**, and
it is why trust is retained.

Two readings that would be wrong, stated so they are not made:

- `IMU0_BIAS_DRIFT` censored in **all** arms is **not a miss**. The failsafe
  policy's `att_caution` is on `max(imu0, imu1)`; one IMU degrading while the
  other holds is redundancy working as designed. The diagnosis still names it
  correctly and identifiably on 104 ticks. "Detected and named, no escalation
  warranted."
- `DUAL_IMU_FAILURE` reports **585 `WRONG_UNIQUE`** ticks. That is honest
  accounting, not a defect discovered here: two simultaneous faults are
  injected against a **single-fault** model, so no modeled hypothesis is
  correct and truth is `None` by construction. It is the one mechanism where
  the modelling assumption is knowingly violated.

### 39. TRANSPORT RESULTS

**Not a separate measurement.** `GNSS_TRANSPORT_STARVATION` is INAPPLICABLE
because in this simulator the `dropout` kind **is** transport starvation at the
CSIA boundary: no samples arrive, freshness lapses, and the gate goes to zero.
That is the identical injection already measured as `GNSS_FIX_LOSS` in §37.

Reporting it as a second mechanism would have made the matrix look broader
than the evidence is. What §37 measures — trust responds at 26.00 s, sequential
is structurally censored, support flags loss of identifiability at 25.00 s —
**is** the transport-starvation result.

A genuine transport fault distinguishable from sensor dropout (link loss with
the sensor healthy, MAVLink rate starvation, a wedged serial port) is **not**
represented in the frozen catalogue and is not claimed.

### 40. SENTINEL REGRESSIONS

Both sentinel rows are INAPPLICABLE as Phase 3B *mechanisms* because they are
**ingest-layer** conditions, fixed and regression-tested in Phase 1. They reach
diagnosis only as `gate → 0`.

| | condition | v1 behaviour | v1.1 behaviour |
|---|---|---|---|
| **D1** | `current_battery = -1` after a real 5.00 A reading | `5.0 A`, present | absent, `SENTINEL` |
| **D2** | all-zero magnetometer triple | previous field, present | absent, `SENTINEL` |
| **D3** | ULog `current_a == -1.0` | `-1.0 A`, valid | absent, invalid |
| **D4** | plugins `current_battery = -1` | `0.0 A`, valid | absent, invalid |
| **D5** | GNSS `fix_type < 3` *(control)* | absent, `NO_3D_FIX` | **unchanged** |

Guard: `tests/test_v1_1_canonical_ingest.py`, 13 tests, `make
v1-1-ingest-check`. **All still pass at the Phase 3B commit**, on the same
pre-fix/post-fix hashed records (`7fdd3d65…` / `7fff288a…`), with D5 the
byte-identical control.

**No sentinel regression was introduced by Phase 3B**, which is expected —
Phase 3B adds no production code and reads the frozen pipeline only.

### 41. TRUST-ONLY RESULT (T0, T1)

| mechanism | T0 `TRUST_FLAT` | T1 `TRUST_GRAPH` |
|---|---:|---:|
| `CLEAN` | censored | censored |
| `GNSS_RAMP_SLOW` | 32.48 s | 32.48 s |
| `GNSS_RAMP_FAST` | 24.36 s | 24.36 s |
| `GNSS_FIX_LOSS` | **26.00 s** | **26.00 s** |
| `IMU0_BIAS_DRIFT` | censored | censored |
| `DUAL_IMU_FAILURE` | **34.12 s** | 34.40 s |
| `MAG_DEGRADED` | 30.04 s | 30.04 s |
| `POWER_SAG` | 33.72 s | 33.72 s |
| `VIBRATION_ANOMALY` | 34.16 s | 34.16 s |

Trust responds on **6 of 9** mechanisms and is the **sole** responder on two
(`GNSS_FIX_LOSS`, `DUAL_IMU_FAILURE`). T0 and T1 are identical everywhere
except `DUAL_IMU_FAILURE`, where flat is 0.28 s **earlier**. This reproduces
Phase 3A exactly.

### 42. SEQUENTIAL-ONLY RESULT (T2)

| mechanism | T2 | node(s) alarming | onset | latency |
|---|---:|---|---:|---:|
| `GNSS_RAMP_SLOW` | **24.40 s** | `gps` | 20.0 | 4.40 s |
| `GNSS_RAMP_FAST` | **21.16 s** | `gps` | 20.0 | 1.16 s |
| `MAG_DEGRADED` | **25.08 s** | `mag` | 25.0 | **0.08 s** |
| `POWER_SAG` | **30.12 s** | `battery`, `motor_esc`, `vibration` | 30.0 | **0.12 s** |
| `VIBRATION_ANOMALY` | **28.08 s** | `vibration` | 28.0 | **0.08 s** |
| `CLEAN` | censored | — | — | **0 alarms — correct** |
| `GNSS_FIX_LOSS` | censored | — | — | absence is gated out — correct |
| `IMU0_BIAS_DRIFT` | censored | — | — | **no IMU residual exists** |
| `DUAL_IMU_FAILURE` | censored | — | — | **no IMU residual exists** |

Covers **5 of 9**, and is **earlier than trust on every one of those five**.
Sub-100 ms on two. Right-censored on four, three of them for a structural
reason and one (`CLEAN`) because silence is the correct answer.

**Sequential alone is not a viable architecture**: it has no cover for
`GNSS_FIX_LOSS` or `DUAL_IMU_FAILURE`.

### 43. FLAT + SEQUENTIAL RESULT (T3)

| mechanism | T3 | source of the response |
|---|---:|---|
| `CLEAN` | censored | — |
| `GNSS_RAMP_SLOW` | **24.40 s** | sequential |
| `GNSS_RAMP_FAST` | **21.16 s** | sequential |
| `GNSS_FIX_LOSS` | **26.00 s** | **trust** |
| `IMU0_BIAS_DRIFT` | censored | — (correct, §38) |
| `DUAL_IMU_FAILURE` | **34.12 s** | **trust** |
| `MAG_DEGRADED` | **25.08 s** | sequential |
| `POWER_SAG` | **30.12 s** | sequential |
| `VIBRATION_ANOMALY` | **28.08 s** | sequential |

**8 of 9 mechanisms responded** — every one where a response is warranted. The
two components cover disjoint sets and the union is complete over the
catalogue: sequential supplies five, trust supplies the two it alone can see.

### 44. GRAPH + SEQUENTIAL RESULT (T4)

Identical to T3 on **8 of 9** mechanisms. The single difference:

    DUAL_IMU_FAILURE    T4 34.40 s    vs    T3 34.12 s

T4 is **0.28 s later** — the only mechanism where neighbour-trust propagation
changes anything at all, and it changes it for the worse.

### 45. GRAPH INCREMENTAL VALUE

Measured twice, once without the sequential channel and once with it. Positive
= later = worse.

| mechanism | `T1 − T0` | `T4 − T3` |
|---|---:|---:|
| `GNSS_RAMP_SLOW` | 0.00 | 0.00 |
| `GNSS_RAMP_FAST` | 0.00 | 0.00 |
| `GNSS_FIX_LOSS` | 0.00 | 0.00 |
| `MAG_DEGRADED` | 0.00 | 0.00 |
| `POWER_SAG` | 0.00 | 0.00 |
| `VIBRATION_ANOMALY` | 0.00 | 0.00 |
| `DUAL_IMU_FAILURE` | **+0.28** | **+0.28** |
| `CLEAN` | — both censored | — both censored |
| `IMU0_BIAS_DRIFT` | — both censored | — both censored |

**Zero benefit on every mechanism; one regression of 0.28 s.** Adding the
sequential channel does not rescue propagation — the incremental value is
unchanged.

Attribution **cannot** be affected: `csia/diagnosis/bayes.py` imports only
`consistency` from the trust engine and never reads `TrustHistory.trust`. This
is a structural fact about the frozen code, not a measurement, and it means all
of `correct_unique`, `safe_ambiguity` and support are identical across arms by
construction.

Compute is not a tie-breaker either way — the paired differences straddle zero
(§14, §47). **The graph is cheap. The case against it is the absence of
benefit, not the presence of cost.**

`GRAPH_TOPOLOGY ≠ NEIGHBOUR-TRUST PROPAGATION.` What loses is one factor on
one line. The relation bank is **not** implicated and is retained in full.

### 46. SEQUENTIAL INCREMENTAL VALUE

| mechanism | `T3 − T0` | `T4 − T1` |
|---|---:|---:|
| `GNSS_RAMP_SLOW` | **−8.08** | **−8.08** |
| `VIBRATION_ANOMALY` | **−6.08** | **−6.08** |
| `MAG_DEGRADED` | **−4.96** | **−4.96** |
| `POWER_SAG` | **−3.60** | **−3.60** |
| `GNSS_RAMP_FAST` | **−3.20** | **−3.20** |
| `GNSS_FIX_LOSS` | 0.00 | 0.00 |
| `DUAL_IMU_FAILURE` | 0.00 | 0.00 |
| `CLEAN` | — both censored | — both censored |
| `IMU0_BIAS_DRIFT` | — both censored | — both censored |

**Improves 5 of 9. Regresses none. Zero clean alarms.** The improvement is the
same on flat and graph trust, so the two components are independent in this
catalogue.

`SEQUENTIAL DETECTION ≠ COMPLETE FAULT COVERAGE.` The channel wins on ramps
and is blind to the IMU family, so it is added, not substituted.

### 47. COMPUTE / MEMORY

**Compute** — Python microbenchmark, µs per tick, n = 9 runs each:

| arm | median | min |
|---|---:|---:|
| T0 `TRUST_FLAT` | 126.14 | 124.47 |
| T1 `TRUST_GRAPH` | 128.11 | 125.98 |
| T3 `TRUST_FLAT_PLUS_SEQ` | 129.85 | 123.47 |
| T4 `TRUST_GRAPH_PLUS_SEQ` | 128.80 | 122.93 |

**The distributions overlap and the minima are out of rank order** (T4's min is
below T0's). Read as **no measurable difference between architectures**, not as
a ranking. T2 carries no trust arm and is not comparable on this axis, so it is
not benchmarked. This is CPython on a general-purpose host; **no embedded or
target-hardware figure exists and none is claimed.**

**Memory** — mutable inter-tick state, `PHASE3B_MEMORY_STATE.json`:

| | floats | bytes @ 8 |
|---|---:|---:|
| trust recursion (α, β) | 16 | 128 |
| trust carried between ticks for propagation | 8 | 64 |
| sequential CUSUM `S`, per covered node | **5** | **40** |
| diagnosis smoothing, per hypothesis | 8 | 64 |

Sequential is the **cheapest component in the system** — 5 floats and one
comparison per covered node per tick — and it buys 3.20–8.08 s on five
mechanisms.

Removing propagation deletes the inter-node read of `trust[]` inside the
neighbour weight. It does **not** delete `trust[]`, which is still computed
from α/β and still reported. The planned C structs are recorded for Phase 5.

### 48. FINAL ARCHITECTURE DECISION

    E:  TRUST_FLAT_PLUS_SEQUENTIAL

§21 requires exactly one of A–F, and this is one, not "hybrid TBD".

| component | decision |
|---|---|
| neighbour-trust propagation | **REMOVE** — subject to review (§30) |
| trust recursion | **KEEP** |
| sequential (CUSUM) channels | **KEEP** |
| support-aware diagnosis | **KEEP** |
| relation topology, all 11 relations | **KEEP** |
| `UNKNOWN` / unmodeled | **remains NOT IMPLEMENTED** |

Three findings decide it, and none of them is a preference:

1. Sequential improves 5 of 9 with zero regressions and zero clean alarms
   (§46), and on `GNSS_RAMP_SLOW` it is the **only** thing that responds in
   useful time because the diagnosis never attributes a slow drift.
2. Trust is the **sole** cover for `GNSS_FIX_LOSS` and `DUAL_IMU_FAILURE`
   (§37, §38), so sequential cannot replace it.
3. Propagation has zero benefit anywhere and one 0.28 s regression, both with
   and without the sequential channel (§45), and it cannot affect attribution
   at all.

All four of §18's removal conditions hold for propagation, including the
tie-breaker that flat is equal or earlier on every meaningful response.

Full record: `ARCHITECTURE_DECISION.md`.

### 49. COMPONENTS TO REMOVE

**Exactly one factor, on exactly one line.** Nothing else.

    file:  csia/trust_engine/engine.py
    line:  110
    from:  w = float(gate_e) * self.trust[other]
    to:    w = float(gate_e)

**Nothing has been executed.** §30 requires review before the deletion commit;
`csia/trust_engine` is FROZEN and carries zero diff at this commit. The staged
plan (`GRAPH_SIMPLIFICATION_PLAN.md` §4) is: freeze and hash the current trust
matrices → carry a versioned flag rather than deleting, **breaking the freeze
on purpose and recording it** → re-measure everything that consumes trust
trajectories → re-run Phase 3A with the flag flipped and confirm bit-for-bit
agreement → only then decide the default.

Stated in the plan and repeated here: **a reviewer who judges that removing a
coupling is not worth a production change to a frozen core is reading the same
evidence defensibly.** The data compels not *claiming* the graph helps. It does
not compel removal.

### 50. COMPONENTS TO RETAIN

| component | why |
|---|---|
| **trust recursion** | sole cover for `GNSS_FIX_LOSS` and `DUAL_IMU_FAILURE`; the sequential bank has no IMU residual |
| **sequential CUSUM bank** | 3.20–8.08 s earlier on five mechanisms, zero regressions, zero clean alarms, 40 bytes of state |
| **relation topology, all 11 relations, all gates** | **never ablated.** They are the evidence supply. `GRAPH_TOPOLOGY ≠ NEIGHBOUR-TRUST PROPAGATION` |
| **node definitions, relation ownership, source mappings** | not implicated by any measurement |
| **support-aware diagnosis** | identical across all five arms; it is what turns a 0.9998 posterior with no discriminating evidence into `SAFE_AMBIGUITY` |
| **frozen diagnosis core** | unmodified, zero diff |

`UNKNOWN` stays unimplemented (§24): the threshold-free set-adequacy criterion
was built and measured, and adopting it needs either a tolerance (the forbidden
threshold) or adjudication against fault labels (the forbidden circularity).
The audit script is retained as evidence, wired into nothing.

### 51. PHASE 3C FEASIBILITY

§28 forbade adding an IMU sequential residual in this phase, and **none was
added** — a test asserts `imu_cusum.py` does not exist. §33's short audit was
done instead.

    OPEN_ENGINEERING_QUESTION:
    The v1.1 architecture retains trust SOLELY because the sequential bank has
    no IMU residual. Would an established IMU change detector permit removing
    or simplifying trust?

**For `DUAL_IMU_FAILURE`:** cheap and standard. The `redundant_imu` relation
already produces a per-tick λ that the layer already computes. A CUSUM on that
standardised residual is the same established statistic, on an existing stream.
No new sensor, no new message, no new mathematics.

**For `GNSS_FIX_LOSS`:** a detector is the wrong tool. Fix loss is **absence of
evidence** — the gate goes to zero and the residual stops existing. A CUSUM on
a stopped stream cannot fire and should not. This is a freshness-and-support
question, already handled by Phases 1 and 2.

**Consequence: trust cannot be removed even if Phase 3C succeeds.** The
realistic upside is simplification of trust's role, not deletion — materially
less than it first appears, and better said now than after building it.

    PHASE 3C NEEDED:  NO

Recommendation: **do not start Phase 3C.** The architecture is decided and
stable enough to freeze; adding a detector now would change the very
architecture Phase 5 is meant to port, which is what §33 warns against. If it
is wanted anyway, its scope is **one** CUSUM on the existing `redundant_imu`
residual with the same `k = 0.5` and the same zero-clean-alarm `h` selection
rule, measured against the same nine mechanisms before anything is retained.

### 52. EXACT NEXT STEP

**Phase 4 — function eligibility, assurance ledger, output API.** Not Phase 3C
(§51), and not yet Phase 5.

`FUNCTION_ELIGIBILITY_INPUT_REQUIREMENTS.md` is written as **preparation only**
— it enumerates what a future deterministic policy table may read (`trust`,
`fresh`, `missing_reason`, `sequential_alarm`, `leader`, `posterior`,
`active_evidence_count`, `discriminating_evidence`, `leader_identifiable`,
`ambiguity`, `prior_sensitive`, `support_state`, `assurance_level`) and what it
must **not** read: `UNKNOWN` (unimplemented), a high posterior alone, a
sequential alarm as cause attribution, or anything learned. **No eligibility
policy is implemented.**

Two things gate Phase 5 (the C/C++ port) and neither is a measurement:

1. **The §30 review of the propagation removal.** Phase 5 should port the
   architecture that is actually going to ship, and that line is still open.
2. **No golden-trace corpus or equivalence tolerance spec exists yet.** G6 is
   `NOT_STARTED` — now unblocked by the architecture decision, but unstarted.

Also outstanding, unchanged by Phase 3B: research campaigns still need
remeasurement for v1.1; `current_valid` is still an unversioned interface
change; the `MaxAge` / `STALE_TIMEOUT_S` disagreement is still banked; library
access is still the sole blocker on G8; and hardware is still the blocker on
G1–G3.
