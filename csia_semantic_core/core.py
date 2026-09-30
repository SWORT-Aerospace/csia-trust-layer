"""One tick through Semantic Core 2.1.0, and its 2.0.0 view.

`SemanticCore21` is configured once from a symptom table, a predicate table
and a relation table: an engine's own, or any other. `reason(records)` then
evaluates one tick of evidence records.

- **Nothing is mutated.** Records are read, never changed. The historical
  adapter `reason_historical_tick` evaluates a recorded 2.0.0
  `SystemAssurance`, or its `to_dict()` document, under 2.1.0 and leaves the
  original exactly as it was.
- **2.1.0 is not the default.** Nothing in `csia/` imports this package, and
  the frozen engine still produces 2.0.0.

`Corrections` switches each approved correction separately. That serves two
purposes: every changed decision can be attributed to the rule that changed
it, and with every correction off the 2.0.0 view is frozen v2, byte for byte
(the identity check). C5 and C7 have no switch, because they change labels
and trace and never a decision.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState

from .attribution import attribute_2_1
from .index import SuccessorIndex
from .localization import localize_all_2_1
from .predicates import (successor_predicate_table, successor_symptoms,
                         validate_table)

SEMANTICS_VERSION = "2.1.0"
SCHEMA = "csia.semantic_core/2.1.0"
#: The version whose view `to_v2_0_view` produces.
HISTORICAL_SEMANTICS_VERSION = "2.0.0"


@dataclass(frozen=True)
class Corrections:
    """The approved decision-affecting corrections. All on by default."""

    c1: bool = True    # relevance-gated discriminator
    f2: bool = True    # localization-agreement gate
    c2: bool = True    # Kleene aggregation
    c3: bool = True    # subject scope
    c4: bool = True    # error transparency
    c6: bool = True    # idempotence and same-key conflicts

    @classmethod
    def none(cls) -> "Corrections":
        return cls(**{f.name: False for f in fields(cls)})

    @classmethod
    def only(cls, *ids) -> "Corrections":
        want = {i.lower() for i in ids}
        unknown = want - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown corrections: {sorted(unknown)}")
        return cls(**{f.name: f.name in want for f in fields(cls)})

    def ids(self) -> tuple:
        return tuple(f.name.upper() for f in fields(self)
                     if getattr(self, f.name))


@dataclass(frozen=True)
class TickResult:
    localizations: tuple
    attribution: object
    corrections: Corrections
    duplicates_collapsed: dict
    conflicting_keys: tuple

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "semantics_version": SEMANTICS_VERSION,
            "corrections": list(self.corrections.ids()),
            "localization": [x.to_dict() for x in self.localizations],
            "attribution": self.attribution.to_dict(),
            "evidence_handling": {
                "duplicates_collapsed": dict(self.duplicates_collapsed),
                "conflicting_keys_not_read": list(self.conflicting_keys)},
        }

    def to_v2_0_view(self) -> dict:
        """The same decisions in the 2.0.0 schema and labels: the
        `attribution` and `localization` entries of
        `SystemAssurance.to_dict()`."""
        return {"attribution": self.attribution.to_v2_0_dict(),
                "localization": [x.to_v2_0_dict()
                                 for x in self.localizations]}


class SemanticCore21:
    """Semantic Core 2.1.0, configured for one symptom, predicate and
    relation table."""

    def __init__(self, symptoms, predicates, relations=(),
                 corrections: Corrections = Corrections(),
                 trace: bool = True):
        self.corrections = corrections
        self.relations = tuple(relations)
        self.trace = trace
        c = corrections
        self.symptoms = successor_symptoms(symptoms, c2=c.c2, c3=c.c3)
        self.predicates = successor_predicate_table(
            dict(predicates), c2=c.c2, c3=c.c3, c4=c.c4)
        validate_table(self.symptoms, self.predicates)

    @classmethod
    def from_engine(cls, engine, corrections: Corrections = Corrections(),
                    trace: bool = True) -> "SemanticCore21":
        """The tables a frozen `AssuranceEngine` reasons with. The engine is
        read, not changed."""
        return cls(engine.symptoms, engine.predicates, engine.relations,
                   corrections, trace)

    def reason(self, records) -> TickResult:
        c = self.corrections
        index = SuccessorIndex(records, c6=c.c6, tracing=self.trace)
        locs = (localize_all_2_1(self.symptoms, index, self.predicates,
                                 detailed_trace=self.trace)
                if self.symptoms else ())
        attr = attribute_2_1(index.records, self.relations, locs,
                             c1=c.c1, f2=c.f2)
        return TickResult(locs, attr, c, dict(index.duplicates_collapsed),
                          tuple(sorted(f"{comp}:{rel}"
                                       for rel, comp in index.conflicts)))


def reason_historical_tick(assurance, core: SemanticCore21) -> TickResult:
    """Evaluate a recorded 2.0.0 tick under 2.1.0 without modifying it.

    `assurance` is a frozen `SystemAssurance`, or the dict its `to_dict()`
    produced. Only its evidence records are read.
    """
    if isinstance(assurance, dict):
        return core.reason(records_from_v2_0_document(assurance))
    return core.reason(assurance.records)


_TUPLES = ("affected_functions", "reason_codes", "dependencies")
_DERIVED = ("latencies",)


def records_from_v2_0_document(doc: dict) -> tuple:
    """Rebuild the evidence records of a `SystemAssurance.to_dict()`
    document. The document is not changed."""
    names = {f.name for f in fields(EvidenceRecord)}
    out = []
    for raw in doc.get("evidence", ()):
        kw = {k: v for k, v in raw.items()
              if k in names and k not in _DERIVED}
        kw["observation_state"] = ObservationState(kw["observation_state"])
        kw["applicability"] = Applicability(kw["applicability"])
        for k in _TUPLES:
            if k in kw and kw[k] is not None:
                kw[k] = tuple(kw[k])
        kw["provenance"] = dict(kw.get("provenance") or {})
        kw["detail"] = dict(kw.get("detail") or {})
        out.append(EvidenceRecord(**kw))
    return tuple(out)
