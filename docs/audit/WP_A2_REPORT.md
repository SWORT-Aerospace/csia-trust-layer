# WP-A2 Report — Complete External Claim Audit

**Date:** 2026-08-22 · **Branch:** `research/wp_e1` · **Suite:** 445 before,
448 after (the three added tests are the documentation-count guard)
**Artifacts:** `WP_A2_CLAIM_PROVENANCE_MATRIX.csv`,
`WP_A2_THRESHOLD_PROVENANCE.md`, `WP_A2_CORRECTION_PACKAGE.md`,
`reports/wp_a2/`

---

## 1. Verdict

Twenty-six quantitative claims from the xTech Apex Intercept submission were
traced to source. **Nothing was fabricated.** Every figure was the true
measured value at the commit it was written from, and five reproduce exactly
today with no qualification needed. The defects are of four kinds: *scope
inflation* (a whole-suite test count presented as fault-detection evidence,
inflated 4× to 7.75×), *prohibited framing* ("flight-validated" and
"flight-proven" against a corpus with 0.000 h verified-healthy and 0.000 h
held-out exposure), *staleness* (an alert rate that has since moved twice, and
counts that go stale within days), and *omission* (a 100% detection figure
whose own measured floor is not stated). The submission's internal
contradiction — 62 tests in one section, 48 in another — resolves benignly:
both were exactly right, at commits two days apart, and the sections were
never reconciled. The one claim with no recorded evidence at all is the 55 m
GPS case study, whose most striking half was never measured by any code. The
most consequential new finding is not in the submission's wording but beneath
it: at the channel counts the corpus actually carries, `nominal` structurally
absorbs at least one fault hypothesis in **26 of 26 logs**.

---

## 2. Claim matrix summary

| Status | Count | Claims |
|---|---|---|
| `TRUE_BUT_SCOPE_INFLATED` | 8 | A1a, A1b, A2d, A3a, A4c, A5b, A6, A8b |
| `UNVERIFIABLE_NO_SOURCE` | 7 | A3b, A9, A10a–e |
| `TRUE_AND_REPRODUCIBLE` | 5 | A4a, A7a, A7b, A7c, A8a |
| `PROHIBITED_FRAMING` | 3 | A2a, A2b, A2c |
| `INTERNALLY_INCONSISTENT` | 1 | A1c |
| `TRUE_BUT_AMBIGUOUS` | 1 | A4b |
| `SUPERSEDED` | 1 | A5a |
| `FALSE` | **0** | — |
| **Total** | **26** | |

Four claims carry `prohibited_wording = Y` (A2a–c and A5a): the three
flight-validated instances and the alert rate whose framing presented an
unannotated corpus as healthy.

**The A4b probe.** Directed to determine whether "100% detection at tested
magnitudes" is false or merely misleading. It is **not false**. The campaign's
nominal magnitudes (`ir_decoy` 6.0°, `rf_jam` 4.0° azimuth, from
`csia/seeker/scenarios.py:16-20`) are **not members** of the swept set
{0.1, 0.2, 0.35, 0.6, 1.5, 4.0}° — the decoy nominal exceeds the largest swept
point — and both sit far above the ~0.36° combined bearing-noise floor. The
sweep is a deliberate probe *below* the floor, not a contradiction of the
campaign. Status downgraded from `FALSE` to `TRUE_BUT_AMBIGUOUS`; the defect
is that the prose omits the floor its own table reports. **This distinction
was worth resolving: "misleading by omission" and "false" are not the same
representation to a government customer.**

---

## 3. The four findings that change the evidence base

### Finding 1 — Prohibited framing, already flagged internally and never fixed

Four instances of "flight-validated"/"flight-proven". `docs/TRL_ASSESSMENT.md:75-77`
already states, verbatim: *"'TRL 4 (flight-validated)' in older materials
overstates: **it has not flown.** … (Fixed in v0.8.0 README; **whitepaper edit
pending**.)"* The same section flags the 674 ns figure and the seeker 100%
claim as pending. **Three WP-A2 findings are unclosed action items, not
discoveries.**

There is a second-order problem. That document's own prescribed replacement —
*"validated on real flight-log replay"* — was itself later prohibited by
Rule W7, which forbids presenting the unannotated corpus as validated.
`TRL_ASSESSMENT.md` is baselined at `c13889f` and has **never been updated
post-Slice-3A**, so the TRL 4 derivation still rests partly on evidence that
was subsequently downgraded to 0.000 h verified-healthy. The correction of
record needs correcting.

