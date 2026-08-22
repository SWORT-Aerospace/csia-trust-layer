# WP-A2 Correction Package — SWORT_CSIA.pdf (xTech Apex Intercept)

**Prepared:** 2026-08-22 · **Repository baseline:** branch `research/wp-e1`
**Supporting audit:** `WP_A2_CLAIM_PROVENANCE_MATRIX.csv`,
`CSIA_EXTERNAL_CLAIM_PROVENANCE_AUDIT.md`, `WP_A2_THRESHOLD_PROVENANCE.md`
**Measurements:** `reports/wp_a2/`

---

## D1. Cover note

### What is being corrected

Six categories of defect in the technical evidence presented in our xTech Apex
Intercept submission. Each affects how an evaluator should weigh our
validation evidence, and in four cases the submission claims more than the
evidence supports.

### The defects

**1. Prohibited framing: "flight-validated" and "flight-proven."** The
submission describes the trust/diagnosis core as flight-validated in four
places, including the header table. **CSIA has never flown in the loop.** The
real-flight evidence is offline replay of 26 public PX4 logs, and those logs
are **entirely unannotated** — no log carries a ground-truth health label, so
**verified-healthy exposure is 0.000 hours**. Absence of a CSIA alert on an
unannotated log is the hypothesis under test, not evidence for it. All 26 logs
also shaped the system's field-mode tolerances, so **held-out exposure is
0.000 hours**: the corpus is a training set, and any number computed on it is
a training-set number.

**2. A superseded alert rate, quoted as a point estimate.** The submission
states "3 candidate false alarms (4.5/flight-hour)." Two independent errors
were later found. The count included a failsafe *recovery* edge as an alarm
(a 1.50× over-count), and the denominator included the 20-second arm window in
which no alert can be raised — 21.8% of the quoted exposure. The corrected
figure is **2 alert episodes across 0.5183 monitored flight-hours = 3.86 per
hour, Poisson 95% CI [0.47, 13.94]**. That interval spans a factor of 30. At
n = 26 flights, a bare point estimate overstates the precision by roughly an
order of magnitude and should never be quoted alone.

**3. A test-count figure inflated 4× to 7.75× by scope.** "Validated via a
62-test automated fault harness" attributes the size of our entire test suite
to fault-detection evidence. 62 was the whole suite. The fault harness proper
is **five scripted scenarios exercised by eight tests** (fifteen including the
seeker scenarios); the remaining tests are software-correctness contracts —
causality, online/batch equivalence, C-vs-Python parity, determinism. Further,
those five scenarios are **synthetic injections**, and their assertions are
regression bounds set below values measured from the same seeds, so passing
indicates no regression rather than detection capability.

**4. A channel-availability figure stated as typical when it is the maximum.**
"5 of 8 monitored channels" was reached by fewer than half the corpus. The
distribution is **mean 3.88**: 12 of 26 flights at 5 channels, 5 at 4, 3 at 3,
and **6 at 2**. This is not a presentational detail. Channel availability is
structural: our diagnosis skips a feature whose channels are absent rather
than down-weighting it, so hypotheses can become formally indistinguishable.
We have now measured this on the corpus for the first time, and the result is
significant — **see §D4, finding 4**.

**5. An unqualified 100% detection figure that omits its own measured floor.**
Part 3 states 100% detection without the synthetic qualifier that appears on
Table 2, and "100% detection at tested magnitudes" omits the detection floor
the same table reports. To be precise about severity: **the 100% figure is
true.** The campaign's nominal magnitudes sit far above the noise floor, and
the magnitude sweep is a separate experiment that deliberately probes below
it. The defect is **omission, not falsehood** — but the omitted floor
(0/20 detections at 0.1°, 10/20 at 0.2°) is the more credible and more
useful result, and should be stated.

**6. A case study with no recorded evidence.** "A 55 m GPS glitch invisible in
fused output but caught from the raw stream." The SITL harness requests both
the fused and raw GPS messages but **reads only the fused one, and only for
altitude gating**. No code compares the two, and the tool writes no artifact.
The striking half of that claim — that the glitch was concealed in the fused
estimate — was a live observation that nothing recorded. It should be
withdrawn or restated as an unrecorded observation.

