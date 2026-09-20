# Phase 3.2 results — direct preregistered consequence test (H2)

**Evidence level: `MODEL_BASED_ACTION_CONSEQUENCE`.** Not SITL, not HIL, not
hardware, not flight. No autopilot executed anything. No vehicle was armed
except as a boolean in a simulated telemetry stream. **Nothing flew.**

**Not pooled with Phase 3 or Phase 3.1.** Three disjoint partitions, asserted
by test. Phase 3's `3/24` vs `1/24` at p = 0.625 and Phase 3.1's `40/40` vs
`0/40` at p = 1.82 × 10⁻¹² both stand exactly as recorded, and tests assert
six of their locked artifacts are byte-identical.

| item | value |
|---|---|
| preregistration | `PREREGISTRATION_PHASE32.md`, committed at `e95c616` before the locked partition was opened |
| partition | `locked`, 40 seeds, manifest `b1867fb6a050bb78…` |
| scenarios | 880 (40 seeds × 2 families × (1 nominal + 5 grid × 2 conditions)) |
| **invalid runs** | **0** |
| deterministic replay | two full locked runs, **byte-identical**, sha256 `f9a198b9cf705077…` |

---

## H2 PHASE-3.2 RESULT — **SUPPORTED**

At the single preregistered confirmatory grid point — `structural`, gain 3.0,
EG versus EA, paired by seed:

| | conflicts | 95 % CI (Clopper–Pearson) |
|---|---|---|
| **EG** — evidence gated (ESC telemetry absent, flying) | **40 / 40** | [0.911903, 1.0] |
| **EA** — evidence applicable (ESC telemetry present) | **0 / 40** | [0.0, 0.088097] |

- discordant pairs: b = 40, c = 0
- **exact two-sided McNemar: p = 1.82 × 10⁻¹²**
- **paired risk difference: RD = 1.0**, exact conditional 95 % interval
  **[0.823806, 1.0]** — *conditional on the 40 discordant pairs*, as the
  preregistration requires it to be labelled
- odds ratio: **not finite** (c = 0). No point estimate is reported.
- pairs dropped: **0**, so `UNDERPOWERED_BY_EXCLUSIONS` does not apply
- matched nominal control **N**: 0 conflicts, **0 false escalations**

All three preregistered conditions are met: p < α, RD ≥ `MIN_RD = 0.50` in the
direction of more conflicts under EG, and no false escalation in N.

**Phase 3.1's 40/40 versus 0/40 reproduces on a fresh locked partition drawn
after that finding, with the design fixed beforehand.**

### What the conflict is

With ESC telemetry present, the rotor-vibration anomaly reaches `CRITICAL` at
**34.22 s** and the vehicle is on the ground at **54.38 s**. With it absent —
armed, airborne, past `arm_time` — the fault **never reaches any failsafe
level at all** and the vehicle **never lands**. Correct response class
`TERMINATE`; issued class `NO_ACTION`.

## CONSEQUENCE TABLE (locked, P0, means over 40 seeds)

### Primary arm — `structural`, the full declared gain grid

| cond | gain | conflicts | corr. esc. | false esc. | t → CRITICAL | t → safe state | ambiguity | outcome |
|---|---|---|---|---|---|---|---|---|
| N | — | 0 / 40 | 0 | **0** | — | — | 0.00 s | 40 correct |
| EA | 1.5 | 0 / 40 | 40 | 0 | 32.227 s | 52.387 s | 0.00 s | 40 correct |
| EA | 2.0 | 0 / 40 | 40 | 0 | 33.225 s | 53.385 s | 0.00 s | 40 correct |
| EA | 2.5 | 0 / 40 | 40 | 0 | 33.810 s | 53.970 s | 0.00 s | 40 correct |
| EA | **3.0** | 0 / 40 | 40 | 0 | 34.220 s | 54.380 s | 0.00 s | 40 correct |
| EA | 4.0 | 0 / 40 | 40 | 0 | 34.852 s | 55.012 s | 0.00 s | 40 correct |
| EG | 1.5 | **40 / 40** | 0 | 0 | **never** | **never** | 55.04 s | 40 missed escalation |
| EG | 2.0 | **40 / 40** | 0 | 0 | never | never | 55.04 s | 40 missed escalation |
| EG | 2.5 | **40 / 40** | 0 | 0 | never | never | 55.04 s | 40 missed escalation |
| EG | **3.0** | **40 / 40** | 0 | 0 | never | never | 55.04 s | 40 missed escalation |
| EG | 4.0 | **40 / 40** | 0 | 0 | never | never | 55.04 s | 40 missed escalation |

