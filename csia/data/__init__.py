"""CSIA-ACEG data foundation (research layer; embedded runtime imports none of this)."""

from .adapters import (ADAPTERS, UNIFIED_SCHEMA_VERSION, CsvAdapter,
                       DatasetAdapter, FlightRecord, PX4UlogAdapter,
                       VisualInertialAdapter)
from .px4_topics import (PX4_ASSURANCE_TOPICS, TOPIC_INDEX, TopicAvailability,
                         survey_ulog)
from .store import (CROSS_DATASET_PARTITIONS, NormalizedStore, RawStore,
                    assign_partition, check_group_leakage, duckdb_summary,
                    flight_quality, sha256_file)
from .ulog_fixture import write_fixture

__all__ = [
    "FlightRecord", "DatasetAdapter", "PX4UlogAdapter", "CsvAdapter",
    "VisualInertialAdapter", "ADAPTERS", "UNIFIED_SCHEMA_VERSION",
    "PX4_ASSURANCE_TOPICS", "TOPIC_INDEX", "TopicAvailability", "survey_ulog",
    "RawStore", "NormalizedStore", "flight_quality", "duckdb_summary",
    "assign_partition", "check_group_leakage", "CROSS_DATASET_PARTITIONS",
    "sha256_file", "write_fixture",
]
