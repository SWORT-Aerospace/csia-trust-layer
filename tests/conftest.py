"""Shared fixtures: one truth flight and cached scenario pipeline runs.

Every scenario is deterministic (fixed seeds), so results are cached at
session scope — the full suite runs each scenario exactly once.
"""

import pytest

from csia.scenarios import SCENARIOS, run_scenario
from csia.sensors import generate_flight


@pytest.fixture(scope="session")
def truth():
    return generate_flight()


@pytest.fixture(scope="session")
def scenario_cache(truth):
    cache = {}

    def get(name: str):
        if name not in cache:
            cache[name] = run_scenario(name, truth=truth)
        return cache[name]  # (title, faults, td, hist, diag)

    return get


@pytest.fixture(scope="session")
def clean_run(scenario_cache):
    return scenario_cache("clean")


def pytest_collection_modifyitems(items):
    # keep scenario harness tests last (they are the slow ones)
    items.sort(key=lambda it: "scenarios" in str(it.fspath))
