"""Immutable raw storage + Parquet normalization + partitions + quality.

Layout (ACEG slice 2, Part 4):
    datasets/raw/<dataset_id>/<sha256>/<original_name>
    datasets/normalized/v<schema>/dataset=<id>/aircraft=<id>/flight=<id>/
        topic=<t>/instance=<i>/part.parquet
Raw files are write-once; ingest refuses to overwrite a differing file at the
same content address. Every normalized artifact records its raw hash, the
transform config hash, the software commit and the schema version.
"""

import hashlib
import json
import os
import shutil

from .adapters import UNIFIED_SCHEMA_VERSION


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class RawStore:
    def __init__(self, root="datasets/raw"):
        self.root = root

    def ingest(self, path: str, dataset_id: str) -> dict:
        """Copy into content-addressed storage. Immutable: re-ingesting the
        same content is a no-op; a different file claiming the same address is
        impossible by construction (address IS the hash)."""
        digest = sha256_file(path)
        d = os.path.join(self.root, dataset_id, digest)
        dest = os.path.join(d, os.path.basename(path))
        if os.path.exists(dest):
            if sha256_file(dest) != digest:
                raise RuntimeError(f"immutability violation at {dest}")
            return {"sha256": digest, "path": dest, "status": "ALREADY_PRESENT"}
        os.makedirs(d, exist_ok=True)
        shutil.copy2(path, dest)
        os.chmod(dest, 0o444)                       # read-only
        return {"sha256": digest, "path": dest, "status": "INGESTED"}


def _transform_config_hash(cfg: dict) -> str:
    return hashlib.sha256(
        json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def _git_commit():
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL, timeout=10).strip()
    except Exception:
        return None


class NormalizedStore:
    def __init__(self, root="datasets/normalized"):
        self.root = root

    def write(self, rec, raw_sha256: str, quality: dict | None = None) -> str:
        """FlightRecord -> partitioned Parquet with provenance columns.
        Missing values stay null in Parquet — never imputed, never zero."""
        import polars as pl
        n = rec.n
        data = {k: v for k, v in rec.columns.items()}
        df = pl.DataFrame(data, strict=False).with_columns([
            pl.lit(rec.dataset_id).alias("dataset_id"),
            pl.lit(rec.aircraft_id).alias("aircraft_id"),
            pl.lit(rec.flight_id).alias("flight_id"),
            pl.lit(rec.sensor_instance).alias("sensor_instance"),
            pl.lit(rec.device_id).alias("device_id"),
            pl.lit(rec.time_domain).alias("time_domain"),
            pl.lit(rec.sync_method).alias("sync_method"),
        ])
        # per-field missingness masks (Part 5: missingness is first-class)
        for f in rec.columns:
            if f != "timestamp":
                df = df.with_columns(
                    pl.col(f).is_null().alias(f"{f}__missing"))
        d = os.path.join(
            self.root, f"v{UNIFIED_SCHEMA_VERSION}",
            f"dataset={rec.dataset_id}", f"aircraft={rec.aircraft_id}",
            f"flight={rec.flight_id}", f"topic={rec.topic}",
            f"instance={rec.sensor_instance}")
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, "part.parquet")
        df.write_parquet(out, compression="zstd")
        manifest = {
            "raw_sha256": raw_sha256,
            "transform_version": "1.0.0",
            "transform_config_sha256": _transform_config_hash({
                "adapter": rec.provenance.get("adapter"),
                "schema": UNIFIED_SCHEMA_VERSION}),
            "software_commit": _git_commit(),
            "schema_version": UNIFIED_SCHEMA_VERSION,
            "timestamp_alignment": rec.sync_method,
            "unit_policy": rec.normalized_unit,
            "rows": n,
            "quality": quality or {},
            "provenance": rec.provenance,
        }
        with open(os.path.join(d, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=1, sort_keys=True)
        return out


# --- quality (Part 9) ---------------------------------------------------------

def flight_quality(records) -> dict:
    """Per-flight quality report from normalized FlightRecords."""
    topics = {}
    for r in records:
        ts = [t for t in r.columns["timestamp"] if t is not None]
        gaps, regress, dupes = [], 0, 0
        for a, b in zip(ts, ts[1:]):
            d = b - a
            if d < 0:
                regress += 1
            elif d == 0:
                dupes += 1
            else:
                gaps.append(d)
        med = sorted(gaps)[len(gaps) // 2] if gaps else None
        missing = {f: sum(1 for v in col if v is None)
                   for f, col in r.columns.items() if f != "timestamp"}
        topics[f"{r.topic}#{r.sensor_instance}"] = {
            "rows": r.n,
            "duration_s": (ts[-1] - ts[0]) / 1e6 if len(ts) > 1 else 0.0,
            "median_period_us": med,
            "max_gap_us": max(gaps) if gaps else None,
            "timestamp_regressions": regress,
            "duplicate_timestamps": dupes,
            "missing_by_field": {k: v for k, v in missing.items() if v},
            "device_id": r.device_id,
        }
    return {"topics": topics, "topic_count": len(topics)}


def duckdb_summary(normalized_root: str) -> dict:
    """Dataset-level rollup over all normalized Parquet via DuckDB."""
    import duckdb
    glob = os.path.join(normalized_root, "**", "part.parquet")
    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT dataset_id, aircraft_id, flight_id, count(*) AS rows "
            "FROM read_parquet(?, hive_partitioning=false) "
            "GROUP BY 1,2,3 ORDER BY 1,2,3", [glob]).fetchall()
    except Exception as exc:
        return {"error": str(exc), "flights": []}
    return {"flights": [{"dataset_id": r[0], "aircraft_id": r[1],
                         "flight_id": r[2], "rows": r[3]} for r in rows]}


# --- aircraft-level partitions (Part 8) ---------------------------------------

CROSS_DATASET_PARTITIONS = ("DEVELOPMENT", "CALIBRATION", "VALIDATION",
                            "BLIND_TEST", "EXTERNAL_REPLICATION")
#: shares must sum to 1; EXTERNAL_REPLICATION is assigned explicitly, not by
#: hash (it is a policy decision per dataset).
PARTITION_SHARES = (("DEVELOPMENT", 0.40), ("CALIBRATION", 0.15),
                    ("VALIDATION", 0.20), ("BLIND_TEST", 0.25))
PARTITION_SEED = "csia-aceg-slice2-2026-08-03"


def assign_partition(group_id: str) -> str:
    """Deterministic, metadata-only, GROUP-level (aircraft/campaign — never
    rows or windows). Same group => same partition, always."""
    h = hashlib.sha256(f"{PARTITION_SEED}:{group_id}".encode()).hexdigest()
    x = int(h[:8], 16) / 0xFFFFFFFF
    acc = 0.0
    for name, share in PARTITION_SHARES:
        acc += share
        if x < acc:
            return name
    return PARTITION_SHARES[-1][0]


def check_group_leakage(assignments: dict) -> list:
    """assignments: flight_id -> (group_id, partition). A group in two
    partitions is leakage."""
    seen, leaks = {}, []
    for fid, (gid, part) in assignments.items():
        if gid in seen and seen[gid][1] != part:
            leaks.append({"group": gid, "flights": [seen[gid][0], fid],
                          "partitions": [seen[gid][1], part]})
        seen.setdefault(gid, (fid, part))
    return leaks
