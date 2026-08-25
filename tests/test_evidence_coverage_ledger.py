"""The coverage ledger's gate extractor, which must not be blank on anything.

The ledger's value is that "why is this relation dark" is a lookup instead of a
source-reading exercise. A relation whose gate column reads NOT FOUND has no
such answer, and the extractor used to be blank on exactly two relations --
`velocity_gps_doppler_0` and `_1`, which carry the flagship GNSS check --
because they are assigned inside a `for` loop, so the subscript is a Name that
`ast.literal_eval` cannot read.

Parses source. Reads no artifact and runs nothing.
"""

from __future__ import annotations

import ast
import importlib.util
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOL = os.path.join(ROOT, "tools", "simulation", "evidence_coverage_ledger.py")


def _load():
    spec = importlib.util.spec_from_file_location("_ecl", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ledger():
    return _load()


def test_every_relation_in_the_table_has_a_gate(ledger):
    """No relation may reach the table without an answer to 'why is it dark'."""
    gates = ledger.gate_expressions()
    missing = sorted(r for r in ledger.ENDPOINTS if r not in gates)
    assert not missing, f"gate expression not extracted for: {missing}"


def test_the_loop_constructed_doppler_edges_resolve(ledger):
    """The specific regression: both are gated on gvalid, in a for loop."""
    gates = ledger.gate_expressions()
    for rel in ("velocity_gps_doppler_0", "velocity_gps_doppler_1"):
        assert gates[rel] == "gvalid", (rel, gates[rel])


def test_extracted_gates_match_the_source_text(ledger):
    """Spot-check against what online.py actually says, not against itself."""
    gates = ledger.gate_expressions()
    assert gates["heading_course"] == "speed_gate * gvalid"
    assert gates["altitude_baro"] == "gvalid"
    assert gates["temp_bias_drift"] == "0.2"


def test_loop_bindings_reads_a_tuple_of_tuples(ledger):
    src = 'for n, acc, key in (("imu0", a0, "rel_0"), ("imu1", a1, "rel_1")):\n    E[key] = f(), g\n'
    node = ast.parse(src).body[0]
    assert ledger._loop_bindings(node) == {
        "n": ["imu0", "imu1"], "key": ["rel_0", "rel_1"]}


def test_loop_bindings_reads_a_plain_name_loop(ledger):
    node = ast.parse('for key in ("a", "b"):\n    E[key] = f(), g\n').body[0]
    assert ledger._loop_bindings(node) == {"key": ["a", "b"]}


def test_loop_bindings_refuses_a_shape_it_cannot_read(ledger):
    """An unrecognised loop must yield nothing rather than guess a key."""
    node = ast.parse('for key in some_list:\n    E[key] = f(), g\n').body[0]
    assert ledger._loop_bindings(node) == {}
    node = ast.parse('for a, b in ((x, y), (p, q)):\n    E[a] = f(), g\n').body[0]
    assert ledger._loop_bindings(node) == {}


def test_the_aliasing_ceiling_stays_below_half_the_tick_rate(ledger):
    """Arrivals are counted once per tick, so nothing above this is measurable.

    Nine false RATE_MISDECLARED findings came from testifying above it.
    """
    assert ledger.MEASURABLE_CEILING_HZ < ledger.TICK_HZ / 2.0
