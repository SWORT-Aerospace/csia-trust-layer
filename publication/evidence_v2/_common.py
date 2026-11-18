"""Shared stamping and deterministic output for publication/evidence_v2.

Every figure and table gets a sidecar `<output>.stamp.json` carrying the git
commit, dataset ids, config files with SHA-256, seeds, the script and a run
timestamp. Two of those fields need a convention to stay compatible with
`make evidence-v2` regenerating bit-for-bit:

- `git_commit` is the last commit that changed the script, this library or any
  declared input or config. A later commit that touches none of them leaves the
  stamp unchanged, so regeneration at a later HEAD still matches. While any of
  those files is uncommitted the stamp says `UNCOMMITTED`, and
  `check_stamps.py` refuses it.
- `run_timestamp_utc` is that commit's committer time (the SOURCE_DATE_EPOCH
  convention). A wall-clock time would differ on every run. Where wall-clock
  time matters, for the soak and SITL measurements, it is recorded inside the
  committed measurement data, and the stamp quotes it from there.

Nothing here touches the engine. Scripts import csia only to run it unchanged.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(HERE, "data")
FIGURES = os.path.join(HERE, "figures")
TABLES = os.path.join(HERE, "tables")
SCHEMA = "csia.evidence_v2.stamp/1"

#: chart tokens, light surface (dataviz reference palette; slots validated)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")


def rel(path: str) -> str:
    return os.path.relpath(os.path.abspath(path), ROOT).replace(os.sep, "/")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(os.path.join(ROOT, path) if not os.path.isabs(path) else path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def inputs_commit(paths) -> str:
    """Last commit changing any of `paths`, or UNCOMMITTED if any differs from it."""
    rels = sorted({rel(p) for p in paths})
    dirty = git("status", "--porcelain", "--", *rels)
    if dirty:
        return "UNCOMMITTED"
    return git("log", "-1", "--format=%H", "--", *rels)


def commit_time_utc(commit: str) -> str | None:
    if commit == "UNCOMMITTED":
        return None
    env = dict(os.environ, TZ="UTC")
    return subprocess.run(["git", "show", "-s", "--format=%cd",
                           "--date=format-local:%Y-%m-%dT%H:%M:%SZ", commit],
                          cwd=ROOT, capture_output=True, text=True, check=True,
                          env=env).stdout.strip()


def software() -> dict:
    out = {"python": platform.python_version()}
    for mod in ("numpy", "scipy", "matplotlib"):
        try:
            out[mod] = __import__(mod).__version__
        except ImportError:
            out[mod] = None
    return out


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")


def write_csv(path: str, header, rows) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_csv_gz(path: str, header, rows) -> None:
    """gzip with mtime 0 and no file name, so equal content gives equal bytes."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(buf.getvalue().encode("utf-8"))


def read_csv(path: str):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def style():
    """matplotlib with fixed fonts and recessive axes; returns pyplot."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "text.color": TEXT,
        "axes.labelcolor": TEXT, "axes.edgecolor": TEXT_2,
        "xtick.color": TEXT_2, "ytick.color": TEXT_2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "lines.linewidth": 1.6, "svg.hashsalt": "csia-evidence-v2",
        "path.simplify": False,
    })
    return plt


def savefig(fig, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=200, metadata={"Software": None}, bbox_inches="tight")


def stamp(output: str, script: str, *, inputs=(), configs=(), datasets=None,
          seeds=None, definitions=(), measured_at_utc=None, notes=()) -> dict:
    """Write `<output>.stamp.json`. `configs` are (path, role) pairs."""
    tracked = [script, __file__, *inputs, *(p for p, _ in configs)]
    commit = inputs_commit(tracked)
    body = {
        "schema": SCHEMA,
        "output": rel(output),
        "output_sha256": sha256_file(output),
        "script": rel(script),
        "script_sha256": sha256_file(script),
        "shared_library_sha256": sha256_file(__file__),
        "git_commit": commit,
        "git_commit_basis": "last commit that changed the script, _common.py or any listed "
                            "input or config; UNCOMMITTED if any of them differs from it",
        "run_timestamp_utc": commit_time_utc(commit),
        "run_timestamp_basis": "committer time of git_commit (SOURCE_DATE_EPOCH convention), "
                               "so regeneration is bit-for-bit",
        "measured_at_utc": measured_at_utc,
        "inputs": [{"path": rel(p), "sha256": sha256_file(p)} for p in inputs],
        "configs": [{"path": rel(p), "role": role, "sha256": sha256_file(p)} for p, role in configs],
        "datasets": datasets or {},
        "seeds": seeds or {},
        "definitions": list(definitions),
        "software": software(),
        "notes": list(notes),
    }
    write_json(output + ".stamp.json", body)
    return body


def main_guard(fn):
    """Run fn() and exit with its status; keeps every script's tail identical."""
    sys.exit(fn())
