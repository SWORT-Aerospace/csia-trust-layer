# TRUST-MODE FINAL DECISION — Phase 4.5 §1

Gate A. The final review of the neighbour-trust propagation question, taken on
the Phase 3 and Phase 4 evidence as the decision record.

    TRUST_MODE_REVIEW:  PASS

    FLAT_V1_1                      default for v1.1
    LEGACY_NEIGHBOR_PROPAGATION    retained, historical/research reproduction

---

## 1. WHAT IS DECIDED, AND WHAT IS EXPLICITLY NOT

**Rejected — one mechanism, and only this one:**

> the neighbour's trust multiplying the weight of a relation in the
> neighbour-consistency average, `csia/trust_engine/engine.py:110`.

**Not rejected, not deleted, not ablated, and retained in full:**

| | |
|---|---|
| relation topology | 8 nodes, 11 edges, unchanged |
| the 11 relations | every one, with its gate |
| node definitions | unchanged |
| relation ownership | unchanged |
| the trust recursion itself | **kept** — it is the sole cover for `GNSS_FIX_LOSS` and `DUAL_IMU_FAILURE` |
| the frozen v1 engine | **not modified.** Zero diff, still |

`GRAPH_TOPOLOGY ≠ NEIGHBOUR-TRUST PROPAGATION`. Anyone reading this decision
as "delete the graph" would be acting on a claim the experiment never made.

## 2. THE EVIDENCE

### 2.1 Zero incremental benefit on the measured catalogue

Measured twice — without the sequential channel (`T1 − T0`) and with it
(`T4 − T3`). Positive = later = worse.

| mechanism | `T1 − T0` | `T4 − T3` |
|---|---:|---:|
| `GNSS_RAMP_SLOW` | 0.00 | 0.00 |
| `GNSS_RAMP_FAST` | 0.00 | 0.00 |
| `GNSS_FIX_LOSS` | 0.00 | 0.00 |
| `MAG_DEGRADED` | 0.00 | 0.00 |
| `POWER_SAG` | 0.00 | 0.00 |
| `VIBRATION_ANOMALY` | 0.00 | 0.00 |
| `DUAL_IMU_FAILURE` | **+0.28** | **+0.28** |
| `CLEAN` | — both right-censored | — both right-censored |
| `IMU0_BIAS_DRIFT` | — both right-censored | — both right-censored |

**Six of nine identical, two censored in both arms, one regression.** Adding
the sequential channel does not rescue propagation: the incremental value is
the same number before and after.

Source: `PHASE3B_PAIRED_DIFFERENCES.csv`.

### 2.2 A 0.28 s regression on `dual_imu_failure`

    T0 TRUST_FLAT          34.12 s     first NORMAL -> CRITICAL
    T1 TRUST_GRAPH         34.40 s
    T3 FLAT + SEQUENTIAL   34.12 s
    T4 GRAPH + SEQUENTIAL  34.40 s

Propagation is **later on the one safety-critical mechanism where the two
differ at all**, and Phase 3A measured the same sign again downstream:
`CRITICAL → EMERGENCY` at 49.16 s GRAPH against 48.56 s FLAT, 0.60 s later.

The magnitude is a fraction of a second and is stated as such. The **sign** is
what carries the decision: there is no mechanism, anywhere in the catalogue,
on which propagation is earlier.

### 2.3 Attribution cannot be affected — structural, not measured

`csia/diagnosis/bayes.py` is 172 lines and imports exactly four things:

    from dataclasses import dataclass
    import numpy
    from ..prediction.predictors import ew_smooth
    from ..trust_engine.engine import consistency

It imports `consistency` — a pure function of one residual — and **nothing
else from the trust engine**. The string `TrustHistory` does not occur in the
file, and no attribute named `trust` is read anywhere in it (verified by AST,
not by grep).

Therefore the posterior, the leader, identifiability, ambiguity, prior
sensitivity and support state are **graph-independent by construction**. No
experiment could have shown propagation improving attribution, because there
is no path by which it could.

