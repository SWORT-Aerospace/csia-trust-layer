# SEARCH PROTOCOL — Stage R0.2 frontier selection

Item 40. This file exists so the novelty search itself is reproducible and so
that anyone reading the conclusions can see exactly how much evidential weight
they are entitled to carry.

---

## 0. THE LIMITATION THAT GOVERNS EVERYTHING BELOW

**Zero full texts were read. Not one.**

Item 3 sets the evidence standard for this stage:

> For any paper used to KILL or SUPPORT the final top-three ranking: prefer
> full paper / publisher version / author manuscript / arXiv full text /
> official technical report. Search snippets alone are NOT sufficient to
> assert "paper X does not address Y." If full text cannot be obtained: mark
> `PARTIAL_SOURCE_ONLY` and do not use absence from the snippet as evidence
> of novelty.

This environment cannot obtain full text. Every scholarly host was probed
directly at the start of the session, before any candidate was written down:

```
$ curl -sS -o /dev/null -w "%{http_code}" https://arxiv.org/abs/2301.00001
curl: (56) CONNECT tunnel failed, response 403

$ curl -sS "$HTTPS_PROXY/__agentproxy/status"
  "recentRelayFailures": [
    { "kind": "connect_rejected",
      "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
      "host": "arxiv.org:443" } ]
```

Hosts probed, all returning `000` (no connection established through the
egress proxy):

| host | result |
|---|---|
| `arxiv.org` | 403 CONNECT / EGRESS_BLOCKED |
| `export.arxiv.org` | 000 |
| `dl.acm.org` | 000 |
| `link.springer.com` | 000 |
| `ieeexplore.ieee.org` | 000 |
| `www.sciencedirect.com` | 000 |
| `www.semanticscholar.org`, `api.semanticscholar.org` | 000 |
| `api.openalex.org` | 000 |
| `api.crossref.org` | 000 |
| `openreview.net` | 000 |
| `ntrs.nasa.gov` | 000 |
| `core.ac.uk` | 000 |
| `www.mdpi.com` | 000 |
| `hal.science` | 000 |
| `www.ncbi.nlm.nih.gov` | 000 |

`WebFetch` on `https://arxiv.org/abs/2402.05043` returned
`{"error_type":"EGRESS_BLOCKED","domain":"arxiv.org"}`.

**Consequence, stated plainly:**

1. `full_text_read` is `NO` for **every** row of `PRIMARY_SOURCE_INDEX.csv`.
   All 90 sources are `PARTIAL_SOURCE_ONLY`.
2. No claim in this package of the form *"paper X does not address Y"* is
   made. Where a candidate survives, it survives because the **abstract
   problem it names was not visibly answered in any snippet** — which is a
   much weaker statement, and is recorded as such.
3. Per item 42, **no candidate can receive `PROVED — POSSIBLE NOVEL
   CONTRIBUTION`** out of this stage. The ceiling is `PROVISIONAL`.
4. The selected candidate's Stage-0 prompt therefore opens with a full-text
   gate, not with an experiment. See
   `SELECTED_CANDIDATE_STAGE0_PROMPT.md` §1.

This is not a formality. It is the single largest weakness of this stage and
it is load-bearing for the executive verdict.

---

## 1. SEARCH DATE

2026-09-01 (single session, `claude/code-reviewer-repo-export-zicovg`,
base commit `76eaa17`).

---

## 2. DATABASES / ENGINES USED

| engine | availability | what it returned |
|---|---|---|
| `WebSearch` (Anthropic-side web search, US-indexed) | **working** | title + URL result blocks, plus a short synthesised snippet paragraph per query |
| `WebFetch` (full page → markdown) | **blocked** for every scholarly host | `EGRESS_BLOCKED` |
| `curl` direct | **blocked** by the agent proxy for every scholarly host | 403 CONNECT / 000 |
| Institutional library, Google Scholar, Scopus, Web of Science | **not available** in this environment | — |

So the search is a **single-engine search**. There is no second engine to
cross-check recall against. A source that this engine does not surface is
invisible to this stage, and that is an unquantified recall gap.

---

## 3. QUERIES

36 queries were executed. They are listed verbatim so the search can be
re-run. They are grouped by the candidate family they were aimed at; several
queries served more than one family.

**Candidate A — assurance of the assurance monitor**
1. `runtime assurance monitor itself insufficient evidence self-assurance "runtime assurance" monitor uncertainty 2024 2025`
2. `"monitorability" runtime verification insufficient observations verdict inconclusive abstention monitor`
3. `monitorability under observation loss dynamic monitorability recomputed at runtime available signals verdict determinacy`
4. `vacuous satisfaction runtime monitor silently passes because input unavailable missing signal monitor false negative safety property`
5. `self-diagnosis of safety monitor monitor health monitoring the monitor watchdog coverage aerospace "who monitors the monitor"`
6. `runtime assurance decision module sensor fault false safe verdict monitor blind to degraded sensing input integrity assumption`
7. `simplex architecture run time assurance assumes trusted sensor input decision module degraded sensing monitor cannot detect violation`
8. `Ruchkin confidence monitors verification assumptions conservative composition runtime guarantee holds cyber-physical 2022 2024`

