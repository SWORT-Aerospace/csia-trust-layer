"""Runtime tests: online layer equivalence, source plugin contract, and the
failsafe state machine (the "critical mission emergency plan")."""

import numpy as np
import pytest

from csia.runtime import (FailsafeLevel, FailsafePolicy, OnlineTrustLayer,
                          SimulatedFlightSource, TrustLayerRuntime)


def _run_online(scenario, truth):
    src = SimulatedFlightSource(scenario, truth=truth)
    layer = OnlineTrustLayer()
    states = []
    last_t = 0.0
    for sensor, t, ch in src.samples():
        states.extend(layer.ingest(sensor, t, ch))
        last_t = t
    states.extend(layer.flush(last_t))
    return states


def test_online_matches_batch(truth, scenario_cache):
    """The deployable online layer and the batch replay pipeline are the
    same algorithm: fed identical samples, trust trajectories must agree.
    (Small tolerance: the online path calibrates the IMUs causally by
    replaying the buffered ground window, the batch path retroactively.)"""
    _, _, td, hist, diag = scenario_cache("gps_spoof")
    states = _run_online("gps_spoof", truth)
    n = min(len(states), len(hist.t))
    t = hist.t[:n]
    worst = {}
    for name in hist.names:
        batch = hist.trust[:n, hist.col(name)]
        online = np.array([s.trust[name] for s in states[:n]])
        # t 5-20 s: the decaying tail of the calibration-window difference
        # (online calibrates the IMUs causally, batch retroactively) —
        # bounded, and it must DECAY:
        early = float(np.abs(batch - online)[(t > 5) & (t < 20)].max())
        late = float(np.abs(batch - online)[t > 20].max())
        worst[name] = late
        assert early < 0.07, f"{name}: warm-up divergence {early:.3f}"
        assert late < 0.01, f"{name}: converged divergence {late:.3f}"
    print("\nonline-vs-batch converged divergence (t>20s): "
          f"max {max(worst.values()):.4f}")

    # diagnosis must agree on the story too
    gi = diag.causes.index("gps_fault")
    k = np.argmin(np.abs(t - 28.0))
    assert abs(states[k].posterior["gps_fault"]
               - diag.posterior[k, gi]) < 0.05


def test_source_emits_time_ordered_contract(truth):
    src = SimulatedFlightSource("clean", truth=truth)
    prev = -1.0
    seen = set()
    for i, (sensor, t, ch) in enumerate(src.samples()):
        assert t >= prev, "samples out of order"
        prev = t
        seen.add(sensor)
        if i > 2000:
            break
    assert seen == {"imu0", "imu1", "baro", "mag", "gps",
                    "motor_esc", "battery", "vibration"}


def _summary(scenario, truth):
    runtime = TrustLayerRuntime(SimulatedFlightSource(scenario, truth=truth))
    return runtime.run()


def test_failsafe_clean_no_false_alarms(truth):
    s = _summary("clean", truth)
    assert s.final_level == "NORMAL"
    assert not s.transitions, \
        f"clean flight raised failsafe: {[t.reasons for t in s.transitions]}"


def test_failsafe_gps_spoof_caution_and_recovery(truth):
    s = _summary("gps_spoof", truth)
    levels = [tr.level for tr in s.transitions]
    assert FailsafeLevel.CAUTION in levels
    assert FailsafeLevel.EMERGENCY not in levels, \
        "a nav fault with healthy attitude must not trigger emergency descent"
    caution = next(tr for tr in s.transitions
                   if tr.level == FailsafeLevel.CAUTION)
    assert 20.0 < caution.t < 28.0, f"caution at t={caution.t}"
    acts = [a for _, a in [(t, a) for t, a in s.actions]]
    assert "SWITCH_NAV_INERTIAL" in acts and "INHIBIT_GPS_MODES" in acts
    assert s.final_level == "NORMAL", "must de-escalate after spoof ends"


