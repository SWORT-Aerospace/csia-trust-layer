"""Layer C — the experimental auditor.

Layer C does not run the experiment and does not score it. It checks that the
experiment was run the way the preregistration says, and in particular that
Layer A never acquired the ability to see truth.

The central check here is static, not dynamic. A runtime check ("did this
function receive a GroundTruth?") only fails on the paths a test happens to
exercise. Parsing the import graph fails on paths nobody has run yet, which is
the point: the guarantee has to hold for code that has not been written.
"""
from __future__ import annotations

import ast
import pathlib
from typing import Dict, Iterable, List, Set, Tuple

LAYER = "C"
SCHEMA = "csia.independent_validation.audit/1"

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The deployable certificate and everything it is allowed to be built from.
#: If a new module joins Layer A it goes here, and the import walk starts
#: enforcing the same rule on it.
LAYER_A_MODULES: Tuple[str, ...] = (
    "csia_active_evidence.rcec",
    "csia_active_evidence.probes",
    "csia_active_evidence.rcec_selector",
    "csia_active_evidence.realized_moments",
    "csia_active_evidence.waveform_compensation",
    "csia_active_evidence.moment_feedback",
    "csia_active_evidence.polarization",
    "csia_active_evidence.identifiability",
    "csia_active_evidence.authority",
)

#: Local top-level packages worth following. Anything outside these is a
#: third-party or standard-library import and cannot carry our ground truth.
LOCAL_ROOTS: Tuple[str, ...] = (
    "csia", "csia_active_evidence", "csia_evidence", "csia_components",
    "csia_independent_validation", "csia_assurance", "csia_mission",
    "csia_stress", "csia_supervision", "tools",
)

#: Names that must never appear anywhere in Layer A's transitive closure.
FORBIDDEN_IN_LAYER_A: Tuple[str, ...] = (
    "csia_independent_validation.truth",
    "csia_independent_validation.plants",
    "csia_independent_validation.evaluator",
    "csia_independent_validation.ceilings",
)


def _module_path(module: str) -> pathlib.Path | None:
    candidate = ROOT / (module.replace(".", "/") + ".py")
    if candidate.is_file():
        return candidate
    package = ROOT / module.replace(".", "/") / "__init__.py"
    return package if package.is_file() else None


def direct_imports(module: str) -> Set[str]:
    """Local modules imported by ``module``, read from its source.

    Relative imports are resolved against the module's own package, so
    ``from .truth import GroundTruth`` inside ``csia_independent_validation``
    is reported as ``csia_independent_validation.truth`` and not missed.
    """
    path = _module_path(module)
    if path is None:
        return set()
    tree = ast.parse(path.read_text(), filename=str(path))
    package = module.rsplit(".", 1)[0] if "." in module else module
    if path.name == "__init__.py":
        package = module
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[:len(parts) - node.level + 1])
                prefix = f"{base}.{node.module}" if node.module else base
            else:
                prefix = node.module or ""
            if prefix:
                found.add(prefix)
                for alias in node.names:
                    found.add(f"{prefix}.{alias.name}")
    return {name for name in found
            if name.split(".")[0] in LOCAL_ROOTS}


def transitive_imports(modules: Iterable[str]) -> Set[str]:
    """Everything reachable from ``modules`` through local imports."""
    seen: Set[str] = set()
    queue: List[str] = list(modules)
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        for name in direct_imports(current):
            if name not in seen:
                queue.append(name)
    return seen


def truth_bearing_modules() -> Set[str]:
    """Every local module that declares ``TRUTH_BEARING = True``.

    Discovered by reading the source, so a module becomes protected the moment
    it declares itself rather than when somebody remembers to list it.
    """
    found: Set[str] = set()
    for root in LOCAL_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(), filename=str(path))
            except SyntaxError:
                continue
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                targets = {t.id for t in node.targets
                           if isinstance(t, ast.Name)}
                if "TRUTH_BEARING" not in targets:
                    continue
                if isinstance(node.value, ast.Constant) and node.value.value:
                    relative = path.relative_to(ROOT).with_suffix("")
                    parts = list(relative.parts)
                    if parts[-1] == "__init__":
                        parts.pop()
                    found.add(".".join(parts))
    return found


def layer_a_leaks(modules: Iterable[str] = LAYER_A_MODULES) -> Dict[str, list]:
    """What Layer A can reach that it must not. Empty dict means clean."""
    reachable = transitive_imports(modules)
    leaks: Dict[str, list] = {}
    forbidden = reachable & set(FORBIDDEN_IN_LAYER_A)
    if forbidden:
        leaks["forbidden_modules"] = sorted(forbidden)
    truthy = reachable & truth_bearing_modules()
    if truthy:
        leaks["truth_bearing_modules"] = sorted(truthy)
    return leaks


def observation_schema_is_clean(field_names: Iterable[str]) -> List[str]:
    """Field names on the Layer A observation that smell of ground truth.

    A leak does not have to be an import. Adding ``r0_true`` to the
    observation would hand Layer A the answer through a data schema, and the
    import graph would stay green.
    """
    suspicious = ("true", "truth", "fault", "label", "hidden", "actual",
                  "oracle", "answer", "gt_", "_gt")
    return sorted(name for name in field_names
                  if any(token in name.lower() for token in suspicious))
