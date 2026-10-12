# Phase-II methodology — permanent rules

These are binding on every Phase-II work package. Rules 1-10 are the standing
set. The "how it was learned" column is not decoration: each rule that carries
one was added after a specific instrument or attribution failed, and the
failure is preserved in the correction history rather than deleted.

| # | rule | how it was learned |
|---|---|---|
| 1 | `COMMAND_ISSUED != INTERVENTION_VALID` | `SIM_GPS_GLITCH_X` does not exist on ArduCopter 4.8. Writing it is a silent no-op that would have produced clean flights labelled as fault arms. Enforced by `modern_rig.set_param` raising on legacy names, and by the V1-V6 contract. |
| 2 | **Every instrument requires a null control** | E1 run 1's displacement estimator read **38.89 m on a zero-injection nominal arm** and invalidated the three cells that decided the question. Enforced by `modern_rig.instrument_control()`. |
| 3 | **Names never establish semantics** | `ESC_TELEMETRY_1_TO_4.rpm` is not a motor-speed model. SITL computes it as `motors[i].get_command() * SIM_VIB_MOT_MAX * 60`, a vibration-model term whose parameter defaults to 0. |
| 4 | **Causal claims require intermediate-state evidence** | The first R10 attribution blamed the `phys_battery` voltage residual on arithmetic that fit to within 0.002 V. Logging `components['battery']['phys']` showed it reading 1.000 all flight. The real driver was the `power_thrust` edge. |
| 5 | **All failed instruments remain in the correction history** | `results/e1_modern_run1_defective_instrument.json`, the failed `rpm` null control in `power_thrust_contract.json`, and claim `C1_WITHDRAWN` in `claims.yaml` are kept, not deleted. |
| 6 | **Protected cells are not used for tuning** | `CANDIDATE_REGISTRY.yaml` partitions: specs 0-2 for search, specs 3-5 protected and still `UNTOUCHED`. |
| 7 | **Baseline failure does not justify relaxing a pre-existing requirement** | R10's budget stayed at 0 when the frozen baseline broke it on 4.8. The breach was diagnosed to a simulator stub; the requirement was never moved. |
| 8 | **No production changes before candidate measurement behind a flag** | Two production changes exist in the whole programme, both from Phase I. Phase II has made none. |
| 9 | **No theorem claim generated from simulation alone** | The WP-C8 mass-invariance "theorem" was wrong by 0.198 and predicted the wrong tick by 59. Corrected forms are stated as algebra verified against shipping code, not as theorems. |
| 10 | **No generalisation from one autopilot stack** | E1's `SURVIVES_BOUNDED` verdict is bounded to ArduCopter 4.8, one flight profile, one flight per cell. PX4 is tracked as `C10`, open. |

## Rule 2, in the form that catches the most

A null control is not "check the code looks right". It is: **run the
instrument on an arm where the thing it measures is known to be absent, and
require it to read approximately zero.**

Two instruments have failed this in Phase II, and the second failure is the
instructive one:

- E1 run 1's displacement estimator: failed the control, at 38.89 m.
- P0.5's chosen null control (`rpm` from the same message as the audited
  field) **was itself constant**, so it certified nothing. The correct response
  was to report `HARNESS_LIVE_...` only after substituting a control that
  did discriminate (`BATTERY_STATUS.current_battery`, 375 distinct values on
  the same ticks) — not to conclude anyway. The analysis code printed
  `INSTRUMENT_DEAD_NOTHING_CONCLUDABLE` and refused.

## Rule 4, in the form that catches the most

An attribution that fits the arithmetic is not an attribution. Before naming a
mechanism, **log the intermediate the mechanism runs through** and show it
moving. If the intermediate is flat, the mechanism is wrong however well the
numbers agree.

## A rule this phase did not have and now does

**Rule 2a — freshness is not informativeness.** A channel can be present,
fresh, well-formed, correctly scaled and empty. `online.py:603-613`'s
watchdog detects a channel that *stops*; it has no notion of a channel that
never carried anything. Every Phase-II measurement on a new stack must
establish that each newly available channel *varies* before any relation
consuming it is scored.

This is recorded as a methodology rule, not as a proposed production change.
Whether CSIA should acquire such a gate is an invention-gate question and the
gate is `CLOSED`.
