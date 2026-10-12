# Prior-art matrix — assurance under conflicting semantic authorities

Items 4–6, 43. Searched August 2026, **before** the model was built.

## Method, and its limit

Web search returning titles, venues and snippets. **Full-text retrieval is
blocked by this environment's egress policy for every scholarly host tried.**
Every row rests on title, venue and snippet. That can only cause prior art to
be understated, so the `KNOWN/SUBSUMED` findings are safe and the "surviving
difference" column should be assumed too generous.

## Headline

**Every component is established, in four separate literatures.**

| component of the proposal | subsumed by | status |
|---|---|---|
| multiple authorities that may disagree; inconsistency *tolerated* rather than resolved | **ViewPoints / multi-perspective specification** (Finkelstein, Nuseibeh, Kramer, Hunter; TSE 1994, TOSEM 1998, SEJ 1996) | KNOWN/SUBSUMED |
| set-valued interpretation, no weights, decision robust iff invariant over the set | **credal sets / imprecise probability / distributionally robust optimization** | KNOWN/SUBSUMED |
| multiple implementations of one interface disagreeing on identical raw input | **parser differentials / LangSec**; ParDiff (OOPSLA 2024); N-version programming | KNOWN/SUBSUMED |
| conflicting evidence in a safety argument | **Dempster–Shafer safety-case confidence**; evidence-theory fault diagnosis with conflicting reports | KNOWN/SUBSUMED |

Item 44's proposition — *"y is robust iff F(C,w) = y for all C ∈ 𝒞"* — is the
textbook definition of robustness over an ambiguity set. The brief predicts it
is tautological. It is.

## Matrix

