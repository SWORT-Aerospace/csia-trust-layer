<!-- publication-guard: research-note -->
# BIBLIOGRAPHY VERIFICATION — CANDIDATES, NOT VERIFICATION

**NO MARKER IN `refs.bib` WAS RETIRED. NOT ONE.**

`refs.bib`'s own header states the rule and it was followed:

> Run `make bib-verify`, which compares every entry against the publisher's
> own Crossref deposit field by field… **A web search result is NOT a
> publisher record and must not be used here**: it is a second unverified
> source, and swapping one for another while deleting the warning leaves the
> risk and removes the notice.

`make bib-verify` needs `api.crossref.org`. Measured this session:

```
api.crossref.org:443   CONNECT -> 403   (organisation egress policy)
doi.org:443            CONNECT -> 403
dblp.org:443           CONNECT -> 403
```

Every publisher-record route is denied. The tool correctly exits 2 and clears
nothing. **The bibliography remains BLOCKED and it blocks submission.**

Retiring a marker without a record is now also mechanically prevented:
`papers/BIB_VERIFICATION_LEDGER.yaml` + `tests/test_bib_verification_ledger.py`
require a `VERIFIED` row naming an accepted route, a checker and a date before
an entry may carry no marker.

## What this file is for

A human doing the verification should not start from a blank page. Below are
**candidates**, each with the search that produced it. Every one carries
`WEB_SEARCH_ONLY — NOT A PUBLISHER RECORD`. Nothing here may be copied into
`refs.bib` without checking it against the publisher.

**Two of the eleven entries look actively wrong**, and those are the findings
worth acting on first. They are §1 and §2.

This file carries the `publication-guard: research-note` opt-out on line 1, so
it can never enter a submission bundle.

---

## 1. `hurdle2007faulttree` — APPEARS TO CONFLATE TWO DIFFERENT PAPERS

**This is the more serious of the two probable errors, because unlike §2 the
entry IS cited by `main.tex`.**

`refs.bib` currently reads:

```
title   = {Fault diagnostics of dynamic system operation using a fault tree
           based method}
journal = {Proc. IMechE Part O: J. Risk and Reliability}
volume = {221}, number = {1}, pages = {43--55}, year = {2007},
doi     = {10.1243/1748006XJRR6}
```

Searching those fields returns **two distinct works by the same authors**:

| | |
|---|---|
| **"System fault diagnostics using fault tree analysis"** | Hurdle, Bartlett, Andrews — *Proc. IMechE Part O: J. Risk and Reliability*, **221**, **43–55**, **2007** |
| **"Fault diagnostics of dynamic system operation using a fault tree based method"** | on ScienceDirect as `S0951832009000313`, i.e. *Reliability Engineering & System Safety*, **2009** |

The entry pairs the **title of the second** with the **journal, volume, pages
and year of the first**. The DOI prefix `1748006X` is the IMechE Part O
journal, which is consistent with the first and not the second.

The entry's own note already says the title was "reconstructed from brief
prose in WP-C5 and was not restated in WP-C6; treat it as VERIFY" — so the
title was always the soft field, and this is what it drifted into.

**Recommended action, for a human:** decide which paper the manuscript's
argument actually needs, then verify that one against the publisher. Do not
simply swap the title: if the argument depends on the 2009 RESS paper, the
journal, volume, pages, year and DOI must all change together.

*(WEB_SEARCH_ONLY. Neither publisher record was consulted.)*

## 2. `kang2024gnss` — APPEARS TO BE FILED UNDER THE WRONG SUBJECT

`refs.bib` places this under the section heading `--- GNSS integrity
monitoring ---` with `journal = {Sensors}, volume = {24}, number = {14},
pages = {4445}, doi = {10.3390/s24144445}`.

A search for that DOI returns:

> **Sensor Network Attack Synthesis against Fault Diagnosis of Discrete Event
> Systems** — Kang, T.; Hou, Y.; Liu, D. — *Sensors* 24(14), 4445, 2024 —
> Special Issue on Anomaly Detection and Fault Diagnosis in Sensor Networks.
> https://www.mdpi.com/1424-8220/24/14/4445

Surnames and every numeric field match. **The subject does not.** That is a
discrete-event-systems sensor-attack paper, not GNSS integrity monitoring.

Candidate initials, `WEB_SEARCH_ONLY`: T. Kang, Y. Hou, D. Liu.

**Recommended action:** this entry is also **uncited by `main.tex`**. Either
verify it, correct the title, initials and section heading, and cite it where
it actually belongs — or drop it. A mis-sectioned entry in a submission is
worse than either.

## 3. `takai2021diagnosability` — missing title

Entry has `Automatica` **129**, article **109669**, **2021**, DOI
`10.1016/j.automatica.2021.109669`; `title` is a literal `VERIFY` placeholder.

Candidate title, `WEB_SEARCH_ONLY`:

> **A general framework for diagnosis of discrete event systems subject to
> sensor failures** — Shigemasa Takai — *Automatica* 129, 109669, July 2021.
> https://www.sciencedirect.com/science/article/abs/pii/S0005109821001898

Author, journal, volume, article number and year all match what is already in
the entry. Only the title is new. Corroborating: the paper's abstract, as
summarised by search, concerns intermittent **and** permanent sensor failures
treated in one framework — which is why `papers/gate_conditioning/refs.bib`
carries this candidate title while the systems paper's copy keeps the
placeholder.

