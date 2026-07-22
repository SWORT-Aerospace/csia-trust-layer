# Held-Out Real-Data Validation Protocol (closes review finding C2)

C2 (docs/ARCHITECTURE_REVIEW.md): the public-log false-alarm rate was tuned
and reported on the same 26 flights — train/test contamination. This
protocol produces a false-alarm number an adversarial evaluator cannot
dismiss. Nothing here requires new code; it requires discipline about
WHICH logs touch WHICH decisions.

## Rules

1. **Freeze first.** Tag the exact commit under test. Every number in the
   final table comes from that tag; any code or threshold change restarts
   the protocol from step 3.
2. **Two disjoint log sets.**
   - `CAL` (calibration set): the existing 26 flights
     (`data/real_logs_report.json`) plus anything else already used during
     development. These may tune sigmas, gates, and thresholds. Their
     false-alarm rate is REPORTED AS CALIBRATION, never as the headline.
   - `HOLD` (held-out set): ≥ 200 fresh multirotor logs, ≥ 10 flight
     hours, downloaded by UUID from the PX4 Flight Review public database,
     selected by a pre-registered query (vehicle type + minimum duration +
     date range), NOT by inspecting their contents. The UUID list is
     committed BEFORE any of them is run (`campaigns/holdout_uuids.json`).
3. **One pass, one config.** Run
   `csia analyze-logs "data/holdout/*.ulg" --out campaigns/holdout_report.json`
   exactly once per frozen tag with the same
   `OnlineTrustLayer(field_mode=True)` posture used for CAL. No per-log
   options. If the run crashes on a log, the crash is a reported result,
   not a reason to drop the log.
4. **Report everything the run produced.** Alarms/flight-hour with the
   Poisson 95% CI (the machinery exists in `csia.validation`), the count
   of alarm-free flights, excluded-channel statistics, and contained-error
   counts. Alarms may be annotated after the fact ("log shows real GPS
   loss at this timestamp") but never removed from the count — annotation
   distinguishes candidate false alarms from true detections in prose,
   the number stays the number.
5. **Iterate honestly.** If HOLD's rate is unacceptable, fix the model,
   move the burned HOLD set into CAL, draw a NEW hold-out set, and repeat
   from step 3. A hold-out set is single-use.

## Sample-size floor

At the current claimed order (~4.5/hr on 0.66 h, Poisson 95% CI ≈
[1, 13]/hr — nearly an order of magnitude wide), the number is not yet
evidence. 10 flight hours bounds a zero-alarm result below 0.37/hr (95%)
and a 5-alarm result to [1.6, 11.7]/hr → the target of ≥ 10 h is the
minimum for a quotable rate; 30+ h is the goal for Phase-2 claims.

## Armed-state note (2026-07 hardening)

`analyze-logs` now consumes the ULog `vehicle_status` topic: segments where
the vehicle is disarmed no longer produce failsafe activations. The
committed 3-alarm / 4.5-per-hour figure predates this. Re-run the CAL set
(`python tools/fetch_real_logs.py`) before drawing the first HOLD set so
the calibration baseline reflects the current code.
