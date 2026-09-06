# Bibliography — human verification work order

**For:** the research director, or anyone with journal access.
**Why a work order and not a task:** this environment **cannot** do it. The
agent proxy answers **403 at CONNECT** for every publisher and metadata host
tried — `doi.org`, `dl.acm.org`, `ieeexplore.ieee.org`, `link.springer.com`,
`www.sciencedirect.com`, `arxiv.org`, `api.crossref.org`. That is a policy
denial at the gateway, not a TLS problem, not a rate limit, and not something a
retry or a different client fixes. **No further engineering time will be spent
attempting these hosts.**

## The gate

| status | count |
|---|---|
| `UNVERIFIED` — not read at all | **10** |
| `CORROBORATED_NO_PUBLISHER_RECORD` — corroborated from search results, publisher record never seen | **9** |
| **`VERIFIED`** | **0** |

**`publisher_verified = 0`.** While that is true, neither manuscript is
submission-ready if the project's publication gate requires authoritative
verification — and `tools/publication/bib_guard.py` enforces the marker
vocabulary so the state cannot be quietly upgraded in prose.

## What "verified" requires

For each entry: open the **publisher's own record** (not a search result, not a
preprint mirror, not a citation in another paper) and confirm every field
below. Then set `status: VERIFIED`, `checked_by`, `checked_on` and `record`
(the URL or DOI resolved) in `papers/BIB_VERIFICATION_LEDGER.yaml`.

**A search snippet is not a publisher record.** The nine
`CORROBORATED_NO_PUBLISHER_RECORD` entries are already at that level; promoting
them needs the record itself.

### One entry shows why this matters

`dong2024statedependent` was supplied with the title *"Verification of
diagnosability for discrete-event systems under state-dependent observations"*.
Two independent searches place that DOI, volume, issue, page and year on a
**different title by the same authors**. The title was corrected in the ledger.
That correction was possible from search results; confirming which is right
needs the publisher record.

---

## The entries


| # | key | paper | status | fields needing confirmation |
|---|---|---|---|---|
| 1 | `dong2024statedependent` | csia_systems | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 2 | `carvalho2012intermittent` | csia_systems | `UNVERIFIED` | **DOI (absent)**, title, authors, venue, year |
| 3 | `carvalho2013permanent` | csia_systems | `UNVERIFIED` | title, authors, venue, year |
| 4 | `takai2021diagnosability` | csia_systems | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 5 | `yin_phidiagnosability` | csia_systems | `UNVERIFIED` | **DOI (absent)**, title, authors, venue, year |
| 6 | `krysander2024multimode` | csia_systems | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 7 | `krysander2008sensorplacement` | csia_systems | `UNVERIFIED` | title, authors, venue, year |
| 8 | `hurdle2007faulttree` | csia_systems | `UNVERIFIED` | title, authors, venue, year |
| 9 | `reeves2019sensorselection` | csia_systems | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 10 | `kang2024gnss` | csia_systems | `UNVERIFIED` | title, authors, venue, year |
| 11 | `blanke2003ftc` | csia_systems | `UNVERIFIED` | **DOI (absent)**, title, authors, venue, year |
| 12 | `rukhin1997bounded` | gate_conditioning | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 13 | `speekenbrink2025statedep` | gate_conditioning | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 14 | `heitjan1991car` | gate_conditioning | `CORROBORATED_NO_PUBLISHER_RECORD` | **DOI (absent)**, publisher record only |
| 15 | `dong2024statedependent` | gate_conditioning | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 16 | `carvalho2012intermittent` | gate_conditioning | `UNVERIFIED` | **DOI (absent)**, title, authors, venue, year |
| 17 | `carvalho2013permanent` | gate_conditioning | `UNVERIFIED` | title, authors, venue, year |
| 18 | `takai2021diagnosability` | gate_conditioning | `CORROBORATED_NO_PUBLISHER_RECORD` | publisher record only |
| 19 | `krysander2008sensorplacement` | gate_conditioning | `UNVERIFIED` | title, authors, venue, year |

---

## Per-entry detail

