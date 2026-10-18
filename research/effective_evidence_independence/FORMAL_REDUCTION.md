# FORMAL REDUCTION

Items 6, 7, 9, 20. What the mathematical objects are, what can honestly be
said relating them, and — item 20 — which direction the bound actually runs.

---

## 1. OBJECTS

| symbol | object |
|---|---|
| G_t = (V, E_t) | provenance DAG at time *t*; nodes and edges as fixed by `PROVISIONAL_GRAPH_MODEL.md` |
| F ⊆ V | sensing frontier: nodes with no admitted incoming edge (transducers, exogenous inputs) |
| E_v(t) ⊆ V | the evidence variables consumed by verdict *v* at time *t* |
| κ_prov(t, v) | minimum source-separating vertex cut between F and E_v(t) in G_t |
| R_v | the diagnostic relation / residual map producing the comparison behind *v* |
| f | a fault or perturbation, sited at some node |
| S_{R,f}(t) | sensitivity of R_v to f: ∂R_v/∂f where differentiable, otherwise the finite-difference or set-valued equivalent |

**κ_prov is a graph quantity. S is an analytic quantity. They are different
objects and this document does not conflate them.**

---

## 2. ITEM 7 — LANGUAGE DISCIPLINE

Statistical **test power** means P(reject H₀ | H₁). It requires a test, a null,
an alternative and a distribution. None of those is supplied by a provenance
graph.

The frontier report used "zero power" for a structural statement. **That was
imprecise.** Throughout this package the structural notion is called:

- **fault sensitivity** — S_{R,f}, how much the residual moves under a
  perturbation at a site; or
- **structural distinguishability** — whether two hypotheses induce different
  residual behaviour at all.

"Power" is used only where an actual statistical test is specified. It is not
specified anywhere in this package, so the word does not appear as a claim.

---

## 3. ITEM 9 — WHAT CAN BE SAID, AND WHY IT IS NEARLY EMPTY

The candidate statement item 9 permits *only if true*:

> If all evidence variables in E_v(t) are functions of a common corrupted
> latent variable *c*, and R_v is invariant to perturbations in *c*, then
> ∂R_v/∂f = 0.

This is true, and it is **a tautology dressed as a theorem**: the conclusion is
a restatement of the hypothesis "R_v is invariant to perturbations in *c*". It
carries no content. Item 9 says as much and instructs that the real question be
attacked aggressively:

> The research question is whether graph structure can certify such invariance
> WITHOUT already having the complete functional model.

**Answer, from `MENGER_CLAIM_COUNTEREXAMPLES.md`: it cannot.**

- Counterexample A: κ_prov = 1 with f₁′ ≠ f₂′ gives ∂R/∂δ ≠ 0. Graph structure
  is consistent with both blindness and sensitivity, so it does not certify
  invariance.
- Counterexample B: κ_prov = 2 with a shared physical disturbance gives
  ∂R/∂ε = 0. Graph structure is consistent with both, in this direction too.

Graph separation is therefore **neither necessary nor sufficient** for the
invariance the claim needs. It cannot certify it.

The only surviving formal statement is the trivial one above, and this package
does not present it as a contribution.

---

## 4. ITEM 20 — BOUND DIRECTION, DERIVED RATHER THAN ASSERTED

Item 20 requires the direction to be worked out and proved, not asserted.
Doing so **overturns the statement made in the frontier report.**

> `research/frontier_selection/SELECTED_CANDIDATE_FORMAL_TARGET.md` §6, proof
> obligation PO-2, asserts: *"a missing edge inflates κ … κ_t is an upper bound
> on effective independence."*
>
> **That is wrong.** The derivation below gives the opposite for omitted edges,
> and shows that no single bound direction holds in general.

Two distinct audit error modes have opposite effects, and they must be
separated.

### 4.1 Error mode 1 — omitted edges (a dependency exists; the audit missed it)

Let G be the true graph and Ĝ the audited graph with Ĝ ⊆ G (same node set,
edge set a subset).

Removing edges cannot create paths. So the maximum number of vertex-disjoint
F→E_v paths in Ĝ is ≤ that in G. By Menger's theorem the minimum vertex cut
satisfies

    κ_prov(Ĝ) ≤ κ_prov(G)

**Omitted edges make κ_prov an UNDER-estimate.**

*Worked case.* True edges {s₁→a, s₁→b, s₂→b}: paths s₁→a and s₂→b are
vertex-disjoint, κ = 2. Audit misses s₂→b, leaving {s₁→a, s₁→b}: every path
runs through s₁, κ̂ = 1. 1 < 2. ∎

**Consequence:** an audit that misses edges reports *more* independence
deficits than exist. It produces **false deficits** — the direction that
flatters the researcher's hypothesis. That is the dangerous direction here, and
it is the opposite of what the frontier report claimed.

### 4.2 Error mode 2 — aliasing (two graph nodes are one physical object)

Suppose accel readings reach two channels through what is physically one
buffer, but the audit models it as two nodes (say because two source files each
name a local variable).

Then paths that share a physical object appear vertex-disjoint. Splitting one
node into two can only increase the number of disjoint paths, so

    κ_prov(Ĝ) ≥ κ_prov(G)

**Aliasing makes κ_prov an OVER-estimate**, and hides real deficits.

### 4.3 The honest conclusion

Both error modes are ordinary in a source audit: dynamic dispatch, conditional
compilation and configuration-dependent wiring cause omissions; identifying
whether two names denote one object across module boundaries causes aliasing.

> **κ_prov is neither an upper nor a lower bound on true structural diversity
> in general.**
>
> - It is a **lower** bound under the assumption that node identity is complete
>   and correct (no aliasing).
> - It is an **upper** bound under the assumption that all dependency edges
>   were found (no omission).
> - **Neither assumption is discharged by a source audit**, and the audit's own
>   extraction rules exclude whole classes of dependency (shared clock,
>   calibration, power, physical environment) that are known to exist.

Any experiment built on κ_prov must therefore state which assumption it is
relying on, per verdict, and must not report deficits as if the bound ran one
way.

---

## 5. THE OBJECT THAT WOULD ACTUALLY MATTER

Item 6 says the candidate is only interesting if a **structural change** causes
a change in **diagnostic sensitivity**. Items 26 and 27 say the scientific
question is *does diagnostic distinguishability change*, not *does κ change*.

Given §3 and §4, the honest position is:

- κ_prov cannot be the primary quantity. It neither measures nor certifies
  S_{R,f}.
- S_{R,f} *can* be measured — but measuring it requires the residual, the fault
  model and a perturbation, i.e. the ordinary machinery of structural FDI
  sensitivity analysis. Which raises the prior-art question that this stage
  could not answer: **is that just fault sensitivity analysis, recomputed?**

That question is unresolved and is the first item in
`REQUIRED_READING_MANIFEST.md`.
