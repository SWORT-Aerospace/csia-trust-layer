"""The frozen core must be deterministic: same log in, same trust out.

THIS FILE HAS NEVER EXISTED BEFORE, AND CI HAS BEEN PRETENDING IT DID.
`.github/workflows/v11.yml` carries a step named "determinism" that ran

    pytest -q tests/test_determinism.py -k determin || true

against a file that was never written. pytest exits 4 on a missing path, and
`|| true` turned that into green. The step has therefore reported success for
the entire life of the repository while testing nothing, which is worse than
having no step at all: it occupied the place where a real check would go.

WHAT DETERMINISM MEANS HERE, precisely. Replaying one committed flight log
through a fresh `OnlineTrustLayer` twice, in the same process, must produce
bit-identical trust trajectories. That is the property every replay-based
result in this repository silently assumes:

  * `diagnose_escalation.py` withholds its diagnosis unless a replay
    reproduces the logged trust, and reported worst delta 0.0 across 6000
    values;
  * the Mechanism B reconstruction compares T_hat against T_runtime at 1e-15;
  * the post-hoc S0 sensitivity re-steps recorded traces.

If the core were not deterministic, every one of those comparisons would be
measuring scheduler noise and calling it agreement. Nothing checked it.

The core is FROZEN, so this test only observes it.
"""

import glob
import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))

from csia.runtime.online import OnlineTrustLayer              # noqa: E402


def _a_committed_flight_log():
    """Any real flight log this repository has kept, or None."""
    for pat in ("logs/mechanism_b_gps/*.trace.jsonl",
                "research/v1_1/results/mechanism_b/*.trace.jsonl.gz",
                "research/v1_1/results/mechanism_b_gps/*.trace.jsonl.gz"):
        hits = sorted(glob.glob(os.path.join(ROOT, pat)))
        if hits:
            return hits[0]
    return None


def _replay(path, limit=400):
    """Drive the frozen core from a recorded flight log. Returns trajectories."""
    from profile_core_from_log import core_samples_for_tick, load_ticks
    layer = OnlineTrustLayer(tick_hz=25.0, field_mode=True)
    out, prev, n = [], None, 0
    for tick in load_ticks(path):
        samples = core_samples_for_tick(tick, prev)
        prev = {k: v["value"]
                for k, v in tick["canonical"]["channels"].items()
                if v.get("usable")}
        for sensor, t, chans in samples:
            for state in layer.ingest(sensor, t, chans) or []:
                out.append((round(state.t, 6),
                            tuple(sorted((k, float(v))
                                         for k, v in state.trust.items()))))
                n += 1
        if n >= limit:
            break
    return out


def _flight_log(min_ticks=200):
    """A flight log with enough content to be worth replaying.

    NOT simply the first file found. `logs/` accumulates aborted runs -- the
    first ArduPilot log in this checkout is a 30-tick fragment that yields
    zero core samples, and a determinism test that "passed" on it would be
    comparing two empty lists.
    """
    from profile_core_from_log import core_samples_for_tick, load_ticks
    for pat in ("logs/shadow-sitl-ardupilot/*.jsonl",
                "logs/mechanism_b_gps/*.jsonl",
                "logs/shadow-sitl-px4/*.jsonl"):
        for path in sorted(glob.glob(os.path.join(ROOT, pat)), reverse=True):
            if "trace" in os.path.basename(path):
                continue
            try:
                ticks = list(load_ticks(path))
            except (OSError, ValueError):
                continue
            if len(ticks) < min_ticks:
                continue
            if core_samples_for_tick(ticks[5], None):
                return path
    return None


class TestFrozenCoreDeterminism:

    def test_a_flight_log_is_available_to_replay(self):
        """Guard the guard: no log means these tests prove nothing."""
        if _flight_log() is None:
            pytest.skip("no committed flight log in this checkout")

    def test_two_replays_of_one_log_agree_exactly(self):
        path = _flight_log()
        if path is None:
            pytest.skip("no committed flight log in this checkout")
        a = _replay(path)
        b = _replay(path)
        assert a, "replay produced no engine states"
        assert len(a) == len(b), (
            f"replay produced {len(a)} states then {len(b)}; the core's tick "
            f"firing is not reproducible")
        for i, (ra, rb) in enumerate(zip(a, b)):
            assert ra == rb, (
                f"divergence at engine step {i}, t={ra[0]}:\n"
                f"  run 1 {ra[1]}\n  run 2 {rb[1]}")

    def test_a_fresh_layer_starts_from_the_same_prior_every_time(self):
        one = OnlineTrustLayer(tick_hz=25.0, field_mode=True)
        two = OnlineTrustLayer(tick_hz=25.0, field_mode=True)
        assert one.core.alpha == two.core.alpha
        assert one.core.beta == two.core.beta
        assert one.core.trust == two.core.trust

    def test_the_comparison_would_notice_a_difference(self):
        """A determinism test that cannot fail is not a determinism test."""
        path = _flight_log()
        if path is None:
            pytest.skip("no committed flight log in this checkout")
        a = _replay(path)
        assert a, "replay produced no engine states"
        b = list(a)
        assert len(b[0]) == 2
        t, trust = b[0]
        perturbed = tuple((k, v + 1e-12) for k, v in trust)
        b[0] = (t, perturbed)
        assert a[0] != b[0], (
            "the trajectory comparison does not see a 1e-12 perturbation, so "
            "it could not see a real divergence either")
