# PRIOR-ART REDUCTION — THE FIVE PROBLEMS

Item 4. Candidate B survives only if it cannot be reduced without residue to
one of P1–P4. This document states each neighbouring problem, states P5, and
gives the honest position on the reduction — which, for every one of them, is
**unresolved**, because no full text was obtained.

---

## P1 — DESIGN-TIME COMMON-CAUSE ANALYSIS

*Can one failure defeat redundant channels?* — ARP4761 CCA/CMA, fault trees,
common-cause groups, minimal cut sets.

**Reduction status: UNRESOLVED.** `ARP4761_CCA_REDUCTION.md`. The standard is
paywalled. The specific unanswered question is whether ARP already treats a
redundancy manager's reconfiguration as a design-time condition, in which case
"the selector moved" adds nothing.

---

## P2 — CORRELATED ESTIMATE FUSION

*How do we fuse estimates consistently under unknown common information?* —
CI, ICI, data-incest management, conditional-independence testing.

**Reduction status: UNRESOLVED, and weaker for the candidate than the previous
stage judged.** `COMMON_INFORMATION_REDUCTION.md`. A signal-level
conditional-independence test detects the physical-common-mode case that a
provenance graph provably cannot see; on that failure mode it is strictly
better than κ_prov.

---

## P3 — DYNAMIC RELIABILITY / REDUNDANCY

*How does reliability evolve as dependencies, reconfiguration, spares and
common-cause failures evolve?* — DFT, Markov, Bayesian reliability.

**Reduction status: UNRESOLVED.** `DYNAMIC_FAULT_TREE_REDUCTION.md`. If the
surviving content were "recompute a minimal cut set as topology changes", item
14 fires and the candidate is subsumed. The counterexamples remove that
fallback anyway.

---

## P4 — DIAGNOSTIC MODEL / RESIDUAL VALIDITY

*Is the analytical redundancy relation itself valid?* — meta-diagnosis, ARR
analysis, diagnosability, structural FDI.

**Reduction status: UNRESOLVED, and now the most serious threat.**
`META_DIAGNOSIS_REDUCTION.md` §3. The counterexamples force the candidate off
κ_prov and onto residual fault sensitivity — which is structural FDI's own
apparatus. The re-centring moves the candidate *closer* to its nearest prior
art, not further.

---

## P5 — RUNTIME DIAGNOSTIC EVIDENCE STRUCTURE

The problem the candidate would have to own:

> Does the evidence currently feeding a specific diagnostic/assurance verdict
> still possess enough distinct causal structure for the comparison being
> performed to discriminate the fault family it claims to monitor?

Item 4: *"Do not assume P5 is distinct. Prove the distinction from full text or
kill it."*

**No full text was obtained. The distinction is therefore NOT PROVED.**

Item 4 offers two outcomes and this stage can reach neither: the distinction is
not proved, and the candidate is not killed by a source this stage could read.
That is precisely what `INCONCLUSIVE_MISSING_FULLTEXT` means, and it is why the
stage stops rather than proceeding to Stage 0B.

---

## WHAT THIS STAGE *DID* SETTLE, WITHOUT LITERATURE

Two things, neither of which needed a paper, and both of which cut against the
candidate's original formulation:

**1. κ_prov cannot be the central quantity.** Item 11's hostile null
H_KILL_PROVENANCE is correct in both directions — shared source with different
downstream transforms leaves the residual sensitive; distinct sources with a
shared physical disturbance leave it blind
(`MENGER_CLAIM_COUNTEREXAMPLES.md`). Item 11's instruction is then binding:
κ_prov is not sufficient, and it is not redefined here to make it sufficient.

**2. The bound direction in the frontier report was wrong.** Omitted edges make
κ_prov an *under*-estimate, not an over-estimate; aliased nodes make it an
over-estimate; neither bound holds in general
(`FORMAL_REDUCTION.md` §4). The frontier report's PO-2 asserted the opposite
and is superseded by this document. Per the v1.1 brief's instruction not to
rewrite frontier-selection artifacts, `research/frontier_selection/` is left
byte-identical and the correction lives here.

And one thing that cuts *for* it:

**3. The runtime topology genuinely changes.** ArduPilot's `VIBRATION`
provenance follows `_first_usable_accel`, reassigned every main-loop iteration
from sensor health, with no instance field on the wire
(`RUNTIME_TOPOLOGY_SOURCE_AUDIT.md`). Item 16's gate passes; the verdict is not
`STATIC_DEPENDENCE_ONLY`.

But (3) is weakened by the discovery that PX4 already publishes exactly this as
`SensorSelection`, which reframes the ArduPilot finding as a telemetry gap in
one stack rather than a conceptual gap in the field.
