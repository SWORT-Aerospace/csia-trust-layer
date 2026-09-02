# CSIA v1.1 — ENGINEERING REVIEW REPORT (PHASES 1–4.5)

Engineering only. FIXED / HARDENED / VALIDATED / SIMPLIFIED / IMPROVED.
No novelty language, and none is warranted (§31).

Items **1–30** are the Phases 1–3A report, **31–52** the Phase 3B additions,
**53–74** the Phase 4 additions and **75–92** the Phase 4.5 additions. Where an
earlier item was written while a later phase was still unrun, it has been
**updated in place and the update is marked**, not silently rewritten.

**Two Phase 4 claims are corrected by Phase 4.5**, in §77 and §78, rather than
quietly dropped: the predicted PX4 `motor_esc` exposure is not reachable, and
the node-timeout rule is `max` over required channels rather than `min`.

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
| Phase 4A | `b9fc5d6` versioned trust mode + architecture freeze |
| Phase 4B | `8260736` function eligibility |
| Phase 4C | `3ca0f32` assurance ledger |
| Phase 4D | `bf6a19e` output API, firewall, freeze |
| Phase 4.5 A+B | `5490cce` trust-mode decision + staleness closure |
| Phase 4.5 C | `dfedac5` csia-monitor, the first real consumer |
| Phase 4.5 freeze | this commit — golden corpus, numeric spec, Phase 5 authorization |
| tests | 971 → **1211** |

**Frozen core: zero diff.** `csia/trust_engine`, `csia/diagnosis`,
`csia/runtime/online.py`, `csia/runtime/failsafe.py`, `csia/scenarios.py`,
`csia/profiles.py`. Phases 2, 3, 4 and 4.5 are entirely read-only over it —
they add `csia/v1_1/` one level above the freeze and touch nothing inside it.
Phase 4.5's staleness fix is an argument passed to `OnlineTrustLayer`, which
already accepted it; the frozen default table is unedited.

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

---

# PHASE 4 ADDITIONS (§46, items 53–74)

Everything below is produced by `engineering/v1_1/phase4/run_p4{a,b,c,d}.py`
(`make v1-1-p4a` … `v1-1-p4d`) and guarded by four test files:
`test_v1_1_trust_mode.py` (24), `test_v1_1_eligibility.py` (27),
`test_v1_1_ledger.py` (17), `test_v1_1_output_api.py` (25).

### 53. PHASE 3 ARCHITECTURE APPROVAL

`E: TRUST_FLAT_PLUS_SEQUENTIAL` was approved and Phase 4 implemented it as
approved. Nothing in the decision was revisited.

    KEEP    11 relations, topology, node definitions, flat trust recursion,
            diagnosis core, sequential CUSUM bank, support-aware diagnosis,
            canonical ingestion
    REMOVE  neighbour-trust propagation FROM THE DEFAULT

**`csia/trust_engine/engine.py:110` still contains
`w = float(gate_e) * self.trust[other]`. Nothing was deleted.** The frozen
core carries **zero diff** against `csia-v1.0-research-final` at this commit,
enforced by both the git-diff and the recorded-SHA-256 guards. The default
simply no longer selects that line.

### 54. TRUST-MODE VERSIONING

    LEGACY_NEIGHBOR_PROPAGATION   w = float(gate_e) * self.trust[other]
    FLAT_V1_1                     w = float(gate_e)          <-- DEFAULT

**The flag is not in the engine, and that is a decision, not an omission.**
The brief asks for both "FLAT is the default" and "frozen v1 must remain
reproducible"; editing the frozen engine would have satisfied the first by
breaking the second. `GRAPH_SIMPLIFICATION_PLAN.md` §4 S2 named this
alternative in advance — carry the flag in a layer above the freeze — and that
is what `csia/v1_1/trust_mode.py` does.

**LEGACY returns the frozen `TrustCore` class itself, not a copy.** There is
no second implementation of the v1 trust update to keep in sync, so legacy
behaviour cannot drift from v1. FLAT subclasses it and neutralises one factor;
a test parses the AST and fails if the frozen `step` body is ever copied in.

`trust_mode_of()` **raises** on an unknown string rather than defaulting: a
typo that silently selected FLAT would change which architecture produced a
flight record. The resolved mode rides on every ledger event and every API
payload.

Real-time selection is a plain attribute assignment (`OnlineTrustLayer.core`);
the batch path substitutes the class `TrustEngine.run` looks up, scoped and
restored in a `finally`, with a test asserting the restoration. The
alternative was copying `run()`, which is the drift this design exists to
prevent.

### 55. ARCHITECTURE FREEZE

`V1_1_ARCHITECTURE_FREEZE.md` + `.json`. Written only after §3's regression
returned PASS.

**§3's STOP gate. Tolerance declared 0.0 BEFORE running.**

| axis | LEGACY vs Phase 3A/3B GRAPH | FLAT_V1_1 vs Phase 3A/3B FLAT |
|---|---|---|
| raw trace / canonical input / relation bank hashes | identical | identical |
| trust trajectory | **bit-identical**, max abs Δ **0.0** | **bit-identical**, max abs Δ **0.0** |
| assurance transitions | identical, times and levels | identical, times and levels |

    VERDICT: PASS.  Tolerance needed: 0.0.

No tolerance was needed, which is the expected result of the construction: if
one had been, something would have been re-implemented that should not have
been.

FLAT reproduces the Phase 3B detection times exactly — 32.48 / 24.36 / 26.00 /
34.12 / 30.04 / 33.72 / 34.16 s, nothing on `CLEAN` or `IMU0_BIAS_DRIFT` — and
a separate test derives **T3** from the two reproduced components and compares
it against `PHASE3B_ARCHITECTURE_RESULTS.csv` rather than a copied list.

The CUSUM bank was promoted from the ablation harness to `csia/v1_1/
sequential.py` as the stateful per-tick form Phase 5 ports. Same statistic,
`k = 0.5`, `h = 500`; the online bank's first-alarm index equals the batch
statistic on every mechanism. In-control statistics are **frozen constants**,
not re-estimated at runtime — an in-control statistic re-estimated during a
fault stops being in-control — and a test re-derives them from the clean arm.

Frozen: source SHA, trust mode, `k`/`h`/covered nodes, 11 relations, 8
hypotheses, support semantics, ingest rules R1–R5, schema version 1.1.0.
**Explicitly not frozen: golden-trace numbers, embedded timing, the production
line removal, `UNKNOWN`.**

### 56. FUNCTION SET

Five specified, one omitted.

| function | needs | support policy | assurance boundary |
|---|---|---|---|
| `COARSE_NAVIGATION` | gps | TOLERATE_AMBIGUITY | CRITICAL |
| `POSITION_HOLD` | gps, baro, one IMU | TOLERATE_AMBIGUITY | CRITICAL |
| `PRECISION_NAVIGATION` | gps, mag, one IMU | **REQUIRE_IDENTIFIABLE** | CAUTION |
| `GEOFENCE_SUPPORT` | gps | **REQUIRE_IDENTIFIABLE** | CRITICAL |
| `INERTIAL_CONTINUATION` | baro, one IMU — **no GNSS** | TOLERATE_AMBIGUITY | EMERGENCY |

