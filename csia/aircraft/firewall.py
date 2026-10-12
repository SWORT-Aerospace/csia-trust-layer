"""The profile/science firewall: a protected namespace GENERATED from source.

WHY THIS MODULE EXISTS SEPARATELY FROM `profile.py`
---------------------------------------------------
`profile.py` carries FORBIDDEN_KEYS, a hand-written blacklist. It works, it
gives excellent error messages, and it has already decayed once: FL-001 records
that it named "speed_gate", "gate_lo" and "gate_hi" while the comparator
actually defines `GATE_SPEED_LO`, so the horizontal-speed gate threshold was
settable from a profile and nothing objected. A test reading the constants out
of source caught it.

That is the whole argument for this module. A list maintained by a person
protects the parameters that person remembered. A namespace DERIVED from the
frozen core protects the parameters the frozen core actually has, including the
ones added tomorrow by someone who never reads this file.

WHAT IS PROTECTED, AND THE RULE THAT DECIDES
--------------------------------------------
Two generated sets, both read out of `FROZEN_PATHS` with `ast`:

  1. every module-level ALL-CAPS constant whose value is a number, or a
     container of numbers -- `EPS`, `SMOOTH_ALPHA`, `GATE`-style thresholds,
     `TICK_HZ`, the confidence knees;
  2. every annotated field of a frozen class whose name ends in `Config` --
     `FailsafeConfig` and `EngineConfig` today, whatever is added later.

Result dataclasses are DELIBERATELY EXCLUDED, and the exclusion is not
laziness. `HypothesisReport`, `TrustState`, `BaselineVerdict` and friends carry
fields called `description`, `name`, `params`, `context`, `notes`, `sensors`
and `valid`. Protecting those would reject `vehicle_profile.description` -- a
label -- on every shipped profile, and a firewall that fires on the airframe's
prose teaches its operator to route around it. The threat model is narrower
than "any word the core uses", and stating it narrowly is what makes it
enforceable:

  THE THREAT. Nothing in the frozen core reads a vehicle profile today; the
  profile is parsed into a `VehicleProfile` and the core never sees it. The
  hole this guards is the NEXT wiring change -- someone passing `profile.raw`,
  or a `tuning:` block, into `FailsafeConfig(**...)` or `EngineConfig(**...)`,
  or reading a named constant from it. A key that could land on a core
  configuration field or shadow a named core constant is therefore refused at
  the door, before any such wiring can be written.

  MEASURED, NOT ASSUMED: the frozen core reads NO environment variable
  (grepping FROZEN_PATHS for `os.environ` and `getenv` returns nothing, and
  `test_the_frozen_core_reads_no_environment_variable` keeps it that way), so
  the environment route is closed at the source. The env-var checks below are
  defence in depth against that changing, not a patch for a live hole.

WHY NORMALISATION, AND WHY IT IS AGGRESSIVE
-------------------------------------------
A blacklist keyed on exact spelling is defeated by `navCaution`, `NAV-CAUTION`,
`nav caution`, `CSIA_NAV_CAUTION` and `nav_cautions`, none of which a reviewer
would read as an evasion attempt and all of which mean the same thing to a
person. Keys are folded to a comparison form -- camelCase split, lowercased,
separators dropped -- a small set of framing prefixes is stripped, and trailing
plurals are folded. `tests/test_profile_science_firewall.py` fuzzes every
protected name through all of those transforms and asserts each is refused.

FAIL CLOSED, AND EXACTLY WHERE
------------------------------
A blacklist can only reject what it recognises. Two places additionally reject
anything they do NOT recognise:

  - the profile's TOP-LEVEL sections, and
  - the per-channel stream spec.

Those are the two places where an unrecognised key is both silently ignored
today and plausibly meant as tuning ("streams.imu0.accel.sigma"). Deeper
sections -- `transport`, `experiment`, `safety` -- are NOT allowlisted, on
purpose: the fault-injector block is specified to grow in P5, and an allowlist
written before the thing it lists exists is a guess that will be widened under
deadline pressure, which is worse than no allowlist at all.
"""

