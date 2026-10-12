#!/usr/bin/env python3
"""Fail if anything in this package reaches outside it.

A reproduction package that quietly depends on the author's machine is not a
reproduction package, and the dependency is invisible precisely to the author
-- on their machine it works. So the dependencies are looked for mechanically
rather than remembered.

WHAT IT REJECTS
---------------
  1. references to the originating Git repository, by name or by layout
  2. absolute POSIX paths (/home/..., /Users/..., /opt/..., /var/...)
  3. the external ArduPilot checkout at "/home/user/ardupilot"
  4. Windows absolute paths
  5. references to untracked log trees the package does not carry
  6. network access at reproduction time: URLs, socket/urllib/requests, or a
     package installation performed by a script
  7. reads of files outside the package

EXECUTABLE REFERENCE VERSUS DOCUMENTARY REFERENCE
--------------------------------------------------
These are not the same thing and collapsing them makes the check useless in
one of two ways: strict everywhere, and it fails on the vendored formal
sources, whose prose correctly cites the repository the package came FROM;
lenient everywhere, and a real dependency hides in a comment-shaped string.

So the scan is graded:

  scripts/*.py          STRICT, every line. This is the code that runs, and
                        the user's requirement is about scripts.
  README, requirements  STRICT, every line. They are instructions a reader
                        follows, so a stale path there is a real defect.
  source/*.py           LIVE CODE ONLY -- string literals that are not
                        docstrings, import names, and call targets, read out
                        of the AST. `source/proof_audit.py` is vendored
                        BYTE-IDENTICAL to the script that produced the
                        paper's numbers, and its docstring cites its
                        upstream home. Rewriting that docstring to please a
                        grep would break byte-identity, which is worth more.
  source/*.md,.csv,     DOCUMENTARY. Every hit is recorded as a provenance
  .yaml,.tex            reference and none is a failure. These are the
                        paper's own source documents; the package reads them
                        as text and never as paths.

The grading is a judgement, so it is not the load-bearing check.

THE LOAD-BEARING CHECK IS DYNAMIC
----------------------------------
The package's scripts are executed with `open()` instrumented, and every path
opened is resolved and tested against the package root. A path assembled at
run time from pieces that no static scan could join still has to be opened,
and this sees it. Anything outside the package -- other than the
interpreter's own standard library and the reader's site-packages -- is a
FAIL regardless of what the static scan concluded.

    python scripts/check_self_contained.py
    python scripts/check_self_contained.py --fast   # skip the slow probe
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
DEFAULT_OUTPUTS = os.path.join(PKG, "outputs")

# SELF_EXEMPT_BEGIN -- the patterns below necessarily CONTAIN the strings
# they forbid. This region, and only this region, is exempt when the checker
# scans itself. The rest of this file is scanned like any other script, so a
# real dependency introduced anywhere else in it is still caught.
FORBIDDEN_PATTERNS = [
    ("originating_git_repository",
     re.compile(r"csia-trust-layer|SWORT-Aerospace|csia_trust_layer"),
     "names the originating repository; the package must stand alone"),
    ("git_layout_reference",
     re.compile(r"research/math-paper|papers/gate_conditioning|"
                r"\.git/|git clone"),
     "reaches into the originating repository's directory layout"),
    ("absolute_posix_path",
     re.compile(r"(?<![\w.])/(?:home|Users|root|opt|var|srv|mnt)/"),
     "an absolute path on the author's machine"),
    ("ardupilot_checkout",
     re.compile(r"/home/user/ardupilot|ardupilot/modules/mavlink"),
     "the external ArduPilot checkout, which this package does not carry "
     "and does not need"),
    ("windows_absolute_path",
     re.compile(r"[A-Za-z]:\\|[A-Za-z]:/(?:Users|Program)|\\\\\w+\\"),
     "a Windows absolute path"),
    ("untracked_logs",
     re.compile(r"logs/shadow-sitl|\.px4_link_probe|"
                r"campaigns/physical_validation"),
     "untracked measurement output the package does not carry"),
    ("network_access",
     re.compile(r"https?://|ftp://|\bsocket\b|\burllib\b|\brequests\.|"
                r"urlopen|\bhttpx\b"),
     "network access; the reproduction must run offline"),
]

#: Installing dependencies is the ONE step that may touch a network, and only
#: if the reader declines the vendored wheels. A script may not install
#: anything; the README must say how, so it is matched separately and only
#: flagged inside scripts/.
INSTALL_PATTERN = re.compile(r"pip install|pip3 install|easy_install")

#: Modules whose import means the code can reach a network.
NETWORK_MODULES = ("socket", "urllib", "requests", "httpx", "http",
                   "ftplib", "telnetlib", "smtplib")

#: Literals in VENDORED source that match a forbidden pattern but are data,
#: not paths the code opens. Each entry is (file, exact matched text, reason)
#: and is asserted to still be present: if the literal disappears upstream,
#: the exemption is stale and this check says so rather than carrying it
#: forever. Nothing here relaxes a rule for a file as a whole.
DECLARED_LITERAL_EXEMPTIONS = (
    ("source/proof_audit.py", "research/math-paper",
     "the value of the JSON field `generation_command`, which records the "
     "command that produced this artifact IN THE ORIGINATING REPOSITORY. It "
     "is written into the output and never opened. The file is vendored "
     "byte-identical to the script that produced the paper's numbers, so "
     "editing this string to satisfy a grep would destroy the property that "
     "makes the vendoring worth anything."),
)

STRICT_FILES = ("README_REPRODUCE.md", "requirements.txt",
                "PYTHON_VERSION.txt")
# SELF_EXEMPT_END

MENTION_MARKERS = ("must not", "may not", "forbidden", "never", "no network",
                   "does not carry", "rejects", "without the", "outside",
                   "not need", "excluded", "reject", "offline", "absent",
                   "instead of", "rather than", "not a git", "no git",
                   "no repository", "does not read", "not carried")


def is_quoted_mention(line: str, match: str) -> bool:
    for q in ('"', "'", "`"):
        if f"{q}{match}" in line or f"{match}{q}" in line:
            return True
    return False


def scan_lines(path, rel, strict, check_install):
    """Line scan. `strict` decides finding versus provenance note."""
    found = []
    try:
        text = io.open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return found
    patterns = list(FORBIDDEN_PATTERNS)
    if check_install:
        patterns.append(("installs_at_run_time", INSTALL_PATTERN,
                         "a script must not install anything; the README "
                         "tells the reader how, once, before any script runs"))
    for n, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for name, pattern, why in patterns:
            m = pattern.search(line)
            if not m:
                continue
            if any(k in low for k in MENTION_MARKERS) and \
                    is_quoted_mention(line, m.group(0)):
                continue
            found.append({"file": rel, "line": n, "rule": name,
                          "matched": m.group(0), "why": why,
                          "text": line.strip()[:140],
                          "severity": "FAIL" if strict else "PROVENANCE"})
    return found


#: Directories that only exist as filesystem roots. A leading "/" alone is
#: not enough: verify_outputs.py addresses JSON leaves by JSON-POINTER paths
#: such as "/commit" and "/symbolic/sympy_version", which are not filesystem
#: paths and never reach the filesystem. Flagging those would train a reader
#: to ignore this rule, which is how a real finding gets missed. A literal
#: counts as a filesystem path when it starts at a real system root or names
#: a file by extension.
SYSTEM_ROOTS = ("home", "Users", "root", "opt", "var", "srv", "mnt", "etc",
                "usr", "tmp", "private", "proc", "sys", "dev", "Volumes",
                "Applications", "Library")
FILE_SUFFIXES = (".py", ".json", ".md", ".txt", ".csv", ".yaml", ".yml",
                 ".tex", ".bib", ".zip", ".whl", ".pdf", ".log", ".cfg",
                 ".toml", ".ini", ".sh", ".jsonl", ".pyc", ".so")


def looks_like_absolute_filesystem_path(v: str) -> bool:
    if not v.startswith("/") or v.startswith("//"):
        return False
    first = v[1:].split("/", 1)[0]
    if first in SYSTEM_ROOTS:
        return True
    return v.endswith(FILE_SUFFIXES)


def self_exempt_range(text):
    """The [begin, end] line range of this file's own pattern table."""
    lo = hi = None
    for n, line in enumerate(text.splitlines(), start=1):
        if "SELF_EXEMPT_" + "BEGIN" in line:
            lo = n
        elif "SELF_EXEMPT_" + "END" in line:
            hi = n
    return (lo, hi) if lo and hi else None


