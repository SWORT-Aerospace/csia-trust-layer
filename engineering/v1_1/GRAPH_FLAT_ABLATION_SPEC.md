# GRAPH vs FLAT ABLATION — SPECIFICATION AND RESULT

Phase 3A. §§16–22. Engineering: IMPROVED / SIMPLIFIED / OUTPERFORMED.
No novelty language, and none is warranted.

---

## 1. WHAT WAS ABLATED — AND WHAT WAS NOT

**This is the single most important scoping statement in the phase, and
getting it wrong would make the verdict meaningless.**

CSIA's "graph" is two different things wearing one word:

| | | ablated? |
|---|---|---|
| **the edge topology** | which sensor pairs are compared at all — `build_trust_graph()`, 8 nodes, 11 edges | **NO. Retained identically in both arms.** |
| **the trust propagation** | the neighbour's trust weighting each incident edge, so trust flows between nodes | **YES. This is the ablation.** |

The one line, `csia/trust_engine/engine.py:110`:

```python
w = float(gate_e) * self.trust[other]      # GRAPH
w = float(gate_e)                          # FLAT
```

`self.trust[other]` — the *neighbour's* current trust — is the graph-specific
responsibility propagation. An edge to a node that is itself distrusted counts
for less, so blame flows away from the distrusted end.

**FLAT keeps every edge, every gate, every relation.** It averages edge
consistencies by gate alone. Nothing else changes.

## 2. HOW MATCHING IS GUARANTEED (§17, §18)

Not asserted — enforced by construction.

- **Same raw trace.** Both arms consume the *same `td` object in memory*. The
  raw-trace SHA256 is recorded per scenario and is identical by identity, not
  by comparison.
- **Same frozen code.** `FlatTrustCore` **subclasses** the frozen `TrustCore`
  and calls `super().step()` verbatim. No method is copied. Every other line —
  the consistency function, gates, physics/temporal/statistical components,
  the `w_nbr/w_phys/w_temp/w_stat` mixture, `rho`, the Beta update, freshness
  handling — is literally the same code executing.
- **Same diagnosis.** Computed once and shared by both arms (§3 explains why
  that is not a shortcut).
- **Same assurance policy.** The frozen `FailsafePolicy` with the frozen
  `FailsafeConfig`, replayed over each arm's trust trajectory.
- **The GRAPH arm reproduces the frozen pipeline exactly** —
  `np.array_equal(graph_arm.trust, scenarios.run_pipeline().trust)` is `True`.
  If the harness had drifted, this would have caught it.

## 3. THE STRUCTURAL FINDING — ATTRIBUTION CANNOT DIFFER

Before any measurement:

> `csia/diagnosis/bayes.py` imports **only** `consistency` (a pure function)
> from `csia.trust_engine.engine`, and reads `td.hist` — the comparator's
> temporal-stability λ — never `TrustHistory.trust`.

**The diagnosis posterior is therefore structurally independent of the trust
graph.** Correct attribution, wrong attribution, ambiguity and support state
*cannot* differ between GRAPH and FLAT, because the graph never reaches the
diagnosis at all.

That answers §20's primary endpoints outright: on attribution, the graph
earns nothing, and it cannot, by construction. The measurement below therefore
concentrates on where the graph *can* act — trust, and the assurance decisions
driven from it.

## 4. RESULTS

Nine deterministic scenarios, 1500 ticks each. Full data in
`GRAPH_FLAT_RESULTS.csv` and `GRAPH_FLAT_SUMMARY.json`.

| scenario | max abs Δtrust | assurance levels identical | transitions G/F |
|---|---:|---|---|
| `clean` | 0.00140 | yes | 0 / 0 |
| `gps_dropout` | 0.00212 | yes | 2 / 2 |
| `gps_spoof` | 0.01850 | yes | 2 / 2 |
| `imu0_bias_drift` | 0.02237 | yes | 0 / 0 |
| `mag_emi` | 0.04117 | **no** | 2 / 2 |
| `power_sag` | 0.02650 | yes | 2 / 2 |
| `vibration_anomaly` | 0.04713 | yes | 2 / 2 |
| `dual_imu_failure` | 0.04563 | **no** | 2 / 2 |
| `high_speed_dash` | 0.00553 | yes | 0 / 0 |

**Trust never differs by more than 0.047**, against failsafe thresholds
separated by 0.05–0.12.

### The two scenarios where assurance differs

Both have the **same number of transitions, the same levels, and the same
action counts**. Only the *timing* moves:

| | GRAPH | FLAT | Δ |
|---|---|---|---|
| `mag_emi` NORMAL→CAUTION | 30.04 s | 30.04 s | **0.00 s** |
| `mag_emi` CAUTION→NORMAL | 40.08 s | 40.04 s | 0.04 s (one tick) |
| `dual_imu_failure` NORMAL→CRITICAL | 34.40 s | **34.12 s** | 0.28 s |
| `dual_imu_failure` CRITICAL→EMERGENCY | 49.16 s | **48.56 s** | 0.60 s |

**FLAT escalates earlier in both directions on the safety-critical dual-IMU
case** — 0.28 s and 0.60 s sooner. The difference favours FLAT, not GRAPH.
That is not a large effect and it is not presented as one; the point is that
it does not favour the graph.

### Compute (§19, §28)

Seven paired runs with **alternating execution order** to cancel drift:

    GRAPH  median 115.71 us/tick   min 113.32
    FLAT   median 117.47 us/tick   min 111.49
    paired diffs (G-F): 8.65, 5.82, 3.60, 3.79, -4.40, -2.57, -5.94

**The sign changes. The difference straddles zero and is below measurement
noise.** FLAT does strictly less arithmetic, so its true cost cannot be
higher; the measurement simply cannot resolve the gap at this size. Reported
as *no measurable difference*, not as a FLAT win.

### Graph complexity (§19)

8 nodes, 11 edges. The propagation costs one dict lookup and one multiply per
incident edge per node — 22 lookups per tick — and carries 8 extra floats
(64 bytes) between ticks.

**The graph is cheap.** That cuts both ways and is stated rather than glossed:
a cheap component needs less benefit to justify keeping, so the case for
removal rests on the benefit being *absent*, not on the cost being high.

## 5. VERDICT (§22)

    GRAPH_NO_MATERIAL_GAIN

- **Attribution:** the graph cannot affect it. Structural, not measured.
- **Trust:** max |Δ| = 0.047 over nine scenarios.
- **Assurance:** identical in 7 of 9; in the other two only timing moves, by
  0.04–0.60 s, and **in FLAT's favour**.
- **Compute:** no measurable difference.

Per §22, `GRAPH_SIMPLIFICATION_PLAN.md` is written and **the graph is not
removed in this commit.** That is deliberate: §22 requires ChatGPT review
before removal, and the plan explains why the recommendation is narrower than
"delete the graph".

## 6. WHAT THIS RESULT DOES NOT SAY

- **It does not say the trust graph's edges are useless.** They were never
  ablated. Every relation is present in both arms and every one of them
  contributes evidence. Removing the edge topology would be a completely
  different experiment with a completely different expected answer.
- **It does not say the graph never helps.** It says that on these nine
  deterministic scenarios, with this 8-node topology, it does not. A denser
  graph, or one with a genuinely distrusted hub, could behave differently —
  and §21 forbids inventing such a scenario now that the graph is losing.
- **It is not a novelty claim.** It is an engineering ablation of one
  production coupling.