| Work | Year | Venue | Authority types | May conflict? | Conflict representation | Privileged authority? | Set-valued output? | Abstention? | Downstream safety decision? | Real interfaces? | Minimal traces? | Diagnostic consequence? | Exact overlap | Surviving difference |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ViewPoints / inconsistency handling** (Finkelstein et al.; Hunter & Nuseibeh TSE'94; Easterbrook & Nuseibeh SEJ'96; *Managing inconsistent specifications* TOSEM'98) | 1993–98 | TSE, TOSEM, SEJ | stakeholder perspectives, each with its own partial specification | **yes, by design** | logic-based; inconsistency tolerated and used to trigger action | **no — explicitly not** | reasoning over inconsistent sets | yes | requirements, not runtime | no | no | no | **Total** on the framing: multiple authorities, disagreement as the object, resolution deliberately deferred | requirements-time; no sensor interfaces; no runtime assurance consequence |
| **Credal sets / imprecise probability / DRO** | 1991– | many | sets of models | n/a | convex set of distributions | no | **yes** | yes | yes | no | no | no | **Total** on the mathematics of item 44 and of set-valued output | no semantics-of-interfaces content |
| **Parser differentials / LangSec** (*A Survey of Parser Differential Anti-Patterns*, LangSec 2023; HTTP request smuggling; ParDiff OOPSLA 2024) | 2011– | LangSec, USENIX, OOPSLA | multiple implementations of one format | **yes — the whole subject** | disagreement on identical input, as a *vulnerability* | no | no | no | security consequence, yes | **yes** | yes (ParDiff) | no | **Total** on cross-consumer disagreement over one raw input, including the security framing item 48 raises | no protocol-vs-producer axis; no assurance/diagnosis layer |
| **Dempster–Shafer safety-case confidence; conflicting-evidence fusion** | 2011– | safety/RE venues, Symmetry 2026 | evidence items in an assurance argument | **yes** | belief functions; conflict coefficient | no | belief intervals | yes | **yes, that is the point** | no | no | partly | **Total** on "an assurance argument with conflicting evidence" | weights and combination rules everywhere — which item 10 forbids here |
| **N-version programming / back-to-back testing** | 1977– | FTCS, TSE | independent implementations | yes | voting / disagreement detection | majority | no | no | yes | yes | no | no | High on implementation disagreement | resolves by vote; item 10 forbids that |
| **Paraconsistent logic / belief revision (AGM)** | 1970s– | logic | inconsistent knowledge bases | yes | non-explosive entailment; revision operators | no | yes | yes | no | no | no | no | Total on reasoning without choosing | not about interfaces |
| **Semantic interoperability conflict** (ontology mismatch, OPC UA / DDS type compatibility) | 2000s– | standards, SW eng | schemas and their mappings | yes | mismatch taxonomies | usually one canonical model | no | no | no | yes | no | no | High on "two systems mean different things by one field" | resolution by canonical model, not by preserving the conflict |
| **DES diagnosability under observation masks** | 1995– | DES | observation masks | n/a | partition refinement | n/a | n/a | n/a | yes | no | yes | **yes** | Cited in the previous package; the downstream-consequence half | no authority notion |

## Item 6's kill condition, applied

> multiple competing semantic authorities **+** set-valued interpretation
> under disagreement **+** runtime assurance consequences **+** real
> cyber-physical/autonomy interface evaluation → `KNOWN/SUBSUMED`.

No single work found does all four. ViewPoints has the first with the third
in a requirements sense; credal sets have the second; LangSec has the first
and fourth; Dempster–Shafer safety cases have the first and third.

So the literal conjunction was not found. **That is not a licence to claim
the gap is worth filling** — the same shape recurred in the two previous
packages and both concluded that a combination of established techniques
applied to one codebase is a domain instantiation, not a contribution. And
in this case the empirical result removes the question anyway: see
`CHATGPT_REVIEW_REPORT.md` §1.

## What prior art kills outright

1. Any claim that representing conflicting specifications without resolving
   them is new — ViewPoints, thirty years ago, with "tolerate inconsistency"
   as the stated principle.
2. Any claim that set-valued output under model ambiguity is new — credal
   sets, imprecise probability, DRO.
3. Any claim that robustness-as-invariance is a new proposition — item 44 is
   the definition.
4. Any claim that multiple implementations disagreeing on one raw input is a
   new phenomenon or a new security concern — LangSec parser differentials.
5. Any claim that conflicting evidence in a safety argument is unaddressed —
   Dempster–Shafer safety-case confidence.

## Not searched, and it should be

* Certification treatment (DO-178C, ISO 26262) of a standard that is silent
  where implementations must choose — this is the *actual* problem the GNSS
  case exposes and it was not searched.
* The MAVLink community's own dialect-conflict and interoperability process.
* Formal work on underspecification specifically, as distinct from
  inconsistency; the two are not the same and this package needed the
  distinction.

## Sources

- [Inconsistency Handling in Multi-Perspective Specifications (TSE 1994)](http://www0.cs.ucl.ac.uk/staff/a.hunter/papers/tse94.pdf)
- [Managing inconsistent specifications: reasoning, analysis, and action (TOSEM 1998)](https://dl.acm.org/doi/10.1145/292182.292187)
- [Using ViewPoints for inconsistency management (Software Engineering Journal 1996)](https://digital-library.theiet.org/doi/10.1049/sej.1996.0004)
- [Towards a framework for managing inconsistency between multiple views (Viewpoints '96)](https://dl.acm.org/doi/10.1145/243327.243651)
- [On the interplay between inconsistency and incompleteness in multi-perspective requirements specifications](https://www.sciencedirect.com/science/article/abs/pii/S0950584907000055)
- [Credal Sets: Modeling Epistemic Uncertainty](https://www.emergentmind.com/topics/credal-sets)
- [Making Decisions Using Sets of Probabilities: Updating, Time Consistency, and Calibration](https://arxiv.org/pdf/1401.3906)
- [Bulk-Calibrated Credal Ambiguity Sets](https://arxiv.org/abs/2601.21324)
- [A Survey of Parser Differential Anti-Patterns (LangSec 2023)](https://langsec.org/spw23/papers/Ali_LangSec23.pdf)
- [Parser differentials, ;login: Winter 2020](https://www.usenix.org/system/files/login/articles/login_winter20_06_bratus.pdf)
- [ParDiff: Practical Static Differential Analysis of Network Protocol Parsers (OOPSLA 2024)](https://dl.acm.org/doi/10.1145/3649854)
- [Safety Case Confidence Propagation Based on Dempster-Shafer theory](https://www.researchgate.net/publication/330995896_Safety_Case_Confidence_Propagation_Based_on_Dempster-Shafer_theory)
- [Towards Measurement of Confidence in Safety Cases](https://www.researchgate.net/publication/221494787_Towards_Measurement_of_Confidence_in_Safety_Cases)
- [Uncertainty-Driven Risk Evaluation for Safety-Critical Software Under Conflicting Evidence Judgments](https://www.mdpi.com/2073-8994/18/4/625)
- [Conflicting evidence combination based on uncertainty measure and distance of evidence](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4967071/)