### Context

Having stated the defects: **no figure in the submission was fabricated.**
Every number we published was the true measured value at the commit it was
written from. The two test counts that contradict each other inside the
document — 62 and 48 — were both exactly correct, at commits two days apart;
the sections were written against different snapshots and never reconciled.
The trust values, the run counts, the latencies and the graph topology all
reproduce exactly from committed artifacts today.

The defects are **scope inflation, framing, staleness and omission** — not
invention.

We also want the evaluator to know that we found these ourselves. The
prohibited "healthy flight hours" framing was identified in our own dataset
provenance audit, corrected in the repository, and enforced with an automated
test that fails the build if any log is ever classified as verified-healthy.
The "flight-validated" wording was flagged in our own TRL assessment with the
note *"whitepaper edit pending."* That edit is what this package delivers. We
are issuing it before being asked, and we have added CI that prevents a stale
test count from reaching a public artifact again.

---

## D2. Drop-in replacement text

Organised by the submission's section structure. Replace in place.

### Header table

> **Old:** TRL 4 core (flight-validated)
>
> **New:** TRL 4 core (self-assessed; validated in simulation, on unannotated
> real flight-log replay, and in live SITL — not flown)

### Part 1 — Technology description

> **Old:** Its validated core … is flight-proven
>
> **New:** Its core is validated in simulation, exercised on unannotated real
> flight-log replay, and demonstrated in live ArduPilot SITL with fault
> injection. It has not flown in the loop.

> **Old:** Dynamic Trust Graph (8 sensor nodes, 11 physics-based edges). Every
> edge carries a validity gate.
>
> **New:** Dynamic Trust Graph (8 sensor nodes, 11 physics-based edges). Every
> edge carries a gate weight; six of the eleven vary with vehicle state (armed
> ramp, GPS fix validity, ground-speed), and five are constants — four
> permanently open because their physical relationship is always valid, and one
> (`temp_bias_drift`) fixed at 0.2, which never actuates and contributes no
> discriminating evidence.

### Part 3 — Fire-control extension

> **Old:** the flight-validated trust/diagnosis core
>
> **New:** the trust/diagnosis core validated in simulation, on real
> flight-log replay, and in live SITL

> **Old:** 100% detection across 100 seeded Monte Carlo runs, 0.44 s (IR decoy)
> and 0.24 s (RF jam) mean latency, and 100% fault attribution
>
> **New:** **SYNTHETIC — sensor models only; not validated against seeker
> hardware.** 100% detection across 100 seeded Monte Carlo runs (50 per
> scenario), mean latency 0.436 s (IR decoy) and 0.242 s (RF jam), 100% fault
> attribution. A separate 20-runs-per-point magnitude sweep establishes the
> detection floor: detection falls to 0.50 at a 0.2° decoy offset and to 0.00
> at 0.1°, consistent with a combined bearing-noise floor near 0.36°. The
> campaign magnitudes (6.0° decoy; 4.0° azimuth jam) sit well above that floor.

> **Old:** 100% detection at tested magnitudes with 1/50 clean false alarms
>
> **New:** 100% detection at the campaign magnitudes, with a measured
> detection floor near 0.36° (see sweep), and a clean false-alarm rate of 1/50
> (0.02) — a single brief CAUTION in terminal endgame geometry that
> self-cleared.

### Technical Maturity

> **Old:** Trust/Diagnosis Engine, TRL 4 … Validated via a 62-test automated
> fault harness
>
> **New:** Trust/Diagnosis Engine, TRL 4 (self-assessed; component validated
> in the laboratory, not in a relevant environment). Regression-gated by a
> CI-enforced suite of behavioral contracts — causality, online/batch
> equivalence, C-vs-Python numerical parity at 1e-12, determinism, bounds
> safety — which includes a five-scenario synthetic fault harness. The
> harness asserts regression bounds set below previously measured values from
> the same seeds; passing indicates no regression, not independent evidence of
> detection capability.