from __future__ import annotations

import ast
import functools
import os
import re
from typing import Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

#: The frozen scientific core, verbatim from EVIDENCE_EXTENSION.yaml's
#: forbidden_paths. Not a copy of a concept -- a copy of the list, and
#: `tests/test_profile_science_firewall.py` asserts the two agree.
FROZEN_PATHS = (
    "csia/trust_engine",
    "csia/diagnosis",
    "csia/runtime/online.py",
    "csia/runtime/failsafe.py",
    "csia/scenarios.py",
    "csia/profiles.py",
)

#: Class-name suffixes whose annotated fields are configuration rather than
#: result. Kept as a suffix rule rather than a list of class names so a new
#: `SequentialConfig` is protected the day it is written.
CONFIG_CLASS_SUFFIXES = ("Config", "Params", "Tuning", "Settings")

#: Framing words a key might be wrapped in while meaning the same parameter.
#: `CSIA_NAV_CAUTION`, `tuning.nav_caution`, `override_rho_max` and
#: `my_smooth_alpha` all reduce to a protected name once these come off.
STRIPPABLE_PREFIXES = (
    "csia", "core", "trust", "diag", "diagnostic", "diagnostics",
    "tune", "tuning", "param", "params", "parameter", "parameters",
    "override", "overrides", "default", "defaults", "custom", "my",
    "env", "cfg", "config", "conf", "setting", "settings", "set",
    "vehicle", "profile", "aircraft", "platform",
)

#: Top-level sections a profile may contain. FAIL CLOSED: anything else is
#: refused rather than ignored.
ALLOWED_TOP_LEVEL = frozenset({
    "vehicle_profile", "profile_id",
    "autopilot", "autopilot_family",
    "transport", "streams", "functions", "experiment", "safety",
})

#: Keys a per-channel stream spec may carry. FAIL CLOSED, for the same reason.
ALLOWED_STREAM_SPEC_KEYS = frozenset({"status", "nominal_rate_hz", "note"})

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NONWORD = re.compile(r"[^a-z0-9]+")
#: `${FOO}`, `$FOO`, `%FOO%` and `env:FOO` -- the four ways a YAML value
#: smuggles an environment variable past a key-only check.
_ENV_REF = re.compile(
    r"\$\{\s*([A-Za-z_][A-Za-z0-9_]*)|"
    r"\$([A-Za-z_][A-Za-z0-9_]*)|"
    r"%([A-Za-z_][A-Za-z0-9_]*)%|"
    r"\benv:([A-Za-z_][A-Za-z0-9_]*)")


