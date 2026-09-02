# TRUST MODE VERSIONING — Phase 4 §2

Phase 3B decided `E: TRUST_FLAT_PLUS_SEQUENTIAL`. §1 of the Phase 4 brief
approves removing neighbour-trust propagation from the default and adds one
constraint that shapes the whole implementation:

> **do NOT erase historical behavior.**

---

## 1. THE TWO MODES

    LEGACY_NEIGHBOR_PROPAGATION     w = float(gate_e) * self.trust[other]
    FLAT_V1_1                       w = float(gate_e)          <-- DEFAULT

`w` is the neighbour-edge weight inside `TrustCore.step`
(`csia/trust_engine/engine.py:110`). It is the entire graph-specific coupling
in the trust update. Everything else — consistency, gates, physics, temporal
and statistical components, the `w_nbr/w_phys/w_temp/w_stat` mixture, `rho`,
the Beta update, freshness handling — is identical in both modes because it is
the same code in both modes.

Implementation: `csia/v1_1/trust_mode.py`.

## 2. WHERE THE FLAG LIVES, AND WHY NOT IN THE ENGINE

**The frozen core was not modified. `csia/trust_engine` still carries zero
diff against `csia-v1.0-research-final`.**

`GRAPH_SIMPLIFICATION_PLAN.md` §4 S2 anticipated this decision and named the
two options: lift the freeze deliberately and re-tag, or carry the flag in a
v1.1 layer outside the frozen path. Phase 4 takes the second, because the
brief asks for both "FLAT is the default" and "frozen v1 must remain
reproducible", and editing the frozen engine would satisfy the first by
breaking the second. The freeze is enforced twice — a git diff against the tag
and recorded SHA-256 hashes in `docs/v1/FROZEN_BASELINE.json` — and its guard
says plainly that it is not a test to update.

So the mode selector sits one level above:

| mode | what it actually returns |
|---|---|
| `LEGACY_NEIGHBOR_PROPAGATION` | `csia.trust_engine.engine.TrustCore` — **the frozen class itself** |
| `FLAT_V1_1` | `FlatTrustCore`, which subclasses it and neutralises one factor |

**Legacy is not a re-implementation.** There is no second copy of the v1 trust
update to keep in sync, so legacy behaviour cannot drift from v1 — it is the
same object. That is a stronger reproducibility guarantee than a flag inside a
modified engine would have given.

`FlatTrustCore` is four lines:

```python
class FlatTrustCore(TrustCore):
    def step(self, edges, phys, hist, var_ratio, fresh):
        self.trust = {n: 1.0 for n in self.names}
        return super().step(edges, phys, hist, var_ratio, fresh)
```

`self.trust` is read in exactly one place inside the frozen `step()` — the
neighbour weight. Presenting it as all-ones for the duration of the call
removes the coupling and nothing else. The frozen method reassigns
`self.trust = new_trust` before returning, so the substitution is redone each
tick, which is what happens.

## 3. SELECTING A MODE

**Real-time path** — `OnlineTrustLayer.core` is a public attribute holding a
freshly constructed core, so `attach_to_online_layer(layer, mode)` assigns it.
No patching, no indirection.

**Batch replay path** — `TrustEngine.run` constructs its core inline, so
`V1_1TrustEngine` substitutes the class name `run()` looks up, scoped to the
call and restored in a `finally`. A test asserts the restoration. The
alternative was copying `run()`, which would duplicate frozen code and create
exactly the drift this design exists to prevent.

`trust_mode_of()` **raises** on an unknown string rather than falling back to
the default: a typo in a trust mode that silently selected FLAT would change
which architecture produced a flight record.

The resolved mode is carried in every ledger event and every API payload
(`trust_mode` field), so a trajectory can never be attributed to the wrong
mode after the fact.

## 4. THE REGRESSION — §3'S STOP GATE

Declared **before** running: `TRUST_TRAJECTORY_TOLERANCE = 0.0`. Exact.

Result over all nine mechanisms (`TRUST_MODE_REGRESSION.json`,
`python engineering/v1_1/phase4/run_p4a.py`):

| axis | LEGACY vs Phase 3A/3B GRAPH | FLAT_V1_1 vs Phase 3A/3B FLAT |
|---|---|---|
| raw trace hash | identical | identical |
| canonical input hash | identical | identical |
| relation bank hash | identical | identical |
| trust trajectory | **bit-identical** (`np.array_equal`), max abs Δ = 0.0 | **bit-identical**, max abs Δ = 0.0 |
| assurance transitions | identical, times and levels | identical, times and levels |

    VERDICT: PASS
    tolerance declared: 0.0
    tolerance actually needed: 0.0

**No tolerance was needed.** That is the expected result and the point of the
construction: if a nonzero tolerance had been required, something would have
been re-implemented that should not have been, and §3 says STOP.

FLAT transitions, reproducing Phase 3B's detection times exactly:

| mechanism | transitions (t, level) |
|---|---|
| `CLEAN` | none |
| `GNSS_RAMP_SLOW` | 32.48 → CAUTION, 42.28 → NORMAL |
| `GNSS_RAMP_FAST` | 24.36 → CAUTION, 42.88 → NORMAL |
| `GNSS_FIX_LOSS` | 26.00 → CAUTION, 38.00 → NORMAL |
| `IMU0_BIAS_DRIFT` | none — correct, redundancy working |
| `DUAL_IMU_FAILURE` | 34.12 → CRITICAL, 48.56 → EMERGENCY |
| `MAG_DEGRADED` | 30.04 → CAUTION, 40.04 → NORMAL |
| `POWER_SAG` | 33.72 → CRITICAL, 47.36 → NORMAL |
| `VIBRATION_ANOMALY` | 34.16 → CRITICAL, 48.00 → NORMAL |

## 5. THE SEQUENTIAL BANK WAS PROMOTED THE SAME WAY

`csia/v1_1/sequential.py` carries the CUSUM as a **stateful per-tick bank**
(one float per covered node) rather than the batch loop the ablation used,
because that is the form Phase 5 ports. It is the same statistic: `k = 0.5`,
`h = 500`, on the pre-transform smoothed chi-square, gated samples skipped.

Proven equal, not assumed: the online bank's first-alarm index equals the
batch `cusum_alarms` index on every mechanism —

    GNSS_RAMP_FAST   gps 529     -> 21.16 s
    GNSS_RAMP_SLOW   gps 610     -> 24.40 s
    MAG_DEGRADED     mag 627     -> 25.08 s
    POWER_SAG        motor_esc 753, battery 755, vibration 884 -> 30.12 s
    VIBRATION        vibration 702 -> 28.08 s
    CLEAN, FIX_LOSS, IMU0, DUAL_IMU   no alarm

Identical to Phase 3B. **Known prior art (Page 1954); no algorithmic novelty
is claimed.**

## 6. WHAT THIS DOES NOT DO

- It does not delete the neighbour-propagation code. Legacy replay needs it,
  and it is the frozen engine, which is not ours to delete.
- It does not change any relation, gate, threshold, weight or likelihood.
- It does not change the v1 default for v1 consumers — a v1 replay that does
  not name a mode is a v1.1 consumer by definition, and a research replay must
  name `LEGACY_NEIGHBOR_PROPAGATION` explicitly. Every existing v1 result
  remains reproducible from the frozen tag with no flag at all.
