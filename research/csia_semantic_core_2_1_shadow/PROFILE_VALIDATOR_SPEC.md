# Static profile validator, and the adversarial profile tests behind it

**2026-09-30. Parts 23, 24, 39 and 40 of the shadow-validation brief.**
- **Code:** `csia_semantic_core/profile_validator.py`.
- **Tests:** one failing profile per rule, in
  `tests/test_semantic_core_2_1_shadow.py`.
- **Mutation results:** `ADVERSARIAL_PROFILE_RESULTS.json`, written by
  `adversarial_profiles.py`.

## 1. The principle

**CSIA cannot reason more correctly than the dependency model it is given.**
G-1 and G-2 showed the frozen profile to be part of the assurance chain:
- 601 of 2.1's weakened units were decided by one missing tuple entry;
- the only unsafe repair candidate was physically true, but interacted with a
  predicate's scope.

A profile is therefore an assurance input. It needs an identity and a
validation status, like any other input. Section 5 lists the minimum.

## 2. How 2.1 and v2.0 react to profile mistakes

**Method.** Each mutation rewrites profile declarations on every tick of the
30 aircraft scenarios in dataset A (1,800 ticks). Each reasoner is compared
with itself on the unmutated records.

**Columns:**
- **overconfident:** a graded unit becomes wrong, or a wrong UNIQUE appears;
- **underconfident:** a correct SUPPORTED or UNIQUE is lost, or a real
  symptom is no longer raised;
- **spurious:** a symptom is raised on an unaffected function.

| mutation (Part 23 class) | v2.0: changed / over / under / spurious | 2.1: changed / over / under / spurious | fails safely? | validator |
|---|---|---|---|---|
| M1 missing edge: nav_solution no longer depends on the estimator | 265 / 0 / 226 / 0 | 265 / 0 / 226 / 0 | yes, both, but it goes unnoticed | **not detected** |
| M1b missing serving edge: nothing declares it serves PRECISION_NAVIGATION | 0 / 0 / 0 / 0 | 601 / 0 / 601 / 0 | 2.1: yes, underconfident, with `scope_gaps` in the trace | **PV1** |
| M2 extra irrelevant edge: the ESC CAN bus serves navigation (R-BAD) | 0 / 0 / 0 / 0 | 204 / 0 / 0 / **126** | 2.1: no. It raises false navigation symptoms, as v2.0 always did | **PV3** |
| M2b extra irrelevant edge: the telemetry link serves navigation | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | not exercised: the link is never adverse there | **PV3** |
| M3 wrong subject: a misspelled function name | 0 / 0 / 0 / 0 | 601 / 0 / 601 / 0 | 2.1: yes, underconfident | **PV7** |
| M4 wrong domain in a dependency (SENSOR/cpu) | 0 / 0 / 0 / 0 | 3 / 0 / 3 / 0 | yes | **PV5** |
| M4b wrong domain on a record (the GNSS link labelled SENSOR) | 276 / **81** / 123 / 0 | 366 / 0 / 213 / 0 | **v2.0: no, 81 overconfident.** 2.1: yes | **PV5** |
| M5 duplicate relation, identical | 313 / 0 / 0 / 0 | **0** / 0 / 0 / 0 | 2.1 is idempotent (C6) | none needed |
| M5b duplicate relation, conflicting declarations | 313 / 0 / 0 / 0 | 313 / 0 / 0 / 0 | yes | **PV8** |
| M6 cycle: the CPU depends on the estimator | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | yes: the scope closure and the alternative walk visit each node once | **PV6** |

Neither reasoner crashed on any mutation.

**Reading the table.**
- **2.1 is more sensitive to profile errors than v2.0.** It reads the declared
  model where v2.0 read the whole tick. Its errors are, however, mostly
  **underconfident**: its answers get weaker, not wrong.
- **The exception is over-connection (M2).** It makes 2.1 raise the false
  symptoms v2.0 raised anyway.
- **v2.0 was overconfident on one mutation (M4b), 2.1 on none.**
- **One mutation is invisible to both reasoners and to any static check.**
  Removing a true edge (M1) leaves a self-consistent graph. Catching it would
  need a cross-check against the platform's real data flow, for example the
  PX4 uORB publish/subscribe graph. That is recorded as a later item, not
  built.

## 3. The rules

Each rule is implemented because an observed failure motivates it.

