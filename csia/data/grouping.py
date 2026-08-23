"""Recover legitimate grouping metadata before partitions are frozen.

Protected partitions are only as strong as the identity they group by. This
module hunts for real identity — aircraft, campaign, session, lineage — in
mapping metadata, directory structure, filenames, and ULog *header* info,
then reports honestly how good the best available option is.

Two rules govern what happens here:

  * Only metadata is read. ULog parsing is restricted to the header info
    dictionary (`message_name_filter_list=[]` parses no topic data), so no
    signal content, residual, or anomaly evidence is ever touched.
  * Identity is never fabricated. A filename is accepted as an aircraft id
    only when a documented deterministic rule matches and is verified across
    the corpus; otherwise the field is REJECTED and the weakness recorded.
"""

import os
import re

#: field names by identity class, checked in this order
FIELD_CLASSES = (
    ("aircraft", ("aircraft_id", "aircraft", "vehicle_id", "vehicle",
                  "uav_id", "uav", "drone_id", "drone", "airframe",
                  "platform", "sys_uuid", "vehicle_uuid", "system_uuid",
                  "sys_id", "system_id", "device_uuid")),
    ("campaign", ("campaign", "campaign_id", "experiment", "experiment_id",
                  "batch", "collection", "source_campaign")),
    ("session", ("session", "session_id", "flight_session", "date",
                 "flight_date", "recording_date", "day", "time_ref_utc")),
    ("lineage", ("source", "source_dir", "origin", "subset", "folder",
                 "directory", "split_origin")),
)

#: ULog header info keys that carry identity, never signal content
ULOG_IDENTITY_KEYS = ("sys_uuid", "ver_hw", "ver_hw_subtype", "ver_sw",
                      "ver_sw_release", "sys_name", "sys_os_name",
                      "sys_os_ver", "time_ref_utc", "replay")

#: a stem shared by more than this many files is a generic prefix, not an
#: identity — treating it as one would invent aircraft that do not exist
GENERIC_STEM_THRESHOLD = 8

_STEM_TAIL = re.compile(r"[_\-.]?\d+$")


def normalized_stem(path: str) -> str:
    stem = os.path.splitext(os.path.basename(str(path)))[0]
    return _STEM_TAIL.sub("", stem) or stem


def ulog_identity(path: str) -> dict:
    """Header-only identity fields from a ULog. Parses NO topic data."""
    try:
        from pyulog import ULog
    except ImportError:
        return {}
    try:
        # empty filter list => header/info parsed, zero data messages
        log = ULog(path, message_name_filter_list=[])
    except Exception:
        return {}
    info = dict(getattr(log, "msg_info_dict", {}) or {})
    return {k: str(info[k]) for k in ULOG_IDENTITY_KEYS if k in info}


def _profile(values: dict, total: int) -> dict:
    """Completeness / uniqueness / consistency of one candidate field."""
    present = {k: v for k, v in values.items() if v not in (None, "", [], {})}
    distinct = sorted({str(v) for v in present.values()})
    sizes = {}
    for v in present.values():
        sizes[str(v)] = sizes.get(str(v), 0) + 1
    return {
        "completeness": round(len(present) / total, 4) if total else 0.0,
        "populated": len(present),
        "missing": total - len(present),
        "unique_values": len(distinct),
        "uniqueness_ratio": (round(len(distinct) / len(present), 4)
                             if present else 0.0),
        "group_size_min": min(sizes.values()) if sizes else 0,
        "group_size_max": max(sizes.values()) if sizes else 0,
        "singleton_groups": sum(1 for n in sizes.values() if n == 1),
        "example_values": distinct[:5],
    }


def _usable(prof: dict, total: int) -> tuple:
    """Is a candidate strong enough to group by? Returns (ok, reason)."""
    if prof["completeness"] < 1.0:
        return False, (f"incomplete: {prof['missing']} of {total} flights "
                       f"have no value")
    if prof["unique_values"] < 2:
        return False, "degenerate: a single value covers every flight"
    if prof["unique_values"] == prof["populated"]:
        return False, ("value is unique per flight — it identifies flights, "
                       "not a shared airframe or campaign")
    return True, "complete, non-degenerate, and shared across flights"


