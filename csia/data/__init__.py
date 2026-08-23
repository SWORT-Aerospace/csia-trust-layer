"""CSIA-ACEG data foundation (research layer; embedded runtime imports none of this)."""

from .adapters import (ADAPTERS, UNIFIED_SCHEMA_VERSION, CsvAdapter,
                       DatasetAdapter, FlightRecord, PX4UlogAdapter,
                       VisualInertialAdapter)
from .paths import (ENV_VAR, REPO_FALLBACK, REPO_ROOT, DataRoot, DataRootError,
                    check_free_space, check_writable,
                    require_external_data_root, resolve_data_root)
from .px4_topics import (PX4_ASSURANCE_TOPICS, TOPIC_INDEX, TopicAvailability,
                         survey_ulog)
from .registry import (RegistryError, UnknownDatasetError,
                       acknowledgement_required, dataset_ids, declared_license,
                       doi, get_dataset, load_registry, provider,
                       select_datasets, source_block)
from .snapshot import (aggregate_hash, build_manifest, materialize,
                       provenance_record, write_provenance)
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
    "DataRoot", "DataRootError", "resolve_data_root",
    "require_external_data_root", "check_writable", "check_free_space",
    "ENV_VAR", "REPO_ROOT", "REPO_FALLBACK",
    "load_registry", "dataset_ids", "get_dataset", "select_datasets",
    "acknowledgement_required", "RegistryError", "UnknownDatasetError",
    "provider", "source_block", "doi", "declared_license",
    "build_manifest", "aggregate_hash", "materialize", "provenance_record",
    "write_provenance",
]