| rule | severity | the failure it catches, and where that failure was seen |
|---|---|---|
| PV1 SUBJECT_WITHOUT_SERVING_COMPONENT | GAP | a function that a scoped symptom can name, which nothing is declared to serve. **Real:** COARSE_NAVIGATION in the frozen aircraft profile (G-1). **Mutation:** M1b |
| PV2 DEAD_SUPPORTING_DOMAIN | WARNING | a supporting or optional domain no record of that domain names, so the declaration can never act. **Real:** COARSE_NAVIGATION's COMPUTE and TIMING (G-1); also GEOFENCE_SUPPORT, PROPULSION and TELEMETRY's COMPUTE (aircraft), and CONDITION_MONITORING's TIMING (pump station) |
| PV3 UNWATCHED_DECLARATION | WARNING | a record naming a function whose table entry does not watch that record's domain: the function graph ignores it, while 2.1's scope may use it (a cross-layer inconsistency). **Real:** the ESC CAN link names PROPULSION, which does not watch COMMUNICATION (aircraft); rails name DATA_LOGGING and SPEED_MEASUREMENT (test stand) and CONDITION_MONITORING (pump station). **Mutations:** M2 and M2b; candidates R1 and R4 |
| PV4 DANGLING_DEPENDENCY | ERROR | a dependency on a component no record describes. No real case; the test's mutation adds `COMPUTE/ghost`. Kept because it stops closure-based scope silently dropping the edge |
| PV5 DEPENDENCY_DOMAIN_MISMATCH | ERROR | a dependency naming a real component under the wrong domain. **Mutations:** M4, and M4b, the one on which v2.0 became overconfident |
| PV6 DEPENDENCY_CYCLE | ERROR | common-cause reasoning presumes an acyclic depends-on graph. M6 is harmless in this data, but a cycle makes "ancestor" meaningless. Kept as ERROR because the cost of a false positive is only that a profile is refused |
| PV7 UNKNOWN_FUNCTION | ERROR | a misspelled function. **Mutation:** M3, 601 units silently weakened |
| PV8 INCONSISTENT_COMPONENT_DEPENDENCIES | ERROR | records of one component declaring different dependency sets, so scope depends on which record is read. **Mutation:** M5b |

**Checks from the brief deliberately not implemented:**
- **"Component serving no function" and "orphan component".** Many legitimate
  records name no function (source health, integrity), so the check would
  flag correct profiles. No failure motivated it.
- **"Duplicate relation".** Identical duplicates are harmless under C6 (M5),
  and conflicting ones are caught by PV8 or at runtime as a C6 conflict.
- **"Signature references undeclared relation".** Already enforced by 2.1's
  `validate_table`, which raises before any tick.
- **"Unreachable hypothesis".** No static failure was observed. A related,
  real problem is platform-conditioned isolability: MS_B4 and MS_B5 are
  identical on the multirotor, because nothing observes the shaft. That is a
  property of the evidence available, not of the profile's structure, and is
  recorded as loophole L15.

## 4. Findings on the shipped profiles

| profile | ERROR | WARNING | GAP |
|---|---|---|---|
| aircraft (frozen) | 0 | PV2 ×5 (COARSE_NAVIGATION:COMPUTE, COARSE_NAVIGATION:TIMING, GEOFENCE_SUPPORT:COMPUTE, PROPULSION:COMPUTE, TELEMETRY:COMPUTE); PV3 ×1 (esc_can → PROPULSION) | PV1 ×1 (COARSE_NAVIGATION) |
| aircraft + successor r1 | 0 | PV2 ×3 (GEOFENCE_SUPPORT, PROPULSION, TELEMETRY); PV3 ×1 | 0 |
| test stand | 0 | PV3 ×4 (dc_supply and rail_5v → DATA_LOGGING and SPEED_MEASUREMENT) | 0 |
| pump station | 0 | PV2 ×1 (CONDITION_MONITORING:TIMING); PV3 ×2 (mains_dc and rail_24v → CONDITION_MONITORING) | 0 |

**The remaining warnings are owner questions about the frozen function
tables.** For example:
- Should PROPULSION watch COMMUNICATION, so that an ESC CAN fault degrades
  it?
- Should DATA_LOGGING watch POWER?

They are recorded, not fixed.

## 5. The minimum identity a profile needs (Part 39)

| field | why | example |
|---|---|---|
| name and version | so results can be tied to a specific model | `aircraft-successor` r1 |
| digest | results record which model they were reasoned against; the shadow runner already writes it into every tick record | `c7541cab…` |
| base profile | an overlay is meaningless without the frozen profile it extends | `csia/v2/profiles/aircraft.py` |
| validation status | the validator's findings at the digest (ERROR count must be 0 to deploy) | ERROR 0, WARNING 4, GAP 0 |
| per-declaration source and kind | so a reviewer can check each edge (DIRECT / DERIVED / CONDITIONAL) | in `aircraft_successor_r1.json` |
| effective configuration | the configuration epoch a declaration holds for. imu1 as an estimator input is true in one estimator configuration and false in another (R6, E1) | *not yet: needed before any CONDITIONAL declaration is accepted* |
| compatibility | the semantics version the profile was validated against | `csia.semantic_core/2.1.0` |

**Not proposed:** a full digital twin, a profile compiler, or runtime
reconfiguration of the profile.
