"""CSIA INTEGRATION QUICKSTART — runnable, self-checking.

    python engineering/v2/quickstart.py

Run it from anywhere with the package installed. It needs no repository
checkout and no data directory.

WHY THIS EXISTS
---------------
The obvious first thing to write against the v2 API is

    engine = build_engine_for(SCENARIOS["NOMINAL"])
    results = run(engine, scenario, ticks=5)

and it returns TEN FUNCTIONS IN `UNKNOWN`, limited by SENSOR, with no
localizations. Nothing is broken: on the aircraft profile the SENSOR domain is
the v1.1 wrapper, and with no v1.1 payload supplied it has no evidence --
which the layer correctly reports as UNKNOWN rather than as health. But a
newcomer sees ten UNKNOWNs and reasonably concludes something is wrong with
the library.

That is a missing on-ramp, not a defect in the layer, and this file is the
on-ramp. Step 1 reproduces the trap deliberately so the difference between
"absent evidence" and "a broken install" is visible once and never again.

EVERY STEP ASSERTS ITS OWN RESULT. If the printed narrative and the behaviour
ever diverge, this exits non-zero rather than printing a comforting story.
`tests/test_quickstart.py` runs it in CI.
"""

from __future__ import annotations

import sys


def _h(n, title):
    print(f"\n{'=' * 72}\n{n}. {title}\n{'=' * 72}")


def step1_the_trap():
    _h(1, "THE TRAP: no v1.1 payload means no SENSOR evidence")
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import SCENARIOS, build_engine_for

    sc = SCENARIOS["NOMINAL"]
    engine = build_engine_for(sc)
    final = SC.run(engine, sc, ticks=5)[-1]

    for name, v in sorted(final.functions.items()):
        spec = engine.functions.functions[name]
        needs = "SENSOR" in spec.required_domains
        print(f"  {name:<24} {v.state:<9} "
              f"limited_by={str(v.limiting_domain):<7} "
              f"{'requires SENSOR' if needs else ''}")

    unknown = {n for n, v in final.functions.items() if v.state == "UNKNOWN"}
    needs_sensor = {n for n, s in engine.functions.functions.items()
                    if "SENSOR" in s.required_domains}
    # THE POINT, and it is sharper than "everything breaks": the set that
    # goes UNKNOWN is EXACTLY the set that requires the silent domain.
    assert unknown == needs_sensor, (unknown, needs_sensor)
    assert all(final.functions[n].limiting_domain == "SENSOR"
               for n in unknown)
    eligible = set(final.functions) - unknown
    assert all(final.functions[n].state == "ELIGIBLE" for n in eligible)

    print(f"\n  {len(unknown)} UNKNOWN, {len(eligible)} ELIGIBLE, and the")
    print("  UNKNOWN set is EXACTLY the set of functions that require SENSOR.")
    print("  On the aircraft profile SENSOR is the v1.1 wrapper, and with no")
    print("  v1.1 payload it has no evidence to transcribe.")
    print("\n  Nothing is broken. `UNKNOWN` is not `ELIGIBLE`: a domain that")
    print("  reported nothing has not reported health. A consumer that treats")
    print("  absent evidence as permission has inverted the contract. Note")
    print("  the loss is SURGICAL -- a silent domain removes exactly the")
    print("  functions that need it, and leaves the rest alone.")
    return engine


def step2_the_right_wiring():
    _h(2, "THE RIGHT WIRING: supply the v1.1 payload the SENSOR domain wraps")
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import SCENARIOS, build_engine_for
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed

    sc = SCENARIOS["NOMINAL"]
    engine = build_engine_for(sc)
    final = SC.run(engine, sc, ticks=20,
                   payload_for=example_payload_feed("clean"))[-1]

    for name, v in sorted(final.functions.items()):
        print(f"  {name:<24} {v.state}")
    plugins = {k: v["state"] for k, v in sorted(final.plugins.items())}
    print(f"\n  plugins: {plugins}")
    print(f"  localizations: {len(final.localizations)}  "
          f"(nothing is wrong, so there is nothing to localize)")

    assert {v.state for v in final.functions.values()} == {"ELIGIBLE"}
    assert set(plugins.values()) == {"AVAILABLE"}
    assert not final.localizations
    return final


def step3_a_fault_and_what_it_says():
    _h(3, "A FAULT: what the layer actually reports, and what it will not say")
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import build_engine_for
    from csia.v2.profiles.matched_scenarios import MATCHED_BY_NAME
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed

    sc = MATCHED_BY_NAME["MS_A2_COMMUNICATION_DELAY"]
    engine = build_engine_for(sc)
    feed = example_payload_feed(getattr(sc, "v1_1_variant", "clean"))
    final = SC.run(engine, sc, ticks=60, payload_for=feed)[-1]

    loc = [x for x in final.localizations if x.symptom == "OUTPUT_STALE"]
    assert loc, "the injected transport delay produced no OUTPUT_STALE symptom"
    x = loc[0]
    print(f"  symptom   : {x.symptom} on {x.subject}")
    print(f"  verdict   : {x.verdict}")
    print(f"  started at: {len(x.initial_candidates)} candidate hypotheses "
          f"across {len(x.initial_domains)} domains")
    print(f"  supported : {list(x.supported)}")
    print(f"  rejected  :")
    for h, why in x.rejected:
        print(f"                {h:<32} refuted by {why}")
    print(f"  unresolved: {list(x.unresolved) or 'none'}")

    assert x.verdict == "SUPPORTED"
    assert x.supported == ("COMMUNICATION/transport_delay",)
    assert not x.unresolved
    print("\n  Every elimination NAMES the predicate that did it. There is no")
    print("  anonymous elimination, and no cause is asserted without a")
    print("  discriminating measurement.")
    return final


