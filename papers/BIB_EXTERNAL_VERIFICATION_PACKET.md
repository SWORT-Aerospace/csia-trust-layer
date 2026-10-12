<!-- publication-guard: research-note -->
# BIBLIOGRAPHY — EXTERNAL VERIFICATION PACKET

Peer-review hardening campaign, §25. **A work order for one person with
library access.** Everything below can be done in one sitting; none of it can
be done from the authoring environment.

Prepared 2026-09-04 against `papers/BIB_VERIFICATION_LEDGER.yaml` (19 rows,
across two bibliographies).

---

## 0. Why a human is needed, stated precisely

Six routes were measured, not assumed. All six are refused at the proxy's
CONNECT:

| host | verdict | would have been |
|---|---|---|
| `api.crossref.org` | 403 | an accepted route |
| `doi.org` | 403 | an accepted route |
| `dblp.org` | 403 | a rejected route (secondary index) |
| `api.openalex.org` | 403 | rejected |
| `api.semanticscholar.org` | 403 | rejected |
| `export.arxiv.org` | 403 | rejected |

Publisher *pages* fetch no better: `impan.pl`, `projecteuclid.org`,
`ieeexplore.ieee.org` and `arxiv.org` all return `EGRESS_BLOCKED`.

Web **search** does work, and it is what produced everything in §2 and §3
below. It is not a publisher record, `rejected_routes` in the ledger says so,
and **no marker was retired on it.** The status
`CORROBORATED_NO_PUBLISHER_RECORD` exists precisely so that "several indices
agree on every field" is visibly better than "unknown" and visibly worse than
"verified".

## 1. The procedure, three steps

For each entry below:

1. Open the publisher's own record for the DOI (or the version of record).
2. Compare **every** field: authors, title, venue, volume, number, pages,
   year, DOI.
3. If and only if all match: delete the marker from `refs.bib` **and** set the
   ledger row to `VERIFIED` with `route`, `checked_by`, `checked_on` and
   `record` filled in. **Both edits in the same commit** —
   `tests/test_bib_verification_ledger.py` fails if only the first is made.

If a field differs, fix the field and leave the marker. A corrected entry that
still has not been seen at the publisher is still unverified.

## 2. Group A — corroborated, confirm and retire (9 rows)

Every field below was independently reproduced by two or more search indices
with nothing in dispute. These should be quick.

| key | paper(s) | what to check | DOI |
|---|---|---|---|
| `heitjan1991car` | math | **the highest-priority row in the packet.** Prop. C2's KNOWN label and the paper's central concession hang on it. Annals of Statistics 19(4), 2244–2253, 1991 | none supplied — look it up by title |
| `speekenbrink2025statedep` | math | Psychometrika 90(2), 476–507, 2025. Note the Cambridge University Press DOI prefix, not the older Springer one | `10.1017/psy.2024.3` |
| `rukhin1997bounded` | math | Applicationes Mathematicae 24(4), 415–423, 1997 | `10.4064/am-24-4-415-423` |
| `dong2024statedependent` | both | **read §3 item B-1 before touching this one** | `10.1109/TAC.2023.3266021` |
| `takai2021diagnosability` | both | Automatica 129, article 109669, 2021 | `10.1016/j.automatica.2021.109669` |
| `reeves2019sensorselection` | systems | **the given name is disputed** — see §3 item B-2 | `10.1177/1748006X18804690` |
| `krysander2024multimode` | systems | OASIcs vol. 125, pp. 28:1–28:14, DX 2024, Schloss Dagstuhl | `10.4230/OASIcs.DX.2024.28` |

(`dong2024statedependent` and `takai2021diagnosability` each appear in both
bibliographies and therefore hold two ledger rows apiece; confirming one
confirms both, but **both rows must be updated**.)

## 3. Group B — findings that need a decision, not just a lookup

These are the reason this packet exists. Each was found by corroborating a
DOI and discovering that the entry around it does not match.

### B-1 `dong2024statedependent` — the title was wrong, and the *reason for citing it* may be too

The brief supplied the title *"Verification of diagnosability for
discrete-event systems under state-dependent observations"*. Search-index
consensus places DOI `10.1109/TAC.2023.3266021` — IEEE TAC 69(1), p.145,
January 2024, same three authors, first author's given name **Weijie** not
Wei — on a different title:

> *A Uniform Framework for Diagnosis of Discrete-Event Systems with Unreliable
> Sensors using Linear Temporal Logic* (arXiv preprint 2204.13057)

The bibliography now carries the corroborated title. **The open question is
why the paper cites it.** This repository has been attributing to it *"the
general mechanism of fault-state-dependent observation loss: a state-dependent
observation map $O: Q \times \Sigma \to 2^{\Delta \cup \{\epsilon\}}$"*. The
corroborated subject is unreliable sensors whose behaviour is described by an
LTL formula. Those may be the same thing; they are not obviously the same
thing, and it cannot be settled without reading the paper.