### 1. `dong2024statedependent`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** csia_systems  
* **title:** A Uniform Framework for Diagnosis of Discrete-Event Systems with Unreliable Sensors using Linear Temporal Logic  
* **authors:** Dong, Weijie and Yin, Xiang and Li, Shaoyuan  
* **venue:** IEEE Transactions on Automatic Control  
* **year:** 2024  
* **DOI:** `10.1109/TAC.2023.3266021`  
* **authoritative target:** `https://doi.org/10.1109/TAC.2023.3266021`  
* **ledger note:** TITLE CORRECTED 2026-09-04, AND THE CORRECTION MATTERS MORE THAN THE METADATA. The WP-C6 brief supplied the title "Verification of diagnosability for discrete-e  

### 2. `carvalho2012intermittent`

* **status:** `UNVERIFIED`  
* **paper:** csia_systems  
* **title:** Robust diagnosis of discrete event systems against intermittent loss of observations  
* **authors:** Carvalho, Lilian K. and Basilio, Jo{\~a}o C. and Moreira, Marcos V.  
* **venue:** Automatica  
* **year:** 2012  
* **DOI:** **NONE SUPPLIED** — `bib-verify` cannot key on one.  
* **authoritative target:** publisher search by exact title + first author  
* **ledger note:** Complete except that no DOI was supplied, so bib-verify cannot key on one.  

### 3. `carvalho2013permanent`

