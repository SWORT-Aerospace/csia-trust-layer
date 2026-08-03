# CSIA Trust Layer — Evidence Matrix

**Baseline:** commit `c13889f` (v0.8.0).
**Purpose:** the artifact an Army technology-transition reviewer would build:
every technical claim the repository makes, the evidence behind it, and an
honest confidence classification. Where a public claim is stronger than its
evidence, weaker wording is recommended.

**Classification:**
- **Validated** — independently reproducible measurement backs the exact claim.
- **Supported** — direct evidence, but scope-limited (e.g. desktop only,
  synthetic only) and the claim is correspondingly scoped.
- **Partially Supported** — evidence exists for part of the claim; part is
  extrapolation.
- **Concept Only** — designed/implemented but not measured.
- **Unsupported** — asserted without evidence (none should remain; flagged
  loudly if found).

| # | Claim (as stated) | Evidence | Test / artifact | File | Confidence | Status |
|---|---|---|---|---|---|---|
| C1 | Per-sensor Trust Coefficient in [0,1], recursive Beta-Bayesian, adaptive forgetting | Bounds/convergence tests pass across suite | `test_engine.py` | `trust_engine/engine.py` | High | **Validated** |
| C2 | Diagnosis outputs a probability distribution over causes, never a binary flag | Posterior-is-distribution test; scenario attribution | `test_diagnosis.py`, scenario harness | `diagnosis/bayes.py` | High | **Validated** |
| C3 | Detection: gps_spoof 2.2 s, mag/power/vib fast, latencies per table | 150-run MC, single frozen config, CIs reported | `campaigns/monte_carlo.json` | `validation.py` | High | **Validated** (4 classes) |
| C4 | "IMU isolation 99%/0%" / slow bias-drift handled | MC shows **imu_bias TPR 0.00 [0,0.30]** | `campaigns/monte_carlo.json` | comparator | — | **Unsupported for slow-drift detection** — the isolation *test* (which IMU) passes on the fast scripted case, but *detection* of slow bias fails. See wording note W1. |
| C5 | Zero false alarms in clean flight | Clean MC 0 alarms / 0.8 h; bench clean=0 both configs | `campaigns/monte_carlo.json`, `bench.json` | validation | High (Poisson CI [0,4.4]/hr) | **Supported** (CI is wide; not "zero rate") |
| C6 | Native C core matches Python to 1e-12 | Parity tests (trust + diag + no-evidence + bounds) | `test_native.py` | `csia/native/` | High | **Validated** |
| C7 | Native core 674 ns/tick (247 trust + 427 diagnosis) | Measured on desktop; **not** on target | (author benchmark) | `csia/native/` | Medium | **Supported (desktop)** — see W2 |
| C8 | "est. 7–15 µs on the STM32H743 … ≈0.04% FC CPU at 25 Hz" | Extrapolation from desktop, no target run | none | — | Low | **Concept Only** — see W3 |
| C9 | Causal by construction (bit-identical with/without future data) | Truncation regression atol 1e-10 | `test_comparator.py::test_causality_no_lookahead` | comparator | High | **Validated** |
| C10 | Online layer == batch pipeline (<0.01 divergence) | Regression test | `test_runtime.py::test_online_matches_batch` | online | High | **Validated** |
| C11 | Real-flight: 26 PX4 logs, 0.66 h, **2 candidate false alarms → 3.0 alert episodes/hr (95% CI 0.4–10.9)**, 24/26 alarm-free | analyze-logs campaign report, recounted under `csia/metrics` | `data/real_logs_report.json` | metrics, ulog_source, cli | Medium | **Supported, restated** — supersedes "3 → 4.5/hr", which counted a failsafe *recovery* edge as an alarm (audit F-01, 1.50× over-count). Train/test contamination (C2) still applies; interval is wide at 2 events. See W4 |
| C12 | ArduPilot SITL: full mission, 6 sensors, min trust 0.78, zero false alarms, landed | SITL run (pre-hardening) | `tools/sitl_validate.py` | plugins | Medium | **Partially Supported** — predates v0.8.0 armed/vz/reboot changes; **must be re-run**. See W5 |
| C13 | SITL fault injection: GPS glitch + fix-kill detected live from raw stream | SITL --inject run (pre-hardening) | `tools/sitl_validate.py` | plugins | Medium | **Partially Supported** — same re-run caveat |
| C14 | Raw-GPS monitoring catches a 55 m glitch invisible in fused output | SITL injection observation | `tools/sitl_validate.py` | plugins | Medium | **Supported** (SITL, single scenario) |
| C15 | Soak: 21.2 h flight-equiv, 0 errors, +0.1 MB, latency 1.11× | soak run (desktop) | `tools/soak.py` | runtime | High (desktop) | **Supported (desktop)** — on-target OPEN |
| C16 | Determinism / bit-for-bit reproducible results | Determinism tests; campaigns regenerate byte-identical | `test_sensors.py`, `campaigns/*.json` | sensors, validation | High | **Validated** |
| C17 | Armed-state gating from real vehicle state | Unit tests both directions + MAVLink map | `test_runtime.py`, `test_mavlink_map.py` | online/failsafe/plugins | Medium-High | **Supported** — live armed/disarm on hardware not yet observed |
| C18 | Interceptor seeker: 100% detection, 0.44 s / 0.24 s latency, 100% attribution | 50-run/scenario seeker MC | `deliverables/montecarlo_results.json` | seeker/ | Medium | **Supported (SYNTHETIC)** — clearly labeled synthetic; not seeker hardware. See W6 |
| C19 | 62-test suite, CI-gated | pytest suite green; CI builds native core | `.github/workflows/ci.yml` | tests/ | High | **Validated** |
| C20 | Advisory by default; commands nothing unless opted in | LoggingActuator default; MavlinkActuator gated | (code) | `service.py` | High | **Validated** |

