# interceptor_seeker — Failsafe / escalation transitions (SYNTHETIC)

One representative run (seed 0, 100 Hz) per scenario. The escalation
ladder reuses the CSIA FailsafeLevel enum (NORMAL/CAUTION/CRITICAL);
conditions and actions are seeker-specific (csia/seeker/runtime.py:
SeekerPolicy). This is the 'engagement-confidence signal' the white
paper maps to fire-control gating. Advisory only.

## clean_engagement
*Full closing engagement, no faults* — engagement 13.1 s.

No escalation transitions (remained NORMAL).

## ir_decoy
*IR decoy: bearing pulled 6 deg from t=8 s* — engagement 13.1 s.

| t (s) | from | to | trigger | actions |
|---|---|---|---|---|
| 8.8 | NORMAL | CAUTION | ir_seeker trust 0.59 degraded | DEWEIGHT_CHANNEL{'channel': 'ir_seeker'} |
| 9.14 | CAUTION | CRITICAL | ir_seeker trust 0.49 < 0.55 — targeting channel unreliable | INHIBIT_TERMINAL_COMMIT{'channel': 'ir_seeker'}; HANDOVER_TO_ALT_SEEKER{'prefer': 'rf_seeker'} |

## rf_jam
*RF jam: 4 deg az bias + 40 m/s range-rate bias from t=8 s* — engagement 13.1 s.

| t (s) | from | to | trigger | actions |
|---|---|---|---|---|
| 8.63 | NORMAL | CAUTION | ir_seeker trust 0.58 degraded | DEWEIGHT_CHANNEL{'channel': 'ir_seeker'} |
| 8.88 | CAUTION | CRITICAL | rf_seeker trust 0.41 < 0.55 — targeting channel unreliable | INHIBIT_TERMINAL_COMMIT{'channel': 'rf_seeker'}; HANDOVER_TO_ALT_SEEKER{'prefer': 'ir_seeker'} |

## multipath_glitch
*RF multipath: 2-tick range/az spike at t=10 s* — engagement 13.1 s.

| t (s) | from | to | trigger | actions |
|---|---|---|---|---|
| 10.99 | NORMAL | CAUTION | rf_seeker trust 0.75 degraded | DEWEIGHT_CHANNEL{'channel': 'rf_seeker'} |
| 12.0 | CAUTION | NORMAL | conditions cleared | — |
