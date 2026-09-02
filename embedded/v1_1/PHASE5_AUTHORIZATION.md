# PHASE 5 AUTHORIZATION — Phase 4.5 §28

    PHASE5_READY:  YES

Authorized for the C/C++ port of the v1.1 architecture, against the frozen
golden corpus in `embedded/v1_1/golden/` and the tolerance in
`NUMERIC_EQUIVALENCE_SPEC.md`.

**No C exists yet.** A test asserts `embedded/` contains no `.c`, `.h`,
`.cpp` or `.hpp` file, and §29 forbids writing one in Phase 4.5.

---

## 1. THE GATES — §§20, 33

| | gate | status | evidence |
|---|---|---|---|
| **A** | trust-mode review | **PASS** | `TRUST_MODE_FINAL_DECISION.md` — `TRUST_MODE_REVIEW: PASS` |
| **B** | staleness, nominal rate | **PASS** | 0.00% false-stale on every admissible node, both platforms |
| **C** | staleness, hard dropout | **PASS** | every admissible node still detects; worst 1.08 s, bounded by construction |
| **D** | Phase 4 function regression | **PASS** | `NO_BEHAVIOURAL_CHANGE`, structural + behavioural |
| **E** | API consumer | **PASS** | `csia-monitor`, 2/2 accepted, 6/6 negatives refused |
| **F** | firewall | **PASS** | 5/5 control operations denied through the consumer |
| **G** | golden corpus frozen | **PASS** | 11 cases, 13 500 ticks, manifest hashed |
| **H** | numeric spec before C | **PASS** | derived from `u = 2⁻²⁴`, no C in the tree |
| **I** | full test suite | **PASS** | 1211 passed, 0 failed |

`build_golden.py` re-checks A, B, D, E, F and H at generation time and
**refuses to write a corpus** if any is missing. Freezing traces for an
architecture still in motion is the failure this phase exists to prevent, so
the check is in the tool rather than in a person's memory.

## 2. WHAT IS FROZEN — §§21–23

**Eleven cases**, the nine scenario mechanisms plus the two ingest cases:

    CLEAN  GNSS_RAMP_SLOW  GNSS_RAMP_FAST  GNSS_FIX_LOSS
    IMU0_BIAS_DRIFT  DUAL_IMU_FAILURE  MAG_DEGRADED  POWER_SAG
    VIBRATION_ANOMALY            13 500 ticks total
    BATTERY_SENTINEL  MAG_SENTINEL    ingest-layer, R1-R5, no trust tick

**Inputs, hashed** (§22): the scenario definitions via
`raw_trace_sha256` / `canonical_input_sha256` / `relation_bank_sha256` per
case, plus the SHA-256 of every file that can change the answer — the
requirements, the reason codes, the output schema, the five v1.1 runtime
modules, `staleness.py`, and the frozen `scenarios.py`, `bayes.py`,
`engine.py` and `failsafe.py`.

**Tier A, per tick, EXACT** (§23): assurance state, every function's
eligibility state and reason-code set, diagnosis leader, identifiability,
ambiguity, support state, non-identifiable set, sequential alarming set,
per-node freshness, missing reasons, active and suppressed relation sets with
their suppression reasons, and the ledger event sequence.

Tier A is stored **run-length encoded and losslessly**: the discrete series is
piecewise constant, so change-points plus run lengths reconstruct it exactly,
and the manifest carries the SHA-256 of the **full per-tick series** as well as
of the stored file. A test reconstructs the full series and checks it against
that hash rather than taking the encoding on trust. This is the same argument
Phase 4B used for the eligibility series, and it took the corpus from 20 MB to
under 1 MB without discarding a single tick.

**Tier B** is a continuous trajectory and does not compress. It is stored at
**stride 10** with the full-series hash beside it: the stride localises a
divergence to a ten-tick window, and the hash settles whether the whole series
matches. Quantities: `trust` per node, CUSUM `S` per covered node, posterior,
and the per-hypothesis `smoothed` and `score` vectors.

**Tier C is not compared** — event ids, content hashes, configuration and
software hashes hash the implementation. The corpus generator writes
`TIER_C_NOT_COMPARED` into those ledger fields so a port cannot accidentally
be graded on them.

    corpus sha256: f183f0355a0ab966fa0ab3b2a696f3af8adae5473220ff7bef75002820060e0f

## 3. THE NUMERIC TOLERANCE — FROZEN BEFORE C — §§24–25

| quantity | derived | **DECLARED** |
|---|---:|---:|
| `trust[node]` | 3.0e-5 abs | **1e-4 abs** |
| `alpha`, `beta` | 3.0e-5 rel | **1e-4 rel** |
| `smoothed`, `score` | 1.22e-4 abs | **1e-3 abs** |
| `posterior` | 6.1e-5 abs | **1e-3 abs** |
| `sequential.S` | 4.49e-2 abs | **0.5 abs** |

Derived from IEEE-754 binary32 unit roundoff, the recurrence structure and a
1500-tick run length. The CUSUM is the worst case because it has no forgetting
factor — the only quantity whose bound grows with run length.

