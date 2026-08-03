"""Deterministic, metadata-only partition freezing.

Protected partitions must be assigned BEFORE anything about a flight's
signal content is inspected: before CSIA runs, before thresholds are chosen,
before residuals or alerts are looked at. Assigning afterwards — even
honestly — cannot be distinguished from assigning to flatter a result.

Grouping is at the strongest identity available, never per-flight, because
two flights of the same airframe landing on opposite sides of a
DEVELOPMENT/BLIND_TEST split leak the airframe's idiosyncrasies across the
boundary. Tiers, strongest first:

    1. aircraft / vehicle identity
    2. campaign / session identity
    3. source lineage (upstream subdirectory or collection)
    4. stable file-group identity (shared filename stem)
    5. per-flight hash — LAST RESORT, recorded as a weakness

EXTERNAL_REPLICATION is never assigned by hash: holding data back for an
outside party is a policy decision, so it is opt-in per dataset.
"""

import os
import re

from .store import (CROSS_DATASET_PARTITIONS, PARTITION_SEED,
                    PARTITION_SHARES, assign_partition, check_group_leakage)

POLICY_VERSION = "1.0.0"

#: metadata keys that identify an airframe, strongest first
AIRCRAFT_KEYS = ("aircraft_id", "aircraft", "vehicle_id", "vehicle", "uav_id",
                 "uav", "drone_id", "drone", "airframe", "platform",
                 "sys_id", "system_id")
CAMPAIGN_KEYS = ("campaign", "campaign_id", "session", "session_id",
                 "experiment", "experiment_id", "batch", "dataset_session",
                 "collection", "date", "flight_date")
LINEAGE_KEYS = ("source", "source_dir", "origin", "subset", "split_origin",
                "folder", "directory")

TIER_AIRCRAFT = "aircraft_identity"
TIER_CAMPAIGN = "campaign_identity"
TIER_LINEAGE = "source_lineage"
TIER_FILEGROUP = "stable_file_group"
TIER_FLIGHT = "per_flight_hash_LAST_RESORT"

#: trailing run/sortie counter, e.g. log_0042_3.ulg -> log_0042
_STEM_TAIL = re.compile(r"[_\-.]?\d+$")


def _lookup(meta: dict, keys) -> tuple:
    if not isinstance(meta, dict):
        return None, None
    lowered = {str(k).lower(): k for k in meta}
    for want in keys:
        if want in lowered:
            val = meta[lowered[want]]
            if val not in (None, "", [], {}):
                return str(val).strip(), lowered[want]
    return None, None


def _file_group(flight_id: str) -> str:
    stem = os.path.splitext(os.path.basename(str(flight_id)))[0]
    trimmed = _STEM_TAIL.sub("", stem)
    return trimmed or stem


def derive_group(flight_id: str, meta: dict | None) -> dict:
    """Strongest available grouping key for one flight."""
    for keys, tier in ((AIRCRAFT_KEYS, TIER_AIRCRAFT),
                       (CAMPAIGN_KEYS, TIER_CAMPAIGN),
                       (LINEAGE_KEYS, TIER_LINEAGE)):
        val, field = _lookup(meta or {}, keys)
        if val:
            return {"group_id": f"{tier}:{val}", "tier": tier,
                    "field": field, "value": val}
    grp = _file_group(flight_id)
    if grp and grp != os.path.splitext(os.path.basename(str(flight_id)))[0]:
        return {"group_id": f"{TIER_FILEGROUP}:{grp}", "tier": TIER_FILEGROUP,
                "field": "<filename stem>", "value": grp}
    return {"group_id": f"{TIER_FLIGHT}:{flight_id}", "tier": TIER_FLIGHT,
            "field": "<flight id>", "value": str(flight_id)}


def freeze_partitions(flights: dict, snapshot_hash: str, software_commit,
                      assigned_utc: str,
                      external_replication_groups=None) -> dict:
    """Assign every flight to a protected partition, group-coherently.

    `flights` maps flight_id -> {"sha256": ..., "metadata": {...}}. Nothing
    here reads signal content: only identifiers and file hashes.
    """
    external = set(external_replication_groups or ())
    assignments, tier_counts, groups = {}, {}, {}

    for flight_id in sorted(flights):
        rec = flights[flight_id] or {}
        g = derive_group(flight_id, rec.get("metadata"))
        gid = g["group_id"]
        part = ("EXTERNAL_REPLICATION" if gid in external
                else assign_partition(gid))
        tier_counts[g["tier"]] = tier_counts.get(g["tier"], 0) + 1
        groups.setdefault(gid, []).append(flight_id)
        assignments[flight_id] = {
            "flight_id": flight_id,
            "source_sha256": rec.get("sha256"),
            "group_id": gid,
            "group_tier": g["tier"],
            "group_field": g["field"],
            "partition": part,
        }

    # a group split across partitions is leakage by construction
    leakage = check_group_leakage(
        {fid: (a["group_id"], a["partition"])
         for fid, a in assignments.items()})

    counts = {p: 0 for p in CROSS_DATASET_PARTITIONS}
    for a in assignments.values():
        counts[a["partition"]] = counts.get(a["partition"], 0) + 1

    weakest = TIER_FLIGHT if TIER_FLIGHT in tier_counts else None
    return {
        "policy_version": POLICY_VERSION,
        "seed": PARTITION_SEED,
        "shares": {name: share for name, share in PARTITION_SHARES},
        "partitions": list(CROSS_DATASET_PARTITIONS),
        "grouping_tiers_used": dict(sorted(tier_counts.items())),
        "grouping_fields_used": sorted(
            {a["group_field"] for a in assignments.values()}),
        "weakest_grouping_tier": weakest,
        "grouping_warning": (
            "some flights fell back to per-flight hashing: those flights have "
            "NO group protection and must not carry airframe-level "
            "generalization claims" if weakest else None),
        "flight_count": len(assignments),
        "group_count": len(groups),
        "partition_counts": counts,
        "assignments": assignments,
        "leakage": leakage,
        "leakage_free": not leakage,
        "assigned_utc": assigned_utc,
        "software_commit": software_commit,
        "aggregate_snapshot_sha256": snapshot_hash,
        "frozen_before_signal_inspection": True,
        "note": "metadata-only assignment: no signal content was read, no "
                "CSIA output was produced, and no threshold was selected "
                "before this freeze",
    }
