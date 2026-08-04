# Python ↔ native-C equivalence

Recovered at `bc3ed977e14d6eb6c5dc3a8b771b2349337de91a`.
Sources: `csia/native/csia_core.c` (175 lines), `csia/native/__init__.py`,
`tests/test_native.py`.

## What "pinned to Python at 1e-12" actually covers

| Question | Answer | Source |
|---|---|---|
| Which inputs | Randomised synthetic vectors: `elam`, `egate`, `plam`, `pgate`, `hist`, `var_ratio`, `hist_has`, `fresh` — drawn from `np.random.default_rng` exponentials/uniforms, **not** from real scenario residuals | `test_native.py:27-34, 148-155` |
| Which outputs | `out_trust[i]` and `out_ev[i]` per node (trust core); posterior per cause (diagnosis). **α, β, ρ and the four sub-scores are never compared** | `:57-59, 87-88, 122, 176-178` |
| How many vectors | 500 steps (4-node), 300 steps (8-node production), 300 steps (diagnosis), 3 steps (no-evidence) = **1103 tick comparisons** | `:26, 114, 147, 69-73` |
| Which profiles | None. Topology is taken from `build_trust_graph()`; `VehicleProfile` never enters the C path | `:132-137` |
| Which state histories | Sequential stepping carries α/β and the diagnosis EW forward, so history *is* exercised — but only along randomised trajectories | `:26-54, 147-173` |
| Diagnosis included | Yes, separately: `test_native_diag_matches_python`, 300 steps, all 8 causes | `:102-122` |
| Clamps / edge cases | Partly: the no-evidence branch is explicitly covered (`:62-88`), and gates are randomised to 0 at ~25-30% (`:149,151`). Bounds rejection covered (`:91-99`) | |
| Per tick or after a sequence | **Per tick** — asserted inside the loop at every step | `:56-59, 175-178` |

## Classification

**Kernel-level numerical equivalence, test-corpus scoped.**

Justification for that classification, and against the stronger ones:

- Not **full behavioral equivalence**: the C core implements only the trust
  recursion and the diagnosis softmax. It contains no comparator, no edge
  library, no `_SensorSlot`, no scheduler, no freshness logic, no failsafe. The
  README states this plainly (README:126-128: "not currently on any production
  execution path"), and the audit agrees.
- Not merely **partial**: the production 8-node/11-edge topology *is* covered
  (`test_native_parity_on_production_topology`), including the no-evidence
  branch that was a real past divergence (`:62-65` documents the regression:
  "Python divided by zero while C updated the belief with fabricated 0.5
  evidence").
- **Test-corpus scoped** because the inputs are randomised synthetics. No test
  drives the C core with residuals from an actual scenario or flight log, so
  equivalence on the input distribution the system really sees is *not*
  established — only on a distribution that covers the branch structure.

## Gap that materially weakens the claim

`tests/test_native.py:11-12`:
```python
pytestmark = pytest.mark.skipif(not native.available,
                                reason="native core not built")
```
If `csia/native/build.sh` has not been run, **all five parity tests skip
silently** and the suite still reports success. CI runs the build first
(`ci.yml:25`), so CI is honest; a developer running bare `pytest` is not
warned. Recorded as WP1 finding F-N1.

Verified for this audit: the native core was built (`bash csia/native/build.sh`
→ `built: libcsia_core.so`) before the baseline run, so all parity tests
executed rather than skipping.
