# Changelog

All notable changes to the CSIA Trust Layer. Format: [Keep a Changelog];
this project versions the **software and its evidence**, not just code.
Validated scientific results (trust model, diagnosis, campaigns) are
preserved across releases — campaign artifacts regenerate byte-identical.

## [Unreleased] — 2026-09 — Product hardening pass

No behaviour changed. `campaigns/monte_carlo.json`, `campaigns/bench.json` and
every scenario artifact still regenerate bit-identically; the frozen v1 core
was not touched.

### Fixed (claims and code hygiene, not behaviour)
- **The Monte Carlo campaign never varied the flight, and said it did.**
  `csia/validation.py` drew a fresh seed per trial and passed it to
  `generate_flight`, whose scripted truth ignores seeds entirely — every one
  of the 150 runs flew the same trajectory. The numbers are unaffected and
  reproduce exactly; what was wrong was the appearance of per-trial flight
  randomization. The call is now explicit, the consequence is stated where
  the confidence intervals are produced, and the stream draw is deliberately
  RETAINED because removing it would shift every subsequent draw and change a
  committed regression artifact. `tests/test_flight_truth_determinism.py`
  pins all of it.
- **The mathematical paper described a posterior threshold that does not
  exist.** It said support is withheld for "a leader above 0.999"; the
  implementation applies the structural condition alone, at any posterior,
  and `engineering/v1_1/support/support.py` refuses to filter by posterior
  mass on purpose — doing so would make identifiability depend on the score
  whose support is in question. The firing ticks run down to 0.9691, which a
  0.999 gate would have excluded. Corrected, bound to the artifact, and
  guarded by `tests/test_support_state_posterior_range.py`.
- Dead code removed from nine shipped modules (unused imports, unused locals,
  a spurious f-string). Each was a statement that claimed to do something and
  did not; one of them was the only visible symptom of the defect above.

### Added
- `tools/publication/proof_audit_check.py` and `make proof-audit-check` — the
  mathematical paper's verification artifact is regenerated and compared
  against what is committed, with the `commit` field exempt by name. Every
  other load-bearing artifact already had a staleness gate; this one did not.
  Wired into `BLOCKING_GUARDS` and the publication CI lane.
- `tests/test_package_lint.py` — the shipped package is pyflakes-clean. The
  single exemption is `csia/diagnosis/`, which is FROZEN and therefore
  un-fixable; the exemption is checked against the freeze test's own path list
  and fails if it ever stops being needed. `pyflakes` added to the `dev`
  extra.
- A version-drift guard: `csia.__version__` and `pyproject.toml` are two
  hand-maintained copies of one fact and nothing compared them.
- `csia-shadow --help` now describes what the tool does, states that it has no
  command path in any mode, and points at `--self-test`.

### Documented
- `papers/BIB_VERIFICATION_LEDGER.yaml` records six blocked verification
  routes rather than three: OpenAlex, Semantic Scholar and arXiv were checked
  this session and also fail at the proxy. All three are `rejected_routes`
  anyway, so none could have retired a marker — they were tried so that "no
  route exists" is a measurement. **No marker was retired. The bibliography
  blocker stands.**

## [Unreleased] — 2026-08 — Evidence foundation (slice 3A)

### Added
- `csia/datasets/` — log manifests, SHA-256 integrity, stable ids, dataset
  aggregate hash, exact + conservative near-duplicate detection, partition
  policy with automated leakage checks.
- `csia/experiments/manifest.py` — canonical provenance (commit, dirty tree,
  dataset hash, config hashes, seed, compiler, evidence environment).
- `csia/metrics/exposure.py` — exposure accounting by health class, partition,
  autopilot, firmware, airframe and sensor config; exact Poisson intervals;
  zero-event bounds; exposure planner.
- Versioned schemas `datasets/schemas/*.json`; CI gates on schema validity,
  split leakage and stale committed artifacts.
- `docs/audit/CSIA_DATASET_PROVENANCE_AUDIT.md`,
  `docs/validation/DATASET_SPLIT_POLICY.md`,
  `docs/validation/DATASET_DEDUPLICATION_REPORT.md`,
  `docs/validation/EXPOSURE_PRECISION_PLAN.md`.

### Corrected (claims, not behavior)
- **"Healthy flight hours" withdrawn.** No corpus log carries any annotation.
  Verified-healthy exposure is **0.000 h**; all 26 logs are UNANNOTATED.
  Absence of a CSIA alert is the hypothesis under test, not evidence for it.
- **Rate denominator corrected.** 21.8% of recorded duration lies inside
  `arm_time`, where no alert can be raised. Rate restated from 3.02/h on
  0.663 raw hours to **3.86/h on 0.518 MONITORED hours (95% CI 0.47–13.94)**.
