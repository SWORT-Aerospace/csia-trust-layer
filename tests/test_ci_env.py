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
#: Directories whose sources are SCANNED for third-party imports. These are
#: the trees CI installs dependencies for.
SCANNED_DIRS = ("csia", "tests", "tools")

#: Directories that merely CONTRIBUTE IMPORTABLE NAMES. Wider than
#: SCANNED_DIRS on purpose, and the distinction matters:
#:
#:   "what do our first-party sources import?"   -> SCANNED_DIRS
#:   "what is importable from this repository?"  -> SCANNED_DIRS + these
#:
#: research/ holds modules that tests legitimately import after a sys.path
#: insert -- the independent checker and the clean-room structural reference,
#: which exist precisely so that a test can drive them. Without this, both
#: were reported as undeclared PyPI dependencies.
#:
#: research/ is deliberately NOT in SCANNED_DIRS: it also holds analysis
#: scripts importing matplotlib, sympy and friends, which CI does not install
#: and does not need to. Widening the scan to make the name lookup work would
#: have imported that problem to solve this one.
# `csia_assurance` and `csia_mission` are FIRST-PARTY: top-level packages in
# this repository, packaged by the `csia*` include in pyproject.toml. They are
# listed here because the scan derives local names from directories it
# walks, and a top-level package outside those directories would
# otherwise be reported as an undeclared PyPI dependency.
#
# ALL THREE WERE CAUGHT BY THIS GUARD ON THEIR FIRST COMMIT, which is the
# guard working: a genuinely undeclared dependency and a first-party package
# outside the scanned set look identical to the scan, and the fix differs.
LOCAL_NAME_DIRS = SCANNED_DIRS + ("research", "engineering",
                                  "csia_assurance", "csia_mission",
                                  "csia_stress")

#: import name -> PyPI distribution, where they differ
IMPORT_TO_DIST = {"yaml": "pyyaml", "z3": "z3-solver"}


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
    for d in LOCAL_NAME_DIRS:
        local.add(d)
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        # WALK, do not listdir. The first version looked only at the top
        # level, so `tools/simulation/qualify_platform.py` was invisible to it
        # and a test importing that module after a sys.path insert -- the
        # pattern this function's docstring exists to permit -- was reported
        # as an undeclared PyPI dependency. The rule is "a name importable
        # from this repository", and depth has nothing to do with it.
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [n for n in dirnames if n != "__pycache__"]
            local.update(dirnames)
            local.update(fn[:-3] for fn in filenames if fn.endswith(".py"))
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


# --------------------------------------------------------------------------
# A CI step that cannot fail is not a check.

def _workflow_files():
    wf_dir = os.path.join(ROOT, ".github", "workflows")
    for fn in sorted(os.listdir(wf_dir)):
        if fn.endswith((".yml", ".yaml")):
            yield os.path.join(wf_dir, fn)


def test_every_test_path_named_in_a_workflow_exists():
    """CI ran `pytest tests/test_determinism.py` for weeks. No such file.

    pytest exits 4 on a missing path, `|| true` swallowed it, and a step
    called "determinism" reported success while testing nothing. A path
    typo in a workflow is invisible precisely because the step goes green.
    """
    missing = []
    for path in _workflow_files():
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                # COMMANDS ONLY. A comment is allowed to name a path that no
                # longer exists -- the note explaining this very defect names
                # tests/test_determinism.py, and flagging that would make the
                # guard fire on its own documentation.
                if line.lstrip().startswith("#"):
                    continue
                for ref in re.findall(r"tests/[A-Za-z0-9_/]+\.py", line):
                    if not os.path.exists(os.path.join(ROOT, ref)):
                        missing.append(
                            f"{os.path.basename(path)}:{lineno} -> {ref}")
    assert not missing, (
        f"workflow steps name test files that do not exist: {missing}. "
        f"pytest exits 4 for a missing path, which reads as a failure only "
        f"if nothing swallows it")


def test_no_pytest_invocation_swallows_its_own_result():
    """`|| true` on a test step makes the step decorative.

    Same defect class as the qualification gate that printed FAIL and exited
    0: a guard whose result nobody can see is not a guard.
    """
    offenders = []
    for path in _workflow_files():
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                # A YAML COMMENT CANNOT SWALLOW ANYTHING. This guard scanned
                # raw lines, so the comment DOCUMENTING the `|| true` defect
                # was itself reported as the defect -- a guard firing on its
                # own explanation. Only executable lines can discard a result.
                if line.lstrip().startswith("#"):
                    continue
                if "pytest" not in line:
                    continue
                if "|| true" in line or "|| :" in line:
                    offenders.append(
                        f"{os.path.basename(path)}:{lineno}: {line.strip()}")
    assert not offenders, (
        f"pytest results are being discarded: {offenders}")


def test_the_determinism_selection_actually_selects_something():
    """The replacement must not be vacuous in the other direction.

    `pytest -k determin` over an empty selection exits 5, which is also a
    failure -- but a selection that quietly shrinks to nothing later would
    not be. Count the tests that carry the name.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "tests")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=fn)
            for node in ast.walk(tree):
                if (isinstance(node, ast.FunctionDef)
                        and node.name.startswith("test")
                        and "determin" in node.name):
                    found.append(f"{fn}::{node.name}")
    assert len(found) >= 10, (
        f"only {len(found)} determinism tests found: {found}. The CI step "
        f"selects by name, so a rename silently shrinks what it covers")


# ============================================================ version drift
def test_the_package_version_and_the_build_version_agree():
    """`csia.__version__` and `pyproject.toml [project].version` are two
    hand-maintained copies of one fact, and nothing checked they matched.

    Both are customer-visible: the first is what `csia info` prints and what a
    running deployment reports about itself; the second is what `pip` records
    and what a wheel is named after. A release where they disagree ships a
    binary that misidentifies itself, and the mismatch survives every existing
    test because neither value is ever compared to the other.

    Single-sourcing this through the build backend would work too, and would
    be a packaging change. A guard is enough and cannot break an install.
    """
    import csia

    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        build_version = tomllib.load(fh)["project"]["version"]
    assert csia.__version__ == build_version, (
        f"version drift: csia/__init__.py says {csia.__version__!r}, "
        f"pyproject.toml says {build_version!r}. Bump both, in one commit.")