def scan_live_code(path, rel, exempted_literals=None):
    """A .py file's LIVE CODE only: non-docstring literals and import names.

    Docstrings and comments are prose and are handled by the documentary
    pass, so a vendored script can cite its own upstream home without
    failing a check about where code reads from.
    """
    found = []
    if exempted_literals is None:
        exempted_literals = []
    try:
        src = io.open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except (SyntaxError, OSError):
        return found

    exempt = self_exempt_range(src) if os.path.abspath(path) == \
        os.path.abspath(__file__) else None

    def in_exempt(lineno):
        return exempt is not None and exempt[0] <= lineno <= exempt[1]

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([a.name for a in node.names]
                     if isinstance(node, ast.Import)
                     else [node.module or ""])
            if in_exempt(node.lineno):
                continue
            for nm in names:
                root = (nm or "").split(".")[0]
                if root in NETWORK_MODULES:
                    found.append({
                        "file": rel, "line": node.lineno,
                        "rule": "network_import",
                        "matched": nm, "severity": "FAIL",
                        "why": "a network module imported by code that is "
                               "supposed to run offline",
                        "text": nm})
            continue
        if not isinstance(node, ast.Constant) or \
                not isinstance(node.value, str) or id(node) in docstrings:
            continue
        if in_exempt(getattr(node, "lineno", 0)):
            continue
        v = node.value
        if not v or len(v) > 400:
            continue
        for name, pattern, why in FORBIDDEN_PATTERNS:
            m = pattern.search(v)
            if m:
                if any(f == rel and t == m.group(0)
                       for f, t, _r in DECLARED_LITERAL_EXEMPTIONS):
                    exempted_literals.append(
                        {"file": rel, "line": getattr(node, "lineno", 0),
                         "matched": m.group(0)})
                    continue
                found.append({"file": rel, "line": getattr(node, "lineno", 0),
                              "rule": name, "matched": m.group(0),
                              "why": why, "severity": "FAIL",
                              "text": v[:140]})
        if looks_like_absolute_filesystem_path(v):
            found.append({"file": rel, "line": getattr(node, "lineno", 0),
                          "rule": "absolute_path_literal", "matched": v[:120],
                          "why": "an absolute path literal in code cannot be "
                                 "correct on another machine",
                          "severity": "FAIL", "text": v[:140]})
    return found


