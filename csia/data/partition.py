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
                 "sys_uuid", "vehicle_uuid", "system_uuid", "sys_id",
                 "system_id")
CAMPAIGN_KEYS = ("campaign", "campaign_id", "experiment", "experiment_id",
                 "batch", "collection", "source_campaign")
SESSION_KEYS = ("session", "session_id", "flight_session", "dataset_session",
                "date", "flight_date", "recording_date", "time_ref_utc")
LINEAGE_KEYS = ("source", "source_dir", "origin", "subset", "split_origin",
                "folder", "directory")

TIER_AIRCRAFT = "aircraft_identity"
TIER_CAMPAIGN = "campaign_identity"
TIER_SESSION = "session_identity"
TIER_LINEAGE = "source_lineage"
TIER_FILEGROUP = "stable_file_group"
TIER_FLIGHT = "per_flight_hash_LAST_RESORT"

#: partition-quality classification, strongest first
QUALITY_AIRCRAFT = "AIRCRAFT_GROUPED"
QUALITY_CAMPAIGN = "CAMPAIGN_GROUPED"
QUALITY_SESSION = "SESSION_GROUPED"
QUALITY_LINEAGE = "SOURCE_LINEAGE_GROUPED"
QUALITY_FILE = "FILE_GROUPED"
QUALITY_UNGROUPED = "UNGROUPED_FLIGHT_HASH"

TIER_TO_QUALITY = {
    TIER_AIRCRAFT: QUALITY_AIRCRAFT,
    TIER_CAMPAIGN: QUALITY_CAMPAIGN,
    TIER_SESSION: QUALITY_SESSION,
    TIER_LINEAGE: QUALITY_LINEAGE,
    TIER_FILEGROUP: QUALITY_FILE,
    TIER_FLIGHT: QUALITY_UNGROUPED,
}
#: weakest last — overall quality is the WEAKEST tier present (fail closed)
QUALITY_ORDER = (QUALITY_AIRCRAFT, QUALITY_CAMPAIGN, QUALITY_SESSION,
                 QUALITY_LINEAGE, QUALITY_FILE, QUALITY_UNGROUPED)

#: qualities strong enough to call the protected split a blind test
STRONG_QUALITIES = (QUALITY_AIRCRAFT, QUALITY_CAMPAIGN, QUALITY_SESSION,
                    QUALITY_LINEAGE)

#: protected-partition label per quality class
HOLDOUT_LABEL = {
    QUALITY_AIRCRAFT: "BLIND_TEST",
    QUALITY_CAMPAIGN: "BLIND_TEST",
    QUALITY_SESSION: "BLIND_TEST",
    QUALITY_LINEAGE: "BLIND_TEST",
    QUALITY_FILE: "FILE_LEVEL_HOLDOUT",
    QUALITY_UNGROUPED: "UNGROUPED_HOLDOUT",
}

#: claims that require vehicle-level grouping and nothing weaker
AIRCRAFT_LEVEL_CLAIMS = (
    "unseen-aircraft generalization",
    "aircraft-level transfer",
    "independent vehicle validation",
)


def partition_quality(tier_counts: dict) -> str:
    """Overall quality = the WEAKEST tier any flight relied on.

    Fail closed: one ungrouped flight in a protected split is enough to
    invalidate an aircraft-level claim over the whole corpus.
    """
    present = {TIER_TO_QUALITY[t] for t in tier_counts if t in TIER_TO_QUALITY}
    for q in reversed(QUALITY_ORDER):
        if q in present:
            return q
    return QUALITY_UNGROUPED


