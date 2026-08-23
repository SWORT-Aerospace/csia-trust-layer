# Harness release audit

**Subject:** the GNSS fault-injection and observation harness described in
`research/wp_c8/HARNESS_RELEASE.md`, plus the Phase-II modern rig under
`research/phase2/`.

**Scope of this document:** it records what the repository's own evidence
shows. It is not legal advice and reaches no legal conclusion beyond what a
committed file states. Two of the five verdicts below are deliberately
`HUMAN_DECISION_REQUIRED` because the repository contains no evidence that
could settle them.

**Nothing has been published.** No package was uploaded, no release tag cut,
no licence applied to the harness.

---

## LICENSE: **BLOCKED**

**Repository evidence.** `LICENSE` reads:

> CSIA Trust Layer — Proprietary Software. Copyright (c) 2026 SWORT LLC.
> All rights reserved. This software and its documentation are the
> proprietary property of SWORT LLC.

The harness lives inside this repository and is therefore covered by that
licence today. Publishing it as a citable research tool requires a different
licence for at least the harness subtree, and no such licence exists in the
repository.

**Dependency position, from `deliverables/license_audit.md`:** no GPL, AGPL or
SSPL anywhere in the dependency set. One flag: `pymavlink` is **LGPL-3.0**,
used as an optional extra (`[mavlink]`), imported as pure Python, and
therefore dynamically linked and user-replaceable. That audit records the
flag as reviewed for proprietary distribution; it does **not** address
redistribution of a research tool under an open licence, which is a different
question.

**What blocks it:** a licence decision for the harness subtree. That is an
owner decision, not a repository fact.

---

## SECRETS: **CLEAR**

`make secrets-scan` over all 434 tracked files:

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

**Two review items remain, neither a credential:**

1. `docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md` contains
   `/Users/ZINTRAX-5/swort/csia-trust-layer` nine times, and
   `tests/test_mac_pipeline.py:512` **asserts that the runbook contains it**.
   This is deliberate: the test enforces that the acquisition runbook keeps
   the operator's real paths. It exposes a machine or account name in a
   repository that may become public. It has **not** been changed, because
   changing it would alter a deliberate test invariant, and that is an owner
   decision. → carried to HUMAN DECISIONS below.
2. `LICENSE` carries the copyright holder's contact email, placed on purpose.
   Allowlisted with that reason.

Container-local paths (`/home/user/...`, `/home/runner/...`) appear in
Phase-II artifacts and a retained CI log as run provenance. Allowlisted
individually with reasons in `tools/publication/secrets_scan.py`.

---

## CUSTOMER / IP SCOPE: **HUMAN_DECISION_REQUIRED**

**What the repository shows.** No customer name, no contract identifier and no
third-party proprietary artifact appears in any tracked file. Datasets are
public: `datasets/manifests/px4_public_v1.json` is content-addressed and its
provenance is audited in `docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md`.

**Why this is not CLEAR.** The repository contains material whose commercial
and programme context it cannot itself adjudicate:

- `docs/COMMERCIALIZATION.md`, `docs/ORG_BLUEPRINT.md`,
  `docs/strategy/`, `deliverables/HANDOFF_WHITEPAPER.md`
- `docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md`, and the `interceptor_*` tooling
  under `tools/`, whose naming indicates a defence-adjacent application

Whether any of that is customer-scoped, programme-scoped or unrestricted is
not derivable from the files. An owner must say.

---

## EXPORT / RESTRICTED CONTENT: **REQUIRES HUMAN REVIEW**

**What the repository shows.** The harness itself drives an open-source
autopilot (ArduPilot) in software-in-the-loop and injects GNSS faults via that
simulator's own documented parameters. No cryptographic implementation, no
weapons model, no classified data and no restricted algorithm appears in the
tracked tree.

**Why review is required anyway.** The repository contains
`docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md` and interceptor Monte-Carlo tooling.
"SEAD" and "interceptor" denote a defence application domain. Whether GNSS
spoofing-detection tooling in that context attracts export control is a
jurisdictional question this repository holds no evidence about, and it is
not one to answer by inference from filenames.

**No conclusion is drawn here in either direction.**

---

## PUBLICATION DECISION: **NOT_READY**

Blocked on two items that are decisions rather than work:

1. **LICENSE** — no licence exists under which the harness could be released.
2. **CUSTOMER/IP SCOPE and EXPORT** — unresolved, and not resolvable from
   repository evidence.

Everything technical is in place: the harness is documented
(`research/wp_c8/HARNESS_RELEASE.md`), reproducible, and free of credentials.

---

## Human decisions still required

| # | decision | why it cannot be made here |
|---|---|---|
| H-1 | Licence for the harness subtree, if it is to be released | `LICENSE` is proprietary and all-rights-reserved; only the owner can relicense |
| H-2 | Whether `/Users/ZINTRAX-5/...` may appear in a public repository, and if not, how to change it given `tests/test_mac_pipeline.py` asserts its presence | changing it alters a deliberate test invariant |
| H-3 | Customer / programme scope of `docs/COMMERCIALIZATION.md`, `docs/ORG_BLUEPRINT.md`, `docs/strategy/`, the SEAD runbook and the interceptor tooling | no repository evidence establishes it |
| H-4 | Export-control position for the defence-adjacent material | jurisdictional, not technical |
| H-5 | Whether the harness release is in scope for Systems Paper I at all, or is a separate deliverable | `research/wp_c8/HARNESS_RELEASE.md` records it as prepared and awaiting approval |

---

## Verdict block

```
LICENSE:                    BLOCKED
SECRETS:                    CLEAR
CUSTOMER/IP SCOPE:          HUMAN_DECISION_REQUIRED
EXPORT/RESTRICTED CONTENT:  REQUIRES HUMAN REVIEW
PUBLICATION DECISION:       NOT_READY
```

Re-run the evidence behind the SECRETS line with `make secrets-scan`.
