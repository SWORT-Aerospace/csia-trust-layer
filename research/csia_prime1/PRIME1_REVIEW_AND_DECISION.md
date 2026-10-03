# PRIME-1 review and decision (Phase 40)

**2026-10-03. Boundary:**
- **OFFBOARD:** after the flight, on logs;
- **ZERO CONTROL authority:** it commands nothing, recovers nothing;
- **NO FORGE;** no onboard component and no H743 port (Phases 35-36);
- no flight-safety approval.

**Decision:** **`CSIA_PRIME1_READY_FOR_EXTERNAL_PILOT`**.

**PHYSICAL VALIDATION REMAINS OPEN.** This is the brief's stated endpoint when
real data is unavailable: EXTERNAL PILOT READY + PHYSICAL VALIDATION OPEN.

## 1. Gates

| gate | requirement | evidence | status |
|---|---|---|---|
| P1 KNOWN_DEFECTS_CLOSED | D-PRIME-1 and D-PRIME-2 fixed in a versioned successor; history unchanged; any defect found on the way fixed or recorded | prime1: neither reproduces; release 2.3: both still reproduce exactly as recorded (`FINAL_STATE_PRIME1.json`); `HISTORICAL_GATE.json` unchanged; D-PRIME-3 (the wheel could not analyse a log) found and fixed (`FRESH_INSTALL_PRIME1.json`) | **MET** |
| P2 EVENT_DISCOVERY_COMMERCIALLY_USABLE | the successor front end promoted by a frozen, prospective, held-out comparison | `HELDOUT_RESULTS.json`: PROMOTE, S1-S6 all hold. **EVENT DISCOVERY PROMOTION IS SIMULATION-ONLY** | **MET (simulation only)** |
| P3 EXTERNAL_PILOT_PACKAGE_READY | a blinded bundle with zero known ground-truth leaks, an installable wheel, participant and experimenter documents, an offer, an intake, a protocol, metrics | `PILOT_BUNDLE_PRIME1.json`, `BLINDNESS_AUDIT.json` (ZERO KNOWN GROUND-TRUTH LEAKS), `FRESH_INSTALL_PRIME1.json` (the bundle's own wheel), `PILOT_OFFER.md`, `PILOT_INTAKE_AND_PROTOCOL.md`, `PILOT_METRICS.md` | **MET** |
| P4 REAL_DATA_READY | a real log can be received, analysed blind, sealed and revealed without code | `REAL_DATA_READY_CHECK.json`: all checks pass on 7 real logs | **MET** (for processing; not for correctness: see question 20) |
| P5 PHYSICAL_VALIDATION | a diagnostic conclusion checked against physical truth | no physical propulsion evidence exists; nothing is PHYSICAL_VALIDATED | **NOT MET** |

**Why this token and not CSIA_PRIME1_READY_BUT_BLOCKED_ON_REAL_DATA.**
Nothing in the pilot waits for data SWORT must produce. A blind pilot on a
customer's own logs is exactly how real data arrives, and the whole chain
needed to run one is measured working:
- the offer;
- the intake;
- the engagement workflow;
- the installed wheel;
- the sealed protocol.

What real data blocks is **P5**, and P5 is not a pilot prerequisite: every
document says "validated in PX4 simulation only".

**Why not the other tokens:**
- **CSIA_PRIME1_DEFECT_FIX_FAILED:** both fixes hold and history is unchanged;
- **CSIA_PRIME1_EVENT_DISCOVERY_NOT_READY:** the held-out comparison
  promoted, in simulation;
- **CSIA_PRIME1_REQUIRES_SEMANTIC_REVIEW:** Semantic Core 2.1.1 is untouched.
  The new event semantics are named and tested;
- **CSIA_PRIME1_REQUIRES_ARCHITECTURE_REVISION:** every change is additive and
  versioned.

## 2. Stop conditions honoured

- **No historical result changed.** Release 2.3, its reports, XSYS (3,872
  slots, 55/55, LB 0.7616), Phase C, PRIME's results and sample reports, and
  the sealed manifests reproduce (`FINAL_STATE_PRIME1.json`).
- **The failure ledger is unchanged** (pinned SHA). Five drafts (FL-053 to
  FL-057) wait in `FAILURE_LEDGER_DRAFTS.yaml` for the owner.
- **No simulation was substituted for physical evidence.** The held-out SITL
  flights decide only the event front end, and say so.
- **D-PRIME-2 is not an absolute value.** Two named one-sided statistics; a
  permanent test pins it.

## 3. The twenty-one answers

**1. Were the two defects fixed?** Yes, in release `prime1` only.
- **D-PRIME-1:** a canonical integer-microsecond timebase and integer-tick
  comparisons in the gate. Shifts of 0.3, 0.4999, 0.5, 0.5001, 0.7, 1 and
  2.7 us now keep the conclusion; nanosecond and coarser producers are
  compared at their declared resolution.
- **D-PRIME-2:** separate RPM_DEFICIT and RPM_EXCESS arms, plus a telemetry
  baseline-validity condition: a corrupted reference is never read as
  NOMINAL.

**2. Did any historical result change?** No. Release 2.3 is the default of
every historical entry point and reproduces byte for byte (the manifest's
code digest aside, documented).

**3. Do shortfall and excess each open an event without simulation
messages?** Yes, as RPM_DEFICIT_EVENT and RPM_EXCESS_EVENT. Removing PX4's
injection messages and SIH parameters changes nothing (a permanent test;
S6 on all 14 held-out flights).

**4. Which telemetry classes are supported?**
- **Discovered and reported:** shortfall, excess, ESC offline.
- **Refused, never read as a fault:** dropout.
- **Blind spots, stated:** stuck value in steady flight, static offset,
  slow drift.
- **Simulation only, offline corruption:** matched discrimination.

**5. Which method was selected?** Separate one-sided CUSUM arms on the 2.3
telemetry statistic with a reference-consistency band, plus a compensation
CUSUM gated by steadiness and heading, and PX4's monitors with an
identical-condition merge. Model-based residual methods were rejected for the
product: they need a per-vehicle identified model a customer log does not
bring.

**6. Was the comparison prospective?** Yes. Code and criteria were frozen
(22 file hashes) and committed before the 14 held-out flights were flown;
the evaluation refuses to run twice or on changed code.

**7. What is the false event rate?** 3.35 per nominal in-flight hour (1
event in 0.298 h: PX4's own magnetometer-timeout error at a real
reconfiguration; 0 propulsion events), against 308.4 for release 2.3. The
same under timestamp jitter. **In PX4 simulation only.**

**8. What is the false symptom rate?** 0 in 0.509 flight hours (14 flights),
and 0 under jitter.

**9. What is the wrong-attribution rate?** 0 (no wrong motor, no wrong
UNIQUE) in 0.509 flight hours.

**10. What is the recall?** 6 of 6 held-out faults found at onset (median
error 0.010 s): 4 losses, 1 RPM excess, 1 ESC offline. Release 2.3 found 5
and missed the excess. Losses in hover and hold were confirmed on the right
motor; losses mid-maneuver were found but, by design, not confirmed.

**11. Are unsupported vehicles blocked?** Yes. UNSUPPORTED_VEHICLE_CONFIGURATION
is decided before interpretation. The page states the detected type, the
requested profile and the supported classes, and gives only a generic
analysis: version, integrity, PX4's warnings. Shown on a real boat and a real
VTOL.

**12. How many schemas and configurations?** 5 support states; 8
configurations in the contract:
- 1 SUPPORTED (quad X with allocation and ESC RPM, SIMULATION);
- 2 PARTIAL;
- 4 UNSUPPORTED_VEHICLE_CONFIGURATION;
- 1 UNSUPPORTED_SCHEMA.

Full analysis is tested on one PX4 version (547e2ca). Others are PARTIAL or
UNKNOWN_VERSION.

**13. Does a fresh install work?** Yes, the exact wheel in the bundle:
- a new environment;
- `csia-assure` outside the repository;
- outputs byte-identical to the repository's on 8 logs;
- nothing imported from the repository.

It did not before PRIME-1 (D-PRIME-3).

**14. Does every conclusion have a receipt?** Yes, with all fifteen Phase 16
fields, in deterministic JSON.

**15. Is the bundle blind?** Yes: ZERO KNOWN GROUND-TRUTH LEAKS after three
audit runs, the first two kept on record.
- **Fixed:** the injection parameter's firmware-default records and the
  harness's in-flight parameter changes.
- **Unchanged by blinding:** all 12 logs keep their conclusions.

**16. Can a real log be handled tomorrow without coding?** Yes: `csia-assure
engagement init / ingest / run / seal / reveal / verify`, measured on 7 real
logs.

**17. What exactly is the product?** `csia-assure`:
- wheel `csia_trust_layer-0.8.0`;
- release prime1, analyzer 2.2.1, Semantic Core 2.1.1;
- profile multirotor-quad r1, view prime1-view-2, support contract
  prime1-r1;
- sold as a services-assisted pilot with a locally run Analyzer
  (`PILOT_OFFER.md`). Not SaaS, not onboard.

**18. Which claims are simulation-only?** Every diagnostic and
event-discovery claim. These are rows M-T1 to M-T7, M-S1, M-S4 and M-E1 of
`CLAIM_EVIDENCE_MATRIX_PRIME1.md`.

**19. Which claims are website-ready?** The eight SUPPORTED NOW sentences and
the six SIMULATION ONLY sentences of `PUBLIC_CLAIMS.md`, quoted exactly with
"in PX4 simulation". Nothing else.

**20. Is physical validation still needed?** Yes, for every diagnostic
claim. The first steps are:
- **real nominal flights of a customer's vehicle:** they set its thresholds
  and measure real false observations;
- **real propulsion events with independent truth:** a pilot customer's
  diagnosed incidents, or the bench A/B already designed.

**21. What is the highest-value pilot?** A blind engagement with one PX4
quad-X flight-test team that logs `actuator_motors` and ESC RPM
(bidirectional DShot or telemetry ESCs). The team provides:
- 10 to 20 logs with at least one propulsion or ESC-telemetry event it has
  already diagnosed, its diagnosis sealed;
- 5 or more nominal flights of the same vehicle.

The pilot tests the one unproven step: whether the separation of physical
from telemetry evidence survives real data.

## 4. Regression

Full suite at commit 343389a: **4,759 passed, 41 skipped, 2 expected
failures, 1 failure.**
- **The one failure** was the build-provenance check, which by design fails
  until the record is refreshed for a new checkout. It was refreshed
  (`research/physical_validation/results/BUILD_PROVENANCE.json`) in the
  commit that carries this section.
- **The 2 expected failures** are PRIME's strict pins of D-PRIME-1 and
  D-PRIME-2 on the historical release 2.3, which keeps both defects by the
  owner's decision.
- **No PRIME-1 test is an expected failure.** The fixed behaviour is pinned
  by ordinary tests on the successor path: 65 in `tests/test_csia_prime1.py`
  and 8 in `tests/test_csia_prime1_docs.py`.
- **The 41 skips** are the suite's environment-dependent tests (for
  example the `sitl` marker for a live simulator binary). PRIME-1 adds no
  skipped test.

## 5. What PRIME-1 did not do (on purpose)

- **No new research architecture.** Semantic Core 2.1.1 unchanged.
- **No onboard port, no FORGE.**
- **No pricing figure and no ROI.** Pricing is a COMMERCIAL HYPOTHESIS NOT
  YET MARKET-VALIDATED.
- **No ledger edit.**
- **No physical claim.**