def claim_policy(quality: str) -> dict:
    """What this grouping quality does and does not license."""
    strong = quality in STRONG_QUALITIES
    aircraft = quality == QUALITY_AIRCRAFT
    permitted = ["within-corpus detection and false-alert characterization"]
    if strong:
        permitted.append(f"held-out evaluation on {HOLDOUT_LABEL[quality]}")
    if aircraft:
        permitted.append("aircraft-level held-out evaluation")
    prohibited = []
    if not aircraft:
        prohibited.extend(AIRCRAFT_LEVEL_CLAIMS)
    if not strong:
        prohibited.append("any claim that the holdout is externally blind")
        prohibited.append("aircraft-independent generalization")
    return {
        "partition_quality": quality,
        "protected_partition_label": HOLDOUT_LABEL[quality],
        "blind_test_label_permitted": strong,
        "aircraft_level_blind_claim_permitted": aircraft,
        "permitted_evaluation_claims": permitted,
        "prohibited_claims": prohibited,
        "rationale": (
            "vehicle-level grouping present: flights of one airframe never "
            "straddle the protected boundary"
            if aircraft else
            f"best grouping is {quality}: the same airframe can appear on "
            f"both sides of the boundary, so vehicle-level generalization is "
            f"not evidenced"
            if strong else
            f"grouping is {quality}: the protected split is a "
            f"{HOLDOUT_LABEL[quality]}, not a blind test"),
    }

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
                       (SESSION_KEYS, TIER_SESSION),
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
                      assigned_utc: str, external_replication_groups=None,
                      labels: dict | None = None,
                      grouping_audit: dict | None = None) -> dict:
    """Assign every flight to a protected partition, group-coherently.

    `flights` maps flight_id -> {"sha256": ..., "metadata": {...}}. Nothing
    here reads signal content: only identifiers, file hashes, and (for
    balance reporting) the annotation labels already present in mapping.json.
    """
    external = set(external_replication_groups or ())
    labels = labels or {}
    assignments, tier_counts, groups = {}, {}, {}

    for flight_id in sorted(flights):
        rec = flights[flight_id] or {}
        g = derive_group(flight_id, rec.get("metadata"))
        gid = g["group_id"]
        tier_counts[g["tier"]] = tier_counts.get(g["tier"], 0) + 1
        groups.setdefault(gid, []).append(flight_id)
        assignments[flight_id] = {
            "flight_id": flight_id,
            "source_sha256": rec.get("sha256"),
            "group_id": gid,
            "group_tier": g["tier"],
            "group_field": g["field"],
            "label": labels.get(flight_id),
        }

    quality = partition_quality(tier_counts)
    policy = claim_policy(quality)
    holdout = policy["protected_partition_label"]

    # The protected slot is renamed, not just annotated: a manifest that says
    # BLIND_TEST when the grouping cannot support one is how an unsupported
    # claim gets made downstream by someone reading only the label.
    for fid, a in assignments.items():
        part = ("EXTERNAL_REPLICATION" if a["group_id"] in external
                else assign_partition(a["group_id"]))
        a["partition"] = holdout if part == "BLIND_TEST" else part

    leakage = check_group_leakage(
        {fid: (a["group_id"], a["partition"])
         for fid, a in assignments.items()})

    counts = {(holdout if p == "BLIND_TEST" else p): 0
              for p in CROSS_DATASET_PARTITIONS}
    for a in assignments.values():
        counts[a["partition"]] = counts.get(a["partition"], 0) + 1

    sizes = sorted(len(v) for v in groups.values())
    dist = {}
    for n in sizes:
        dist[str(n)] = dist.get(str(n), 0) + 1

    labels_by_partition, families_by_partition = {}, {}
    for a in assignments.values():
        p = a["partition"]
        lab = a.get("label")
        bucket = labels_by_partition.setdefault(p, {})
        key = "UNLABELLED" if lab in (None, "", []) else str(lab)
        bucket[key] = bucket.get(key, 0) + 1
        if lab not in (None, "", []):
            fam = families_by_partition.setdefault(p, {})
            for one in (lab if isinstance(lab, list) else [lab]):
                fam[str(one)] = fam.get(str(one), 0) + 1

    risks = []
    if len(groups) < 2:
        risks.append(
            "DEGENERATE: every flight fell into a single group, so no "
            "protected split exists — the grouping key is a naming "
            "convention, not an identity")
    if quality in (QUALITY_FILE, QUALITY_UNGROUPED):
        risks.append(f"grouping is {quality}: flights of one airframe can "
                     f"appear in both training and protected partitions")
    if any(n == 1 for n in sizes):
        risks.append(f"{sum(1 for n in sizes if n == 1)} singleton group(s) "
                     f"carry no within-group generalization evidence")
    if grouping_audit and grouping_audit.get("collisions", {}).get(
            "collision_count"):
        risks.append(
            f"{grouping_audit['collisions']['collision_count']} related-file "
            f"collision(s) reported by the grouping audit")
    if leakage:
        risks.append(f"{len(leakage)} group(s) straddle a partition boundary")

    return {
        "policy_version": POLICY_VERSION,
        "seed": PARTITION_SEED,
        "shares": {name: share for name, share in PARTITION_SHARES},
        "partitions": sorted(counts),
        "partition_quality": quality,
        "protected_partition_label": holdout,
        "blind_test_label_permitted": policy["blind_test_label_permitted"],
        "aircraft_level_blind_claim_permitted":
            policy["aircraft_level_blind_claim_permitted"],
        "permitted_evaluation_claims": policy["permitted_evaluation_claims"],
        "prohibited_claims": policy["prohibited_claims"],
        "claim_rationale": policy["rationale"],
        "grouping_tiers_used": dict(sorted(tier_counts.items())),
        "grouping_fields_used": sorted(
            {a["group_field"] for a in assignments.values()}),
        "weakest_grouping_tier": (TIER_FLIGHT if TIER_FLIGHT in tier_counts
                                  else None),
        "grouping_warning": (
            "some flights fell back to per-flight hashing: those flights have "
            "NO group protection and must not carry airframe-level "
            "generalization claims"
            if TIER_FLIGHT in tier_counts else None),
        "flight_count": len(assignments),
        "group_count": len(groups),
        "group_size_distribution": dist,
        "group_size_min": sizes[0] if sizes else 0,
        "group_size_max": sizes[-1] if sizes else 0,
        "suspected_related_file_collisions": (
            (grouping_audit or {}).get("collisions", {})
            .get("related_file_collisions", [])),
        "partition_counts": counts,
        "label_distribution_by_partition": labels_by_partition,
        "anomaly_family_distribution_by_partition": families_by_partition,
        "potential_leakage_risks": risks,
        "assignments": assignments,
        "leakage": leakage,
        "leakage_free": not leakage,
        "assigned_utc": assigned_utc,
        "software_commit": software_commit,
        "aggregate_snapshot_sha256": snapshot_hash,
        "grouping_audit_summary": {
            "selected_rule": (grouping_audit or {}).get(
                "selected_grouping_rule"),
            "limitations": (grouping_audit or {}).get(
                "scientific_limitations", []),
        } if grouping_audit else None,
        "frozen_before_signal_inspection": True,
        "note": "metadata-only assignment: no signal content was read, no "
                "CSIA output was produced, and no threshold was selected "
                "before this freeze",
    }