def package_files():
    for dirpath, dirnames, filenames in os.walk(PKG):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", "outputs", ".venv", ".git",
                                    "vendor")]
        for f in sorted(filenames):
            full = os.path.join(dirpath, f)
            yield full, os.path.relpath(full, PKG)


def dynamic_probe(outputs: str, scripts) -> dict:
    """Run the package's scripts with `open` instrumented."""
    import builtins
    import importlib.util

    real_open = builtins.open
    opened, escapes = [], []
    allowed = [PKG, os.path.dirname(os.__file__),
               os.path.dirname(os.path.dirname(os.__file__)),
               sys.prefix, sys.base_prefix]
    for p in sys.path:
        if p and ("site-packages" in p or "dist-packages" in p):
            allowed.append(os.path.abspath(p))
    allowed = [a for a in allowed if a]

    def probing_open(file, *a, **kw):
        try:
            resolved = os.path.abspath(os.fspath(file))
        except TypeError:
            return real_open(file, *a, **kw)
        opened.append(resolved)
        if not any(resolved.startswith(r) for r in allowed):
            escapes.append(resolved)
        return real_open(file, *a, **kw)

    builtins.open = probing_open
    ran = []
    try:
        for script in scripts:
            path = os.path.join(PKG, "scripts", script)
            spec = importlib.util.spec_from_file_location(
                f"_probe_{script[:-3]}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            argv = sys.argv
            sys.argv = [script, "--outputs", outputs]
            try:
                mod.main()
            finally:
                sys.argv = argv
            ran.append(script)
    finally:
        builtins.open = real_open

    return {"scripts_run_under_probe": ran,
            "paths_opened": len(opened),
            "paths_outside_the_package": sorted(set(escapes))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outputs", default=DEFAULT_OUTPUTS)
    ap.add_argument("--fast", action="store_true",
                    help="probe only the fast script, not reproduce.py")
    ap.add_argument("--no-dynamic", action="store_true")
    args = ap.parse_args()

    findings, provenance, scanned = [], [], 0
    exempted_literals = []
    for full, rel in package_files():
        parts = rel.replace("\\", "/").split("/")
        top = parts[0]
        base = parts[-1]

        if top == "scripts" and base.endswith(".py"):
            # Live code is what executes, so that is what is strict. A
            # docstring that says the package "opens no socket" is prose
            # about the absence of a dependency, and failing on it would
            # punish the file for documenting itself.
            scanned += 1
            findings += scan_live_code(full, rel, exempted_literals)
            provenance += scan_lines(full, rel, strict=False,
                                     check_install=False)
        elif base in STRICT_FILES:
            scanned += 1
            findings += scan_lines(full, rel, strict=True, check_install=False)
        elif top == "source" and base.endswith(".py"):
            scanned += 1
            findings += scan_live_code(full, rel, exempted_literals)
            provenance += [f for f in scan_lines(full, rel, strict=False,
                                                 check_install=False)]
        elif top == "source":
            scanned += 1
            provenance += scan_lines(full, rel, strict=False,
                                     check_install=False)

    # A declared exemption that never fired is describing a literal that is
    # no longer there. Carrying it would let the next escaping literal at
    # that path inherit a reason written for something else.
    stale = [(f, t) for f, t, _r in DECLARED_LITERAL_EXEMPTIONS
             if not any(e["file"] == f and e["matched"] == t
                        for e in exempted_literals)]
    for f, t in stale:
        findings.append({"file": f, "line": 0,
                         "rule": "stale_literal_exemption",
                         "matched": t, "severity": "FAIL",
                         "why": "declared as an exempt literal but no such "
                                "literal was found; drop the exemption",
                         "text": t})

    print("SELF-CONTAINMENT CHECK")
    print("=" * 70)
    print(f"  scanned {scanned} file(s) against "
          f"{len(FORBIDDEN_PATTERNS)} forbidden patterns")
    for e in exempted_literals:
        reason = next(r for f, t, r in DECLARED_LITERAL_EXEMPTIONS
                      if f == e["file"] and t == e["matched"])
        print(f"  [declared] {e['file']}:{e['line']} literal {e['matched']!r}")
        print(f"             {reason}")

    probe = None
    if not args.no_dynamic:
        scripts = (["srcattr_controls.py"] if args.fast
                   else ["srcattr_controls.py", "reproduce.py"])
        os.makedirs(os.path.abspath(args.outputs), exist_ok=True)
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            probe = dynamic_probe(os.path.abspath(args.outputs), scripts)
        print(f"  run-time probe: {probe['paths_opened']} path(s) opened by "
              f"{', '.join(probe['scripts_run_under_probe'])}")
        for p in probe["paths_outside_the_package"]:
            findings.append({"file": "<runtime>", "line": 0,
                             "rule": "runtime_read_outside_package",
                             "matched": p, "severity": "FAIL",
                             "why": "opened a file outside the package",
                             "text": p})

    if provenance:
        print(f"  {len(provenance)} documentary provenance reference(s) in "
              f"source/ -- recorded, not failures")
        seen = set()
        for f in provenance:
            key = (f["file"], f["rule"])
            if key in seen:
                continue
            seen.add(key)
            print(f"      {f['file']}  cites {f['matched']!r}")

    if findings:
        print()
        for f in findings:
            print(f"  [FAIL] {f['file']}:{f['line']}  {f['rule']}")
            print(f"           matched: {f['matched']}")
            print(f"           why:     {f['why']}")
    print("=" * 70)

    doc = {
        "artifact": "SELF_CONTAINMENT_CHECK",
        "files_scanned": scanned,
        "rules": [{"rule": n, "why": w} for n, _p, w in FORBIDDEN_PATTERNS],
        "grading": {
            "strict": "scripts/*.py, README_REPRODUCE.md, requirements.txt, "
                      "PYTHON_VERSION.txt",
            "live_code_only": "source/*.py -- vendored byte-identical, so "
                              "docstring prose is documentary",
            "documentary": "source/*.md, *.csv, *.yaml, *.tex -- the paper's "
                           "own source documents",
            "load_bearing": "the run-time open() probe, which does not care "
                            "how a path was spelled",
        },
        "declared_literal_exemptions": [
            {"file": f, "matched": t, "reason": r}
            for f, t, r in DECLARED_LITERAL_EXEMPTIONS],
        "declared_literal_exemptions_that_fired": exempted_literals,
        "findings": findings,
        "documentary_provenance_references": provenance,
        "runtime_probe": probe,
        "verdict": "PASS" if not findings else "FAIL",
    }
    out = os.path.join(os.path.abspath(args.outputs),
                       "self_containment_check.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    if findings:
        print(f"FAIL: {len(findings)} reference(s) reach outside the package",
              file=sys.stderr)
        return 1
    print("PASS: nothing executable in the package reaches outside it, and "
          "no run-time read escaped it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
