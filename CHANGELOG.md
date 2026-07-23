# Changelog

All notable changes to the CSIA Trust Layer. Format: [Keep a Changelog];
this project versions the **software and its evidence**, not just code.
Validated scientific results (trust model, diagnosis, campaigns) are
preserved across releases — campaign artifacts regenerate byte-identical.

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
