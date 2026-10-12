# CSIA PRIME: final review and decision

**2026-10-03.** OFFBOARD. ZERO CONTROL authority. NO FORGE. No new
architecture (no 2.4, 3.0, ZETH, new detector, estimator, allocator or
runtime assurance). Every frozen and sealed result is unchanged
(`FINAL_STATE_PRIME.json`).

## 1. The decision

**`CSIA_PRIME_BLOCKED_ON_REAL_DATA`**

**Why this token, from what was measured:**
- **Priorities 1-4 are blocked by access, not by results:**
  - real propulsion logs: none reachable. The environment's network policy
    refuses logs.px4.io, Zenodo, Figshare, Hugging Face and
    rfly-openha.github.io, and no user logs were supplied;
  - the physical A/B: no hardware, no USB bus, no serial device;
  - real calibration: no real nominal propulsion corpus;
  - B3 on HIL or hardware: no HIL.
- **Without them, PRIME-B, PRIME-C and PRIME-D cannot be evaluated.** The
  program's central question, whether CSIA's evidence relationships survive
  real hardware, has no answer yet.

**Why not the other tokens:**
- **`CSIA_PRIME_REALITY_GAP_FOUND`:** real data did expose gaps (RR-09 to
  RR-12), but at the edges: support boundary, warning flapping, topic
  rates, gyro bias at rest. **None tested a propulsion relationship.**
  D-PRIME-2 was exposed by removing a simulation artefact, not by physical
  data.
- **`CSIA_PRIME_COMMERCIAL_PILOT_READY`:** PRIME-A and PRIME-E are met, but
  choosing this token on software deliverables would reverse the brief's
  priority order. D-PRIME-2 is also open **on the real-log path**.
- **`CSIA_PRIME_PHYSICAL_EVIDENCE_SUPPORTED`:** there is no physical
  evidence.
- **`CSIA_PRIME_REQUIRES_ARCHITECTURE_REVISION`:** nothing measured calls
  for it. Both defects have local fixes in existing layers.

## 2. Gates

| gate | verdict | evidence |
|---|---|---|
| PRIME-A `COMMERCIAL_MVP_USABLE` | **MET** | `PRIME_A_GATE.json`: 39/39 logs without a crash; deterministic; installs fresh; A1 first page tested. Caveat: one report class is unclear (D-PRIME-2) |
| PRIME-B `REAL_EVIDENCE_CALIBRATED` | **NOT MET: blocked on data** | no real nominal propulsion corpus; real timing measured on one boat log only (`SIM_TO_REAL_RECEIPTS.md`) |
| PRIME-C `MATCHED_PHYSICAL_SEPARABILITY_SUPPORTED` | **NOT MET: blocked on hardware** | protocol and decision rule frozen (`B4_MATCHED_AB_PROTOCOL.md`, `ab_scoring.py`); nothing run |
| PRIME-D `MANEUVER_EVIDENCE_SUPPORTED` | **NOT MET: blocked on HIL/hardware** | B3 challenged in SITL only (`B3_CHALLENGE.md`): predicted REQUIRES_VALIDITY_CONDITION |
| PRIME-E `EXTERNAL_PILOT_READY` | **MET as defined** | installable wheel; support matrix; 12 blinded sample logs; quick start; protocol and frozen rubric; `CLAIM_EVIDENCE_MATRIX.md`. **Not run with anyone.** Distribution is an owner decision |

## 3. Stop conditions

