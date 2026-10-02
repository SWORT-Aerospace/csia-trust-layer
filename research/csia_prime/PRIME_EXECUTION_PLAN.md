# CSIA PRIME: execution plan, from the repository's actual state

**2026-10-02. Written and committed before any PRIME track work.**

**Boundary:**
- **OFFBOARD;** SITL, HIL, flight-test and incident replay;
- **ZERO CONTROL authority;**
- **NO FORGE,** no automatic recovery, no onboard port.

**The baseline is locked:** `verify_prime_baseline.py` → `BASELINE_PRIME.json`,
`BASELINE_PRIME_LOCKED: true`, at HEAD 16e19d4. Unchanged and verified:
- Semantic Core 2.1.1 and frozen v2.0;
- XSYS-001 (55/55, lower bound 0.7616, hard gate PASS) and Phase C;
- every 2.2, pilot, 2.3 and RB-001 result and test file (51 + 22 + 33 + 10
  tests pass);
- 2.3's committed V1, V9 and V13 reports regenerate byte for byte.

## 1. What the repository and this environment actually provide

**The product exists.** `python -m csia_evidence_assurance analyze
flight.ulg` takes an ordinary PX4 log, with no onset, sidecar or research
input. It writes `report.json`, `report.txt` and `manifest.json`. A pilot
test pins that output set to exactly those three files, so any new
commercial output must come from a new subcommand, not from `analyze`.

**What the report already answers, of A1's list:**
- what happened, when, the subsystem;
- what remains, what was eliminated and why, what supports it;
- which monitors agreed and whether they were independent;
- what was not observable, and what would resolve the ambiguity.

**What it does not answer:**
- "what evidence was rejected, and why" is not in the summary;
- there is no per-conclusion receipt;
- there is no explicit coverage taxonomy (A4);
- there is no support check: on the real FMUv5 boat log below, the
  product accepted the multirotor-quad profile for a boat and did not say
  the vehicle is unsupported.

**Real data reachable from here** (priority 1; the full search is in
`REAL_DATA_ACQUISITION.md`, written in Track B):

| source | real? | what it is | useful for |
|---|---|---|---|
| pyulog test logs (RB-001) | 4 real boards, 2 SITL | no propulsion event, little or no flight | timing, rest noise, schema variety |
| PX4 docs asset in the PX4-Autopilot checkout (`sample_log_boat_testing_2022-7-28`) | **real** FMUv5, PX4 about 1.13, a boat (airframe 50005), 496 s, armed 59 % | `actuator_motors`, allocator status, battery, 3 IMUs; no `esc_status` | real timing; real PX4 warnings; an unsupported-vehicle test |
| RflyMAD descriptor (`lerlis/data_processing_tools`) | describes 497 real flights | which topics the real ULogs carry: `esc_status` with RPM and current, battery current, `actuator_controls_0`; **no `actuator_motors`, allocator status or torque setpoint** | the support matrix; the data request to the owner |
| two RflyMAD real ROS bags (same repository) | real | MAVROS topics only (IMU, RC out, battery); no ESC | not ingestible by the product |
| Flight Review, Zenodo, Figshare, Hugging Face, the RflyMAD site | — | **refused by the network policy** | — |
| hardware | — | no USB bus, no serial/I2C/SPI devices | — |

**So the real propulsion corpus is still empty.** That fixes the program's
shape: Tracks B and C can be designed, frozen and pre-analysed, but not
validated.

## 2. One design fact that changes the physical plan

**On an open-loop motor bench, the stock product has no independent
cross-system witness:**
- its physical-response evidence is the allocator compensation, which
  needs a closed loop;
- ESC current shares the ESC MCU with ESC RPM (one lineage);
- no stock producer turns bus current or thrust into per-motor evidence.

**So "CSIA separates A from B on a bench with stock producers alone" has
no physically independent witness:** stop condition 10, recorded now and
not tested.

**The route that keeps the architecture unchanged.** 2.2 already takes
external witness producers with their own contract and lineage. XSYS-001's
W_RPM, W_DYN and W_CTRL enter that way (`adapters/xsys_witness.py`). The
bench's load cell becomes such a producer: lineage root
`sensor:loadcell.0`, record `actuation.physical_response`. The
tachometer and the run sheet stay ground truth only.

**The adapter is specified now and built only when the first bench CSV
exists:** reality-first rule 5, a direct integration requirement. The
closed-loop alternative is RB5, a restrained vehicle, where the 2.3
compensation witness exists unchanged.

## 3. The plan, in the brief's priority order

