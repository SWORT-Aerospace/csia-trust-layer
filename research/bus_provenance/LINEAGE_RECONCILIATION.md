# Lineage reconciliation, 2026-09-15

Reported findings checked against the repository before any of them was relied
on. Each row says where the claim actually lives and whether it is current.
Nothing was taken on the say-so of the brief that prompted the check.

## Confirmed as stated

| claim | where it actually lives | verdict |
|---|---|---|
| FL-016 — gate closure did **not** cause trust to rise; the control arm rose more | `research/physical_validation/FAILURE_LEDGER.yaml` | **CONFIRMED.** Fault delta median +0.007007 over [+0.006996, +0.007145]; control +0.020594 over [+0.020572, +0.020804]; n=20 each, ranges disjoint. ~3×, not the "~3x" being a rounding of something weaker. The fault *suppresses* an ongoing rise |
| FL-017 — original vs repeat watchdog differed, 0.5 s vs 1.0 s | same ledger | **CONFIRMED,** and the finding is sharper than "they differed": *neither preregistration named the watchdog as a pinned environment field.* The frozen core is byte-identical across the two commits; `csia/deploy/shadow.py` changed |
| FL-019 — ArduPilot pre-fault trust discrepancy unresolved | same ledger | **CONFIRMED and still open.** PX4 moved −0.033, ArduPilot +0.000177; the replay that settles PX4 cannot settle this. No cause invented |
| `zero_volume` / `empty_intersection` / `separation_margin` distinct | `csia_independent_validation/discrimination.py:31-35` | **CONFIRMED** as three named outcomes, with a touching-set counterexample in `tests/test_iv_discrimination.py` |
| pre-gate redundant within the tested envelope | `results/GATE_TABLE_FINAL.json` | **CONFIRMED.** `pre=False/post=True` has **n = 0**, so accept-if-both is identical to accept-if-post |
| safety sub-gate vacuous | same artifact | **CONFIRMED,** and labelled in the artifact itself: "the safety sub-gate cannot fail for any admissible action" (IV-19) |

## Corrected — the brief's figure is superseded

| claim as reported | what the repository says |
|---|---|
| "2,404 accepted inferences were correct against simulator truth" | **2,404 is the VALIDATION-partition figure and is superseded.** On the sealed final partition the number is **3,925 accepted, 0 false, coverage 0.18171** over 21,600 main rows (`GATE_TABLE_FINAL.json`, `table_point_metric.policies.accept_if_post`). 2,404 remains true of validation and is still correctly cited as such in `CLAIM_LEDGER.md` H4 and C-2gate. Quoting it as the current headline would understate a completed result by 63% |

The companion claim — "many correct inferences were conservatively refused" —
is **confirmed and quantifiable** on the sealed partition: of 21,600 rows,
17,675 were refused by the post gate, and **12,899 of the refused rows were in
fact resolved** (5,871 in `pre=False/post=False` plus 7,028 in
`pre=True/post=False`). Accepting everything would have resolved more and been
wrong 4,776 times; the gate trades that for zero.

## Ambiguous in the repository, and now flagged

**"F1/F2/F3" does not identify a unique series.** Four live namespaces use it:

| namespace | F1/F2/F3 mean |
|---|---|
| `research/evidence_semantics/README.md` §"The three findings" | GNSS `NO_3D_FIX` ≡ "nothing arrived"; battery `−1` sentinel served as `5.00 A`; all-zero magnetometer ingested as a field |
| `docs/FMEA.md` | false-alarm cascade; missed fast fault; missed slow drift |
| `research/ai_contract_synthesis/CHATGPT_REVIEW_REPORT.md` | three contradictory beliefs about `valid`/sentinel/zero |
| `research/active_evidence/independent_validation/CLAIM_LEDGER.md` §B3 | the paired-design follow-up rows F1–F10, added 2026-09-14 |

The **evidence-semantics** three are the ones meant by "the three findings",
and they are the ones `csia_bus_provenance` builds on. The collision is
recorded rather than resolved by renaming: three of the four namespaces predate
this work and renaming another package's rows to suit this one would be the
kind of retroactive tidying the repository forbids elsewhere. A reader citing
"F2" must say which document.

## Not re-verified here

These were reported and are **not** relied on by anything in
`csia_bus_provenance`, so they were not re-derived. They are listed so the gap
is visible rather than implied:

the errors-in-variables attenuation and its λ expression; the corrected
slope/scatter analysis; the palindrome-vs-realized-current asymmetry under
closed-loop lag; the replaced polarization bound; the withdrawn "conservative
under lag" claim; the reconstructed pilot artifact's label; the
empty-by-construction false-certificate statistic; the "90% frontier"
correction; the bit-identical plant-margin identity; P7a/P7b/P7c and the
ceiling invariants.

## Provenance guard

`tests/test_post_e1_hardening_round2.py::test_the_build_provenance_describes_this_checkout`
requires `BUILD_PROVENANCE.json` to name a commit within a 3-commit window of
HEAD, which conflicts with a many-small-commits protocol. It was **not
disabled or widened.** It is satisfied the way it is meant to be: the record is
regenerated in every commit that would otherwise age it out.
