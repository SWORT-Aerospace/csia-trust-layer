#!/usr/bin/env python3
"""Phase 11: profile validation under 2.1.1. RESEARCH ONLY.

    .venv/bin/python research/csia_semantic_core_2_1_revision/profile_validation.py

1. The static validator (PV1-PV9) on the three shipped profiles, with and
   without the successor profiles, and with r2's pacing declarations.
2. The shadow study's ten profile mutations (`adversarial_profiles.MUTATIONS`,
   imported, unchanged), re-run over the aircraft scenarios through frozen
   v2.0, 2.1.0 + successor r1 and 2.1.1 + successor r2, with the shadow
   study's own grading (`adversarial_profiles.compare`).
3. Pacing-declaration mutations, new with R-2: what a wrong pacing
   declaration does, and whether PV9 or the loader catches it. Each is run
   over the aircraft scenarios and over the IMU pacing-loss counterfactual
   (W7), where the right answer keeps input starvation open.

The division of labour this checks: the profile says which existing edge
paces an output (architecture); the predicate says what starvation means.

Writes PROFILE_VALIDATION_RESULTS.json.
"""
from __future__ import annotations

import sys
from dataclasses import replace

import revision_common as RC

import adversarial_profiles as AP  # noqa: E402
import semantic_probe as P  # noqa: E402
import shadow_validation as S  # noqa: E402

from csia.v2.evidence import ObservationState as OS  # noqa: E402
from csia.v2.localization import SUPPORTED  # noqa: E402
from csia.v2.profiles import SCENARIOS  # noqa: E402
from csia_semantic_core import Corrections, SemanticCore21  # noqa: E402
from csia_semantic_core.profile_overlay import (ProfileOverlay,  # noqa: E402
                                                load_successor)
from csia_semantic_core.profile_validator import ERROR, validate_profile  # noqa: E402

OUT = RC.HERE / "PROFILE_VALIDATION_RESULTS.json"
REVISED = Corrections.revised()


def findings(records, functions, pacing=None):
    return [f.to_dict() for f in validate_profile(records, functions, pacing=pacing)]


def w7(engine, res, pacing, ov):
    recs = tuple(replace(r, observation_state=OS.VIOLATED, reason_codes=("SOURCE_STALE",))
                 if r.component == "source.imu0" else r for r in res[-1].records)
    recs = ov.apply(recs) if ov else recs
    core = SemanticCore21.from_engine(engine, REVISED, trace=False, pacing=pacing)
    x = [x for x in core.reason(recs).localizations
         if x.symptom == "OUTPUT_MISSING" and x.subject == "state_estimator"][0]
    wrong = x.v2.verdict == SUPPORTED and x.supported == ("COMPUTE/process_stall",)
    return {"verdict": x.v2.verdict, "supported": list(x.supported),
            "unresolved": list(x.unresolved), "wrong_process_stall_supported": wrong}


