"""Data-root resolution for the CSIA data lake.

Acquired dataset payload NEVER belongs in the Git repository: it is large,
externally licensed, and not ours to redistribute. Every runtime artifact
lives beneath a resolved data root instead.

Precedence (highest first):
    1. --data-root PATH   explicit CLI argument
    2. CSIA_DATA_ROOT     environment variable
    3. <repo>/datasets    tests and fixtures ONLY — never acquisition

The third tier exists so the test suite runs hermetically with no external
volume mounted. `require_external_data_root` refuses it, so no acquisition
path can fall back into the repository by accident.
"""

import os
import shutil
import tempfile

ENV_VAR = "CSIA_DATA_ROOT"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
#: Deliberately NOT <repo>/datasets: that tree holds tracked registry files
#: and committed report fixtures, and a runtime write there would dirty the
#: working tree. This path is gitignored.
REPO_FALLBACK = os.path.join(REPO_ROOT, ".csia-data")

#: DataRoot.source values
SOURCE_CLI = "cli:--data-root"
SOURCE_ENV = f"env:{ENV_VAR}"
SOURCE_REPO = "repository-fixture-fallback"

#: every runtime artifact class lives in one of these subtrees
SUBTREES = ("raw", "normalized", "manifests", "reports", "cache", "exports")


class DataRootError(RuntimeError):
    """Data root is missing, unwritable, too small, or inside the repo."""


def _is_within(child: str, parent: str) -> bool:
    child = os.path.realpath(child)
    parent = os.path.realpath(parent)
    return child == parent or child.startswith(parent + os.sep)


class DataRoot:
    """A resolved data root plus its fixed subtree layout."""

    def __init__(self, path: str, source: str):
        self.path = os.path.abspath(os.path.expanduser(str(path)))
        self.source = source

    def __repr__(self):
        return f"DataRoot({self.path!r}, source={self.source!r})"

    def __eq__(self, other):
        return (isinstance(other, DataRoot) and self.path == other.path
                and self.source == other.source)

    @property
    def is_repo_local(self) -> bool:
        """True when the root sits inside the Git working tree."""
        return _is_within(self.path, REPO_ROOT)

    def sub(self, name: str) -> str:
        if name not in SUBTREES:
            raise ValueError(f"unknown subtree {name!r}; valid: {SUBTREES}")
        return os.path.join(self.path, name)

    raw = property(lambda self: self.sub("raw"))
    normalized = property(lambda self: self.sub("normalized"))
    manifests = property(lambda self: self.sub("manifests"))
    reports = property(lambda self: self.sub("reports"))
    cache = property(lambda self: self.sub("cache"))
    exports = property(lambda self: self.sub("exports"))

    def raw_dir(self, dataset_id: str) -> str:
        return os.path.join(self.raw, dataset_id)

    def report(self, name: str) -> str:
        return os.path.join(self.reports, name)

    def free_bytes(self) -> int:
        """Free space on the filesystem holding the nearest existing parent."""
        p = self.path
        while p and not os.path.isdir(p):
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
        return shutil.disk_usage(p).free

    def ensure(self) -> "DataRoot":
        for name in SUBTREES:
            os.makedirs(self.sub(name), exist_ok=True)
        return self

    def describe(self) -> dict:
        return {
            "path": self.path,
            "source": self.source,
            "is_repo_local": self.is_repo_local,
            "free_bytes": self.free_bytes(),
            "free_gib": round(self.free_bytes() / (1 << 30), 2),
            "subtrees": {n: self.sub(n) for n in SUBTREES},
        }


def resolve_data_root(cli_value: str | None = None,
                      env: dict | None = None) -> DataRoot:
    """Apply the documented precedence. Never touches the filesystem."""
    env = os.environ if env is None else env
    if cli_value and str(cli_value).strip():
        return DataRoot(str(cli_value).strip(), SOURCE_CLI)
    from_env = (env.get(ENV_VAR) or "").strip()
    if from_env:
        return DataRoot(from_env, SOURCE_ENV)
    return DataRoot(REPO_FALLBACK, SOURCE_REPO)


def check_writable(path: str) -> None:
    """Probe an actual write. os.access() lies under root, mode bits lie
    under NFS/ACLs; creating a file is the only honest test."""
    if not os.path.isdir(path):
        raise DataRootError(f"data root does not exist or is not a "
                            f"directory: {path}")
    try:
        fd, probe = tempfile.mkstemp(prefix=".csia-write-probe-", dir=path)
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        raise DataRootError(f"data root is not writable: {path} ({exc})") \
            from None


def check_free_space(root: DataRoot, need_bytes: int | None) -> None:
    if not need_bytes:
        return
    free = root.free_bytes()
    if free < need_bytes:
        raise DataRootError(
            f"insufficient free space at {root.path}: need "
            f"{need_bytes / (1 << 30):.1f} GiB, have "
            f"{free / (1 << 30):.1f} GiB")


def require_external_data_root(root: DataRoot,
                               need_bytes: int | None = None) -> DataRoot:
    """Gate for every path that writes ACQUIRED dataset payload.

    Refuses the repository-fixture fallback: external dataset payload must
    never land inside the Git working tree, whatever the caller intended.
    """
    if root.is_repo_local:
        raise DataRootError(
            f"refusing to write acquired dataset payload inside the Git "
            f"repository ({root.path}). Pass --data-root PATH or set "
            f"{ENV_VAR} to an external location "
            f"(e.g. /Volumes/CSIA_DATA/CSIA_DATA_LAKE).")
    check_writable(root.path)
    check_free_space(root, need_bytes)
    return root


def assert_outside_repo(path: str) -> str:
    """Belt-and-braces check on an individual destination path."""
    if _is_within(path, REPO_ROOT):
        raise DataRootError(
            f"refusing to write dataset payload inside the Git repository: "
            f"{path}")
    return path