**`PRECISION_LANDING` is omitted**, per §6's instruction to omit rather than
invent: it needs a rangefinder, optical flow or landing beacon, and none
exists in the node set, in the 11 relations, or in any adapter channel.

`GEOFENCE_SUPPORT` is deliberately **stricter than `COARSE_NAVIGATION` on the
same inputs**. A boundary decision made on a spoofed position is worse than no
boundary decision: it reports "inside" with authority while the vehicle
leaves.

### 57. FUNCTION REQUIREMENT DEFINITIONS

**There is not one new number in `FUNCTION_REQUIREMENTS.yaml`.**

Every trust requirement names a field of the **frozen** `FailsafeConfig` and
inherits its value **by name, resolved at construction** — `nav_caution` 0.75,
`heading_caution` 0.60, `att_caution` 0.82, `att_emergency` 0.70, plus
`dwell_up` 1.0 s and `dwell_down` 5.0 s for the hysteresis. No value is
copied, so the two cannot drift, and a test asserts every `inherits` resolves.
§12 permits a threshold only when it already comes from a declared engineering
requirement; these are the v1 safety path's own.

**Where no declared threshold exists, none is invented.**
`INERTIAL_CONTINUATION` requires barometer *freshness* and states in the file
that it gates on no barometer trust value, because `FailsafeConfig` declares
no barometer threshold.

Requirements are stated as requirements — required sources, redundant groups,
required relations, sensitive hypotheses, support policy, assurance boundary —
never as `if gps_trust > 0.8`.

**Preregistered (§12, gate C).** The file was written and hashed
(`62d9f1f3…`) before any mechanism was evaluated; the runner refuses to run
and a test fails if the hash no longer matches.

### 58. FUNCTION ELIGIBILITY RESULTS

Nine mechanisms × five functions, 83 transitions
(`FUNCTION_ELIGIBILITY_RESULTS.csv`, `FUNCTION_TRANSITIONS.json`).

Transitions **after** the 201-tick startup every mechanism shares (§59).
`E`/`D`/`I` = ELIGIBLE / DEGRADED / INELIGIBLE, with the time in seconds.

| mechanism | COARSE_NAV | POSITION_HOLD | PRECISION_NAV | GEOFENCE | INERTIAL_CONT |
|---|---|---|---|---|---|
| `CLEAN` | — | — | — | — | — |
| `GNSS_RAMP_SLOW` | E→D 25.40, D→I 32.48, I→D 42.28 | E→D 25.40, D→I 32.48, I→D 42.28 | E→D 23.76, D→I 32.48, I→D 42.28 | E→D 23.76, D→I 32.48, I→D 42.28 | — |
| `GNSS_RAMP_FAST` | E→D 22.16, D→I 24.36, I→D 42.88 | E→D 22.16, D→I 24.36, I→D 42.88 | E→D 21.72, D→I 24.36, I→D 42.88 | E→D 21.72, D→I 24.36, I→D 42.88 | — |
| `GNSS_FIX_LOSS` | **E→I 26.00**, I→E 38.00 | **E→I 26.00**, I→E 38.00 | **E→I 26.00**, I→E 38.00 | **E→I 26.00**, I→E 38.00 | **— (ELIGIBLE throughout)** |
| `IMU0_BIAS_DRIFT` | — | — | — | — | **E→D 34.04**, D→E 42.20 |
| `DUAL_IMU_FAILURE` | E→I 49.56 | **E→I 34.12** | **E→I 34.12** | E→I 49.56 | **E→D 32.64, D→I 48.56** |
| `MAG_DEGRADED` | — | — | E→D 26.08, D→I 30.04, I→D 40.04 | — | — |
| `POWER_SAG` | — | — | E→I 34.72, I→E 52.36 | — | — |
| `VIBRATION_ANOMALY` | — | — | E→I 35.16, I→E 53.00 | — | — |

Three details worth reading rather than skimming, each taken from the recorded
reason codes rather than inferred:

- **On both ramps a function degrades well before it is removed**, and the
  `D→I` is always `TRUST_BELOW_INHERITED_REQUIREMENT`. What drives the earlier
  `E→D` differs by mechanism and by function:

      GNSS_RAMP_SLOW  23.76  PRECISION, GEOFENCE   PRIOR_SENSITIVE_LEADER
                      25.40  COARSE, POSITION      SEQUENTIAL_ALARM_ON_REQUIRED_SOURCE
      GNSS_RAMP_FAST  21.72  PRECISION, GEOFENCE   NAMED_CAUSE + SEQUENTIAL_ALARM
                      22.16  COARSE, POSITION      NAMED_CAUSE + SEQUENTIAL_ALARM

  On the **slow** ramp the two `REQUIRE_IDENTIFIABLE` functions move 1.64 s
  earlier than the others, and not because of the detector: the leader is
  prior-driven before it is trusted. That is a Phase 2 signal doing work the
  sequential channel could not do, on the one mechanism where Phase 3B found
  the diagnosis never attributes at all.
- **The sequential channel buys function-level time, not just detection
  time.** On `GNSS_RAMP_SLOW`, `COARSE_NAVIGATION` degrades at 25.40 s —
  the 24.40 s CUSUM alarm plus the inherited 1.0 s `dwell_up` — against a
  `D→I` at 32.48 s driven by trust. **7.08 s of warning that the trust path
  alone would not have given.**
- **The ramps recover to DEGRADED, not to ELIGIBLE.** The `I→D` at 42.28 /
  42.88 s carries `SEQUENTIAL_ALARM_ON_REQUIRED_SOURCE`: trust has recovered
  above `nav_caution` but the CUSUM is still latched. The function is
  available again and the record still says the evidence behind it is reduced.

`POWER_SAG` and `VIBRATION_ANOMALY` go straight `E→I` with no degraded stage,
because what removes `PRECISION_NAVIGATION` there is
`ASSURANCE_BEYOND_FUNCTION_BOUNDARY` — a CRITICAL assurance level against a
declared CAUTION boundary — which is a step, not a slide.

The shape is the one the requirements predict: a GNSS problem removes the GNSS
functions and leaves the inertial fallback; a power or vibration fault
restricts precision work through the assurance boundary while position
knowledge survives; a magnetometer fault touches only the function that needs
heading.

**A rule that was wrong and was changed after seeing results**, disclosed in
`FUNCTION_ELIGIBILITY_SPEC.md` §6 rather than absorbed. The first
implementation fired `PRIOR_SENSITIVE_LEADER` on **any** prior-sensitive
leader, degrading `PRECISION_NAVIGATION` and `GEOFENCE_SUPPORT` for 310 ticks
of `IMU0_BIAS_DRIFT` on a leader neither declares sensitive. §7 says
"affecting **the required information**", so the rule now fires only when the
leader or the uniform-prior leader is one of the function's sensitive
hypotheses. 90 → 83 transitions; every changed cell is a DEGRADED → ELIGIBLE
reclassification on an IMU mechanism, and nothing moved out of INELIGIBLE. The
requirements file did not change, so the preregistration hash stands.

### 59. CLEAN FUNCTION BEHAVIOUR

| | |
|---|---|
| CUSUM alarms | **0** |
| assurance transitions | **0** |
| eligibility transitions | **one per function**, all at t = 8.04 s |
| after that | **stable to the end of the run** |

