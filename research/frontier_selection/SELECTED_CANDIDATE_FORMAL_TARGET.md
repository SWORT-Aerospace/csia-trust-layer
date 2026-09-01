# FORMAL TARGET — CANDIDATE B

Item 35. Mathematical objects, proposition candidate, the known theorem it
reduces to, the counterexample needed, the proof obligation, and the novelty
status.

Item 13 says: *"Do NOT force a theorem. A strong systems contribution may use
known mathematics. But label it honestly."* This file is written to that
instruction. **The proposition below is a corollary of a classical theorem and
is labelled as one throughout.**

---

## 1. MATHEMATICAL OBJECTS

**Evidence-provenance graph.** For a system under study, let

    G_t = (V, E_t)

be a finite directed acyclic graph at time *t*.

- *V* is the set of **evidence vertices**: physical transducers, raw protocol
  fields, decoded values, derived channel values, estimator states, and
  monitored channel outputs.
- *E_t ⊆ V × V* is the set of **derivation edges** in force at time *t*:
  `u → w` means the value at *w* at time *t* is a function of the value at *u*.
  Edges are time-indexed because gating, staleness, mode and configuration can
  add or remove a derivation.

**Sensing frontier.** *F ⊆ V* is the set of vertices with no incoming edge —
the physical transducers and other exogenous inputs. These are the only places
a physical fault can originate.

**Verdict and its support.** A monitor emits verdict *v* computed from a
channel set *S(v) ⊆ V*.

**Effective independence.**

    κ_t(v) = min { |C| : C ⊆ V \ (S(v) ∪ F),
                   C separates S(v) from F in G_t }

the size of a minimum vertex cut between the verdict's channel set and the
sensing frontier. Equivalently, by Menger's theorem, the maximum number of
internally vertex-disjoint paths from *F* to *S(v)*.

**Nominal independence.** κ̂(v) is the number of independent evidence sources
the *design* credits for *v* — from a β-factor group, a redundancy claim, an
architectural assertion, or the count of channels the cross-check compares.

**The quantity of interest.**

    Δ_t(v) = κ̂(v) − κ_t(v)

Δ_t(v) > 0 is a **runtime independence deficit**: the verdict is currently
backed by fewer distinct sources than its argument assumed.

**Residual / consistency test.** For a channel pair (a, b) ⊆ S(v), a
consistency test T_ab is a predicate on the observed values that the monitor
reads as evidence of health when it passes.

---

## 2. PROPOSITION CANDIDATE

> **Proposition (structural blindness).** Let (a, b) ⊆ S(v) and suppose every
> path from *F* to {a, b} in G_t passes through a single vertex *c*, i.e. {c}
> is a vertex cut of size 1. Then for any fault modelled as a perturbation of
> the value at *c*, the consistency test T_ab has zero power: the perturbed and
> unperturbed traces are indistinguishable to T_ab.

**Informally:** if two channels' current values are both functions of one
upstream value, comparing them cannot detect a fault in that value. Agreement
between them is not evidence.

**Corollary (verdict-level).** If κ_t(v) = 1 then no consistency test over
S(v) has power against a fault at the cut vertex, and any health inference *v*
draws from agreement is void at time *t*.

---

## 3. THE KNOWN THEOREM IT REDUCES TO

Three, and the reduction is immediate in each case.

**Menger's theorem (1927).** The maximum number of internally vertex-disjoint
paths between two vertex sets equals the minimum size of a vertex cut
separating them. This is the whole content of the equivalence in §1's
definition of κ. Nothing is added.

**d-separation / conditional independence in DAGs (Pearl).** If {c} separates
{a, b} from *F*, then a and b are conditionally independent of the frontier
given c — so all information a and b carry about a frontier fault is already
in c, and their difference carries none of it. The proposition is the
deterministic special case.

**Minimal cut sets in fault-tree analysis.** A minimum vertex cut of a
provenance graph is formally the same object as a minimal cut set of a fault
tree over the same structure. Aerospace common-mode analysis (ARP4761) is the
process built on that object. **If runtime κ is nothing more than a minimal cut
set recomputed at each tick, then this candidate is common-mode analysis with a
clock, and it should be abandoned.** That question is unresolved in this
package and is the first gate of the Stage-0 prompt.

---