def collect_candidates(flights: dict, ulg_dir: str | None = None,
                       read_ulog: bool = True) -> dict:
    """Gather every candidate grouping field from all permitted sources."""
    total = len(flights)
    sources, per_field = {}, {}

    def record(field, source, flight_id, value):
        per_field.setdefault(field, {})[flight_id] = value
        sources[field] = source

    for fid, rec in flights.items():
        meta = (rec or {}).get("metadata") or {}
        for key, val in (meta.items() if isinstance(meta, dict) else []):
            record(f"mapping:{key}", "mapping.json", fid, val)

        rel = (rec or {}).get("relative_path") or fid
        parent = os.path.dirname(str(rel).replace("\\", "/"))
        if parent and parent not in (".", "ulg_files"):
            record("path:parent_directory", "directory structure", fid,
                   parent.split("/")[-1])
        record("filename:normalized_stem", "file name", fid,
               normalized_stem(fid))

        if read_ulog and ulg_dir:
            p = os.path.join(ulg_dir, os.path.basename(str(fid)))
            if os.path.isfile(p):
                for k, v in ulog_identity(p).items():
                    record(f"ulog:{k}", "ULog header info", fid, v)

    candidates = {}
    for field, values in sorted(per_field.items()):
        prof = _profile(values, total)
        ok, reason = _usable(prof, total)
        cls = None
        bare = field.split(":", 1)[1].lower()
        for name, keys in FIELD_CLASSES:
            if bare in keys:
                cls = name
                break
        if field == "path:parent_directory":
            cls = cls or "lineage"
        candidates[field] = dict(prof, source=sources[field],
                                 identity_class=cls, usable=ok,
                                 assessment=reason)
    return candidates


def detect_collisions(assign_group, flights: dict) -> dict:
    """Files that look related but were grouped apart.

    A shared filename stem is only treated as evidence of relatedness when
    it is specific: a stem covering more than GENERIC_STEM_THRESHOLD files is
    a naming convention, not an identity, and flagging it would invent
    relationships that do not exist.
    """
    by_stem = {}
    for fid in flights:
        by_stem.setdefault(normalized_stem(fid), []).append(fid)

    collisions, generic = [], []
    for stem, members in sorted(by_stem.items()):
        if len(members) < 2:
            continue
        if len(members) > GENERIC_STEM_THRESHOLD:
            generic.append({"stem": stem, "files": len(members)})
            continue
        groups = {assign_group(f) for f in members}
        if len(groups) > 1:
            collisions.append({"stem": stem, "files": sorted(members),
                               "groups": sorted(groups)})
    return {
        "related_file_collisions": collisions,
        "collision_count": len(collisions),
        "generic_stems_ignored": generic,
        "generic_stem_threshold": GENERIC_STEM_THRESHOLD,
    }


def audit_grouping(flights: dict, ulg_dir: str | None = None,
                   read_ulog: bool = True) -> dict:
    """Full grouping audit: candidates, selection, rejections, limitations."""
    total = len(flights)
    candidates = collect_candidates(flights, ulg_dir, read_ulog)

    ranked, rejected = [], []
    for cls, _ in FIELD_CLASSES:
        for field, c in candidates.items():
            if c["identity_class"] != cls:
                continue
            (ranked if c["usable"] else rejected).append(
                {"field": field, "identity_class": cls, **c})
    for field, c in candidates.items():
        if c["identity_class"] is None:
            rejected.append({"field": field, "identity_class": None,
                             "reason": "field does not name a known identity "
                                       "class (aircraft/campaign/session/"
                                       "lineage)", **c})
    for r in rejected:
        r.setdefault("reason", r.get("assessment"))

    selected = ranked[0] if ranked else None
    limitations = []
    if selected is None:
        limitations.append(
            "no complete, non-degenerate identity field was found: grouping "
            "must fall back to filename stems or per-flight hashing, which "
            "cannot support any aircraft-level generalization claim")
    elif selected["identity_class"] != "aircraft":
        limitations.append(
            f"best available identity is {selected['identity_class']!r}, not "
            f"aircraft: the same airframe may appear in more than one "
            f"{selected['identity_class']}, so unseen-aircraft claims are "
            f"NOT supported")
    if selected and selected["singleton_groups"]:
        limitations.append(
            f"{selected['singleton_groups']} group(s) contain a single "
            f"flight; those carry no within-group generalization evidence")

    def assign(fid):
        """Group id a flight would receive under the selected rule."""
        if selected is None:
            return normalized_stem(fid)
        bare = selected["field"].split(":", 1)[1]
        meta = (flights.get(fid) or {}).get("metadata") or {}
        for key, val in meta.items():
            if str(key).lower() == bare.lower():
                return str(val)
        return normalized_stem(fid)

    coll = detect_collisions(assign, flights)
    if coll["collision_count"]:
        limitations.append(
            f"{coll['collision_count']} related-file collision(s): files "
            f"sharing a specific name stem were assigned different groups — "
            f"partitioning refuses until this is resolved")

    return {
        "audit_version": "1.0.0",
        "flight_count": total,
        "ulog_header_metadata_read": bool(read_ulog and ulg_dir),
        "signal_content_read": False,
        "candidate_fields": candidates,
        "candidate_count": len(candidates),
        "ranked_usable_fields": [r["field"] for r in ranked],
        "selected_grouping_rule": selected,
        "rejected_grouping_rules": rejected,
        "collisions": coll,
        "scientific_limitations": limitations,
        "safe_to_partition": coll["collision_count"] == 0,
        "note": "metadata and ULog header info only; no topic data, no "
                "residual, no CSIA output was read",
    }
