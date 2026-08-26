# Dual-channel admissibility — confirmatory stage

**NOTHING HAS BEEN RUN. NO CONFIRMATORY TRACE HAS BEEN CAPTURED.**
This package is a frozen preregistration awaiting independent review (item 32).

Base exploratory commit: `b21b539`.

Read [`CHATGPT_PREREGISTRATION_REVIEW_REPORT.md`](CHATGPT_PREREGISTRATION_REVIEW_REPORT.md)
first. Its §20–21 are the ones that matter: a literature search was run, and it
subsumes the architectural claim.

## The headline before you read anything else

**ARINC 429's Sign/Status Matrix has distinguished Failure Warning from No
Computed Data since the 1970s.** That is exactly `SENSOR_INVALID` versus
`TRANSPORT_UNAVAILABLE`. Together with SEVA self-validating sensors and NAMUR
NE 107, this makes the architectural separation `KNOWN/SUBSUMED`. The formal
results are `KNOWN/SUBSUMED` too — they restate Fisher–Neyman sufficiency and
the standard observation-mask formulation of diagnosability.

What survives is narrow and is engineering, not theory: a measured instance of
a consumer discarding a distinction its own input protocol supplies.

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
| `tool_self_audit.py` | `results/TOOL_SELF_AUDIT.json` | **No** — instrument regression guard |
| `trace_manifest.py` | `results/DEVELOPMENT_TRACE_MANIFEST.json` | n/a |

`results/CONFIRMATORY_TRACE_PLAN.json` (30 planned trials, none captured) and
`results/COUNTEREXAMPLE_GENERATOR_FREEZE.json` (hashes) are hand-authored.

```
make dual-confirmatory-prep    # everything above; runs no confirmatory trial
```

## Contamination

`results/DEVELOPMENT_TRACE_MANIFEST.json` lists 16 recordings and 4 analysis
outputs the exploratory phase touched. Every synthetic exploratory fixture was
programmed over the **carrier** of the development recording, so a new schedule
over that carrier would still be contaminated — which is why every confirmatory
trial must be a fresh SITL boot captured end to end.