*Operational effect (E5):* the arm-window exclusion that produced the
corrected denominator is **spread, not concentrated** — every flight longer
than the 20 s window loses exactly 20 s, and the top five flights own only
19.2% of the lost time. But the *per-flight* median unmonitored fraction is
**40.0%** (max 63.5%), so the aggregate 21.8% substantially understates what a
typical flight in this corpus loses.

### Finding 2 — Scope inflation on the test count, and the harness is weaker than "synthetic" implies

62 was the entire suite; the fault harness is 5 scenarios / 8 tests. Beyond
scope, the harness's assertions are **regression bounds derived from the same
seeded runs they evaluate** (`test_fault_scenarios.py:22-27`).

*Operational effect (E4):* measured against the bounds actually asserted —

| Scenario | latency | asserted | slack | min-trust | asserted | slack |
|---|---|---|---|---|---|---|
| gps_spoof | 2.16 s | < 5.0 | **+2.84 s** | 0.5905 | < 0.72 | +0.129 |
| imu0_bias_drift | 13.0 s | < 16.0 | **+3.00 s** | 0.7657 | < 0.85 | +0.084 |
| mag_emi | 1.48 s | < 4.0 | **+2.52 s** | 0.2764 | < 0.50 | +0.224 |
| power_sag | 1.60 s | < 4.0 | **+2.40 s** | 0.3991 | < 0.60 | +0.201 |
| vibration_anomaly | 2.56 s | < 5.0 | **+2.44 s** | 0.1658 | < 0.45 | +0.284 |

**Detection could take roughly twice as long in every scenario and still
pass.** Min-trust bounds are tighter, `imu0_bias_drift` tightest at +0.084.
The measured values reproduce the in-source comment exactly (2.16/0.5905/0.8934
against 2.2/0.59/0.89), confirming both the provenance and the arithmetic.

### Finding 3 — "Every edge carries a validity gate": inflated wording, *small* operational effect

Six of eleven gates vary with vehicle state; five are compile-time constants.
The natural inference — that 45% of the graph is dead weight — is **wrong**,
and the measurement says so.

*Operational effect (E1), by ablation of `TickData.edges` with the engine,
diagnosis, graph, thresholds and seeds unchanged:*

- **`redundant_imu` is the most load-bearing edge in the graph.** Removing it
  makes `imu0_bias_drift` **never detected at all** — trust never crosses the
  0.85 line — and collapses the correct-cause posterior by **−0.82**. This is
  by design: the IMUs deliberately have no self-model, so IMU health is judged
  only through graph edges.
- `attitude_gravity_mag` moves `mag_emi` latency by +0.32 s and
  `imu0_bias_drift` min-trust by −0.074.
- `vibration_prop_freq` moves `vibration_anomaly` min-trust by +0.086.
- `power_thrust` contributes between 1e-6 and 6.7e-4 — negligible, even on the
  power-sag scenario it spans, because the battery and motor self-models carry
  that signal.
- **`temp_bias_drift` is genuinely inert**: exactly 0.0 on every metric in
  every scenario. Its permanent 0.2 gate induces a steady-state trust offset of
  **1.8e-4 on `baro` and 6e-5 on `battery`** — three orders of magnitude below
  anything operational. It also appears in **no hypothesis's LOW set**, so it
  is inert in both directions.

**A constant gate is not a dead edge.** "Always open" is a legitimate design
choice for a relationship whose physics is always valid. The genuinely inert
component is **one edge in eleven, not five.** The wording defect stands; the
severity is small and is reported as small.

### Finding 4 — Structural diagnostic coverage on the real corpus (new)

The largest finding in WP-A2, and the first measurement of κ on a real corpus.
Because `bayes.py:99-100` **skips** a feature whose gate is closed rather than
down-weighting it, two hypotheses whose LOW signatures coincide over the
surviving features receive identical likelihood on every remaining feature and
stay pinned at their prior ratio forever.

> **What this is and is not.** The mechanism measured here is **channel
> unavailability** — channels absent from the logs entirely, a property of the
> corpus. It is **not** gate-conditioning, in which a gate closes as a
> function of the fault being diagnosed. Both coarsen the partition; only the
> second is endogenous, and **gate-induced coarsening remains unmeasured**.
> κ is agnostic to *why* a channel is inactive, so it covers this case
> cleanly; results that turn on the *cause* of closure do not. Any downstream
> write-up must use the channel-absence framing, not the endogeneity framing.
>
> **The number is a lower bound.** κ was computed from channel inventory
> alone. In flight, validity gates close on top of absent channels, so actual
> in-flight coarsening is at least this severe and probably worse.

