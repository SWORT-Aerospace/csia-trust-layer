"""Hugging Face Hub dataset backend.

Uses the official `huggingface_hub` client — never HTML scraping, never
hardcoded per-file URLs, both of which break silently when a repository is
reorganized.

Revision policy: a dataset is NEVER acquired from a moving `main`. The Hub
API resolves `main` to a commit SHA, that SHA is recorded, and the download
is pinned to it, so the snapshot is reproducible after the branch advances.

Every Hub-touching call lives in this module so the rest of the pipeline —
and the test suite — can exercise the acquisition path with no network.
"""

import fnmatch
import inspect
import os

#: Repository paths CSIA acquires. `ulg_files` is the repository's own
#: spelling and is preserved verbatim: renaming it during raw acquisition
#: would break provenance against the published repository.
ALLOW_PATTERNS = [
    "ulg_files/**",
    "mapping.json",
    "README.md",
    ".gitattributes",
]

#: free-space margin over the Hub-reported total
MARGIN_KNOWN = 1.25
#: margin when the Hub cannot report every file size
MARGIN_UNKNOWN = 2.0
#: absolute floor required when the total size is unknown entirely
CONSERVATIVE_FLOOR_BYTES = 64 * (1 << 30)


class HubError(RuntimeError):
    """Hub API unreachable, repository missing, or metadata unusable."""


def matches_allow(path: str, patterns=None) -> bool:
    """True when a repository-relative path is inside the acquisition scope."""
    for pat in (patterns if patterns is not None else ALLOW_PATTERNS):
        if pat.endswith("/**"):
            if path.startswith(pat[:-2]):
                return True
        elif fnmatch.fnmatch(path, pat):
            return True
    return False


def _sibling_size(sib):
    """LFS-backed files report size under .lfs; plain files under .size."""
    size = getattr(sib, "size", None)
    if size is None:
        lfs = getattr(sib, "lfs", None)
        if lfs is not None:
            size = (lfs.get("size") if isinstance(lfs, dict)
                    else getattr(lfs, "size", None))
    return size


