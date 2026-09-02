# GRAPH SIMPLIFICATION PLAN

Required by §22 (Phase 3A) and §30 (Phase 3B). The Phase 3A verdict was
`GRAPH_NO_MATERIAL_GAIN`; **Phase 3B confirms it with the sequential channel
present**, and the final architecture decision is
`E: TRUST_FLAT_PLUS_SEQUENTIAL`.

> **Nothing in this plan has been executed.** §22: *"Do not remove graph in
> the same commit before ChatGPT review."* The production trust engine is
> unchanged and remains FROZEN.

---

## 1. WHAT IS RECOMMENDED FOR REMOVAL — AND IT IS NARROW

**Recommended for removal: the neighbour-trust weighting.** One factor, one
line, `csia/trust_engine/engine.py:110`:

```python
w = float(gate_e) * self.trust[other]        # today
w = float(gate_e)                            # proposed
```

**NOT recommended for removal: anything else.** In particular the trust graph's
**edge topology stays exactly as it is.** All 11 relations, all gates, all
endpoints. They were never ablated and there is no evidence against them.

Anyone reading "the graph does not earn its complexity" as "delete
`csia/trust_graph`" would be acting on a claim this experiment did not make.

## 1b. THE EXACT PRODUCTION LINE TO CHANGE (§30)

    file:  csia/trust_engine/engine.py
    line:  110
    from:  w = float(gate_e) * self.trust[other]
    to:    w = float(gate_e)

That is the entire change. One line. Nothing else in the file, and no other
file.

**PRESERVE, explicitly:** relation topology (`csia/trust_graph/graph.py`, 8
nodes and 11 edges), node definitions, relation ownership, the diagnosis
feature set (`csia/diagnosis/bayes.py CAUSES`), and the source mappings in
`csia/aircraft/adapters/`. None of these was ablated and none is implicated.

## 1c. PHASE 3B CONFIRMATION

`T4 − T3` — the incremental value of neighbour-trust propagation **after** the
sequential channel is present — differs on exactly one of nine mechanisms:

    DUAL_IMU_FAILURE   T4 (graph) 34.40 s   vs   T3 (flat) 34.12 s

Propagation is **0.28 s later**. It is identical on the other eight. All four
of §18's removal conditions hold, including the tie-breaker that FLAT is equal
or earlier on every meaningful response.

## 2. WHY

| endpoint | finding |
|---|---|
| attribution / ambiguity / support | **cannot** be affected — the diagnosis never reads trust |
| trust trajectory | max abs Δ = 0.047 across nine scenarios |
| assurance levels | identical in 7 of 9 scenarios |
| assurance timing | differs in 2; by 0.04–0.60 s; **in FLAT's favour both times** |
| compute | no measurable difference |

## 3. WHY IT IS NOT A LARGE WIN EITHER

Stated plainly so the plan is not oversold:

- The graph costs 22 dict lookups and 8 floats per tick. Removing it saves
  approximately nothing measurable.
- The benefit is **conceptual, not numeric**: one fewer coupling between
  nodes, one fewer path by which a distrusted sensor can quietly reweight
  another's evidence, and a trust update that is a pure function of a node's
  own incident evidence.
- On the safety-critical `dual_imu_failure` case FLAT reaches CRITICAL 0.28 s
  and EMERGENCY 0.60 s sooner. That is the strongest single argument for the
  change and it is still a fraction of a second.

If the reviewer's judgement is that removing a coupling is not worth a
production change to a frozen core, **that is a defensible reading of this
same evidence.** The data does not compel removal; it compels not *claiming*
the graph helps.

## 4. STAGED PLAN, IF APPROVED

Not to be started without review.

**S1 — freeze.** Tag the current engine. Record the nine-scenario GRAPH
trust matrices and assurance trajectories as the pre-change reference, with
hashes.

**S2 — versioned config, not a deletion.** Add an `EngineConfig` flag —
`neighbour_trust_weighting: bool = True` — defaulting to today's behaviour.
`csia/trust_engine` is FROZEN, so this requires either lifting the freeze
deliberately and re-tagging, or carrying the flag in a v1.1 subclass outside
the frozen path. **The freeze must be broken on purpose and recorded, never
by accident.**

**S3 — re-measure everything that depends on trust.** The v1 research results
that consume trust trajectories, and Phase 2's support results, are computed
over a specific trust path. Changing it invalidates none of them as *v1*
results and requires all of them to be re-measured as *v1.1* results.
`V1_1_ENGINEERING_MANIFEST.md` §5 already carries this discipline.

**S4 — re-run Phase 3A with the flag flipped**, and confirm the FLAT arm and
the flagged production path agree bit-for-bit.

**S5 — decide the default.** Only then.

## 5. WHAT WOULD OVERTURN THIS RECOMMENDATION

Recorded now, before anyone is tempted to go looking for it after the fact:

- A scenario with a **genuinely distrusted hub** — a node on many edges whose
  trust collapses — where propagation should matter most. The current
  topology has no such hub, and §21 forbids inventing a scenario now that the
  graph is losing. If such a scenario is added, it must be added for an
  independent reason and pre-registered.
- A **denser graph**. Eight nodes and eleven edges is close to a tree; trust
  propagation has little room to act. A vehicle with more redundant sensors
  might behave differently.
- **HIL or real-flight data** where trust trajectories are noisier than in
  deterministic simulation, and a 0.047 difference could cross a threshold.
  This is the most plausible of the three, and it is a reason to keep the flag
  rather than delete the code.