## 4. NOVELTY STATUS

| element | status | justification |
|---|---|---|
| Menger / d-separation / min-cut mathematics | `KNOWN/SUBSUMED` | classical |
| "Agreement between commonly-sourced channels is not evidence" | `KNOWN/SUBSUMED` | Littlewood & Miller 1989 (S065); common-cause failure theory |
| The proposition in §2 | **corollary, not a contribution** | follows from Menger plus the definition of a residual |
| κ_t as a *runtime* quantity computed from source-derived provenance | `PROVISIONAL` | not visibly present in any snippet; **cannot be claimed** — no full text was read, and ARP4761 CCA was unreachable |
| The measured incidence of Δ_t > 0 on a real autopilot stack | `CONJECTURE` (no measurement exists yet) | nothing has been run |

**No element reaches `PROVED — POSSIBLE NOVEL CONTRIBUTION`, and none may,
out of this stage.** Item 42 forbids awarding it on the basis that no identical
title was found, and `SEARCH_PROTOCOL.md` §0 establishes that title-and-snippet
is all this stage had.

---

## 5. COUNTEREXAMPLE NEEDED

Two, and the second matters more than the first.

**Counterexample 1 — against the proposition.** A channel pair with κ_t = 1
whose agreement is nevertheless informative. This exists whenever the two paths
apply *independent physical constraints* downstream of the shared vertex — for
example, if a and b are both derived from one raw position but b additionally
incorporates a barometric constraint. Then T_ab retains power against some
faults at *c*. Finding this bounds the proposition's reach, and it should be
looked for deliberately rather than avoided, because a proposition with no
boundary is a proposition with no content.

**Counterexample 2 — against the phenomenon.** A complete real flight in which
Δ_t(v) = 0 for every monitored verdict at every tick. This would refute the
candidate outright and is the cheapest possible outcome. The Stage-0 design is
built so that this outcome is reached first if it is true.

---

## 6. PROOF OBLIGATIONS

If any formal statement is to be made at all, these must be discharged. They
are listed so that a later stage cannot quietly skip them.

**PO-1 — Soundness of graph construction.** Every edge `u → w` in E_t must
correspond to an actual data dependency in the executing system. The obligation
is discharged by pinning each edge to a verified `file:line` in producer or
consumer source and re-reading that line at check time — the citation-verifier
discipline already used in `research/semantic_authority_conflict/authorities.py`,
which caught five bad citations on its first run.

**PO-2 — Completeness of graph construction, or an explicit admission of
incompleteness.** A *missing* edge inflates κ and makes the system look more
independent than it is — the dangerous direction. Because static analysis of
configuration-dependent wiring cannot be assumed complete, the honest position
is that κ_t is an **upper bound** on effective independence, and every reported
value must be labelled as such. A deficit Δ_t > 0 found under an upper bound is
still a real deficit; the reverse inference is not available.

**PO-3 — Time-indexing is real, not cosmetic.** It must be shown that E_t
actually varies with *t* on real data. If E_t is constant, κ is a design-time
quantity and the runtime framing must be dropped (pre-mortem reason 3).

**PO-4 — The proposition's boundary.** Either exhibit counterexample 1 or
state the additional condition under which it cannot occur.

**PO-5 — Distinctness from minimal cut sets and CCA.** A written argument,
against full text, that runtime κ is not ARP4761 common-mode analysis
recomputed. If this obligation cannot be discharged, the candidate is
abandoned rather than reworded.

---

## 7. WHAT IS *NOT* BEING CLAIMED

Stated explicitly so that no later document can drift into claiming it:

- Not that common-cause failure is a new problem. It is from at least 1985–89.
- Not that dependent evidence in fusion is unhandled. Covariance Intersection
  and Inverse Covariance Intersection handle it for the *estimate*.
- Not that the proposition in §2 is a new theorem. It is a corollary.
- Not that agreement-is-not-evidence is a new insight.
- Not that no one has computed a min-cut over a dependency graph. That is
  routine.
- Not that this stage established the absence of prior art. It could not read
  any.

The only thing that could survive is narrow: **a runtime, source-derived,
per-verdict effective-independence count for a safety monitor, and the measured
fact of whether it collapses in real flight without anything noticing.** If
even that is occupied, the candidate dies, and the correct response is to
record the kill.