def step4_ambiguity_is_a_real_answer():
    _h(4, "AMBIGUITY: the layer will refuse to name a unique cause")
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import build_engine_for
    from csia.v2.profiles.matched_scenarios import MATCHED_BY_NAME
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed

    sc = MATCHED_BY_NAME["MS_B4_MECHANICAL"]
    engine = build_engine_for(sc)
    final = SC.run(engine, sc, ticks=60,
                   payload_for=example_payload_feed(
                       getattr(sc, "v1_1_variant", "clean")))[-1]
    loc = [x for x in final.localizations
           if x.symptom == "COMMAND_NO_RESPONSE"]
    assert loc
    x = loc[0]
    print(f"  symptom   : {x.symptom} on {x.subject}")
    print(f"  verdict   : {x.verdict}")
    print(f"  supported : {list(x.supported)}")
    print(f"  unmeasurable on this platform: {list(x.unmeasurable)}")
    assert x.verdict == "AMBIGUOUS"
    assert len(x.supported) == 2
    print("\n  Two hypotheses are supported by the SAME observation and this")
    print("  airframe has no channel that separates them. The layer reports")
    print("  AMBIGUOUS rather than picking one. A consumer must be able to")
    print("  act on that; it is the honest answer, not a failure.")


def step5_a_failed_plugin_never_reads_healthy():
    _h(5, "PLUGIN FAILURE: a crashed domain is FAILED, never healthy")
    from csia.v2 import scenarios as SC
    from csia.v2.plugin_runtime import FAILED, FailingDomain
    from csia.v2.profiles import SCENARIOS, build_engine_for
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed

    sc = SCENARIOS["NOMINAL"]
    engine = build_engine_for(sc)
    engine.registry.replace(FailingDomain(engine.registry.get("POWER"),
                                          mode="raise", after_tick=1))
    final = SC.run(engine, sc, ticks=6,
                   payload_for=example_payload_feed("clean"))[-1]

    st = final.plugins["POWER"]
    print(f"  POWER plugin state: {st['state']}")
    print(f"  last error        : {st['last_error'][:60]}")
    touched = sorted(f for f, v in final.functions.items()
                     if "POWER" in v.domain_states)
    print(f"  functions declaring POWER: {len(touched)}")
    print(f"  their POWER domain_state : "
          f"{sorted({final.functions[f].domain_states['POWER'] for f in touched})}")
    others = {k: v["state"] for k, v in sorted(final.plugins.items())
              if k != "POWER"}
    print(f"  other plugins still reporting: {others}")

    assert st["state"] == FAILED
    assert all(final.functions[f].domain_states["POWER"] == "UNAVAILABLE"
               for f in touched)
    assert set(others.values()) == {"AVAILABLE"}
    print("\n  The failure propagates as ABSENCE of evidence. It does not")
    print("  crash the engine, and it does not read as health.")


def step6_the_integrator_rules():
    _h(6, "THE FOUR RULES, checked rather than asserted")
    from csia.v2 import scenarios as SC
    from csia.v2.explanation import explain_all
    from csia.v2.profiles import SCENARIOS, build_engine_for
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed

    sc = SCENARIOS["NOMINAL"]
    engine = build_engine_for(sc)
    final = SC.run(engine, sc, ticks=20,
                   payload_for=example_payload_feed("clean"))[-1]
    ex = explain_all(final, engine.functions)

    # 1. UNKNOWN is not ELIGIBLE -- demonstrated in step 1.
    print("  1. UNKNOWN is not ELIGIBLE                       "
          "-- demonstrated in step 1")

    # 2. an ELIGIBLE function has no limiting domain
    bad = [e.function for e in ex if e.state == "ELIGIBLE"
           and e.limiting_domains]
    assert not bad, bad
    print(f"  2. an ELIGIBLE function has no limiting domain   "
          f"-- {len(ex)} explanations, {len(bad)} violations")

    # 3. possible_domains are alternatives, never causes
    overlap = [e.function for e in ex
               if set(e.limiting_domains) & set(e.possible_domains)]
    assert not overlap, overlap
    print(f"  3. possible_domains never overlap limiting       "
          f"-- {len(overlap)} violations")

    # 4. no wall-clock reading reaches the replayable document
    leaked = [k for st in final.plugins.values() for k in st
              if k in ("last_execution_s", "max_execution_s",
                       "deadline_misses")]
    assert not leaked, leaked
    print(f"  4. no wall-clock field in the per-tick document  "
          f"-- {len(leaked)} leaked")

    print("\n  And the layer issues NO COMMAND. There is no code path from")
    print("  here to an actuator; the controller decides what to do.")


def main() -> int:
    print("CSIA INTEGRATION QUICKSTART")
    print("SIMULATION / RESEARCH PROTOTYPE -- NOT FLIGHT SOFTWARE")
    step1_the_trap()
    step2_the_right_wiring()
    step3_a_fault_and_what_it_says()
    step4_ambiguity_is_a_real_answer()
    step5_a_failed_plugin_never_reads_healthy()
    step6_the_integrator_rules()
    print(f"\n{'=' * 72}")
    print("All steps asserted their own result. See")
    print("  engineering/v2/CONTROLLER_INTEGRATION_SPEC.md   the contract")
    print("  docs/product/CSIA_READINESS.md                  what it is and "
          "is not ready for")
    return 0


if __name__ == "__main__":
    sys.exit(main())
