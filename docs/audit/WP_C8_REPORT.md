# WP-C8 — Response Surface, Four-Quantity Metrics, Paper Structure

**Date:** 2026-08-23 · **Branch:** `research/wp-e1` · **PR #13**
**Suite: 482 → 482, all passing.** No production changes. The escalation defect
is characterised, not fixed.
**Deliverables:** `research/wp_c8/`, restructured `papers/csia_systems/`,
`docs/audit/WP_C8_REPORT.md`, three figures, a prepared harness release.

---

## 0. Two readings of the brief, flagged before anything else

**The header says "fix the duration-limited escalation defect". Part 3 says
"Implement no fix" and the deliverables say "No production changes."** I treated
the body as authoritative and characterised it. Section 3 below derives it,
predicts the boundary and tests the prediction; nothing in `engine.py`,
`online.py` or `failsafe.py` changed. Say the word and the correction is a
short, well-evidenced change — the algebra now says exactly which constant to
move and what it buys.

**"The BibTeX arrived." It did not.** No BibTeX text appears anywhere in the
brief. This is the third failed transfer. I filled nothing, invented nothing,
and the 14 `VERIFY` placeholders stand exactly as they were. Section 6 lists
what each one still needs.

---

## 1. Verdict

**The neither-detected region exists and it is not a corner.** 8 of 21 cells by
detection, 9 of 21 by escalation. More useful than the count is the shape: it
is a **wedge that widens as the error slows**. A step is caught above 2 m, a
4 s ramp is missed up to 5.6 m, a 20 s ramp is missed up to 22.3 m. Both
detectors fail the same way on slow errors, so they overlap rather than cover
each other.

**The escalation defect now has closed-form algebra that matches the shipping
code exactly** and a boundary that classifies 19 of 21 cells. The mechanism is
not what I assumed a package ago, and the correction is the most interesting
thing in this report: **the delay is set by the belief mass banked during calm
flight, not by the evidence margin.**

**The four-quantity decomposition immediately earned its keep.** The glitch arm
has the *largest* false-healthy exposure of any arm, 24.64 of 25 s, and
`T_SOFH = 0` exactly. Under one pooled quantity this programme was attributing
its biggest measured exposure to the wrong mechanism.

---

## 2. Part 1 — the response surface

`research/wp_c8/response_surface.py`, 36 flights.

### 2.1 Coverage

| Coverage | By detection | By escalation |
|---|---|---|
| both | 12 / 21 | 3 / 21 |
| estimator only | 0 / 21 | 9 / 21 |
| layer only | 1 / 21 | 0 / 21 |
| **neither** | **8 / 21 (38%)** | **9 / 21 (43%)** |

Criteria, all from the systems themselves rather than chosen by us:
estimator detection is `pos_horiz_variance > 0.8`, ArduPilot's own
`FS_EKF_THRESH` default over its own normalised innovation test ratios; layer
detection is the physics residual saturating below 0.10; escalation is the
failsafe leaving NORMAL.

### 2.2 The uncovered wedge

| Slew | Largest error missed by BOTH |
|---|---|
| step | 0.5 m (2 m is caught by the layer) |
| 4 s ramp | 5.6 m |
| 20 s ramp | 22.3 m |

The estimator misses slow errors because it absorbs them into its state with
small innovations. The layer misses them because its step detector never
saturates. **The two blind spots move the same way with slew**, which is why
the region exists at all: complementary detectors would have opposite slopes.

**Judged by escalation the picture is worse.** The layer escalates in 3 of 21
cells. Nine cells are detected by the estimator and acted on by nobody, because
the estimator's response in these tests is an internal variance rise rather
than a mode change. A detection nobody acts on is not coverage.

### 2.3 Detection and escalation kept apart throughout

The brief was right that a naive detection-rate table would erase the crux.
It is visible in every row: at 5566 m the residual saturates at 0.0000 and
trust reaches only 0.8881, no escalation. At 556.6 m over 20 s the same
residual saturates and trust reaches 0.7148, escalation. **The difference is
duration, not magnitude, and only a two-column table shows it.**

### 2.4 Flight phase

The same 556.6 m 4 s ramp during climb, cruise and descent gives minimum trust
0.697, 0.735, 0.744; only climb escalated. Real but small, and smaller than the
slew dependence. One flight per phase, so this is an indication and not a
result.

