"""Canonical experiment provenance.

Slice 3A, audit finding F-05. Provenance previously existed in three
fragments that recorded different things: ``perf_regression`` captured a commit,
``benchmark_pi`` captured a platform, ``monte_carlo`` captured a seed. Nothing
captured dataset identity, working-tree cleanliness, configuration hashes, or a
result-schema version, so no committed result could state which code and which
data produced it.

Callers do not assemble provenance by hand — they call ``build()`` and the
environment is collected for them.
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum

MANIFEST_SCHEMA_VERSION = "1.0.0"
RESULT_SCHEMA_VERSION = "1.0.0"
METRIC_DEFINITIONS_VERSION = "1.1.0"   # docs/validation/METRIC_DEFINITIONS.md


class EvidenceEnvironment(str, Enum):
    """Where the evidence came from. Never mix these in one claim."""
    SIMULATION = "SIMULATION"
    SITL = "SITL"
    HIL = "HIL"
    REAL_LOG_REPLAY = "REAL_LOG_REPLAY"
    LIVE_SHADOW_FLIGHT = "LIVE_SHADOW_FLIGHT"
    LIVE_ACTIVE_FLIGHT = "LIVE_ACTIVE_FLIGHT"


def _sh(*cmd) -> str | None:
    try:
        return subprocess.check_output(
            cmd, stderr=subprocess.DEVNULL, text=True, timeout=15).strip()
    except Exception:
        return None


def _config_hash(obj) -> str:
    """Stable hash of a dataclass/dict configuration."""
    if hasattr(obj, "__dataclass_fields__"):
        obj = asdict(obj)
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _dependency_lock_hash() -> str | None:
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    for name in ("requirements.txt", "pyproject.toml"):
        p = os.path.join(root, name)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()[:16]
    return None


def _compiler_info() -> dict:
    cc = _sh("cc", "--version")
    return {"compiler": cc.splitlines()[0] if cc else None,
            "native_flags": "-std=c11 -Wall -Wextra -Wpedantic -Werror -O2"}


@dataclass
class ExperimentManifest:
    """Everything needed to regenerate a result, or to know you cannot."""
    manifest_schema_version: str = MANIFEST_SCHEMA_VERSION
    result_schema_version: str = RESULT_SCHEMA_VERSION
    metric_definitions_version: str = METRIC_DEFINITIONS_VERSION
    experiment_id: str = ""
    experiment_type: str = ""
    evidence_environment: str = EvidenceEnvironment.SIMULATION.value
    timestamp_utc: str = ""
    git_commit: str | None = None
    git_dirty: bool | None = None
    git_remote: str | None = None
    command: str = ""
    python_version: str = ""
    dependency_lock_sha256: str | None = None
    os_platform: str = ""
    processor_arch: str = ""
    compiler: str | None = None
    native_flags: str | None = None
    dataset_id: str | None = None
    dataset_aggregate_hash: str | None = None
    dataset_partition: str | None = None
    input_logs: list = field(default_factory=list)   # [{log_id, sha256}]
    csia_config_hash: str | None = None
    trust_graph_config_hash: str | None = None
    threshold_config_hash: str | None = None
    failsafe_config_hash: str | None = None
    random_seed: int | None = None
    output_paths: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    runtime_duration_s: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=1, sort_keys=True)
        return path


def build(experiment_type: str,
          evidence_environment: EvidenceEnvironment
          = EvidenceEnvironment.SIMULATION,
          dataset_id: str | None = None,
          dataset_aggregate_hash: str | None = None,
          dataset_partition: str | None = None,
          input_logs=None,
          random_seed: int | None = None,
          engine_config=None,
          failsafe_config=None,
          output_paths=None,
          exclusions=None) -> ExperimentManifest:
    """Collect provenance automatically. Callers supply only what is theirs."""
    commit = _sh("git", "rev-parse", "HEAD")
    status = _sh("git", "status", "--porcelain")
    dirty = None if status is None else bool(status.strip())

    if engine_config is None:
        from ..trust_engine.engine import EngineConfig
        engine_config = EngineConfig()
    if failsafe_config is None:
        from ..runtime.failsafe import FailsafeConfig
        failsafe_config = FailsafeConfig()

    try:
        from ..trust_graph import build_trust_graph
        g = build_trust_graph()
        graph_hash = _config_hash({"nodes": list(g.nodes),
                                   "edges": sorted(map(list, g.edges))})
    except Exception:
        graph_hash = None

    ci = _compiler_info()
    return ExperimentManifest(
        experiment_id=f"{experiment_type}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}",
        experiment_type=experiment_type,
        evidence_environment=evidence_environment.value,
        timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        git_commit=commit,
        git_dirty=dirty,
        git_remote=_sh("git", "config", "--get", "remote.origin.url"),
        command=" ".join(sys.argv) if sys.argv else "",
        python_version=platform.python_version(),
        dependency_lock_sha256=_dependency_lock_hash(),
        os_platform=platform.platform(),
        processor_arch=platform.machine(),
        compiler=ci["compiler"],
        native_flags=ci["native_flags"],
        dataset_id=dataset_id,
        dataset_aggregate_hash=dataset_aggregate_hash,
        dataset_partition=dataset_partition,
        input_logs=list(input_logs or []),
        csia_config_hash=_config_hash(engine_config),
        trust_graph_config_hash=graph_hash,
        threshold_config_hash=_config_hash(failsafe_config),
        failsafe_config_hash=_config_hash(failsafe_config),
        random_seed=random_seed,
        output_paths=list(output_paths or []),
        exclusions=list(exclusions or []),
    )


REQUIRED_FIELDS = (
    "manifest_schema_version", "result_schema_version",
    "metric_definitions_version", "experiment_id", "experiment_type",
    "evidence_environment", "timestamp_utc", "git_commit", "git_dirty",
    "command", "python_version", "os_platform", "processor_arch",
    "csia_config_hash", "threshold_config_hash",
)


def validate(manifest) -> list:
    """Return a list of provenance problems; empty means complete."""
    d = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest)
    problems = []
    for f in REQUIRED_FIELDS:
        if d.get(f) in (None, ""):
            problems.append(f"missing required provenance field: {f}")
    if d.get("git_dirty"):
        problems.append(
            "WORKING TREE DIRTY — result is not attributable to a commit")
    env = d.get("evidence_environment")
    if env not in {e.value for e in EvidenceEnvironment}:
        problems.append(f"unknown evidence_environment: {env!r}")
    if env == EvidenceEnvironment.REAL_LOG_REPLAY.value \
            and not d.get("dataset_aggregate_hash"):
        problems.append(
            "real-log replay result carries no dataset_aggregate_hash")
    return problems