**The startup window is exactly explained**, which §30 asks for:

    76 ticks   genuine -- before GPS is fresh the leader cannot be separated
               from `gps_fault`, the same 76-tick window Phase 2 measured on
               every scenario including `clean`
  + 125 ticks  dwell_down (5.0 s at 25 Hz), the inherited relaxation delay
  = 201 ticks  = 8.04 s

`COARSE_NAVIGATION` spends them DEGRADED rather than INELIGIBLE because it is
`TOLERATE_AMBIGUITY`; `INERTIAL_CONTINUATION` is unaffected because it does
not require GNSS. **No oscillation anywhere** — the dwell inherits the frozen
failsafe hysteresis rather than introducing one.

This is a **deterministic replay control, not a field false-alarm rate.**

### 60. GNSS FIX-LOSS FUNCTION BEHAVIOUR

The acceptance test, and the reason the layer exists.

At **t = 26.00 s** all four GNSS functions go INELIGIBLE carrying

    REQUIRED_SOURCE_NOT_FRESH
    REQUIRED_RELATION_NOT_APPLICABLE
    SUPPORT_LOST_FOR_REQUIRED_INFORMATION

`INERTIAL_CONTINUATION` stays ELIGIBLE throughout. Support loss is detected at
25.00 s and the eligibility transition follows at 26.00 s — the inherited
`dwell_up` of 1.0 s — coinciding with the assurance transition.

**§10 is proven independently of freshness.** A regression holds GNSS *fresh,
trusted, relations gated in and assurance NORMAL*, changing only the support
verdict:

    leader                        nominal
    posterior                     0.9998
    discriminating vs gps_fault   0
    -> PRECISION_NAVIGATION       INELIGIBLE
    -> required_inputs_available  True     <-- the inputs were all present
    -> GEOFENCE_SUPPORT           INELIGIBLE
    -> COARSE_NAVIGATION          DEGRADED (TOLERATE_AMBIGUITY)
    -> INERTIAL_CONTINUATION      ELIGIBLE

The control test changes only the support verdict back and gets ELIGIBLE. **A
high posterior alone never carries a function.**

### 61. IMU FUNCTION BEHAVIOUR

§32's distinction, and the two cases do not look the same.

| | `IMU0_BIAS_DRIFT` | `DUAL_IMU_FAILURE` |
|---|---|---|
| `POSITION_HOLD` | **ELIGIBLE** — untouched | **INELIGIBLE at 34.12 s** |
| `PRECISION_NAVIGATION` | **ELIGIBLE** — untouched | **INELIGIBLE at 34.12 s** |
| `INERTIAL_CONTINUATION` | **DEGRADED at 34.04 s** | **DEGRADED 32.64 s → INELIGIBLE 48.56 s** |
| reason | `NAMED_CAUSE_AFFECTS_FUNCTION` | `TRUST_BELOW_INHERITED_REQUIREMENT` |

One IMU degrading is **redundancy working**: the requirement is on
`max(imu0, imu1)` against `att_caution`, exactly as the frozen failsafe policy
computes it, so no navigation function is removed. What *is* recorded is that
the fallback is degraded — the diagnosis names `imu0_bias_drift`
identifiably on 104 ticks, and redundancy has been consumed.

Losing both crosses `att_caution` (nav functions) and then `att_emergency`
(the fallback). **The system says plainly that there is no inertial fallback
left**, which is the honest and uncomfortable answer.

### 62. ASSURANCE LEDGER

`csia/v1_1/ledger.py`, spec in `ASSURANCE_LEDGER_SPEC.md`.

Five things open an event: assurance state, function eligibility, support
state, ambiguity, sequential alarm set. **Per-tick sampling is not a ledger** —
1500 ticks × nine mechanisms produced **159 events**, every one a state change
with a reason. Order within a tick is fixed (assurance, functions in sorted
name order, support, ambiguity, sequential) because a ledger whose event order
depended on dict iteration would not reproduce.

Every §16 field is carried. Two are easy to lose and are not:

- **`suppression_reasons`** distinguishes `GATE_CLOSED` (the check did not
  apply) from `ENDPOINT_NOT_FRESH:<node>` (a sensor went away). The frozen
  runtime multiplies every edge gate by both endpoints' freshness
  (`online.py:610`), so both produce a zero gate and collapsing them would
  lose the distinction Phase 2 exists to preserve.
- **`configuration_hash`** covers the requirements, the reason codes and the
  five v1.1 runtime modules. A ledger that looked identical across a policy
  change would be worthless.

**The event the whole layer exists for** — `GNSS_FIX_LOSS`, t = 26.00 s:

    trust["gps"]                     0.987      <-- the sensor looks healthy
    fresh["gps"]                     false
    leader / posterior               nominal / 0.992
    discriminating_evidence_count    0
    support_state                    NON_IDENTIFIABLE
    suppressed_relations             altitude_baro, heading_course,
                                     velocity_gps_doppler
    suppression_reasons              all: ENDPOINT_NOT_FRESH:gps
    function_eligibility             four GNSS functions INELIGIBLE,
                                     INERTIAL_CONTINUATION ELIGIBLE
    recommendations                  RESTRICT_PRECISION_NAV,
                                     INHIBIT_GPS_MODES, SWITCH_NAV_INERTIAL

**GPS trust is 0.987 and every GNSS function is ineligible.** A trust-only
system reading the first number would have reported the GPS healthy.

### 63. LEDGER DETERMINISM

    event_id = sha256({"seq": n, "content": content_sha256})[:32]

Hashes of content and timing. **No random UUIDs**, as §17 requires — an
identifier that changed on replay would make reproduction unprovable. A test
parses the AST rather than grepping, because the module's docstring uses the
word "random" precisely to explain that none is used.

Every mechanism is built **twice**, in two independent `AssuranceLedger`
instances, and compared including every id and hash:

| | |
|---|---|
| mechanisms | 9 |
| total events | **159** |
| identical on rerun | **9 of 9** |
| chain verified | **9 of 9**, zero problems |

`verify_chain()` re-derives every hash from the stored content rather than
trusting the stored hash, so it fails on a hand-edited file. A test tampers
with an event and swaps two events, and both are caught.

**The hash chain is a hash chain and nothing more** (§18): `content_sha256`
plus `previous_event_hash`, genesis of 64 zeros, for detecting a missing or
reordered event. It is **not a blockchain**, not distributed, not tamper-proof
against anyone who can rewrite the file. Stated in the module, in the spec and
in the artifact's own `chain_note`, and a test asserts the word only ever
appears in a denial.

### 64. REASON CODES

`REASON_CODES.yaml` is the single source of truth: 17 eligibility codes and 5
ledger event types. A test fails if the policy or the ledger emits a code the
table does not define, so a new code cannot reach a flight record without
reaching the table.

`SUPPORT_LOST_FOR_REQUIRED_INFORMATION` carries severity `POLICY` — INELIGIBLE
for a `REQUIRE_IDENTIFIABLE` function, DEGRADED for a `TOLERATE_AMBIGUITY`
one. The same evidence means different things to a function that assumes its
position is correct and one that does not.

`Event.render()` produces a sentence for a display —
`"PRECISION_NAVIGATION ELIGIBLE -> INELIGIBLE"`. **The sentence is never
stored as canonical evidence**, and a test asserts `render` is absent from the
serialised event.

