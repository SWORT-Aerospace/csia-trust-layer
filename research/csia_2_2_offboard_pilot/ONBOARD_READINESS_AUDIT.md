# Onboard readiness audit (Phase 27)

**2026-10-01.** **Not a port, and not an authorization.** CSIA 2.2 stays
offboard, observational, with zero control authority. This audit lists
what would remain before any onboard use.

**Status key:**
- **DONE:** exists and is tested for onboard use;
- **PARTIAL:** exists offboard or as an estimate only;
- **NOT STARTED:** nothing exists.

| item | status | what exists | what remains |
|---|---|---|---|
| C implementation of 2.2 (envelope, admissibility, lineage) | NOT STARTED | nothing. `docs/embedded/NATIVE_RUNTIME_STATUS.md`: CSIA runs in Python; a native C core of selected v1 trust functions exists and is parity-tested on the host only | the whole layer in C, parity-tested against Python on the same inputs |
| C implementation of Semantic Core 2.1.1 | NOT STARTED | a design-level delta (`research/csia_semantic_core_2_1_revision/C_RUNTIME_DELTA_UPDATE.md`) | implementation and parity |
| memory bounds | PARTIAL | 2.1.1 core: about 13-15 KB RAM, ESTIMATED (H743_UPDATE.md). 2.2: measured only offboard on desktop CPython (`SCALE.md`) | a static bound for 2.2 per tick: envelopes × lineage roots (≤ 16) × records |
| runtime bounds | PARTIAL | 2.1.1 core: 30-500 µs/tick at 480 MHz, ESTIMATED. 2.2 offboard: Analyzer step 2.4 ms median on desktop CPython (2.2 review) | a target build and WCET measurement |
| contract loading | PARTIAL | versioned JSON, validated once at load (Python) | a compiled contract table, and load-time validation on target |
| profile loading | PARTIAL | the PV1-PV9 + PG1 gate (Python) | the gate run at build time, and a profile digest checked on target |
| epoch integration | PARTIAL | from logs: the lane counter, IMU, aiding sets, unwrapped reset counters. S1 shows the selector path on a real log | uORB subscriptions to `estimator_selector_status`, `estimator_status`, `sensor_selection` on target; a real lane switch (designed, not run) |
| producer health | PARTIAL | from logs (alignment, fault flags, time slip; CUSUM freshness) | the same from live topics, with timeouts |
| fault containment | PARTIAL | offboard, one malformed producer never fails a tick; `analyze-many` isolates each input in a process | onboard isolation: no allocation, bounded loops, no exception path |
| watchdog behaviour | NOT STARTED | — | what happens when the reasoner overruns or stops; it must have no effect on flight |
| logging | PARTIAL | offboard byte-stable reports and manifests | an onboard log topic with bounded size, so offboard replay can reproduce onboard results |
| RTA / authority boundary | NOT STARTED for 2.2 | v1.1's firewall reports and logs, with no command authority (`csia/v1_1/firewall.py`). 2.2 has no output path into the vehicle at all | an explicit, reviewed boundary, before any onboard output exists |
| hardware testing | NOT STARTED | no STM32H743 build or measurement in this repository | a target build, HIL, and timing and memory measurement |

**Conclusion.** Nothing in the pilot changes the 2.2 position: offboard only.

**Onboard prerequisites still open:**
- C implementation;
- target timing and memory bounds;
- watchdog behaviour;
- a reviewed authority boundary;
- hardware testing.