## 4. `krysander2024multimode` — missing title

Entry has DX 2024, OASIcs, **2024**, DOI `10.4230/OASIcs.DX.2024.28`.

Candidate, `WEB_SEARCH_ONLY`:

> **Test Selection for Diagnosing Multimode Systems (Short Paper)** — Mattias
> Krysander, Fatemeh Hashemniya — DX 2024, OASIcs vol. 125, article 28.

The DOI's article number 28 matches. Note the entry may also need
`(Short Paper)` in the title and the OASIcs volume number, which it lacks.

## 5. `reeves2019sensorselection` — missing title

Entry has *Proc. IMechE Part O*, **233**(4), **537–552**, **2019**, DOI
`10.1177/1748006X18804690`.

Candidate, `WEB_SEARCH_ONLY`:

> **Sensor selection for fault diagnostics using performance metric** —
> J. Reeves, R. Remenyte-Prescott, J. Andrews — *Proc. IMechE Part O*,
> 233(4), 537–552, 2019. https://doi.org/10.1177/1748006X18804690

Every numeric field matches and the DOI resolves to that title in two
independent search results. Only the title is new.

## 6. `blanke2003ftc` — the edition risk is REAL, and larger than the note says

The entry warns: *"A later edition exists and this may be citing the wrong
one."* Search confirms **two** later editions, not one:

| edition | year | note |
|---|---|---|
| 1st | **2003** | Springer-Verlag **Berlin**, 571 pp, ISBN 3-540-01056-4 (from a 2005 review) |
| 2nd | **2006** | Springer |
| 3rd | **2015** | Springer, DOI `10.1007/978-3-662-47943-8` |

So the entry's `year = {2003}` is a real 1st-edition year rather than an
invention, and the missing fields are the publisher location (**Berlin**) and
the edition number.

**Recommended action:** decide which edition the manuscript's claim is drawn
from. §Related-work cites it for isolation at the granularity of
reconfiguration; if that argument came from a later edition's treatment, the
page numbering and the DOI differ and citing the 1st would be wrong.

*(WEB_SEARCH_ONLY: the ISBN and page count come from a journal review of the
book, not from the publisher's own record.)*

## 7. `yin_phidiagnosability` — STILL NOT LOCATABLE, SEARCHED TWICE

`refs.bib` marks it `RECONSTRUCTED FROM BRIEF PROSE` with `VERIFY` for both
venue and year, and calls it "the least supported entry in the file". That
assessment stands and is now stronger.

**Two independent searches** — one for the reconstructed title, one for
uniform φ-diagnosability attributed to Yin, Gao and Li under state-dependent
observation — returned **nothing matchable**. Adjacent work by Yin and by
Li exists in the DES diagnosability literature; none of it matches the
reconstructed entry.

**An unsuccessful search is not evidence the work does not exist.** It is
evidence that a reader with the same tools will not find it either, which for
a citation is the operative problem.

**Recommended action:** locate it, or **drop the citation and the sentence
that depends on it**. A reconstructed entry with no locatable source should
not reach a referee.

## 8. Entries needing confirmation only

Complete fields; no reconstruction, no missing title. They need a publisher
check and nothing more.

| key | why it is only a confirmation |
|---|---|
| `dong2024statedependent` | all fields present; the note flags only the title *rendering* as unconfirmed. Cited where the paper **concedes priority**, so a wrong attribution here misdirects a concession |
| `carvalho2012intermittent` | complete except no DOI was supplied, so `bib-verify` cannot key on one — this one needs a title/venue lookup rather than a DOI resolution |
| `carvalho2013permanent` | complete with DOI |
| `krysander2008sensorplacement` | complete with DOI |

---

## Scoreboard

| entry | gap | candidate | status |
|---|---|---|---|
| `hurdle2007faulttree` | **title and venue appear to belong to two different papers** — and it IS cited | two distinct works identified | **UNVERIFIED — resolve first** |
| `kang2024gnss` | **probably wrong subject**; missing title and initials | found, and it contradicts the section heading | **UNVERIFIED — investigate or drop** |
| `takai2021diagnosability` | title | found | UNVERIFIED |
| `krysander2024multimode` | title | found | UNVERIFIED |
| `reeves2019sensorselection` | title | found | UNVERIFIED |
| `blanke2003ftc` | edition, year, location | 1st/2nd/3rd editions identified | UNVERIFIED |
| `yin_phidiagnosability` | everything | **none, after two searches** | UNVERIFIED — least supported |
| the other 4 | confirmation only | n/a | UNVERIFIED |

**11 of 11 entries unverified. `make bib-guard` fails. Systems Paper I cannot
be submitted.**

## What changed since the first version of this file

The first version reported one probable error (`kang2024gnss`) and candidates
for three missing titles. This version adds a **second probable error**
(`hurdle2007faulttree`, §1), resolves the `blanke2003ftc` edition question far
enough to show the risk is bigger than its own note said, and records that
`yin_phidiagnosability` survived a **second** search unfound.

None of that retires a marker. What it does is turn "eleven entries need
checking" into "two need a decision before checking, one may need dropping,
three need a title pasted in, and four need a DOI resolved" — which is a
smaller and better-ordered job for whoever has publisher access.
