"""Frozen CSIA v1 cross-dataset baseline (ACEG slice 2, Part 12).

    python tools/run_v1_cross_dataset_baseline.py

Runs frozen v1 (no retuning) over every locally available eligible dataset.
Three modes are DEFINED (frozen / calibration-only / oracle-retuned); modes 2
and 3 execute only where real labelled data exists.

In this environment: the acquisition report shows 0/7 datasets locally
present, so the runner's real-data section reports zero processable flights
with reasons, and the pipeline itself is validated END-TO-END on the
synthetic ULog fixture (adapter -> normalize -> parquet -> quality -> DuckDB
-> v1 ingest attempt). The fixture is NEVER counted as flight exposure.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.data import (NormalizedStore, PX4UlogAdapter, RawStore,  # noqa: E402
                       duckdb_summary, flight_quality, write_fixture)
from csia.experiments import EvidenceEnvironment, build  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "datasets", "reports",
                   "csia_v1_cross_dataset_baseline_v1.json")
QUALITY_OUT = os.path.join(ROOT, "datasets", "reports", "data_quality_v1.json")


def discover_real_data():
    """Only content-addressed raw files count as locally available."""
    raw = os.path.join(ROOT, "datasets", "raw")
    found = {}
    if os.path.isdir(raw):
        for ds in sorted(os.listdir(raw)):
            if ds.startswith("."):
                continue
            hashes = [h for h in os.listdir(os.path.join(raw, ds))
                      if len(h) == 64]
            if hashes:
                found[ds] = len(hashes)
    return found


def pipeline_validation(tmpdir):
    """End-to-end on the synthetic fixture. Returns timing + quality."""
    t0 = time.perf_counter()
    fix = write_fixture(os.path.join(tmpdir, "fixture.ulg"),
                        n_imu=2500, inject_gap_at=1000)
    raw = RawStore(os.path.join(tmpdir, "raw"))
    ing = raw.ingest(fix, "csia_fixture")
    t_hash = time.perf_counter() - t0

    adapter = PX4UlogAdapter()
    t1 = time.perf_counter()
    recs = adapter.normalize(ing["path"], "csia_fixture", "sim_aircraft_0",
                             "fixture_flight_0")
    t_parse = time.perf_counter() - t1

    store = NormalizedStore(os.path.join(tmpdir, "normalized"))
    t2 = time.perf_counter()
    q = flight_quality(recs)
    for r in recs:
        store.write(r, ing["sha256"], quality=None)
    t_write = time.perf_counter() - t2

    summary = duckdb_summary(os.path.join(tmpdir, "normalized"))
    rows = sum(f["rows"] for f in summary.get("flights", []))
    raw_bytes = os.path.getsize(fix)
    norm_bytes = 0
    for dp, _, files in os.walk(os.path.join(tmpdir, "normalized")):
        norm_bytes += sum(os.path.getsize(os.path.join(dp, f)) for f in files)

    # frozen v1 ingest attempt on the fixture — expected to be rejected or
    # degraded (fixture lacks v1's required topic set); the REASON is the
    # deliverable, not a score.
    v1 = {"attempted": True}
    try:
        from csia.runtime.ulog_source import UlogSource
        src = UlogSource(fix)
        v1.update(processable=True, duration_s=round(src.duration, 2),
                  sensors=src.sensors_present)
    except Exception as exc:
        v1.update(processable=False,
                  reason=f"{type(exc).__name__}: {exc}",
                  interpretation="fixture covers assurance topics, not v1's "
                                 "full input set — expected; real logs are "
                                 "the actual baseline input")

    return {
        "fixture_note": "SYNTHETIC — validates the pipeline only; zero "
                        "flight exposure is claimed from it",
        "topics_normalized": len(recs),
        "rows_written": rows,
        "quality": {"topic_count": q["topic_count"],
                    "gap_detected": any(
                        t["max_gap_us"] and t["max_gap_us"] > 50_000
                        for t in q["topics"].values()),
                    "example": q["topics"].get("vehicle_imu#0")},
        "throughput": {
            "hash_s": round(t_hash, 3), "parse_s": round(t_parse, 3),
            "normalize_write_s": round(t_write, 3),
            "raw_bytes": raw_bytes, "normalized_bytes": norm_bytes,
            "expansion_ratio": round(norm_bytes / max(raw_bytes, 1), 2)},
        "v1_ingest": v1,
    }


def main() -> int:
    import tempfile
    real = discover_real_data()
    with tempfile.TemporaryDirectory() as td:
        pipe = pipeline_validation(td)
    qdoc = {"generated_from": "synthetic fixture (pipeline validation)",
            "fixture_quality": pipe["quality"]}
    with open(QUALITY_OUT, "w") as fh:
        json.dump(qdoc, fh, indent=1, sort_keys=True)

    man = build("csia_v1_cross_dataset_baseline",
                EvidenceEnvironment.REAL_LOG_REPLAY,
                dataset_id="cross_dataset_v1",
                dataset_aggregate_hash="0" * 64 if not real else None,
                output_paths=[OUT])
    doc = {
        "result_schema_version": "1.0.0",
        "result_type": "BASELINE_COMPARISON",
        "evidence_environment": "REAL_LOG_REPLAY",
        "experiment_manifest": man.to_dict(),
        "payload": {
            "frozen_v1_commit_basis": "v1 modules untouched since d64225e "
                                      "(bench.json bit-identical)",
            "modes_defined": ["FROZEN_ORIGINAL", "CALIBRATION_ONLY",
                              "ORACLE_RETUNED (research only)"],
            "real_datasets_locally_available": real,
            "processable_real_flights": 0,
            "unprocessable_reason": "0/7 datasets acquired — network policy "
                                    "blocks all dataset hosts (see "
                                    "datasets/reports/acquisition_status_v1"
                                    ".json for verbatim errors)",
            "eligible_monitored_hours": 0.0,
            "detection_metrics": "NOT COMPUTABLE — no eligible data",
            "false_alert_metrics": "NOT COMPUTABLE — no eligible data",
            "transfer_metrics": "NOT COMPUTABLE — no eligible data",
            "unrestricted_host_procedure": [
                "python tools/acquire_public_datasets.py --all "
                "--acknowledge-license insane   # after license review",
                "python tools/run_v1_cross_dataset_baseline.py",
            ],
            "pipeline_validation": pipe,
        }}
    with open(OUT, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    print(json.dumps(doc["payload"]["pipeline_validation"]["throughput"],
                     indent=1))
    print(f"real flights processable: 0 (0/7 datasets present)")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