---

## 3. Part 3 — the escalation defect, characterised

`research/wp_c8/escalation_algebra.py`

### 3.1 The algebra, and a wrong first version

**Lemma.** Belief mass `S_k = alpha_k + beta_k` obeys `S_{k+1} = rho S_k + 1`
regardless of evidence, with fixed point `1/(1-rho)`.

**Theorem.** Settled at trust `T_0` with mass `S_0`, then holding evidence at
`e_f` for `N` ticks at a new constant `rho`, with `M = 1/(1-rho)` and
`x = rho^N`:

```
T_N = [ x S_0 T_0 + (1-x) M e_f ] / [ x S_0 + (1-x) M ]
```

**My first version asserted mass invariance across the transition** and gave
the simple lag `T_N = T_0 rho^N + e_f (1 - rho^N)`. Verified against the
shipping `TrustCore` it missed by 0.198 and predicted escalation at tick 35
where the code took 94. The invariance holds only for constant `rho`. Calm
flight runs at `rho_max = 0.998` so the belief settles carrying `S_0 = 500`
units; the fault drops `rho` to 0.95 whose sustainable mass is `M = 20`. The
corrected equation is **exact: maximum absolute error 0.00 over 200 ticks.**

I would not have found this by inspection. The verification against production
code is what caught it, and that is the argument for writing the check before
believing the derivation.

### 3.2 What the algebra says

**The evidence floor.** Weights at the GPS node are 0.35 / 0.30 / 0.20 / 0.15.
Destroying only the physics residual leaves `e_f = 0.70` against a 0.75
threshold. **Measured minimum fused evidence in the saturated cells: 0.7000.**
Eight of 21 cells land on it to four decimals; the rest sit slightly below
because the neighbour term also degraded, which the same equation predicts.

**Ticks required.**

```
N* = ln( M(T*-e_f) / (S_0(T_0-T*) + M(T*-e_f)) ) / ln(rho) = 93.31 ticks = 3.73 s
```

**What dominates is the finding.** `S_0(T_0-T*) = 125` against
`M(T*-e_f) = 1.0`. The escalation delay is set by how much agreement the calm
period banked, not by how bad the fault is. **Halving the concentration cap
nearly halves the delay; doubling the threshold margin barely moves it.** If
the correction is authorised, that is the constant to move, and this is the
evidence for choosing it over the threshold.

**Why magnitude cannot substitute.** The step peak decays 0.85 per tick, so
`N_floor` grows as `ln(amplitude)`: a 1000x larger error buys at most 42 extra
ticks, every one on a residual already pinned at zero. A saturating detector
with a fixed decay cannot escalate on magnitude alone.

### 3.3 The prediction, tested

**Retro-validation, zero free parameters.** N* separates all nine runs WP-C7
flew before this derivation existed: six steps at 26 to 40 floor ticks, none
escalated; three ramps at 104 to 168, all escalated; N* = 93 lies in the gap.
**9 of 9 correct.**

**Forward test on the new grid.** Escalation additionally requires the
failsafe's 1 s dwell, so the boundary is `N* + 25 = 118.31` ticks. Over the 21
sweep cells this classifies **19 correctly**. The two misses:

| Cell | Floor ticks | From boundary | Predicted | Observed |
|---|---|---|---|---|
| `a55.7_s20` | 119 | +0.7 | escalates | did not |
| `a5566_s4` | 106 | -12.3 | does not | escalated |

Both sit inside the model's own error bar: it assumes a constant `e_f`, and the
measured floor ranges 0.678 to 0.700 because large fast ramps degrade the
neighbour term too. I am reporting the misses rather than tuning the boundary
to absorb them.

**The dedicated duration experiment was degenerate and I am saying so.** Twelve
held-glitch cells were all predicted negative and all observed negative, so it
confirms the prediction on one side only. Releasing the offset stops refreshing
the step peak, so held glitches capped at 80 floor ticks and never reached the
boundary. The positive side is exercised by the grid, where sustained ramps
reach 106 to 423 ticks. A one-sided test is weak evidence and pretending
otherwise would be the easy mistake here.

---

## 4. Part 2 — everything re-reported under four quantities

`research/wp_c8/four_quantity_metrics.py`, 15 flights.

