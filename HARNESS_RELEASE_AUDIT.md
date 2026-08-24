# Harness release audit

**Subject:** the GNSS fault-injection and observation harness described in
`research/wp_c8/HARNESS_RELEASE.md`, plus the Phase-II modern rig under
`research/phase2/`.

**Scope of this document:** it records what the repository's own evidence
shows, and what the owner decided on the questions the evidence could not
settle. It is not legal advice and reaches no legal conclusion beyond what a
committed file states or a recorded decision directs.

**Nothing has been published.** No package was uploaded, no release tag cut,
no licence applied to the harness, and no archive sent outside the repository
by this work package.

**Decisions H-1 … H-7 were taken on 2026-08-24** and are applied below. The
five verdicts that were previously open are now either closed by decision or
referred with a named owner.

---

## LICENSE: **PROPRIETARY — CLOSED BY DECISION H-1**

**Decision H-1: KEEP PROPRIETARY.** The CSIA harness, the CSIA core
implementation and the proprietary research infrastructure are not published
and not open-sourced. The existing all-rights-reserved status is preserved
unchanged.

```
HARNESS PUBLIC RELEASE:  NOT_AUTHORIZED
```

That marking stands until a later explicit decision reverses it. Nothing in
this work package, and nothing in Systems Paper I, constitutes such a
reversal.

**Repository evidence.** `LICENSE` reads:

> CSIA Trust Layer — Proprietary Software. Copyright (c) 2026 SWORT LLC.
> All rights reserved. This software and its documentation are the
> proprietary property of SWORT LLC.

That licence is unchanged by this work package. It travels inside the
sanitized publication package so a recipient cannot mistake the package for
an open-source release.

**Dependency position, from `deliverables/license_audit.md`:** no GPL, AGPL or
SSPL anywhere in the dependency set. One flag: `pymavlink` is **LGPL-3.0**,
used as an optional extra (`[mavlink]`), imported as pure Python, and
therefore dynamically linked and user-replaceable. That audit records the flag
as reviewed for proprietary distribution. It does not address redistribution
under an open licence — a question decision H-1 makes moot for now.

**What replaces a harness release.** A sanitized publication package
containing evidence and artifacts only, built from an allowlist:
`publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml`. See H-5 below for
the reproducibility boundary it creates, stated honestly.

---

## SECRETS: **CLEAR**

`make secrets-scan` over every tracked file:

| class | result |
|---|---|
| AWS keys, GitHub tokens, OpenAI keys, Slack tokens, Google API keys | **0** |
| private key blocks | **0** |
| bearer authorization headers | **0** |
| secret-shaped assignments (`api_key = "..."`, etc.) | **0** |
| private IPv4 addresses | **0** |
| NDA / "confidential" / "do not distribute" markers | **0** |

No credential-shaped string exists in any tracked file. The scan prints a
redacted SHA-256 fingerprint rather than a value if one ever appears.

### Review item 1 — private operator username: **RESOLVED under H-2**

`docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md` previously hard-coded an absolute
macOS home directory containing the operator's account name, nine times, and
`tests/test_mac_pipeline.py` **asserted its presence**, which made the leak a
test invariant.

Both were changed:

- the runbook now addresses the code folder as `$HOME/swort/csia-trust-layer`;
- the `pwd` and `which python` checks now assert a path *ending* in
  `/swort/csia-trust-layer` rather than an absolute one;
- the test is now `test_runbook_exists_and_uses_portable_paths`, which asserts
  the portable form **and asserts `/Users/` does not appear at all**. The
  invariant was not removed; it was inverted, so a regression fails the suite.

The account name appears in **no tracked file**, including this one. The
source was fixed rather than the generated output redacted.

### Review item 2 — licence contact email: **accepted**

`LICENSE` carries the copyright holder's contact address, placed on purpose.
Allowlisted with that reason in `tools/publication/secrets_scan.py`.

### Container-local paths

`/home/user/...` and `/home/runner/...` appear in Phase-II artifacts and a
retained CI log as run provenance. Allowlisted individually with reasons.
**None of them is reachable by the release packager** — no Phase-II artifact
and no CI log is on the publication allowlist — and the post-pack scan fails
the release if a `/home/...` path appears in a built archive anyway.

---

## CUSTOMER / PROGRAMME / STRATEGY SCOPE: **CLOSED BY DECISION H-3**

**Decision H-3:** commercialization, org-blueprint, strategy, customer, NDA,
programme-strategy, SEAD-runbook and interceptor-tooling material is
**PRIVATE and out of scope for every paper release**. It is **not deleted**
from the private repository; it is excluded from publication artifacts.

**Mechanism, and why it is an allowlist.** Packaging never copies the
repository. `tools/publication/build_public_release.py` reads
`publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml` and packs exactly
the paths named there. A blacklist would have to be updated every time a
sensitive file is added, and would fail silently when it was not. Under an
allowlist a new file is excluded by default.

**Repository evidence, unchanged.** No customer name, no contract identifier
and no third-party proprietary artifact appears in any tracked file. Datasets
are public: `datasets/manifests/px4_public_v1.json` is content-addressed and
its provenance is audited in `docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md`.

---

## EXPORT / RESTRICTED CONTENT: **SCREENED — TWO CLASSES REFERRED**

**Decision H-4:** no defence-specific code, runbook, implementation or
configuration tooling, technical data, or customer/programme material is
authorized for public release by this work package.

The screening record is `docs/compliance/EXPORT_CONTROL_REVIEW.md`. It
classifies nine classes and assigns no EAR or ITAR classification by guessing.
`EAR99` is assigned nowhere.

