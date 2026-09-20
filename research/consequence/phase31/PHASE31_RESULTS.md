# Phase 3.1 results — actionability-precondition study

**Evidence level: `MODEL_BASED_ACTION_CONSEQUENCE`.** Not SITL, not HIL, not
hardware, not flight. No autopilot executed anything. No vehicle was armed
except as a boolean in a simulated telemetry stream. **Nothing flew.**

**Phase 3 is not reopened and its numbers are not pooled with these.** Tests
assert its four locked artifacts still hash to what they hashed at `4cc60eb`,
and that its mutation result is still 38 evaluated / 36 killed / 2 survived
with `P3-03` and `P3-04` the survivors. Its `3/24` versus `1/24` at
**p = 0.625** stands exactly as recorded.

| item | value |
|---|---|
| amendment | `PREREGISTRATION_PHASE31.md`, committed at `7b890ba` before the locked partition was opened |
| partition | `locked`, **40** seeds, manifest `713abd66227760d9…` |
| scenarios | 360 (40 seeds × 3 families × 3 conditions) |
| policies per scenario | 3, on one pass of the trust layer |
| deterministic replay | two full locked runs, **byte-identical**, sha256 `e8c2d90d81b16835…` |

---

## ACTIONABILITY PRECONDITION — **SATISFIED**

The report is **not** `NO_ACTIONABLE_CONSEQUENCE_REACHABLE_UNDER_CURRENT_MODEL`.

Three things Phase 3 could not reach were reached here, all armed, airborne,
past `arm_time`, and with **no disarmed-gate scenario used anywhere**:

1. **Stronger-than-`CAUTION` responses.** `power_sag` and
   `vibration_anomaly` reach `CRITICAL`; `dual_imu_failure` reaches
   `EMERGENCY`. Phase 3's inability to exercise them was a scenario-selection
   limitation of Phase 3, not a structural limit of the architecture.
2. **A confident attribution issued while its separating evidence is entirely
   gated off** — 40 of 360 scenarios, Clopper–Pearson 95 % CI
   **[0.0806, 0.1482]**.
3. **An occlusion-caused action conflict with a measurable consequence** —
   `structural/EG`, 40 of 40 seeds.

### Minimum magnitude and duration to cross each transition

Swept on development seeds, `imu0` accel-z `bias_drift`:

| duration | ESC present | ESC absent |
|---|---|---|
| 10 s | no crossing at any rate ≤ 0.25 | no crossing at any rate ≤ 0.25 |
| 20 s | `CAUTION` + `SELECT_IMU` from 0.05 | `CRITICAL` from 0.03 |
| 40 s | `CAUTION` + `SELECT_IMU` from 0.03 | `CRITICAL` from 0.03 |

**Duration binds, not magnitude**, and **crossing time is not monotone in
fault rate**: 0.12 crosses at 26.96 s while 0.18 and 0.25 cross later. That is
a property of the frozen detector, reported rather than explained.

## The gating condition, and why it is not the Phase-3 control

Every edge is `gate * fresh[a] * fresh[b]`, and both `accel_motor_current` and
`accel_esc_rpm` have `motor_esc` as an endpoint — as does the cross-sensor
gate on `phys_vibration`. An airframe that does not report ESC telemetry, a
case the frozen core's own comments contemplate, drives those gates to zero
**while flying**. Phase 3's disarmed control could not do that and was
excluded from every Phase-3 finding; this one is a real configuration, and a
test asserts every Phase-3.1 scenario's armed schedule is `[[0.0, True]]`.

## CONSEQUENCE TABLE (locked, means over 40 seeds)

| family / cond | pol | conflicts | unsupported | ambiguity | first action | time to safe state | position err | fence margin | outcome |
|---|---|---|---|---|---|---|---|---|---|
| `imu_isolation` / N | P0 | 0 | 0.00 s | 0.00 s | — | — | 0.000 m | 120.000 m | 40 correct |
| `imu_isolation` / EA | P0 | 0 | 0.00 s | 0.00 s | 26.90 s | — | 63.570 m | 56.430 m | 40 correct |
| `imu_isolation` / **EG** | P0 | 0 | **0.04 s** | **55.04 s** | 26.86 s | **49.59 s** | 51.570 m | 68.430 m | **40 unsupported confidence** |
| `imu_isolation` / **EG** | P2 | **40** | 0.00 s | 55.04 s | 26.86 s | 49.59 s | 51.590 m | 68.410 m | **40 abstention** |
| `power` / EA | P0 | 0 | 0.00 s | 0.00 s | 51.05 s | — | 0.000 m | 120.000 m | 40 correct |
| `power` / EG | P0 | 0 | 0.00 s | 55.04 s | 51.05 s | — | 0.000 m | 120.000 m | 40 correct |
| `structural` / EA | P0 | 0 | 0.00 s | 0.00 s | 34.22 s | **54.38 s** | 0.000 m | 120.000 m | 40 correct |
| `structural` / **EG** | P0 | **40** | 0.00 s | 55.04 s | **never** | **never** | 0.000 m | 120.000 m | **40 missed escalation** |