def _numeric(node) -> bool:
    """Is this AST node a number, or a container of nothing but numbers?"""
    if isinstance(node, ast.Constant):
        return (isinstance(node.value, (int, float))
                and not isinstance(node.value, bool))
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return bool(node.elts) and all(_numeric(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return bool(node.values) and all(_numeric(v) for v in node.values)
    if isinstance(node, ast.UnaryOp):
        return _numeric(node.operand)
    if isinstance(node, ast.BinOp):
        return _numeric(node.left) and _numeric(node.right)
    return False


def frozen_source_files(root: Optional[str] = None) -> tuple:
    root = root or ROOT
    out = []
    for rel in FROZEN_PATHS:
        path = os.path.join(root, rel)
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                out += [os.path.join(dirpath, fn)
                        for fn in sorted(filenames) if fn.endswith(".py")]
        elif os.path.isfile(path):
            out.append(path)
    return tuple(sorted(out))


@functools.lru_cache(maxsize=4)
def protected_names(root: Optional[str] = None) -> frozenset:
    """Every core parameter name, read out of the frozen source.

    Returns names in their SOURCE spelling (`SMOOTH_ALPHA`, `nav_caution`) so
    an error message can say where the collision is. Comparison happens on the
    folded form; see `collision()`.
    """
    names = set()
    for path in frozen_source_files(root):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for node in tree.body:
            if isinstance(node, ast.Assign) and _numeric(node.value):
                for tgt in node.targets:
                    if (isinstance(tgt, ast.Name) and tgt.id.isupper()
                            and len(tgt.id) > 2):
                        names.add(tgt.id)
            if isinstance(node, ast.ClassDef) and node.name.endswith(
                    CONFIG_CLASS_SUFFIXES):
                for body in node.body:
                    if (isinstance(body, ast.AnnAssign)
                            and isinstance(body.target, ast.Name)):
                        names.add(body.target.id)
    return frozenset(names)


def fold(key: str) -> str:
    """The comparison form: lowercased, everything but [a-z0-9] dropped.

    `navCaution`, `NAV-CAUTION`, `nav caution` and `nav_caution` all fold to
    `navcaution`. Folding is where the spelling-variant fuzz is defeated; the
    prefix and plural rules in `_variants()` handle the rest.

    NO CAMEL SPLIT HERE, and the absence is deliberate. The first version ran
    `_CAMEL` before lowercasing, which is a provable no-op: the split inserts
    an underscore that `_NONWORD` then removes. Mutation testing found it --
    deleting the split changed no test result -- and dead code inside a
    security boundary is worse than dead code elsewhere, because a reader
    trusts the boundary to mean what it says. The camel split IS load-bearing
    one function down, in `_variants()`, where tokens must survive to be
    matched against STRIPPABLE_PREFIXES.
    """
    return _NONWORD.sub("", str(key).lower())


def _variants(key: str) -> set:
    """Every form of `key` that means the same core parameter to a reader."""
    tokens = _NONWORD.sub("_", _CAMEL.sub("_", str(key)).lower()).strip("_")
    forms = {tokens}
    parts = [p for p in tokens.split("_") if p]
    # Strip framing prefixes, possibly stacked: csia_tuning_nav_caution.
    while parts and parts[0] in STRIPPABLE_PREFIXES:
        parts = parts[1:]
        if parts:
            forms.add("_".join(parts))
    # NO PLURAL FOLD HERE. It belongs on the other side of the comparison, and
    # doing it on both sides is a duplicate that mutation testing caught:
    # disabling this loop's plural handling changed no test result, because
    # `_folded_index` already indexes every protected name under both numbers.
    # One place to read, one place to fix.
    return {f for f in (fold(form) for form in forms) if f}


@functools.lru_cache(maxsize=4)
def _folded_index(root: Optional[str] = None) -> dict:
    """folded form -> source spelling, for every protected name."""
    index = {}
    for name in protected_names(root):
        index.setdefault(fold(name), name)
        # A protected name is also matched in its own plural/singular, so
        # `w_phys` catches `w_physes` and `weights` catches `weight`.
        folded = fold(name)
        if folded.endswith("s") and len(folded) > 3:
            index.setdefault(folded[:-1], name)
        else:
            index.setdefault(folded + "s", name)
    return index


def collision(key: str, root: Optional[str] = None) -> Optional[str]:
    """The frozen-core parameter `key` would shadow, or None.

    Returns the SOURCE spelling so the caller can point at the real constant
    rather than at the folded form nobody wrote.
    """
    index = _folded_index(root)
    for variant in _variants(key):
        if variant in index:
            return index[variant]
    return None


def env_collision(value, root: Optional[str] = None) -> Optional[tuple]:
    """A protected name referenced through an environment interpolation.

    Returns (referenced_name, protected_name) or None. Defence in depth: the
    frozen core reads no environment variable today, and this exists so that
    changing is not silently also a way in.
    """
    if not isinstance(value, str):
        return None
    for match in _ENV_REF.finditer(value):
        name = next(g for g in match.groups() if g)
        hit = collision(name, root)
        if hit:
            return (name, hit)
    return None
