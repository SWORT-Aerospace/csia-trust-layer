# Cross-Dataset Protocol (v1)

1. Acquire via `tools/acquire_public_datasets.py` (immutable raw + SHA-256
   BEFORE conversion; licenses acknowledged explicitly; INSANE research-only).
2. Partition BY GROUP before signal inspection (see partition policy).
3. Normalize via adapters to unified_flight_schema_v1; absence stays null.
4. Quality-report every flight; eligibility flags decide which metrics a
   flight may support (a region-labelled flight is latency-ineligible).
5. Frozen v1 first, in three modes: FROZEN / CALIBRATION-ONLY / ORACLE
   (research). Transfer + retuning-burden metrics per Part 13: thresholds
   changed, % change, calibration samples, engineer-hours, regression tests
   affected; performance: frozen loss -> calibration recovery -> oracle
   recovery, with aircraft-level variance.
6. BLIND_TEST evaluated once per frozen implementation; access ledgered.
7. Every result carries an experiment manifest + dataset aggregate hash.
