# The partition model

Items 22–24. The generic architecture, the partition condition, and the
necessity result — with prior-art status assigned before any of it is used.

## Architecture

```
                 φ_A                      A          operational
raw state R  ──────────►  operational  ──────►       action / admissibility
      │                    projection
      │          φ_D
      └───────────────────►  diagnostic  ──────►      D / diagnostic state
                             projection
```

**Coupled architecture:** `φ_D = f ∘ φ_A` for some `f` — the diagnostic layer
sees the raw state only through the operational projection. The special case
this implementation realises is `D = A`.

**Split architecture:** `φ_D` is computed from `R` independently, and may
preserve distinctions `φ_A` discards.

## Two equivalence relations

`φ_A` induces an equivalence on `R`:

```
r₁ ~_A r₂   ⟺   φ_A(r₁) = φ_A(r₂)
```

The diagnostic task induces another. For a hypothesis set `H`:

```
r₁ ~_D r₂   ⟺   ∀ h_a, h_b ∈ H:
                log p(r₁|h_a)/p(r₁|h_b) = log p(r₂|h_a)/p(r₂|h_b)
```

— two raw states are diagnostically interchangeable exactly when they induce
the same likelihood ratios for every hypothesis pair.

## P1 — Aliasing

**Proposition.** If `φ_D = f ∘ φ_A`, then any diagnostic procedure assigns the
same output to `r₁` and `r₂` whenever `r₁ ~_A r₂`. Consequently, if there exist
`r₁ ~_A r₂` with `r₁ ≁_D r₂`, the coupled architecture cannot realise the
discrimination that `~_D` supports.

**Proof.** `φ_D(r₁) = f(φ_A(r₁)) = f(φ_A(r₂)) = φ_D(r₂)`; a function of
`φ_D` is therefore constant on `~_A` cells. ∎

## P2 — Necessity

**Proposition.** Diagnosing from the operational state alone loses no
information **iff** `~_A` refines `~_D`, i.e. `r₁ ~_A r₂ ⟹ r₁ ~_D r₂`.
Equivalently: information is lost iff

```
∃ h_a, h_b, r₁, r₂ :  φ_A(r₁) = φ_A(r₂)
                      ∧  log p(r₁|h_a)/p(r₁|h_b) ≠ log p(r₂|h_a)/p(r₂|h_b)
```

**Proof.** The stated condition is exactly the failure of the Fisher–Neyman
factorisation criterion for `φ_A` as a statistic for `H`: `φ_A` is sufficient
iff the likelihood ratio is constant within each cell `φ_A⁻¹(a)`, which is the
statement `~_A` refines `~_D`. ∎

**This is item 24's condition, and it is exactly the negation of sufficiency.**

> **Status: PROVED — KNOWN/SUBSUMED.**
>
> P1 and P2 restate the Fisher–Neyman factorisation criterion and the standard
> partition/observation-mask formulation of diagnosability under partial
> observation. `PRIOR_ART_MATRIX.md` records the sources. Neither is claimed as
> a contribution, and the exploratory package's `NOVELTY NOT ESTABLISHED`
> labels are downgraded to `KNOWN/SUBSUMED` accordingly.

## The one statement worth making, and it is not a theorem

What the mathematics *does* license is a design criterion:

> **An assurance architecture that gates diagnosis on its operational
> admissibility variable is asserting that the variable is a sufficient
> statistic for the diagnostic task. That assertion is rarely made
> explicitly, and in this implementation it is false.**

That is a way of *reading* a standard result, not a new result. It is useful
precisely because it turns an architectural question into a checkable one:
enumerate the raw states, ask whether `φ_A` merges any pair with different
likelihood ratios, and if it does, the coupling is losing information.

## Guarding against overreach

The brief asks for counterexamples to any overly broad statement. Three
tempting overstatements and why each is wrong:

**"Coupling always loses diagnostic information."** False. If `~_A` already
refines `~_D` — the operational projection happens to be at least as fine as
the diagnosis needs — coupling loses nothing. A system whose only fault
hypotheses are "this sensor is usable" and "this sensor is not" is exactly
such a case.

**"The split always recovers the lost information."** False, and T3 gives the
condition: only if some observable outside the coupled gate discriminates the
pair. Against transport loss there is nothing to recover.

**"C0 must alias the two mechanisms."** **False in this implementation, and
measured to be false.** `results/DESIGN_FEASIBILITY.json`: under matched `A`,
the coupled arm still differs between sensor-invalid and transport-loss in
`trust_gps` on 857/857 ticks and in `post_gps_fault` on 181/857, because a
propagated invalid sample feeds the *ungated* temporal features while a missing
message feeds nothing. The aliasing is at the level of the **leading cause**
(0/857 differ), not at every level of state.

That last one matters enough to restate: **P1 says a coupled architecture
cannot use what `φ_A` discards, but this implementation is not purely
coupled.** It has a leak — a propagated invalid sample feeds the ungated
`temp_<sensor>` path, a missing message feeds nothing.

## Is the leak usable? Measured, and mostly not

The leak's existence does not make it information. Measured over the matched
interval (`results/DESIGN_FEASIBILITY.json`, `residue_usability`):

| Field | Changes inside the interval? | Max between-mechanism difference | Best single-threshold accuracy |
|---|---|---|---|
| `trust_gps` | **No — frozen** | 0.001313, constant | **1.0000** |
| `post_gps_fault` | yes | 0.004118 | 0.5047 |
| `post_nominal` | yes | 0.004118 | 0.5053 |

Read the `trust_gps` row carefully, because it is a trap. **Trust freezes the
moment `A` closes** — the Beta update is gated on `fresh`
(`csia/trust_engine/engine.py:146`) — so within the scored interval it takes
exactly one value per mechanism and never moves. Its between-mechanism
difference is a **constant inherited from the onset transient that the scored
interval deliberately excludes**. A threshold fitted on this one pair scores
1.0 while carrying no live information at all, and the frozen value depends on
the whole pre-onset trajectory, so across pairs with different onsets the two
classes would interleave and the threshold would be meaningless.

The fields that *do* move — the posteriors — discriminate at chance.

**So the honest correction to the paragraph above: the leak is real but it is
an onset artefact, not usable evidence.** The exploratory framing ("residual
information survives the coupled gate") overstated it, and this document
overstated it in its first draft.

## Consequence for the experiment

C0's failure is therefore **close to analytically forced** once the transient is
excluded, and C2's success is close to tautological given its inputs. Two
outcomes remain live, but they are narrower than first claimed:

1. A single **cross-pair** threshold on raw `trust_gps` stays at chance, C0's
   decision aliases the mechanisms, and the split recovers them.
2. That threshold generalises across pairs after all — in which case **there
   was no need for D to be separate from A** and the claim collapses.

Outcome 2 is why `C0_STRONG` is mandatory, and why its threshold must be
**one value frozen across all ten pairs**. A per-pair threshold would score 1.0
on the artefact above and prove nothing.