> **Old:** 674 ns per tick (247 trust + 427 diagnosis), sized for an STM32H743
> flight computer (~0.04% CPU at 25 Hz)
>
> **New:** **Host benchmark, not a deployed measurement.** The native C core
> measures approximately 247 ns (trust) + 427 ns (diagnosis) per tick on an
> x86-64 desktop compiled `-O2`. It is parity-pinned to the Python
> implementation at 1e-12 over the production 8-node/11-edge graph and is
> sized for an STM32H743-class flight computer, but **no target build and no
> target measurement exist**, and the C core is **not on any production
> execution path** — the Python runtime is what executes today. Any
> microsecond or CPU-percentage figure for the STM32H743 is a projection from
> host timing.

> **Old:** mag interference and power sag 1.5–1.6 s; GPS spoofing 2.2 s;
> vibration 2.6 s; IMU bias drift (slow drift by design) 13.0 s
>
> **New:** Detection latencies on **scripted synthetic fault injection** from
> fixed seeds: mag interference 1.5 s, power sag 1.6 s, GPS spoofing 2.2 s,
> vibration 2.6 s, IMU slow bias drift 13.0 s. Simulation results, not
> real-fault measurements. Independently, Monte Carlo shows slow-IMU-bias
> **detection** at TPR 0.00 [0, 0.30]; the isolation (which-unit attribution)
> result holds only on the scripted fast-bias case.

> **Old:** 3 candidate false alarms (4.5/flight-hour; 24 of 26 flights
> alarm-free) across 26 real PX4 flight logs (0.66 flight-hours), 5 of 8
> monitored channels, offline, without airframe-specific threshold calibration
>
> **New:** CSIA was replayed offline against 26 public PX4 Flight Review logs
> without airframe-specific threshold calibration. **No CSIA alert episode
> occurred in 24 of the 26.** Two alert episodes across **0.5183 monitored
> flight-hours** give **3.86 episodes per hour, Poisson 95% CI [0.47, 13.94]**
> (n = 26 flights). Exposure is *monitored* time; raw log duration is 0.663 h,
> of which 21.8% lies inside the arm window where no alert can be raised —
> and that aggregate understates the per-flight effect, because **the median
> flight loses 40.0% of its duration to the arm window and the worst loses
> 63.5%**. Channel availability ranged from 2 to 5 of 8 trust-graph channels,
> **mean 3.88** (12 flights at 5, 5 at 4, 3 at 3, 6 at 2). **Verified-healthy
> exposure: 0.000 h** — these logs carry no annotation, and CSIA's silence is
> not evidence of health. **Held-out exposure: 0.000 h** — all 26 shaped the
> field-mode tolerances. Further, at these channel counts the diagnosis layer
> could not have *named* most faults had they occurred: in all 26 logs at
> least one fault hypothesis is structurally indistinguishable from healthy
> flight, and in the six 2-channel logs all eight hypotheses collapse into a
> single class (see §D4, finding 6). Alarm-free silence on this corpus is
> therefore doubly weak evidence — the logs are unannotated, *and* the
> attribution layer was structurally incapable of separating most causes. The
> confidence interval spans a factor of 30; this is a sanity result on real
> data, not a validated false-alarm rate.

### Case study

> **Old:** a 55 m GPS glitch invisible in fused output but caught from the raw
> stream
>
> **New (restated):** In a live ArduPilot SITL run, a 55 m GPS position glitch
> was injected into the simulator and CSIA raised a GPS trust degradation from
> the raw `GPS_RAW_INT` stream. Whether the glitch was simultaneously
> concealed in the autopilot's fused estimate was observed during the run but
> **not recorded**, and no artifact preserves it. The architectural rationale
> for monitoring the raw stream stands; the comparative claim is withdrawn
> pending a re-run that records both streams. These SITL results also predate
> our 2026-07 live-path hardening and require re-measurement.
>
> **Alternative: delete the claim.** Recommended if space is tight — it is the
> weakest-evidenced item in the submission.

### Business section

