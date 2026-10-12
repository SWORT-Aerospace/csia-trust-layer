# WP-E1 — Empirical Gate Study, executed as Option C-plus

**Date:** 2026-08-22 · **Branch:** `research/wp_e1` · **Not merged to main**
**Standing constraint honoured:** no production file modified. No trust
engine, diagnosis algorithm, gate predicate, signature matrix, hypothesis
bank, failsafe, threshold or prior was edited. Nothing found here was "fixed";
it was recorded and the study continued. Suite: **448 passed** before and
after.

**Artifacts:** `structural_consequence_map.json`, `armed_divergence.json`,
`kappa_mechanisms.png`; code in `research/wp_e1/`.

---

## 1. What WP-E1 delivers, and what it does not

WP-E1 was specified to measure whether **endogenous gate closure** — a gate
closing as a function of the fault being diagnosed — has measurable structural
consequences. The Part 0 audit established that the measurement as specified
is not executable in this repository (§2). Option C-plus was selected: publish
the audit as the study's result, and compute the structural consequence map
**deterministically**, from the signature matrix and the source-verified gate
map, with no flight data.

| | Status |
|---|---|
| Structural consequence of gate closure (κ, absorption, merges, interaction) | **Computed, complete, exact** |
| Disjointness of gate effects | **Resolved** (§4) |
| `armed_gate` batch-vs-runtime discrepancy | **Quantified** (§5) |
| Empirical gate closure *in flight* | **NOT MEASURED** — deferred to WP-E2 |
| Whether gates actually close during real faults | **UNKNOWN** |

> **The distinction this report exists to protect.** What is computed here is
> what gate closure *would* do to identifiability. It is a structural bound,
> not an observation. Nothing in WP-E1 shows that gates close as a function of
> the fault being diagnosed — that is the endogeneity question, and it remains
> open.

---

## 2. Part 0 audit — why Phase A was not run

Published as WP-E1's first result rather than as a blocker note.

**2.1 The 26 raw `.ulg` logs do not exist here.** `data/real_logs/` is absent
and gitignored. The only committed artifact is
`data/real_logs_report.json`, which carries per-log id, duration, channel
list, min trust, transition list, bad-sample count and excluded channels —
**no timestamps and no tick-level telemetry**. Phase A required per-tick gate
traces. It is structurally impossible from committed artifacts.

**2.2 The "62-test automated fault harness" does not exist as described.**
Nine scenarios, eight fault-scenario tests. The string "62" appears in the
test tree only as a UUID fragment (`tests/test_datasets.py:50`). Fully traced
in `docs/audit/CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md`.

**2.3 The gate inventory is 14, not "roughly 8".** Six channel-disabling
(`armed_gate`, `gvalid`, `speed_gate`, `gps_warmup`, `temp_bias_scale`,
`quasi_static`) plus eight freshness gates. **The freshness gates do not gate
diagnostic features** — they block *belief updates* in the trust recursion
(`engine.py:146`) and drive the failsafe's independent freshness branch
(`failsafe.py:144-145`), while `bayes.py:131-133` sets every `temp_*` gate to
`np.ones` unconditionally. Of the six channel-disabling gates, only **four
actuate on a feature some hypothesis references**.

**2.4 Two of the six are structurally inert.**
- `temp_bias_scale` is a constant `0.2 * ones` (`comparator.py:182-183`). It
  never opens and never closes, and the feature it controls
  (`temp_bias_drift`) appears in **no hypothesis LOW set**, so it cannot
  affect the partition even in principle. WP-A2 E1 independently measured its
  operational effect as **exactly 0.0** across all five scenarios, with a
  steady-state trust offset of 1.8e-4 on `baro` and 6e-5 on `battery`.
- `quasi_static` modulates an attitude *estimate*, not a diagnostic feature.

**2.5 `armed_gate` diverges between execution paths.** Recorded as a WP1
discrepancy and quantified in §5.

---

## 3. The structural consequence map

Computed over all 2⁴ configurations of the four actuating gates, under the
**runtime armed-flag semantics** (`online.py:491-496`), from
`research/formalization/diagnostic_signature_matrix.yaml`. H = 8 hypotheses;
κ = (H − P)/(H − 1).

### 3.1 Per-gate severity

| Gate | κ alone | Absorbed into `nominal` | Merged classes |
|---|---|---|---|
| `gvalid` | 0.143 | `gps_fault` | `gps_fault` ≡ `nominal` |
| `gps_warmup` | 0.143 | `gps_fault` | `gps_fault` ≡ `nominal` |
| `armed_gate` | 0.143 | — | `imu0_bias_drift` ≡ `imu1_bias_drift` |
| `speed_gate` | **0.000** | — | none |

**`speed_gate` is structurally inert for identifiability.** It controls only
`heading_course`, which is one of four features in `mag_interference`'s LOW
set; losing it leaves that signature unique. This is a new result — the
canonical "regime gate" the white paper holds up as the exemplar of
domain-of-validity gating has **no effect whatsoever on which hypotheses can
be distinguished**. It still affects trust values; it does not affect
identifiability.

