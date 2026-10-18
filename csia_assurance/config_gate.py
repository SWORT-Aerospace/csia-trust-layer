"""A strict configuration gate. Outside the frozen core, by rule.

WHAT IT IS FOR
--------------
`csia/deploy/deployment.py` validates a deployment config against what it
MEANS: does the mode exist, does the profile name something real, is every
core-reaching key declared with a reason. That is semantic validation and it is
good at what it does.

It does NOT reject a key it has never heard of. A config carrying
`tick_hz_override: 50.0` loads clean, the value reaches nothing, and nobody is
told. Most of the time that is harmless. The case where it is not harmless is
the one this file exists for: an operator who believes a key is in effect,
because the file loaded without complaint, and whose evidence record therefore
describes a configuration nobody was running.

So this gate is EXACT-KEY: a config passes only if every key it contains is a
key this build knows. Unknown, aliased, case-shifted, separator-shifted,
nested-override and environment-variable forms are all REFUSED, each with a
distinct reason so the refusal says what was wrong.

WHY IT SITS HERE AND NOT IN `csia/`
------------------------------------
The programme's rule is that new protective components start OUTSIDE the frozen
core. `csia/deploy/` is not in FROZEN_PATHS, so this COULD have been an edit to
`validate()` -- and that is exactly why it is not one. A strict gate that starts
life inside the loader cannot be adopted gradually, cannot be run against
historical configs to see what it would have rejected, and turns every existing
committed config into a load error the moment it lands.

It runs as a gate in front of the loader. Adopting it inside `validate()` is a
deliberate later decision with its own evidence, not a side effect of writing
it.

THE ONE THING IT DELIBERATELY DOES NOT DO
------------------------------------------
It does not guess. There is no "did you mean" and no nearest-key suggestion
that a caller could act on automatically. A rejected key is reported with the
known set; a human decides. Suggesting `tick_hz` for `tickHz` is one refactor
away from applying the suggestion.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Mapping

__all__ = ["KNOWN_KEYS", "REFUSAL_REASONS", "check", "ConfigRefusal",
           "normalise", "env_overrides_present"]

#: Every key a deployment config may contain, as dotted paths. Read from the
#: committed reference config rather than typed here: a hand list says what was
#: true when someone last looked, and FL-001 is this repository's standing
#: evidence about hand lists.
_REFERENCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "configs", "vehicle", "reference_quad_ardupilot_v2.yaml")

REFUSAL_REASONS = (
    "UNKNOWN_KEY",
    "ALIAS_OF_KNOWN_KEY",
    "CASE_VARIANT_OF_KNOWN_KEY",
    "SEPARATOR_VARIANT_OF_KNOWN_KEY",
    "NESTED_OVERRIDE_BLOCK",
    "ENVIRONMENT_OVERRIDE_PRESENT",
    "NOT_A_MAPPING",
)

#: Key names whose presence means "override something else from here", in any
#: capitalisation. A config that can override itself has two answers to every
#: question and the loader picks one.
_OVERRIDE_BLOCK_NAMES = ("override", "overrides", "extra", "extras",
                         "patch", "patches", "defaults_override")

#: The environment prefix an operator would reach for. Checked because an
#: env-var that silently wins over a file is the config equivalent of a silent
#: healthy substitution.
ENV_PREFIX = "CSIA_"


class ConfigRefusal(ValueError):
    """A configuration this build will not read."""


def _walk(node: Any, prefix: str = "") -> Iterable[str]:
    if isinstance(node, Mapping):
        for k, v in node.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            yield path
            yield from _walk(v, path)


def _known_keys(reference: str | None = None) -> frozenset:
    import yaml
    path = reference or _REFERENCE
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    keys = set(_walk(doc))
    # List entries under science_surface and channel_overrides are DATA, not
    # configuration keys; their shape is the loader's business.
    return frozenset(k for k in keys
                     if not k.startswith("science_surface.")
                     and not k.startswith("channel_overrides."))


KNOWN_KEYS = _known_keys()


def normalise(key: str) -> str:
    """Fold the four confusable forms onto one another.

    Used ONLY to classify a refusal, never to accept one. `tickHz`,
    `TICK_HZ`, `tick-hz` and `tick_hz` all normalise to `tickhz`; the first
    three are still refused, and the normalisation is what lets the refusal
    say WHICH known key they resemble.
    """
    leaf = key.rsplit(".", 1)[-1]
    return re.sub(r"[^a-z0-9]", "", leaf.lower())


_KNOWN_NORMAL = {}
for _k in KNOWN_KEYS:
    _KNOWN_NORMAL.setdefault(normalise(_k), set()).add(_k)


def env_overrides_present(environ: Mapping[str, str] | None = None) -> list:
    """Environment variables that LOOK like they configure this system."""
    env = os.environ if environ is None else environ
    return sorted(k for k in env if k.startswith(ENV_PREFIX))


def _classify(key: str) -> tuple:
    """(reason, resembles) for a key that is not exactly known."""
    leaf = key.rsplit(".", 1)[-1]
    for name in _OVERRIDE_BLOCK_NAMES:
        if leaf.lower() == name:
            return "NESTED_OVERRIDE_BLOCK", None

    near = _KNOWN_NORMAL.get(normalise(key))
    if not near:
        return "UNKNOWN_KEY", None

    resembles = sorted(near)
    known_leaves = {k.rsplit(".", 1)[-1] for k in near}
    # Distinguish the three confusable forms, because the fix differs.
    if any(leaf.lower() == kl.lower() for kl in known_leaves):
        return "CASE_VARIANT_OF_KNOWN_KEY", resembles
    if any(re.sub(r"[-_]", "", leaf) == re.sub(r"[-_]", "", kl)
           for kl in known_leaves):
        return "SEPARATOR_VARIANT_OF_KNOWN_KEY", resembles
    return "ALIAS_OF_KNOWN_KEY", resembles


def check(doc: Any, environ: Mapping[str, str] | None = None,
          known: Iterable[str] | None = None) -> list:
    """Every refusal this document earns. Empty list means it passes.

    Returns rather than raises, so a caller can report ALL of a config's
    problems at once instead of the first one.
    """
    if not isinstance(doc, Mapping):
        return [{"key": None, "reason": "NOT_A_MAPPING", "resembles": None}]

    allowed = frozenset(known) if known is not None else KNOWN_KEYS
    refusals = []
    for key in sorted(_walk(doc)):
        if key in allowed:
            continue
        # A key nested inside an already-refused override block is reported
        # once, by its block, rather than repeating the whole subtree.
        if any(key.startswith(r["key"] + ".") for r in refusals
               if r["key"] and r["reason"] == "NESTED_OVERRIDE_BLOCK"):
            continue
        reason, resembles = _classify(key)
        refusals.append({"key": key, "reason": reason,
                         "resembles": resembles})

    for name in env_overrides_present(environ):
        refusals.append({"key": name,
                         "reason": "ENVIRONMENT_OVERRIDE_PRESENT",
                         "resembles": None})
    return refusals


def enforce(doc: Any, environ: Mapping[str, str] | None = None,
            known: Iterable[str] | None = None) -> None:
    """`check`, as an exception. Nothing is repaired and nothing is guessed."""
    bad = check(doc, environ, known)
    if bad:
        lines = "\n  ".join(
            f"{r['key']}: {r['reason']}"
            + (f" (resembles {', '.join(r['resembles'])})"
               if r["resembles"] else "")
            for r in bad)
        raise ConfigRefusal(
            f"this build refuses {len(bad)} configuration element(s):\n  "
            f"{lines}\n\nKnown keys: {sorted(KNOWN_KEYS)}\n"
            f"No key is guessed or corrected. A human decides which was "
            f"meant.")
