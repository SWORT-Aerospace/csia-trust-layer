# CSIA Systems Paper I — sanitized publication package

**Licence: proprietary.** See `LICENSE`. Nothing in this package is
open-sourced, and receiving it grants no licence to the CSIA implementation.
It exists so a scientific reviewer can check the paper's numbers.

Built by `tools/publication/build_public_release.py` from the allowlist in
`PUBLIC_RELEASE_MANIFEST.yaml`. Every file here was named explicitly. The
repository was never copied and pruned.

---

## What is in here

| directory | what it is |
|---|---|
| `evidence_export/` | the 16-file authoritative evidence export — definitions, results, corrections ledger, claim ledger, artifact map, reproduction commands, repository state. **Start at `evidence_export/00_README.md`.** |
| `research/wp_c*/results/`, `reports/wp_a2/` | the 30 result JSON files every reported scalar is read from |
| `figures/` | the 19 figures, as published |
| `research/wp_*/figures.py`, `research/wp_a2/e_figures.py` | the seven figure generators, which read the JSON above |
| `datasets/manifests/`, `datasets/schemas/`, `datasets/registry/` | dataset identity, result schema, environment lock |
| `datasets/reports/` | the real-log exposure artifact and its supporting reports |

---

## The reproducibility boundary, stated plainly

This is decision **H-5**: the measurement contract is exposed, the proprietary
tooling is not. Concretely:

**You can, from this package alone:**

- read every definition the paper depends on, verbatim from source, in
  `evidence_export/02_FROZEN_DEFINITIONS.md`;
- check every reported scalar against the result JSON it came from, using the
  file-and-key pointers in `evidence_export/12_ARTIFACT_MAP.yaml`, which
  carries a SHA-256 for each artifact;
- **regenerate 16 of the 19 figures** from the committed JSON, with
  `matplotlib` and `numpy` and nothing else;
- audit what was withdrawn, refuted and narrowed, in
  `evidence_export/10_CORRECTIONS_LEDGER.md`;
- see exactly which claims are eligible for the paper and at what scope, in
  `evidence_export/11_CLAIM_LEDGER.yaml`.

**You cannot, from this package alone:**

- **re-run any experiment.** The fault-injection harness, the SITL campaign
  drivers and the bench scenario driver are not here. Neither is the CSIA
  core they import.
- **regenerate the three `wp_c1_*` figures.** `research/wp_c1/figures.py`
  imports `research.wp_c1.certificate`, which carries the declared structure,
  so it is withheld. Those three ship as PNGs only.
- **re-derive a result from the implementation.** The closed-form escalation
  check in `evidence_export/05_ESCALATION_RESULT.md` reports
  `max_abs_error_vs_equation_1 = 0.0` against the shipping `TrustCore`; you
  can read the derivation and the verification output, but you cannot re-run
  the comparison without the engine.

**What this means for the paper's claims.** Every number is *traceable* — to a
committed artifact, a file, a key and a hash — and none is *independently
re-executable* from this package. The paper should say so rather than imply
a reproduction package it does not ship.
`evidence_export/14_REPRODUCTION_COMMANDS.md` lists the exact commands that
would reproduce each result **inside the private repository**, so the boundary
is a licensing boundary and not a missing-method boundary.

---

## What is deliberately absent

Not oversight, and not "not needed" — screened out by decision:

| absent | decision |
|---|---|
| CSIA core implementation (`csia/`) | H-1 KEEP PROPRIETARY |
| fault-injection harness and SITL campaign drivers | H-1 / H-5 FULL HARNESS RELEASE = NO |
| all Phase-II material (`research/phase2/`) | H-7 strict phase separation |
| commercialization, org and strategy documents | H-3 PUBLIC_RELEASE = NO |
| SEAD runbook, interceptor tooling | H-4 HOLD / COUNSEL_REQUIRED |
| `.git` history | H-2 no history travels with a public archive |

The full screening is in `docs/compliance/EXPORT_CONTROL_REVIEW.md` in the
private repository.

---

## Sanitization

The archive is unpacked and scanned after packing, not before. It contains no
operator username, no absolute home path, no credential, no private address,
no strategy document, no interceptor tooling, no `.git`, and no Phase-II
identifier outside the files whose stated job is to say what is excluded.

A failed scan deletes the archive.
