# Dual-channel admissibility — confirmatory preregistration

**Status: FROZEN ON COMMIT. NOT RUN.**
Base exploratory commit: `b21b539`. Nothing in this document may be changed
after the first confirmatory trial is scored; a change voids the campaign and
requires a new preregistration.

---

## 0. What this campaign is NOT for

Two things are settled before it starts, and neither is at stake:

**The architecture is not novel.** `PRIOR_ART_MATRIX.md` establishes that
separating operational validity from diagnostic status is standard: ARINC 429's
Sign/Status Matrix has distinguished **Failure Warning** from **No Computed
Data** — precisely `SENSOR_INVALID` versus `TRANSPORT_UNAVAILABLE` — since the
1970s; SEVA sensors emit value, uncertainty and status separately; NAMUR NE 107
defines four status signals with an explicit operator-versus-technician split.
**Status: `KNOWN/SUBSUMED`.** No result of this campaign can change that, and
no wording implying otherwise may be used.

**The formal results are not novel.** T1–T5 and the partition/necessity
condition are downgraded to `KNOWN/SUBSUMED` by `FORMAL_AUDIT.md` and
`OPERATIONAL_DIAGNOSTIC_PARTITION_MODEL.md`: they restate the Fisher–Neyman
factorisation criterion and the standard observation-mask formulation of
diagnosability.

What remains is an **engineering question about one implementation**: does this
consumer discard a distinction its own input protocol supplies, and does
separating `D` from `A` recover it? That is worth measuring. It is not a
contribution to theory.

## 1. The frozen claim

> Two fault mechanisms can produce the same operational inadmissibility state
> `A = 0` while requiring different diagnostic interpretations. Under coupled
> semantics `D = A`, the distinction may be lost at the decision point.

**Candidate principle, not to be called novel:** *operational inadmissibility
is not equivalent to diagnostic noninformativeness.*

## 2. Primary confirmatory question

When two fault mechanisms produce **matched** operational inadmissibility, does
separating `A` from `D` preserve mechanism-discriminating information that
coupling loses?

## 3. Hypotheses, frozen

**H1 (primary, WEAK FORM).** Under matched `A = 0`, `C1` and `C2` classify the
mechanism correctly on materially more scored ticks than `C0`.

> H1 is stated in its weak form deliberately. The **strong form** — "C0 aliases
> the two mechanisms" — was tested during design and is **FALSE** for this
> implementation. `results/DESIGN_FEASIBILITY.json`: under matched `A`, the
> coupled arm still differs between mechanisms in `trust_gps` on 857/857 ticks
> and in `post_gps_fault` on 181/857, because a propagated invalid sample feeds
> the *ungated* temporal features while a missing message feeds nothing. The
> aliasing is at the level of the **leading decision** (0/857 differ), not at
> every level of state. Freezing the strong form would have frozen a known
> falsehood.

**H2 (information retention).** `I(M; E_C1) > I(M; E_C0)` and
`I(M; E_C2) > I(M; E_C0)` over the scored population.

**H3 (the killing hypothesis).** `C0_STRONG` — the coupled arm given a
development-fitted threshold on its continuous residue — **cannot** reach C2's
discrimination.

> **If H3 is false, the architectural claim collapses**: the coupled
> architecture retained enough to do the job and the split was unnecessary.
> That outcome is a legitimate result of this campaign and will be reported as
> the headline if it occurs.

## 4. Arms

| Arm | Operational invalidity | Diagnostic evidence | `D` gating |
|---|---|---|---|
| `C0` | propagated, `A = 0` | categorical observation state | `D = A` |
| `C1` | propagated, `A = 0` | categorical state **+ `h_acc`** | independent |
| `C2` | propagated, `A = 0` | categorical state **only** | independent |
| `C0_STRONG` | propagated, `A = 0` | `D = A`, plus a threshold on `trust_gps` residue | `D = A` |

`C2` is **required**, not optional (item 8). `C0_STRONG` is required.

`C1` and `C2` differ from `C0` in exactly one boolean, asserted by test.
Implementation maps to the frozen exploratory arms: `C0 = S1`, `C1 = S2c2`,
`C2 = S2a`, with hashes in `results/COUNTEREXAMPLE_GENERATOR_FREEZE.json`.

**No arm may make an operationally invalid navigation VALUE admissible.**
`gnss.position` and `gnss.velocity` are gated off by the frozen core under
every arm; the wrapper cannot readmit them, and a test asserts the only
features any arm may add are the two status ones.

## 5. Mechanisms and matching

Per `MECHANISM_MATCHING_SPEC.md`. `C_SENSOR`: messages continue, all
`fix_type < 3`. `C_TRANSPORT`: no messages delivered, receiver healthy.

**Scored interval:** `[onset + 0.5 + 0.2, end − 0.5 − 0.2]` s.

**Admissibility gate, zero tolerance:** a pair is scored only if
`A_trace_sha256` is **equal** between its two mechanisms over the scored
interval and `A == 0` throughout. If more than 2 of 10 pairs fail, the campaign
**stops** and the design is reconsidered — the tolerance is not loosened.

## 6. Data

30 trials — 10 `SENSOR_INVALID`, 10 `TRANSPORT_UNAVAILABLE` (paired), 10
`CLEAN` — per `results/CONFIRMATORY_TRACE_PLAN.json`. Every trial is a **fresh
ArduPilot SITL boot**, captured end to end.

**Disjointness.** No confirmatory trial may reuse, or be built over the carrier
of, anything in `results/DEVELOPMENT_TRACE_MANIFEST.json` (16 recordings, 4
analysis outputs, hashed). Checked by SHA-256 before scoring. Fresh boots are
required precisely because the exploratory synthetic fixtures were programmed
over the *carrier* of the development recording, so a new schedule over the old
carrier would still be contaminated.

