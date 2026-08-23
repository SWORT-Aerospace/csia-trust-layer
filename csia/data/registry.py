"""Public-dataset registry parsing.

The registry is a MAPPING keyed by dataset id, not a list:

    registry_version: "1.0.0"
    datasets:
      uav_sead: {title: ..., licensing: {...}, ...}
      alfa:     {...}

An absent, non-mapping, or empty `datasets` block is FATAL. The failure this
module exists to prevent is a tool reporting "0/0 complete" — a
success-shaped message for a registry that was never read.
"""

import os

from .paths import REPO_ROOT

DEFAULT_REGISTRY = os.path.join(REPO_ROOT, "datasets", "registry",
                                "public_datasets_v1.yaml")

#: licensing values that require an explicit --acknowledge-license
RESTRICTED_VALUES = {"RESTRICTED", "RESEARCH_ONLY", "NO"}


class RegistryError(RuntimeError):
    """Registry is missing, malformed, or empty."""


class UnknownDatasetError(RegistryError):
    """Caller asked for a dataset id the registry does not define."""


def load_registry(path: str | None = None) -> dict:
    import yaml
    path = os.path.abspath(path or DEFAULT_REGISTRY)
    if not os.path.isfile(path):
        raise RegistryError(f"registry not found: {path}")
    with open(path) as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise RegistryError(
            f"registry root must be a mapping with keys 'registry_version' "
            f"and 'datasets', got {type(doc).__name__}: {path}")
    datasets = doc.get("datasets")
    if datasets is None:
        raise RegistryError(f"registry has no 'datasets' block: {path}")
    if not isinstance(datasets, dict):
        raise RegistryError(
            f"'datasets' must be a mapping keyed by dataset id, got "
            f"{type(datasets).__name__}: {path}")
    if not datasets:
        raise RegistryError(
            f"registry declares zero datasets: {path} — refusing to report "
            f"'0/0 complete', which reads as success for a broken registry")
    return {"registry_version": doc.get("registry_version"),
            "datasets": datasets, "path": path}


def dataset_ids(reg: dict) -> list:
    return sorted(reg["datasets"])


def get_dataset(reg: dict, dataset_id: str) -> dict:
    try:
        return reg["datasets"][dataset_id]
    except KeyError:
        raise UnknownDatasetError(
            f"unknown dataset id {dataset_id!r}. Valid ids: "
            f"{', '.join(dataset_ids(reg))}") from None


def select_datasets(reg: dict, ids=None, all_: bool = False) -> list:
    """Resolve the requested selection, validating every id up front."""
    if all_ or not ids:
        return dataset_ids(reg)
    unknown = [i for i in ids if i not in reg["datasets"]]
    if unknown:
        raise UnknownDatasetError(
            f"unknown dataset id(s): {', '.join(sorted(unknown))}. "
            f"Valid ids: {', '.join(dataset_ids(reg))}")
    # de-duplicate, preserve caller order
    return list(dict.fromkeys(ids))


def licensing(entry: dict) -> dict:
    lic = entry.get("licensing") or {}
    return {
        "license": lic.get("license", "UNKNOWN"),
        "commercial_use": lic.get("commercial_use", "UNKNOWN"),
        "redistribution": lic.get("redistribution", "UNKNOWN"),
        "citation_required": lic.get("citation_required"),
        "attribution_requirement": lic.get("attribution_requirement"),
    }


def acknowledgement_required(entry: dict) -> bool:
    """A restricted licence must be acknowledged before any download.

    Fails CLOSED: an unparseable licensing block counts as restricted.
    """
    lic = licensing(entry)
    for key in ("commercial_use", "redistribution"):
        if str(lic.get(key, "")).strip().upper() in RESTRICTED_VALUES:
            return True
    return "RESEARCH-ONLY" in str(lic.get("license", "")).upper()


def expected_size_bytes(entry: dict) -> int | None:
    spec = entry.get("published_specification") or {}
    gb = spec.get("approx_size_gb")
    if isinstance(gb, (int, float)) and gb > 0:
        return int(gb * (1 << 30))
    return None


def source_block(entry: dict) -> dict:
    src = entry.get("source")
    return src if isinstance(src, dict) else {}


def provider(entry: dict) -> str:
    """Acquisition backend for this dataset. 'url' is the legacy default."""
    return str(source_block(entry).get("provider") or "url").lower()


def doi(entry: dict):
    return source_block(entry).get("doi")


def declared_license(entry: dict):
    return licensing(entry).get("license")


def expected_inventory(entry: dict) -> list:
    spec = entry.get("published_specification") or {}
    files = spec.get("archive_files")
    if isinstance(files, list) and files:
        return list(files)
    return ["UNKNOWN — confirm the archive inventory from the official "
            "source page before downloading"]