def main():
    r1 = load_successor("aircraft_successor_r1")
    r2 = load_successor("aircraft_successor_r2")
    runs = {n: P.run_scenario(SCENARIOS[n]) for n in sorted(SCENARIOS)}
    out = {"harness": "semantic_core_2_1_revision_profile_validation",
           "successor_r2_digest": r2.digest()}
    # 1. validator on shipped profiles
    val = {}
    for name in ("NOMINAL", "TS_NOMINAL", "PS_NOMINAL"):
        engine, res = runs[name]
        recs = res[0].records
        val[name] = {"frozen": findings(recs, engine.functions)}
        if name == "NOMINAL":
            val[name]["successor_r1"] = findings(r1.apply(recs), engine.functions)
            val[name]["successor_r2"] = findings(r2.apply(recs), engine.functions,
                                                 r2.pacing_map())
        val[name]["errors"] = {k: [f for f in v if f["severity"] == ERROR]
                               for k, v in val[name].items()}
    out["validator_on_shipped_profiles"] = val
    # 2. the shadow study's mutations
    aircraft = [n for n, (e, _r) in runs.items()
                if "state_estimator" in {r.component for r in _r[0].records}]
    cfgs = {"v2_0": None, "2_1_0_r1": (Corrections(), r1), "2_1_1_r2": (REVISED, r2)}
    base = {}
    for n in aircraft:
        engine, res = runs[n]
        cores = {k: SemanticCore21.from_engine(engine, c, trace=False,
                                               pacing=ov.pacing_map() if c.is_revised else None)
                 for k, (c, ov) in ((k, v) for k, v in cfgs.items() if v)}
        rows = []
        for sa in res:
            row = {"v2_0": AP.run_v20(engine, sa.records)}
            for k, (c, ov) in ((k, v) for k, v in cfgs.items() if v):
                row[k] = AP.run_v21(cores[k], ov.apply(sa.records))
            rows.append(row)
        base[n] = (cores, rows)
    first = runs["NOMINAL"][1][0].records
    engine0 = runs["NOMINAL"][0]
    muts = {}
    for mid, (what, fn) in AP.MUTATIONS.items():
        row = {"what": what}
        for who in cfgs:
            row[who] = {"crashed_ticks": 0, "ticks_changed": 0, "overconfident": 0,
                        "underconfident": 0, "spurious": 0}
        for n in aircraft:
            engine, res = runs[n]
            cores, rows = base[n]
            for t, sa in enumerate(res):
                for who, v in cfgs.items():
                    try:
                        if v is None:
                            m = AP.run_v20(engine, fn(sa.records))
                        else:
                            m = AP.run_v21(cores[who], fn(v[1].apply(sa.records)))
                    except Exception:  # noqa: BLE001 -- measuring it
                        row[who]["crashed_ticks"] += 1
                        continue
                    c = AP.compare(n, sa.records, rows[t][who], m)
                    row[who]["ticks_changed"] += c["changed"]
                    for k in ("overconfident", "underconfident", "spurious"):
                        row[who][k] += c[k]
        b = {(f["rule"], f["subject"]) for f in findings(r2.apply(first), engine0.functions,
                                                         r2.pacing_map())}
        new = [f for f in findings(fn(r2.apply(first)), engine0.functions, r2.pacing_map())
               if (f["rule"], f["subject"]) not in b]
        row["validator_new_findings_on_r2"] = new
        row["detected_by_validator"] = bool(new)
        muts[mid] = row
        print(mid, {w: {k: row[w][k] for k in ("overconfident", "underconfident", "spurious",
                                               "crashed_ticks")} for w in cfgs},
              "detected", row["detected_by_validator"])
    out["shadow_mutations"] = muts
    # 3. pacing-declaration mutations
    gnss_edge = ProfileOverlay(r2.name, "r2+R5b", r2.base_profile,
                               r2.declarations + S.overlay("R5b").declarations)
    pmuts = {
        "PM0_CORRECT_r2": ("the accepted declaration", r2.pacing_map(), r2),
        "PM1_GNSS_AS_PACING_NO_EDGE": (
            "the GNSS link declared to pace the estimator, without a dependency on it",
            {"state_estimator": ("ALL", ("COMMUNICATION/gnss_serial",))}, r2),
        "PM2_GNSS_AS_PACING_WITH_EDGE": (
            "the GNSS link declared a dependency (R5b) AND to pace the estimator",
            {"state_estimator": ("ALL", ("COMMUNICATION/gnss_serial",))}, gnss_edge),
        "PM3_CPU_ALSO_PACING": (
            "the CPU (a real dependency) also declared to pace the estimator",
            {"state_estimator": ("ALL", ("SENSOR/source.imu0", "COMPUTE/cpu"))}, r2),
        "PM4_NO_PACING_DECLARATION": (
            "no pacing declaration (successor r1 under 2.1.1)", {}, r1),
        "PM5_PACING_ON_MISSPELLED_COMPONENT": (
            "pacing declared on 'state_estimatr'",
            {"state_estimatr": ("ALL", ("SENSOR/source.imu0",))}, r2),
        "PM6_ANY_INSTEAD_OF_ALL_SINGLE_INPUT": (
            "mode ANY with the one input (equivalent to ALL)",
            {"state_estimator": ("ANY", ("SENSOR/source.imu0",))}, r2),
    }
    pres = {}
    for pid, (what, pacing, ov) in pmuts.items():
        row = {"what": what, "pacing": {k: [m, list(v)] for k, (m, v) in pacing.items()}}
        b = {(f["rule"], f["subject"]) for f in findings(r2.apply(first), engine0.functions,
                                                         r2.pacing_map())}
        new = [f for f in findings(ov.apply(first), engine0.functions, pacing)
               if (f["rule"], f["subject"]) not in b]
        row["validator_new_findings"] = new
        row["validator_errors"] = [f for f in new if f["severity"] == ERROR]
        row["W7_imu_pacing_loss"] = w7(*runs["PROCESS_STALL"], pacing, ov)
        stats = {"overconfident": 0, "underconfident": 0, "spurious": 0, "ticks_changed": 0}
        for n in aircraft:
            engine, res = runs[n]
            core = SemanticCore21.from_engine(engine, REVISED, trace=False, pacing=pacing)
            cores, rows = base[n]
            for t, sa in enumerate(res):
                m = AP.run_v21(core, ov.apply(sa.records))
                c = AP.compare(n, sa.records, rows[t]["2_1_1_r2"], m)
                stats["ticks_changed"] += c["changed"]
                for k in ("overconfident", "underconfident", "spurious"):
                    stats[k] += c[k]
        row["aircraft_scenarios_vs_r2"] = stats
        pres[pid] = row
        print(pid, stats, "W7 wrong:", row["W7_imu_pacing_loss"]["wrong_process_stall_supported"],
              "validator errors:", [f["rule"] for f in row["validator_errors"]])
    for bad in ({"state_estimator": ("SOME", ("SENSOR/source.imu0",))},
                {"state_estimator": ("ALL", ())}):
        try:
            SemanticCore21.from_engine(engine0, REVISED, pacing=bad)
            pres.setdefault("PM7_MALFORMED_REFUSED", []).append({"pacing": str(bad), "refused": False})
        except ValueError as exc:
            pres.setdefault("PM7_MALFORMED_REFUSED", []).append(
                {"pacing": str(bad), "refused": True, "error": str(exc)})
    out["pacing_mutations"] = pres
    out["aircraft_scenarios"] = aircraft
    RC.write_json(OUT, out)


if __name__ == "__main__":
    sys.exit(main())
