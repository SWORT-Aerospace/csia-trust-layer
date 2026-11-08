# 03 — Self-occlusion, the primary run

**Arm B, `B_denial_only`.** This is the run behind the paper's headline
result.

**Artifact:** `research/wp_c4/results/self_occlusion.json`
**SHA256:** `f5fd3def036a2b81bf64b5b3ea51daba7421e48f4ea17a3d6112f7e5c7417160`
**Script:** `research/wp_c4/self_occlusion_experiment.py`
**Commit:** `3f41e5558468b181caa1c4d94238815b1ed5cc14`

---

## 1. Configuration, from the artifact

| item | value | source |
|---|---|---|
| arm label | `B_denial_only` | `arms.B_denial_only` |
| arm description | fix INVALID — the self-occlusion case | `arms.B_denial_only` |
| onset | 20.0 s | `onset_s` |
| ticks scored after onset | 1000 | `results.B_denial_only.n_ticks_after_onset` |
| tick rate | 25.0 Hz | `escalation_algebra.json.constants_from_source.tick_hz` |
| **scored duration after onset** | **40 s** | derived: ticks / tick_hz |
| actionable trust threshold | 0.85 | `actionable_trust_threshold` |
| failsafe driver | shipping FailsafePolicy, driven as dashboard/export.py drives it | `failsafe` |

**Seed.** Not recorded per run in this artifact. The pipeline is deterministic
by construction: `csia/scenarios.py:make_sensors()` fixes seeds 1-8 for the
eight sensor nodes, and `docs/REQUIREMENTS.md` R3 requires identical inputs to
give identical outputs. Per-run seed field: **UNRECOVERABLE** (never emitted).

**Fault mechanism.** Denial of the GNSS fix: the arm drives the receiver to an
invalid-fix state, so `gvalid` closes. Contrast arm A drives a position spoof
that leaves the fix valid. See `04` for the contrast.

---

## 2. Downstream injection verification

The gate is the observable that proves the injection reached the layer, not
merely that a command was issued.

| quantity | value | meaning |
|---|---|---|
| `gvalid_min_after_onset` | **0.0** | the gate reached fully closed |
| `gvalid_frac_closed_after_onset` | **0.625** | fraction of post-onset ticks with the gate closed |

Compare arm A, where the same field reads `1.0` and
`0.0`: the gate never closes. The two arms
are distinguished by a measured gate state, not by an intent.

---

## 3. What the layer did

| quantity | arm B value | artifact key |
|---|---|---|
| top-cause occupancy after onset | `{"nominal": 1.0}` | `top_cause_occupancy_after_onset` |
| time to first `gps_fault` lead | **None** (never) | `time_to_first_gps_fault_lead_s` |
| seconds `nominal` on top while faulted | **40.0** | `seconds_nominal_on_top_while_faulted` |
| seconds confident-wrong above actionable trust | **40.0** | `seconds_confident_wrong_nominal_above_actionable_trust` |
| **GPS trust minimum after onset** | **0.9767** | `gps_trust_min_after_onset` |
| max failsafe level | **1** | `max_failsafe_level` |
| failsafe actions | 3 | `n_failsafe_actions` |

**Failsafe trajectory, verbatim:**

```json
[
 {
  "action": "SWITCH_NAV_INERTIAL",
  "params": {},
  "t": 21.0
 },
 {
  "action": "INHIBIT_GPS_MODES",
  "params": {},
  "t": 21.0
 },
 {
  "action": "RESUME_NORMAL",
  "params": {},
  "t": 50.0
 }
]
```

`max_failsafe_level = 1`. In
`csia/runtime/failsafe.py` the levels are ordered NORMAL, CAUTION, CRITICAL,
EMERGENCY, so level 1 is **CAUTION**. The actions are
`SWITCH_NAV_INERTIAL` and `INHIBIT_GPS_MODES`, i.e. the navigation
reconfiguration, followed by `RESUME_NORMAL`.

**The freshness path is what produced them.** The failsafe reaches CAUTION
through a data-freshness disjunct that does not consult the diagnosis. That is
why `deployed_status` and `attribution_status` are scored separately: see
`02` section 1.5.

---

## 4. Verification of the four values carried in conversation

| claimed in conversation | repository value | verdict |
|---|---|---|
| 40 s denial duration | 40 s scored after onset (1000 ticks at 25.0 Hz); `seconds_nominal_on_top_while_faulted` = 40.0 | **CONFIRMED** as the scored post-onset window. Note it is the scoring window, not a separately recorded injection duration |
| GPS trust approximately 0.9767 | **0.9767** exactly, as the post-onset **minimum** | **CONFIRMED**, and it is a minimum, not an average |
| diagnosis nominal throughout | `top_cause_occupancy_after_onset` = `{"nominal": 1.0}`, and `time_to_first_gps_fault_lead_s` = `None` | **CONFIRMED**: 100% nominal occupancy, `gps_fault` never leads |
| maximum failsafe = CAUTION | `max_failsafe_level` = 1 | **CONFIRMED** |

---

## 5. Exposure and SOI for this run

`T_NA`, `T_UH`, `T_FH`, `T_SOFH` are **not** emitted by this artifact. They
are measured by a different experiment against ArduCopter SITL, reported in
`06_EXPOSURE_RESULTS.md`. Do not read exposure numbers off this run.

`SOI(gps_fault) = 1.0` is a property of the effective signature matrix, not of
this run; derivation in `02` section 2.4. This run is what turns that matrix
property into an observed behaviour, which is the claim the paper can make.

---

## 6. Scope, exactly

This run establishes self-occlusion **for a tested fix-loss fault**. It does
not establish it for GNSS faults in general; arm A is the counterexample
inside the same artifact. See `04_REPAIR_EXPERIMENT.md` and `01_PHASE1_SCOPE.md`.