```
COMMERCIALIZATION / ORG STRATEGY   PUBLIC_RELEASE = NO
CUSTOMER MATERIAL                  PUBLIC_RELEASE = NO
SEAD RUNBOOK                       PUBLIC_RELEASE = HOLD / COUNSEL_REQUIRED
INTERCEPTOR TOOLING                PUBLIC_RELEASE = HOLD / COUNSEL_REQUIRED
CORE PROPRIETARY HARNESS           PUBLIC_RELEASE = NO
PAPER-SPECIFIC SANITIZED RESULTS   PUBLIC_RELEASE = REVIEW  (ECCN_PENDING)
```

**What the repository shows, for the record.** The harness drives an
open-source autopilot in software-in-the-loop and injects GNSS faults through
that simulator's own documented parameters. No cryptographic implementation,
no weapons model, no guidance law, no classified data and no restricted
algorithm appears in the tracked tree. Two naming conventions — `UAV_SEAD_*`
and `interceptor_*` — indicate a defence application domain, and **naming is
the whole of the evidence**: enough to require a referral, not enough to
support a determination in either direction. No conclusion is drawn here.

---

## HARNESS RELEASE IN SYSTEMS PAPER I: **NO — DECISION H-5**

**FULL HARNESS RELEASE = NO.** Systems Paper I exposes the measurement and
reproducibility contract without releasing proprietary core tooling.

**What the paper's evidence package does expose:** definitions verbatim from
source, exact result tables, the underlying result JSON, source and commit
provenance, schemas, non-sensitive experiment configuration, the reproduction
and analysis commands, figure generation for 16 of 19 figures, and the trial
validity contract.

**What it does not:** the fault-injection harness, the SITL campaign drivers,
the bench scenario driver, and the CSIA core they import.

**The resulting reproducibility boundary, stated honestly.** Every number in
the paper is *traceable* — to a committed artifact, a file, a key and a
SHA-256 — and **none is independently re-executable from the released
package**. Three figures (`wp_c1_*`) ship as PNGs only, because their
generator imports the module carrying the declared structure. The full text of
the boundary is in
`publication/system_paper_i/SANITIZED_PACKAGE_README.md`, which ships inside
the package rather than being asserted only here. The paper must state this
limit rather than imply a reproduction package it does not ship.

---

## PUBLICATION DECISION: **PACKAGING READY / MANUSCRIPT BLOCKED**

```
HARNESS PUBLIC RELEASE:      NOT_AUTHORIZED           (H-1, H-5)
PUBLICATION PACKAGING:       PREPARED_FOR_REVIEW      (H-3, H-4)
EXPORT CLASSIFICATION:       ECCN_PENDING             (H-4)
MANUSCRIPT SUBMISSION:       BLOCKED                  (H-6)
```

The packaging work is complete: archives build reproducibly from an allowlist
and pass a post-pack sanitization scan. Two things still stand between this
and a submission, and neither is engineering work:

1. **Bibliography — decision H-6.** 37 unresolved provenance markers in
   `papers/csia_systems/refs.bib`. The guard stays red until independently
   verified source records are supplied. No marker is deleted and no metadata
   is fabricated to clear it.
2. **Export classification.** Classes #6 and #7 in the screening record are
   `ECCN_PENDING`. Prepared, screened for content, not classified.

---

## Decisions taken

| # | decision | applied as |
|---|---|---|
| H-1 | **KEEP PROPRIETARY.** No harness, core or research-infrastructure release. Harness public release `NOT_AUTHORIZED`. | licence unchanged; sanitized package replaces a harness release |
| H-2 | Private username must not appear in public artifacts. Fix the source, not the output. | runbook de-personalized; test inverted to forbid `/Users/`; post-pack archive scan |
| H-3 | Strategy / customer / programme material is private and out of scope. Packaging is an allowlist. | `PUBLIC_RELEASE_MANIFEST.yaml` + `build_public_release.py` |
| H-4 | No defence-specific material authorized. Classify without guessing. | `docs/compliance/EXPORT_CONTROL_REVIEW.md` |
| H-5 | Full harness release = NO; expose the measurement contract only. | evidence export + `SANITIZED_PACKAGE_README.md` boundary statement |
| H-6 | 37 references remain a submission blocker. | `bib_guard.py` stays red by design |
| H-7 | Strict phase separation preferred. | see `RESEARCH_STATE.md` for the branch outcome |

## Still open, with owners

| # | open item | owner | why it cannot be closed here |
|---|---|---|---|
| O-1 | EAR/ITAR classification for the sanitized results and the manuscripts (`ECCN_PENDING`) | counsel | jurisdictional, not technical |
| O-2 | SEAD runbook and interceptor tooling remain `HOLD / COUNSEL_REQUIRED` | counsel | naming is the whole of the evidence |
| O-3 | 37 bibliography entries need verification against publisher records | writing/research agent | no repository evidence can supply a citation |

---

## Verdict block

```
LICENSE:                    PROPRIETARY (H-1, closed)
HARNESS PUBLIC RELEASE:     NOT_AUTHORIZED
SECRETS:                    CLEAR
CUSTOMER/IP SCOPE:          CLOSED BY DECISION (H-3)
EXPORT/RESTRICTED CONTENT:  SCREENED; 2 classes COUNSEL_REQUIRED
PUBLICATION PACKAGING:      PREPARED_FOR_REVIEW
MANUSCRIPT SUBMISSION:      BLOCKED (bibliography, H-6)
```

Re-run the evidence behind the SECRETS line with `make secrets-scan`, and the
evidence behind the packaging line with `make public-release`.