Unchanged by this package. Unit cost, integration NRE, headcount, capital
raised and the self-assessed MRL are company facts with no supporting
repository artifact; they are outside the scope of this technical audit and
were **not verified**. If any is quoted as derived from engineering analysis,
supply the basis or mark it as an internal estimate.

---

## D3. Evidence table

| Claim | Old text | New text | Supporting artifact | Commit | sha256 (16) |
|---|---|---|---|---|---|
| A1a/b | "62-test automated fault harness" / "48-test suite" | CI suite of behavioral contracts incl. 5-scenario synthetic fault harness | `pytest --collect-only` at `c13889f` / `10727b6` | `c13889f`, `10727b6` | n/a (re-derived) |
| A2a–d | "flight-validated" / "flight-proven" | validated in simulation, on unannotated replay, and in live SITL — not flown | `docs/TRL_ASSESSMENT.md:75-77` | `c13889f` | n/a (doc) |
| A3a | "674 ns per tick" | host benchmark; C core not on any execution path | `docs/embedded/NATIVE_RUNTIME_STATUS.md` | `944134f` | n/a (doc) |
| A3b | "~0.04% CPU at 25 Hz" | projection; no target build exists | same | `944134f` | n/a (doc) |
| A4a | "100 runs" / "150-run campaign" | unchanged (correct) | `deliverables/montecarlo_results.json` | `329bc93` | `5797ecd0de03ec43` |
| A4b | "100% detection at tested magnitudes" | 100% at campaign magnitudes + measured floor ≈0.36° | `reports/wp_a2/e3_detection_floor.json` | `cb0ef62` | `ff6bd9a46751e685` |
| A4c | unqualified 100% | synthetic qualifier on every instance | `deliverables/montecarlo_results.json` (`config.note`) | `329bc93` | `5797ecd0de03ec43` |
| A5a | "3 false alarms, 4.5/flight-hour" | 2 episodes / 0.5183 h → 3.86/h, CI [0.47, 13.94] | `data/real_logs_report.json` | `f2786f6` | `3fc299136873826a` |
| A5b | "5 of 8 monitored channels" | 2–5, mean 3.88 (12/5/3/6 distribution) | `reports/wp_a2/e2_channel_coverage.json` | `cb0ef62` | `2e7bc6b9ecca6b27` |
| A6 | latency table | same values, scoped as synthetic + regression-bounded | `reports/wp_a2/e4_regression_headroom.json` | `cb0ef62` | `d063b5d994544f0c` |
| A7a–c | INS 0.752/0.935, IR 0.214, INS 0.272, t=8.63/8.88 s | unchanged (correct); add synthetic qualifier | `deliverables/montecarlo_results.json` | `329bc93` | `5797ecd0de03ec43` |
| A8a | "8 nodes, 11 edges" | unchanged (correct) | `csia/trust_graph/graph.py` | `f2786f6` | n/a (source) |
| A8b | "Every edge carries a validity gate" | 6 of 11 vary with state; 5 constant; `temp_bias_drift` inert | `reports/wp_a2/e1_inert_gates.json` | `cb0ef62` | `4659fab924ac37f7` |
| A9 | "55 m glitch invisible in fused output" | withdraw or restate as unrecorded observation | `tools/sitl_validate.py:125-132` | `f2786f6` | n/a (source) |
| A5 denom | 0.66 h | 0.5183 monitored h; 21.8% inside arm window | `reports/wp_a2/e5_armtime_exposure.json` | `cb0ef62` | `936156aee80445a9` |
| corpus | — | 26 logs, hashes null (not acquired) | `datasets/manifests/px4_public_v1.json` | `9d50671` | `d0cd67b20e4d8163` |

---

## D4. What the corrected evidence does and does not support

### Supported

1. **The software is well-engineered and its behavior is pinned.** Causality
   (no lookahead, atol 1e-10), online/batch equivalence, C-vs-Python parity at
   1e-12 over the production graph, byte-identical campaign regeneration.
   These are verified and reproducible.
2. **The trust and diagnosis mathematics does what it claims** on simulated
   data: bounded coefficients, a posterior distribution over causes rather
   than a binary flag, graceful degradation without cascade.
