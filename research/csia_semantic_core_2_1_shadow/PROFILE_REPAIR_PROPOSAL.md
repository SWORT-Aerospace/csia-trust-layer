# Profile repair proposal and decision

**2026-09-30. Parts 6 and 47 of the shadow-validation brief.**

**How this was produced.** Each candidate was written into
`profile_candidates.json`, with its justification and source, before it was
run. R5a and R5b were added after the first run, which found R5 unsafe; they
split R5 into its source half and its link half. The note inside the file
records this. The evidence behind each decision is in
`G1_COARSE_NAVIGATION_AUDIT.md`, `G2_ESTIMATOR_INPUT_AUDIT.md` and
`PROFILE_COUNTERFACTUAL_RESULTS.md`.

**Nothing here edits `csia/v2/profiles/aircraft.py`.** Accepted declarations
form a versioned successor profile, `aircraft_successor_r1.json`, which is
applied as an overlay:
- **What reads it.** Only 2.1 in shadow, and the frozen function graph when
  fed the overlaid records, as a measurement.
- **Its identity.** SHA-256 of the canonical JSON is `c7541cab…93bb0`
  (`ProfileOverlay.digest()`). The file's own bytes hash to `0279fe1c…2b68`.

## 1. The declarations

Graphs are written as `component --serves--> function` and
`component --depends_on--> component`.

### R2: state_estimator serves COARSE_NAVIGATION

**Graph change:**
- **Old:** `state_estimator --serves--> PRECISION_NAVIGATION, POSITION_HOLD, AUTONOMOUS_MISSION`.
- **New:** the same, plus `--serves--> COARSE_NAVIGATION`.

**Physical justification:** every position a PX4 navigation function
consumes is EKF2 output (PX4 `547e2ca`, cited in the G-1 audit §3). The
frozen table already names COMPUTE a supporting domain of COARSE_NAVIGATION,
so this brings a dead declaration to life.

**Affected scenarios:** estimator and CPU faults, namely PROCESS_STALL, MS_D2,
MS_A4, ESTIMATOR_LATE, CPU_OVERLOAD, MS_C4 and MS_D4.

**Affected 2.1 results:**
- Alone, R2 restores 0 units, because the timing channel's evidence is still
  out of scope.
- With R3 it takes 171 contradictions with the function graph away. The graph
  then calls COARSE_NAVIGATION DEGRADED, not ELIGIBLE, under an estimator
  fault.

**Risk of over-connecting:** low. The estimator is on the path of every
position. A platform with an estimator-independent coarse position would be
over-connected; this profile is for PX4 EKF2 vehicles only.

**Risk of under-connecting:** a stall removes the position rather than
degrading it, but the table models COMPUTE as supporting. So the graph says
DEGRADED where "unavailable" is closer. That is a function-table question,
recorded with G-3.

**Decision: ACCEPT.**

### R3: nav_solution serves COARSE_NAVIGATION

**Graph change:**
- **Old:** `nav_solution --serves--> PRECISION_NAVIGATION, POSITION_HOLD, AUTONOMOUS_MISSION`,
  with `depends_on state_estimator, cpu, gnss_serial`.
- **New:** the same, plus `--serves--> COARSE_NAVIGATION`.

**Physical justification:** the channel "carries the position", in the
comment at aircraft.py lines 263-268. TIMING is a declared supporting domain
of COARSE_NAVIGATION, and was dead.

**Affected scenarios:** timing and link faults, namely CLOCK_DRIFT, MS_A1,
MS_A2, MS_A3, MS_C3, MS_D3 and PACKET_LOSS. Through the closure it also
covers the estimator faults above.

**Affected 2.1 results:**
- **The 601 G-1 units are restored**: they again equal v2.0.
- 120 survivor sets shrink back to v2.0's.
- 0 new incorrect results and 0 new wrong UNIQUE.

**Risk of over-connecting:** the closure brings in state_estimator, cpu and
gnss_serial. All three are on COARSE_NAVIGATION's real path.

**Risk of under-connecting:** none measured.

**Decision: ACCEPT.**

### R1: gnss_serial serves COARSE_NAVIGATION

**Graph change:** `gnss_serial --serves--> COARSE_NAVIGATION` is added.

**Justification:** true as information flow, but it is **DERIVED**. The link
reaches COARSE_NAVIGATION only through the estimator, and R3's closure
already contains it.

**Affected 2.1 results:**
- R1 alone restores nothing and flags 42 units as possible regressions. Those
  are a partial-declaration effect: MS_A2's delay is visible only on
  nav_solution timing.
- On top of R2 and R3 it changes nothing.

**Risk of over-connecting:** it adds a COMMUNICATION record that
COARSE_NAVIGATION's table entry does not watch. The graph ignores it while
2.1's scope uses it. The validator reports this as
`PV3_UNWATCHED_DECLARATION`.

**Decision: REJECT**, as redundant and cross-layer inconsistent.

### R4: gnss_serial serves POSITION_HOLD, PRECISION_NAVIGATION, GEOFENCE_SUPPORT

**Graph change:** those three functions are added to gnss_serial's
`--serves-->` set.

**Justification:** DERIVED for the first two, already through nav_solution.
CONDITIONAL for GEOFENCE_SUPPORT: raw GNSS reaches it only under
`GF_SOURCE_GPS`.