- **Held-out exposure recorded as 0.000 h** — all 26 logs shaped `field_mode`
  and the offline failsafe posture, so none is eligible for blind evaluation.

### Unchanged
- No trust-algorithm, threshold, failsafe or recommendation change.
  `campaigns/bench.json` regenerates bit-identical.

## [Unreleased] — 2026-07 — Dashboard: tactical console + high-speed envelope

### Added (dashboard / demo only — no algorithm, engine, or sensor change)
- **Tactical cross-sensor HUD**: pure-black C2/HUD dashboard theme (neutral
  greys, no color cast; saturated color reserved strictly for trust status).
- **Ground-velocity readout** on the right column, below the regime gate.
- **Autonomous-remediation response panel**: SCAN→ANALYZE→FIX→STABILIZE loop
  surfacing the failsafe posture and advisory action log at the cursor.
- **`high_speed_dash` scenario** + `fast_cruise` flight profile (peak 52.0 m/s
  ground speed) exercising the velocity readout and speed-gated heading edge
  at an elevated envelope. Trust layer flies it clean (min trust 0.89,
  failsafe NORMAL). Kinematic only — aerodynamic drag not modeled, sensor
  tolerances quad-tuned; labeled as such in the scenario title and README.
- **Self-contained `dashboard_standalone.html`** (all nine replays embedded,
  zero network fetches) via `tools/build_standalone_dashboard.py`.
- Dashboard screenshots in `deliverables/` (`dashboard_gps_spoof.png`,
  `dashboard_high_speed_dash.png`).

### Fixed (dashboard rendering)
- **Playback stutter**: cursor now interpolates on a fractional index every
  animation frame (smooth glide) while data updates stay at the 25 Hz tick
  rate, instead of snapping only on integer tick changes.
- **Column misalignment**: remediation log locked to a fixed height and chart
  heights retuned so both columns bottom-align identically across scenarios.
- **Blue color cast**: background moved from a blue-tinted gradient
  (#04060A / #0A0F16) to pure neutral black (#000000) with true greys.

### Preserved / verified unchanged
- Trust model, diagnosis engine, sensor models, runtime, and all eight
  original scenarios are byte-for-byte untouched; the existing test corpus
  and committed campaign artifacts are unaffected.

## [0.8.0] — 2026-07 — Deployment-grade runtime + engineering hardening

### Fixed (demonstrable bugs)
- **No-evidence divide-by-zero** in `TrustCore.step`: a node losing every
  evidence source at once crashed the runtime (reachable in field mode and
  the seeker path). Now holds the Beta belief; Python and C agree; pinned by
  regression + native-parity tests. (REQ-020)
- **FC-reboot data loss**: post-reboot MAVLink samples were dropped forever
  (negative timestamps). Now the epoch re-anchors monotonically. (REQ-023)
- **C-core stack safety**: oversized `n`/`nc` could overrun stack scratch;
  now bounds-checked and rejected. (REQ-025)

### Added (robustness, no algorithm change)
- Armed-state gating from HEARTBEAT / ULog `vehicle_status` (REQ-014).
- GPS `vz_valid=False` handling for GPS_RAW_INT (no fabricated z-residual).
- Per-sample crash containment + monitor self-health in `state.jsonl` (REQ-021/022).
- MAVLink stream reconnection with capped backoff (REQ-024).
- `tools/soak.py`, `tools/perf_regression.py`, `tools/fetch_real_logs.py`.
- `deploy/` systemd package (`csia.service`, `install.sh`, `install_pi.sh`).
- Engineering docs: requirements system, traceability matrix, evidence
  matrix, hardware validation plan, embedded checklist, report templates,
  TRL assessment, transition report, hardware BOM, held-out validation
  protocol.

### Preserved / verified unchanged
- `csia bench`, `csia mc` (150 runs), and the seeker Monte Carlo regenerate
  **byte-identical** to the committed `campaigns/*.json` and
  `deliverables/montecarlo_results.*` — hardening changed no validated result.
- Trust model, diagnosis engine, sensor models, scenario catalog: untouched.

### Known gaps (tracked, not hidden)
- Slow IMU bias-drift detection: MC TPR 0.00 [0, 0.30] — claim withdrawn (REQ-005).
- Target-hardware timing/soak: OPEN pending Pi 5 (REQ-050/052).
- Flight heritage: none yet (REQ-053).
- SITL numbers predate this release — re-run required.

## [0.7.0] — earlier baseline
- Native C core (674 ns/tick desktop), raw-GPS monitoring, SITL fault
  injection, real-log campaign (26 flights), Monte Carlo framework,
  REQUIREMENTS.md, FMEA.md, adversarial architecture review.

[Keep a Changelog]: https://keepachangelog.com/