Three codes (`SOURCE_ABSENT_STALE`, `_NOT_RECEIVED`, `_NO_3D_FIX`) are defined
but not reachable from the scenario catalogue, which has no ingest layer.
That is stated rather than hidden, and the test that checks for unreachable
codes allows exactly those three by name.

### 65. OUTPUT SCHEMA

`engineering/v1_1/csia_output_v1_1.schema.json`, version **1.1.0**, JSON
Schema draft 2020-12. **13 500 payloads — every tick of all nine mechanisms —
validate.**

`additionalProperties: false` at the top level and on every nested object, so
an unrecognised field is a validation failure rather than a silent pass. `k`
and `h` are schema `const`s, so a payload cannot carry a re-tuned detector.

**Two naming decisions that are not cosmetic:**

**`posterior`, never `confidence`** (§22). It is a posterior probability under
a stated prior and likelihood; "confidence" would assert a calibration nothing
here establishes. `GNSS_FIX_LOSS` is exactly where that would mislead — the
leader sits at 0.992 with zero discriminating evidence. A consumer reading
`posterior` next to `discriminating_evidence_count: 0` and
`support_state: NON_IDENTIFIABLE` has what it needs not to be fooled. A test
walks the whole payload and fails on any key containing "confidence".

**`UNKNOWN` means two things and never shares a field.**
`function_eligibility[*].state == "UNKNOWN"` is *the policy cannot determine
eligibility*; `diagnosis.unknown_fault_model` is the `const`
`"NOT_IMPLEMENTED"`, so a payload cannot claim an unknown-fault capability
that was never built.

### 66. API COMPATIBILITY

Exactly **two** behaviours for an existing consumer, and no third:
`project_v1(payload)` returns the v1-shaped subset, or
`assert_schema_version()` raises. **No field is ever silently reinterpreted.**

The projection deliberately carries one field v1 never had: `trust_mode`. A v1
consumer quietly receiving `FLAT_V1_1` trajectories believing them to be v1's
would be precisely the silent reinterpretation §26 forbids, so the mode is
made unmissable rather than dropped.

**`current_valid` versioning (§28) closes the last unversioned semantic
change.** Phase 1 changed what the battery current channel means and
introduced `current_valid` as a bare field — blocker 5 in the Phases 1–3
report. It is now `evidence.current_valid`, typed `boolean|null` where `null`
means *the ingest layer did not report on it* rather than `false`, sitting
beside `missing_reason` as a closed enum, with its meaning fixed by
`schema_version`.

Provenance rides on **every** payload — `software_sha`, `configuration_hash`,
`input_trace_hash`, `trust_mode`, `frozen_core_tag` — so a payload extracted
from a log by itself is still attributable.

### 67. OUTPUT FIREWALL

`csia/v1_1/firewall.py`, **default-deny**. `request()` permits only what is
explicitly allow-listed, so a MAVLink command added upstream tomorrow is
denied today. A deny-list would be one missing entry away from arming an
aircraft.

Permitted: `READ_TELEMETRY`, `READ_PARAMETERS`, `WRITE_LOG`, `READ_LOG`,
`EMIT_OUTPUT`, `EMIT_RECOMMENDATION`.

Denied and unit-tested by name — all fourteen: `WRITE_PARAMETER`,
`SET_FLIGHT_MODE`, `WRITE_MISSION`, `CLEAR_MISSION`, `ACTUATOR_COMMAND`,
`SET_SERVO`, `ARM`, `DISARM`, **`RTL`**, **`LAND`**, `TAKEOFF`,
`REBOOT_AUTOPILOT`, `SET_HOME`, `CALIBRATE`. Plus unrecognised strings, empty
strings and lower-case variants.

Every denial is **recorded before it raises** and appears in `evidence()`: a
shadow deployment that silently swallowed a command attempt would hide the
more important half of the event, which is that one was attempted.

This is the layer **above** the existing transport guard, not a replacement
for it. `csia/deploy/guard.py` already denies the MAVLink transmit surface —
`conn.mav` raises on every attribute, the socket's write half is shut where
the transport has one, the process asserts its own inability at startup, and a
static scan backs it. `attach()` composes the two, and a test shows both
layers refusing.

**No hardware was required for any of this**, as §25 says.

### 68. STALENESS-LAYER AUDIT

The banked blocker was one row. **It is six of eight nodes, with one common
cause.**

`MaxAge` (adapter, v1.1) derives `5 / declared_rate_hz` **per platform** from
the channel contract. `STALE_TIMEOUT_S` (frozen core) applies the same rule
with the rate baked into a constant, and cannot derive it because the frozen
core knows nothing about adapters. They are the same property measured at two
points, disagreeing because they assume different producer rates.

| node | `MaxAge` | declared (AP/PX4) | `STALE_TIMEOUT_S` | rate it implies | agree? |
|---|---:|---:|---:|---:|---|
| `imu0` | 0.20 | 25 / **50** | 0.05 | 100 Hz | no |
| `imu1` | 0.20 | 25 / 25 | 0.05 | 100 Hz | no |
| `baro` | 0.50 | 10 / 10 | 0.10 | 50 Hz | no |
| `mag` | 0.20 | 25 / **14** | 0.10 | 50 Hz | no |
| `gps` | 1.00 | 5 / 5 | 0.50 | 10 Hz | no — *the banked row* |
| `motor_esc` | 0.50 | 10 / **1** | 0.10 | 50 Hz | **no — worst** |
| `battery` | 0.50 | 10 / 10 | 0.50 | 10 Hz | yes |
| `vibration` | 0.50 | 10 / 10 | 0.50 | 10 Hz | yes |

**The finding that is worse than the banked one: PX4 `motor_esc`.**
`ESC_STATUS` publishes at 1 Hz — already discovered and fixed once on the
adapter side, never available to the frozen layer. Three facts make the
exposure real, and all three hold: `to_core_samples` emits a sensor only when
it has new data, so `last_t` advances once per second; the frozen watchdog is
an arrival-age test on exactly that value; and `csia/deploy/shadow.py:109`
constructs `OnlineTrustLayer` **without** `stale_timeout_s`, while the ULog
CLI does pass it. On a live PX4 shadow flight `motor_esc` would be stale for
~0.9 s of every 1.0 s.

**Deployment-layer defect, not a frozen-core defect — and not fixed here.** It
changes live behaviour on a path with no coverage in this environment, which
is the regression analysis §27 requires first.

**The canonical rule needs no freeze break.** `OnlineTrustLayer` already
accepts `stale_timeout_s`; deriving the per-node timeout from the same
contract and passing it at construction is the whole change. Every derived
value is *more* tolerant than today's, so the risk it introduces is
under-detection of a dead sensor — the right direction to be careful about,
and the reason it is proposed and not applied.

**The design decision the audit forces:** eligibility reads the **frozen
layer's** freshness, and the adapter's `missing_reason` only refines the
`SOURCE_ABSENT_*` code. Anything else could declare a function ELIGIBLE on a
node whose evidence the trust layer had already withdrawn.

### 69. PHASE 4 COMPUTE

`PHASE4_COMPUTE.json`. Clean scenario, first 400 ticks, CPython on a
general-purpose host. **CORE and REPORTING are separated because §29 forbids
folding logging and serialization into an embedded-core claim.**

