# CSIA Trust Layer — Commercialization & SBIR Readiness

SWORT LLC · SAM-registered · operating avionics business with revenue.

## The pitch in three measured numbers

1. **Detection** (deterministic sim harness, 39 automated tests): GPS spoof
   detected in 2.2 s at 89% attributed confidence; IMU drift isolated to the
   correct unit at 99%/0%; mag/power/vibration faults at 100%, 1.5–2.6 s.
2. **Real-data validation** (26 public PX4 quadrotor flights, 0.66 flight
   hours, `csia analyze-logs`): **3 candidate false alarms → 4.5/flight-hour**
   in offline-validation posture; 24/26 flights alarm-free. Public logs carry
   only 5 of 8 monitored channels at usable rates — the SOW001 vehicle
   provides all 8 by design.
3. **SITL-validated live path** (`tools/sitl_validate.py`): full autonomous
   ArduCopter mission with the runtime consuming live MAVLink; 6 sensors
   monitored, min trust 0.78, zero false alarms, PASS.

## SBIR/STTR fit

**AFWERX Open Topic (Phase I)** — direct fit: assured PNT / GPS-denied
resilience / sensor integrity for attritable UAS.
- *Technical objectives for Phase I* (all are natural extensions of this
  repo): (1) Monte Carlo detection datasheet (ROC curves, latency
  distributions vs fault amplitude — `csia report` scaled to 10^3
  randomized flights); (2) σ-calibration campaign on SOW001 hardware
  (procedure already written: docs/HARDWARE.md); (3) multi-fault diagnosis
  upgrade (factor-graph replacement for naive Bayes); (4) SITL fault
  injection matrix (GPS spoof via SITL SIM_GPS_TYPE, EKF comparisons).
- *Commercialization narrative*: existing custom-avionics revenue; the trust
  layer ships as (a) companion-computer software licensed per vehicle,
  (b) SDK licensed to OEMs/integrators, (c) fleet monitoring for Part-107
  operators (mission-reliability, insurance data).
- *TRL statement*: TRL 4 (component validation in lab/SITL environment),
  targeting TRL 6 in Phase II on SOW001 flight hardware.

**NASA SBIR** — adjacent topics: autonomous systems health management,
UAS traffic management safety cases.

## What exists today (evidence package)

| Artifact | Where |
|---|---|
| Runtime + failsafe + plugins, 39 tests, CI | this repo, `csia/`, `.github/workflows/ci.yml` |
| Real-data validation report | `data/real_logs_report.json`, `csia analyze-logs` |
| SITL validation harness | `tools/sitl_validate.py` (PASS) |
| Live demo | `csia service` → dashboard LIVE tab |
| Hardware deployment guide | `docs/HARDWARE.md` |
| Math/architecture spec | README architecture section |

## Gap list to close before Phase I submission

- [ ] Monte Carlo datasheet (extend `csia report` to N randomized seeds ×
      fault amplitudes; ROC + latency percentiles) — compute only, ~1 day.
- [ ] 2-page one-pager + 90 s dashboard screen recording.
- [ ] Whitepaper (README math + real-data section, PDF).
- [ ] Provisional patent decision (gated-evidence dynamic trust graph +
      self-baselining field mode). File BEFORE public demos/publication.
- [ ] SOW001 bench: 60 s ground + hover logs → first hardware σ calibration.
- [ ] Push to private GitHub (CI is committed and ready).

## Known technical debt (disclosed, not hidden)

- Diagnosis is naive Bayes: simultaneous independent faults split the
  posterior (Phase I objective 3).
- Real-data attitude scoring rests on 2 graph edges when only one IMU
  stream exists; full-rate dual-IMU telemetry (SOW001) restores the
  designed 5-edge evidence base.
- MavlinkActuator command path is SITL-only until tethered validation.
- Certification: advisory-only product until a customer-funded DO-178C
  program; language everywhere reflects this.