Seconds in a 25 s window, attribution channel unless stated:

| Arm | F_h | T_NA | T_UH | T_FH | T_SOFH | T_FH status | T_FH abstaining |
|---|---|---|---|---|---|---|---|
| `nominal` | no | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **`glitch`** | yes | **0.00** | **0.00** | **24.64** | **0.00** | 24.64 | **24.64** |
| `link loss` | yes | 24.48 | 24.48 | 24.96 | **24.48** | 1.52 | 0.48 |
| `denial` | yes | 24.56 | 23.97 | 24.37 | **23.97** | 1.44 | 0.40 |
| `denial, recovered` | yes | 15.20 | 14.61 | 14.37 | 13.97 | 1.44 | 0.40 |

**The glitch row is why the decomposition was necessary.** Largest false-healthy
exposure of any arm, and `T_SOFH = 0` exactly, because `A_h = 1` for every
tick: the fix is retained, `gvalid` stays open, `phys_gps` keeps contributing.
No part of that exposure can be self-occlusion.

**And the abstaining policy does nothing for it.** `T_FH` stays at 24.64 s,
unchanged to two decimals, while it removes the denial and link-loss exposure
almost entirely (24.37 → 0.40, 24.96 → 0.48). **Two defects, two fixes.** That
is now design guidance in the paper rather than a buried observation.

**Verdict vocabulary** adopted as instructed: ISO/IEC 9646-1
PASS / FAIL / INCONCLUSIVE / INAPPLICABLE presented as HEALTHY / FAULT /
UNKNOWN / NOT_APPLICABLE, with ARINC 429 Sign/Status Matrix and OPC UA
StatusCode `Bad` cited as the field-level precedent that unusable data is not
normal data. LTL3 and conformal prediction are not claimed. No term is coined
for the exposure quantity.

**Stale-usage sweep**, done the way the gate ceiling was: every `T_FH` in the
manuscript, figures and claim table was located and either replaced with the
correct quantity or confirmed correct. The old single-quantity definition in
the section opener is gone, the claim table gained the `T_SOFH` rows and a row
recording that a single quantity was refuted by our own measurement, and the
WP-C7 figure is superseded by a four-quantity figure.

---

## 5. Part 4 — manuscript structure

Restructured toward the exemplar's shape.

1. **Contribution sentence, plain register.** "We studied which GNSS fault
   classes a deployed cross-sensor diagnostic layer detects, which it
   escalates, and how long it reports health without applicable evidence, using
   controlled injection against a real autopilot; we report the fault classes
   where it and the vehicle's own estimator are both blind, a closed-form
   account of why detection does not imply escalation, and the fault-injection
   harness we used." No framework language.
2. **Explicit fault taxonomy table** in the introduction: fix-loss denial,
   receiver link loss, retained-fix step, retained-fix ramp, each with its
   effect on applicability. The applicability column is what separates
   self-occlusion from everything else, and having it early stops the reader
   pooling them.
3. **Harness release prepared**, `research/wp_c8/HARNESS_RELEASE.md`, and
   **not published**. Section 5.1 below.
4. **Benchmark then degrade**: the nominal arm is the baseline row in every
   table, then each fault class against it.
5. **Conclusions are six numbered pieces of design guidance**, each traceable
   to a measurement: one ungated relation; a saturating detector cannot
   escalate on magnitude; size the delay from the concentration cap not the
   threshold; verify raw-reading and fused-reading monitors jointly; give the
   system a way to say it cannot assess; separate detection from escalation and
   unsupported from false.
6. **Limitations kept at length**, plus the four-quantity constraint: `T_FH`
   and `T_SOFH` both condition on `F_h`, which does not exist in unannotated
   telemetry, so only `T_NA` and `T_UH` are ever estimable from the corpus.

**Hard rules, checked mechanically:** 0 em dashes, 0 en dashes, 0 "novel", 0
theorem labels, braces 761/761, environments matched, 9 of 9 cite keys resolve,
**19 of 19 cross-references resolve**, 12 of 12 figures present. The
reference-resolution and duplicate-label checks are new this round, added
because the restructure introduced cross-references and there is no compiler
here to catch a dangling one.

The exemplar itself is **not cited**: I have author surname, year and venue but
no title, which is the same situation as Takai and Kang, and the same decision
follows.

