# REDUCTION TEST — META-DIAGNOSIS AND STRUCTURAL FDI

Item 13, and the fifth block of item 2. **Verdict: UNRESOLVED. No full text
obtained.**

Item 13 calls meta-diagnosis "an especially hostile source". On the evidence
gathered in this stage it is now **the most serious threat to the candidate**,
ahead of the fusion literature the previous stage ranked first. The reason is
in §3.

---

## The question

Does candidate B reduce to *"meta-diagnose whether the current residual
relation is valid"*?

## Decision rule, fixed in advance

| finding | consequence |
|---|---|
| meta-diagnosis already reasons online about whether the residual in use has lost sensitivity to the fault it targets | `KILLED_BY_META_DIAGNOSIS`. Stop |
| structural FDI already recomputes fault sensitivity as the applicable relation set changes | `KILLED_BY_STRUCTURAL_FDI`. Stop |
| both are design-time or model-error-oriented, and neither addresses a relation that is *formally valid but currently uninformative* | candidate survives, provisionally |

## Status

Not obtained. See `REQUIRED_READING_MANIFEST.md` §1.3.

---

## 3. WHY THIS THREAT GREW DURING THIS STAGE

The candidate arrived at this stage centred on κ_prov, a graph quantity, whose
nearest neighbours are common-cause analysis and fusion. Two results in this
stage moved it:

1. `MENGER_CLAIM_COUNTEREXAMPLES.md` refutes κ_prov as a determinant of
   diagnostic diversity in both directions, so κ_prov cannot be the central
   quantity.
2. `FORMAL_REDUCTION.md` §5 concludes that the only defensible quantity left is
   **residual fault sensitivity S_{R,f}** — how much the residual actually in
   use moves under the fault it is supposed to catch.

But **fault sensitivity of residuals is what structural FDI computes.** Fault
signature matrices, isolability analysis and ARR sensitivity are that field's
core apparatus. Meta-diagnosis then asks whether the relation being used is
itself sound.

So the re-centring that the counterexamples force moves the candidate *out* of
the graph/common-cause neighbourhood and *into* the FDI neighbourhood — where
the closest prior art is much closer. That is a worse position than the one the
candidate started in, and it is recorded as such rather than presented as a
sharpening.

## 4. THE ONLY DISTINCTION LEFT TO TEST

If anything survives, it is this narrow shape, and it is written as a question
because it has not been checked:

> Meta-diagnosis, as generally understood, addresses relations that are
> **wrong** — a false ARR, a modelling error, a bad observation. Does any of it
> address a relation that is **formally correct and currently uninformative**,
> because the runtime source selection has made its two arguments the same
> physical measurement?

If the answer is yes — and a treatment of ARR applicability under
reconfiguration would very plausibly say yes — the candidate is subsumed.

**No claim is made here that the answer is no.** Item 30 permits the
"we did not identify…" sentence only when a full-text audit supports it, and
there was none.