def test_failsafe_emergency_descent_on_attitude_loss(truth):
    """The user-facing contract: sensors failing -> the vehicle stabilizes
    and brings itself down."""
    s = _summary("dual_imu_failure", truth)
    assert s.final_level == "EMERGENCY"
    emer = next(tr for tr in s.transitions
                if tr.level == FailsafeLevel.EMERGENCY)
    names = [a.name for a in emer.actions]
    assert "STABILIZE" in names
    assert "CONTROLLED_DESCENT" in names
    descent = next(a for a in emer.actions if a.name == "CONTROLLED_DESCENT")
    assert descent.params["rate_mps"] > 0
    stab = next(a for a in emer.actions if a.name == "STABILIZE")
    assert stab.params["source"] in ("imu0", "imu1")
    # escalation went through CRITICAL first (prepare landing), not 0->3
    assert any(tr.level == FailsafeLevel.CRITICAL for tr in s.transitions)


def test_failsafe_not_armed_during_ground_checks(truth):
    policy = FailsafePolicy()
    states = _run_online("clean", truth)
    for st in states:
        if st.t < policy.cfg.arm_time:
            assert policy.update(st) == []
    assert policy.level == FailsafeLevel.NORMAL


def test_online_rejects_unknown_sensor():
    layer = OnlineTrustLayer()
    with pytest.raises(ValueError, match="unknown sensor"):
        layer.ingest("lidar", 0.0, {"range": 1.0})


def test_stale_sensor_watchdog(truth):
    """A sensor that goes SILENT (no samples, not just invalid ones) must be
    declared not-fresh and handled by the failsafe — silent death must never
    hold stale values forever."""
    from csia.runtime.plugins import SimulatedFlightSource

    class GpsSilentAfter30(SimulatedFlightSource):
        def samples(self):
            for sensor, t, ch in super().samples():
                if sensor == "gps" and t > 30.0:
                    continue
                yield sensor, t, ch

    runtime = TrustLayerRuntime(GpsSilentAfter30("clean", truth=truth),
                                keep_states=True)
    s = runtime.run()
    fresh_after = [st.fresh["gps"] for st in s.states if st.t > 31.0]
    assert not any(fresh_after), "silent GPS still reported fresh"
    levels = [tr.level for tr in s.transitions]
    assert FailsafeLevel.CAUTION in levels, \
        "GPS silence did not raise nav-degraded caution"
    caution = next(tr for tr in s.transitions
                   if tr.level == FailsafeLevel.CAUTION)
    assert "invalid" in " ".join(caution.reasons)


def _ground_stream(duration=30.0, hz=25.0, armed=None, climb=0.0,
                   vz_mode="true"):
    """Synthetic on-ground / steady-climb sample stream at uniform rate.
    armed: None = never report vehicle status; True/False = report it.
    vz_mode: 'true' = GPS reports real vz; 'fabricated' = vz forced to 0 but
    still claimed valid (the old GPS_RAW_INT behavior); 'flagged' = vz 0
    with vz_valid=False (the fixed GPS_RAW_INT mapping)."""
    G = 9.80665
    for i in range(int(duration * hz)):
        t = i / hz
        alt = climb * t
        vz = climb if vz_mode == "true" else 0.0
        gps_ch = {"pos": np.array([0.0, 0.0, alt]),
                  "vel": np.array([0.0, 0.0, vz]), "valid": True}
        if vz_mode == "flagged":
            gps_ch["vz_valid"] = False
        yield "imu0", t, {"accel": np.array([0.0, 0.0, G]),
                          "gyro": np.zeros(3), "valid": True}
        yield "imu1", t, {"accel": np.array([0.0, 0.0, G]),
                          "gyro": np.zeros(3), "valid": True}
        yield "baro", t, {"altitude": alt, "temp_c": 25.0, "valid": True}
        yield "mag", t, {"field_ut": np.array([22.0, 0.0, -42.0]),
                         "valid": True}
        yield "gps", t, gps_ch
        yield "motor_esc", t, {"rpm": np.zeros(4), "current": np.zeros(4),
                               "valid": True}
        yield "battery", t, {"voltage": 16.8, "current": 0.6, "valid": True}
        yield "vibration", t, {"rms": 0.08, "valid": True}
        if armed is not None:
            yield "vehicle_status", t, {"armed": armed}


def _run_stream(layer, stream):
    states = []
    for sensor, t, ch in stream:
        states.extend(layer.ingest(sensor, t, ch))
    return states