def repo_inventory(repo_id: str, repo_type: str = "dataset",
                   revision: str = "main", token=None,
                   patterns=None) -> dict:
    """Resolve `revision` to a commit SHA and inventory the files in scope.

    Read-only: this issues Hub API calls but downloads no payload.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:                       # pragma: no cover
        raise HubError(f"huggingface_hub is not installed: {exc}") from None
    try:
        info = HfApi().repo_info(repo_id=repo_id, repo_type=repo_type,
                                 revision=revision, files_metadata=True,
                                 token=token)
    except Exception as exc:
        raise HubError(
            f"Hub API call failed for {repo_type} {repo_id}@{revision}: "
            f"{type(exc).__name__}: {exc}") from None

    sha = getattr(info, "sha", None)
    if not sha:
        raise HubError(
            f"Hub returned no commit SHA for {repo_id}@{revision}; refusing "
            f"to acquire from an unpinned revision")

    included, excluded, unknown = [], [], 0
    for sib in getattr(info, "siblings", None) or []:
        path = getattr(sib, "rfilename", None)
        if not path:
            continue
        if not matches_allow(path, patterns):
            excluded.append(path)
            continue
        size = _sibling_size(sib)
        if size is None:
            unknown += 1
        included.append({"path": path, "size": size})
    included.sort(key=lambda f: f["path"])
    excluded.sort()

    total = sum(f["size"] for f in included if f["size"] is not None)
    card = getattr(info, "card_data", None) or getattr(info, "cardData", None)
    license_ = None
    if card is not None:
        license_ = (card.get("license") if hasattr(card, "get")
                    else getattr(card, "license", None))
    if isinstance(license_, list):
        license_ = ", ".join(str(x) for x in license_)

    return {
        "provider": "huggingface",
        "repo_id": repo_id,
        "repo_type": repo_type,
        "requested_revision": revision,
        "resolved_commit_sha": sha,
        "files": included,
        "file_count": len(included),
        "excluded_paths": excluded,
        "excluded_count": len(excluded),
        "total_bytes": total,
        "sizes_unknown_for": unknown,
        "size_known": unknown == 0 and bool(included),
        "hub_license": license_,
        "private": bool(getattr(info, "private", False)),
        "gated": getattr(info, "gated", False) or False,
    }


def authentication_required(inv: dict) -> bool:
    return bool(inv.get("private")) or bool(inv.get("gated"))


def required_free_bytes(inv: dict) -> tuple:
    """(bytes_required, human explanation). Conservative when size is unknown."""
    total = inv.get("total_bytes") or 0
    if inv.get("size_known") and total:
        return int(total * MARGIN_KNOWN), (
            f"{MARGIN_KNOWN}x the Hub-reported total "
            f"({total / (1 << 30):.2f} GiB)")
    if total:
        return int(total * MARGIN_UNKNOWN), (
            f"{MARGIN_UNKNOWN}x the PARTIAL Hub-reported total "
            f"({total / (1 << 30):.2f} GiB); "
            f"{inv.get('sizes_unknown_for')} file(s) reported no size")
    return CONSERVATIVE_FLOOR_BYTES, (
        f"Hub reported no usable sizes; requiring a conservative floor of "
        f"{CONSERVATIVE_FLOOR_BYTES / (1 << 30):.0f} GiB")


def download_snapshot(repo_id: str, repo_type: str, revision_sha: str,
                      local_dir: str, patterns=None, token=None,
                      max_workers: int = 8) -> str:
    """Pinned snapshot download into a staging directory.

    huggingface_hub resumes partial transfers itself; completeness is NOT
    trusted from that and is re-verified against the pinned inventory by the
    caller before anything is promoted to the immutable raw store.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:                       # pragma: no cover
        raise HubError(f"huggingface_hub is not installed: {exc}") from None
    if not revision_sha or revision_sha == "main":
        raise HubError(
            "refusing to download from an unpinned revision: resolve the "
            "commit SHA with repo_inventory() first")

    kwargs = {
        "repo_id": repo_id,
        "repo_type": repo_type,
        "revision": revision_sha,
        "local_dir": local_dir,
        "allow_patterns": list(patterns if patterns is not None
                               else ALLOW_PATTERNS),
        "token": token,
        "max_workers": max_workers,
    }
    # Adapt to the installed client: older releases accept
    # local_dir_use_symlinks, v1 removed it. A decorated snapshot_download
    # (huggingface_hub wraps it) exposes only **kwargs — filtering against
    # that would silently drop EVERY argument including `revision`, which
    # would quietly download from main. So filter only when the signature is
    # explicit.
    params = inspect.signature(snapshot_download).parameters
    accepts_var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD
                         for p in params.values())
    if not accepts_var_kw:
        kwargs = {k: v for k, v in kwargs.items() if k in params}
        if "local_dir_use_symlinks" in params:
            kwargs["local_dir_use_symlinks"] = False
    if kwargs.get("revision") != revision_sha:
        raise HubError("internal: pinned revision was dropped while adapting "
                       "to the installed huggingface_hub signature")
    os.makedirs(local_dir, exist_ok=True)
    try:
        return snapshot_download(**kwargs)
    except Exception as exc:
        raise HubError(f"snapshot_download failed for {repo_id}@"
                       f"{revision_sha}: {type(exc).__name__}: {exc}") from None


def verify_against_inventory(local_dir: str, inv: dict) -> dict:
    """Is the staged tree complete against the PINNED inventory?

    Partial transfers are never counted as complete: huggingface_hub writes
    `.incomplete` sidecars, and a short file fails the size comparison.
    """
    missing, short, incomplete = [], [], []
    for f in inv["files"]:
        dest = os.path.join(local_dir, f["path"])
        if not os.path.isfile(dest):
            missing.append(f["path"])
            continue
        if f["size"] is not None and os.path.getsize(dest) != f["size"]:
            short.append({"path": f["path"], "expected": f["size"],
                          "actual": os.path.getsize(dest)})
    for dirpath, _, filenames in os.walk(local_dir):
        for fn in filenames:
            if fn.endswith(".incomplete"):
                incomplete.append(os.path.relpath(
                    os.path.join(dirpath, fn), local_dir))
    return {
        "complete": not missing and not short and not incomplete,
        "missing": sorted(missing),
        "size_mismatch": short,
        "incomplete_markers": sorted(incomplete),
        "expected_file_count": len(inv["files"]),
    }
