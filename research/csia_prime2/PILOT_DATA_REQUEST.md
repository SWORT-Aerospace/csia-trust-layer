# PRIME-2 pilot data request

**2026-10-03. Status: CSIA_PRIME2_WAITING_FOR_REAL_PILOT_DATA.**

PRIME-2 asks one question: on real PX4 quad-X flight-test data, does CSIA
produce engineering value that an individual monitor, the raw ULog, or
ordinary manual review does not? Answering it needs real logs from outside
the CSIA development loop, with the team's own diagnosis held back until
CSIA's result is sealed. **No such data is available today**, so nothing
has been analysed and nothing will be simulated in its place.

**Boundary:** offboard log analysis only; zero control authority; no FORGE;
no onboard component.

## 1. What was checked (2026-10-03)

| source | found | qualifies? |
|---|---|---|
| this machine | internal SITL flights; the 7 real logs already used in PRIME and PRIME-1 (six pyulog test logs, the PX4 docs boat); two RflyMAD ROS bags | **no**: no external team, no withheld diagnosis; the bags are not ULog, have no ESC data and no licence |
| repository branches and issues | issue #2 proposes public Flight Review logs | **no**: no withheld diagnosis; the network policy refuses `logs.px4.io` and `review.px4.io` (403) |
| connected Google Drive | no ULog or flight-log files | — |
| connected Gmail | no flight logs (one unrelated inquiry) | — |

## 2. The exact minimum we need

| item | minimum | preferred |
|---|---|---|
| vehicle | PX4 multirotor | **quad X** (other vehicles are refused by design, not analysed) |
| logs with events | at least 1 | **10 to 20** flight-test logs containing events the team has **already investigated** |
| nominal logs | **5 or more** from the same vehicle and configuration | 10 or more, including maneuvering and wind |
| format | original PX4 ULog (`.ulg`), unmodified | — |
| ESC RPM | not required: without it, propulsion conclusions are limited and the page says so | **strongly preferred** (`esc_status` with RPM, e.g. bidirectional DShot or telemetry ESCs) |
| command path | — | `actuator_motors` (PX4 with control allocation) |
| other topics | — | `vehicle_angular_velocity`, `vehicle_attitude`, `estimator_status`, `battery_status` (with current if measured), `vehicle_status`, `control_allocator_status`, PX4's log messages |
| per log, platform metadata | PX4 version, airframe, approximate flight date | known hardware modifications; ESC model and protocol; whether ESC current is logged |

**A corpus is not rejected for missing optional topics.** Each log gets a
support state before anything is interpreted:
- SUPPORTED;
- PARTIAL;
- UNKNOWN_VERSION;
- UNSUPPORTED_SCHEMA;
- UNSUPPORTED_VEHICLE_CONFIGURATION.

The report then states what can and cannot be diagnosed from what is
present.

**No diagnosis is needed before the analysis.** Please send none.

## 3. How the blind pilot runs

1. **You choose the logs.** Give them neutral file names (e.g. `F01.ulg`).
   Keep the diagnosis, event times and labels out of names, folders, notes
   and sidecar files.
2. **You send only the logs and the platform metadata above.** The intake
   fields are: PX4 version, airframe or vehicle class, ESC telemetry, known
   modifications, free notes without findings. In blind mode an expected
   event time is refused.
3. **CSIA hashes every file on arrival.** The originals are kept read-only
   and never enter git.
4. **The frozen release runs exactly once** (section 5). Nothing is tuned on
   your data before scoring.
5. **The result is sealed:** input hashes, versions, every machine and human
   report hash. The seal is given to you.
6. **Only then do you reveal your findings.** Event times, diagnosis,
   confirmed hardware issue, maintenance or replacement result, pilot notes,
   other evidence.
7. **Comparison and scoring follow.** Misses, wrong answers and correct
   ambiguities are recorded as they are; CSIA's blind result is never
   overwritten.

## 4. Confidentiality and anonymisation

- Logs stay on SWORT's local analysis machine (or yours: the analyzer runs
  offline from a wheel, so you can run it yourselves under the same seal
  protocol). They are never committed, uploaded or shared.
- Only file hashes and anonymised results enter SWORT's records.
- You may remove position topics (e.g. global position, GPS) before sending.
  Please tell us which topics you removed; propulsion analysis does not use
  them.
- An NDA can be signed before any transfer.
- Nothing is published, and no case study is written, without your written
  permission. Any case study is anonymised and separates your facts from
  CSIA's blind result.

## 5. What will run (frozen)

| element | value |
|---|---|
| command | `csia-assure` (release prime1) |
| wheel | `csia_trust_layer-0.8.0-py3-none-any.whl`, SHA-256 `04e2ec961de9cec37650fd5a062f86b3766e1c3de1337bcfb7669058acaac331` |
| support contract | prime1-r1, SHA-256 `5955c309e14175c8434ad6ab307a88581891398e9692fdd0636a9500131e27b9` |
| claim-evidence matrix | SHA-256 `53eabc7a8c3958bfc25716c7af47bd8072a5e6c920d8db6a50a03a1c841c5110` |
| PRIME-1 final state | SHA-256 `6de818af3c317f1c4fb25e442a64a2a544a379fc4be8a5e5d1c80414a24ea422` |
| repository commit | `a0de6c8` (branch `claude/csia-prime-pilot`) |

On receipt, and before any log is opened, the PRIME-2 baseline lock (Phase
0) re-runs the historical gates, the fresh-install check, the pilot
regression tests and the expected historical defect pins. If anything
differs, the pilot stops with PRIME2_BASELINE_MISMATCH.

## 6. What you get

- **A first page per log:**
  - what happened;
  - what the evidence justifies and what it cannot;
  - the evidence that was refused, and why;
  - shared sources;
  - missing instrumentation;
  - the next engineering check.
- **A receipt per conclusion,** and the sealed manifest.
- **After your reveal, a scored comparison.** Every CSIA statement is classed
  against your findings, including what CSIA missed or got wrong.

**Current validation, stated plainly:** PX4 simulation only. No real
propulsion fault has yet been analysed against independent truth. That is
what this pilot is for. Pricing remains a commercial hypothesis
(`research/csia_prime1/PILOT_OFFER.md`).
