"""The v1 diagnostic core is frozen. This test is the freeze.

`docs/v1/V1_FINAL_RESEARCH_VERDICT.md` §7 says engineering work may change how
CSIA is fed and how its output is carried, and may not change a threshold,
weight, gate or relation. That is a promise until something checks it.

If one of these fails, the correct response is NOT to update the expected
value. It is to decide whether a v1 algorithm change was intended, and if so
to re-freeze the baseline explicitly and record the before/after in the
verdict document.
"""

import subprocess

import pytest

FROZEN_TAG = "csia-v1.0-research-final"

# The diagnostic core. Adapters, deployment and simulation tooling are NOT
# here: those are exactly what v1.1 is allowed to add.
FROZEN_PATHS = [
    "csia/trust_engine",
    "csia/diagnosis",
    "csia/runtime/online.py",
    "csia/runtime/failsafe.py",
    "csia/scenarios.py",
    "csia/profiles.py",
]


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def _tag_exists() -> bool:
    rc, out = _git("tag", "-l", FROZEN_TAG)
    return rc == 0 and out.strip() == FROZEN_TAG


requires_tag = pytest.mark.skipif(
    not _tag_exists(),
    reason=f"{FROZEN_TAG} not present (shallow clone or fresh fork)")


@requires_tag
def test_diagnostic_core_is_unchanged_since_the_freeze():
    rc, out = _git("diff", "--stat", FROZEN_TAG, "--", *FROZEN_PATHS)
    assert rc == 0
    assert out == "", (
        "the FROZEN v1 diagnostic core has changed:\n" + out +
        "\n\nThis is not a test to update. Either revert the change, or "
        "re-freeze the baseline explicitly and record the before/after in "
        "docs/v1/V1_FINAL_RESEARCH_VERDICT.md.")


def test_deployment_layers_exist():
    """The freeze must not have been achieved by adding nothing.

    A test that only asserts 'nothing changed' would also pass if v1.1 had
    never been written.
    """
    import csia.aircraft.adapters as adapters
    import csia.deploy.shadow as shadow
    import csia.simulation.contract as contract
    assert adapters.ADAPTERS, "no platform adapters registered"
    assert shadow.ShadowRunner is not None
    assert contract.TrialContract is not None


def _imported_modules(module) -> set:
    """Module names actually IMPORTED, parsed rather than grepped.

    Grepping the source for a name matches prose: the word "diagnosis" appears
    in qualification.py's docstring explaining why the estimator is excluded
    FROM diagnosis, which is the opposite of importing it. The AST does not
    make that mistake.
    """
    import ast
    tree = ast.parse(open(module.__file__, encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = ("." * (node.level or 0)) + (node.module or "")
            names.add(base)
            names.update(f"{base}.{a.name}" for a in node.names)
    return names


def test_qualification_does_not_import_the_core():
    """Qualification must sit at the adapter, not inside the algorithm."""
    import csia.aircraft.qualification as q
    imported = _imported_modules(q)
    for banned in ("trust_engine", "online", "diagnosis", "failsafe"):
        offenders = [n for n in imported if banned in n]
        assert not offenders, (
            f"qualification imports {offenders}: the S2 layer must not reach "
            f"into the frozen core")


def test_frozen_core_does_not_import_the_deployment_layer():
    """The dependency runs one way. The core must not learn about adapters."""
    import csia.runtime.online as online
    imported = _imported_modules(online)
    for banned in ("aircraft", "deploy"):
        offenders = [n for n in imported if banned in n]
        assert not offenders, (
            f"the frozen core imports {offenders}: v1.1 has leaked into v1")