**Candidate B — common-cause / correlated evidence failure**
9. `common-cause failure correlated sensor faults apparent redundancy loss of independence runtime autonomous systems 2024`
10. `runtime detection loss of conditional independence between monitor channels shared upstream estimator effective redundancy degradation`
11. `cross-channel agreement not evidence when channels share upstream source correlated failure voting common mode Littlewood Miller coincident failures`
12. `monitor independence assumption violated monitor shares sensor with controller common input safety monitor cannot be independent`
13. `"diagnostic coverage" IEC 61508 computed at design time online runtime estimation varying coverage safety integrity autonomous`

**Candidate C — runtime structural ambiguity / online diagnosability**
14. `online diagnosability time-varying evidence structure fault hypotheses indistinguishable runtime sensor availability`
15. `diagnosability under intermittent loss of observations dynamic observability discrete event systems robust codiagnosability`
16. `structural analysis fault isolability matrix sensor loss reconfiguration runtime recomputation residual generators available`
17. `Bayesian diagnosability active fault identification 2025 indistinguishable hypotheses information gathering autonomous`
18. `fault detectability depends on operating condition excitation time-varying detectability guarantee not constant runtime monitor coverage`

**Candidate D — online calibration failure without labels**
19. `detect calibration failure without labels unsupervised miscalibration detection distribution shift runtime confidence 2025`
20. `conformal prediction exchangeability assumption violated time series autonomous runtime guarantee invalid distribution shift limitation 2025`

**Candidate E — physics + learned perception assurance**
21. `perception monitor learned uncertainty not ground truth probability conformal prediction runtime assurance UAV SOTIF safety cage 2025`
22. `runtime assurance safety filter assumes accurate state estimation limitation control barrier function measurement error autonomous aircraft`

**Candidate F — adversarial consistency**
23. `stealthy false data injection remains inside consistency manifold undetectable attack secure state estimation UAV 2024 2025`
24. `GNSS spoofing defeats cross-sensor consistency checks all navigation channels agree common mode UAV integrity monitoring RAIM limitation`

**Candidate G — model misspecification / unknown fault**
25. `open-set fault diagnosis unknown fault none of modeled hypotheses explain residual adequacy posterior predictive check runtime`
26. `compositional diagnosis cyber-physical systems 2025 unmodeled fault hypothesis none explain evidence abstain diagnosis`

**Candidate H — safe authority under diagnostic ambiguity**
27. `fault-tolerant control under diagnostic ambiguity set-valued diagnosis authority degradation autonomy level formal relationship`
28. `graceful degradation autonomy authority levels degraded mode fallback minimal risk condition formal justification evidence availability`

**Candidate I — dynamic evidence dependency / data incest**
29. `data incest double counting evidence decentralized fusion covariance intersection common information runtime dependency tracking`
30. `circular validation estimator feedback sensor checked against estimate that uses the sensor innovation gating self-confirming EKF`

**Cross-cutting: monitoring under imperfect information, assurance cases, standards**
31. `runtime verification incomplete unreliable traces monitoring with partial observations state estimation lossy trace gaps`
32. `"uncertainty in runtime verification" survey open challenges future directions Bartocci 2023 taxonomy uncertainty sources`
33. `confidence in assurance cases eliminative argumentation defeaters runtime evidence invalidation Denney Pai Goodenough`
34. `"assurance deficit" safety case runtime residual uncertainty Hawkins Habli McDermid confidence argument deficits`
35. `ASTM F3269 run time assurance standard bounded behavior aviation certification autonomy assumptions runtime monitor evidence`
36. `RTLola stream monitoring unmanned aircraft Volocopter lessons learned limitations sensor validation monitor specification 2024`

---

## 4. INCLUSION CRITERIA

A result was indexed in `PRIMARY_SOURCE_INDEX.csv` if **all** of:

- it is a paper, book, standard, technical report, or official documentation
  (not a vendor blog, marketing page, glossary entry, or aggregator summary);
- its title or the returned snippet identifies a **method, formal result,
  standard clause, or stated assumption** relevant to at least one candidate
  family;
- it is the closest visible work to a specific candidate's problem statement,
  or it is foundational work that could subsume one.

Priority within these: 2022–2026 for the active frontier, foundational work
where it is the thing that would subsume a candidate.

## 5. EXCLUSION CRITERIA

Excluded, and why:

- **Patents.** Several searches returned USPTO documents
  (`image-ppubs.uspto.gov`). Patents are excluded from the source index
  because their claims language cannot be compared to a research gap without
  full text, and they are not usable as kill evidence at snippet depth. This
  is a real exclusion — a patent could in principle subsume a candidate, and
  this stage cannot rule that out.
- **Aggregator and encyclopaedia pages** (`emergentmind.com`,
  `sciencedirect.com/topics/...`, glossary sites). They summarise but are not
  primary.