| phase | median µs/tick |
|---|---:|
| `core_trust_step` | 82.7 |
| `core_sequential_step` | 7.8 |
| **CORE total** | **90.5** |
| `support_metadata` | 168.2 |
| `function_eligibility` | 119.8 |
| `ledger_event` | 126.9 |
| `api_build` | 51.3 |
| `api_serialize` | 74.9 |
| **REPORTING total** | **541.0** |

**Reporting is 86% of the per-tick cost** — six times the core. That is the
number that must never appear in an embedded claim, and it is the reason §29
insists on the split. The sequential channel, the component Phase 3B added,
costs **7.8 µs and 5 floats**; it remains the cheapest thing in the system.

A first version of this measurement labelled the CUSUM step alone as "core"
and reported 11 µs. That was wrong — it omitted the trust update — and the
measurement was rebuilt to step `FlatTrustCore` directly rather than reusing
the batch result.

**No target-hardware figure exists and none is claimed.**

### 70. FINAL v1.1 ARCHITECTURE

    canonical ingestion (R1-R5)
      -> 11-relation evidence bank, 8 nodes
      -> FLAT persistent trust          float alpha[8], beta[8], trust[8]
      -> mechanism-specific CUSUM       float S[5], k=0.5, h=500
      -> frozen diagnosis posterior     float smoothed[8]
      -> support / identifiability / ambiguity
      -> deterministic function eligibility  (5 functions, 0 new thresholds)
      -> deterministic assurance policy      (frozen v1 failsafe)
      -> reproducible assurance ledger
      -> read-only versioned output API      (schema 1.1.0)

    STATUS: V1_1_ARCHITECTURE_FROZEN

**No AI, no GNN, no learned policy, no unknown-fault detector, no new
diagnosis algorithm, no direct aircraft control, and no research novelty
claimed** (§43). The one statistic added is Page's 1954 CUSUM, used as a
baseline.

### 71. GOLDEN-TRACE READINESS

`embedded/v1_1/GOLDEN_TRACE_PLAN.md`. **Cases and comparison rule only; no
numbers frozen, no C code written**, per §37 and §36.

Eleven cases: the nine mechanisms plus `BATTERY_SENTINEL` and `MAG_SENTINEL`,
which run from the Phase 1 fixtures because they exercise the ingest rules
rather than the trust update and would otherwise be ported untested.

Three comparison tiers, because they cannot share a tolerance:

- **Tier A — EXACT.** Assurance level, every function state and reason-code
  set, leader, ambiguity, identifiability, support state, alarming set,
  freshness, active/suppressed relations, and the ledger event sequence.
  There is no such thing as an off-by-a-little failsafe level.
- **Tier B — NUMERIC**, tolerance **deliberately not declared yet**. It must
  come from an arithmetic argument (float32 epsilon, accumulation length, the
  smoothing constants) plus a measured distribution — never from whatever the
  first port happens to produce. The CUSUM `S` is a running sum and is the
  worst case in the set.
- **Tier C — NOT COMPARED.** Event ids and content hashes hash the
  *implementation*, not the behaviour.

The rule: a tier-A difference on any tick of any case fails the port, and the
**maximum** tier-B deviation is reported, never the mean — a mean hides
exactly the excursion that matters. **A tier-A difference is never resolved by
relaxing tier A.**

### 72. PHASE 5 READINESS

**Not ready, and the plan says why.** Three things must settle first, and none
is a measurement:

1. **The §30 review of the propagation removal.** The default is `FLAT_V1_1`
   and the frozen engine still contains the legacy line. If the review changes
   the decision, every trace changes.
2. **The staleness rule.** §68 proposes a canonical timeout and does not adopt
   it. Adopting it changes admissibility on every tick, so freezing traces
   first would waste them.
3. **The schema has never met a real consumer.** It validates 13 500 payloads
   and zero integrations.

Freezing numbers before those settle would freeze the wrong ones.

### 73. REMAINING BLOCKERS

1. **No C code, no golden-trace values, no declared tolerance.** G6.
2. **PX4 `motor_esc` staleness** — the most concrete known deployment defect;
   needs a PX4 replay or bench regression this environment cannot run.
3. **The §30 propagation review** is still open; nothing has been deleted.
4. **Research campaigns still need remeasurement for v1.1.** Phase 1 changed
   ingestion; the v1 numbers stay labelled v1 and were not edited.
5. **No library access** — the sole blocker on G8.
6. **No hardware** — blocks G1, G2, G3.
7. **No GNSS step mechanism exists** in the frozen injector; the ramp results
   do not cover steps.
8. **`UNKNOWN` / unmodeled fault** remains unimplemented, pending a
   model-adequacy test.
9. **Zero verified-clean hours.** No false-alert rate is claimed or
   supportable.

Resolved since the Phases 1–3 report: the Phase 3B arms (§29.1) and
`current_valid` versioning (§29.5).

### 74. PRODUCT MATURITY

**M2 — cross-platform simulation validated.** Unchanged, and Phase 4 does not
claim to move it: **freezing an architecture is a precondition for the port,
not the port.**

    M3 embedded-equivalent     no C port exists
    M4 physical-FC HIL         no hardware
    M5 real-aircraft shadow    no aircraft
    M6 clean exposure          ZERO verified-clean hours

What changed is the runtime architecture's status:
**`V1_1_ARCHITECTURE_FROZEN`**, recorded in the graduation matrix as an
engineering milestone and deliberately not as a matrix row, because freezing
an interface is not evidence about the world.

**Research maturity: none established.**

G4 `VALIDATED_SITL`, G5 `VALIDATED_SITL`, every other row unchanged.

---

# PHASE 4.5 ADDITIONS (§34, items 75–92)

Three deployment gates closed, then the golden corpus frozen. Produced by
`validation/v1_1/deployment/run_staleness.py`,
`engineering/v1_1/phase4_5/run_gate_c.py` and `embedded/v1_1/build_golden.py`,
guarded by `test_v1_1_staleness.py` (26), `test_v1_1_monitor.py` (29) and
`test_v1_1_golden.py` (23).

### 75. TRUST-MODE FINAL DECISION

    TRUST_MODE_REVIEW:  PASS

`TRUST_MODE_FINAL_DECISION.md`. `FLAT_V1_1` is the v1.1 default;
`LEGACY_NEIGHBOR_PROPAGATION` is retained solely for historical and research
reproduction. **Exactly one mechanism is rejected** — the neighbour's trust
multiplying a relation's weight at `engine.py:110`. Relation topology, all 11
relations, node definitions, relation ownership and the trust recursion itself
are retained, and nothing is deleted.

Four things carry it:

1. **Zero incremental benefit.** `T1 − T0` and `T4 − T3` are both 0.00 on six
   mechanisms and censored on two.
2. **A 0.28 s regression** on `dual_imu_failure`, the one safety-critical
   mechanism where the modes differ, with the same sign again downstream
   (`CRITICAL → EMERGENCY` 0.60 s later). There is no mechanism anywhere in
   the catalogue on which propagation is earlier.