| # | item | what runs here | what is gated | output |
|---|---|---|---|---|
| 1 | real propulsion logs / nominal data | the search above; the unchanged product on every real log reachable (no crash, coverage, timing, warnings) | the owner's logs, RflyMAD's real ULogs or bench data | `REAL_DATA_ACQUISITION.md`, `REAL_LOG_RESULTS.json` |
| 2 | matched physical A/B | **frozen protocol:** matching rule, decision rule, sample count, success and failure criteria; the load-cell producer's contract specified | hardware | `B4_MATCHED_AB_PROTOCOL.md` |
| 3 | real calibration + sim-to-real receipts | receipts from the new real log; the **reality stress envelope** (B2): each producer's tolerance to jitter, loss, rate, latency, quantization, noise, bias, motor variation and producer restart, by offline perturbation of base logs, against the real magnitudes measured in RB0 and on the boat log | real nominal corpus for the calibration itself | `STRESS_ENVELOPE.json/.md`, `SIM_TO_REAL_RECEIPTS.md` |
| 4 | B3 physical/HIL validation | **model-sensitivity analysis** on the development and calibration flights only (gyro bias, latency, inertia/effectiveness mismatch, motor asymmetry, mass/thrust offset, vibration noise); the physical acceptance test frozen | RB5 or HIL hardware | `B3_CHALLENGE.md` |
| 5 | event discovery cleanup | comparison of established triggers (below) on existing data; the alert-burden target; persistent-warning grouping justified by the real boat log | the real nominal corpus, for any threshold that is to ship | `EVENT_DISCOVERY_STUDY.md` |
| 6 | commercial report / support matrix | `assure` subcommand: summary, receipts, coverage states, support check; machine-readable support matrix; ten sample reports | — | Track A outputs |
| 7 | external-engineer pilot package | package, task-test protocol, pilot definition, value metrics | a real engineer | Track E outputs |
| 8 | defensibility/IP | function matrix against established categories, the narrowest defensible claim, IP screen, demo design; built on the repository's earlier prior-art packages | — | Track D outputs |

**No new SITL flights.** Every SITL analysis uses flights already flown
(2.3 V1-V13; RB-001 CAL, EN, EF, EH, ET; XSYS-001). New flights would
substitute simulation for the missing reality, which the brief forbids.

## 4. Data separation for the analyses that choose anything

| analysis | chooses on | evaluated on | never touched |
|---|---|---|---|
| B3 sensitivity | nothing (a sensitivity sweep, no threshold changes) | development V1-V13 and calibration CAL1-CAL5 | RB-001 evaluation flights |
| event discovery | calibration: CAL1-CAL5 nominal; development: V1-V13 | RB-001 EN/EF/EH/ET, once, after a committed preregistration; the 121 XSYS-001 blind-replay cases as a recall check | — |
| stress envelope | nothing chosen; tolerance measured | V4, V12, V10 (faults) and V5, V11 (nominal) | — |

**Disclosure:** the RB-001 evaluation flights were scored before, for a
different question (maneuver-aware evidence at the product's events). No
event-discovery choice was made on them. Their product event counts (339
per hour) are known; that is the baseline being compared against, not a
target being tuned to.

## 5. Track A product changes, and why each is allowed

**The reality-first rule** allows code only for a measured physical
failure, a measured usability gap, a required commercial workflow,
reproducibility, or a direct integration requirement.

| change | rule | measured by |
|---|---|---|
| `assure` subcommand: the A1 summary, A3 receipts, A4 coverage states | required commercial workflow; usability gap (rejected evidence and receipts absent from the summary) | the A1 checklist against the current report (section 1) |
| support check (vehicle type, PX4 version, required topics, logging rates) | **measured usability gap on real data:** a boat accepted as a quadrotor | the FMUv5 boat log |
| alert grouping of re-raised identical PX4 warnings (view only; event discovery unchanged) | **measured on real data:** one persistent low-battery condition became 9 separate events | the FMUv5 boat log |
| `csia-assure` console script | required commercial workflow (installable one-command analyzer) | — |

**Every historical output stays byte-identical:**
- `analyze` and the schema-4 report are unchanged;
- the new outputs are written only by `assure`;
- the regression tests pin both.

## 6. Gates (defined now; evaluated in the final review)

| gate | requires (all of) |
|---|---|
| PRIME-A `COMMERCIAL_MVP_USABLE` | ordinary supported ULog; no research sidecars; the A1 summary first; coverage explicit (A4, tested); deterministic (two runs, identical bytes); no crash on every schema reachable; installable in a fresh environment |
| PRIME-B `REAL_EVIDENCE_CALIBRATED` | a real nominal propulsion corpus; real timing and noise measured; hardware thresholds calibrated prospectively; no simulator threshold reused |
| PRIME-C `MATCHED_PHYSICAL_SEPARABILITY_SUPPORTED` | physical A and B cases; matched local symptom; independent ground truth; no wrong UNIQUE; dependency accounting; prospective scoring |
| PRIME-D `MANEUVER_EVIDENCE_SUPPORTED` | real or HIL maneuvering; true degradation detected; nominal maneuvering clean; no wrong motor; B3 (or a replacement) validated outside its development model |
| PRIME-E `EXTERNAL_PILOT_READY` | installable analyzer; support matrix; sample data; quick start; external test protocol; claim/evidence matrix |

**Expected from the facts above:**
- PRIME-B, C and D cannot be met without real propulsion data;
- PRIME-A and PRIME-E are within reach.

The final token is chosen from what is measured, not from this
expectation.

## 7. Stop conditions, watched throughout

All ten of the brief's conditions apply. Two are already live:
- **condition 10** (section 2): no physically independent witness exists for
  "stock producers alone separate A from B on a bench";
- **condition 9**, to be tested in Track D: whether the product answers more
  than the underlying monitor already says.

Any Semantic Core 2.1.1 or 2.2 failure on real evidence is reproduced and
reported, not patched from the product layer.
