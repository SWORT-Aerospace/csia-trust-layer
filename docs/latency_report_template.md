# CSIA Trust Layer — On-Target Latency Report (TEMPLATE)

> Populate from `tools/benchmark_pi.py --out reports/latency_pi.json` run on
> the target. Do not fill from desktop numbers. Every `<...>` is a blank.
> Satisfies **REQ-050**. Budget: 40 ms per tick (25 Hz).

## Host
- Model: `<from /proc/device-tree/model, e.g. Raspberry Pi 5 Model B Rev 1.0>`
- Arch / cores: `<aarch64, 4x Cortex-A76 @ 2.4 GHz>`
- OS / kernel: `<Raspberry Pi OS 64-bit, kernel x.y.z>`
- Python: `<3.x>`
- Native core available: `<yes/no>`
- CPU temp at start: `<°C>` · governor: `<performance/ondemand>`

## Method
- Tool: `tools/benchmark_pi.py`, repeats = `<N>`
- Scenario: clean (nominal flight, no faults) — worst-case is the full
  edge/physics/diagnosis path every tick
- Cores measured: pure-Python (reported), native-C (parity-verified)
- Methodology UNCHANGED from desktop harness (same code paths)

## Results — per-tick latency (µs)

| core | ticks | mean | p50 | p95 | p99 | max | p99 margin vs 40 ms |
|---|---|---|---|---|---|---|---|
| python | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>`x |
| native | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>`x |

## Verdict
- p99 (python path) < 40 ms: `<PASS/FAIL>`
- Stated margin: `<>`x
- Notes (throttling, outliers, first-tick warmup): `<>`

## Interpretation
- CSIA CPU budget as a fraction of the 40 ms tick: `<p99/40000>` = `<%>`
- Headroom for the autopilot + companion workload alongside CSIA: `<>`
- This **measures** what the README previously **projected** (7–15 µs
  STM32 estimate / "0.04% CPU"). Replace those projections with these
  measured numbers, host-labeled, in the README once filled.

Signed-off: `<name>` `<date>`
