"""Dataset manifests: identity, integrity, provenance and classification.

Slice 3A. The repository previously described its real-log corpus as
"24/26 flights alarm-free" on "0.66 healthy flight hours". Neither adjective
survives inspection: the logs carry no annotation of any kind, so absence of a
reported event is not evidence of health, and 21.8% of the recorded duration
lies inside the failsafe arm window where no alert can be raised at all.

This module makes every one of those distinctions explicit and machine-checked.
Nothing here infers metadata: a field that is not known is ``UNKNOWN``, never
a guess.
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from enum import Enum

MANIFEST_SCHEMA_VERSION = "1.0.0"


class SourceType(str, Enum):
    REAL_FLIGHT = "REAL_FLIGHT"
    SITL = "SITL"
    HIL = "HIL"
    SIMULATION = "SIMULATION"
    UNKNOWN = "UNKNOWN"


class HealthClassification(str, Enum):
    """How the flight's health is *known*, not how it appears.

    VERIFIED_HEALTHY requires positive evidence — a pilot/operator report, a
    maintenance record, or an annotation. "No alert fired" is NOT evidence of
    health: it is the very thing under test, and using it would be circular.
    """
    VERIFIED_HEALTHY = "VERIFIED_HEALTHY"
    VERIFIED_FAULTED = "VERIFIED_FAULTED"
    KNOWN_ANOMALY = "KNOWN_ANOMALY"
    UNANNOTATED = "UNANNOTATED"
    UNKNOWN = "UNKNOWN"
    UNUSABLE = "UNUSABLE"


class AnnotationStatus(str, Enum):
    ANNOTATED = "ANNOTATED"
    PARTIALLY_ANNOTATED = "PARTIALLY_ANNOTATED"
    UNANNOTATED = "UNANNOTATED"


class Partition(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    THRESHOLD_TUNING = "THRESHOLD_TUNING"
    REGRESSION = "REGRESSION"
    HELD_OUT_EVALUATION = "HELD_OUT_EVALUATION"
    BLIND_EXTERNAL = "BLIND_EXTERNAL"
    UNASSIGNED = "UNASSIGNED"


#: Partitions that must never share a split_group_id with one another.
RESTRICTED_PARTITIONS = frozenset({
    Partition.THRESHOLD_TUNING, Partition.REGRESSION,
    Partition.HELD_OUT_EVALUATION, Partition.BLIND_EXTERNAL})


class Confidentiality(str, Enum):
    PUBLIC = "PUBLIC"
    CLIENT_CONFIDENTIAL = "CLIENT_CONFIDENTIAL"
    INTERNAL = "INTERNAL"
    UNKNOWN = "UNKNOWN"


class Redistribution(str, Enum):
    PERMITTED = "PERMITTED"
    PROHIBITED = "PROHIBITED"
    UNKNOWN = "UNKNOWN"


#: Channels CSIA needs before a log can exercise the full trust graph.
REQUIRED_CHANNELS = ("imu0", "imu1", "baro", "mag", "gps",
                     "motor_esc", "battery", "vibration")

UNKNOWN = "UNKNOWN"


@dataclass
class LogManifest:
    """One flight log. Field names match dataset_manifest_v1.schema.json."""
    log_id: str
    dataset_id: str
    content_sha256: str | None = None      # None = file not present locally
    byte_size: int | None = None
    source_type: str = SourceType.UNKNOWN.value
    source_reference: str | None = None
    retrieved_at: str | None = None
    autopilot: str = UNKNOWN
    firmware_version: str | None = None
    airframe_type: str | None = None
    vehicle_id: str | None = None
    campaign_id: str | None = None
    mission_id: str | None = None
    flight_duration_s: float = 0.0
    monitored_duration_s: float = 0.0      # duration the failsafe could alert in
    sensor_inventory: list = field(default_factory=list)
    available_channels: list = field(default_factory=list)
    missing_channels: list = field(default_factory=list)
    annotation_status: str = AnnotationStatus.UNANNOTATED.value
    health_classification: str = HealthClassification.UNKNOWN.value
    known_faults: list = field(default_factory=list)
    known_anomalies: list = field(default_factory=list)
    confidentiality: str = Confidentiality.UNKNOWN.value
    redistribution_permission: str = Redistribution.UNKNOWN.value
    license: str | None = None
    dataset_partition: str = Partition.UNASSIGNED.value
    split_group_id: str | None = None
    used_for_threshold_tuning: bool = False
    used_for_architecture_design: bool = False
    eligible_for_blind_evaluation: bool = False
    file_present: bool = False
    parse_status: str = UNKNOWN
    exclusion_reason: str | None = None
    duplicate_of: str | None = None
    suspected_near_duplicate_of: list = field(default_factory=list)
    alert_episodes: int = 0
    notes: list = field(default_factory=list)

    @property
    def excluded(self) -> bool:
        return self.exclusion_reason is not None

    @property
    def counts_toward_exposure(self) -> bool:
        """Duplicates and excluded logs must not inflate exposure totals."""
        return not self.excluded and self.duplicate_of is None

    def to_dict(self) -> dict:
        return asdict(self)


# --- integrity ---------------------------------------------------------------

def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_log_id(filename: str) -> str:
    """Identity from the source reference, stable across re-download.

    PX4 Flight Review logs are ``fr_<uuid>.ulg``; the UUID is the server-side
    identity and is preserved. Anything else falls back to its basename, so an
    id never silently depends on a local path.
    """
    base = os.path.basename(filename)
    if base.startswith("fr_") and base.endswith(".ulg"):
        return base[3:-4]
    return os.path.splitext(base)[0]


def dataset_aggregate_hash(manifests) -> str:
    """Order-independent hash over per-log identity+content.

    Changes if any log's content changes, is added, or is removed — so a
    result can be pinned to the exact corpus that produced it. Logs whose
    content hash is unknown contribute their id and a NULL marker, so a
    manifest-only corpus still hashes deterministically.
    """
    parts = sorted(f"{m.log_id}:{m.content_sha256 or 'NULL'}" for m in manifests)
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


# --- integrity validation -----------------------------------------------------

def verify_files(manifests, root: str) -> dict:
    """Check manifest ↔ filesystem consistency. Mutates nothing."""
    missing, corrupted, ok, absent = [], [], [], []
    for m in manifests:
        path = os.path.join(root, f"fr_{m.log_id}.ulg")
        if not os.path.exists(path):
            (missing if m.file_present else absent).append(m.log_id)
            continue
        if m.content_sha256 is None:
            ok.append(m.log_id)
            continue
        if sha256_file(path) != m.content_sha256:
            corrupted.append(m.log_id)
        else:
            ok.append(m.log_id)
    return {"verified": ok, "missing": missing, "corrupted": corrupted,
            "not_yet_acquired": absent}


# --- deduplication ------------------------------------------------------------

def find_exact_duplicates(manifests) -> dict:
    """content_sha256 -> [log_id, ...] for hashes appearing more than once."""
    by_hash: dict = {}
    for m in manifests:
        if m.content_sha256:
            by_hash.setdefault(m.content_sha256, []).append(m.log_id)
    return {h: sorted(ids) for h, ids in by_hash.items() if len(ids) > 1}


def find_suspected_near_duplicates(manifests, duration_tol_s: float = 0.05):
    """Conservative near-duplicate CANDIDATES. Never authoritative.

    Signals combined: identical (to tolerance) duration, identical sensor
    inventory, and matching vehicle id where known. Duration alone is a weak
    signal, so a pair matching ONLY on duration is reported with lower
    confidence rather than asserted. Nothing is deleted or auto-excluded.
    """
    out = []
    ms = [m for m in manifests if m.counts_toward_exposure]
    for i in range(len(ms)):
        for j in range(i + 1, len(ms)):
            a, b = ms[i], ms[j]
            if abs(a.flight_duration_s - b.flight_duration_s) > duration_tol_s:
                continue
            signals = ["duration"]
            if sorted(a.sensor_inventory) == sorted(b.sensor_inventory):
                signals.append("sensor_inventory")
            if a.vehicle_id and a.vehicle_id == b.vehicle_id:
                signals.append("vehicle_id")
            if a.firmware_version and a.firmware_version == b.firmware_version:
                signals.append("firmware")
            out.append({
                "log_a": a.log_id, "log_b": b.log_id,
                "duration_s": a.flight_duration_s,
                "matching_signals": signals,
                "confidence": ("LOW" if len(signals) == 1 else
                               "MEDIUM" if len(signals) == 2 else "HIGH"),
                "action": "REVIEW_REQUIRED — not excluded automatically",
            })
    return out


# --- partition leakage --------------------------------------------------------

def check_split_leakage(manifests) -> list:
    """A split_group_id appearing in >1 restricted partition is leakage."""
    groups: dict = {}
    for m in manifests:
        if m.split_group_id is None:
            continue
        try:
            p = Partition(m.dataset_partition)
        except ValueError:
            continue
        if p in RESTRICTED_PARTITIONS:
            groups.setdefault(m.split_group_id, {}).setdefault(
                p.value, []).append(m.log_id)
    return [{"split_group_id": g, "partitions": parts}
            for g, parts in sorted(groups.items()) if len(parts) > 1]


def check_tuning_not_heldout(manifests) -> list:
    """A log used for tuning or design can never be held out or blind."""
    bad = []
    for m in manifests:
        contaminated = m.used_for_threshold_tuning or m.used_for_architecture_design
        heldout = m.dataset_partition in (Partition.HELD_OUT_EVALUATION.value,
                                          Partition.BLIND_EXTERNAL.value)
        if contaminated and heldout:
            bad.append({"log_id": m.log_id,
                        "partition": m.dataset_partition,
                        "used_for_threshold_tuning": m.used_for_threshold_tuning,
                        "used_for_architecture_design":
                            m.used_for_architecture_design})
        if m.eligible_for_blind_evaluation and contaminated:
            bad.append({"log_id": m.log_id,
                        "reason": "marked blind-eligible but was seen in development"})
    return bad


# --- persistence --------------------------------------------------------------

def save_manifests(manifests, path: str, dataset_id: str, notes=None) -> dict:
    doc = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_aggregate_hash": dataset_aggregate_hash(manifests),
        "log_count": len(manifests),
        "notes": notes or [],
        "logs": [m.to_dict() for m in manifests],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    return doc


def load_manifests(path: str):
    with open(path) as fh:
        doc = json.load(fh)
    return [LogManifest(**row) for row in doc["logs"]], doc
