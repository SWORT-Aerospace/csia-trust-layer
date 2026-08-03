# Shared-Power Baseline Report

**Protocol:** `SHARED_POWER_BASELINE_PROTOCOL.md` (pre-registered, frozen
before implementation) · **Frozen CSIA commit:** `92d6140`
**Campaign hash:** `10f4fe6b7245a657321c4021e9802fe407f8c421159a62716d34a4278f1ce922`
**Evidence environment:** SIMULATION only · **Authorization:** SHADOW_ONLY
**Result artifact:** `campaigns/results/shared_power_baseline_v1.json`

---

## VERDICT: Outcome B — CSIA is statistically equivalent to a simple rule on this fault family

**The hand-written shared-resource rule (System D) matches or slightly exceeds
CSIA on shared-power root-cause identification.** The pre-registered
comparative-value criterion is **NOT met**. This is reported as measured; no
model change followed.

| Blind synthetic (n=31, 26 positive) | Root cause | 95% CI | Exact set | F1 | Bad shared | Blame |
|---|---|---|---|---|---|---|
| A — legacy single-source | 0.000 | — | 0.000 | 0.538 | 0.000 | 0.000 |
| B — majority vote | 0.000 | — | 0.000 | 0.710 | 0.000 | 0.000 |
| C — per-source threshold | 0.000 | — | 0.000 | 0.688 | 0.000 | 0.032 |
| **D — shared-resource rule** | **0.923** | [0.759, 0.979] | **0.923** | 0.807 | 0.000 | 0.000 |
| **E — CSIA** | 0.885 | [0.710, 0.960] | 0.885 | 0.807 | 0.000 | 0.000 |

**The 3.85 pp gap is one scenario out of 26 and the confidence intervals
overlap almost entirely.** The honest statement is *no detectable difference*,
not "D wins".

---

## Results by stratum

| Stratum | n | A root | B root | C root | **D root** | **E root** |
|---|---|---|---|---|---|---|
| ALL (positives) | 110 | 0.000 | 0.000 | 0.000 | **0.882** | 0.860 |
| VALIDATION | 24 | 0.000 | 0.000 | 0.000 | **1.000** | **1.000** |
| BLIND_SYNTHETIC | 31 | 0.000 | 0.000 | 0.000 | **0.923** | 0.885 |
| ADVERSARIAL | 9 | 0.000 | 0.000 | 0.000 | **0.667** | 0.500 |
| OBSERVABLE_POSITIVE | 82 | 0.000 | 0.000 | 0.000 | **1.000** | 0.976 |
| DETECTABILITY_FLOOR | 11 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

Systems A, B and C score **0.000 on root cause everywhere — structurally**,
not through error: none can emit a shared resource. Recorded as `UNSUPPORTED`,
distinct from `INCORRECT`.

**Detectability floor (n=11, all `rpm_loss=100`):** every system scores zero.
The motor-side severity peaks at 0.001–0.056, so the second source is absent
from the measurements. No architecture can recover a signal that is not there.

## Where CSIA does lead

| Metric (ALL, n=110) | D — rule | **E — CSIA** |
|---|---|---|
| Exact affected set, all scenarios | 0.773 | **0.809** |
| Source-level F1 | 0.773 | **0.809** |
| Abstention rate | 0.255 | **0.055** |
| Adversarial F1 | 0.556 | **0.667** |
| Validation F1 | 0.917 | **0.958** |

D abstains on **25.5%** of scenarios — it is silent on every fault family that
is not shared power. CSIA answers those (single-source, independent, healthy)
and is right more often overall. **That coverage advantage is +3.6 pp, well
short of the pre-registered +10 pp threshold.**

## Safety metrics — no system blames wrongly except C

| Stratum | C blame | D blame | E blame |
|---|---|---|---|
| Healthy (n=3) | **1.000** | 0.000 | 0.000 |
| Independent (n=8) | **0.250** | 0.000 | 0.000 |
| Single-source (n=6) | 0.000 | 0.000 | 0.000 |

