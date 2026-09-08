# CSIA Trust Layer — Hardware Validation Plan

**Baseline:** commit `c13889f` (v0.8.0). **Status of this document:** PLAN +
TEMPLATE. No results are filled in — populate the tables as tests run. Do not
copy numbers from the desktop; the point of this document is *target* data.

This plan takes CSIA from "deployable advisory software (desktop-validated)"
to "validated on target hardware, flown in an advisory role." It maps to the
embedded requirements REQ-050…REQ-053.

**Companion documents.** The bench build (boards, wiring, power, fault
injector) is `hardware/validation_rig/E2_BUILD_PACKET.md`. The software
integration — how to connect CSIA, what each stage should produce, and how to
prove out a hypothesis — is `docs/FIELD_INTEGRATION_RUNBOOK.md`. Run
`tools/deploy/preflight.py` before every session; a trial without its
preflight record cannot be attributed to a build.

## Test articles

| Item | Role | Requirement |
|---|---|---|
| Raspberry Pi 5 (companion computer) | runs the CSIA advisory service | REQ-050/051/052 |
| Flight controller (ArduPilot/PX4) | provides MAVLink telemetry | REQ-014, 023, 053 |
| Airframe (any COTS quad) | carries the stack in flight | REQ-053 |

CSIA **listens only** — any ArduPilot/PX4 vehicle is a valid test article.
The SOW001 FC is not required to establish advisory flight heritage.

## Validation sequence (each gate must pass before the next)

### Gate A — Bring-up (bench, no props)
- [ ] `deploy/install_pi.sh` completes; native core builds on aarch64.
- [ ] `pytest tests/test_native.py` passes on the Pi (**REQ-051**, 1e-12).
- [ ] Full suite `pytest -q` passes on the Pi.
- [ ] `tools/benchmark_pi.py` → p99 tick < 40 ms with margin (**REQ-050**).
  Record in `docs/latency_report_template.md`.

### Gate B — Telemetry integration (bench, FC powered, no props)
- [ ] Pi receives MAVLink from the FC; `csia run --source mavlink` streams.
- [ ] HEARTBEAT arm/disarm toggles motor-edge gating (**REQ-014**) — verify
  in `state.jsonl` that motor edges gate to 0 when disarmed.
- [ ] Pull the telemetry link; confirm reconnect with backoff (**REQ-024**).
- [ ] Reboot the FC; confirm epoch re-anchor + layer reset (**REQ-023**).

### Gate C — Endurance (bench, overnight)
- [ ] `tools/stress_pi.py --hours 8` → no leak, no thermal deadline miss
  (**REQ-052**). Record in `docs/reliability_report_template.md`.

### Gate D — Calibration (airframe, ground + hover)
- [ ] Sigma-calibration procedure (docs/HARDWARE.md) on this airframe;
  `OnlineTrustLayer(auto_baseline_s=...)` baseline captured.
- [ ] Clean ground run → zero failsafe transitions.

### Gate E — Advisory flight (field, supervised)
- [ ] One supervised advisory-only flight, VLOS, applicable UAS rules.
- [ ] Service in advisory mode (`enable_commands` OFF); `state.jsonl` recorded.
- [ ] Post-flight: zero contained errors, sane trust track, no spurious
  EMERGENCY (**REQ-053**). This establishes advisory flight heritage.

### Gate F — SITL regression (any time, in parallel)
- [ ] `tools/sitl_validate.py` re-run on v0.8.0 (refreshes C12).
- [ ] `tools/sitl_validate.py --inject gps_glitch` (refreshes C13).

## Sign-off

| Gate | Date | Operator | Result | Report artifact |
|---|---|---|---|---|
| A Bring-up | | | | reports/latency_pi.json |
| B Telemetry | | | | |
| C Endurance | | | | reports/soak_pi.jsonl |
| D Calibration | | | | |
| E Advisory flight | | | | flight state.jsonl |
| F SITL regression | | | | |

**Only after Gate E may the README/whitepaper state "flown in an advisory
role."** Command authority (beyond advisory) is out of scope for this plan.
