# P1 step 0 — test-partition contamination audit

**Committed before any candidate was tuned.** Derived by
`partition_audit.py` from the artifacts, not asserted.
**Artifact:** `results/partition_audit.json`.

---

## 1. The declared partition, and what it actually is now

`CANDIDATE_REGISTRY.yaml` declared, for the Phase-I rig:

```
development:  flight_specs [0, 1, 2]   slews_s [0, 4, 20]
protected:    flight_specs [3, 4, 5]   slews_s [0, 4, 20, 60, 120]   status: UNTOUCHED
```

### Flight-spec axis

| spec | home | declared | **measured** |
|---|---|---|---|
| 0 | 47.397742, 8.545594 | development | **ALREADY_OBSERVED** |
| 1 | −35.363261, 149.165230 | development | DEVELOPMENT |
| 2 | 37.413360, −121.996500 | development | DEVELOPMENT |
| 3 | 55.953251, −3.188267 | protected | PROTECTED_UNTOUCHED |
| 4 | −22.906847, −43.172896 | protected | PROTECTED_UNTOUCHED |
| 5 | 64.128288, −21.827774 | protected | PROTECTED_UNTOUCHED |

Every Phase-II flight before P1 used `modern_rig.HOME`, which is spec 0: E1
run 1, E1 run 2, the V6 diagnosis, the R10 investigation, the P0.5 contract
audit, the R10 attribution intervention and both P1 discovery probes.

### Slew axis

| slew | declared | observed | **measured** |
|---|---|---|---|
| 0 s | development | no | DEVELOPMENT |
| 4 s | development | no | DEVELOPMENT |
| 20 s | development + protected | yes | ALREADY_OBSERVED |
| **60 s** | **protected only** | **yes** | **CONTAMINATED** |
| **120 s** | **protected only** | **yes** | **CONTAMINATED** |
| 240 s | **neither list** | yes | ALREADY_OBSERVED |

---

## 2. Findings, stated plainly

**The protected partition is not untouched.** The registry says
`status: UNTOUCHED`. On the slew axis that is false: 60 s and 120 s are
declared protected-only and were flown and inspected in E1 run 1, E1 run 2 and
the V6 diagnosis. The brief's instruction is explicit — do not pretend an
already inspected E1 cell is a protected validation cell — so those two levels
are marked **CONTAMINATED**.

**E1 flew outside the declared partition entirely.** Slew 240 s appears in
neither the development nor the protected list. It was not a protected cell
being spent; it was a level the partition never contemplated.

**The partition was defined for a different rig.** It was written against
ArduCopter 3.3. Every Phase-II flight is on 4.8, where two graph nodes are
live that were dead on 3.3 and the ESC channel is a stub. A partition defined
on one rig does not transfer to another by assumption.

**The wind factor is real on the modern target, and was not on the legacy
one.** The six flight specs vary `(home, wind)`. WP-C7 measured wind as
**cosmetic** on ArduCopter 3.3, which would have made the specs differ only by
home site. Measured here on 4.8 (`results/p1_wind_isolated.json`), with
altitude held at 18.4 m in every stage and a null stage between:

| SIM_WIND_SPD | mean attitude lean |
|---|---|
| 0 (baseline) | 0.183 rad |
| 15 m/s | **0.471 rad** |
| 0 (null control) | 0.189 rad |
| 25 m/s | **0.522 rad** |

So the flight-spec partition carries a genuine second factor here that it did
not carry in Phase I.

*An earlier probe reported wind as not reaching the airframe. That probe was
confounded: it ran the wind stage immediately after a violent vibration
injection that had put the vehicle at 3.4 m, and `SIM_WIND_T` defaults to
`WIND_TYPE_SQRT`, which scales wind by `sqrt(alt / 60)`. The isolated re-run
above holds altitude constant. The failed probe is preserved.*

---

## 3. The partition P1 actually used, declared before tuning

| role | flight spec | rule |
|---|---|---|
| **DEVELOPMENT** | 0 | already thoroughly observed, so nothing is lost. All B2/B3/B4 parameter search happened here and nowhere else. |
| **VALIDATION (touch 1)** | 3 | never flown on the modern target before P1. Touched once, with parameters already frozen. |
| **VALIDATION (touch 2)** | 4 | never flown on the modern target before P1. Touched once, after an instrument repair, with the same frozen parameters. |
| **RESERVED UNTOUCHED** | 1, 2, 5 | not used by P1 at all. Kept for E2 and later validation. |

**Why two validation touches, disclosed.** Spec 3 was flown, and then a third
instrument defect was found: the stream handed to B4 for the `gps` node was
`_lam["phys_gps"]`, which is identically zero even under a GPS spoof, because
`online.py:568-573` forms `P["gps"] = max(lam_gps, (gps_step_peak/20)²)` and
the step term does all the work. B4's GPS blindness was therefore an artifact
of my recording, not a property of the method. The repair required re-flying,
and rather than touch spec 3 twice, spec 4 was spent as a fresh validation
set. **No parameter was changed between the two touches** — `k = 5` and
`h = 500` were frozen on spec 0 before either. Spec 3's result is retained.

**No parameter was searched on any validation spec.** The B2 `k` grid and the
B4 `h` grid are re-printed in the validation artifacts only to show that the
same value is selected there; the selection rule reads the clean nominal arm
alone and never a fault outcome.

---

## 4. What this costs

Two of the three originally protected flight specs are now spent. One (spec 5)
plus the two unflown development specs (1, 2) remain untouched. E2's
preregistration does not name a flight spec, so it is unaffected; if E2 needs
a fresh set it should use 1, 2 or 5 and say so before flying.
