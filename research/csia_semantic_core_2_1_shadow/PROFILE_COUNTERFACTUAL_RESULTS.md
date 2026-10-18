# Counterfactual profile test

**2026-09-30. Part 7 of the shadow-validation brief.** Source:
`SHADOW_RESULTS.json`, `counterfactual_profiles`, written by
`shadow_validation.py`.

**What was run.** Every configuration runs on dataset A (44 scenarios, 60
ticks each, 2,640 ticks), in shadow, with frozen v2.0 authoritative. Each
configuration's overlay digest is recorded next to its results.

## 1. What each column measures

| column | meaning |
|---|---|
| categories vs v2.0 | the Part 3 classification of every unit that still differs from v2.0 under this profile |
| restored | units that differed from v2.0 under 2.1 without an overlay, and equal v2.0 under this one |
| new | units equal to v2.0 without an overlay that differ under this one |
| shrink / expand | localizations whose survivor set gets strictly smaller or larger than under 2.1 without an overlay |
| new UNIQUE | ticks whose attribution becomes UNIQUE where 2.1 without an overlay was not |
| wrong UNIQUE | ticks whose 2.1 attribution is UNIQUE and names a domain other than this tick's true cause |
| P16 | POSITION_UNAVAILABLE localizations on a function the frozen function graph, fed the same records, calls ELIGIBLE |
| Phase C | the frozen `decision_gate` over 2.1's matched-set localizations |

## 2. Results

| profile | categories vs v2.0 | restored | new | shrink | expand | new UNIQUE | wrong UNIQUE | P16 | Phase C verdict and qualifying answers |
|---|---|---|---|---|---|---|---|---|---|
| none (2.1 as shipped) | FIX 273, WITHHOLD 197, GAP 805 | — | — | — | — | — | 3 (as v2.0) | 168 / 1,322 | FUNCTIONAL, identical |
| **successor r1 (R2 + R3)** | FIX 273, WITHHOLD 197, **GAP 204** | **601** | **0** | 120 | 0 | 0 | 3 (as v2.0) | 252 / 1,803 | FUNCTIONAL, identical |
| R1 | FIX 273, WITHHOLD 197, GAP 763, POSSIBLE_REGRESSION 42 | 0 | 0 | 120 | 0 | 0 | 3 | 252 / 1,406 | FUNCTIONAL, identical |
| R2 | FIX 273, WITHHOLD 197, GAP 805 | 0 | 0 | 120 | 0 | 0 | 3 | 168 / 1,635 | FUNCTIONAL, identical |
| R3 | FIX 273, WITHHOLD 197, GAP 204 | 601 | 0 | 120 | 0 | 0 | 3 | 423 / 1,803 | FUNCTIONAL, identical |
| R1 + R2 + R3 | FIX 273, WITHHOLD 197, GAP 204 | 601 | 0 | 120 | 0 | 0 | 3 | 252 / 1,803 | FUNCTIONAL, identical |
| R4 | FIX 273, WITHHOLD 197, GAP 805 | 0 | 0 | 0 | 0 | 0 | 3 | 168 / 1,322 | FUNCTIONAL, identical |
| R5 | FIX 273, WITHHOLD 197, GAP 601 | 204 | 0 | 123 | 0 | 81 | 3 | 168 / 1,322 | FUNCTIONAL, identical |
| R5a | same as R5 | 204 | 0 | 123 | 0 | 81 | 3 | 168 / 1,322 | FUNCTIONAL, identical |
| R5b | same as R5 | 204 | 0 | 123 | 0 | 81 | 3 | 168 / 1,322 | FUNCTIONAL, identical |
| r1 + R5 | FIX 273, WITHHOLD 197 | 805 | 0 | 243 | 0 | 81 | 3 | 252 / 1,803 | FUNCTIONAL, identical |
| R1 to R5 (every candidate) | FIX 273, WITHHOLD 197 | 805 | 0 | 243 | 0 | 81 | 3 | 252 / 1,803 | FUNCTIONAL, identical |
| R1 to R6 | as above | 805 | 0 | 243 | 0 | 81 | 3 | 252 / 1,803 | FUNCTIONAL, identical |
| **with R-BAD** | **FIX 147**, WITHHOLD 197 | 931 | 0 | 243 | 0 | 81 | 3 | 378 / 1,929 | FUNCTIONAL, identical |

**The 3 wrong UNIQUE ticks** are TS_CPU_OVERLOAD ticks 26-28, and they are
identical in v2.0. At onset the encoder timing segment crosses its limit
before the CPU and the controller cross theirs, so the evidence shows the
effect before the cause. This is loophole L16 in `LOOPHOLE_REGISTER.csv`.

**SHARED_RAIL is not a wrong UNIQUE.** Its ticks 0-28 name SENSOR/source.gps
UNIQUE. That is correct: the real v1.1 "fixloss" payload has lost its GPS fix
from tick 0, while the injected rail stays inside tolerance until tick 29.
`ground_truth.py` makes that one case time-resolved (`payload_cause`).

**Phase C** keeps verdict `CROSS_DOMAIN_ASSURANCE_FUNCTIONAL` in every
configuration. The qualifying sets are A_STALE_OUTPUT and
B_ACTUATOR_RESPONSE_BENCH, and their six answers are identical everywhere.

**Set D stays non-qualifying.**
- **Without an overlay, and with any configuration lacking R3:** "not every
  member reduced to a supported hypothesis".
- **With R3:** "two members reduced to the SAME hypothesis". That is frozen
  v2.0's own recorded reason.

**XSYS-001 (dataset B) is unaffected by construction.** Its adapter builds
its own records and never reads the aircraft profile. Under 2.1 it gives:
- the hard gate PASS;
- 3,872 slots;
- 0 decision, 0 outcome and 0 full-view differences against the sealed run;
- the primary at 55/55 with lower bound 0.7616.

## 3. What the test says

1. **The accepted repair restores exactly the units it should.**
   - **Restored:** successor r1 takes back all 601 G-1 units, with no new
      incorrect result, no new wrong UNIQUE and no expanded candidate set.
   - **Still differing from v2.0:** 273 correctness fixes, 197 conservative
     withholds and 204 G-2 units. The G-2 units are explicitly blocked in
     `G2_ESTIMATOR_INPUT_AUDIT.md`.
2. **Every configuration that restores the G-2 units restores a wrong reason
   with them.** That is R5, R5a, R5b and every superset. Dataset A cannot show
   this: in every shipped scenario the restored answer happens to be right.
   The IMU pacing-loss counterfactual shows it (W7). Counting restored units
   is therefore not enough to accept a repair, and the brief's Part 7 test
   ("restores historical certainty by reintroducing logically unrelated
   evidence") is what rejects them.
3. **Over-connection is visible and specific.**
   - **R-BAD** restores 126 of the MS_B1 false navigation symptoms that 2.1
     removed. Its correctness fixes fall from 273 to 147, and 126 unit-ticks
     of symptoms reappear on unaffected functions.
   - **A validator would stop it before any run:** it is
     `PV3_UNWATCHED_DECLARATION` (`PROFILE_VALIDATOR_SPEC.md`).
4. **No configuration changed XSYS-001 or the Phase C headline.**