| # | condition | status |
|---|---|---|
| 1 | 2.1.1 semantic failure on real evidence | not triggered; no real propulsion evidence to test |
| 2 | 2.2 admits invalid / rejects valid evidence | **TRIGGERED TWICE, reported, not patched:**<br>• **D-PRIME-1:** valid evidence rejected when time is off the microsecond grid; not on the ULog path<br>• **D-PRIME-2:** a late event's telemetry comparison admitted although its BEFORE window is already corrupted; an RPM excess never discovered; **on the real-log path** |
| 3 | physical tests contradict an assumption | untestable: no physical tests |
| 4 | B3 wrong motor on hardware | untestable. In SITL B3 named a wrong motor only under heavy angular-acceleration noise (2 states at 10 rad/s², 3 at 20) |
| 5 | lineage disagrees with hardware | **predicted, not yet testable:** lineage roots at topic channels; the A/B protocol's S4 expects a failure until a wiring map exists |
| 6 | a fix alters sealed history | respected: nothing sealed changed; both defects left unpatched partly for this reason |
| 7 | a result tuned on its evaluation | respected: the event-discovery evaluation ran once after a committed preregistration; the stress envelope tuned nothing |
| 8 | already solved by established methods | applied: every CSIA function exists in established practice (D1); the candidate claim was narrowed (D2); event discovery compared only mature methods (C3) |
| 9 | the product says no more than the monitor | **not triggered in SITL; partly triggered for one fault class.** The demo: the RPM monitor reads the same in A and B, while CSIA separates them. For a telemetry **excess** the product says *less* than the raw ESC signal shows (D-PRIME-2) |
| 10 | no physically independent witness | **triggered for the stock-only bench claim** (the open-loop bench has no stock physical response). Routed through a 2.2 external witness (a load cell) in the A/B protocol |

## 4. The twenty questions

**1. What can CSIA do today that individual monitors cannot?** In PX4
simulation, and as software behaviour:
- **it decides what the monitors' outputs jointly justify.** In the demo
  pair, an RPM-versus-command monitor reads a 0.40 deficit in both A
  (motor loss) and B (RPM report corrupted). CSIA:
  - confirms A: the compensation is VIOLATED 0.663;
  - keeps B as an UNCONFIRMED observation: the compensation is NOMINAL
    0.0015;
- **it counts three agreeing monitors as two independent lines;**
- **it eliminates the sensor explanation, lists four remaining causes and
  names the measurement that would split them;**
- **it refuses evidence outside its validity** and says why
  (NOT_STEADY_FLIGHT);
- **it states coverage** (4 of 29 records observed in a stock log) and
  whether the log is inside the supported scope.

**No single PX4 monitor reports any of that.** Not demonstrated on real
hardware.

**2. What did physical data invalidate from simulation?** No physical
propulsion data exists. **Real non-propulsion data invalidated five
assumptions:**
- the vehicle is the profile's: RR-09, a real boat passed the profile gate;
- PX4 warnings are clean triggers: RR-10, a battery warning rose 32 times
  in 294 s;
- real logs carry allocation topics: RR-11, RflyMAD's 497 real flights are
  pre-allocation;
- rates are bias-free: RR-12, a real CubeOrange at rest carries
  0.067 rad/s, past the 0.05 edge;
- `failure_detector_status` runs at 10 Hz: RR-05, it runs at 2 Hz on a real
  FMUv5.

**Removing a simulation-only record also invalidated a test result's
basis:** 2.3 V10 relied on PX4's injection message (D-PRIME-2).

**3. Which producers transferred?** **None has been tested on a real
propulsion event.** On real logs:
- PX4-monitor triggers reported real conditions correctly (the boat: low
  battery, kill switch);
- the support check stated three real logs correctly;
- every producer ran without a crash on 6 real logs.

**4. Which required recalibration?** Predicted, not measured on propulsion:
- the compensation's steadiness gate needs a de-biased rate (RR-06/RR-12);
- the gap rule needs per-version topic rates (RR-05);
- the telemetry CUSUM's k and h, B3's noise floor and its model need real
  identification;
- alert grouping was needed and is applied in the view (RR-10).

**5. Which failed?**
- **on real data:**
  - the gap rule applied to `failure_detector_status` (481/481 windows
    refused; latent);
  - the profile gate's acceptance of a boat (now caught by the support
    check);
  - the raw event list (147 events per armed hour on the boat);
- **after removing a simulation artefact:** telemetry-excess discovery
  (D-PRIME-2);
- **under off-grid time:** the window anchor (D-PRIME-1).

**6. Does B3 survive physical/HIL testing?** **Untested.** In SITL it
tolerated:
- ±30 % model error;
- 100 ms latency;
- 20 % motor asymmetry.

It has a structural CG/payload confound: a false loss on every nominal
flight at a 0.01 roll-torque step. Its false edge is 5 rad/s² of
angular-acceleration noise, against 1.7-4.8 rad/s² measured on a real boat.
**Predicted class: REQUIRES_VALIDITY_CONDITION.**

