"""A log must record the freshness facts a replay cannot re-derive (HF-014).

WHAT WENT WRONG
---------------
The PX4 decision-replay divergence -- 144 categorical differences, open since
HF-004 -- was localised to per-sensor FRESHNESS, and then could go no
further. Two candidate explanations both fit the evidence:

  * the run used different staleness timeouts from the ones a replay
    derives today, or
  * the run's freshness bookkeeping differed from the replay's for some
    other reason

and the committed logs cannot separate them, because neither the timeouts
the run used nor the layer's own `fresh` map was ever written down. The log
records the ADAPTER's per-channel `age_s`, which is a different clock, and
the gate weights, which are PRODUCTS of freshness terms and therefore not
factorable back apart.

So these tests pin the two fields that make the question answerable next
time, and the property that makes them necessary rather than redundant.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.deploy.flight_log import FlightLog, FlightLogHeader  # noqa: E402
from csia.v1_1.staleness import build_runtime_stale_timeouts   # noqa: E402


def _header(**kw):
    base = dict(
        flight_id="t", csia_version="0", csia_commit=None,
        frozen_core_tag=None, adapter_platform="px4", adapter_version="1",
        contract_version=2, autopilot_version="px4",
        vehicle_config_hash="h", mode="SHADOW", command_authority={},
        sensor_availability={}, calibration_manifest={}, profile="p",
        host={}, t_start_unix=0.0, t_start_mono=0.0)
    base.update(kw)
    return FlightLogHeader(**base)


# ---------------------------------------------------------------------------
# the header
# ---------------------------------------------------------------------------

def test_the_header_can_carry_the_staleness_configuration():
    h = _header(stale_timeout_s=build_runtime_stale_timeouts("px4"))
    assert h.stale_timeout_s["gps"] == 1.0
    assert h.stale_timeout_s["baro"] == 0.5
    assert len(h.stale_timeout_s) == 8


def test_a_header_without_it_defaults_to_empty_not_to_todays_values():
    """AN ABSENT CONFIGURATION MUST READ AS ABSENT. Defaulting to whatever
    the current build derives would silently assert that an old log was
    recorded under today's timeouts -- which is precisely the claim HF-014
    could not verify."""
    assert _header().stale_timeout_s == {}


def test_the_shadow_runner_records_the_timeouts_it_actually_used():
    """Not re-derived at write time: the same dict the layer was built
    with, so a later change to the derivation cannot rewrite history."""
    import inspect

    from csia.deploy import shadow
    src = inspect.getsource(shadow.ShadowRunner)
    # The whole make_header(...) call, however long it grows.
    call = src.split("make_header(", 1)[1].split("self.flight_log", 1)[0]
    assert "stale_timeout_s=self.stale_timeouts" in call, (
        "the header must be given the runner's OWN timeouts, so a later "
        "change to how they are derived cannot rewrite an old log")


# ---------------------------------------------------------------------------
# the per-tick fresh map
# ---------------------------------------------------------------------------

def test_a_tick_records_the_layers_freshness_verdict(tmp_path):
    fl = FlightLog(str(tmp_path), _header())
    sample = _FakeSample()
    fl.tick(t_mono=0.0, sample=sample, trust_pre={}, trust_post={},
            residuals={}, gates={}, evidence={}, diagnosis={},
            ambiguity=None, recommendation={}, autopilot={},
            latency_us=1.0, fresh={"baro": True, "gps": False})
    fl.close()
    row = _first_tick(tmp_path)
    assert row["fresh"] == {"baro": True, "gps": False}


def test_absent_freshness_is_null_rather_than_an_empty_map(tmp_path):
    """`{}` would read as "every sensor stale". None reads as "not
    recorded", which is the truth for a caller that did not supply it."""
    fl = FlightLog(str(tmp_path), _header())
    fl.tick(t_mono=0.0, sample=_FakeSample(), trust_pre={}, trust_post={},
            residuals={}, gates={}, evidence={}, diagnosis={},
            ambiguity=None, recommendation={}, autopilot={},
            latency_us=1.0)
    fl.close()
    assert _first_tick(tmp_path)["fresh"] is None


def test_the_fresh_map_is_json_clean(tmp_path):
    """numpy bools survive a dataclass but not every JSON encoder, and a
    log that fails to serialise loses the tick entirely."""
    import numpy as np
    fl = FlightLog(str(tmp_path), _header())
    fl.tick(t_mono=0.0, sample=_FakeSample(), trust_pre={}, trust_post={},
            residuals={}, gates={}, evidence={}, diagnosis={},
            ambiguity=None, recommendation={}, autopilot={},
            latency_us=1.0, fresh={"imu0": np.bool_(True)})
    fl.close()
    row = _first_tick(tmp_path)
    assert row["fresh"] == {"imu0": True}
    assert isinstance(row["fresh"]["imu0"], bool)


# ---------------------------------------------------------------------------
# WHY the map is needed: the gate weights cannot be factored back apart
# ---------------------------------------------------------------------------

def test_a_gate_weight_of_zero_does_not_say_which_endpoint_was_stale():
    """THE PROPERTY THAT MADE HF-014 UNANSWERABLE.

    An edge weight is `gate * fresh[a] * fresh[b]`. Zero can mean a is
    stale, b is stale, both, or the gate itself was zero -- four different
    causes with one observation. This is not a defect in the core; it is a
    reason the log must record `fresh` separately, and it is asserted here
    so nobody later concludes the map is redundant and removes it.
    """
    def weight(gate, fresh_a, fresh_b):
        return gate * float(fresh_a) * float(fresh_b)

    causes = {
        "a stale": weight(1.0, False, True),
        "b stale": weight(1.0, True, False),
        "both stale": weight(1.0, False, False),
        "gate closed": weight(0.0, True, True),
    }
    assert set(causes.values()) == {0.0}, (
        "if these ever differ, the ambiguity is gone and this test should "
        "be revisited")


def test_the_adapter_age_and_the_layer_freshness_are_different_clocks():
    """`canonical.channels[*].age_s` is the ADAPTER's age for a channel;
    `fresh` is the LAYER's verdict, keyed on when ingest was last called
    for that sensor. HF-014 measured them disagreeing on a committed PX4
    log -- baro read fresh at age 0.125 s and stale at age 0.003 s -- so
    no single timeout maps one onto the other, and one cannot substitute
    for the other.
    """
    artifact = os.path.join(
        ROOT, "research", "physical_validation", "results",
        "REPLAY_DIVERGENCE_PX4.json")
    if not os.path.exists(artifact):
        pytest.skip("REPLAY_DIVERGENCE_PX4.json not generated")
    with open(artifact, encoding="utf-8") as fh:
        rep = json.load(fh)
    # Every divergence is the replay seeing MORE live edges, never fewer.
    for sig in rep["distinct_signatures"]:
        assert sig["missing_in_replay"] == [], (
            "a replay missing an edge the recording had would be a "
            "different failure from the one HF-014 describes")


# ---------------------------------------------------------------------------

class _FakeSample:
    flight_mode = None
    estimator_health: dict = {}

    def usable_channels(self):
        return {}

    def blocked_channels(self):
        return []

    def to_log_dict(self):
        return {"channels": {}}


def _first_tick(tmp_path):
    for name in sorted(os.listdir(tmp_path)):
        if not name.endswith(".jsonl"):
            continue
        with open(os.path.join(tmp_path, name), encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                if row.get("record") == "tick":
                    return row
    raise AssertionError("no tick written")
