# Dual-channel admissibility — confirmatory stage

**STAGE 2.1 COMPLETE. The 10+10 confirmatory campaign was NOT run and is now
recommended against.** Three held-out matched pairs were captured and scored
instead, which settled the question.

Base exploratory commit: `b21b539`. Preregistration: `cea85f1` (unmodified).

**Verdict: `IMPLEMENTATION_DEFECTS_ONLY`** — see
[`STAGE2_1_DECISION_REPORT.md`](STAGE2_1_DECISION_REPORT.md).

Read [`CHATGPT_PREREGISTRATION_REVIEW_REPORT.md`](CHATGPT_PREREGISTRATION_REVIEW_REPORT.md)
first. Its §20–21 are the ones that matter: a literature search was run, and it
subsumes the architectural claim.

## The headline before you read anything else

**SEVA self-validating sensors and NAMUR NE 107 already separate a
measurement's value from a status that stays informative when the value is
unusable.** That makes the principle `KNOWN/SUBSUMED`. The formal results are
`KNOWN/SUBSUMED` too — they restate Fisher–Neyman sufficiency and the standard
observation-mask formulation of diagnosability.

*(Stage 2 claimed ARINC 429's FW/NCD pair was the same distinction. **That was
wrong** — both are transmitted source statuses and absence has no SSM encoding
at all. Corrected in [`PRIOR_ART_CORRECTION.md`](PRIOR_ART_CORRECTION.md).)*

What survives is narrow and is engineering, not theory: three measured,
independently fixable defects, and a checker that found them.

## What was frozen, and what was falsified during freezing

The **strong form of H1** — "C0 aliases the two mechanisms" — was tested during
design and is **FALSE**. Under matched `A`, the coupled arm still differs
between mechanisms in `trust_gps` on 857/857 ticks, because a propagated
invalid sample feeds the *ungated* temporal features while a missing message
feeds nothing. H1 is frozen in its weak form, and a `C0_STRONG` arm exists
specifically to try to exploit that leak and kill the claim.

## Documents

| | |
|---|---|
| `CHATGPT_PREREGISTRATION_REVIEW_REPORT.md` | **start here** — 27 sections, recommendation |
| `DUAL_ADMISSIBILITY_PREREGISTRATION.md` | the frozen document |
| `FORMAL_AUDIT.md` | T1–T5 restated with assumptions and their counterexamples |
| `OPERATIONAL_DIAGNOSTIC_PARTITION_MODEL.md` | the partition/sufficiency condition, and what it does not license |
| `PRIMARY_ENDPOINT_SPEC.md` | mechanism discrimination; the retired posterior endpoint |
| `MECHANISM_MATCHING_SPEC.md` | how `A` is matched, and the proof it can be |
| `STATUS_ONLY_ABLATION_SPEC.md` | the arm with no new detector |
| `CROSS_PATH_EQUIVALENCE_SPEC.md` | separate, non-statistical result |
| `PRIOR_ART_MATRIX.md` | what the search killed |
| `BATTERY_SOURCE_AUDIT.md` | the only other candidate family, source only |
| `PHYSICAL_HIL_VALIDATION_PLAN.md` | three levels; criterion 0 gates everything |

## Scripts and their outputs

| Script | Produces | Scored? |
|---|---|---|
| `design_feasibility.py` | `results/DESIGN_FEASIBILITY.json` | **No** — development traces, design input only |
| `heldout_capture.py` | `results/heldout_raw/*.json.gz` | six held-out SITL traces, three matched pairs |
| `live_vs_inherited.py` | `results/LIVE_VS_INHERITED_INFORMATION.{json,csv}` | development sweep over six onsets |
| `kill_test.py` | `results/STAGE2_1_KILL_TEST.json`, the two `*_HELDOUT_3PAIR.csv`, `HISTORY_REMOVAL_CONTROL.json` | **yes** — the decisive test |
| `cross_path_checker.py` | `results/COUNTEREXAMPLE_CROSS_PATH_RESULTS.json` | separate defect result |
| `tool_self_audit.py` | `results/TOOL_SELF_AUDIT.json` | **No** — instrument regression guard |
| `trace_manifest.py` | `results/DEVELOPMENT_TRACE_MANIFEST.json` | n/a |

`results/CONFIRMATORY_TRACE_PLAN.json` (30 planned trials, none captured) and
`results/COUNTEREXAMPLE_GENERATOR_FREEZE.json` (hashes) are hand-authored.

```
make dual-confirmatory-prep    # source audits and instrument self-check
make dual-heldout-capture      # six fresh SITL boots (~10 min)
make dual-kill-test            # score the frozen arms against them
```

## Contamination

`results/DEVELOPMENT_TRACE_MANIFEST.json` lists 16 recordings and 4 analysis
outputs the exploratory phase touched. Every synthetic exploratory fixture was
programmed over the **carrier** of the development recording, so a new schedule
over that carrier would still be contaminated — which is why every confirmatory
trial must be a fresh SITL boot captured end to end.