### 3.2 The ceiling

| Gates closed | P | κ |
|---|---|---|
| none | 8 | 0.000 |
| any single gate | 7–8 | 0.000–0.143 |
| `armed_gate` + any GPS gate | 6 | 0.286 |
| **all four** | **6** | **0.286** |

**Closing every actuating gate simultaneously costs only two of eight
distinctions.** The maximum gate-induced coarsening is **κ = 0.286**. Five of
the eight hypotheses remain mutually distinguishable under total gate closure,
because their signatures rest on features no gate controls (`redundant_imu`,
`attitude_gravity_mag`, all `phys_*` except `phys_gps`, all `temp_*`).

### 3.3 The two collisions, confirmed exactly

- **`gvalid` or `gps_warmup` closed → `gps_fault` ≡ `nominal`.** `gps_fault`'s
  LOW set is the singleton `{phys_gps}`; losing it leaves the empty signature,
  which is `nominal`'s. The posterior ratio is then pinned at the prior ratio
  0.02 : 0.86 for the remainder of the flight. A GPS fault cannot be diagnosed
  in the mode where GPS is invalid — which is the mode a GPS fault produces.
  This is the sharpest identifiability failure in the system.
- **`armed_gate` closed → `imu0_bias_drift` ≡ `imu1_bias_drift`.** Both
  restrict to `{redundant_imu}`. Equal priors, so the posterior splits evenly
  and no evidence can separate them.

Both are genuine indistinguishability rather than weak evidence, because
`bayes.py:99-100` **skips** a gated feature entirely instead of down-weighting
it: the two hypotheses receive identical log-likelihood on every surviving
feature, forever.

---

## 4. Disjointness — resolved

Part 0C returned a preliminary verdict of "SHARED, not disjoint; joint
counterfactuals mandatory; **pure interaction possible**." The computation
settles the open half.

**Sharing is real.** Two features are products of two gates each:
`heading_course ← speed_gate × gvalid` and `phys_gps ← gvalid × (ticks > 3)`.

**But there is no pure interaction.** Because the composition is
*multiplicative*, closure is an **OR**: either gate alone drives the feature to
zero. Across all 11 multi-gate configurations, **no gate set produces a merge
that no proper subset produces**, and **no configuration is superadditive** in
κ (joint κ never exceeds the sum of its members' marginals — it is always far
below).

> **Verdict: SHARED BUT SUB-ADDITIVE.** Level-1 marginals still cannot be
> summed — but the reason is **over-counting**, not hidden interaction.
> `gvalid` alone and `gps_warmup` alone each yield κ = 0.143, and closing both
> also yields 0.143, because they destroy the *same* feature. Naïve addition
> would have doubled a real effect rather than missing one.

This is a correction to the Part 0C expectation, in the direction that makes
the system *better behaved* than feared. It is recorded as measured, not
argued.

---

## 5. WP1 discrepancy — `armed_gate` batch proxy vs runtime flag

| Path | `armed_gate` |
|---|---|
| batch (`comparator.py:137`) | `clip((ticks − 5.0)/1.0, 0, 1)` — unconditional; **no armed flag exists** |
| runtime, flag `None` (`online.py:491`) | identical proxy |
| runtime, flag `True` | `clip(τ − armed_since, 0, 1)` |
| runtime, flag `False` | hard `0.0` |

The runtime flag comes from real vehicle state: `ulog_source.py:217-225` emits
`vehicle_status.arming_state == 2` when that topic is present in the log.
**WP-E1 adopts the runtime flag as reference semantics** and records the
divergence rather than repairing either path.

### Corpus fraction in the disagreement window

The proxy is unsaturated only over **[0, 6) s** of each flight. Across the
corpus that is **156.0 s = 6.54% of raw exposure** — and **0.0% of monitored
exposure**, because the entire window lies inside the 20 s arm-time exclusion
already removed from the denominator.

| Assumed arming time | Disagreement window | Corpus seconds | % raw | Reaches monitored time? |
|---|---|---|---|---|
| 0 s | [0, 6) | 156.0 | 6.54% | No |
| 2 s | [2, 6) | 104.0 | 4.36% | No |
| **5 s** | — | **0.0** | 0.00% | **Paths coincide exactly** |
| 10 s | [5, 11) | 156.0 | 6.54% | No |
| 20 s | [5, 21) | 416.0 | 17.44% | **Yes** |
| 30 s | [5, 31) | 676.0 | 28.33% | **Yes** |
| 60 s | [5, 61) | 1151.2 | 48.25% | **Yes** |

**Consequence.** For any vehicle arming at or before the 20 s arm window, the
divergence cannot affect a single published real-log figure. For a vehicle
arming *later*, it reaches monitored time, and the runtime correctly withholds
motor-edge evidence that the batch path would credit.

