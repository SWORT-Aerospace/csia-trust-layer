# REQUIRED READING MANIFEST

Item 1. This environment cannot obtain full texts. Item 1 forbids substituting
snippets and requires this manifest plus a stop at
**`INCONCLUSIVE_MISSING_FULLTEXT`** where an unresolved source is capable of
killing the contribution. Every source below is capable of killing it.

---

## 0. ACCESS EVIDENCE, RE-CHECKED THIS STAGE

Not carried over from the previous stage — re-probed at the start of this one:

```
WebFetch https://arxiv.org/abs/2111.03782
  -> {"error_type":"EGRESS_BLOCKED","domain":"arxiv.org"}
```

Direct probes, all returning `000` (no connection through the egress proxy),
including institutional and author-hosted copies, which are normally the way
round a publisher paywall:

| host | purpose | result |
|---|---|---|
| `isas.iar.kit.edu` | author copy of Noack et al., ICI, Automatica 2017 | 000 |
| `ivan.ece.ufl.edu` | author copy of Ruchkin et al., CoCo, ICCPS 2022 | 000 |
| `shemesh.larc.nasa.gov` | NASA RTA papers | 000 |
| `www.csl.sri.com` | Rushby technical reports | 000 |
| `doi.org` | DOI resolution | 000 |
| `citeseerx.ist.psu.edu` | preprint mirror | 000 |
| `www.researchgate.net` | author uploads | 000 |
| `docs.px4.io` | PX4 documentation | 000 |

Publisher hosts (arXiv, ACM, Springer, IEEE, ScienceDirect, Semantic Scholar,
OpenAlex, Crossref, OpenReview, NTRS, CORE, MDPI, HAL, NCBI) were probed in the
preceding stage and recorded at
`research/frontier_selection/SEARCH_PROTOCOL.md` §0; all blocked.

**Full texts read in this stage: 0. Search snippets used to establish absence
of prior art: 0** — item 1 forbids it and no such use is made.

---

## 1. SOURCES REQUIRED BEFORE CANDIDATE B MAY PROCEED

Each row states the exact section needed and what it would decide. A source is
listed only if it can, by itself, close the candidate.

### 1.1 Aircraft common-cause (item 2, first block) — **highest priority**

| | |
|---|---|
| **Source** | SAE **ARP4761** / **ARP4761A**, *Guidelines and Methods for Conducting the Safety Assessment Process on Civil Airborne Systems and Equipment* |
| **Sections needed** | Common Cause Analysis; Common Mode Analysis; independence criteria; dependence diagrams; minimal cut sets; any treatment of reconfiguration or time-varying dependence |
| **Decides** | Whether ARP requires *runtime verification of realised independence*, or only *design-time demonstration that independence mechanisms are not defeated by identified common causes*. Item 15 makes this decisive |
| **If it requires runtime verification** | `KILLED_BY_COMMON_CAUSE_ANALYSIS` |
| **Obtainable via** | SAE subscription, or a university engineering library. Paywalled; not reachable here |
| **Cross-check** | FAA advisory material describing ARP4761 CMA, per item 2 — also unreachable (`faa.gov` blocked) |

### 1.2 Common information / fusion (item 2, second block)

| | |
|---|---|
| **Sources** | Noack, Sijs, Reinhardt, Hanebeck, *Decentralized data fusion with inverse covariance intersection*, **Automatica 2017** · Le Caillec, *Testing conditional independence to determine shared information in a data/signal fusion process*, **Signal Processing 2017** · the graph-theoretic data-incest literature |
| **Sections needed** | The object each protects (estimate vs test); whether a shared-information verdict is ever attached to a *decision* rather than to a covariance; assumptions; limitations; future work |
| **Decides** | Whether the estimate-vs-test distinction this package leans on is real, or already crossed |
| **If Le Caillec attaches shared information to a diagnostic decision** | `KILLED_BY_COMMON_INFORMATION_FUSION` |
| **Note** | The Noack author copy at `isas.iar.kit.edu` is the normal free route and is blocked here |

### 1.3 Structural FDI and meta-diagnosis (item 2, fifth block) — **now the most serious threat**

| | |
|---|---|
| **Sources** | *Meta-Diagnosis in FDI: Reasoning About False Analytical Redundancy Relations* · *Diagnosis based on reliability analysis using monitors and sensors* · the analytical-redundancy-relation and structural-diagnosability literature (Blanke et al.; Frisk/Krysander) |
| **Sections needed** | What invalidates an ARR; whether ARR validity is assessed online; fault-sensitivity analysis of residuals; whether sensitivity is recomputed as the applicable relation set changes |
| **Decides** | Whether "the residual currently in use has lost sensitivity to the fault it is supposed to catch" is already the definition of meta-diagnosis |
| **If yes** | `KILLED_BY_META_DIAGNOSIS` or `KILLED_BY_STRUCTURAL_FDI` |
| **Why it is now first among the technical threats** | `FORMAL_REDUCTION.md` §5 concludes the only defensible quantity is residual fault sensitivity, not κ_prov — and fault sensitivity of residuals is exactly what structural FDI computes |

### 1.4 Dynamic reliability (item 2, fourth block)

| | |
|---|---|
| **Sources** | Dynamic Fault Tree foundational work · *A Review of Dynamic Fault Tree Analysis and Capacity Degradation for Complex Redundant Systems* (2024/2025) · recent avionics DFT / common-cause work |
| **Sections needed** | Whether DFT/DBN formalisms model *changing* dependency structure online, and whether minimal cut sets are recomputed as topology changes |
| **Decides** | Whether "recompute a minimal cut set as topology changes" is already standard |
| **If yes** | `KILLED_BY_DYNAMIC_RELIABILITY` |

### 1.5 Assurance-assumption dependence (item 2, third block)

| | |
|---|---|
| **Source** | Ruchkin, Cleaveland, Ivanov, Lu, Carpenter, Sokolsky, Lee, *Confidence Composition for Monitors of Verification Assumptions*, **ICCPS 2022** |
| **Sections needed** | The conditional-independence assumptions behind composition; shared causes of assumption violation; composition correctness conditions; stated limitations and future work |
| **Decides** | Whether "the constituent monitors share a cause, so the composed confidence is wrong" is already stated as an open problem there — in which case the gap is *named* by prior art rather than open |

### 1.6 Foundational dependence (item 2, sixth block)

| | |
|---|---|
| **Source** | Littlewood & Miller, *Conceptual modelling of coincident failures in multiversion software*, IEEE TSE 1989, or equivalent |
| **Sections needed** | The formal model of correlated failure and what it assumes |
| **Decides** | Nothing on its own — it is already accepted as foundational and as forbidding any claim to the *principle*. Needed for correct attribution, not for the verdict |

---

## 2. VERDICT FORCED BY THIS MANIFEST

Item 1: *"STOP with INCONCLUSIVE_MISSING_FULLTEXT if the unresolved source is
capable of killing the contribution."*

Sources 1.1, 1.2, 1.3 and 1.4 are each individually capable of killing it.
None was obtained.

> **PRIOR-ART VERDICT: `INCONCLUSIVE_MISSING_FULLTEXT`.**

This is not a soft outcome. It means the prior-art question is **not answered**
and no statement of the form "we did not identify a method that…" is made
anywhere in this package, because item 30 permits that sentence only when it is
literally supported by a full-text audit, and there was none.

---

## 3. WHAT TO DO WITH THIS FILE

Hand it to a person with library access. The reading is roughly two to four
days. Sections 1.1 and 1.3 first — on the evidence of this stage those are the
two most likely to end the candidate, and 1.3 has overtaken the fusion
literature that the previous stage ranked highest.
