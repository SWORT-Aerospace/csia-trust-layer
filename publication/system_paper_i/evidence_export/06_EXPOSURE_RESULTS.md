# 06 — Four-quantity exposure results

Definitions are frozen in `02`. Do not read these numbers without it.

**Artifact:** `research/wp_c8/results/four_quantity_metrics.json`
**SHA256:** `2f6bee8950ec34ef151f7a8fba2c87f719e7dbae33b05faf25c30ab2d5fe5e39`
**Script:** `research/wp_c8/four_quantity_metrics.py` · **Commit:** `3597f18c953e52111978f09af17c9432c6b794c9`
**Target hypothesis:** `gps_fault`
**Window:** 60.0 s to 85.0 s, i.e.
25 s at 25.0 Hz
**Denominator:** `window_ticks` inside that window, armed and past arm time

---

## 1. Headline table, attribution channel

The attribution channel is the one the paper's claim is about: it scores what
the **diagnosis** says, with the failsafe excluded.

| arm | F_h (ground truth) | flights | T_NA (s) | T_UH (s) | T_FH (s) | T_SOFH (s) |
|---|---|---|---|---|---|---|
| `denial` | True | 3 | 24.56 | 23.973 | 24.373 | 23.973 |
| `denial_recovered` | True | 3 | 15.2 | 14.613 | 14.373 | 13.973 |
| `glitch` | True | 3 | 0.0 | 0.0 | 24.64 | 0.0 |
| `link_loss` | True | 3 | 24.48 | 24.48 | 24.96 | 24.48 |
| `nominal` | False | 3 | 0.0 | 0.0 | 0.0 | 0.0 |

## 2. All three channels

| arm | channel | T_UH (s) | T_FH (s) | T_SOFH (s) |
|---|---|---|---|---|
| `denial` | attribution | 23.973 | 24.373 | 23.973 |
| `denial` | status | 1.04 | 1.44 | 1.04 |
| `denial` | abstaining | 0.0 | 0.4 | 0.0 |
| `denial_recovered` | attribution | 14.613 | 14.373 | 13.973 |
| `denial_recovered` | status | 1.04 | 1.44 | 1.04 |
| `denial_recovered` | abstaining | 0.0 | 0.4 | 0.0 |
| `glitch` | attribution | 0.0 | 24.64 | 0.0 |
| `glitch` | status | 0.0 | 24.64 | 0.0 |
| `glitch` | abstaining | 0.0 | 24.64 | 0.0 |
| `link_loss` | attribution | 24.48 | 24.96 | 24.48 |
| `link_loss` | status | 1.04 | 1.52 | 1.04 |
| `link_loss` | abstaining | 0.0 | 0.48 | 0.0 |
| `nominal` | attribution | 0.0 | 0.0 | 0.0 |
| `nominal` | status | 0.0 | 0.0 | 0.0 |
| `nominal` | abstaining | 0.0 | 0.0 | 0.0 |

---

## 3. The case that refuted the single quantity

Verbatim from the artifact:

> it measured an unsupported healthy verdict, not a false one. Without ground truth a healthy verdict with no applicable evidence may be correct by accident.

**The glitch row.** `T_NA_s` = 0.0,
`T_SOFH_s` = 0.0 on the attribution channel,
while `T_FH_s` = **24.64**.

> A_gps_fault = 1 for every tick of the glitch arm: the fix is retained, gvalid stays open and phys_gps keeps contributing. The hypothesis is applicable throughout, so no part of the glitch arm's exposure can be self-occlusion. Its exposure is T_FH only, and its cause is detector sensitivity and the escalation interface, which WP-C8 Part 3 characterises separately.

**Verification of the claim carried in conversation.** "The glitch arm had the
largest false-healthy-style exposure while `T_SOFH = 0`":

| arm | attribution `T_FH_s` | attribution `T_SOFH_s` |
|---|---|---|
| `denial` | 24.373 | 23.973 |
| `denial_recovered` | 14.373 | 13.973 |
| `glitch` | 24.64 | 0.0 |
| `link_loss` | 24.96 | 24.48 |
| `nominal` | 0.0 | 0.0 |

Ranked by attribution `T_FH_s`, the glitch arm is **rank 2 of 5** overall at 24.64 s. The single larger arm is `link_loss` at 24.96 s, which carries `T_SOFH_s` = 24.48 s and is therefore self-occlusion, not the contrast case.

Restricted to arms with **`T_SOFH_s` = 0**, the glitch arm is the largest at 24.64 s (the only other such arm is `nominal` at 0.0 s).

**Verdict on the conversational claim: SUPPORTED AS STATED, with the ranking made explicit.** The glitch arm carries the largest false-healthy exposure of any arm whose exposure is not self-occlusion (24.64 s), while `T_SOFH_s` = 0.0. It is not the largest `T_FH_s` overall. Both facts are in the table above and the paper should state the restricted version, because the restriction is the point: substantial false-healthy time with zero self-occlusion is what forces the four-way split.

---

## 4. Corpus limit

> F_h does not exist in unannotated telemetry, so T_FH and T_SOFH are permanently unavailable from the 26-log corpus. T_NA and T_UH are estimable from it. This is a limit of the data, not of the method.

## 5. Verdict vocabulary

| item | value |
|---|---|
| standard | ISO/IEC 9646-1 conformance verdicts |
| mapping | `{"FAULT": "FAIL", "HEALTHY": "PASS", "NOT_APPLICABLE": "INAPPLICABLE", "UNKNOWN": "INCONCLUSIVE"}` |
| field-level precedent | ARINC 429 Sign/Status Matrix distinguishes Failure Warning and No Computed Data from Normal Operation; OPC UA StatusCode Bad severity means the value must not be used. Both establish that unusable data is not normal data. |
| explicitly **not** precedent | LTL3 and conformal prediction were checked and are different conditions; neither is claimed here. |
| no standard term for the exposure quantity | True |