def test_disarmed_vehicle_gates_motor_edges_and_failsafe():
    """Real armed state: a vehicle idling DISARMED on the ground (rotors
    stopped, accel reading gravity) must not false-alarm its motor edges,
    and the failsafe must stay silent — for as long as it sits there."""
    layer = OnlineTrustLayer()
    states = _run_stream(layer, _ground_stream(duration=30.0, armed=False))
    late = [s for s in states if s.t > 10.0]
    assert late
    for s in late:
        assert s.armed is False
        assert s.edges["accel_motor_current"][1] == 0.0
        assert s.edges["accel_esc_rpm"][1] == 0.0
    worst = min(s.trust[n] for s in late
                for n in ("imu0", "imu1", "motor_esc"))
    assert worst > 0.7, f"disarmed ground idle degraded trust to {worst:.2f}"
    policy = FailsafePolicy()
    for s in states:
        assert policy.update(s) == [], "failsafe acted on a disarmed vehicle"
    assert policy.level == FailsafeLevel.NORMAL


def test_time_proxy_fallback_poisons_motor_edges_disarmed_ground():
    """Documents WHY real armed state matters: with no vehicle_status (the
    simulator time-proxy fallback), a disarmed ground idle drives the motor
    edges fully inconsistent once the t>5s proxy opens (gravity vs zero
    thrust), eroding imu1/motor_esc trust toward the strict profile's
    caution threshold. Graph fusion cushions the collapse — but the
    evidence is corrupted, which is exactly what armed gating prevents.
    (Measured: worst ~0.84 vs ~0.99 armed-aware.)"""
    layer = OnlineTrustLayer()
    states = _run_stream(layer, _ground_stream(duration=30.0, armed=None))
    late = [s for s in states if s.t > 15.0]
    last = late[-1]
    for key in ("accel_motor_current", "accel_esc_rpm"):
        c, gate = last.edges[key]
        assert gate == 1.0, "proxy should have gated the motor edges in"
        assert c < 0.05, "motor edges should read fully inconsistent"
    worst = min(s.trust[n] for s in late for n in ("imu1", "motor_esc"))
    assert worst < 0.87, "time-proxy no longer erodes trust; update docs"


def test_gps_vz_invalid_does_not_false_alarm_on_climb():
    """GPS vertical velocity: GPS_RAW_INT carries no vertical rate. A
    fabricated vz=0 during a steady 2 m/s climb reads as a spoof-like
    vertical residual in phys_gps (the old behavior); with vz_valid=False
    the layer judges horizontal only and GPS trust must hold."""
    def gps_min(vz_mode):
        layer = OnlineTrustLayer()
        states = _run_stream(layer, _ground_stream(
            duration=30.0, armed=False, climb=2.0, vz_mode=vz_mode))
        return min(s.trust["gps"] for s in states if s.t > 10.0)

    assert gps_min("true") > 0.85       # control: real vz is consistent
    assert gps_min("flagged") > 0.85    # the fix: no fabricated z-residual
    assert gps_min("fabricated") < 0.8  # the bug this guards against


def test_runtime_resets_on_source_time_jump(truth):
    """FC reboot / looped replay: source time going backwards must reset
    the layer (filters, calibration, tick counter) and keep running — not
    integrate a negative dt or die."""
    class RebootingSource(SimulatedFlightSource):
        def samples(self):
            for s, t, ch in super().samples():
                if t <= 20.0:
                    yield s, t, ch
            for s, t, ch in super().samples():
                if t <= 10.0:
                    yield s, t, ch

    rt = TrustLayerRuntime(RebootingSource("clean", truth=truth))
    s = rt.run()
    assert s.errors == 0
    assert 700 <= s.ticks <= 800, \
        f"expected ~750 ticks across the reboot, got {s.ticks}"