3. **Attribution cannot be affected, structurally.** `bayes.py` is 172 lines
   and imports four things, one of them `consistency` — a pure function of one
   residual. `TrustHistory` does not occur in the file and no attribute named
   `trust` is read anywhere in it, verified by AST rather than grep. No
   experiment could have shown propagation improving attribution.
4. **Legacy reproduction is exact** — bit-identical, tolerance declared 0.0
   and needed 0.0 — because LEGACY returns the frozen class itself rather than
   a re-implementation.

Per §2, **Phase 5 ports `FLAT_V1_1` only.** Legacy stays reference-only: there
is no product requirement to run historical propagation on an embedded target,
and a second trust weighting in C is dead complexity in the most expensive
place to carry it.

### 76. THE STALENESS PROBLEM

`MaxAge` (adapter, v1.1) and `STALE_TIMEOUT_S` (frozen core, v1) answer the
**same** question — how many producer periods of silence before a measurement
stops being evidence — and both apply a margin of five periods. They disagree
because one derives the period from the channel contract per platform and the
other has it baked into a constant, which the frozen core cannot avoid because
it knows nothing about adapters.

Six of eight nodes disagree; `battery` and `vibration` agree, and they are
exactly the two whose declared rate is the 10 Hz the frozen table assumed.

**§6's question is answered: same concept, one authoritative rule.** Two
undocumented meanings are not retained.

### 77. PX4 `motor_esc` PRE-FIX REPRODUCTION — A NEGATIVE RESULT

**Phase 4 §68 was wrong, and reproducing it is what found that.**

It predicted `motor_esc` stale for ~0.9 s of every 1.0 s on a live PX4 shadow
flight. It would not be, because **`motor_esc` never reaches the frozen core
on either platform**:

| platform | `esc.rpm` | `esc.current` |
|---|---|---|
| ArduPilot | `STUB_OR_NONINFORMATIVE` | `STUB_OR_NONINFORMATIVE` |
| PX4 | `AVAILABLE_UNVALIDATED` | `STUB_OR_NONINFORMATIVE` |

`to_core_samples` emits a sensor only when every required channel is usable,
and usability is decided by the **qualification contract before any watchdog
runs**. The arithmetic was right; the conclusion skipped a layer.

`PX4_MOTOR_ESC_STALENESS_PRE_FIX.csv` and `..._POST_FIX.csv` are the record:
`motor_esc_reached_core` is **False on every tick in both arms**, at 0.1 s and
at 5.0 s. **Two opposite timeouts, one identical outcome** — which is how you
tell the timeout is not the cause. Both files carry the channel qualification
columns so the file explains itself.

The reproduction produced a negative result and it is committed as one.

### 78. THE CANONICAL TIMEOUT RULE

    runtime_stale_timeout[node] = max over required channels of max_age[channel]
    max_age[channel] = MAX_AGE_MARGIN / declared_rate_hz  (per platform)

**In one sentence: the runtime watchdog agrees with the ingestion layer that
feeds it.**

**No new constant.** `MAX_AGE_MARGIN = 5.0` is *imported* from the adapter,
where it was already declared and justified; the same factor already appears
in `ulog_source.stale_timeouts(factor=5.0)`. §9 forbids optimising a
multiplier after seeing the matrix, and the way to make that impossible is to
have none: a test parses `csia/v1_1/staleness.py` and asserts it contains no
numeric literal of its own (rounding precision excluded by position, not by
being small enough to overlook), and a second test asserts `channel_max_age`
agrees with a live adapter's `_derive_max_age` on every channel.

**A second Phase 4 correction.** §68 said "node timeout = **min** over the
required channels". `max` is correct — a node stops arriving when its
slowest-permitted channel does. **No published number changes**, because every
node's required channels share a declared rate on both platforms, so `min` and
`max` coincide throughout the table. Recorded anyway: a justification that
happens to give the right answer is still the wrong justification.

| node | ArduPilot | PX4 | frozen |
|---|---:|---:|---:|
| `imu0` | 0.200 | 0.100 | 0.05 |
| `imu1` | 0.200 | 0.200 | 0.05 |
| `baro` | 0.500 | 0.500 | 0.10 |
| `mag` | 0.200 | 0.357 | 0.10 |
| `gps` | 1.000 | 1.000 | 0.50 |
| `motor_esc` | 0.500 | 5.000 | 0.10 |
| `battery` | 0.500 | 0.500 | 0.50 |
| `vibration` | 0.500 | 0.500 | 0.50 |

### 79. STALENESS MATRIX

`STALENESS_MATRIX.csv` — 8 nodes × 4 conditions × 2 platforms × 2 arms = 128
rows, all present.

**Inadmissible nodes carry null metrics, not a 100% false-stale rate.**
Reporting one would blame the watchdog for a qualification decision taken a
layer earlier. Inadmissible: `motor_esc` on both platforms; `imu1` and
`battery` additionally on PX4, whose `imu1.accel`, `imu1.gyro` and
`battery.current` are `UNAVAILABLE`. **A PX4 shadow flight today runs on five
nodes, not eight.**

Over the admissible nodes:

| condition | `FROZEN_DEFAULT` | `DERIVED_RULE` |
|---|---|---|
| `NOMINAL_RATE` | **0.00%** everywhere | **0.00%** everywhere |
| `RATE_JITTER` ±30% | `baro` **2.77%** (AP) / **3.69%** (PX4) | **0.00%** everywhere |

**At exactly nominal rates nothing false-stales.** The frozen defaults are
adequate when the wire is perfect. The reproduced defect is one node, ~3% of
ticks, only under jitter — because the frozen `baro` timeout of 0.10 s equals
the 10 Hz nominal period exactly, leaving zero margin, so any positive jitter
trips it.

Also found: **`mag` is not an independent stream on either platform.** It
rides `SCALED_IMU` on ArduPilot and `HIGHRES_IMU` on PX4, so its declared
25 / 14 Hz cannot be realised separately — the magnetometer arrives exactly as
often as `imu0`.

### 80. POST-FIX RESULTS

`csia/deploy/shadow.py` now passes `stale_timeout_s=build_runtime_stale_
timeouts(cfg.platform)`. **The frozen core is untouched and its default table
is unedited** — `OnlineTrustLayer` already accepted the argument, and the ULog
CLI already used one.

    GATE B  nominal-rate  PASS
    GATE B  jitter        PASS
    GATE C  hard-dropout  PASS

A test constructs a real `ShadowRunner` on both platforms and asserts
`runner.layer._stale` equals the derived map; another parses the module and
asserts `STALE_TIMEOUT_S` is neither imported nor referenced and that the sole
`OnlineTrustLayer(...)` call passes `stale_timeout_s`.

### 81. DROPOUT LATENCY TRADEOFF — §7

Every derived timeout is **longer**, so the risk is delayed detection of a
genuinely dead source. Both controls were measured, not just the one that
looks good.

| platform | node | timeout frozen → derived | latency frozen → derived |
|---|---|---|---|
| AP | `imu0`, `imu1` | 0.05 → 0.20 | 0.08 → **0.24 s** |
| AP | `mag` | 0.10 → 0.20 | 0.12 → **0.24 s** |
| AP / PX4 | `baro` | 0.10 → 0.50 | 0.16 → **0.56 s** |
| AP / PX4 | `gps` | 0.50 → 1.00 | 0.56 → **1.08 s** |
| PX4 | `imu0` | 0.05 → 0.10 | 0.08 → **0.12 s** |
| PX4 | `mag` | 0.10 → 0.357 | 0.12 → **0.36 s** |
| both | `battery`, `vibration` | unchanged | 0.56 s, unchanged |