### 5.1 The harness release, prepared and not published

`research/wp_c8/HARNESS_RELEASE.md` sets out what would ship, what it records,
which fault classes it injects, and **two decisions that are yours**:

- **Licence.** Recommendation is permissive on our source with the ArduPilot
  SITL binary fetched at runtime and never redistributed, since the binary is
  GPLv3 and `pymavlink` is LGPLv3. **Not applied.**
- **Scope.** Three options from scripts-as-is to a decoupled harness others can
  plug their own diagnostic into. **Not chosen.**

Also flagged: the files have **not** been audited for credentials, hostnames or
internal identifiers, and that must happen before any release.

---

## 6. Part 5 — the bibliography, unchanged

No BibTeX arrived. Fourteen `VERIFY` placeholders remain, in nine positions:

| Entry | What is still missing |
|---|---|
| Dong, Yin, Li (TAC 69(1) 145-160, 2024) | title |
| Krysander, Hashemniya (DX 2024) | title |
| Reeves, Remenyte-Prescott, Andrews (IMechE O 233(4)) | title |
| Takai (Automatica 129, 109669, 2021) | title |
| Kang, Hou, Liu (Sensors 24(14) 4445, 2024) | title, author initials |
| Hurdle, Bartlett, Andrews (IMechE O 221(1)) | title is reconstructed from prose |
| Yin, Gao, Li (φ-diagnosability) | venue, year, title. Least supported entry |
| Blanke et al. | edition, year, publisher location |
| Adams et al. 2025 (the exemplar) | title; not cited at all |

Nothing was upgraded. Nothing was invented. **The manuscript has still never
been compiled** — no `pdflatex`, `xelatex`, `latexmk` or `tectonic` in this
environment. Standing blocker since WP-C5.

The receiver-observables claim added in WP-C7 remains **uncited**, per the
conflict I flagged then and resolved the same way now.

---

## 7. Which outcome would have weakened the paper

### The response surface

| Outcome | Effect |
|---|---|
| **Empty neither-region** | The dual-blindness finding becomes a curiosity, not a result. Two detectors that jointly cover everything is a good engineering story and a much smaller paper, and the brief was right to make this reportable in advance. |
| **Neither-region only below the noise floor** | Nearly as bad. Not detecting a 2 m GNSS error is correct behaviour, so a region confined there says nothing. This nearly happened: three of the eight uncovered cells are at 0.5 m and are not evidence of anything. What rescues the finding is the *wedge*, which reaches 22.3 m at 20 s slew. |
| **Blind spots with opposite slopes** | Would have been the reassuring outcome and a genuinely useful one: two detectors whose weaknesses are complementary in the strong sense. Ours are complementary in the weak sense only, and both degrade with slew. |
| **Layer escalating across the grid** | Would have made the escalation defect a corner case rather than the dominant behaviour. It escalates in 3 of 21. |

### The escalation algebra

| Outcome | Effect |
|---|---|
| **Closed form not matching the shipping code** | Would have left the defect a description rather than a characterisation. It did not match on the first attempt, and that is how the mass-transition effect was found. |
| **Boundary failing to separate the WP-C7 runs** | Would have refuted the account outright on data collected before it existed. 9 of 9. |
| **N\* dominated by the evidence margin** | Would have pointed the fix at the threshold, which is the tempting place to look and would have been wrong. It is dominated by the concentration cap by two orders of magnitude. |
| **A magnitude that escalates** | Would have downgraded the defect to a sensitivity threshold. None exists up to 5.6 km. |

### The four quantities

| Outcome | Effect |
|---|---|
| **T_SOFH near T_FH in every arm** | The decomposition would have been bookkeeping, and the single quantity would have been fine. Instead the glitch arm separates them completely. |
| **T_SOFH large for the glitch** | Would have meant our applicability model is wrong, since `A_h = 1` there by construction. It came back at exactly 0. |
| **Abstaining fixing the glitch too** | Would have been convenient and would have hidden that there are two defects. It changed nothing there, to two decimals. |

---

## 8. What the campaigns have taken away

Continuing the list. WP-C7 removed eight claims; this package removes or
corrects five more, four of them mine.

1. **"The escalation delay follows a simple first-order lag."** Wrong. Mass is
   not invariant across a change in the forgetting factor, and the simple lag
   misses by 0.198 and 59 ticks.
