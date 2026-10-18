#!/usr/bin/env python3
"""Adversarial profile mutations (Part 23) and the validator check (Part 40).
RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_shadow/adversarial_profiles.py

A profile's declarations travel on the evidence records (`affected_functions`,
`dependencies`, `domain`), so a profile mistake is simulated by rewriting
those fields on every tick of dataset A before reasoning. The evidence
itself (observation states, values) is untouched. Each mutation is run
through frozen v2.0 (`localize_all` + `attribute`, which also read those
fields) and through 2.1, and compared with the same reasoner on the
unmutated records:

    crashed       the reasoner raised (a failure that at least is loud)
    overconfident a graded unit becomes WRONG (true hypothesis rejected or a
                  wrong one SUPPORTED), or a wrong UNIQUE appears
    underconfident a correct SUPPORTED / UNIQUE is lost, or a real
                  POSITION_UNAVAILABLE stops being raised
    spurious      POSITION_UNAVAILABLE raised on a function the scenario
                  does not affect
    detected      `csia_semantic_core.profile_validator` reports the
                  mutation on the first tick of the mutated profile

Writes ADVERSARIAL_PROFILE_RESULTS.json only.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (str(REPO), str(REPO / "research/csia_semantic_correctness"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import ground_truth as GT  # noqa: E402
import semantic_probe as P  # noqa: E402

from csia.v2.attribution import UNIQUE, attribute  # noqa: E402
from csia.v2.localization import SUPPORTED, localize_all  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import SemanticCore21  # noqa: E402
from csia_semantic_core.profile_validator import validate_profile  # noqa: E402

OUT = HERE / "ADVERSARIAL_PROFILE_RESULTS.json"
NAV = ("PRECISION_NAVIGATION", "POSITION_HOLD", "AUTONOMOUS_MISSION")


def _edit(records, match, **change):
    out = []
    for r in records:
        if match(r):
            kw = {k: (v(r) if callable(v) else v) for k, v in change.items()}
            r = replace(r, **kw)
        out.append(r)
    return tuple(out)


def _is(domain, comp, relation=None):
    return lambda r: (r.domain == domain and r.component == comp
                      and (relation is None or r.relation == relation))


def _nav_segment(r):
    return r.domain == "TIMING" and r.component.split(".", 1)[0] == "nav_solution"


MUTATIONS = {
    "M1_MISSING_EDGE_nav_solution_not_on_estimator": (
        "missing edge: the position channel no longer declares that it depends on the estimator",
        lambda rs: _edit(rs, _nav_segment, dependencies=lambda r: tuple(
            d for d in r.dependencies if d != "COMPUTE/state_estimator"))),
    "M1b_MISSING_SERVING_precision_undeclared": (
        "missing edge: nothing declares it serves PRECISION_NAVIGATION (G-1 reproduced on a sibling)",
        lambda rs: _edit(rs, lambda r: "PRECISION_NAVIGATION" in r.affected_functions
                         and r.domain in ("TIMING", "COMPUTE", "COMMUNICATION"),
                         affected_functions=lambda r: tuple(
                             f for f in r.affected_functions if f != "PRECISION_NAVIGATION"))),
    "M2_EXTRA_EDGE_esc_can_serves_navigation": (
        "extra irrelevant edge: the ESC CAN bus declared to serve the navigation functions (R-BAD)",
        lambda rs: _edit(rs, _is("COMMUNICATION", "esc_can"),
                         affected_functions=lambda r: tuple(r.affected_functions) + (
                             "COARSE_NAVIGATION", "POSITION_HOLD", "PRECISION_NAVIGATION"))),
    "M2b_EXTRA_EDGE_telemetry_serves_navigation": (
        "extra irrelevant edge: the telemetry downlink declared to serve position hold and precision navigation",
        lambda rs: _edit(rs, _is("COMMUNICATION", "telemetry_radio"),
                         affected_functions=lambda r: tuple(r.affected_functions) + (
                             "POSITION_HOLD", "PRECISION_NAVIGATION"))),
    "M3_WRONG_SUBJECT_typo": (
        "wrong subject: the position channel names 'PRECISION_NAVIGATON' (a typo)",
        lambda rs: _edit(rs, _nav_segment, affected_functions=lambda r: tuple(
            "PRECISION_NAVIGATON" if f == "PRECISION_NAVIGATION" else f
            for f in r.affected_functions))),
    "M4_WRONG_DOMAIN_dependency": (
        "wrong domain: the estimator declares it depends on SENSOR/cpu instead of COMPUTE/cpu",
        lambda rs: _edit(rs, _is("COMPUTE", "state_estimator"), dependencies=lambda r: tuple(
            "SENSOR/cpu" if d == "COMPUTE/cpu" else d for d in r.dependencies))),
    "M4b_WRONG_DOMAIN_record": (
        "wrong domain: the GNSS link's records are labelled SENSOR instead of COMMUNICATION",
        lambda rs: _edit(rs, _is("COMMUNICATION", "gnss_serial"), domain="SENSOR")),
    "M5_DUPLICATE_RELATION_identical": (
        "duplicate relation: every estimator record appears twice, identical",
        lambda rs: tuple(rs) + tuple(r for r in rs if _is("COMPUTE", "state_estimator")(r))),
    "M5b_DUPLICATE_RELATION_conflicting_declaration": (
        "duplicate relation: every estimator record appears twice, the copy declaring no dependencies",
        lambda rs: tuple(rs) + tuple(replace(r, dependencies=()) for r in rs
                                     if _is("COMPUTE", "state_estimator")(r))),
    "M6_CYCLE_cpu_depends_on_estimator": (
        "cycle: the CPU declared to depend on the estimator that depends on it",
        lambda rs: _edit(rs, _is("COMPUTE", "cpu"), dependencies=lambda r: tuple(
            r.dependencies) + ("COMPUTE/state_estimator",))),
}


def grade_loc(scenario, symptom, supported, unresolved, rejected, verdict):
    th = GT.true_hypothesis(scenario, symptom)
    if th == GT.UNSPECIFIED:
        return "UNGRADED"
    if th is None:
        return "WRONG" if verdict == SUPPORTED else "OK"
    if th in rejected:
        return "WRONG"
    if verdict == SUPPORTED:
        return "CERTAIN" if list(supported) == [th] else "WRONG"
    return "OK" if th in set(supported) | set(unresolved) else "UNGRADED"


def run_v20(engine, recs):
    locs = localize_all(engine.symptoms, recs, engine.predicates) if engine.symptoms else ()
    a = attribute(recs, engine.relations)
    return ([(x.symptom, x.subject, x.supported, x.unresolved,
              tuple(h for h, _ in x.rejected), x.verdict) for x in locs],
            a.verdict, [c.id for c in a.candidates])


def run_v21(core, recs):
    tr = core.reason(recs)
    return ([(x.symptom, x.subject, x.supported, x.unresolved,
              tuple(h for h, _ in x.v2.rejected), x.v2.verdict) for x in tr.localizations],
            tr.attribution.verdict, list(tr.attribution.candidates))


def compare(name, records, base, mut):
    """-> dict of counters for one tick."""
    c = {"overconfident": 0, "underconfident": 0, "spurious": 0, "changed": 0}
    if base == mut:
        return c
    c["changed"] = 1
    bl = {(s, subj): (sup, unr, rej, v) for s, subj, sup, unr, rej, v in base[0]}
    ml = {(s, subj): (sup, unr, rej, v) for s, subj, sup, unr, rej, v in mut[0]}
    for k in set(bl) | set(ml):
        sym, subj = k
        should = GT.symptom_should_exist(name, sym, subj)
        if k in bl and k not in ml:
            c["underconfident"] += int(should is True)
            continue
        if k in ml and k not in bl:
            c["spurious"] += int(should is False)
            continue
        gb = grade_loc(name, sym, *bl[k])
        gm = grade_loc(name, sym, *ml[k])
        c["overconfident"] += int(gm == "WRONG" and gb != "WRONG")
        c["underconfident"] += int(gb == "CERTAIN" and gm != "CERTAIN")
    dom = GT.attribution_domain(name, records)
    if dom not in (None, GT.UNSPECIFIED):
        bw = base[1] == UNIQUE and base[2][0].split("/", 1)[0] != dom
        mw = mut[1] == UNIQUE and mut[2][0].split("/", 1)[0] != dom
        bc = base[1] == UNIQUE and not bw
        mc = mut[1] == UNIQUE and not mw
        c["overconfident"] += int(mw and not bw)
        c["underconfident"] += int(bc and not mc)
    return c


def main():
    runs = {n: P.run_scenario(SCENARIOS[n]) for n in sorted(SCENARIOS)}
    aircraft = [n for n, (e, _r) in runs.items()
                if "state_estimator" in {r.component for r in _r[0].records}]
    out = {"harness": "semantic_core_2_1_adversarial_profiles",
           "scenarios": aircraft, "ticks": sum(len(runs[n][1]) for n in aircraft),
           "mutations": {}}
    base_cache = {}
    for n in aircraft:
        engine, res = runs[n]
        core = SemanticCore21.from_engine(engine, trace=False)
        base_cache[n] = [(run_v20(engine, sa.records), run_v21(core, sa.records)) for sa in res]
    first = runs["NOMINAL"][1][0].records
    engine0 = runs["NOMINAL"][0]
    out["validator_on_unmutated_aircraft_profile"] = [
        f.to_dict() for f in validate_profile(first, engine0.functions)]
    for mid, (what, fn) in MUTATIONS.items():
        row = {"what": what}
        for who in ("v2_0", "v2_1"):
            row[who] = {"crashed_ticks": 0, "ticks_changed": 0, "overconfident": 0,
                        "underconfident": 0, "spurious": 0, "crash_example": None}
        for n in aircraft:
            engine, res = runs[n]
            core = SemanticCore21.from_engine(engine, trace=False)
            for t, sa in enumerate(res):
                recs = fn(sa.records)
                b20, b21 = base_cache[n][t]
                for who, runner, base in (("v2_0", lambda r: run_v20(engine, r), b20),
                                          ("v2_1", lambda r: run_v21(core, r), b21)):
                    try:
                        m = runner(recs)
                    except Exception as exc:  # noqa: BLE001 -- measuring it
                        row[who]["crashed_ticks"] += 1
                        row[who]["crash_example"] = row[who]["crash_example"] or \
                            f"{n}@{t}: {type(exc).__name__}: {exc}"[:200]
                        continue
                    c = compare(n, sa.records, base, m)
                    row[who]["ticks_changed"] += c["changed"]
                    for k in ("overconfident", "underconfident", "spurious"):
                        row[who][k] += c[k]
        base_findings = {(f.rule, f.subject) for f in validate_profile(first, engine0.functions)}
        mut_findings = [f for f in validate_profile(fn(first), engine0.functions)
                        if (f.rule, f.subject) not in base_findings]
        row["validator_new_findings"] = [f.to_dict() for f in mut_findings]
        row["detected_by_validator"] = bool(mut_findings)
        out["mutations"][mid] = row
        print(mid, {w: {k: row[w][k] for k in ("crashed_ticks", "ticks_changed", "overconfident",
                                               "underconfident", "spurious")}
                    for w in ("v2_0", "v2_1")}, "detected:", row["detected_by_validator"],
              [f.rule for f in mut_findings])
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    main()