Per the amendment's §8.1 declaration, **position error is meaningful only for
`imu_isolation`**; `power` and `structural` have declared drift rates of 0.0
and their meaningful column is time to safe state. **The energy margin is
meaningful for no family** and is recorded and labelled, not dropped.

### The two findings, stated separately because they point opposite ways

**`structural/EG` — the occlusion hides a fault.** With ESC telemetry present
the vibration anomaly reaches `CRITICAL` at 34.22 s and the vehicle is on the
ground by 54.38 s. With it absent the fault is **never acted on at all** and
the vehicle **never lands**. Correct response class `TERMINATE`, issued class
`NO_ACTION`.

| | conflicts | 95 % CI |
|---|---|---|
| EG (gate shut) | **40 / 40** | [0.911903, 1.0] |
| EA (gate open) | **0 / 40** | [0.0, 0.088097] |

Seed-paired exact McNemar, two-sided: **p = 1.82 × 10⁻¹²**. This is an
occlusion-caused action conflict, and `phys_vibration` is one of the eight
Phase-2 candidates.

**`imu_isolation/EG` — the occlusion makes the system *more* conservative.**
With ESC absent the same fault escalates to `CRITICAL`, the vehicle lands at
49.59 s, and the modelled position error is **lower** (51.570 m against
63.570 m with the evidence available — a 12.0 m difference, above the
preregistered `MIN_CONSEQUENCE_M = 5.0 m`). Removing evidence did not make
this case worse; it made it end the flight sooner.

Both are true, they point in opposite directions, and this is
not a safety conclusion in either direction.

## H2 STATUS — **unchanged: NOT SUPPORTED, as tested in Phase 3**

Phase 3 tested H2 on its own locked partition and rejected it. **Phase 3.1
did not preregister H2 and cannot change its verdict**, and the amendment's
pooling rule forbids combining the two campaigns.

What Phase 3.1 adds is that **the precondition H2 needs is reachable**: a
conflict of exactly H2's shape — correct response materially different from
the issued one — occurs in `structural/EG` at 40/40 with a matched control at
0/40. That is an input to a **preregistered H2 retest**, not a retroactive
change to H2's result. The honest statement is: H2 was rejected on the
evidence Phase 3 gathered, and Phase 3 did not gather the evidence that would
have tested it hardest.

## H3 STATUS — **now testable, and REJECTED in the harmful direction**

Phase 3 could not test H3 because P2 never fired. Here it fires in every
eligible scenario.

| | P0 | P1 | P2 |
|---|---|---|---|
| scenarios | 360 | 360 | 360 |
| **action conflicts** | **40** | **40** | **80** |
| correct actionable | 280 | 280 | 280 |
| incorrect actionable | 0 | 0 | 0 |
| abstentions | 0 | 0 | **40** |
| missed escalations | 40 | 40 | 40 |
| unsupported-confidence scenarios | 40 | 40 | **0** |
| total abstention time | 0.0 s | 0.0 s | 1.6 s |
| mean coverage loss | 0.5141 | 0.5141 | 0.5142 |
| reached safe state | 80 | 80 | 80 |

- **P2 activated in 40 of 40 eligible scenarios**, CI [0.911903, 1.0].
- **False refusals: 40.** In every one, P0 issued `SELECT_IMU1` — the good
  unit — and P2 withdrew it.
- **Incorrect actionable decisions prevented: 0.**
- P2 **doubled** the action conflicts, 40 → 80, exact McNemar
  **p = 1.82 × 10⁻¹²**.

So the support-aware policy did not reduce incorrect actionable decisions; it
removed a correct attribution in every case it acted on. **H3 is rejected in
the direction opposite to the one it hoped for.**

### Why, and it is a finding about the frozen core

`csia.diagnosis.causal.SOURCE_INDICATORS` gives `imu0: (redundant_imu,
accel_motor_current)` and `imu1: (redundant_imu, accel_esc_rpm)`. It does
**not** list `velocity_gps_doppler_0` and `velocity_gps_doppler_1`, which are
also per-IMU-asymmetric and whose gate reads 1.0 in these runs.

