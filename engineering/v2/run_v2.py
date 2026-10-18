"""CSIA v2 — the full run behind `V2_CHATGPT_REVIEW_REPORT.md`.

    python engineering/v2/run_v2.py

Produces, in `engineering/v2/`:

    V2_DECLARATIONS.json      what each plugin declares, both profiles
    V2_BASELINE_V1_1.json     §36 over EVERY real v1.1 payload, not two
    V2_SCENARIO_RESULTS.json  §§27, 28, 37: all scenarios, all ticks
    V2_LEDGER_EXAMPLE.json    one scenario's ledger, chain verified
    V2_COMPUTE.json           per-tick cost, CORE vs REPORTING
    V2_COMPLEXITY.json        what the framework actually costs to carry

THE §36 RUN IS THE ONE THAT MATTERS
-----------------------------------
`tests/test_v2_navigation_baseline.py` checks the wrapper against the two
committed example payloads, which is enough for CI and not enough for a
claim. This script regenerates the **complete per-tick payload stream** for
every applicable v1.1 mechanism using the Phase 4D machinery — the same
`_payloads()` that produced the committed examples — and asserts exactness on
every tick of every one. Thousands of payloads, all real, none synthesised.

NO NUMBER IN THE ARTIFACTS IS INVENTED. Where a measurement could not be
made, the artifact says so with a null and a reason rather than an estimate.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, ".."))
P4 = os.path.join(ENG, "v1_1", "phase4")
for p in (ROOT, P4, os.path.join(ENG, "v1_1", "ablation"),
          os.path.join(ENG, "v1_1", "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.v2 import api as API                                   # noqa: E402
from csia.v2 import scenarios as SC                              # noqa: E402
from csia.v2.domain import Snapshot                              # noqa: E402
from csia.v2.domains.navigation import _STATE                    # noqa: E402
from csia.v2.engine import coverage_report                       # noqa: E402
from csia.v2.functions import RANK                               # noqa: E402
from csia.v2.ledger import (V2AssuranceLedger,                   # noqa: E402
                            V2LedgerContext, plugin_manifest_hash)
from csia.v2.profiles import (SCENARIOS, build_aircraft_engine,  # noqa: E402
                              build_engine_for,
                              build_test_stand_engine,
                              build_v1_1_baseline_engine)
from csia.v2.profiles.aircraft import (SOURCE_DEPENDENCIES,      # noqa: E402
                                       V1_1_FUNCTIONS)
from csia.v2.profiles.aircraft_scenarios import (                # noqa: E402
    example_payload_feed, load_v1_1_example)

TICKS = 200
#: The exactness check runs on every payload; the six-domain monotonicity
#: pass runs on every Nth. Stated here, reported in the artifact.
MONOTONICITY_STRIDE = 10
_INVERSE = {v.value: k for k, v in _STATE.items()}


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _write(name, obj):
    path = os.path.join(_HERE, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


# ------------------------------------------------------------ declarations
def declarations():
    air, bench = build_aircraft_engine(), build_test_stand_engine()
    return {
        "artifact": "V2_DECLARATIONS",
        "generation_command": "python engineering/v2/run_v2.py",
        "aircraft": {
            "declarations": air.declarations(),
            "coverage": coverage_report(air),
            "plugin_manifest_hash": plugin_manifest_hash(air),
        },
        "test_stand": {
            "declarations": bench.declarations(),
            "coverage": coverage_report(bench),
            "plugin_manifest_hash": plugin_manifest_hash(bench),
        },
        "note": "the two profiles register the SAME domain classes with "
                "different declarations; the test stand registers no SENSOR "
                "domain at all",
    }


# --------------------------------------------------------------- §36 run
def _real_payload_streams():
    """Every applicable v1.1 mechanism, regenerated tick by tick.

    Returns `{mechanism: [payload, ...]}` or `None` with a reason, if the
    Phase 4 machinery is unavailable in this environment. It is never faked.
    """
    try:
        from run_p4b import _series
        from run_p4c import _config_hash
        from run_p4d import _payloads
        from run_phase3b import MECHANISMS, _hashes
        import support as S
    except Exception as exc:                       # pragma: no cover
        return None, f"phase 4 machinery unavailable: {type(exc).__name__}: " \
                     f"{exc}"
    import run_p4d
    prov = {"software_sha": _git("rev-parse", "HEAD"),
            "configuration_hash": _config_hash(), "input_trace_hash": ""}
    out = {}
    for mech, spec in MECHANISMS.items():
        if spec["status"] != "APPLICABLE":
            continue
        cached = _series(mech)
        td = cached[0]
        dec, _sup = S.support_series(td, stride=1)
        run_p4d._DEC[id(td)] = dec
        prov_m = dict(prov, input_trace_hash=_hashes(td)["raw_trace_sha256"])
        out[mech] = _payloads(mech, cached, prov_m)
    return out, None


def baseline_v1_1():
    """§36: the wrapper reproduces v1.1 exactly, on every real payload."""
    streams, why = _real_payload_streams()
    base = build_v1_1_baseline_engine()
    full = build_aircraft_engine()

    result = {
        "artifact": "V2_BASELINE_V1_1",
        "generation_command": "python engineering/v2/run_v2.py",
        "section": "36",
        "claim": "with only the SENSOR domain registered, every v2 function "
                 "state equals the v1.1 payload's function_eligibility "
                 "exactly; and adding the other five domains can only hold "
                 "or restrict a function, never relax one",
    }
    if streams is None:
        result.update(
            payloads_checked=0, exact=None, unavailable_reason=why,
            note="NO CLAIM IS MADE FROM THIS RUN. The committed example "
                 "payloads are still checked by tests/"
                 "test_v2_navigation_baseline.py.")
        return result

    # The EXACTNESS check runs on every payload. The MONOTONICITY check runs
    # on a stride, because it needs the full six-domain engine and each pass
    # re-validates the payload against the v1.1 JSON Schema at ~27 ms a
    # time -- see V2_COMPUTE.json. The stride is stated in the artifact
    # rather than hidden, and the number of ticks it covers is reported.
    checked = mismatches = relaxed = full_checked = 0
    per_mech = {}
    for mech, payloads in sorted(streams.items()):
        m_bad = m_relaxed = m_full = 0
        for i, p in enumerate(payloads):
            want = {k: v["state"]
                    for k, v in p["function_eligibility"].items()}
            got = base.evaluate(Snapshot(t=p["timestamp"], signals={},
                                         v1_1_payload=p)).functions
            if {k: v.state for k, v in got.items()} != want:
                m_bad += 1
            checked += 1
            if i % MONOTONICITY_STRIDE:
                continue
            # Against a snapshot where every OTHER domain is at its worst --
            # the input that would expose any leakage into the SENSOR column.
            f = full.evaluate(Snapshot(t=p["timestamp"],
                                       signals=_worst_case_signals(),
                                       v1_1_payload=p))
            m_full += 1
            for name in V1_1_FUNCTIONS:
                if RANK[f.functions[name].state] < RANK[want[name]]:
                    m_relaxed += 1
                if _INVERSE[f.functions[name].domain_states["SENSOR"]] != \
                        want[name]:
                    m_bad += 1
        per_mech[mech] = {"payloads": len(payloads), "mismatches": m_bad,
                          "full_engine_ticks_checked": m_full,
                          "relaxations": m_relaxed}
        mismatches += m_bad
        relaxed += m_relaxed
        full_checked += m_full
        print(f"  {mech:20s} {len(payloads):5d} payloads  "
              f"mismatches={m_bad}  relaxations={m_relaxed}", flush=True)

    result.update(
        mechanisms=sorted(streams),
        payloads_checked=checked,
        full_engine_ticks_checked=full_checked,
        monotonicity_stride=MONOTONICITY_STRIDE,
        per_mechanism=per_mech,
        exact=(mismatches == 0),
        monotonic=(relaxed == 0),
        mismatches=mismatches,
        relaxations=relaxed,
        payload_source="regenerated per tick by engineering/v1_1/phase4/"
                       "run_p4d.py:_payloads, the same function that produced "
                       "the committed example payloads",
        scope_note=f"exactness was checked on ALL {checked} payloads; "
                   f"monotonicity and the SENSOR-column identity on every "
                   f"{MONOTONICITY_STRIDE}th ({full_checked} ticks), because "
                   f"each full-engine pass re-validates the payload against "
                   f"the v1.1 JSON Schema",
    )
    return result


def _worst_case_signals():
    return {"POWER": {"battery": {}, "rail_5v": {}, "rail_3v3": {}},
            "COMPUTE": {"state_estimator": {"alive": False}, "csia": {},
                        "logger": {}, "cpu": {"cpu_load": 1.0}},
            "TIMING": {}, "COMMUNICATION": {}, "ACTUATION": {}}


def shared_rail_search():
    """§28-E asks for a shared rail affecting TWO SENSORS.

    The committed fixloss payload has one unfresh source. This looks through
    every real payload for a tick where two or more sources on the SAME
    declared rail are simultaneously adverse, and reports what it finds --
    including finding nothing, which is a result and not a failure.
    """
    streams, why = _real_payload_streams()
    if streams is None:
        return {"searched": 0, "unavailable_reason": why}
    hits, searched, adverse_ticks = [], 0, 0
    reasons = {"NOT_FRESH": 0, "SEQUENTIAL_ALARM": 0}
    for mech, payloads in sorted(streams.items()):
        for p in payloads:
            searched += 1
            # Exactly what the wrapper calls adverse for a source, with no
            # trust floor declared: not fresh, or in a sequential alarm.
            alarming = set(p["sequential"].get("alarming", ()))
            adverse = sorted(
                {n for n, ok in p["evidence"]["fresh"].items() if not ok}
                | alarming)
            for n, ok in p["evidence"]["fresh"].items():
                if not ok:
                    reasons["NOT_FRESH"] += 1
            reasons["SEQUENTIAL_ALARM"] += len(alarming)
            if adverse:
                adverse_ticks += 1
            rails: dict = {}
            for node in adverse:
                for dep in SOURCE_DEPENDENCIES.get(node, ()):
                    rails.setdefault(dep, []).append(node)
            for rail, nodes in rails.items():
                if len(nodes) >= 2:
                    hits.append({"mechanism": mech, "t": p["timestamp"],
                                 "rail": rail, "sources": sorted(nodes)})
    return {
        "searched": searched,
        "ticks_with_at_least_one_adverse_source": adverse_ticks,
        "adverse_source_readings_by_reason": reasons,
        "ticks_with_two_or_more_sources_adverse_on_one_rail": len(hits),
        "examples": hits[:5],
        "adverse_definition": "not fresh, or named in sequential.alarming -- "
                              "the same test csia/v2/domains/navigation.py "
                              "applies, with no trust floor declared",
        "note": "if this is zero, no real v1.1 payload in the corpus has two "
                "sources on one declared rail adverse at the same tick, and "
                "the SHARED_RAIL scenario demonstrates the common-cause "
                "mechanism with one source plus two links instead. That is "
                "stated rather than worked around: no payload was edited to "
                "manufacture the literal two-sensor form, and "
                "tests/test_v2_framework.py exercises it directly on "
                "constructed records.",
    }


# ------------------------------------------------------------- scenarios
def scenarios():
    out, ledgers = {}, {}
    for name, sc in sorted(SCENARIOS.items()):
        engine = build_engine_for(sc)
        feed = (example_payload_feed(sc.v1_1_variant)
                if sc.system == "aircraft" else None)
        led = V2AssuranceLedger(V2LedgerContext(
            profile=sc.system, software_sha=_git("rev-parse", "HEAD"),
            configuration_hash=_config_digest(engine),
            plugin_manifest_hash=plugin_manifest_hash(engine)))
        results = []
        for snap in SC.SnapshotSource(sc, ticks=TICKS, payload_for=feed):
            a = engine.evaluate(snap)
            results.append(a)
            led.observe(a)
        ok, problems = led.verify_chain()
        out[name] = {
            "system": sc.system, "section": sc.section,
            "description": sc.description,
            "expectation_written_before_the_run": sc.expectation,
            "tags": list(sc.tags),
            "v1_1_variant": sc.v1_1_variant if sc.system == "aircraft"
            else None,
            **SC.summarize(results),
            "ledger": {"events": len(led.events), "chain_ok": ok,
                       "problems": list(problems),
                       "head": led.to_dict()["head"]},
        }
        ledgers[name] = led
    return {
        "artifact": "V2_SCENARIO_RESULTS",
        "generation_command": "python engineering/v2/run_v2.py",
        "ticks_per_scenario": TICKS,
        "note": "SYNTHETIC. Every injected value was chosen to exercise a "
                "declared threshold. None is a measurement, and none "
                "supports a claim about how any real hardware behaves.",
        "scenarios": out,
    }, ledgers


def _config_digest(engine) -> str:
    return hashlib.sha256(
        json.dumps(engine.declarations(), sort_keys=True).encode("utf-8")
    ).hexdigest()[:32]


# --------------------------------------------------------------- compute
def compute_cost():
    """§29's discipline, carried into v2 — and the correction it forced.

    The first version of this measurement timed all six domains as one
    "core_domains" phase and reported ~28 ms. That number was almost entirely
    `csia.v1_1.monitor.parse` running INSIDE the SENSOR domain: the v1.1
    payload is re-validated against its JSON Schema on every call, at ~27 ms
    a time. Reporting it as a v2 decision cost would have been the same
    mistake Phase 4 caught in its own compute figure -- timing one part of a
    pipeline and labelling it with the name of the whole.

    So each domain is timed separately, and the headline is reported twice:
    including and excluding the v1.1 ingest. The v2 decision proper is the
    second number.
    """
    sc = SCENARIOS["REGULATOR_FAILURE"]
    engine = build_aircraft_engine()
    feed = example_payload_feed("clean")
    snaps = list(SC.SnapshotSource(sc, ticks=TICKS, payload_for=feed))
    led = V2AssuranceLedger(V2LedgerContext(
        profile="aircraft", software_sha="x", configuration_hash="y",
        plugin_manifest_hash=plugin_manifest_hash(engine)))

    from csia.v2.attribution import attribute
    from csia.v2.engine import SystemAssurance
    from csia.v2.evidence import worst
    from csia.v2.functions import system_state

    domain_ids = [d.domain_id for d in engine.registry.domains()]
    phases = {f"domain_{d}": [] for d in domain_ids}
    phases.update({k: [] for k in ("functions", "attribution", "ledger",
                                   "api_build", "api_serialize")})
    for snap in snaps:
        records, domain_states = [], {}
        for domain in engine.registry.domains():
            t0 = time.perf_counter()
            r = domain.evaluate(snap)
            phases[f"domain_{domain.domain_id}"].append(
                (time.perf_counter() - t0) * 1e6)
            records.extend(r.records)
            domain_states[domain.domain_id] = worst(r.records).value

        t0 = time.perf_counter()
        verdicts = engine.functions.evaluate(records)
        t1 = time.perf_counter()
        attr = attribute(records, engine.relations)
        t2 = time.perf_counter()
        a = SystemAssurance(t=snap.t, system=system_state(verdicts),
                            domains=domain_states, functions=verdicts,
                            attribution=attr, records=tuple(records))
        t3 = time.perf_counter()
        led.observe(a)
        t4 = time.perf_counter()
        doc = API.build(a, profile="aircraft", provenance={},
                        declarations=None)
        t5 = time.perf_counter()
        json.dumps(doc, sort_keys=True)
        t6 = time.perf_counter()
        phases["functions"].append((t1 - t0) * 1e6)
        phases["attribution"].append((t2 - t1) * 1e6)
        phases["ledger"].append((t4 - t3) * 1e6)
        phases["api_build"].append((t5 - t4) * 1e6)
        phases["api_serialize"].append((t6 - t5) * 1e6)

    # The v1.1 parse on its own, so the SENSOR domain's figure is legible.
    from csia.v1_1.monitor import parse as _v1_1_parse
    _p = load_v1_1_example("clean")
    _t = time.perf_counter()
    for _ in range(50):
        _v1_1_parse(_p)
    parse_us = (time.perf_counter() - _t) / 50 * 1e6

    stats = {k: {"median_us": round(statistics.median(v), 3),
                 "mean_us": round(statistics.fmean(v), 3),
                 "max_us": round(max(v), 3)} for k, v in phases.items()}
    med = {k: stats[k]["median_us"] for k in stats}
    sensor = med["domain_SENSOR"]
    other_domains = round(sum(med[f"domain_{d}"] for d in domain_ids
                              if d != "SENSOR"), 3)
    decision = round(other_domains + med["functions"] + med["attribution"], 3)
    reporting = round(med["ledger"] + med["api_build"]
                      + med["api_serialize"], 3)
    return {
        "artifact": "V2_COMPUTE",
        "generation_command": "python engineering/v2/run_v2.py",
        "measured_on": f"REGULATOR_FAILURE, {TICKS} ticks, six domains, "
                       f"CPython on a general-purpose host",
        "phases_us_per_tick": stats,
        "v2_decision_us_per_tick_excluding_v1_1_ingest": decision,
        "v1_1_ingest_us_per_tick": round(sensor, 3),
        "v1_1_payload_parse_us_measured_alone": round(parse_us, 1),
        "total_including_v1_1_ingest_us_per_tick": round(sensor + decision, 3),
        "reporting_us_per_tick": reporting,
        "records_per_tick": len(build_aircraft_engine().evaluate(
            snaps[len(snaps) // 2]).records),
        "headline": "the v2 decision over six domains costs "
                    f"{decision} us/tick; ingesting the v1.1 payload costs "
                    f"{round(sensor, 1)} us/tick, of which "
                    f"{round(parse_us, 1)} us is JSON Schema validation",
        "correction_note":
            "AN EARLIER VERSION OF THIS MEASUREMENT WAS WRONG AND IS "
            "RECORDED HERE RATHER THAN QUIETLY REPLACED. It timed all six "
            "domains as one phase and reported ~28000 us as 'core'. That "
            "number was almost entirely csia.v1_1.monitor.parse running "
            "inside the SENSOR domain -- the same class of mistake Phase 4 "
            "caught in its own compute figure. Each domain is now timed "
            "separately and the headline is reported twice.",
        "note": "CORE and REPORTING are separated for the same reason Phase 4 "
                "separated them: folding logging and serialisation into a "
                "decision-path figure would overstate what an embedded port "
                "must carry. NO TARGET-HARDWARE FIGURE EXISTS AND NONE IS "
                "CLAIMED. The v1.1 core figure from Phase 4 is NOT comparable "
                "-- it measured a different thing on a different scenario.",
        "v1_1_ingest_note":
            "csia.v1_1.monitor.parse validates the payload against "
            "engineering/v1_1/csia_output_v1_1.schema.json on EVERY call, and "
            "that dominates the tick by roughly two orders of magnitude. It "
            "is a property of ingesting schema 1.1.0 strictly, NOT of the v2 "
            "decision, and an integration that validates once at ingest "
            "rather than once per consumer does not pay it repeatedly. "
            "NOTHING WAS CHANGED IN v1.1 TO IMPROVE THIS NUMBER (section 19); "
            "it is reported as measured.",
    }


# ------------------------------------------------------------ complexity
def complexity():
    """What the framework costs to carry, counted rather than asserted."""
    import ast

    def measure(path):
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        code = [ln for ln in src.splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
        return {
            "lines": len(src.splitlines()),
            "code_lines_excluding_comments": len(code),
            "functions": sum(1 for n in ast.walk(tree)
                             if isinstance(n, ast.FunctionDef)),
            "classes": sum(1 for n in ast.walk(tree)
                           if isinstance(n, ast.ClassDef)),
        }

    v2 = os.path.join(ROOT, "csia", "v2")
    core, domains, profiles = {}, {}, {}
    for name in sorted(os.listdir(v2)):
        if name.endswith(".py"):
            core[name] = measure(os.path.join(v2, name))
    for sub, into in (("domains", domains), ("profiles", profiles)):
        d = os.path.join(v2, sub)
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                into[name] = measure(os.path.join(d, name))

    air = build_aircraft_engine()
    return {
        "artifact": "V2_COMPLEXITY",
        "generation_command": "python engineering/v2/run_v2.py",
        "core": core, "domains": domains, "profiles": profiles,
        "totals": {
            k: sum(v["code_lines_excluding_comments"] for v in group.values())
            for k, group in (("core", core), ("domains", domains),
                             ("profiles", profiles))},
        "registered_domains_aircraft": len(air.registry),
        "relations_declared": sum(len(d.relations)
                                  for d in air.registry.domains()),
        "cross_domain_relations": len(air.relations),
        "functions_aircraft": len(air.functions.names()),
        "note": "the cost of ADDING a domain is one module implementing "
                "`evaluate`, plus its declarations in a profile. No core "
                "module changes; the six built domains are the evidence for "
                "that, and the five specified-not-built ones are the test "
                "of it that has not been run.",
    }


# ------------------------------------------------------------------ main
def main() -> int:
    paths = []
    paths.append(_write("V2_DECLARATIONS.json", declarations()))

    base = baseline_v1_1()
    base["shared_rail_search"] = shared_rail_search()
    paths.append(_write("V2_BASELINE_V1_1.json", base))

    scen, ledgers = scenarios()
    paths.append(_write("V2_SCENARIO_RESULTS.json", scen))
    paths.append(_write("V2_LEDGER_EXAMPLE.json",
                        ledgers["REGULATOR_FAILURE"].to_dict()))
    paths.append(_write("V2_COMPUTE.json", compute_cost()))
    paths.append(_write("V2_COMPLEXITY.json", complexity()))

    # -- a worked §17-shaped output, as an actual API document -----------
    sc = SCENARIOS["ESTIMATOR_LATE"]
    engine = build_engine_for(sc)
    res = SC.run(engine, sc, ticks=TICKS,
                 payload_for=example_payload_feed("clean"))
    doc = API.validate(API.build(
        res[-1], profile="aircraft",
        provenance={"software_sha": _git("rev-parse", "HEAD")},
        declarations=engine.declarations()))
    paths.append(_write("V2_OUTPUT_EXAMPLE.json", doc))

    print("=" * 70)
    print("CSIA v2 RUN")
    print("=" * 70)
    print(f"\n§36 baseline: {base['payloads_checked']} real v1.1 payloads, "
          f"exact={base.get('exact')} monotonic={base.get('monotonic')}")
    if base.get("unavailable_reason"):
        print(f"  UNAVAILABLE: {base['unavailable_reason']}")
    srs = base["shared_rail_search"]
    print(f"§28-E search: {srs.get('searched', 0)} payloads, "
          f"{srs.get('ticks_with_two_or_more_sources_adverse_on_one_rail')} "
          f"with two sources adverse on one rail")
    print(f"\nscenarios: {len(scen['scenarios'])} at {TICKS} ticks each")
    for name, row in sorted(scen["scenarios"].items()):
        f = row["final"]
        print(f"  {name:22s} {f['system']:12s} {f['attribution']:12s} "
              f"limited by {','.join(f['limiting_domains']) or '-'}")
    print(f"\nledger chains verified: "
          f"{sum(1 for r in scen['scenarios'].values() if r['ledger']['chain_ok'])}"
          f"/{len(scen['scenarios'])}")
    print("\n§17-shaped output (ESTIMATOR_LATE, final tick):")
    print(res[-1].summary())
    print("\nartifacts:")
    for p in paths:
        print(f"  {os.path.relpath(p, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
