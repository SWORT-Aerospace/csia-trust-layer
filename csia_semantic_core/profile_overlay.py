"""Versioned successor-profile declarations, applied as an overlay.

The v2 profiles (`csia/v2/profiles/`) are frozen with v2. A successor
profile therefore does not edit them. It is a small, versioned, hashed list
of ADDITIONAL declarations: which functions a component serves, and which
components it depends on. The list is applied to a tick's records before 2.1
reasons over them.

- **The originals are never modified.** `apply()` returns new records built
  with `dataclasses.replace`.
- **The authoritative v2.0 path never sees the overlay.** It keeps reasoning
  over the engine's own records.
- **Every declaration carries its justification.** Each has a kind (DIRECT,
  DERIVED, CONDITIONAL) and a source, so a reviewer can check why it exists.
- **The overlay has an identity.** `digest()` is the SHA-256 of its
  canonical JSON. A result produced under an overlay records the digest, so
  "which dependency model was this reasoned against?" always has an answer.

Accepted successor profiles live in `successor_profiles/`, one file per
version, and are never edited once written: a correction is a new version.
`aircraft_successor_r1.json` holds the two declarations the shadow study
accepted (`research/csia_semantic_core_2_1_shadow/PROFILE_REPAIR_PROPOSAL.md`).
`aircraft_successor_r2.json` is r1 plus one pacing declaration (revision
R-2, `research/csia_semantic_core_2_1_revision/`). No successor profile is
applied by default, and the frozen v2.0 engine never sees one.

PACING DECLARATIONS (2.1.1, R-2)
--------------------------------
A declaration may also name the inputs that pace a component's output
(`add_pacing_inputs`) and how they combine (`pacing_mode`: ALL or ANY).
That is architecture, so it lives in the profile; what starvation means
lives in the predicate. Pacing is not a record field: `apply()` leaves it
out, and `pacing_map()` hands it to the core (`SemanticCore21(pacing=...)`).
A pacing input must also be a declared dependency (validator rule PV9).
Empty pacing fields are left out of `to_dict()`, so a profile without them
keeps the digest it had before pacing existed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

KINDS = ("DIRECT", "DERIVED", "CONDITIONAL")
PACING_MODES = ("ALL", "ANY")
SUCCESSOR_DIR = Path(__file__).resolve().parent / "successor_profiles"


@dataclass(frozen=True)
class Declaration:
    domain: str
    component: str
    add_affected_functions: tuple = ()
    add_dependencies: tuple = ()
    kind: str = "DIRECT"
    justification: str = ""
    source: str = ""
    add_pacing_inputs: tuple = ()
    pacing_mode: str | None = None

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if not (self.add_affected_functions or self.add_dependencies
                or self.add_pacing_inputs):
            raise ValueError("a declaration must add something")
        if self.add_pacing_inputs and self.pacing_mode not in PACING_MODES:
            raise ValueError(f"pacing_mode must be one of {PACING_MODES}")
        if self.pacing_mode is not None and not self.add_pacing_inputs:
            raise ValueError("pacing_mode without pacing inputs")


@dataclass(frozen=True)
class ProfileOverlay:
    name: str
    version: str
    base_profile: str
    declarations: tuple

    @classmethod
    def from_dict(cls, d: dict) -> "ProfileOverlay":
        return cls(d["name"], d["version"], d["base_profile"],
                   tuple(Declaration(**{k: (tuple(v) if isinstance(v, list) else v)
                                        for k, v in x.items()})
                         for x in d["declarations"]))

    @classmethod
    def from_json(cls, path) -> "ProfileOverlay":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def to_dict(self) -> dict:
        return {"name": self.name, "version": self.version,
                "base_profile": self.base_profile,
                "declarations": [_decl_dict(x) for x in self.declarations]}

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True)
                              .encode()).hexdigest()

    def pacing_map(self) -> dict:
        """`{component: (mode, (node id, ...))}` for `SemanticCore21`. Two
        declarations for one component must agree on the mode."""
        out: dict = {}
        for x in self.declarations:
            if not x.add_pacing_inputs:
                continue
            mode, inputs = out.get(x.component, (x.pacing_mode, ()))
            if mode != x.pacing_mode:
                raise ValueError(f"conflicting pacing modes for {x.component}")
            out[x.component] = (mode, inputs + tuple(
                i for i in x.add_pacing_inputs if i not in inputs))
        return out

    def without(self, *components) -> "ProfileOverlay":
        """The same overlay minus some declarations, for counterfactuals."""
        keep = tuple(x for x in self.declarations if x.component not in components)
        return replace(self, declarations=keep,
                       version=self.version + "-minus-" + "-".join(components))

    def apply(self, records) -> tuple:
        by_key: dict = {}
        for x in self.declarations:
            by_key.setdefault((x.domain, x.component), []).append(x)
        out = []
        for r in records:
            decls = by_key.get((r.domain, r.component))
            if not decls:
                out.append(r)
                continue
            fns = tuple(r.affected_functions or ())
            deps = tuple(r.dependencies or ())
            for x in decls:
                fns += tuple(f for f in x.add_affected_functions if f not in fns)
                deps += tuple(d for d in x.add_dependencies if d not in deps)
            out.append(replace(r, affected_functions=fns, dependencies=deps))
        return tuple(out)


def _decl_dict(x) -> dict:
    d = {"domain": x.domain, "component": x.component,
         "add_affected_functions": list(x.add_affected_functions),
         "add_dependencies": list(x.add_dependencies),
         "kind": x.kind, "justification": x.justification,
         "source": x.source}
    if x.add_pacing_inputs:
        d["add_pacing_inputs"] = list(x.add_pacing_inputs)
        d["pacing_mode"] = x.pacing_mode
    return d


def load_successor(name: str = "aircraft_successor_r1") -> ProfileOverlay:
    """A versioned successor profile from `successor_profiles/`."""
    return ProfileOverlay.from_json(SUCCESSOR_DIR / f"{name}.json")