**Affected 2.1 results:** none. It is inert for 2.1 and for the graph,
because COMMUNICATION is not watched by these functions.

**The underlying question (G-3).** The function table routes a GNSS link's
effect on navigation only through the SENSOR domain, via the GPS source's
own health record. In MS_C3 and MS_D3 the harness pairs a synthetic link
fault with a clean real v1.1 payload, so that record stays NOMINAL. The graph
says ELIGIBLE while 2.1 says POSITION_UNAVAILABLE. That is the entire
residual of 252 contradictions under successor r1.

**What would settle it.** Either a successor function table that makes
COMMUNICATION a required domain of the navigation functions, or a harness
whose v1.1 payload reflects the link fault. Neither is an overlay change.

**Decision: DEFER to the function-table decision.**

### R5: state_estimator depends on gnss_serial and source.gps

**Graph change:**
- **Old:** `state_estimator --depends_on--> cpu, source.imu0`.
- **New:** `... , gnss_serial, source.gps`.

**Justification:** DIRECT as information flow. EKF2 fuses GNSS.

**Affected 2.1 results:** restores all 204 G-2 units, including 81 UNIQUE.

**Risk of over-connecting: realised.**
- FUNCTION_LINKS_NOMINAL now refutes COMMUNICATION/input_starvation for
  OUTPUT_MISSING using the GNSS link.
- On PX4 the GNSS link cannot starve EKF2's output, which is paced by the
  IMU.
- In the IMU pacing-loss counterfactual this yields a wrong SUPPORTED
  process_stall, exactly v2.0's error (G-2 audit §4).

**Decision: REJECT.** It restores historical certainty through evidence
unrelated to the excluded hypothesis.

### R5a: state_estimator depends on source.gps

**Graph change:** `source.gps` is added to the estimator's `depends_on`.

**Justification:** DIRECT.

**Affected 2.1 results:** the same as R5, and the same wrong answer in the
counterfactual.
- The GPS source's own declared dependency on gnss_serial carries the link
  into the estimator's scope through the closure.
- The defect is in the starvation predicate's scope (G-2 audit §5), not in
  this declaration.

**Decision: DEFER** until the starvation predicate reads pacing inputs rather
than the closure. After that it should be accepted.

### R5b: state_estimator depends on gnss_serial

**Graph change:** `gnss_serial` is added to the estimator's `depends_on`.

**Justification:** a real transport path for the measurement, but **NOT
ACTUALLY VALID** as an input whose loss starves the estimator's output.

**Affected 2.1 results:** as R5.

**Decision: REJECT.**

### R6: state_estimator depends on imu1, baro, mag

**Graph change:** those three sources are added to the estimator's
`depends_on`.

**Justification:**
- Baro and mag: DIRECT, but no signature hypothesis reads them for the
  estimator.
- imu1: CONDITIONAL on the multi-IMU / multi-EKF configuration and on
  failover.

**Affected 2.1 results:** none (inert).

**Risk of over-connecting:** a static imu1 dependency is wrong in one of the
two configurations. That is the stale-configuration case in
`CONFIGURATION_TRANSITION_STUDY.md`.

**Decision: DEFER** to the configuration-epoch work.

### R-BAD: esc_can serves the navigation functions

**Graph change:** `esc_can --serves--> COARSE_NAVIGATION, POSITION_HOLD, PRECISION_NAVIGATION`.

**Justification:** NOT ACTUALLY VALID. The ESC CAN bus carries motor
telemetry and commands.

**Affected 2.1 results:**
- It restores 931 units to v2.0, including **126 false navigation symptoms
  in MS_B1** that 2.1 had correctly removed. CORRECTNESS_FIX falls from 273
  to 147.
- It raises 126 unit-ticks of symptoms on unaffected functions (see the
  adversarial result M2).

**Decision: REJECT.** It is the demonstration of what an unacceptable repair
looks like.

## 2. Acceptance conditions for R2 and R3 (Part 47)

| condition | R2 | R3 |
|---|---|---|
| physical / information justification | PX4 EKF2 feeds every position consumer (V4) | the channel carries the position (aircraft.py comment, V4) |
| repository or upstream support | aircraft.py lines 83-90 (COMPUTE supporting); PX4 `547e2ca` | aircraft.py lines 83-90 (TIMING supporting), 258-270 |
| no restoration of a known wrong UNIQUE | MS_B5 and MS_TS_B5: 0 wrong UNIQUE ticks under r1 (`WRONG_UNIQUE_REGRESSION.md`) | same |
| no XSYS-001 regression | XSYS-001 does not use the aircraft profile; dataset B is unchanged by construction (3,872 slots, 0 differences) | same |
| no Phase C headline regression | verdict and every qualifying answer identical; D stays non-qualifying, and its reason reverts to v2.0's ("two members reduced to the SAME hypothesis") | same |
| a regression test | `tests/test_semantic_core_2_1_shadow.py` | same |

## 3. What the successor profile is and is not

**What it is:** a list of **additional** declarations, each carrying a kind,
a justification and a source, with a digest.

**What it is not:**
- not applied to any historical run;
- not read by the authoritative v2.0 path;
- not a change to the frozen function table.

**How it is versioned.** It is r1, and it is never edited: a later decision
(R5a after the predicate change, R4 after the function-table decision) makes
r2.