The trust engine isolates the faulty IMU on evidence the attribution model
does not know it has. The support classifier takes its LOW-sets verbatim from
`SOURCE_INDICATORS`, so it reports `NON_IDENTIFIABLE` in a state where the
system does in fact identify — and P2, trusting it, withdraws a correct
answer.

**This is not fixed here.** The core is frozen, and editing `SOURCE_INDICATORS`
would invalidate Phase 2's inventory and Phase 3's locked result. It is
recorded as a defect in the attribution model at `SOURCE_ANALYSIS`.

## CONSEQUENCE STATUS — **measurable, in both directions**

Phase 3 could not populate time to safe state in any of its 216 scenarios.
Here it is populated in 80 of 360 and it discriminates: `structural/EA`
reaches the ground at 54.38 s and `structural/EG` never does.

## Mutation — 8 of 11, with three survivors kept

`tools/mutation/run_phase31_mutations.py` is a **separate runner**:
`run_e2m_mutations.py` is not touched, so Phase 3's 38/36/2 is byte-identical
and `P3-03` and `P3-04` cannot be killed as a side effect.

11 evaluated, **8 killed, 3 survived, score 0.7273**; unmutated baseline exit
0, canary killed, every kill attributed to a named test node.

| survivor | what it changes | what its survival reveals |
|---|---|---|
| `31-03` | `materially_different` always returns False | the `INCORRECT_ACTIONABLE` branch is never exercised — no Phase-3.1 control produces one |
| `31-07` | drops the declared correct response for a power sag | nothing pins `correct_response_31` for the new families |
| `31-11` | disables the gating in condition EG | no test runs the campaign end to end |

**These are not patched.** Writing a test to catch a specific mutant is the
one thing this repository's mutation doctrine forbids, and I saw the survivors
before deciding — which is exactly when the rule matters. What would close
them legitimately is named in the next-steps list, not written reactively.

## CLAIMS WE CAN MAKE

1. An actionable consequence **is** reachable under the current model, in a
   physically consistent configuration, without any disarmed-gate scenario.
2. `structural/EG` produces an action conflict in 40/40 seeds against 0/40 in
   its matched control, exact McNemar p = 1.82 × 10⁻¹².
3. A confident attribution is issued while its separating evidence is entirely
   gated off in 40/360 scenarios, CI [0.0806, 0.1482] — and in all 40 the
   attribution is nonetheless **correct**.
4. P2's activation precondition is reachable: 40/40 eligible, CI [0.911903, 1.0].
5. P2 produced 40 false refusals and prevented 0 incorrect actionable
   decisions, doubling action conflicts from 40 to 80.
6. `SOURCE_INDICATORS` omits the per-IMU doppler edges, at `SOURCE_ANALYSIS`.
7. Stronger-than-`CAUTION` transitions are reachable: `CRITICAL` by two routes
   and `EMERGENCY` by one.
8. The campaign replays byte-identically.

## CLAIMS WE CANNOT MAKE

- **Any safety conclusion, in either direction.** Not that P2 is unsafe, not
  that withdrawing an attribution is unsafe, not that the occlusion is
  dangerous, not that the system is safe without it.
- That H2 is supported. Phase 3.1 did not preregister H2 and the pooling rule
  forbids merging the campaigns.
- That any vehicle behaved in any way. Nothing flew.
- SITL, HIL, hardware or flight validation of anything.
- Universal prevalence — three fault families, one airframe profile, one
  trajectory, one simulator.
- Anything about the five Phase-2 candidates still outside the frozen core's
  exposed interface. The eight candidates are unchanged and none was replaced.
- Novelty, certification, airworthiness.

## PHASE 4 READINESS

**Ready, with one precondition met and one caveat.**

Phase 4 needs a detector whose delay and false-alarm behaviour can be varied
and compared against CUSUM at matched operating points. Phase 3.1 establishes
that the detector does cross meaningful transitions and measures the minimum
magnitude and duration to do so — which is the input a threshold grid needs.

The caveat is that crossing time is **not monotone in fault rate**. A
threshold grid that assumes monotonicity would mis-order its operating points,
and Phase 4's preregistration must handle that explicitly.

### Next steps, in the order they would change the most

1. **A preregistered H2 retest** on a fresh partition, using
   `structural/EG` — the conflict Phase 3 never had.
2. An `INCORRECT_ACTIONABLE` control and an end-to-end campaign regression
   test, which would legitimately close `31-03`, `31-07` and `31-11`.
3. A read-only accessor on `TrustState` for the `P` node gates and the
   `_hist_ok` withdrawal, bringing four more Phase-2 candidates into scope. A
   frozen-core change; needs its own authorization.
4. A support model that knows about the doppler edges — which means changing
   `SOURCE_INDICATORS`, and therefore re-running Phases 2 and 3.
