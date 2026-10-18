"""Platform profiles — §25.

    Avoid aircraft-only naming in the core plugin framework.
    Platform-specific adapters live outside the common core.

Everything platform-specific lives here: which rails exist, which processes
matter, what a function is called and what it requires. `csia/v2/*.py` — the
evidence record, the plugin contract, the registry, the function graph, the
attribution — contains no aircraft term and no profile-specific constant, and
a test asserts that by parsing the module source.

Two profiles are built:

    `aircraft`    the multirotor v1.1 already serves, with v1.1 wrapped as
                  the SENSOR domain
    `test_stand`  §37's electric motor test stand: no SENSOR domain, no v1.1,
                  no aviation vocabulary anywhere in its construction

The genericity claim of §37 is exactly the difference between them. If the
second one needed a single line of aviation-specific code, the framework
would be aircraft-specific and the answer to §38 would be A.

LAZY, FOR THE SAME REASON THE DOMAINS ARE
-----------------------------------------
`from csia.v2.profiles import SCENARIOS` still works and still spans both
profiles. But `from csia.v2.profiles.test_stand import build_test_stand_engine`
now loads the bench and nothing else — no aircraft table, no v1.1 stack. A
test runs the bench in a fresh interpreter and asserts neither was ever
imported, which is the only form of that claim worth making.
"""

import importlib

_MODULES = {
    "aircraft": ("AIRCRAFT_FUNCTIONS", "AIRCRAFT_RELATIONS",
                 "SOURCE_DEPENDENCIES", "V1_1_FUNCTIONS",
                 "build_aircraft_engine", "build_v1_1_baseline_engine"),
    "aircraft_scenarios": ("AIRCRAFT_NOMINAL", "AIRCRAFT_SCENARIOS",
                           "example_payload_feed", "load_v1_1_example"),
    "test_stand": ("TEST_STAND_FUNCTIONS", "TEST_STAND_RELATIONS",
                   "build_test_stand_engine"),
    "test_stand_scenarios": ("TEST_STAND_NOMINAL", "TEST_STAND_SCENARIOS"),
    "pump_skid": ("PUMP_SKID_FUNCTIONS", "PUMP_SKID_RELATIONS",
                  "PUMP_SKID_NOMINAL", "PUMP_SKID_SCENARIOS",
                  "build_pump_skid_engine"),
    "matched_scenarios": ("MATCHED_SCENARIOS", "MATCHED_BY_NAME",
                          "MATCHED_SETS", "SET_SYMPTOM"),
}
_EXPORTS = {name: mod for mod, names in _MODULES.items() for name in names}

#: Assembled on first access, spanning both profiles. It is here rather than
#: in `csia/v2/scenarios.py` because the harness deliberately knows about no
#: platform and therefore cannot hold this table.
_DERIVED = ("SCENARIOS", "ENGINE_BUILDERS")

__all__ = sorted(set(_EXPORTS) | set(_DERIVED) | {"build_engine_for"})


def _scenarios():
    from .aircraft_scenarios import AIRCRAFT_SCENARIOS
    from .matched_scenarios import MATCHED_SCENARIOS
    from .pump_skid import PUMP_SKID_SCENARIOS
    from .test_stand_scenarios import TEST_STAND_SCENARIOS
    return {s.name: s for s in (AIRCRAFT_SCENARIOS + TEST_STAND_SCENARIOS
                                + PUMP_SKID_SCENARIOS + MATCHED_SCENARIOS)}


def _engine_builders():
    from .aircraft import build_aircraft_engine
    from .pump_skid import build_pump_skid_engine
    from .test_stand import build_test_stand_engine
    return {"aircraft": build_aircraft_engine,
            "test_stand": build_test_stand_engine,
            "pump_skid": build_pump_skid_engine}


def build_engine_for(scenario):
    """The engine a scenario should be run against."""
    return _engine_builders()[scenario.system]()


def __getattr__(name):
    if name == "SCENARIOS":
        return _scenarios()
    if name == "ENGINE_BUILDERS":
        return _engine_builders()
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(f".{module}", __name__), name)


def __dir__():
    return sorted(set(__all__) | set(globals()))