**7. Can real physical degradation and telemetry corruption be
distinguished?** **Unknown on hardware.** In SITL, yes for deficits:
- 0 confusions in 1,056 perturbed runs;
- the demo pair.

**Telemetry excesses are not discovered at all** (D-PRIME-2). The physical
test is designed and frozen; it needs a bench with a load cell.

**8. What evidence is genuinely independent?** At sensor level:
- **the IMU-derived physical response** (compensation, rate transient);
- **the ESC's RPM report.**

They share the motor commands, so lineage counts them as two lines, not
three. The rate transient and the compensation share the IMU. On the bench
only a load cell (or an optical tachometer) is independent of the ESC.
**Lineage is at topic-channel level. Hardware-level independence is
unverified** (stop condition 5, predicted).

**9. What remains structurally ambiguous?**
- **within a propulsion loss:** drive without current, mechanical, command
  not delivered, power path (AMBIGUOUS among 4 in every stock hover loss);
- **losses during continuous maneuvering:** compensation invalid; B3
  confounded by CG shifts;
- **propeller damage** with unaffected RPM;
- **telemetry excess:** undiscovered.

**10. What instrumentation would remove that ambiguity?**
- ESC current (electrical response, stall);
- battery current (power path);
- command-delivery evidence (ESC command echo);
- an independent thrust or RPM witness;
- a recorded payload/CG state for maneuvering;
- `esc_status` logged with margin under the gap rule.

**11. How noisy is event discovery?**
- **the product's discovery (E0):** 310 false candidate events per nominal
  in-flight hour in SITL maneuvering; 5/7 losses found;
- **E2, E3 and E5:** 0 per hour with 7/7 found (SITL, preregistered).
  **Not in the product;**
- **real boat:** 12 events in 294 s armed; grouped into 4 real alerts;
- **one-sided:** the telemetry trigger misses excesses.

**12. How many false symptoms occurred?**
- **0 from the product in every PRIME run:** 1,056 stress runs, the
  event-discovery evaluation, 11 sample reports, 12 blinded bundle logs,
  the demo;
- **B3, outside the product:** 17-75 false VIOLATED under
  angular-acceleration noise of 5-20 rad/s², and 17-42 at CG steps
  (`B3_CHALLENGE.md`);
- **the permanent negative control** (the loosened gate) keeps its 163
  false motor-failure symptoms and 52 wrong-motor states as a regression.

**13. How many wrong UNIQUE conclusions occurred?** **0.** No UNIQUE was
produced at all in PRIME's runs. Hover losses end AMBIGUOUS.

**14. Can a normal engineer use the product?** **Not measured.** The E2
protocol and bundle are ready; no external engineer has used it. What was
measured:
- one command;
- no sidecars;
- a fresh install;
- under 5 s per log;
- a fixed-order first page of 34-58 lines.

Against that: D-PRIME-2 produces a page that reads "nothing adverse" while
a telemetry signal is ten times off.

**15. What is the narrowest product worth selling today?** See section 5:
- a **services-assisted Flight Assurance Pilot** (option D);
- for PX4 quad-X teams;
- SITL/HIL logs as the validated scope;
- flight-test logs as support screen and evidence-quality review, with the
  validation caveat stated.

**16. What exact public claims are supported?** The rows marked YES in
`CLAIM_EVIDENCE_MATRIX.md`, worded as there:
- product behaviour P1-P8;
- SITL diagnostic claims S1-S5, only with "in PX4 simulation".

**17. What claims remain simulation-only?**
- all diagnostic claims: motor attribution, motor vs telemetry, the stress
  envelope, event-discovery rates, B3, the demo;
- every threshold.

**18. What is potentially defensible IP versus established engineering?**
- **Every function is established** (`COMPETITOR_FUNCTION_MATRIX.md`). The
  brief's candidate claim is too broad.
- **Combination 1** (MNC-1) faces a HIGH prior-art concern (EPOS family).
- **Combination 2** (detectability-gated nominal) needs full-text review.
- **The defensible asset is know-how and validation:**
  - the PX4 validity rules and timing traps;
  - the receipts;
  - the support matrix;
  - a real-data corpus with truth, which does not exist yet.
