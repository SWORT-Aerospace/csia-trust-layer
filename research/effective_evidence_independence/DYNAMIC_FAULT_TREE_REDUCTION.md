# REDUCTION TEST — DYNAMIC FAULT TREES AND DYNAMIC RELIABILITY

Item 14, and the fourth block of item 2. **Verdict: UNRESOLVED. No full text
obtained.**

---

## The question

Can a DFT / dynamic Bayesian network already compute, online, exactly the
quantity candidate B needs? In particular: is candidate B only *"recompute a
minimal cut set as topology changes"*?

## Decision rule, fixed in advance

| finding | consequence |
|---|---|
| DFT/DBN formalisms represent changing dependency structure and recompute cut sets as topology changes | `KNOWN/SUBSUMED` or application novelty — stop, item 14 |
| they model dependency for *reliability probability* only, and never for the informativeness of a diagnostic comparison | candidate survives this test, provisionally |

## Status

Not obtained. See `REQUIRED_READING_MANIFEST.md` §1.4.

---

## The argument as it stands, with its weakness stated

**For the candidate.** Dynamic fault trees answer a probabilistic question —
how does *reliability* evolve as dependencies, spares and reconfiguration
evolve. Candidate B's question, after the re-centring forced by
`MENGER_CLAIM_COUNTEREXAMPLES.md`, is about the *informativeness of a specific
comparison to a specific fault* at a specific instant. Those are the objects
`INDEPENDENCE_TAXONOMY.md` calls #1 and #3, and they are not the same object.

**Against the candidate — and this is the part that matters.** A minimum vertex
cut of a provenance graph is formally the same kind of object as a minimal cut
set. If the surviving content of candidate B were "recompute the cut set when
the selector moves", item 14's rule fires immediately and the candidate is
subsumed. `FORMAL_REDUCTION.md` §4 shows κ_prov is not even a reliable bound,
so the candidate is worse off than a DFT recomputation, not better.

The only thing that keeps this test open is that the candidate is **no longer
centred on the cut** — §5 of `FORMAL_REDUCTION.md` moves it to residual
sensitivity. But that move hands the candidate to structural FDI instead
(`META_DIAGNOSIS_REDUCTION.md` §3), so it is not an escape.

## Net effect on the candidate

This test does not kill it outright, but it removes the fallback position. If
the FDI reduction closes, there is no retreat to "at least it is a dynamic
cut-set computation", because that is this test's kill condition.