## Recommended wording changes (claim stronger than evidence)

- **W1 — "IMU isolation 99%/0%" (README validation table).** Keep only if
  qualified. The 0% is the *exonerated neighbor*, which is correct; but the
  same row implies slow-bias detection works, and MC shows TPR 0.00.
  Recommend: *"IMU isolation (which-unit attribution) validated on the
  scripted fast-bias case; slow-drift **detection** is an open gap
  (MC TPR 0.00, tracked)."*
- **W2 — "674 ns/tick" without host qualifier.** Recommend always appending
  *"(desktop x86-64; target-hardware timing pending — see REQ-050)."*
- **W3 — "est. 7–15 µs on the STM32H743 … 0.04% CPU."** This is an
  unmeasured extrapolation. Recommend labeling it explicitly *"projected,
  not measured"* everywhere it appears (README already hedges once; make it
  consistent, and drop the precise "0.04%" until measured).
- **W4 — "4.5/flight-hour."** **RESOLVED 2026-08-03.** The figure was not
  merely under-hedged, it was miscounted: it included a failsafe *recovery*
  edge (audit F-01). Restated as *"2 candidate false alarms → 3.0 alert
  episodes/hr on 0.66 h (Poisson 95% CI 0.4–10.9/hr); untuned upper bound on
  a train/test-contaminated set — held-out campaign per
  docs/VALIDATION_PROTOCOL.md pending."* The definition now lives in
  `docs/validation/METRIC_DEFINITIONS.md` and is shared by `analyze-logs`,
  `bench` and `mc`. README table updated to match.
- **W5 — SITL rows.** Mark in the README table as *"measured pre-v0.8.0;
  re-run required"* until `tools/sitl_validate.py` is re-executed on current
  code. (README "Path to flight" already flags this; the table should too.)
- **W6 — Seeker "100% detection."** Already labeled synthetic — keep the
  "SYNTHETIC / not seeker hardware" qualifier adjacent to *every* instance,
  including any slide or one-pager, not just the table caption.

## Whitepaper (SWORT_CSIA.pdf) — carried-over wording flags

- *"flight-proven" / "TRL 4 (flight-validated)"* → *"validated on real flight
  data and live SITL"* (has not flown in the loop).
- *"247–427 ns per tick"* → *"674 ns/tick (247 trust + 427 diagnosis)"*.
- Test count *"39"* (p.3) and *"48"* (p.5) → *"62"* consistently.
- *"reproducible builds verified bit-for-bit across independent clones"* →
  *"bit-for-bit reproducible results from fixed seeds"* (results, not builds).

## Bottom line

No claim in the repository is **Unsupported** *except* the slow-IMU-bias
detection implication (C4/W1), which the requirements and traceability
already withdraw. The largest confidence gaps are (a) desktop-vs-target
timing (C7/C8), (b) the contaminated real-log false-alarm rate (C11), and
(c) pre-hardening SITL numbers (C12/C13). All three are closable with the
Phase 7 hardware and one SITL re-run — no algorithm change required.