- No patent drafted (`DEFENSIBILITY_AND_IP.md`).

**19. What should NOT be built next?**
- CSIA 2.4 or 3.0, FORGE, ZETH;
- a new detector, estimator, allocator or runtime assurance;
- more SITL campaigns as a substitute for reality;
- a SaaS dashboard before any external user result;
- any probability or confidence score;
- B3 in the product before hardware;
- an unversioned change to default event discovery;
- view-layer patches for D-PRIME-1/2;
- patent drafting;
- further novelty hunting.

**20. What single action has the highest expected commercial value next?**
**One services-assisted Flight Assurance Pilot with a PX4 multirotor team
that supplies real flight-test logs and holds back its own truth.** It is
at once:
- the first real propulsion data (priority 1);
- the first external-user evidence (PRIME-E's test);
- the first commercial signal.

`COMMERCIAL_PILOT.md` defines it. **Before it:**
- the owner decides on D-PRIME-2: fix it in a versioned discovery mode, or
  disclose it;
- the network policy admits logs.px4.io for a real nominal corpus
  (PRIME-B), which costs nothing.

## 5. Product boundary decision

**Chosen: D, a validation and engineering service with the Analyzer.**

**Its scope:**
- PX4 quad-X teams;
- SITL and HIL logs in the validated scope;
- flight-test and incident logs accepted for the support screen, coverage,
  evidence-quality and lineage review, under the stated real-hardware
  caveat.

| option | why not (or why) |
|---|---|
| A, self-service Analyzer | **no external user result;** real-hardware validity unknown; one open real-log defect. Self-service would carry claims N1/N2 implicitly |
| B, SITL/HIL Validator alone | **closest to what is validated, but no buyer evidence.** It is folded into D as the validated scope |
| C, incident replay / root cause | needs real-log diagnostic validity (N2), which does not exist |
| **D, service plus Analyzer** | **the narrowest offer that is honest today.** The service carries the caveats, the blind comparison against the customer's truth, and the instrumentation advice. Each pilot doubles as real-data acquisition |
| E, combination | ambition, not evidence |

## 6. What PRIME produced

| track | deliverables |
|---|---|
| baseline and plan | `BASELINE_PRIME.json`, `PRIME_EXECUTION_PLAN.md` |
| B: reality | `REAL_DATA_ACQUISITION.md`, `STRESS_ENVELOPE.md`, `SIM_TO_REAL_RECEIPTS.md`, `B4_MATCHED_AB_PROTOCOL.md`, `ab_scoring.py`, the draft load-cell contract, `DEFECT_D_PRIME_1.md` |
| C: maneuvering and events | `B3_CHALLENGE.md`, the permanent negative control (tests), `EVENT_DISCOVERY_PREREG.md`, `EVENT_DISCOVERY_STUDY.md` |
| A: commercial MVP | `csia-assure`, first page, receipts, coverage classes, support matrix; `TRACK_A_MVP.md`, `sample_reports/` |
| D: differentiation | `COMPETITOR_FUNCTION_MATRIX.md`, `DEFENSIBILITY_AND_IP.md`, `TECHNICAL_DEMO.md` |
| E: pilot readiness | `EXTERNAL_PILOT_PACKAGE.md`, `pilot_package/`, `pilot_package_experimenter/`, `build_pilot_bundle.py`, `PILOT_BUNDLE.json`, `COMMERCIAL_PILOT.md`, `DEFECT_D_PRIME_2.md` |
| claims | `CLAIM_EVIDENCE_MATRIX.md` |

## 7. Owner actions that unblock PRIME

1. **Network policy:** allow logs.px4.io (real nominal corpus) and
   zenodo.org / rfly-openha.github.io (RflyMAD's labelled real faults).
2. **Real ULogs:** any PX4 multirotor flight-test logs with ESC telemetry,
   with truth held back.
3. **Hardware:** authorise the bench (`B4_MATCHED_AB_PROTOCOL.md`), with a
   load cell.
4. **D-PRIME-1 and D-PRIME-2:** approve fixes as versioned changes, or keep
   them disclosed.
5. **The pilot bundle:** approve its distribution to named external
   engineers, and the recruitment for E2.