**Every admissible node still detects a hard dropout**, and the latency is
bounded *by construction* rather than by luck: detection fires on the first
tick where `age > timeout`, so latency ∈ `(timeout, timeout + 1/tick_hz]`. A
test asserts that inequality on every row rather than checking a table of
measured numbers.

Worst case moves **0.56 s → 1.08 s**, on `gps`. The largest relaxation is
`baro` at 5×, buying 0.40 s of extra detection latency to remove a 3%
false-stale rate. **The false-stale problem was not fixed by making detection
arbitrarily slow.**

### 82. PHASE 4 FUNCTION REGRESSION — §12

**No Phase 4 result moved.** Checked two independent ways, because "we re-ran
it and it looked the same" is not an answer.

**Structural.** The three Phase 4 runners are parsed and contain no reference
to `OnlineTrustLayer`, `get_adapter`, `PlatformAdapter`, `ShadowRunner` or
`build_runtime_stale_timeouts`. The nine scenarios take freshness from the
deterministic simulator's `td.fresh`, so a runtime watchdog **cannot** reach
them. **PASS.**

**Behavioural.** All ten Phase 4 artifacts regenerated and compared field by
field. `FUNCTION_ELIGIBILITY_RESULTS.csv`, `PHASE4_CLEAN_RESULT.json`,
`PHASE4_FIXLOSS_RESULT.json`, `PHASE4_DUAL_IMU_RESULT.json` and
`PHASE4_API_VALIDATION.json` are **byte-identical**. Five differ in bytes only
and only in provenance: `software_sha` moved with the commit, and it sits
inside every ledger event's context by design, so every content hash
downstream moved with it. The excluded fields are named in the artifact rather
than filtered silently.

    VERDICT: NO_BEHAVIOURAL_CHANGE

### 83. API CONSUMER

`csia/v1_1/monitor.py` — `csia-monitor`, a JSONL/terminal consumer.
`API_CONSUMER_SPEC.md`, `API_CONSUMER_RESULTS.json`.

**It imports no producer** — not the trust engine, diagnosis, eligibility
policy, ledger or adapters — and a test parses its imports and fails on any of
them. That is the whole experiment: a consumer that could reach into the
system would recompute what the payload failed to carry, and the schema would
never be tested for sufficiency.

**Result: every §14 field was already in the schema.** Nothing had to be added
to make an external consumer work, which is what Gate C was asking.

It consumes a real file (`api_consumer_stream.jsonl`), 2 payloads accepted, 0
rejected.

### 84. CONSUMER FIX-LOSS INTERPRETATION — §15

The payload says `trust["gps"] = 0.987` and `nominal` at `p = 0.9925`. What
the monitor prints:

    t=   26.00  4 OF 5 FUNCTIONS UNAVAILABLE — support NON_IDENTIFIABLE
      assurance          CAUTION
      diagnosis          nominal p=0.9925 [NON_IDENTIFIABLE, 0 discriminating, AMBIGUOUS]
      evidence           16 active, 0 discriminating
      COARSE_NAVIGATION      INELIGIBLE  REQUIRED_SOURCE_NOT_FRESH, ...
      INERTIAL_CONTINUATION  ELIGIBLE    ALL_REQUIREMENTS_MET
      advisory           RESTRICT_PRECISION_NAV, INHIBIT_GPS_MODES, SWITCH_NAV_INERTIAL

Not "GPS healthy". Not "nominal 99%".

**The primary status is computed from eligibility and support, and the
posterior is not an input to it** — enforced structurally, not by wording. A
test parses two views differing *only* in the posterior (0.9925 against
0.0001) and asserts the primary status is identical.

**The posterior is shown, and never bare.** `format_leader` cannot emit
`p=0.9925` without the support state, the discriminating-evidence count and
the ambiguity beside it. Suppressing it would have been the easy answer and
the wrong one — it is real information; what it must not do is travel alone.

### 85. CONSUMER NEGATIVE TESTS — §16

Six rejection paths, each perturbing exactly one thing, **all refused**:

| case | outcome |
|---|---|
| `schema_version: "2.0.0"` | refused — no coercion |
| a string where an object belongs | refused |
| `diagnosis.posterior` deleted | refused — not defaulted |
| `sequential.h = 5.0` | refused — a **differently configured detector** |
| `trust.mode = FLAT_V2_EXPERIMENTAL` | refused |
| `function state = PROBABLY_FINE` | refused |

Plus unknown reason codes. **No permissive path**: every failure raises
`PayloadRejected`, there is no best-effort degradation and no default for a
missing field. At stream level a rejection is *recorded* rather than raised,
so one bad line does not end the run and `evidence()` says which.

The `k`/`h` check matters more than it looks: a payload carrying `h = 5.0`
came from the detector whose textbook value produced 2681 clean alarm ticks,
and reading it as this one would mix two detectors' outputs in one log.

### 86. FIREWALL INTEGRATION — §18

Every action goes through `OutputFirewall.request`, including accepting a
payload. No branch bypasses it.

`SET_FLIGHT_MODE`, `WRITE_PARAMETER`, `RTL`, `LAND` and an unrecognised
operation: **all denied**, all recorded before raising, all present in
`evidence()`. `READ_TELEMETRY`, `WRITE_LOG`, `EMIT_OUTPUT`: permitted. A test
also asserts the module imports no `socket`, `pymavlink`, `serial`,
`requests`, `urllib`, `http` or `subprocess` — it could not transmit if the
firewall were removed.

**§17 compatibility:** a modelled v1 consumer accepts `project_v1` output and
**refuses** a raw v1.1 payload; a version mismatch raises before projection.
The projection carries `trust_mode`, which v1 never had, so `FLAT_V1_1`
trajectories cannot be received as v1's. **No silent reinterpretation.**

### 87. GOLDEN CORPUS

`embedded/v1_1/golden/`, 11 cases, **13 500 ticks**.

    corpus sha256  f183f0355a0ab966fa0ab3b2a696f3af8adae5473220ff7bef75002820060e0f

`build_golden.py` **re-checks the §20 preconditions itself and refuses to
write a corpus** if any is missing. A gate kept in a person's memory is not a
gate, and freezing traces for an architecture still in motion is the failure
this phase exists to prevent.

Frozen inputs (§22), all hashed: per-case `raw_trace` / `canonical_input` /
`relation_bank` hashes, plus the SHA-256 of the requirements, reason codes,
output schema, the six v1.1 runtime modules and the frozen `scenarios.py`,
`bayes.py`, `engine.py`, `failsafe.py`. A test re-hashes every one against the
working tree, so a corpus describing a system that no longer exists fails
rather than sits there.

The two ingest cases (`BATTERY_SENTINEL`, `MAG_SENTINEL`) are in the corpus
because they exercise R1–R5 rather than the trust update, and a port that
skipped them would ship the ingest rules untested. They have **no Tier B** —
there is no trust tick — and the manifest says so rather than padding an empty
numeric file.

### 88. TIER-A FREEZE — §23