Naive per-source thresholding blames a healthy source in **every** clean
scenario. D and CSIA never do. Zero incorrect shared-cause claims and zero
clean-flight activations for **all** systems.

## Timing and cost (blind, host-Python)

| | D — rule | E — CSIA |
|---|---|---|
| Root-cause latency P50 / P90 / P95 / max | 1.08 / 2.20 / 3.48 / 3.52 s | 1.08 / 2.96 / 3.52 / 6.56 s |
| Censored (never classified) | **2** | **0** |
| Median tick cost | **9.7 µs** | 258.6 µs |

**CSIA costs ~27× more per tick** and is marginally slower at the tail, but
never fails to reach a classification where D leaves 2 scenarios censored.

## Acceptance criteria

| Criterion (blind) | Target | Result | |
|---|---|---|---|
| Root cause, all positives | ≥ 0.75 | 0.885 | ✅ |
| Root cause, observability-qualified | ≥ 0.85 | 0.976 (ALL-observable) | ✅ |
| Incorrect common cause on negatives | ≤ 0.05 | 0.000 | ✅ |
| Clean-flight common-cause | 0 | 0 | ✅ |
| Exact affected set, unconditional | ≥ 0.75 | 0.885 | ✅ |
| Exact set when both observable | ≥ 0.85 | 0.976 | ✅ |
| Source F1 ≥ every baseline | — | 0.807 = D 0.807 | ✅ (tie) |
| **Comparative value vs strongest baseline** | +10 pp root **or** +10 pp set **or** −25% blame **or** better ambiguity w/o more error | −3.85 pp root; +3.6 pp set; blame 0 vs 0 | ❌ **FAILED** |

CSIA meets every absolute criterion and **fails the comparative one**.

## Failure taxonomy

**CSIA blind failures (3 of 26):**

| Cause | n | Description |
|---|---|---|
| DETECTABILITY | 3 | `rpm_loss=100` family; motor severity 0.001–0.056. Not a diagnostic error — the evidence is absent. |

**CSIA adversarial failures (3 of 6):** extreme-ratio and 4–6 s-stagger cases.
The stagger cases are arguably *correct* refusals: a 6 s gap is weak evidence
for a shared rail. D classifies them as shared, which inflates its adversarial
score by accepting cases CSIA deliberately declines.

**D failures (2 blind, censored):** same detectability-floor family, plus D
never abstains-then-recovers, so it silently reports nothing.

Neither system produced a single incorrect shared-cause claim anywhere.

## Ablation attribution (from slice 3C, not re-run here)

- **Topology:** load-bearing (disabling changes results) — but note D achieves
  comparable accuracy using topology as a flat membership list, so CSIA's
  *contradiction* handling bought no measurable accuracy on this family.
- **Temporal:** load-bearing on dispersed onsets only.
- **Severity normalization:** load-bearing — it is what removed the ratio
  sensitivity, and Systems C and D were given it too, which is precisely why
  they perform as well as they do.

**Read honestly: the single most valuable mechanism from slice 3C —
per-source severity normalization — is exactly what makes the simple rule
competitive, because we gave it to the baselines.** The hypothesis
architecture on top of it adds coverage, not accuracy, on this fault family.

## Claims now supportable

- CSIA identifies a shared-power root cause and the exact affected source set
  in 88.5% of blind synthetic positives (97.6% when both sources are
  observable), with zero incorrect shared-cause claims and zero clean-flight
  activations — **in simulation**.
- CSIA answers across more fault families than a shared-power rule (abstention
  0.055 vs 0.255) with a higher overall F1 (0.809 vs 0.773).
- Per-source severity normalization removes the amplitude-ratio sensitivity
  identified in slice 3C.

## Claims still prohibited

- **Any claim that CSIA outperforms a simple shared-resource rule on
  shared-power diagnosis.** It does not, on this evidence.
- Any real-flight common-cause claim (zero real-log validation).
- Any calibrated-probability language.
- Any embedded/native claim for this layer (Python-only, 258 µs/tick host).
- Any claim of value for the general hypothesis architecture based on this
  family alone.
