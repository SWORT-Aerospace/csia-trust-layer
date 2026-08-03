"""CI environment integrity (regression for the 75881b9 collection failure).

GitHub Actions run 30791649248 died during pytest collection with
`ModuleNotFoundError: No module named 'yaml'`: the suite imported packages
(PyYAML, polars, duckdb) that existed only as undeclared manual installs in
the development venv, while CI installed `.[dev] pyulog pymavlink`.

Reproducing that run from a clean clone then exposed a second defect the
runner never reached, because `import yaml` aborted collection two lines
earlier: an unanchored `data/` rule in .gitignore also matched `csia/data/`,
so the entire data-lake package was absent from the repository.

Three invariants prevent the whole class:
  1. every source file under csia/ is actually tracked by git — a clean
     clone must contain the package, not just the developer's disk;
  2. every third-party module imported anywhere in csia/, tests/ or tools/
     must be provided by the dependency set the CI workflow installs
     (pyproject extras named on the workflow's `pip install -e` line);
  3. the Trust Contract schema ships INSIDE the package, so an installed
     wheel can validate contracts without a repository checkout.

All three fail on commit 75881b9 and are pure static analysis: no network,
no environment mutation.
"""

import ast
import os
import re
import subprocess
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCANNED_DIRS = ("csia", "tests", "tools")

#: import name -> PyPI distribution, where they differ
IMPORT_TO_DIST = {"yaml": "pyyaml"}


def _norm(name: str) -> str:
    return name.lower().replace("-", "_")


def _ci_installed_distributions() -> set:
    """Distributions installed by the workflow's editable-install line."""
    with open(os.path.join(ROOT, ".github", "workflows", "ci.yml")) as fh:
        workflow = fh.read()
    m = re.search(r'pip install -e "\.\[([^\]]+)\]"', workflow)
    assert m, ("ci.yml must install the project from declared extras "
               '(pip install -e ".[...]") — ad-hoc package lists on the '
               "install line are how 75881b9 drifted from the dev venv")
    extras = [e.strip() for e in m.group(1).split(",")]

    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        proj = tomllib.load(fh)["project"]
    reqs = list(proj["dependencies"])
    for extra in extras:
        assert extra in proj["optional-dependencies"], \
            f"ci.yml references extra '{extra}' missing from pyproject.toml"
        reqs += proj["optional-dependencies"][extra]
    # maxsplit is keyword-only in practice from 3.13 (positional deprecated)
    return {_norm(re.split(r"[><=!~;\[ ]", r, maxsplit=1)[0]) for r in reqs}


def _imported_third_party_modules() -> set:
    found = set()
    for d in SCANNED_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, d)):
            dirnames[:] = [n for n in dirnames if n != "__pycache__"]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                with open(os.path.join(dirpath, fn)) as fh:
                    tree = ast.parse(fh.read(), filename=fn)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        found.update(a.name.split(".")[0]
                                     for a in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        if node.level == 0 and node.module:
                            found.add(node.module.split(".")[0])
    return {m for m in found
            if m not in _local_module_names()
            and m not in sys.stdlib_module_names}


def _local_module_names() -> set:
    """Names importable from this repository rather than from PyPI.

    Derived from the tree, not hardcoded: tools/ modules import each other
    after a sys.path insert, and a fixed allowlist would flag each new one
    as an undeclared dependency.
    """
    local = {"__future__"}
    for d in SCANNED_DIRS:
        local.add(d)
        base = os.path.join(ROOT, d)
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if name.endswith(".py"):
                local.add(name[:-3])
            elif os.path.isdir(path) and name != "__pycache__":
                local.add(name)
    return local


def test_no_source_file_is_excluded_from_the_repository():
    """A clean clone must contain every shipped source file.

    `git check-ignore` is authoritative here: importing the package from a
    working tree cannot detect that the files were never committed.
    """
    sources = []
    for d in SCANNED_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, d)):
            dirnames[:] = [n for n in dirnames if n != "__pycache__"]
            sources += [os.path.relpath(os.path.join(dirpath, fn), ROOT)
                        for fn in filenames if fn.endswith(".py")]
    assert sources, "found no Python sources to check"

    proc = subprocess.run(["git", "check-ignore", "--no-index", *sources],
                          cwd=ROOT, capture_output=True, text=True)
    ignored = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert not ignored, (
        f".gitignore excludes shipped source files: {ignored} — an "
        "unanchored directory rule (e.g. 'data/' instead of '/data/') "
        "matches at every depth and silently drops packages from clones")


def test_every_third_party_import_is_installed_by_ci():
    installed = _ci_installed_distributions()
    missing = sorted(
        m for m in _imported_third_party_modules()
        if _norm(IMPORT_TO_DIST.get(m, m)) not in installed)
    assert not missing, (
        f"imported but not in any extra CI installs: {missing} — declare "
        "them in pyproject.toml (this is exactly how 75881b9 failed)")


def test_contract_schema_ships_inside_the_package():
    from importlib import resources
    res = resources.files("csia.contracts").joinpath(
        "csia_trust_contract_schema_v0.1.json")
    assert res.is_file(), \
        "Trust Contract schema must be package data, not a repo-only file"

    from csia.contracts import validate_contract
    assert validate_contract({})["verdict"] == "CSIA_CONTRACT_INVALID"