* **status:** `UNVERIFIED`  
* **paper:** csia_systems  
* **title:** Robust diagnosis of discrete-event systems against permanent loss of observations  
* **authors:** Carvalho, Lilian K. and Moreira, Marcos V. and Basilio, Jo{\~a}o C. and Lafortune, St{\'e}phane  
* **venue:** Automatica  
* **year:** 2013  
* **DOI:** `10.1016/j.automatica.2012.09.017`  
* **authoritative target:** `https://doi.org/10.1016/j.automatica.2012.09.017`  
* **ledger note:** Complete with a DOI; needs confirmation only.  

### 4. `takai2021diagnosability`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** csia_systems  
* **title:** A general framework for diagnosis of discrete event systems subject to sensor failures  
* **authors:** Takai, Shigemasa  
* **venue:** Automatica  
* **year:** 2021  
* **DOI:** `10.1016/j.automatica.2021.109669`  
* **authoritative target:** `https://doi.org/10.1016/j.automatica.2021.109669`  
* **ledger note:** TITLE ADDED 2026-09-04. The brief supplied no title and this copy carried a VERIFY placeholder while the gate_conditioning copy carried a search-derived candida  

### 5. `yin_phidiagnosability`

* **status:** `UNVERIFIED`  
* **paper:** csia_systems  
* **title:** Uniform $\varphi$-diagnosability of discrete-event systems under state-dependent observation  
* **authors:** Yin, Xiang and Gao, Chuanchuan and Li, Shaoyuan  
* **venue:** VERIFY: venue not supplied  
* **year:** VERIFY: year not supplied  
* **DOI:** **NONE SUPPLIED** — `bib-verify` cannot key on one.  
* **authoritative target:** publisher search by exact title + first author  
* **ledger note:** THE WEAKEST ENTRY IN EITHER FILE, and now searched TWICE without a match -- once for the reconstructed title, once for uniform phi-diagnosability attributed to   

### 6. `krysander2024multimode`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** csia_systems  
* **title:** Test Selection for Diagnosing Multimode Systems (Short Paper)  
* **authors:** Krysander, Mattias and Hashemniya, Fatemeh  
* **venue:** International Conference on Principles of Diagnosis and Resilient Systems (DX 2024)  
* **year:** 2024  
* **DOI:** `10.4230/OASIcs.DX.2024.28`  
* **authoritative target:** `https://doi.org/10.4230/OASIcs.DX.2024.28`  
* **ledger note:** TITLE, VOLUME, PAGES AND PUBLISHER ADDED 2026-09-04 from search-index consensus on the DOI; the author order the brief supplied matches. NOT READ.  

### 7. `krysander2008sensorplacement`

* **status:** `UNVERIFIED`  
* **paper:** csia_systems  
* **title:** Sensor placement for fault diagnosis  
* **authors:** Krysander, Mattias and Frisk, Erik  
* **venue:** IEEE Transactions on Systems, Man, and Cybernetics -- Part A: Systems and Humans  
* **year:** 2008  
* **DOI:** `10.1109/TSMCA.2008.2003968`  
* **authoritative target:** `https://doi.org/10.1109/TSMCA.2008.2003968`  
* **ledger note:** Complete with a DOI; needs confirmation only.  

### 8. `hurdle2007faulttree`

* **status:** `UNVERIFIED`  
* **paper:** csia_systems  
* **title:** Fault diagnostics of dynamic system operation using a fault tree based method  
* **authors:** Hurdle, E. E. and Bartlett, L. M. and Andrews, J. D.  
* **venue:** Proceedings of the Institution of Mechanical Engineers, Part O: Journal of Risk and Reliability  
* **year:** 2007  
* **DOI:** `10.1243/1748006XJRR6`  
* **authoritative target:** `https://doi.org/10.1243/1748006XJRR6`  
* **ledger note:** APPEARS TO CONFLATE TWO DIFFERENT PAPERS, and unlike kang2024gnss this one IS cited by main.tex. The title matches a 2009 Reliability Engineering & System Safet  

### 9. `reeves2019sensorselection`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** csia_systems  
* **title:** Sensor selection for fault diagnostics using performance metric  
* **authors:** Reeves, VERIFY: given name disputed and Remenyte-Prescott, Rasa and Andrews, John  
* **venue:** Proceedings of the Institution of Mechanical Engineers, Part O: Journal of Risk and Reliability  
* **year:** 2019  
* **DOI:** `10.1177/1748006X18804690`  
* **authoritative target:** `https://doi.org/10.1177/1748006X18804690`  
* **ledger note:** TITLE ADDED 2026-09-04 from search-index consensus on the DOI. THE FIRST AUTHOR'S GIVEN NAME IS DISPUTED: the brief supplied Adam, the sources give the initial   

### 10. `kang2024gnss`

* **status:** `UNVERIFIED`  
* **paper:** csia_systems  
* **title:** VERIFY: title not supplied by the brief  
* **authors:** Kang, VERIFY: initials not supplied and Hou, VERIFY: initials not supplied and Liu, VERIFY: initials not supplied  
* **venue:** Sensors  
* **year:** 2024  
* **DOI:** `10.3390/s24144445`  
* **authoritative target:** `https://doi.org/10.3390/s24144445`  
* **ledger note:** THE SUBJECT IS WRONG, FOUND 2026-09-04. Search-index consensus places DOI 10.3390/s24144445 on "Sensor Network Attack Synthesis against Fault Diagnosis of Discr  

### 11. `blanke2003ftc`

* **status:** `UNVERIFIED`  
* **paper:** csia_systems  
* **title:** Diagnosis and Fault-Tolerant Control  
* **authors:** Blanke, Mogens and Kinnaert, Michel and Lunze, Jan and Staroswiecki, Marcel  
* **venue:** Springer  
* **year:** 2003  
* **DOI:** **NONE SUPPLIED** — `bib-verify` cannot key on one.  
* **authoritative target:** publisher search by exact title + first author  
* **ledger note:** Reconstructed. TWO later editions exist, not one: 1st 2003 (Springer Berlin, 571 pp), 2nd 2006, 3rd 2015 (DOI 10.1007/978-3-662-47943-8). year = 2003 is a real   

### 12. `rukhin1997bounded`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** gate_conditioning  
* **title:** Information-type divergence when the likelihood ratios are bounded  
* **authors:** Rukhin, Andrew L.  
* **venue:** Applicationes Mathematicae  
* **year:** 1997  
* **DOI:** `10.4064/am-24-4-415-423`  
* **authoritative target:** `https://doi.org/10.4064/am-24-4-415-423`  
* **ledger note:** ADDED 2026-09-04. The prior-art matrix carried this as NOT_FOUND_NEEDS_HUMAN, which was a factual error about the world: multiple independent sources reproduce   

### 13. `speekenbrink2025statedep`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** gate_conditioning  
* **title:** State-Dependent Missingness in Hidden Markov Models, with an Application to Drop-Out in a Clinical Trial  
* **authors:** Speekenbrink, Maarten and Visser, Ingmar  
* **venue:** Psychometrika  
* **year:** 2025  
* **DOI:** `10.1017/psy.2024.3`  
* **authoritative target:** `https://doi.org/10.1017/psy.2024.3`  
* **ledger note:** ADDED 2026-09-04 by the prior-art deep audit. Two independent search queries returned the same volume, issue, page range, year and DOI; the journal is now publi  

### 14. `heitjan1991car`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** gate_conditioning  
* **title:** Ignorability and Coarse Data  
* **authors:** Heitjan, Daniel F. and Rubin, Donald B.  
* **venue:** The Annals of Statistics  
* **year:** 1991  
* **DOI:** **NONE SUPPLIED** — `bib-verify` cannot key on one.  
* **authoritative target:** publisher search by exact title + first author  
* **ledger note:** Project Euclid landing URL and two further indices agree on volume, issue, page range, year and DOI, and reproduce the abstract's CAR-plus-distinctness conditio  

### 15. `dong2024statedependent`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** gate_conditioning  
* **title:** A Uniform Framework for Diagnosis of Discrete-Event Systems with Unreliable Sensors using Linear Temporal Logic  
* **authors:** Dong, Weijie and Yin, Xiang and Li, Shaoyuan  
* **venue:** IEEE Transactions on Automatic Control  
* **year:** 2024  
* **DOI:** `10.1109/TAC.2023.3266021`  
* **authoritative target:** `https://doi.org/10.1109/TAC.2023.3266021`  
* **ledger note:** Carried over from the systems paper's bibliography, including the 2026-09-04 title correction and the open question about why it is cited. See that row.  

### 16. `carvalho2012intermittent`

* **status:** `UNVERIFIED`  
* **paper:** gate_conditioning  
* **title:** Robust diagnosis of discrete event systems against intermittent loss of observations  
* **authors:** Carvalho, Lilian K. and Basilio, Jo{\~a}o C. and Moreira, Marcos V.  
* **venue:** Automatica  
* **year:** 2012  
* **DOI:** **NONE SUPPLIED** — `bib-verify` cannot key on one.  
* **authoritative target:** publisher search by exact title + first author  
* **ledger note:** Carried over from the systems paper's bibliography with its status.  

### 17. `carvalho2013permanent`

* **status:** `UNVERIFIED`  
* **paper:** gate_conditioning  
* **title:** Robust diagnosis of discrete-event systems against permanent loss of observations  
* **authors:** Carvalho, Lilian K. and Moreira, Marcos V. and Basilio, Jo{\~a}o C. and Lafortune, St{\'e}phane  
* **venue:** Automatica  
* **year:** 2013  
* **DOI:** `10.1016/j.automatica.2012.09.017`  
* **authoritative target:** `https://doi.org/10.1016/j.automatica.2012.09.017`  
* **ledger note:** Carried over from the systems paper's bibliography with its status.  

### 18. `takai2021diagnosability`

* **status:** `CORROBORATED_NO_PUBLISHER_RECORD`  
* **paper:** gate_conditioning  
* **title:** A general framework for diagnosis of discrete event systems subject to sensor failures  
* **authors:** Takai, Shigemasa  
* **venue:** Automatica  
* **year:** 2021  
* **DOI:** `10.1016/j.automatica.2021.109669`  
* **authoritative target:** `https://doi.org/10.1016/j.automatica.2021.109669`  
* **ledger note:** The search-derived candidate title this copy already carried is now corroborated on the DOI, and the systems paper copy has been brought into line. NOT READ.  

### 19. `krysander2008sensorplacement`

* **status:** `UNVERIFIED`  
* **paper:** gate_conditioning  
* **title:** Sensor placement for fault diagnosis  
* **authors:** Krysander, Mattias and Frisk, Erik  
* **venue:** IEEE Transactions on Systems, Man, and Cybernetics -- Part A: Systems and Humans  
* **year:** 2008  
* **DOI:** `10.1109/TSMCA.2008.2003968`  
* **authoritative target:** `https://doi.org/10.1109/TSMCA.2008.2003968`  
* **ledger note:** Carried over from the systems paper's bibliography with its status.  

---

## What to do with the result

1. Update `papers/BIB_VERIFICATION_LEDGER.yaml` per entry.
2. Run `make bib-guard` — it enforces the marker vocabulary.
3. Run `pytest tests/test_bib_verification_ledger.py`.

**Do not mark an entry `VERIFIED` from a search result.** The whole reason
`CORROBORATED_NO_PUBLISHER_RECORD` exists as a separate status is that the
distinction was being lost.

## What must NOT be done

* No citation invented to make a guard pass.
* No entry dropped from the manuscript to reduce the count.
* No claim that the manuscripts are submission-ready while
  `publisher_verified = 0`.

