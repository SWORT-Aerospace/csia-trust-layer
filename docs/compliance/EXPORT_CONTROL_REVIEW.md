# Export-control review — publication candidates

**Authority:** human decision **H-4**.
**Status of this document:** a screening record, not a legal determination.

**What this document does.** It enumerates every class of material in this
repository that could plausibly be considered for public release, records what
the repository's own evidence shows about it, and assigns two things: a
`PUBLIC_RELEASE` gate set by owner decision, and an `EXPORT_STATUS` that is
either an open question or an explicit referral.

**What this document does not do.** It does not classify anything under the
EAR or the ITAR. No jurisdiction or classification is asserted here by
inference from a filename, a directory name, or the fact that the surrounding
work is academic. Where a classification is required to release, the entry
says `COUNSEL_REQUIRED` and stops.

**`EAR99` appears nowhere below as an assigned value.** Assigning it would be
a classification decision, and this screening has no authority to make one.

---

## Vocabulary

| `EXPORT_STATUS` | meaning |
|---|---|
| `NOT_REVIEWED` | no screening has been performed on this class |
| `NOT_SUBJECT` | the class contains no technical data at all (e.g. a licence notice) |
| `EAR99` | an affirmative EAR classification — **not assigned by this document** |
| `ECCN_PENDING` | an EAR classification is required before release and has not been obtained |
| `USML_PENDING` | a USML/ITAR determination is required before release and has not been obtained |
| `COUNSEL_REQUIRED` | the question is jurisdictional and must go to counsel before any release step |

| `PUBLIC_RELEASE` | meaning |
|---|---|
| `NO` | not authorized for public release by this or any current decision |
| `HOLD` | blocked pending the referral in `EXPORT_STATUS` |
| `REVIEW` | prepared for review and eligible to be considered; not yet released |

**Nothing in this repository has `PUBLIC_RELEASE = YES`.** No package has been
uploaded, no release tag cut, no licence changed.

---

## Screening table

| # | class | representative paths | `PUBLIC_RELEASE` | `EXPORT_STATUS` | basis |
|---|---|---|---|---|---|
| 1 | **Commercialization / org strategy** | `docs/COMMERCIALIZATION.md`, `docs/ORG_BLUEPRINT.md`, `docs/strategy/STAKEHOLDER_INTERVIEW_GUIDES.md`, `deliverables/HANDOFF_WHITEPAPER.md`, `HANDOFF.md` | **NO** | `NOT_REVIEWED` | H-3, H-4. Business material, out of scope for every paper release. Not screened because it is not a release candidate. |
| 2 | **Customer / programme / NDA material** | none currently tracked | **NO** | `NOT_REVIEWED` | H-3, H-4. The class is declared so the sanitizer has an assertion to make and so a future file inherits the gate by default rather than by review. |
| 3 | **SEAD runbook** | `docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md` | **HOLD** | `COUNSEL_REQUIRED` | H-4. "SEAD" denotes a defence application domain. Whether an operator runbook for public-dataset acquisition in that context attracts control is jurisdictional. The repository holds no evidence that could settle it. |
| 4 | **Interceptor tooling** | `tools/interceptor_montecarlo.py`, `tools/interceptor_plots.py`, `deliverables/montecarlo_results.{json,md}`, `deliverables/plot_trust_vs_time_*.png` | **HOLD** | `COUNSEL_REQUIRED` | H-4. Interceptor engagement Monte-Carlo tooling and its outputs. Same reasoning as #3, and it applies to the outputs as well as the code. |
| 5 | **Core proprietary harness and CSIA implementation** | `csia/**`, `research/wp_c6/q_gvalid_campaign.py`, `research/wp_c7/*.py`, `research/wp_c8/response_surface.py`, `research/wp_c8/four_quantity_metrics.py`, `research/wp_c4/self_occlusion_experiment.py`, `research/wp_c8/HARNESS_RELEASE.md` | **NO** | `NOT_REVIEWED` | H-1, H-5. Kept proprietary by decision. Not screened because it is not a release candidate; if a later decision authorizes release, screening starts then. |
| 6 | **Paper-specific sanitized results** | `publication/system_paper_i/evidence_export/**`, the 30 Phase-I result JSON files, the 19 figures, the 7 figure generators, dataset manifests, schemas and the environment lock — the exact set in `PUBLIC_RELEASE_MANIFEST.yaml` | **REVIEW** | `ECCN_PENDING` | H-1, H-4, H-5. Prepared for review. These are numeric results, derived documents and plotting code that drives an open-source autopilot's own documented simulator parameters. That is what the repository shows; it is not a classification, and release still requires one. |
| 7 | **Manuscript text and figures** | `papers/csia_systems/**`, `papers/gate_conditioning/**` | **REVIEW** | `ECCN_PENDING` | H-4. General scientific text and plots may be prepared for review. Packaging remains subject to this screening, and the manuscripts are separately blocked by the bibliography guard (H-6). |
| 8 | **Licence notice** | `LICENSE` | **REVIEW** | `NOT_SUBJECT` | contains no technical data. Travels with the sanitized package so the proprietary status is unambiguous to a recipient. |
| 9 | **Phase-II material** | `research/phase2/**` | **NO** | `NOT_REVIEWED` | H-7. Out of scope for Paper I entirely, independent of any export question. |

---

## What the repository evidence shows, for the record

These are observations, not conclusions.

- The harness drives **ArduPilot** in software-in-the-loop and injects GNSS
  faults through that simulator's own documented `SIM_*` parameters. ArduPilot
  is open source and publicly distributed.
- No cryptographic implementation, no weapons model, no guidance law, no
  classified data and no restricted algorithm appears in any tracked file.
- The datasets are public and content-addressed
  (`datasets/manifests/px4_public_v1.json`), with provenance audited in
  `docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md`.
- No customer name, contract identifier or third-party proprietary artifact
  appears in any tracked file.
- Two directory/file naming conventions — `UAV_SEAD_*` and `interceptor_*` —
  indicate a defence application domain. **Naming is the whole of the
  evidence.** It is enough to require a referral and not enough to support any
  determination in either direction.

---

## What must happen before anything is released

1. **#6 and #7 need a classification.** `ECCN_PENDING` is the honest state:
   they are prepared, screened for content, and not classified.
2. **#3 and #4 need counsel.** They are `HOLD` and stay `HOLD` until a
   determination exists. They must not be released as an incidental part of an
   academic package.
3. **#1, #2, #5, #9 are closed by decision, not by screening.** If a later
   decision reopens any of them, the screening for that class starts from
   `NOT_REVIEWED`.

---

## Enforcement

This document is a record. The mechanism is
`publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml`, which is an
allowlist: `tools/publication/build_public_release.py` packs the paths named
there and nothing else, then unpacks the built archive and scans it. Nothing
in classes #1–#5 or #9 is reachable by that tool, and the post-pack scan fails
the release if one appears anyway.

Verify with `make public-release`.
