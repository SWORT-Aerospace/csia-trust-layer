# Changelog

All notable changes to the CSIA Trust Layer. Format: [Keep a Changelog];
this project versions the **software and its evidence**, not just code.
Validated scientific results (trust model, diagnosis, campaigns) are
preserved across releases — campaign artifacts regenerate byte-identical.

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