This is why the Phase 3B results show `correct_unique`, `safe_ambiguity`,
`wrong_unique`, `unsupported_unique` and `unavailable` identical across all
five arms on every mechanism — that is a consequence of the code, and a test
asserts it rather than hoping for it.

### 2.4 Legacy reproduction is exact

`TRUST_MODE_REGRESSION.json`, tolerance declared **0.0 before running**:

| axis | LEGACY vs Phase 3A/3B GRAPH | FLAT_V1_1 vs Phase 3A/3B FLAT |
|---|---|---|
| raw trace hash | identical, 9/9 | identical, 9/9 |
| canonical input hash | identical, 9/9 | identical, 9/9 |
| relation bank hash | identical, 9/9 | identical, 9/9 |
| trust trajectory | **bit-identical** (`np.array_equal`), max abs Δ **0.0** | **bit-identical**, max abs Δ **0.0** |
| assurance transitions | identical times and levels, 9/9 | identical times and levels, 9/9 |

    VERDICT: PASS.   Tolerance needed: 0.0.

`LEGACY_NEIGHBOR_PROPAGATION` returns the **frozen `TrustCore` class itself**,
not a re-implementation, so this is not a reproduction that has to be
maintained — it is the same object. Legacy behaviour cannot drift from v1
because there is nothing to drift.

### 2.5 Cost is not the argument

Phase 3B: paired compute differences straddle zero and the minima are out of
rank order. **The graph is cheap** — 22 dict lookups and one multiply per
tick, 64 bytes of inter-tick state.

The case against propagation is the **absence of benefit**, not the presence
of cost. Stating it the other way round would be overselling a result that
does not need it.

## 3. WHY LEGACY IS RETAINED RATHER THAN REMOVED — §2

**The default selection is sufficient.** The old line stays inside the frozen
implementation, where it has to stay anyway: `csia/trust_engine` is FROZEN,
enforced by a git diff against `csia-v1.0-research-final` and by recorded
SHA-256 hashes, and every v1 research result was computed with it.

Consequences deliberately adopted:

- **Phase 5 ports `FLAT_V1_1` only.** Legacy reproduction stays
  Python/reference-only. There is no product requirement to run historical
  propagation on an embedded target, and carrying a second trust weighting
  into C would be dead product complexity in the one place complexity is most
  expensive.
- **Nothing is deleted.** No line is removed from the frozen engine, no
  relation is dropped, no topology change is made.
- If a concrete product requirement for embedded legacy replay ever appears,
  it is a new work package with its own justification — not an assumption
  baked in now.

## 4. WHAT WOULD OVERTURN THIS

Recorded before anyone goes looking for it after the fact, unchanged from
`GRAPH_SIMPLIFICATION_PLAN.md` §5:

- **A genuinely distrusted hub** — a node on many edges whose trust collapses,
  where propagation should matter most. The current topology has no such hub
  and none may be invented now that the graph is losing; such a scenario must
  be added for an independent reason and pre-registered.
- **A denser graph.** Eight nodes and eleven edges is close to a tree.
- **HIL or real-flight data**, where trust trajectories are noisier than in
  deterministic simulation and a 0.047 difference could cross a threshold.
  This is the most plausible of the three, and it is the reason legacy is kept
  selectable rather than deleted.

## 5. WHAT THIS DECISION DOES NOT CLAIM

- It does **not** claim propagation is harmful in general. It claims it earns
  nothing on **this** catalogue, on **this** topology, in **deterministic
  simulation**.
- It does **not** rest on statistical significance, and none is claimed: these
  are deterministic scenario comparisons, and §18 of the Phase 3B brief says
  not to demand significance for them.
- It does **not** cover a GNSS step mechanism, because no step injector exists
  in the frozen `KNOWN_KINDS`.

    TRUST_MODE_REVIEW:  PASS