- **Vendor and consultancy blogs** (functional-safety vendor pages,
  reliability-engineering marketing pages), except `exida`'s IEC 61508
  overview report, which is indexed as a secondary source for the standard's
  own definition of diagnostic coverage and is labelled as such.
- **Off-topic results** returned by keyword collision (LLM-agent papers,
  networking RFCs, unrelated bearing-fault deep-learning papers, oilfield
  monitoring services).
- **ResearchGate mirrors** were kept only where no other locator for the same
  work appeared; they are marked in the `doi_or_url` column and carry the same
  `full_text_read=NO`.

## 6. SCREENING AND REVIEW COUNTS

| quantity | value | how it was obtained |
|---|---|---|
| queries executed | **36** | exact; listed above |
| result rows returned | **~300** | approximate; 8–10 links per query, not tallied row by row |
| distinct URLs screened by title + snippet | **~220** | approximate, after mental de-duplication |
| sources indexed in `PRIMARY_SOURCE_INDEX.csv` | **90** | exact (`S001`–`S090`) |
| sources read in full text | **0** | exact |
| sources read at abstract depth | **0** | exact — abstract pages are on blocked hosts |
| sources read at snippet depth | **90** | exact |

The approximate numbers are marked approximate because no per-row tally was
maintained during the search. The two numbers that matter for the verdict —
**90 indexed, 0 full texts** — are exact.

Item 5 asks for approximately 30–60 serious sources. The index carries 90.
That is not an attempt to inflate the count: because no source could be read
past its snippet, more sources were indexed to compensate for shallow depth,
and the shallow depth is exactly why they cannot substitute for the 30–60
*read* sources item 5 intends. Breadth here is a poor substitute for depth,
and it is recorded as such.

Coverage of item 31's requirement (≥5 CLOSE primary sources per finalist and
≥2 hostile/foundational sources that could subsume it), from the
`candidate_relevance` column:

| candidate | CLOSE | HOSTILE | FOUNDATIONAL | meets item 31 |
|---|---|---|---|---|
| A | 13 | 16 | 1 | yes |
| B | 13 | 2 | 2 | yes |
| C | 8 | 7 | 2 | yes |
| D | 0 | 4 | 1 | n/a (rejected) |
| E | 0 | 6 | 1 | n/a (rejected) |
| F | 0 | 6 | 0 | n/a (rejected) |
| G | 2 | 3 | 0 | n/a (rejected) |
| H | 1 | 3 | 1 | n/a (rejected) |
| I | 0 | 4 | 0 | n/a (rejected) |
| J | 5 | 7 | 0 | yes |
| K | 0 | 1 | 0 | n/a (disqualified) |
| L | — | — | — | shares candidate B's sources; rejected as a special case of B |

## 7. SOURCE-QUALITY LIMITATIONS

Ranked by how much damage each does to the conclusions.

1. **No full text (fatal for novelty claims).** Covered in §0.
2. **Single search engine.** No recall cross-check. Unknown-unknowns are
   entirely unbounded.
3. **Snippet paragraphs are model-synthesised.** The prose returned by
   `WebSearch` alongside the links is a summary produced by a search-side
   model, not a verbatim quotation from the paper. Where this document quotes
   such a snippet it is marked as a *snippet paraphrase*, never as a quotation
   from the source. No page or section number is claimed for any source,
   because none was visible. Item 7 asks for exact section/page references
   "when possible"; here it was never possible, and the
   `OPEN_ASSUMPTION_LEDGER.csv` `section_or_page` column says
   `NOT_AVAILABLE_SNIPPET_ONLY` in every row rather than guessing.
4. **US-indexed search.** Non-English and regionally-indexed venues are
   under-represented.
5. **Patents excluded** (§5).
6. **Standards not read.** ASTM F3269-21, IEC 61508 and ARP4761 are paywalled;
   what is recorded about them comes from secondary descriptions and is
   labelled `SECONDARY_DESCRIPTION`.
7. **Dating.** Several returned arXiv identifiers are 2026 (`26xx.xxxxx`).
   Their years are taken from the identifier and the result title only.

## 8. WHAT WOULD MAKE THIS SEARCH SOUND

The minimum repair, to be executed on a machine with library access before
any experiment is run:

- Obtain and read full text for the sources marked `CLOSE` for the selected
  candidate (currently 8) and for the two hostile/foundational sources.
- For each, extract: assumptions, threat/fault model, formal model, inputs,
  outputs, experimental conditions, limitations, stated future work — into
  `OPEN_ASSUMPTION_LEDGER.csv`, replacing `NOT_AVAILABLE_SNIPPET_ONLY` with
  real section references.
- Re-run the five-part gap test in `TOP_THREE.md` against what the full text
  actually says.
- If any of them already performs the runtime computation the selected
  candidate proposes, **stop and record the kill**. Do not adjust the
  candidate to survive.

Until that is done, everything downstream of this file is `PROVISIONAL`.