**What is at stake, and what is not.** The claim it supports is SC-11 — *the
general mechanism of fault-state-dependent observation loss is prior art and
CSIA asserts no priority over it.* That is a **disclaimer**, it costs the
paper nothing, and the Carvalho rows carry it independently. So the science is
unaffected. What is affected is whether the disclaimer points at the right
work, and a misdirected concession is a referee-visible error.

**Decision required:** read it, then either keep the citation with a corrected
description, or move the description to a work that does own the
state-dependent observation map.

### B-2 `reeves2019sensorselection` — the title is now right and the given name is now doubtful

Title corroborated as *"Sensor selection for fault diagnostics using
performance metric"*, Proc. IMechE Part O 233(4), 537–552, 2019. The same
sources give the first author as **J. Reeves**, one naming *Jessica Reeves*.
The brief supplied *Adam*.

The bib entry carries `VERIFY: given name disputed` rather than a silent
replacement, because corroboration is enough to raise a doubt about a personal
name and **not** enough to settle one. **Decision required:** confirm the given
name at the publisher.

### B-3 `kang2024gnss` — the entry is filed under the wrong subject

DOI `10.3390/s24144445` corroborates as *"Sensor Network Attack Synthesis
against Fault Diagnosis of Discrete Event Systems"*, Sensors 24(14):4445,
2024 — a discrete-event **security** paper. The entry sits under a heading
reading `GNSS integrity monitoring`, and its key is literally `kang2024gnss`.
One of the two is wrong.

The ledger row stays `UNVERIFIED`, because nothing was corroborated about the
entry **as written** — the author fields are still placeholders — only about
the DOI it points at.

**Nothing in either paper depends on it: the entry is UNCITED by `main.tex`.**
**Recommendation:** drop it, or replace it with a genuine GNSS-integrity
reference if that section wants one. Do not cite it under the current heading.

### B-4 `yin_phidiagnosability` — probably the same work as `dong2024statedependent`

The entry reads *Yin, Gao and Li, "Uniform φ-diagnosability of discrete-event
systems under state-dependent observation"*, with **no venue and no year** —
the ledger calls it "the least supported entry in the file", and it was
reconstructed from brief prose.

φ-diagnosability is the notion **introduced by** the Dong–Yin–Li paper of B-1:
its abstract proposes *"a new notion of φ-diagnosability as the necessary and
sufficient condition for the existence of a diagnoser when sensor behaviours
satisfy the LTL formula φ"*. A targeted search for a separate Yin–Gao–Li paper
returned nothing.

**This is suggestive and it is not proof, so the entry has NOT been deleted.**
A citation removed on a guess is worse than a citation that is merely weak.
**Decision required:** determine whether a distinct Yin–Gao–Li work exists. If
it does not, merge this entry into `dong2024statedependent`.

## 4. Group C — plain lookups, nothing anomalous found (5 rows)

| key | paper(s) | DOI |
|---|---|---|
| `carvalho2012intermittent` | both | **none supplied.** Automatica 48(9), 2068–2078, 2012 — look up by title |
| `carvalho2013permanent` | both | `10.1016/j.automatica.2012.09.017` |
| `krysander2008sensorplacement` | both | `10.1109/TSMCA.2008.2003968` |
| `hurdle2007faulttree` | systems | `10.1243/1748006XJRR6` — the title was reconstructed from brief prose and should be treated as VERIFY |
| `blanke2003ftc` | systems | **none.** And there are three editions, not one: 1st 2003, 2nd 2006, 3rd 2015 (`10.1007/978-3-662-47943-8`). Decide which edition the related-work claim is drawn from — pagination and DOI differ |

## 5. What may NOT be done, whatever the deadline

* **Do not delete a marker to make `make bib-guard` pass.** The guard fails
  while a marker exists and cannot fail when one is deleted; that asymmetry is
  the whole reason the ledger exists, and
  `tests/test_bib_verification_ledger.py` closes it.
* **Do not record a search result as `VERIFIED`.** `WEB_SEARCH` and
  `SECONDARY_INDEX` are in `rejected_routes` by name so that using one is a
  visible act rather than an oversight.
* **Do not silently repair a personal name** on corroboration alone (B-2).
* **Do not delete a weak citation to tidy the file** (B-4). Removing a
  citation is a claim that no prior art exists there, and that claim needs
  more evidence than keeping it does.

## 6. Current state, for the record

| status | count |
|---|---|
| `VERIFIED` | **0** |
| `CORROBORATED_NO_PUBLISHER_RECORD` | 9 |
| `UNVERIFIED` | 10 |

`make bib-guard` is RED and must stay red until a human works through this
packet. That is the correct state, not a regression: it is a publication
blocker doing its job.
