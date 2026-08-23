# Cross-Dataset Partition Policy

Partitions: DEVELOPMENT / CALIBRATION / VALIDATION / BLIND_TEST /
EXTERNAL_REPLICATION. Implementation: `csia/data/store.py::assign_partition`,
seed `csia-aceg-slice2-2026-08-03`, shares 40/15/20/25 (+ EXTERNAL_REPLICATION
by explicit policy, never hash).

Rules (enforced by `check_group_leakage` + tests):
1. The unit of assignment is the strongest available GROUP — aircraft >
   vehicle-uuid > campaign > recording session > source lineage. Never rows,
   never windows of one flight.
2. Assignment uses metadata + stable hashes BEFORE any signal inspection.
3. A group appearing in two protected partitions is leakage; CI fails.
4. Previously inspected data can never enter BLIND_TEST: the entire
   px4_flightreview_v1 corpus is DEVELOPMENT by decree (v1 contamination).
5. Every BLIND_TEST access is logged to
   datasets/reports/blind_evaluation_access.json (same ledger as slice 3C);
   code changes after viewing convert the campaign to OBSERVED.
6. Re-partitioning requires a new dataset version; assignments are committed.
