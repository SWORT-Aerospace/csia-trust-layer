"""Pytest plugin: run EXISTING tests with 2.1.1 as the default. RESEARCH ONLY,
never loaded by default.

Used only by `property_rerun.py`, which starts a separate pytest process with
`-p revised_defaults_pytest_plugin`. In that process only, and in memory
only, `Corrections()` and the default `corrections` of `SemanticCore21` and
`SemanticCore21.from_engine` mean `Corrections.revised()` (all three
revisions on). `Corrections.none()` and `Corrections.only(...)` keep their
explicit meaning. No file is written and nothing outside the process sees
it. A normal pytest run never loads this module: it is not named `test_*`,
it lives outside `tests/`, and nothing imports it.

No pacing map is given, so R-2's starvation predicate answers None with the
gap NO_DECLARED_PACING_INPUT wherever a test builds a core itself.
"""
from __future__ import annotations

import csia_semantic_core.core as CC


def pytest_configure(config):
    defaults = CC.Corrections.__init__.__defaults__
    CC.Corrections.__init__.__defaults__ = tuple(True for _ in defaults)
    rev = CC.Corrections.revised()
    rel, _c, trace, pacing = CC.SemanticCore21.__init__.__defaults__
    CC.SemanticCore21.__init__.__defaults__ = (rel, rev, trace, pacing)
    _c, trace, pacing = CC.SemanticCore21.from_engine.__func__.__defaults__
    CC.SemanticCore21.from_engine.__func__.__defaults__ = (rev, trace, pacing)
