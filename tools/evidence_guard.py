"""Refuse to overwrite committed evidence by accident.

THE NEAR-MISS THIS EXISTS FOR
------------------------------
`research/phase2/modern_replication.py` writes
`research/phase2/results/modern_replication.json` unconditionally. Running it
to check whether a freshly built simulator was usable therefore overwrote a
committed artifact -- silently, with a zero exit code and a cheerful
"wrote ..." line. It was caught only because `git status` was checked
immediately afterwards, reverted with `git checkout --`, and recorded as
FL-013.

Nothing in the repository would have stopped it, and nothing would have
reported it. The overwrite was small (a build path, a git hash, a few message
counts that differ run to run) which is exactly what makes it dangerous: a
large diff gets noticed, and a diff that looks like noise gets committed with
everything else.

THE RULE
--------
A research script may freely write a file that git does not track. Overwriting
a TRACKED file requires saying so, once, explicitly:

    from tools.evidence_guard import protected_write
    with protected_write(path, regenerate=args.regenerate) as fh:
        json.dump(payload, fh, indent=2)

Without `regenerate=True` the write raises `EvidenceOverwrite` naming the file
and what to do. With it, the write proceeds and the caller has made a
deliberate choice that shows up in their command line and their shell history.

WHY NOT A TEST THAT THE TREE IS CLEAN
--------------------------------------
The obvious alternative -- a test asserting no tracked evidence file is
modified -- is nearly useless where it matters. CI checks out a clean tree, so
the test can never fail there; it would only fire on a developer's machine,
after the damage, and it would fire constantly during legitimate regeneration
until they committed. Refusing at the point of write is the check that
actually runs at the moment the mistake is made.
"""

from __future__ import annotations

import contextlib
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class EvidenceOverwrite(RuntimeError):
    """A write that would replace a committed artifact."""


def is_tracked(path: str) -> bool:
    """Is this path committed to git? Untracked files are free to write."""
    rel = os.path.relpath(os.path.abspath(path), ROOT)
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        # No git, or no repository. Fail OPEN rather than blocking a script
        # that has nothing to do with evidence -- but say nothing reassuring:
        # the caller gets the same behaviour as an untracked file.
        return False
    return proc.returncode == 0


@contextlib.contextmanager
def protected_write(path: str, regenerate: bool = False, mode: str = "w",
                    encoding: str = "utf-8"):
    """Open `path` for writing, refusing to clobber committed evidence."""
    if is_tracked(path) and not regenerate:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
        raise EvidenceOverwrite(
            f"{rel} is committed evidence and this would overwrite it.\n\n"
            f"If you are re-running a probe to see whether it still works, "
            f"write somewhere else:\n"
            f"    --out /tmp/scratch.json\n\n"
            f"If you genuinely intend to regenerate the artifact, pass "
            f"--regenerate, and expect to explain the resulting diff: a "
            f"committed result is what some paper claim cites.\n\n"
            f"This guard exists because a probe overwrote exactly this kind "
            f"of file, silently, with exit code 0 (FL-013).")
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    handle = open(path, mode, encoding=encoding)
    try:
        yield handle
    finally:
        handle.close()
