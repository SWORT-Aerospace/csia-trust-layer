# REDUCTION TEST — COMMON-INFORMATION FUSION AND CONDITIONAL-INDEPENDENCE TESTING

Items 12, and the second block of item 2. **Verdict: UNRESOLVED. No full text
obtained.**

---

## The two questions

**Q1 (fusion).** Does Covariance Intersection / Inverse Covariance
Intersection / data-incest management protect anything other than the
consistency of a *fused estimate*?

**Q2 (item 12 — conditional-independence testing).** Le Caillec-style testing
detects shared information between fusion inputs directly from the signals.
**Could we simply run such a test on the monitor inputs, and if so, what does
source provenance add?**

## Decision rule, fixed in advance

| finding | consequence |
|---|---|
| a shared-information verdict is attached to a *decision* (diagnostic or safety), not only to a covariance | `KILLED_BY_COMMON_INFORMATION_FUSION` |
| the only thing provenance adds over a statistical test is *explainability* | item 12: "that is probably not enough for dissertation novelty" — stop |
| provenance supplies something a signal-level test structurally cannot | candidate survives this test, provisionally |

## Status

Not obtained. The Noack author copy at `isas.iar.kit.edu` — normally the free
route — is blocked along with everything else
(`REQUIRED_READING_MANIFEST.md` §0).

## The honest state of the argument, both ways

**The distinction the frontier report leaned on** was estimate-vs-test: CI/ICI
widen a covariance so a fused estimate stays consistent, which does not restore
a residual's ability to separate hypotheses. That distinction survives as an
*argument*. It has not been checked against text.

**Two things now weigh against it, and both were found in this stage.**

1. **Q2 is the harder question and the frontier report under-weighted it.** A
   conditional-independence test on the monitor's inputs would detect
   counterexample B — the shared physical disturbance with no software edge —
   which the provenance graph provably cannot see
   (`MENGER_CLAIM_COUNTEREXAMPLES.md` §3). On that failure mode the statistical
   test is **strictly better** than κ_prov, not merely an alternative.

2. Where provenance is better is the converse case: a statistical test on
   nominal data may see two channels moving together for benign reasons and
   flag dependence that carries no diagnostic consequence, whereas provenance
   says exactly which node is shared. But that is an *explainability*
   advantage, and item 12 pre-emptively rules that insufficient.

So on the evidence available, the fusion/testing line of attack is **stronger
against the candidate than the previous stage judged**, and the estimate-vs-test
distinction does not by itself rescue κ_prov. It survives only as an argument
about a quantity (residual sensitivity) that this package has already concluded
κ_prov does not measure (`FORMAL_REDUCTION.md` §5).

## What must be read

`REQUIRED_READING_MANIFEST.md` §1.2.