def test_bad_samples_counted_and_health_logged(truth, tmp_path):
    """Monitor self-health: malformed (NaN) telemetry is rejected before
    the filters, counted, surfaced in RunSummary, and written into every
    JSONL state line — the monitor reports on itself."""
    import json

    class CorruptBaro(SimulatedFlightSource):
        def samples(self):
            for s, t, ch in super().samples():
                if s == "baro" and 30.0 < t < 30.5:
                    ch = dict(ch, altitude=float("nan"))
                yield s, t, ch

    log_path = tmp_path / "run.jsonl"
    rt = TrustLayerRuntime(CorruptBaro("clean", truth=truth),
                           log_path=str(log_path))
    s = rt.run()
    assert s.bad_samples > 0, "NaN samples were not rejected/counted"
    assert s.errors == 0
    last = json.loads(log_path.read_text().strip().splitlines()[-1])
    assert last["health"]["bad_samples"] == s.bad_samples
    assert last["health"]["contained_errors"] == 0


def test_field_mode_withdrawn_plus_stale_holds_trust(truth):
    """Regression: in field mode, a chronically-noisy channel has its
    temporal evidence withdrawn (adapt_level > 25); if that sensor then
    goes stale, every edge and physics gate zeroes out and the node has NO
    evidence source left. This used to crash the whole runtime with
    ZeroDivisionError — it must instead hold trust and keep monitoring."""
    src = SimulatedFlightSource("clean", truth=truth)
    layer = OnlineTrustLayer(field_mode=True)
    last_t = 0.0
    states = []
    for sensor, t, ch in src.samples():
        if sensor == "gps" and t > 5.0:
            continue                          # gps goes silent -> stale
        layer.slots["gps"].adapt_level = 30.0  # chronic-noise withdrawal
        states.extend(layer.ingest(sensor, t, ch))
        last_t = t
        if t > 12.0:
            break
    states.extend(layer.flush(last_t))
    after = [s for s in states if s.t > 6.0]
    assert after, "runtime died after gps lost all evidence sources"
    assert not any(s.fresh["gps"] for s in after)
    t_ref = after[0].trust["gps"]
    assert all(abs(s.trust["gps"] - t_ref) < 1e-9 for s in after), \
        "trust must hold, not drift, with no evidence"


def test_runtime_contains_layer_errors(truth):
    """The monitor dying is itself a failure mode: an exception inside the
    trust math must be contained, counted, and surfaced — not kill the
    integrity monitor mid-flight."""
    class BombLayer(OnlineTrustLayer):
        def ingest(self, sensor, t, channels):
            if 20.0 < t < 21.0:
                raise RuntimeError("injected trust-math fault")
            return super().ingest(sensor, t, channels)

    runtime = TrustLayerRuntime(SimulatedFlightSource("clean", truth=truth),
                                layer=BombLayer())
    s = runtime.run()
    assert s.errors > 0, "injected faults were not counted"
    assert s.ticks > 1200, "runtime stopped monitoring after the fault window"
    assert s.final_level == "NORMAL"


def test_profiles_registry_and_validation(truth):
    from csia.profiles import PROFILES, get_profile
    import pytest as _pytest
    assert "sow001_quad" in PROFILES and "sow001_quad_strict" in PROFILES
    strict = get_profile("sow001_quad_strict")
    assert strict.failsafe.dwell_up < get_profile("sow001_quad").failsafe.dwell_up
    with _pytest.raises(KeyError):
        get_profile("mars_rover")
    bad = get_profile("sow001_quad")
    from dataclasses import replace
    with _pytest.raises(ValueError, match="edge library"):
        OnlineTrustLayer(profile=replace(bad, sensors=("imu0", "lidar")))


def test_live_feed_doc_shape(truth):
    """The live feed must be shape-compatible with replay JSON so the
    dashboard renders it with no special cases."""
    from csia.runtime.service import LiveFeed
    feed = LiveFeed()
    states = _run_online("clean", truth)[:100]
    for st in states:
        feed.push(st, "NORMAL")
    doc = feed.doc()
    assert doc is not None
    for key in ("t", "sensors", "trust", "components", "edges",
                "diagnosis", "aux", "layout", "latency_us", "faults"):
        assert key in doc, f"live doc missing {key}"
    assert len(doc["t"]) == 100
    assert set(doc["trust"]) == set(doc["sensors"])
    assert doc["aux"]["speed_gate"], "gate chart data missing"
    e0 = doc["edges"][0]
    assert {"key", "a", "b", "c", "gate"} <= set(e0)
