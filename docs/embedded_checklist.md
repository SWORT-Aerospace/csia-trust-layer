# CSIA Trust Layer — Embedded Readiness Checklist

**Baseline:** commit `c13889f` (v0.8.0). Work top to bottom; each item is a
checkbox with the requirement it satisfies. Nothing here is pre-checked —
these are the acts, not claims.

## 0. Before the hardware arrives (doable now)
- [x] Deployment package exists (`deploy/csia.service`, `install.sh`, `install_pi.sh`)
- [x] On-target tools exist (`benchmark_pi.py`, `stress_pi.py`)
- [x] Report templates exist (latency, reliability, hardware_validation)
- [x] Desktop soak passes (`tools/soak.py`: 21.2 h-equiv, 0 err, +0.1 MB)
- [x] Perf-regression baseline seeded (`campaigns/perf_baseline.json`)

## 1. Flash & bring-up
- [ ] Raspberry Pi OS 64-bit (Bookworm+) flashed, SSH enabled
- [ ] `sudo deploy/install_pi.sh` completes clean
- [ ] Native core builds on aarch64 (**REQ-051**)
- [ ] `pytest tests/test_native.py -q` passes on target (1e-12 parity)
- [ ] `pytest -q` full suite passes on target

## 2. Latency characterization (**REQ-050**)
- [ ] `tools/benchmark_pi.py --out reports/latency_pi.json`
- [ ] p99 tick latency < 40 ms (25 Hz budget) with margin recorded
- [ ] Native vs Python path both under budget
- [ ] Fill `docs/latency_report_template.md`

## 3. Telemetry integration
- [ ] FC → Pi MAVLink link up (mavlink-router or direct UDP)
- [ ] `csia run --source mavlink --conn <route>` streams live
- [ ] Armed/disarmed gating observed in `state.jsonl` (**REQ-014**)
- [ ] Link-drop reconnect observed (**REQ-024**)
- [ ] FC-reboot epoch re-anchor observed (**REQ-023**)
- [ ] `vz_valid=False` path confirmed on GPS_RAW_INT (**GPS vz fix**)

## 4. Endurance (**REQ-052**)
- [ ] `tools/stress_pi.py --hours 8 --out reports/soak_pi.jsonl` overnight
- [ ] RSS growth < 10 MB
- [ ] Worst p99 tick < 40 ms under thermal load
- [ ] Zero contained errors
- [ ] Fill `docs/reliability_report_template.md`

## 5. Airframe calibration
- [ ] Sigma calibration on THIS airframe (docs/HARDWARE.md)
- [ ] `auto_baseline_s` baseline captured; clean ground run = 0 transitions
- [ ] Profile selected/tuned (`csia/profiles.py`)

## 6. Service hardening
- [ ] `systemctl enable --now csia`; survives reboot
- [ ] `Restart=always` verified (kill the process, confirm respawn)
- [ ] Logs rotating in `/var/log/csia/`
- [ ] Self-health block present in `state.jsonl` (**REQ-022**)
- [ ] Advisory-only confirmed (`enable_commands` OFF) (**REQ-046**)

## 7. Flight heritage (**REQ-053**)
- [ ] Supervised advisory-only flight flown, VLOS, rules followed
- [ ] `state.jsonl` recorded end to end
- [ ] Post-flight analysis: 0 errors, sane trust, no spurious EMERGENCY
- [ ] Update README/whitepaper wording to "flown in an advisory role"

## 8. SITL regression (parallel, no hardware)
- [ ] `tools/sitl_validate.py` re-run on v0.8.0
- [ ] `tools/sitl_validate.py --inject gps_glitch` re-run
- [ ] Update evidence matrix C12/C13 confidence

## Exit criteria
All of sections 1–6 checked → **"target-hardware validated"** is defensible.
Section 7 checked → **"advisory flight heritage"** is defensible.
Neither claim may appear in public materials until its section is complete.