**This tolerance is never widened after seeing C.** If a port exceeds it the
port is wrong until proven otherwise.

## 4. THE DECISION-MARGIN AUDIT — §26

Numeric error only matters where it can flip a discrete state.
`DECISION_MARGIN_AUDIT.csv` computes, per tick, the distance to every trust
threshold, the CUSUM `h`, and the diagnosis ranking boundary.

**2 ticks of 13 500 (0.0148%) are `NUMERICALLY_NEAR_BOUNDARY`:**

| case | t | boundary | distance | declared tolerance |
|---|---:|---|---:|---:|
| `DUAL_IMU_FAILURE` | 47.52 s | `att_emergency` (0.70) | **1.26e-5** | 1e-4 |
| `MAG_DEGRADED` | 35.04 s | `heading_caution` (0.60) | **8.74e-5** | 1e-4 |

Both are trust-threshold crossings where a conforming binary32 port could
legitimately land on the other side and produce a Tier-A difference from
arithmetic alone rather than a logic error.

**These two ticks are where Phase 5 looks first.** They are enumerated in
advance, which is the difference between debugging a port and arguing about
one. Neither is excused: a Tier-A difference there is still a Tier-A
difference and still has to be explained — but it will be explained as an
arithmetic near-miss at a named boundary rather than investigated blind.

Reassuringly, no tick is near the CUSUM `h` boundary (closest 477.6 against a
0.5 tolerance) and none is near a diagnosis ranking boundary (closest 4.80
against 1e-3).

## 5. WHAT PHASE 5 PORTS

    canonical ingestion (R1-R5)
      -> 11-relation evidence bank, 8 nodes
      -> FLAT persistent trust        float alpha[8], beta[8], trust[8]
      -> CUSUM bank                   float S[5],  k=0.5, h=500
      -> frozen diagnosis posterior   float smoothed[8]
      -> support / identifiability / ambiguity
      -> deterministic function eligibility
      -> deterministic assurance policy
      -> assurance ledger + read-only versioned output API

**`FLAT_V1_1` only.** `LEGACY_NEIGHBOR_PROPAGATION` stays
Python/reference-only: there is no product requirement to run historical trust
propagation on an embedded target, and carrying a second trust weighting into
C would be dead complexity in the most expensive place to carry it (§2 of the
Phase 4.5 brief).

In-control CUSUM statistics are **constants**. A port that re-estimated them
from live data would not be the same algorithm.

## 6. WHAT PHASE 5 MAY NOT DO

- **Re-tune.** `k = 0.5` and `h = 500` come with a stated selection rule and a
  committed negative result. A port that changed them is a different detector.
- **Fix a disagreement by changing the reference.** The C is wrong until
  proven otherwise; if the Python turns out to be wrong, that is a v1.1 defect
  with its own commit and its own remeasurement, not a silent alignment.
- **Widen the Tier-B tolerance**, or resolve a Tier-A difference by relaxing
  Tier A.
- **Enable `-ffast-math`, SIMD reductions or threading** in the compared path.
  `NUMERIC_EQUIVALENCE_SPEC.md` §5 excludes them: they break the assumption
  that the port computes the same function.
- **Claim a timing figure the reference cannot support.** Python measured
  90 µs/tick core and 541 µs/tick reporting on a general-purpose host. Neither
  is an embedded figure.

## 7. WHAT IS STILL NOT CLOSED — AND WHY IT DOES NOT BLOCK THE PORT

| open item | why it does not block |
|---|---|
| no live MAVLink link was ever exercised | the port is graded against the deterministic corpus, which does not involve a link |
| `motor_esc` is inadmissible on both platforms; `imu1` and `battery.current` are `UNAVAILABLE` on PX4 | a qualification question about platforms, not about whether the C matches the Python |
| no GNSS step mechanism exists in the frozen injector | the corpus is the frozen catalogue; a step case cannot be ported because it cannot be generated |
| zero verified-clean hours | a field-evidence question; the port changes nothing about it |
| the schema has met one consumer, written by the same author | Gate C's stated limit. It proved sufficiency, not independence |
| `UNKNOWN` / unmodeled fault remains unimplemented | deliberate, and the schema pins it as `NOT_IMPLEMENTED` |

**What would have blocked the port, and no longer does:** the propagation
review was open (Gate A closed it), the staleness rule was proposed but
unadopted (Gate B adopted and measured it), and the schema had never been
consumed (Gate C consumed it). Those were the three named in Phase 4 §72, and
they are the three this phase closed.

## 8. PRODUCT MATURITY — UNCHANGED

**M2 — cross-platform simulation validated.** Phase 4.5 does not move M2 → M3
and does not claim to: **freezing the deployment semantics is a precondition
for the port, not the port.**

    M3 embedded-equivalent    no C port exists
    M4 physical-FC HIL        no hardware
    M5 real-aircraft shadow   no aircraft
    M6 clean exposure         ZERO verified-clean hours

Research maturity: **none established.**

    PHASE5_READY:  YES
