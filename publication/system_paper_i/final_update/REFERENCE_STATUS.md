# Paper I — reference verification status, 2026-10-12

## 1. Routes, re-measured today

The ledger `papers/BIB_VERIFICATION_LEDGER.yaml` accepts three routes:
Crossref deposit, publisher page, published PDF. All three remain refused
from this environment, now by two independent mechanisms:

| route | result today |
|---|---|
| `api.crossref.org`, `doi.org`, `export.arxiv.org`, `dblp.org`, `api.openalex.org` via the session proxy | CONNECT refused with 403 (network policy) |
| `api.crossref.org`, `doi.org` and `drops.dagstuhl.de` via the web fetch tool | DNS resolution refused (`ENOTFOUND`) |
| web search | reachable, but a rejected route under the ledger (`WEB_SEARCH`) |

So **no reference can be moved to VERIFIED from here**, and none was. No
ledger status was changed by this work.

## 2. Search corroboration gathered today (not verification)

| key | what search returned | status stays |
|---|---|---|
| `carvalho2013permanent` | one reference list reproduces authors, title, Automatica 49(1):223–231, 2013; DOI not shown | UNVERIFIED |
| `carvalho2012intermittent` | one reference list gives Automatica 48(9):2068–2078, 2012; no DOI found | UNVERIFIED |
| `krysander2008sensorplacement` | the authors' institutional page gives IEEE TSMC-A 38(6):1398–1410, November 2008; DOI not shown | UNVERIFIED |
| `hurdle2007faulttree` | no match for the DOI or the title; the conflation noted in the ledger is unresolved | UNVERIFIED |
| `page1954continuous` (CUSUM) | E. S. Page, "Continuous inspection schemes", Biometrika 41(1–2):100–115, 1954, DOI 10.1093/biomet/41.1-2.100, reproduced by the publisher's issue table of contents as returned by search | not in `refs.bib`; add only after a publisher check |

The four `CORROBORATED_NO_PUBLISHER_RECORD` rows and the remaining UNVERIFIED
rows are unchanged. The three open problems recorded in the ledger still
govern submission: `dong2024statedependent` (title corrected; the reason it is
cited must be checked by reading it), `yin_phidiagnosability` (not found
twice; locate it or drop it with its sentence), and `kang2024gnss` (its DOI is
a discrete-event security paper; uncited by `main.tex`; drop it).

## 3. What the manuscript adds

The owner's manuscript is not in the repository, so its reference list is
unknown. When it arrives, every entry must be put through the same ledger.
Any reference not already in `papers/csia_systems/refs.bib` starts as
UNVERIFIED. Page (1954) is the one this work expects, because Table 9 compares
against a one-sided CUSUM and `csia/v1_1/sequential.py` already names it.

## 4. What a person with publisher access must do

For each DOI below, open the publisher record, compare every field, fix any
difference in `refs.bib`, delete the marker and set the ledger row to
VERIFIED with route, checker, date and record, in one commit:

```
10.1109/TAC.2023.3266021        dong2024statedependent   (also read it: B-1)
10.1016/j.automatica.2012.09.017 carvalho2013permanent
(no DOI recorded)               carvalho2012intermittent (find the DOI)
10.1016/j.automatica.2021.109669 takai2021diagnosability
10.4230/OASIcs.DX.2024.28       krysander2024multimode
10.1109/TSMCA.2008.2003968      krysander2008sensorplacement
10.1243/1748006XJRR6            hurdle2007faulttree      (decide which paper first)
10.1177/1748006X18804690        reeves2019sensorselection (first author's given name)
(edition undecided)             blanke2003ftc
10.1093/biomet/41.1-2.100       Page 1954, if the manuscript cites it
```

From this environment the alternative is a network change: the cloud
environment's settings, Edit, Network access, with `api.crossref.org` and
`doi.org` added under allowed domains
(https://code.claude.com/docs/en/cloud-environments#network-access), after
which `make bib-verify` can run here.
