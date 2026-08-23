"""Dataset adapters (ACEG slice 2, Part 7).

One interface per source format. Adapters expose discovery, metadata, topic
inventory, normalization to the unified schema, labels, and a quality report.
Visual/odometry datasets are NOT forced into a PX4 shape — an adapter
declares its modality and unsupported channels instead.
"""

import os
from dataclasses import dataclass, field

UNIFIED_SCHEMA_VERSION = "1.0.0"


@dataclass
class FlightRecord:
    """One normalized sample stream, unified-schema shape (columnar dict)."""
    dataset_id: str
    aircraft_id: str
    flight_id: str
    topic: str
    sensor_instance: int
    columns: dict                       # field -> list (None = missing, NEVER 0)
    source_unit: dict = field(default_factory=dict)
    normalized_unit: dict = field(default_factory=dict)
    device_id: str | None = None
    time_domain: str = "boot_us"
    sync_method: str = "NONE"
    sync_uncertainty_s: float | None = None
    provenance: dict = field(default_factory=dict)

    @property
    def n(self):
        return len(self.columns.get("timestamp", ()))


class DatasetAdapter:
    """Interface. Concrete adapters implement all methods."""

    modality = "UNKNOWN"

    def discover(self, root: str) -> list:
        raise NotImplementedError

    def metadata(self, path: str) -> dict:
        raise NotImplementedError

    def topics(self, path: str) -> dict:
        raise NotImplementedError

    def normalize(self, path: str, dataset_id: str, aircraft_id: str,
                  flight_id: str) -> list:
        raise NotImplementedError

    def labels(self, path: str) -> list:
        """Ground-truth labels. Empty when the dataset has none — never
        inferred."""
        return []

    def unsupported_channels(self) -> list:
        return []


class PX4UlogAdapter(DatasetAdapter):
    """PX4 ULog via pyulog, restricted to the assurance-topic registry."""

    modality = "AUTOPILOT_LOG"

    def discover(self, root):
        out = []
        for dirpath, _, files in os.walk(root):
            out.extend(os.path.join(dirpath, f) for f in files
                       if f.endswith(".ulg"))
        return sorted(out)

    def _load(self, path):
        from pyulog import ULog
        return ULog(path)

    def metadata(self, path):
        u = self._load(path)
        info = {k: (v.decode() if isinstance(v, bytes) else v)
                for k, v in u.msg_info_dict.items()}
        return {"ver_sw": info.get("ver_sw", "UNKNOWN"),
                "sys_name": info.get("sys_name", "UNKNOWN"),
                "sys_uuid": info.get("sys_uuid", "UNKNOWN"),
                "start_timestamp_us": u.start_timestamp,
                "last_timestamp_us": u.last_timestamp,
                "duration_s": (u.last_timestamp - u.start_timestamp) / 1e6}

    def topics(self, path):
        from .px4_topics import survey_ulog
        return survey_ulog(self._load(path)).to_dict()

    def normalize(self, path, dataset_id, aircraft_id, flight_id):
        from .px4_topics import TOPIC_INDEX
        u = self._load(path)
        out = []
        for d in u.data_list:
            spec = TOPIC_INDEX.get(d.name)
            if spec is None:
                continue
            cols = {"timestamp": [int(v) for v in d.data["timestamp"]]}
            n = len(cols["timestamp"])
            wanted = list(spec.key_fields) + list(spec.flag_fields) \
                + list(spec.reset_fields)
            for f in wanted:
                if f in d.data:
                    cols[f] = [float(v) for v in d.data[f]]
                else:
                    cols[f] = [None] * n          # ABSENT, not zero
            dev = None
            for df in spec.device_id_fields:
                if df in d.data and n:
                    dev = str(int(d.data[df][0]))
                    break
            out.append(FlightRecord(
                dataset_id=dataset_id, aircraft_id=aircraft_id,
                flight_id=flight_id, topic=d.name,
                sensor_instance=d.multi_id, columns=cols,
                source_unit={"timestamp": "us"},
                normalized_unit={"timestamp": "us"},
                device_id=dev, time_domain="boot_us",
                sync_method="ULOG_MONOTONIC",
                provenance={"source_file": os.path.basename(path),
                            "source_topic": d.name,
                            "adapter": "PX4UlogAdapter",
                            "schema_version": UNIFIED_SCHEMA_VERSION}))
        return out


class CsvAdapter(DatasetAdapter):
    """Tabular datasets (e.g. ALFA processed CSVs). One file = one topic.

    Column semantics come from a caller-supplied mapping — nothing inferred.
    """

    modality = "TABULAR"

    def __init__(self, column_map: dict, unit_map: dict,
                 timestamp_col: str = "timestamp"):
        self.column_map = column_map
        self.unit_map = unit_map
        self.timestamp_col = timestamp_col

    def discover(self, root):
        out = []
        for dirpath, _, files in os.walk(root):
            out.extend(os.path.join(dirpath, f) for f in files
                       if f.endswith(".csv"))
        return sorted(out)

    def metadata(self, path):
        return {"format": "csv", "bytes": os.path.getsize(path)}

    def topics(self, path):
        import csv
        with open(path, newline="") as fh:
            header = next(csv.reader(fh))
        mapped = [c for c in header if c in self.column_map]
        return {"present": {os.path.basename(path): [0]},
                "columns": header, "mapped": mapped,
                "unmapped": [c for c in header if c not in self.column_map
                             and c != self.timestamp_col]}

    def normalize(self, path, dataset_id, aircraft_id, flight_id):
        import csv
        cols = {"timestamp": []}
        for target in self.column_map.values():
            cols[target] = []
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                ts = row.get(self.timestamp_col, "")
                cols["timestamp"].append(int(float(ts)) if ts != "" else None)
                for src, target in self.column_map.items():
                    v = row.get(src, "")
                    cols[target].append(float(v) if v != "" else None)
        topic = os.path.splitext(os.path.basename(path))[0]
        return [FlightRecord(
            dataset_id=dataset_id, aircraft_id=aircraft_id,
            flight_id=flight_id, topic=topic, sensor_instance=0,
            columns=cols, source_unit=dict(self.unit_map),
            normalized_unit=dict(self.unit_map),
            time_domain="dataset_native", sync_method="NONE",
            provenance={"source_file": os.path.basename(path),
                        "adapter": "CsvAdapter",
                        "schema_version": UNIFIED_SCHEMA_VERSION})]


class VisualInertialAdapter(DatasetAdapter):
    """EuRoC / TUM-VI style. MODALITY EXTENSION — images are referenced, not
    coerced into signal rows; only IMU/ground-truth streams normalize."""

    modality = "VISUAL_INERTIAL"

    def discover(self, root):
        return []          # requires the dataset locally; none acquired

    def unsupported_channels(self):
        return ["camera frames (referenced by path, not normalized)",
                "per-frame exposure metadata"]

    def metadata(self, path):
        return {"status": "NOT_LOCALLY_AVAILABLE"}

    def topics(self, path):
        return {"present": {}, "absent": ["all — dataset not acquired"]}

    def normalize(self, *a, **k):
        raise RuntimeError("VisualInertialAdapter: no local data; acquisition "
                           "package must run on an unrestricted host first")


ADAPTERS = {
    "px4_ulog": PX4UlogAdapter,
    "csv": CsvAdapter,
    "visual_inertial": VisualInertialAdapter,
}