Per tick, EXACT: assurance state, every function's eligibility state and
reason-code set, leader, identifiability, ambiguity, support state,
non-identifiable set, sequential alarming set, per-node freshness, missing
reasons, active and suppressed relation sets with their suppression reasons,
and the ledger event sequence.

Stored **run-length encoded and losslessly.** The discrete series is piecewise
constant, so change-points plus run lengths reconstruct it exactly. **This is
not a truncation**: the manifest carries the SHA-256 of the *full per-tick
series* as well as of the stored file, and a test reconstructs all 13 500
ticks and checks them against that hash rather than taking the encoding on
trust. It took the corpus from **20 MB to 964 KB without discarding a tick**,
and the corpus hash is byte-identical to the uncompressed build's.

Tier B is a continuous trajectory and does not compress: stored at **stride
10** with the full-series hash beside it, so the stride localises a divergence
to a ten-tick window and the hash settles whether the whole series matches.

**Tier C is excluded from the frozen ledger files entirely** — the generator
writes `TIER_C_NOT_COMPARED` into the software and configuration hash fields,
so a port cannot accidentally be graded on this build's identity. A test
asserts `event_id`, `content_sha256`, `previous_event_hash` and `software_sha`
do not appear in any frozen ledger row.

### 89. TIER-B NUMERIC SPECIFICATION — §§24–25

`NUMERIC_EQUIVALENCE_SPEC.md`. **Derived before any C exists**, and a test
asserts `embedded/` contains no `.c`, `.h`, `.cpp` or `.hpp`.

From IEEE-754 binary32 unit roundoff `u = 2⁻²⁴ = 5.96e-8`, the recurrence
structure, and a 1500-tick run:

| quantity | recurrence | derived | **DECLARED** |
|---|---|---:|---:|
| `trust` | decaying, `u/(1−ρ_max)`, ρ=0.998 | 3.0e-5 abs | **1e-4 abs** |
| `alpha`, `beta` | same | 3.0e-5 rel | **1e-4 rel** |
| `smoothed`, `score` | decaying, `u/α`, α=0.06, `\|ll\|≤82` | 1.22e-4 abs | **1e-3 abs** |
| `posterior` | softmax, Jacobian ≤ ½ | 6.1e-5 abs | **1e-3 abs** |
| `sequential.S` | **no forgetting factor** | 4.49e-2 abs | **0.5 abs** |

The CUSUM is the worst case precisely because it has no decay — the only
quantity whose bound grows with run length. Its `Σ|z|` term stays small
through a self-limiting property worth stating: a large `|z|` reaches `h` in
few steps and a small one takes many, so the product is pinned near `h`
either way.

`posterior` deliberately **inherits** the score's 1e-3 rather than getting a
bound of its own, since its error is derived from the score's and the softmax
contracts. That puts it at 16× headroom, the widest in the table, as a
consequence of keeping the two consistent rather than a separate decision.

**The tolerance is never widened after seeing C.** If a port exceeds it, the
port is wrong until proven otherwise; if the reference turns out to be wrong,
that is a v1.1 defect with its own commit and its own remeasurement.

### 90. DECISION-MARGIN AUDIT — §26

Numeric error only matters where it can flip a **discrete** state.
`DECISION_MARGIN_AUDIT.csv` computes, per tick, the distance to every
inherited trust threshold, the CUSUM `h`, and the diagnosis ranking boundary.

**2 ticks of 13 500 — 0.0148% — are `NUMERICALLY_NEAR_BOUNDARY`:**

| case | t | boundary | distance | tolerance |
|---|---:|---|---:|---:|
| `DUAL_IMU_FAILURE` | 47.52 s | `att_emergency` (0.70) | **1.26e-5** | 1e-4 |
| `MAG_DEGRADED` | 35.04 s | `heading_caution` (0.60) | **8.74e-5** | 1e-4 |

Both are trust-threshold crossings where a conforming binary32 port could
legitimately land on the other side and produce a Tier-A difference from
arithmetic rather than from a logic error. **These are where Phase 5 looks
first** — enumerated in advance, which is the difference between debugging a
port and arguing about one. Neither is excused: a Tier-A difference there is
still a Tier-A difference and still has to be explained.

No tick is near the CUSUM `h` boundary (closest 477.6 against a 0.5 tolerance)
or a ranking boundary (closest 4.80 against 1e-3). **Only trust thresholds are
in reach**, which is what makes the two flagged ticks tractable.

### 91. PHASE 5 READINESS

    PHASE5_READY:  YES

`embedded/v1_1/PHASE5_AUTHORIZATION.md`. All nine gates pass:

| | gate | status |
|---|---|---|
| A | trust-mode review | PASS |
| B | staleness, nominal rate | PASS |
| C | staleness, hard dropout | PASS |
| D | Phase 4 function regression | PASS |
| E | API consumer | PASS |
| F | firewall | PASS |
| G | golden corpus frozen | PASS |
| H | numeric spec before C | PASS |
| I | full test suite | PASS — **1211 passed, 0 failed** |

The three items Phase 4 §72 named as blocking are the three this phase
closed: the propagation review was open (Gate A closed it), the staleness rule
was proposed but unadopted (Gate B adopted and measured it), and the schema
had never been consumed (Gate C consumed it).

**Compute (§19).** The timeout map costs **~10 µs once, at construction**. Its
per-tick cost is **zero**: the watchdog compares against a float either way
and only the value differs — measured 0.711 µs against 0.692 µs, a −0.019 µs
delta that is noise. The consumer is reporting-only and is not folded into any
core figure: `render` 5.5 µs, but `parse` **22.6 ms**, dominated by full
JSON-schema validation. That last number is worth stating plainly — **a
consumer cannot schema-validate every payload at 25 Hz**, and a real
integration will need to validate on connect and spot-check thereafter. It is
a consumer-side design constraint, not a core-path cost.

### 92. REMAINING BLOCKERS

1. **No C code.** G6 remains `NOT_STARTED`; Phase 4.5 ends with frozen traces
   and no port, as §29 requires.
2. **No live MAVLink link was ever exercised.** Tier A evidence is unavailable
   in this environment; the matrix is `SYNTHETIC_DEPLOYMENT_REGRESSION` and is
   labelled so everywhere.
3. **Platform qualification, not staleness:** `motor_esc` is inadmissible on
   both platforms; `imu1` and `battery.current` are `UNAVAILABLE` on PX4. A
   PX4 shadow flight runs on **five of eight nodes**. Promoting `esc.rpm`
   needs a source read, not another flight — the contract says so itself.
4. **One consumer, written by the same author as the producer.** Gate C proved
   sufficiency, not independence.
5. **No transport specified** for the output API, and no authentication.
6. **No GNSS step mechanism** exists in the frozen injector.
7. **`UNKNOWN` / unmodeled fault** remains unimplemented.
8. **Research campaigns still need remeasurement for v1.1.**
9. **No library access** — the sole blocker on G8.
10. **No hardware** — blocks G1, G2, G3.
11. **Zero verified-clean hours.** No false-alert rate is claimed or
    supportable.

Resolved since Phase 4: the propagation review (§75), the staleness rule
(§78–81), and the schema's first consumer (§83–86).

**Product maturity: M2, unchanged.** Freezing the deployment semantics is a
precondition for the port, not the port.