`CAUTION` and `EMERGENCY` are never reached by this family in either
condition; the transition is `NORMAL → CRITICAL` directly. Position error,
altitude error and geofence margin are **0.000 m / 0.000 m / 120.000 m**
throughout, and that is not a null result — per the preregistration's
declaration, carried forward from Phase 3.1, `structural` has a **declared
drift rate of 0.0** and its meaningful column is time to safe state. **The
energy margin (0.9388 everywhere) is meaningful for no family** and is
recorded and labelled rather than dropped. Fault-window duration is 20.0 s.

### Secondary arm — `imu_isolation`, the full declared rate grid

Carries no verdict. Reported in full because the grid discipline is the point.

| cond | rate | conflicts | unsupported | corr. esc. | t → CAUTION | t → CRITICAL | t → safe state | position err | outcome |
|---|---|---|---|---|---|---|---|---|---|
| EA | 0.03 | 0 / 40 | 0 | 40 | 50.215 s | — | — | 63.574 m | 40 correct |
| EA | 0.05 | 0 / 40 | 0 | 40 | 35.168 s | — | — | 63.574 m | 40 correct |
| EA | 0.08 | 0 / 40 | 0 | 40 | 31.395 s | — | — | 63.574 m | 40 correct |
| EA | 0.12 | 0 / 40 | 0 | 40 | 26.885 s | — | — | 63.574 m | 40 correct |
| EA | 0.18 | 0 / 40 | 0 | 40 | **34.752 s** | — | — | 63.574 m | 40 correct |
| EG | 0.03 | **40 / 40** | 0 | 0 | — | 34.153 s | never | 57.693 m | 40 safe fallback |
| EG | 0.05 | **40 / 40** | 0 | 0 | — | 27.769 s | 54.988 s | 55.074 m | 40 safe fallback |
| EG | 0.08 | **31 / 40** | 9 | 9 | — | 27.091 s | 54.260 s | 53.823 m | 31 safe fallback, 9 unsupported |
| EG | 0.12 | **0 / 40** | **40** | 40 | — | 26.844 s | 49.719 s | 51.631 m | 40 unsupported confidence |
| EG | 0.18 | **0 / 40** | **40** | 40 | — | 35.706 s | 55.878 s | 54.601 m | 40 unsupported confidence |

**The non-monotonicity the preregistration refused to assume away is here in
both columns.** Time to `CAUTION` under EA falls from 50.2 s to 26.9 s as the
rate rises to 0.12 and then **rises again to 34.8 s at 0.18**. And the
conflict rate under EG goes 40, 40, 31, **0, 0** — a grid that pruned the
small magnitudes as uninteresting, or stopped at the first "sufficient" rate,
would have reported the opposite of what is here.

At 0.12 and 0.18 the system *does* issue the correct `SELECT_IMU1` — so no
action conflict — but issues it while the pair it discriminates is reported
not identifiable. That is `UNSUPPORTED_CONFIDENCE`: the right answer, from
evidence that could not have told.

## STATISTICAL ANALYSIS

