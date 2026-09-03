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

## What this file is for

A human doing the verification should not start from a blank page. Below are
**candidates** for the fields `refs.bib` is missing, each with the search
result it came from. Every one carries `WEB_SEARCH_ONLY — NOT A PUBLISHER
RECORD`. Nothing here may be copied into `refs.bib` without checking it
against the publisher.

This file carries the `publication-guard: research-note` opt-out on line 1, so
it can never enter a submission bundle.

---

## FINDING 1 — `kang2024gnss` is almost certainly filed under the wrong subject

**This is not a missing field. It is a probable wrong entry.**

`refs.bib` places this under the section heading `--- GNSS integrity
monitoring ---` with `journal = {Sensors}, volume = {24}, number = {14},
pages = {4445}, doi = {10.3390/s24144445}`.

A search for that DOI returns:

> **Sensor Network Attack Synthesis against Fault Diagnosis of Discrete Event
> Systems** — Kang, T.; Hou, Y.; Liu, D. — *Sensors* 24(14), 4445, 2024 —
> Special Issue on Anomaly Detection and Fault Diagnosis in Sensor Networks.
> https://www.mdpi.com/1424-8220/24/14/4445

The surnames and the numeric fields match. **The subject does not.** That is a
discrete-event-systems sensor-attack paper, not GNSS integrity monitoring.

Candidate initials, `WEB_SEARCH_ONLY`: T. Kang, Y. Hou, D. Liu.

**Recommended action, for a human:** this entry is also **uncited by
`main.tex`**. Either (a) verify it, correct the title, initials and section
heading, and cite it where it actually belongs, or (b) drop it. Leaving a
mis-sectioned entry in a submission is worse than either.

---

## FINDING 2 — `takai2021diagnosability`, missing title

`refs.bib` has `journal = {Automatica}, volume = {129}, pages = {109669},
year = {2021}, doi = {10.1016/j.automatica.2021.109669}` and
`title = {VERIFY: title not supplied by the brief}`.

Candidate title, `WEB_SEARCH_ONLY`:

> **A general framework for diagnosis of discrete event systems subject to
> sensor failures** — Shigemasa Takai — *Automatica* 129, 109669, July 2021.
> https://www.sciencedirect.com/science/article/abs/pii/S0005109821001898

Author, journal, volume, article number and year all match what is already in
the entry. Only the title is new.

---

## FINDING 3 — `krysander2024multimode`, missing title

`refs.bib` has `booktitle = {DX 2024}, series = {OASIcs}, year = {2024},
doi = {10.4230/OASIcs.DX.2024.28}` and a `VERIFY` title.

Candidate title, `WEB_SEARCH_ONLY`:

> **Test Selection for Diagnosing Multimode Systems (Short Paper)** — Mattias
> Krysander, Fatemeh Hashemniya — DX 2024, OASIcs vol. 125, article 28.
> https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.DX.2024.28

The DOI's article number 28 matches. Note the entry may need `(Short Paper)`
and the OASIcs volume number 125.

---

## FINDING 4 — `reeves2019sensorselection`, missing title

`refs.bib` has `journal = {Proc. IMechE Part O: J. Risk and Reliability},
volume = {233}, number = {4}, pages = {537--552}, year = {2019},
doi = {10.1177/1748006X18804690}` and a `VERIFY` title.

Candidate title, `WEB_SEARCH_ONLY`:

> **Sensor selection for fault diagnostics using performance metric** —
> J. Reeves, R. Remenyte-Prescott, J. Andrews — *Proc. IMechE Part O*, 233(4),
> 537–552, 2019. https://doi.org/10.1177/1748006X18804690

Every numeric field matches. Only the title is new.

---

## FINDING 5 — `yin_phidiagnosability` remains the weakest entry

`refs.bib` marks it `RECONSTRUCTED FROM BRIEF PROSE` with `VERIFY` for both
venue and year, and calls it "the least supported entry in the file". That
assessment stands: **no candidate was found.** Searches for uniform
φ-diagnosability attributed to Yin, Gao and Li returned nothing that could be
matched to the reconstructed title.

**Recommended action:** either locate it or drop the citation and the sentence
that depends on it. A reconstructed entry with no locatable source should not
reach a referee.

---

## FINDING 6 — `blanke2003ftc` edition risk is real

`refs.bib` already flags it: *"A later edition exists and this may be citing
the wrong one."* Blanke, Kinnaert, Lunze and Staroswiecki, *Diagnosis and
Fault-Tolerant Control*, Springer — later editions are known to exist. The
year, edition and publisher location all need a publisher check.

---

## FINDING 7 — no candidate needed

These entries have complete fields and only need confirmation, not
reconstruction:

| key | why |
|---|---|
| `dong2024statedependent` | all fields present; the `note` says the title rendering is unverified |
| `carvalho2012intermittent` | complete except no DOI was supplied; Automatica 48(9), 2068–2078, 2012 |
| `carvalho2013permanent` | complete with DOI |
| `krysander2008sensorplacement` | complete with DOI |
| `hurdle2007faulttree` | complete with DOI; the title was reconstructed from WP-C5 prose and the `note` says treat it as VERIFY |

---

## Scoreboard

| entry | gap | candidate found | status |
|---|---|---|---|
| `kang2024gnss` | **probably wrong subject**, missing title and initials | yes, and it contradicts the section heading | **UNVERIFIED — investigate or drop** |
| `takai2021diagnosability` | title | yes | UNVERIFIED |
| `krysander2024multimode` | title | yes | UNVERIFIED |
| `reeves2019sensorselection` | title | yes | UNVERIFIED |
| `yin_phidiagnosability` | venue, year, everything | **no** | UNVERIFIED — least supported |
| `blanke2003ftc` | edition, year, location | no | UNVERIFIED |
| the other 5 | confirmation only | n/a | UNVERIFIED |

**11 of 11 entries unverified. `make bib-guard` fails. Systems Paper I cannot
be submitted.**
