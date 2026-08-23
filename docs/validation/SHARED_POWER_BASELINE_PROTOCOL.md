# Shared-Power Baseline Protocol — PRE-REGISTERED

**Status:** frozen before implementation and before any result was viewed.
**Frozen CSIA commit:** `92d6140`
**Campaign:** `shared_power_generalization_v1`, aggregate hash
`10f4fe6b7245a657321c4021e9802fe407f8c421159a62716d34a4278f1ce922`, 110
scenarios (DEVELOPMENT 46 / VALIDATION 24 / BLIND_SYNTHETIC 31 / ADVERSARIAL 9).
**Evidence environment:** SIMULATION only. No real-flight claim follows.

This slice is **evaluation-only**. The common-cause model, thresholds, dwell,
normalization, topology, partitions and scenario generator are not modified.

---

## 1. Benchmark question

Does CSIA's topology-aware common-cause hypothesis layer identify the shared
physical cause **and the affected source set** more accurately than the
existing single-source diagnosis and simpler alternatives?

The decisive comparison is against **System D** (a hand-written shared-resource
rule), not System A. Beating a structurally incapable classifier proves
nothing.

## 2. Compared systems (pre-registered)

All systems consume **identical** comparator feature streams from the same
`generate_flight()` truth and the same `sample_streams`. No system sees
another's output.

### System A — Legacy CSIA single-source diagnosis
The existing 1-of-K `CausalDiagnosis` softmax, unmodified. Emits one dominant
cause, or ambiguity, or nothing. **Structurally cannot** emit a multi-source
set or a shared resource — recorded as `UNSUPPORTED`, reported separately from
`INCORRECT`.

### System B — Simple majority voting
- **A vote** = one comparator feature whose gate is open, cast against the
  source(s) it indicates, using `SOURCE_INDICATORS`.
- **Vote threshold**: a source is voted faulty when > 50% of its own valid
  indicators read `c < 0.70`.
- **Minimum voters**: 1 valid indicator; with none the source abstains.
- **Unavailable evidence**: gated-out features are not counted in numerator or
  denominator.
- **Ties**: 50% exactly → not faulty (conservative, avoids blame).
- **Capability**: emits an affected-source set. **Cannot** name a shared
  resource. Can abstain.

### System C — Independent per-source thresholding
- **Threshold**: the *same* per-source severity used by CSIA
  (`normalize_severity`, `SOURCE_DEGRADED = 0.45`), applied source-by-source
  with no cross-source reasoning. This deliberately gives C the benefit of
  CSIA's normalization so that affected-set credit is not attributed to
  common-cause reasoning when independent thresholding already suffices.
- **Dwell**: 25 ticks (1.0 s) above threshold, identical to CSIA.
- **Recovery**: source clears when severity < 0.27 (0.6 × threshold),
  identical to CSIA's hysteresis.
- **Abstention**: emits an empty set when no source dwells.
- **Capability**: affected-source set only; no shared cause.

### System D — Rule-based shared-resource detector (**the key baseline**)
> If ≥ 2 sources connected to `MAIN_POWER_PACK` are simultaneously degraded
> within a temporal window, classify `MAIN_POWER_PACK` as the shared cause.

- **Source threshold**: `normalize_severity ≥ 0.45` (same as C and CSIA).
- **Required source count**: 2.
- **Temporal window**: onsets within 9.0 s (same outer bound as CSIA's
  temporal decay, so D is not handicapped on timing).
- **Dwell**: 25 ticks with the rule satisfied.
- **Contradiction handling**: none — this is the point of the baseline. It
  does not check whether a strongly coupled member stayed healthy, nor whether
  degradation appeared outside the resource.
- **Partial effects**: not handled; the rule is a hard count.
- **Capability**: full — affected set **and** shared resource.

### System E — CSIA (frozen Slice 3C)
`HypothesisEngine` + `CausalSharedCauseModel` at commit `92d6140`, default
configuration. Arm 10.0 s, dwell 25 ticks, `ACTIVE_CONF` 0.60,
`SOURCE_DEGRADED` 0.45, temporal 2.5→9.0 s, topology `RESOURCE_TOPOLOGY`.

## 3. Observability definition (frozen, CSIA-independent)

A scenario is **observability-qualified** when every ground-truth affected
source reaches per-source severity ≥ `SOURCE_DEGRADED` (0.45) on at least 25
ticks, computed **directly from comparator features** via `normalize_severity`
— no hypothesis output, no CSIA scoring, no thresholds specific to any system.
It applies identically to all five systems.

Rationale: the `rpm_loss = 100` family produces motor-side severities of
0.001–0.056, i.e. the second source is not present in the measurements at all.
**Unconditional results are reported first, always.** Observability
conditioning answers a different question and never replaces the headline.

## 4. Scoring views (frozen)

**Shared output view** — fault detected / predicted affected set / shared vs
independent / abstain. All systems mapped to this.

**Native capability view** — each system's full output, with `UNSUPPORTED`
recorded distinctly from `INCORRECT` for System A.

**Best-effort interpretation**, applied identically:
- Predicting `{battery, motor_esc}` without naming a resource = **correct
  affected set**, **unsupported** root cause.
- Predicting one of two true sources = **PARTIAL_ISOLATION**.
- Abstaining = **no diagnosis** (not counted as incorrect blame).

## 5. Metrics

Root cause: correct / incorrect / shared-as-independent /
independent-as-shared / single-source-as-shared / healthy-as-shared /
abstention / ambiguous.
Affected set: exact match, partial, over, under, incorrect; source-level
precision, recall, F1; Jaccard.
Timing: to detection, to root cause, to exact set, P50/P90/P95/max, censored
count. Both configured-onset and source-observable-onset bases.
Safety: incorrect source blame, incorrect shared blame, healthy activation,
unsafe-recommendation count (would have targeted the wrong source/cause had it
been applied — the layer stays shadow-only).
Compute: median/P95/P99/max per tick, host-Python labelled as such.

All categorical rates report numerator, denominator, point estimate and a
**Wilson 95% interval**. No bare percentages.

## 6. Acceptance criteria (evaluation criteria, not permission to tune)

Blind synthetic partition:
- ≥ 75% correct shared-power root cause on all positive scenarios
- ≥ 85% on observability-qualified positives
- ≤ 5% incorrect common cause on negatives
- 0 common-cause classifications on clean scenarios
- ≥ 75% exact affected-set match unconditionally; ≥ 85% when both sources
  observable; source-level F1 ≥ every baseline

**Comparative value** — CSIA must exceed the strongest non-CSIA baseline by at
least one of: +10 pp correct root cause, +10 pp exact affected set, −25%
incorrect source blame, or better ambiguity handling without more incorrect
diagnoses.

## 7. Integrity rules in force

Implementation frozen before execution; campaign hash recorded; baselines
fully specified above before any result was viewed; identical inputs; no
per-partition baseline tuning; **no CSIA modification after viewing results**;
no post-hoc scenario exclusion; strata reported separately; every failure
preserved; simulation-only.