| grid point | b | c | conflicts EG / EA | RD | exact McNemar p | significant | ≥ MIN_RD |
|---|---|---|---|---|---|---|---|
| `imu_isolation` 0.03 | 40 | 0 | 40 / 0 | 1.000 | 1.82 × 10⁻¹² | yes | yes |
| `imu_isolation` 0.05 | 40 | 0 | 40 / 0 | 1.000 | 1.82 × 10⁻¹² | yes | yes |
| `imu_isolation` 0.08 | 31 | 0 | 31 / 0 | 0.775 | 9.31 × 10⁻¹⁰ | yes | yes |
| `imu_isolation` 0.12 | 0 | 0 | 0 / 0 | 0.000 | 1.0 | no | no |
| `imu_isolation` 0.18 | 0 | 0 | 0 / 0 | 0.000 | 1.0 | no | no |
| `structural` 1.5 | 40 | 0 | 40 / 0 | 1.000 | 1.82 × 10⁻¹² | yes | yes |
| `structural` 2.0 | 40 | 0 | 40 / 0 | 1.000 | 1.82 × 10⁻¹² | yes | yes |
| `structural` 2.5 | 40 | 0 | 40 / 0 | 1.000 | 1.82 × 10⁻¹² | yes | yes |
| **`structural` 3.0** | **40** | **0** | **40 / 0** | **1.000** | **1.82 × 10⁻¹²** | **yes** | **yes** |
| `structural` 4.0 | 40 | 0 | 40 / 0 | 1.000 | 1.82 × 10⁻¹² | yes | yes |

Only the bold row carries the verdict. The other nine are preregistered
dose-response secondaries; **no multiplicity correction is claimed and no
conclusion rests on them.**

Per-seed outcomes for every pair are in
`results/PHASE32_RESULTS_LOCKED.json` under `tests[].per_seed`.

**Invalid runs: 0**, so the exclusion machinery was exercised but never had to
act. Reasons would have been recorded per run; there are none to record.

## P2 EXPLORATORY RESULT

**`P2_CURRENT_IMPLEMENTATION_EXPLORATORY`.** P2 is excluded from the primary
test because `FL-029` establishes its support mapping is invalid:
`SOURCE_INDICATORS` omits the per-IMU Doppler edges, so its
`NON_IDENTIFIABLE` verdicts do not mean what the policy takes them to mean.
`SOURCE_INDICATORS` is **not** repaired — the frozen core is not edited.

| scenario | n | P0 conflicts | P2 conflicts | P2 abstentions | P0 correct esc. | P2 correct esc. |
|---|---|---|---|---|---|---|
| `structural` EG 3.0 | 40 | 40 | 40 | 0 | 0 | 0 |
| `imu_isolation` EG 0.03 | 40 | 40 | 40 | 0 | 0 | 0 |
| `imu_isolation` EG 0.12 | 40 | **0** | **40** | **40** | **40** | **0** |

On the primary arm P2 changes nothing — it has no attribution to withdraw.
On the secondary arm at rate 0.12 it withdraws the correct `SELECT_IMU1` in
40 of 40, turning 0 conflicts into 40, which reproduces Phase 3.1's finding on
a fresh partition.

**Nothing here supports a claim that P2 is safe or unsafe in general.** It is
a statement about this implementation, with a known invalid input.

## Mutation — 7 of 12, five survivors kept, and one of them is uncomfortable

A **third separate runner**. `run_e2m_mutations.py` (38/36/2) and
`run_phase31_mutations.py` (11/8) are untouched, so none of their five
survivors can be killed as a side effect. 12 evaluated, **7 killed, 5
survived, score 0.5833**; unmutated baseline exit 0, canary killed, every kill
attributed to a named test node.

| survivor | what it changes |
|---|---|
| `32-02` | `MAX_DROPPED_PAIRS` 4 → 40, so any number of exclusions passes |
| `32-03` | **picks the best-performing grid point as confirmatory instead of the preregistered one** |
| `32-10` | `false_escalation` always False, so the nominal control cannot veto |
| `32-11` | disables the evidence gating in EG |
| `32-12` | stops detecting one class of invalid run |