**These are deterministic scenarios, not iid samples.** The frozen nuisance
schedule (onsets, durations) is in the trace plan. No interval and no p-value
will be computed.

## 7. Endpoints

Per `PRIMARY_ENDPOINT_SPEC.md`.

**Primary:** mechanism classification correctness under matched `A`, reported
as the confusion matrix over `{SENSOR_INVALID, TRANSPORT_UNAVAILABLE,
UNRESOLVED}`. The classifier is a frozen decision rule over runtime-observable
state, not a likelihood term — which keeps detector magnitude out of the
primary result entirely.

**Second primary:** exact `I(M; E)` at three points in each arm's pipeline. The
data-processing inequality is textbook and is not claimed.

**Clean criterion:** **zero** mechanism classifications across all 10 clean
trials, every arm. An arm that fires is disqualified regardless of its score.

**Secondary, reported not headline:** `gps_fault` posterior and leading-cause
share (the retired exploratory endpoint); `objective_O`; failsafe level and
time to `nav_degraded`; T5's predicted 0.29 s reversal time, measured directly
for the first time.

## 8. Success and failure conditions

**A strong confirmatory result requires all of:**

1. matched `A` on ≥ 8 of 10 pairs, zero mismatched ticks within each;
2. `C0` correct on ≤ 5% of scored ticks, `UNRESOLVED` on ≥ 95%;
3. `C2` correct on ≥ 90% of scored ticks, both mechanisms;
4. `C0_STRONG` correct on ≤ 60% — the split was needed;
5. zero clean false classifications, every arm;
6. no operationally invalid value re-enabled, asserted by test;
7. no fault-label leakage, asserted by test.

**The campaign fails, and reports failure, if:**

* `C2` cannot discriminate under matched `A` — the architectural claim fails at
  its strongest point. **No further evidence term may be added to rescue it**,
  and falling back to `C1` cannot be promoted to the primary result;
* `C0_STRONG` matches `C2` — the split was unnecessary;
* any arm fires on clean data;
* fewer than 8 pairs achieve matched `A`.

## 9. Prohibited actions after the first scored trial

* changing any threshold, constant, evidence term, hypothesis map, classifier
  rule, scored-interval rule or matching tolerance;
* adding an arm or an evidence term;
* modifying the counterexample generator (frozen by hash);
* selecting trials post hoc for any reason other than the preregistered
  matched-`A` gate;
* re-running a trial and keeping the better result.

## 10. Analysis order, fixed in advance

1. Verify the tool self-audit passes (`results/TOOL_SELF_AUDIT.json`).
2. Verify disjointness against the development manifest.
3. Verify matched `A` per pair; record exclusions.
4. Compute the primary confusion matrices.
5. Compute `I(M; E)`.
6. Compute the clean criterion.
7. Only then look at secondary endpoints.

Steps 1–3 gate step 4. Secondary endpoints are computed last so they cannot
influence the reading of the primary.

## 11. Separate, non-statistical result

`CROSS_PATH_EQUIVALENCE_SPEC.md` — whether the choice of ingest path alone
changes `A`, `D`, freshness or mechanism state. Reported standalone with its
own verdict. **It is not combined statistically with the main experiment**, and
it stands whether or not the main experiment succeeds.

## 12. What a clean pass would and would not license

**Would:** stating that this implementation loses mechanism information at the
diagnostic decision point under coupled admissibility, and that a categorical
status channel recovers it — as a defect report and its repair, in one system.

**Would not:** any novelty claim (settled: `KNOWN/SUBSUMED`); any claim of
operational benefit (the exploratory work found the failsafe recommendation
identical across every arm and nothing here tests otherwise); any
generalisation past GNSS (`BATTERY_SOURCE_AUDIT.md` shows battery would test a
different defect); any hardware claim (`PHYSICAL_HIL_VALIDATION_PLAN.md`
LEVEL 1 criterion 0 is not yet established).

## 13. Known weaknesses, stated in advance

* **The primary endpoint is close to analytically determined for `C0`, and
  more so than the first draft of this document admitted.** Under matched `A`,
  T1 says the coupled arm has nothing to read. The *leak* that would have made
  the campaign non-trivial turns out to be mostly an onset artefact:
  `trust_gps` **freezes** when `A` closes (`engine.py:146`), so within the
  scored interval it is a constant inherited from the excluded transient, and
  the fields that do move discriminate at chance (0.5047, 0.5053). The one
  live question is whether a **single cross-pair** threshold on raw trust
  generalises; on one development pair a threshold scores 1.0000, and across
  ten varied onsets it should not. If `C0_STRONG` is weak, the campaign will
  have confirmed a theorem against an implementation — worth doing, but not a
  discovery.
* **`C2`'s classifier maps almost directly from its inputs.** The informative
  half of the primary comparison is `C0`'s failure, not `C2`'s success.
* **Consequently the campaign's genuinely empirical content is small**: the
  clean control on fresh data, and whether `C0_STRONG` generalises across
  onsets. Both are worth knowing; neither needs 30 captures to answer, and the
  review report recommends resequencing on exactly that ground.
* **`SENSOR_DEGRADED_BUT_VALID` is deferred** (item 18). It cannot be
  represented without an `h_acc` magnitude term, which the status-only ablation
  forbids; including it would reintroduce the detector into the primary
  endpoint. Listed as future work rather than quietly dropped.
* **30 deterministic scenarios are not a sample.** Nothing here supports
  inference to a population of flights.
* **`ulog_source.py` is audited from source only** — no ULog file exists in
  this checkout, so the cross-path result covers two of three paths in
  execution.
