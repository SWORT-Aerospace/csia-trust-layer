"""Pytest plugin: run the EXISTING tests with Semantic Core 2.1 decisions.
RESEARCH ONLY, never loaded by default.

Used only by `test_migration_probe.py` (Phase H), which starts a separate
pytest process with `-p semantic_2_1_pytest_plugin`. In that process only, and
in memory only, the frozen v2 entry points return what 2.1 decides, in the
2.0.0 schema:

- `csia.v2.localization.localize` and `localize_all`;
- `csia.v2.attribution.attribute`;
- `csia.v2.engine.AssuranceEngine.evaluate`, whose localizations and
  attribution are replaced;
- `csia.v2.signatures.PREDICATES` and `SYMPTOMS`: the successor table, the
  same dict object refilled, and the scoped detector.

The question it answers is: which existing test would assert something
different if 2.1 were the semantics? No file is written and no frozen file
is edited. A normal pytest run never sees this module: it is not named
`test_*`, it lives outside `tests/`, and nothing imports it.
"""
from __future__ import annotations

import dataclasses

# The successor imports the frozen functions by name first, so it keeps the
# originals when the module attributes are rebound below.
import csia_semantic_core as C
from csia.v2 import attribution as A
from csia.v2 import engine as EN
from csia.v2 import localization as L
from csia.v2 import signatures as SIG
from csia_semantic_core import SemanticCore21, SuccessorIndex
from csia_semantic_core.predicates import (successor_predicate_table,
                                           successor_symptoms)

_localize = L.localize
_evaluate = EN.AssuranceEngine.evaluate
#: Kept ON the engine, never keyed by id(): an id can be reused after the
#: engine is collected, which would hand one profile another's tables.
_CORE_ATTR = "_semantic_core_2_1_probe_core"


def localize_2_1(spec, index, subject, predicates):
    six = SuccessorIndex(index.records, tracing=False)
    table = successor_predicate_table(dict(predicates))
    (spec,) = successor_symptoms((spec,))
    return _localize(spec, six, subject, table)


def localize_all_2_1(specs, records, predicates):
    """Localization only, like the frozen function: no attribution runs."""
    core = SemanticCore21(specs, predicates, (), trace=False)
    six = SuccessorIndex(records, tracing=False)
    return tuple(x.v2 for x in C.localize_all_2_1(core.symptoms, six,
                                                  core.predicates, False))


def attribute_2_1(records, relations=()):
    six = SuccessorIndex(records, tracing=False)
    return C.attribute_2_1(six.records, relations).v2


def evaluate_2_1(self, snapshot):
    sa = _evaluate(self, snapshot)
    core = self.__dict__.get(_CORE_ATTR)
    if core is None:
        core = SemanticCore21.from_engine(self, trace=False)
        self.__dict__[_CORE_ATTR] = core
    tr = core.reason(sa.records)
    return dataclasses.replace(
        sa, localizations=tuple(x.v2 for x in tr.localizations),
        attribution=tr.attribution.v2)


def pytest_configure(config):
    table = successor_predicate_table(dict(SIG.PREDICATES))
    SIG.PREDICATES.clear()
    SIG.PREDICATES.update(table)
    SIG.SYMPTOMS = successor_symptoms(SIG.SYMPTOMS)
    SIG.SYMPTOMS_BY_ID = {s.symptom_id: s for s in SIG.SYMPTOMS}
    L.localize = localize_2_1
    L.localize_all = localize_all_2_1
    A.attribute = attribute_2_1
    EN.AssuranceEngine.evaluate = evaluate_2_1
    config.addinivalue_line("markers", "semantic_2_1_probe: set by the plugin")