**`32-03` is the cherry-pick mutant, and its survival is the most important
thing in this section.** It survives for a reason worth stating precisely
rather than glossing: **every structural grid point in this campaign gives
40/40 versus 0/40, and the maximum-RD point over all ten is `imu_isolation`
0.03 with RD = 1.0 and the same p-value.** Substituting a cherry-pick for the
preregistration produces the identical verdict here. *This study has no cherry
to pick* — which is why no test could catch the mutant on this data, and which
is not the same as the discipline being verified.

**Not patched.** Writing a test to catch a specific mutant is what this
repository's mutation doctrine forbids, and the survivors were seen before the
decision was taken. What they reveal, plainly: the Phase-3.2 suite tests the
statistical primitives thoroughly and **does not test the analysis pipeline's
use of them** — nothing runs `build()` over a synthetic document and checks
the verdict logic, the exclusion accounting or the confirmatory selection.

**This is the second phase in a row with the same gap.** Phase 3.1's `31-03`,
`31-07` and `31-11` survived for the same reason, I named an end-to-end
regression test as the removal action, and I did not write one before running
Phase 3.2. That is a finding about my own process, not only about the tests.

## CLAIMS WE CAN MAKE

1. At the preregistered confirmatory grid point, evidence gating produces an
   action conflict in **40 of 40** paired seeds against **0 of 40** in the
   matched control, exact McNemar **p = 1.82 × 10⁻¹²**, RD = 1.0, exact
   conditional 95 % CI [0.823806, 1.0], 0 exclusions.
2. The matched nominal control produces **0 false escalations**, so the effect
   is not a policy that escalates on clean flights.
3. With ESC telemetry present the fault reaches `CRITICAL` at 34.220 s and
   safe state at 54.380 s; with it absent it reaches **no** failsafe level and
   **never** reaches safe state.
4. The effect holds at every gain in the declared grid, 1.5 through 4.0.
5. Crossing time and conflict rate are both **non-monotone** in fault rate on
   the secondary arm.
6. At rates 0.12 and 0.18 the system issues the correct attribution while the
   pair is reported not identifiable — 40/40 `UNSUPPORTED_CONFIDENCE`.
7. 0 invalid runs; the campaign replays byte-identically.
8. P2 withdraws the correct attribution in 40/40 on the secondary arm at 0.12,
   reproducing Phase 3.1 on a fresh partition.

## CLAIMS WE CANNOT MAKE

- **Hardware or flight validation.** Nothing flew.
- **Autopilot execution.** No autopilot path ran.
- **That P2 is safe, or unsafe, in general.** `FL-029` makes its current
  mapping invalid; that is a statement about this implementation.
- **Universal prevalence.** One confirmatory fault family, one secondary, one
  airframe profile, one trajectory, one simulator.
- **Certification, airworthiness, novelty.**
- Anything about the five Phase-2 candidates outside the frozen core's exposed
  interface. The eight are unchanged and none was replaced.
- That the result generalises to airframes that do report ESC telemetry. It is
  precisely a statement about one that does not.

## PHASE 4 READINESS

**Ready.** Phase 3.2 supplies what a detector-performance study needs:

- a fault family with a measured, reproducible detection transition
  (`structural`, `NORMAL → CRITICAL`, 32.2–34.9 s across the gain grid);
- a second family whose crossing time is **non-monotone** in fault magnitude,
  which is the case a threshold grid must handle rather than assume away;
- a matched control condition with a 0/40 conflict rate and a clean nominal
  arm, which is what a false-alarm operating point has to be measured against;
- 0 invalid runs at this scale, so exclusions will not dominate.

Phase 4 must, per its own preregistration: use the full threshold grid;
compare at **matched false-alarm operating points**; handle non-monotonic
crossing time explicitly; use development and locked partitions; implement
CUSUM correctly as the baseline, not a straw man; and report delay quantiles
alongside false-alarm rates.

**And it should close the gap `32-03` exposed first** — an end-to-end test of
the analysis pipeline, not more tests of its primitives.