Restricting each hypothesis's signature to the features the channels support,
over the configurations the 26 logs actually carry:

| Channels | Logs | Fraction | Observable classes (of 8) | κ | Absorbed into `nominal` |
|---|---|---|---|---|---|
| 5 | 12 | 46% | 5 | 0.429 | `imu0_bias_drift`, `imu1_bias_drift`, `vibration_anomaly` |
| 4 | 3 | 12% | 3 | 0.714 | + `gps_fault`, `unexpected_maneuver` |
| 4 | 2 | 8% | 4 | 0.571 | + `mag_interference` |
| 3 | 2 | 8% | 2 | 0.857 | 6 of 7 faults |
| 3 | 1 | 4% | 4 | 0.571 | 4 faults |
| 2 | 6 | 23% | **1** | **1.000** | **all 7 faults** |

κ = (H − P)/(H − 1); 0 = fully distinguishable, 1 = total collapse.

- **In 26 of 26 logs (100%), at least one fault hypothesis is structurally
  indistinguishable from `nominal`.**
- In the six 2-channel logs (23% of the corpus), **every** hypothesis collapses
  into one class. The diagnosis carries zero discriminating information.
- Even the best-instrumented configuration leaves three faults absorbed.

**Scope, stated precisely.** This constrains *attribution*, not detection. The
trust recursion and the failsafe operate on trust values and data freshness,
not on the diagnosis posterior, so the "24 of 26 alarm-free" result is
unaffected and no safety property is implicated. What it does mean is that had
a fault been present in most of these flights, the diagnosis could not have
named it. That is a further, independent reason not to read the corpus's
silence as evidence of health.

---

## 4. Threshold provenance — `INDETERMINATE`, permanently

Full treatment in `WP_A2_THRESHOLD_PROVENANCE.md`. In summary:

- **Test-assertion thresholds: `NOT_DISJOINT`**, stated in the source itself.
- **`field_mode` on the real corpus: `NOT_DISJOINT`**, already on record
  (Slice-3A D-03; held-out exposure 0.000 h).
- **System σ, gates and failsafe levels: `INDETERMINATE`.**
  `csia/prediction/comparator.py` has exactly one commit in its history — the
  root commit — and that root is a **single squashed import of 56 files** that
  already contains the sensors, the comparator, the scenarios, the tests and
  the real-log campaign. All pre-v0.6.0 development history is absent.

> **This verdict is final, not pending.** No work inside this repository can
> close it. Closing it requires evidence that does not exist here: original
> design notes deriving each σ from sensor physics, component datasheets
> supporting the declared noise classes, or the pre-import git history if it
> survives on another machine.

Weak evidence *for* physical derivation (datasheet-class noise constants,
physical budgets in comments, σ magnitudes an order above the noise floor) and
one structural argument (no tuning fingerprints across 48 commits) are
recorded, but neither upgrades the verdict. Consistency with derivation is not
derivation.

---

## 5. What the corrected evidence supports — a checkable list

1. Causality, online/batch equivalence, C-vs-Python parity at 1e-12,
   determinism and byte-identical campaign regeneration are **verified**.
2. Trust and diagnosis behave as specified **on simulated data**: bounded
   coefficients, a distribution over causes, graceful degradation.
3. **Live SITL integration works** — full autonomous mission, injected GPS
   faults detected from the raw stream. Pre-hardening; re-run required.
4. The seeker synthetic campaign is **exactly reproducible**, with a measured
   detection floor near 0.36°.
5. **No detection performance on real flight data is claimed.** Corpus
   unannotated; verified-healthy and held-out exposure both 0.000 h.
6. The fault harness is **scripted synthetic injection with regression
   bounds**, not independent detection evidence.
7. Embedded timing is a **host benchmark**; no target build exists; the C core
   is not on any production execution path.
8. The alert rate is an **interval**, [0.47, 13.94] per monitored hour.
9. Threshold provenance is **permanently indeterminate**.

---

## 6. Figures

| Figure | File | Replaces / supports |
|---|---|---|
| Detection floor (rate + latency vs magnitude, noise floor marked) | `reports/wp_a2/e3_detection_floor.png` | the unqualified "100% detection" claim |
| Channel-count coverage (κ and faults absorbed per configuration) | `reports/wp_a2/e2_channel_coverage.png` | the "5 of 8 channels" claim; Finding 4 |
| Constant-gate ablation (per-edge Δ min-trust) | `reports/wp_a2/e1_inert_gates.png` | the "every edge carries a validity gate" claim |

---

## 7. Open items and ownership

### The repository can close these

