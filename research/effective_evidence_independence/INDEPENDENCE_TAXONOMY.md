# INDEPENDENCE TAXONOMY

Item 10. Three different things are called "independence" in the literatures
this candidate touches. Conflating them is how the frontier report's
terminology went wrong, and keeping them apart is a precondition for the
candidate meaning anything.

---

## 1. FAILURE INDEPENDENCE

**Question.** Do components fail together more often than the product of their
individual failure rates?

**Object.** A joint failure probability, or a β-factor / common-cause group.

**Home.** Reliability engineering; ARP4761 common-cause and common-mode
analysis; IEC 61508; fault trees and minimal cut sets; Littlewood & Miller on
coincident failures in diverse versions.

**Timescale.** Design time. Assessed once, per architecture, and used in a
probabilistic budget.

**What it does not say.** Nothing about whether a particular comparison, at a
particular instant, can see a particular fault. A pair of channels can be
failure-independent and still produce a residual that cannot detect the fault
in question.

---

## 2. STATISTICAL INDEPENDENCE

**Question.** Are two random variables (or two estimates, or two error terms)
independent, or conditionally independent given something?

**Object.** A distributional property: p(x, y) = p(x)p(y), or a
conditional-independence relation, or an unknown cross-correlation between two
estimates.

**Home.** Estimation and fusion — Covariance Intersection and Inverse
Covariance Intersection, common-information management, data incest,
conditional-independence testing of fusion inputs, Bayesian networks and
d-separation.

**Timescale.** Runtime, but on *signals*: the quantities are estimated or
tested from data.

**What it does not say.** Statistical dependence is neither necessary nor
sufficient for diagnostic usefulness. Two strongly dependent channels can still
carry different information about a specific fault (their *difference* can be
informative precisely because they track together in nominal conditions). Two
independent channels can be jointly useless for a fault neither of them
observes.

---

## 3. DIAGNOSTIC INFORMATION DIVERSITY

**Question.** Do several evidence channels supply *distinct* information for
discriminating between the hypotheses actually under consideration?

**Object.** A property of a residual/test relative to a fault set —
sensitivity S_{R,f}, or structural distinguishability of hypothesis pairs.

**Home.** Structural FDI: analytical redundancy relations, fault signature
matrices, isolability, diagnosability, meta-diagnosis of ARR validity.

**Timescale.** Both. Isolability is normally computed at design time from a
structural model; whether the relations are *currently applicable* is a runtime
question.

**This is what candidate B is about.** It is influenced by #1 and #2 and is
identical to neither.

---

## 4. WHY THE DISTINCTION IS LOAD-BEARING

| | #1 failure independence | #2 statistical independence | #3 diagnostic diversity |
|---|---|---|---|
| measured on | components | random variables | residuals w.r.t. a fault set |
| answer is | a probability | a distributional property | a sensitivity / signature |
| assessed | design time | runtime, from data | design time (usually) |
| κ_prov relates to it | loosely — a shared node is a candidate common cause | not at all — a graph edge is not a correlation | not reliably — see below |

`MENGER_CLAIM_COUNTEREXAMPLES.md` shows κ_prov fails to determine #3 in both
directions:

- shared source, different downstream transforms → residual still sensitive
  (#3 present although κ_prov = 1);
- distinct sources, shared physical disturbance → residual blind
  (#3 absent although κ_prov = 2).

So **κ_prov is a fourth thing** — a structural provenance quantity — and it is
not a proxy for any of the three. Calling it "effective independence" asserted
a relationship to #1 and #2 that has not been established. That is why item 5
required the rename, which this package adopts:

> **κ_prov = provenance cut cardinality**, or *structural evidence diversity*.
> Not "effective independence". Not a standard name. Provisional.

---

## 5. WHAT WOULD HAVE TO BE TRUE FOR THE THREE TO LINE UP

Recorded so that a later stage cannot assume it:

For κ_prov to bear on #3, one would need, at minimum:

1. the residual's functional form on each path (to rule out counterexample A);
2. a model of physical/environmental common-mode coupling outside the software
   graph (to rule out counterexample B);
3. a fault set, since #3 is only defined relative to the hypotheses being
   discriminated.

Items 1 and 3 are exactly what structural FDI already requires and already
has. That is the shape of the prior-art threat, and it is why
`META_DIAGNOSIS_REDUCTION.md` treats structural FDI and meta-diagnosis as the
most serious hostile bodies — more serious, on this evidence, than the fusion
literature the frontier report worried about most.