**Which case applies is UNKNOWN.** `data/real_logs_report.json` records no
timestamps, no arming events and no topic inventory, so neither the per-log
arming time nor even whether `vehicle_status` was present can be recovered
from committed artifacts. The bound above holds without that knowledge.

---

## 6. Second WP1 discrepancy — recorded, not repaired

The WP1 formalization states that under an invalid GPS fix, `gps_fault`
"collapses onto `nominal` **and `unexpected_maneuver`**." **The computation
does not reproduce the second half.** Under `gvalid` closed:

```
gps_fault            []                     <- merges with nominal
nominal              []
unexpected_maneuver  ['temp_gps']           <- remains distinct
```

`unexpected_maneuver`'s LOW set is `{temp_gps}`, and `bayes.py:131-133` gates
every `temp_*` feature with `np.ones` unconditionally — no gate can close it.
The three-way collapse does not occur; the collision is `gps_fault` ≡
`nominal` only.

Per the standing constraint this is recorded, not corrected in the WP1
artifact. The WP1 conclusion that a GPS fault is undiagnosable under invalid
fix is **unaffected** — only the size of the collision class changes, from
three members to two.

---

## 7. The mechanism distinction — and why it must be preserved

Two mechanisms coarsen the diagnostic partition, and they are not the same
thing:

| | Mechanism | Endogenous? | Measured? | Max κ |
|---|---|---|---|---|
| **Gate closure** | a gate closes as a function of vehicle state, potentially the fault itself | **Yes** | **No** | **0.286** (bound) |
| **Channel absence** | the channel is not in the log at all | No — a corpus property | Yes (WP-A2 E2) | **1.000** (observed) |

κ is agnostic to *why* a feature is unobservable, which is what lets one index
cover both. Results that turn on the *cause* of closure cover only the first.

**Any downstream write-up must use the channel-absence framing for the WP-A2
E2 result and must not present it as a measurement of gate conditioning.** The
26-log measurement is a real and strong empirical result — the first
measurement of κ on a real corpus — but the mechanism it measures is channel
unavailability, and gate-induced coarsening remains unmeasured.

The quantitative contrast is itself informative: **the corpus property is
several times more damaging than the theorized mechanism's structural
ceiling.** Gate closure can destroy at most two of eight distinctions; missing
channels destroyed all seven in 23% of the corpus. See
`kappa_mechanisms.png`.

The WP-A2 E2 figure is also a **lower bound**: it was computed from channel
inventory alone, and in flight gates close *on top of* absent channels.

---

## 8. Limitations

1. **No gate closure was observed.** Every κ in §3 is what closure *would*
   cost, not what closure *does* cost, because no per-tick gate trace exists.
2. **Gates are treated as binary.** `armed_gate` and `speed_gate` are ramps in
   [0, 1]; `bayes.py:99-100` skips only at `gate <= 1e-9`. Partial closure
   down-weights rather than removes, so the map describes the endpoints of a
   continuum, not the interior.
3. **The map is per-tick and memoryless.** The diagnosis carries an EW
   accumulator (`SMOOTH_ALPHA = 0.06`, ~15 ticks) that persists across gate
   transitions, so a briefly-closed gate does not instantaneously erase
   accumulated evidence. Transient dynamics are unmodelled.
4. **Signature-level only.** Two hypotheses with distinct signatures may still
   be *practically* inseparable at realistic evidence strengths. κ bounds what
   is possible, not what is achieved.
5. **The gate map was read from source by hand.** It is documented line by
   line in `research/wp_e1/gate_map.py` and is auditable, but it is not
   generated from the code.
6. **Threshold provenance is permanently indeterminate** — see
   `docs/audit/WP_A2_THRESHOLD_PROVENANCE.md`. It bears on every simulated
   result this repository produces.

---

## 9. Handoff to WP-E2

To be preregistered **before** any data is acquired, and after these
limitations are on record.

| # | Question | Requires |
|---|---|---|
| 1 | Do gates actually close during real faults, and which ones? | Per-tick gate traces from re-acquired `.ulg` logs |
| 2 | Does `gvalid` reach 0 during a GPS spoof? | This single measurement decides whether the `gps_fault` ≡ `nominal` collision is an operational blind spot or a latent one |
| 3 | What is in-flight κ, with gates and channel absence together? | Both; WP-A2 E2 is the lower bound to beat |
| 4 | Does the EW accumulator bridge short gate closures? | Tick-level posterior traces across transitions |
| 5 | Which corpus logs carry `vehicle_status`, and when did they arm? | Settles §5 exactly rather than by bound |

Question 2 is the highest-value single measurement in the programme: it
decides whether Paper 1 pursues set-valued isolation or a conditional
impossibility theorem.

**Prerequisite for all five:** re-acquire the corpus
(`tools/fetch_real_logs.py --no-run`, then `tools/build_dataset_manifest.py`)
on a network-permitted host, and hash it — the logs are currently identified
by UUID with `content_sha256: null`, so reproducibility is nominal rather than
cryptographic.