| Item | Action |
|---|---|
| `TRL_ASSESSMENT.md` never updated post-Slice-3A | Re-derive TRL 4 without the withdrawn real-log evidence; replace its own prohibited "validated on real flight-log replay" phrasing |
| 674 ns has no generating artifact | Add a committed benchmark command and artifact, or withdraw the figure |
| SITL rows predate the 2026-07 hardening | Re-run `tools/sitl_validate.py`; record both raw and fused GPS so A9 can be settled either way |
| Corpus content hashes are null | Run `fetch_real_logs.py --no-run` + `build_dataset_manifest.py` on a network-permitted host |
| Stale counts in public artifacts | **Done** — counts removed from prose; `tests/test_doc_counts.py` enforces it |

### Requires the user

| Item | Why |
|---|---|
| **`SWORT_CSIA.pdf` itself** | Never under version control; no PDF has ever been tracked. The submitted wording cannot be diffed, only audited from quoted excerpts. `docs/external/MANIFEST.csv` holds a `PENDING_FILE_NOT_SUPPLIED` row |
| Submission date and channel | Needed for the correction letter and the manifest |
| Business figures (A10a–e) | No repository artifact; company facts |
| Pre-import design notes or history | The only thing that could close threshold provenance |

### Note on `329bc93`

Reported earlier in this session as unreachable. **That was wrong** — it is
reachable from `main`, `research/wp_e1` and
`claude/code-reviewer-repo-export-zicovg`, so it was never at risk from
garbage collection. It is *"Fix Monte Carlo reproducibility (hash-seed bug
found in sanity re-run)"* (2026-07-20), touching `deliverables/SUMMARY.md`,
`montecarlo_results.{json,md}` and `tools/interceptor_montecarlo.py` — the
commit that made the seeker campaign bit-reproducible and moved the clean
false-alarm figure from 0/50 to 1/50. A local tag
`archive/handoff-source-of-record` was created; **pushing it failed on a
network error and it is not on the remote.** No protection is needed, but the
push can be retried for tidiness.

---

## 8. Residual risk — what a reviewer could still challenge

1. **Finding 4 is a structural result, not an empirical one.** It says what
   the diagnosis *could not* have distinguished. A reviewer may reasonably ask
   for the empirical counterpart — posterior trajectories on the real logs —
   which requires re-acquiring the corpus. Deferred to WP-E2.
2. **Threshold provenance stays open forever.** A rigorous evaluator may treat
   every simulated detection result as unverifiable on that basis alone. There
   is no repository-side answer.
3. **The corpus is not content-addressed.** Re-downloading by UUID does not
   prove byte-identity with what the campaign ran on; PX4 Flight Review logs
   can be replaced or deleted by their uploaders. Reproducibility here is
   nominal, not cryptographic.
4. **Slow-IMU-bias detection remains a measured failure** (MC TPR 0.00
   [0, 0.30]). It is documented, not hidden, but it is a genuine capability
   gap in a headline sensor class.
5. **The corrected alert rate is still a training-set number.** Correcting the
   denominator does not create held-out exposure. Approximately 3 zero-event
   flight-hours are needed to bound it below 1/hour, and 30 to bound it below
   0.1/hour.
6. **The self-assessed TRL and MRL are self-assessed.** Nothing here
   constitutes third-party TRL validation.
7. **This audit covered the excerpts supplied.** Claims elsewhere in the PDF
   are unaudited.

---

## 9. Inventory of `UNVERIFIABLE_NO_SOURCE`

These claims **cannot be supported** until the named artifact is supplied.
They should not appear in any future external document in their present form.

| ID | Claim | Missing artifact |
|---|---|---|
| A3b | "sized for an STM32H743 … ~0.04% CPU at 25 Hz" | A target build and a target measurement. Neither exists; the figure is an estimate derived from an estimate |
| A9 | "55 m GPS glitch invisible in fused output" | A SITL run that records both `GPS_RAW_INT` and the fused estimate. No code has ever compared them; the tool writes no artifact |
| A10a | "$1,000–$2,500 per deployed unit" | Costing basis |
| A10b | "Integration NRE est. $1.5–3.0M / 12–24 months" | Estimation basis |
| A10c | "Number of Employees: 5" | Company fact — user confirmation |
| A10d | "Capital Raised Total: $0" | Company fact — user confirmation |
| A10e | "Self-assessed MRL (software-adapted): 6–7" | The MRL rubric used. No MRL assessment exists in the repository |

Plus, categorically: **every claim in `SWORT_CSIA.pdf` not quoted to this
audit is `UNVERIFIABLE_NO_SOURCE`**, because the document has never been under
version control and could not be read.