3. **Live SITL integration works.** CSIA consumed a real autopilot's MAVLink
   stream through a full autonomous mission and detected injected GPS faults
   from the raw receiver stream. (Pre-hardening; re-run required.)
4. **The seeker extension's synthetic results are exactly reproducible**,
   including a measured detection floor.

### Not supported

1. **No detection performance on real flight data is claimed.** The corpus is
   unannotated. We do not know whether any of the 26 flights contained a
   fault, so we cannot report a true-positive rate, a false-negative rate, or
   a validated false-alarm rate on real data.
2. **The fault harness is not independent evidence of detection capability.**
   It is scripted synthetic injection whose assertions are regression bounds
   set below previously measured values from the same seeds. WP-A2 E4
   quantified the slack: every scenario carries **+2.40 s to +3.00 s of
   latency headroom on detections that take 1.5–2.6 s**, so detection could
   roughly double in latency and every test would still pass. The suite
   demonstrates **non-regression within a wide band**, not detection
   capability. Min-trust bounds are tighter (+0.084 to +0.284).
3. **Embedded timing is a host benchmark.** No STM32H743 build exists, no
   target measurement exists, and the C core does not execute in production.
4. **The alert rate is an interval, not a number.** [0.47, 13.94] per
   monitored hour. Approximately 3 additional zero-event flight-hours would be
   needed to bound it below 1/hour, and approximately 30 to bound it below
   0.1/hour.
5. **Threshold provenance is permanently indeterminate.** The repository's
   history begins as a single squashed import that already contains every σ
   value, so whether the detection thresholds were fit against these same
   synthetic injections cannot be determined from it, now or later. See
   `WP_A2_THRESHOLD_PROVENANCE.md`.
6. **Diagnostic attribution on the real corpus was structurally limited.**
   This is the finding a reviewer is most likely to press on, and it is new.
   Because an absent feature is *skipped* rather than down-weighted, two
   hypotheses whose signatures coincide over the surviving features are pinned
   at their prior ratio permanently.

   **Mechanism, stated precisely.** What is measured here is coarsening caused
   by **channels being absent from the logs entirely** — a property of the
   corpus. It is *not* a measurement of gate-conditioning, in which a gate
   closes as a function of the fault being diagnosed. Both mechanisms coarsen
   the partition; only the second is endogenous, and the second is
   **unmeasured**. The index below is agnostic to *why* a channel is inactive,
   which is exactly why it applies here.

   **This is a lower bound.** It was computed from the channel inventory
   alone. In flight, validity gates close *on top of* absent channels, so
   actual in-flight coarsening is at least this severe and probably worse.

   Computing this over the channel configurations the 26 logs actually carry:

   | Channels | Logs | Observable classes (of 8) | κ | Faults absorbed into `nominal` |
   |---|---|---|---|---|
   | 5 | 12 | 5 | 0.429 | 3 |
   | 4 | 5 | 3–4 | 0.571–0.714 | 4–5 |
   | 3 | 3 | 2–4 | 0.571–0.857 | 4–6 |
   | 2 | 6 | **1** | **1.000** | **7 (all)** |

   In **26 of 26 logs**, at least one fault hypothesis is structurally
   indistinguishable from `nominal`. In the six 2-channel logs, all eight
   hypotheses collapse into a single class and the diagnosis carries no
   discriminating information at all.

   **Scope of this finding:** it constrains *attribution*, not detection. The
   trust coefficients and the failsafe operate on trust values and data
   freshness, not on the diagnosis posterior, so the "24 of 26 alarm-free"
   result is unaffected. But it means the corpus could not have attributed
   most faults had they been present, which further weakens any reading of
   that silence as evidence of health.

---

## D5. Recommended transmission

Send D1 and D2 to the submission channel. Attach D3 and D4. Do not attach the
raw audit artifacts unless requested — they are available and we will supply
them on request.

State the corrections as findings we generated, dated, with the enforcement we
added. Do not present them as immaterial. **A correction that undersells the
defect requires a second correction, and the second one does not get the
benefit of the doubt.**