2. **"A single false-healthy exposure quantity measures the failure."**
   Refuted by our own data: it attributed the largest exposure, the glitch
   arm's 24.64 s, to self-occlusion, which contributed exactly zero of it.
3. **"The abstaining state is the fix."** Narrowed. It is the fix for
   applicability loss and does nothing for the glitch.
4. **"Escalation is duration-limited"** (WP-C7, mine). Correct but incomplete:
   the duration required is itself set by the concentration cap, which is the
   actionable part and which WP-C7 did not identify.
5. **"The dedicated duration experiment tests the boundary."** It does not; it
   is one-sided. The grid tests it.

---

## 9. What I got wrong, and how I found out

1. **The mass-invariance theorem.** Asserted, wrong, caught by verifying
   against the shipping `TrustCore` rather than by reading the code again.
   Predicted tick 35, code took 94. The corrected form is exact.
2. **The verification harness itself was wrong first.** My initial check passed
   no neighbour edge, so `c_nbr` was `None`, the weights renormalised over three
   components and `e_f` moved from 0.70 to 0.538. The closed form missed by
   0.17 for a reason that had nothing to do with the algebra. Caught by
   printing the observed evidence and comparing it to the predicted value,
   which is why that field is in the artifact.
3. **My crossing detector scanned the sampled trace, not every tick**, and
   reported 100 instead of 94. Two ticks of thought, six ticks of error, and it
   would have made a confirmed prediction look approximate.
4. **The response-surface verdict was decided by the wrong runs**, again: the
   escalation-boundary print crashed on a renamed key after I split the
   duration experiment out. Caught immediately, but it is the second time in
   two packages that a summary block referenced a stale key.
5. **I designed a degenerate experiment.** The held-glitch duration sweep can
   never cross the boundary, because releasing the offset stops refreshing the
   peak. I should have seen that from equation (3) before flying 12 cells.

---

## 10. What I could not determine

- **Whether the uncovered wedge extends further at slower slews.** The grid
  stops at 20 s. A 60 s ramp would plausibly hide more than 22.3 m and nothing
  here measures it.
- **Why `a5566_s4` escalated 12 ticks inside the boundary.** The likely cause
  is neighbour-term degradation lowering `e_f`, but I did not isolate it.
- **Whether any of this reproduces on a current ArduPilot or PX4.**
- **What a real receiver does**, in any of it.
- **Whether the manuscript compiles.**

---

## 11. Open, with owners

| Item | Owner | Blocking |
|---|---|---|
| **Authorise the escalation fix** | You | characterised and ready; the algebra names the constant |
| **Supply the BibTeX** | You / research agent | third failed transfer; 14 `VERIFY` remain |
| **Compile the manuscript** | You | standing blocker since WP-C5 |
| **Harness licence and scope** | You | release prepared, not published |
| **Audit harness files for secrets** | Me, on your go-ahead | must precede any release |
| Extend the slew axis past 20 s | WP-E2 | nothing |
| Re-run everything on current ArduPilot and PX4 | WP-E2 | needs GitHub access |
| Plumb `satellites_used`, `noise_per_ms`, DOP | Engineering | nothing |
| `failsafe.py:106` fail-open on `att` | Engineering | unanalysed since WP1 |

---

## 12. Reproducing

```sh
curl -sSLO https://dronekit-assets.s3.amazonaws.com/sitl/copter/sitl-linux-copter-3.3.tar.gz
mkdir -p sitl && tar xf sitl-linux-copter-3.3.tar.gz -C sitl
pip install -e '.[mavlink]'
export CSIA_SITL_BINARY=$PWD/sitl/apm CSIA_SITL_EEPROM=$PWD/sitl/default_eeprom.bin
PYTHONPATH=. python research/wp_c8/escalation_algebra.py     # no SITL needed
PYTHONPATH=. python research/wp_c8/response_surface.py       # 36 flights
PYTHONPATH=. python research/wp_c8/four_quantity_metrics.py  # 15 flights
PYTHONPATH=. python research/wp_c8/figures.py
python papers/csia_systems/check.py
```

`response_surface.py` accepts `--reanalyse` to rebuild its report from flights
already on disk. Without the binary every script emits `SITL_UNAVAILABLE` and
substitutes nothing.
