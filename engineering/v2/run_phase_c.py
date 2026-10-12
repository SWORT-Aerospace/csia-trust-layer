"""CSIA v2 PHASE C — the full run behind the report.

    python engineering/v2/run_phase_c.py

Produces, in `engineering/v2/`:

    CROSS_DOMAIN_SIGNATURE_MATRIX.csv     §4, generated from the live table
    LOCALIZATION_RESULTS.csv              §§7-10 over every matched scenario
    EVIDENCE_SUBSET_RESULTS.csv           §6 minimum resolving evidence
    LOCALIZATION_LEDGER.json              §31
    INTERNAL_EXTERNAL_EQUIVALENCE.json    §18, all 13,500 real ticks
    V2_PHASEC_COMPUTE.json                §§19, 43
    PLUGIN_FAILURE_RESULTS.csv            §§21, 22, 37-E
    FUNCTION_REQUIREMENTS_V2.yaml         §28, generated from the profiles
    DOMAIN_EVIDENCE_CONTRACTS/*.md        §3, generated

NO NUMBER HERE IS INVENTED. Where a measurement could not be made the
artifact says so with a null and a reason.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, ".."))
for p in (ROOT, os.path.join(ENG, "v1_1", "phase4"),
          os.path.join(ENG, "v1_1", "ablation"),
          os.path.join(ENG, "v1_1", "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.v2 import scenarios as SC                              # noqa: E402
from csia.v2 import signatures as SIG                            # noqa: E402
from csia.v2.domain import Snapshot                              # noqa: E402
from csia.v2.explanation import explain_all                      # noqa: E402
from csia.v2.ingest import NavigationDomainInput                 # noqa: E402
from csia.v2.ledger import (V2AssuranceLedger,                   # noqa: E402
                            V2LedgerContext, plugin_manifest_hash)
from csia.v2.localization import (AMBIGUOUS, EvidenceIndex,      # noqa: E402
                                  SUPPORTED, UNSUPPORTED,
                                  localize_all,
                                  minimum_resolving_subsets)
from csia.v2.plugin_runtime import FailingDomain                 # noqa: E402
from csia.v2.profiles import SCENARIOS, build_engine_for         # noqa: E402
from csia.v2.profiles.aircraft_scenarios import (                # noqa: E402
    example_payload_feed, load_v1_1_example)
from csia.v2.profiles.matched_scenarios import (                 # noqa: E402
    MATCHED_BY_NAME, MATCHED_SETS, SET_SYMPTOM)

TICKS = 60


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _write_json(name, obj):
    path = os.path.join(_HERE, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def _write_csv(name, rows, fields=None):
    path = os.path.join(_HERE, name)
    fields = fields or list(rows[0])
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path


def _feed(sc):
    return (example_payload_feed(sc.v1_1_variant)
            if sc.system == "aircraft" else None)


def _run(sc, ticks=TICKS):
    engine = build_engine_for(sc)
    return engine, SC.run(engine, sc, ticks=ticks, payload_for=_feed(sc))


# =========================================================== §§7-10 results
def localization_results():
    rows, ledger_blocks = [], {}
    for set_name, members in MATCHED_SETS.items():
        want = SET_SYMPTOM[set_name]
        for name in members:
            sc = MATCHED_BY_NAME[name]
            engine, results = _run(sc)
            final = results[-1]
            hits = [x for x in final.localizations if x.symptom == want]
            led = V2AssuranceLedger(V2LedgerContext(
                profile=sc.system, software_sha=_git("rev-parse", "HEAD"),
                configuration_hash="phase_c",
                plugin_manifest_hash=plugin_manifest_hash(engine)))
            for a in results:
                led.observe(a)
            ok, problems = led.verify_chain()
            ledger_blocks[name] = {
                "events": [e.to_dict() for e in led.events
                           if e.event_type == "LOCALIZATION_CHANGED"],
                "chain_ok": ok, "problems": list(problems)}
            if not hits:
                rows.append({
                    "set": set_name, "scenario": name, "symptom": want,
                    "subject": "", "detected": False,
                    "verdict": "SYMPTOM_NOT_DETECTED",
                    "initial_domains": "", "initial_candidates": 0,
                    "supported": "", "unresolved": "", "rejected": "",
                    "candidate_domains_after": 0,
                    "evidence": "", "unmeasurable": "",
                    "dependency_model_blind_to": "",
                    "expectation": sc.expectation})
                continue
            # §13's coverage gap, reported beside the verdict rather than
            # folded into it: the domains in which this platform's dependency
            # model cannot see a shared node even if one exists.
            blind = "|".join(SIG.uncovered_common_cause_domains(
                EvidenceIndex(final.records)))
            for loc in hits:
                rows.append({
                    "set": set_name, "scenario": name, "symptom": want,
                    "subject": loc.subject,
                    "detected": True, "verdict": loc.verdict,
                    "initial_domains": "|".join(loc.initial_domains),
                    "initial_candidates": len(loc.initial_candidates),
                    "supported": "|".join(loc.supported),
                    "unresolved": "|".join(loc.unresolved),
                    "rejected": "|".join(f"{h}<-{p}"
                                         for h, p in loc.rejected),
                    "candidate_domains_after": loc.candidate_domain_count,
                    "evidence": "|".join(loc.evidence),
                    "unmeasurable": "|".join(loc.unmeasurable),
                    "dependency_model_blind_to": blind,
                    "expectation": sc.expectation})
    return rows, ledger_blocks


# ================================================================ §6 subsets
def evidence_subsets():
    rows = []
    for set_name, members in MATCHED_SETS.items():
        want = SET_SYMPTOM[set_name]
        spec = SIG.SYMPTOMS_BY_ID[want]
        for name in members:
            sc = MATCHED_BY_NAME[name]
            _engine, results = _run(sc)
            index = EvidenceIndex(results[-1].records)
            for subject in spec.detect(index):
                got = minimum_resolving_subsets(spec, index, subject,
                                                SIG.PREDICATES)
                rows.append({
                    "set": set_name, "scenario": name, "symptom": want,
                    "subject": subject, "verdict": got["verdict"],
                    "candidates_initial": got["candidates_initial"],
                    "measurable_predicates":
                        len(got["measurable_predicates"]),
                    "minimum_size": got["minimum_size"],
                    "minimum_subset": "|".join(got["minimum_subset"] or ()),
                    "equivalent_minimum_subsets":
                        len(got["equivalent_minimum_subsets"]),
                    "uniquely_resolved": got["uniquely_resolved"],
                    "unresolved_domains":
                        "|".join(got["unresolved_domains"]),
                    "note": got["note"]})
    return rows


# ============================================================ §18 equivalence
def internal_external_equivalence():
    """All 13,500 real v1.1 ticks through BOTH interfaces."""
    try:
        from run_p4b import _series
        from run_p4c import _config_hash
        from run_p4d import _payloads
        from run_phase3b import MECHANISMS, _hashes
        import run_p4d
        import support as S
    except Exception as exc:                        # pragma: no cover
        return {"artifact": "INTERNAL_EXTERNAL_EQUIVALENCE",
                "checked": 0, "identical": None,
                "unavailable_reason": f"{type(exc).__name__}: {exc}",
                "note": "NO CLAIM IS MADE FROM THIS RUN."}

    from csia.v2.profiles import build_v1_1_baseline_engine
    prov = {"software_sha": _git("rev-parse", "HEAD"),
            "configuration_hash": _config_hash(), "input_trace_hash": ""}

    checked = mismatch = 0
    per_mech = {}
    ext_engine = build_v1_1_baseline_engine()
    int_engine = build_v1_1_baseline_engine()
    for mech, spec in MECHANISMS.items():
        if spec["status"] != "APPLICABLE":
            continue
        cached = _series(mech)
        td = cached[0]
        dec, _sup = S.support_series(td, stride=1)
        run_p4d._DEC[id(td)] = dec
        payloads = _payloads(mech, cached,
                             dict(prov,
                                  input_trace_hash=_hashes(td)
                                  ["raw_trace_sha256"]))
        bad = 0
        for p in payloads:
            a = ext_engine.evaluate(Snapshot(t=p["timestamp"], signals={},
                                             v1_1_payload=p))
            typed = NavigationDomainInput.from_trusted_payload(p)
            b = int_engine.evaluate(Snapshot(t=p["timestamp"], signals={},
                                             v1_1_input=typed))
            if a.to_dict() != b.to_dict():
                bad += 1
            checked += 1
        per_mech[mech] = {"payloads": len(payloads), "mismatches": bad}
        mismatch += bad
        print(f"  {mech:20s} {len(payloads):5d} ticks  mismatches={bad}",
              flush=True)

    return {
        "artifact": "INTERNAL_EXTERNAL_EQUIVALENCE",
        "generation_command": "python engineering/v2/run_phase_c.py",
        "section": "18",
        "checked": checked, "mismatches": mismatch,
        "identical": mismatch == 0,
        "per_mechanism": per_mech,
        "compared": "the FULL SystemAssurance document per tick -- domain "
                    "evidence, function results, cross-domain attribution, "
                    "localization and plugin status",
        "note": "zero tolerance for discrete outputs. The two interfaces "
                "converge on one typed input before any evidence exists, so "
                "equality here is structural rather than coincidental.",
    }


# ============================================================== §§19, 43
def compute():
    p = load_v1_1_example("clean")

    def t(fn, n=200):
        fn()
        t0 = time.perf_counter()
        for _ in range(n):
            fn()
        return (time.perf_counter() - t0) / n * 1e6

    import jsonschema
    from csia.v1_1 import output_api as API
    from csia.v1_1.monitor import parse
    sch = API.schema()

    ingest = {
        "phase_b_uncached_jsonschema_validate_us":
            round(t(lambda: jsonschema.validate(p, sch), 20), 1),
        "cached_validator_validate_us": round(t(lambda: API.validate(p)), 1),
        "external_full_parse_us": round(t(lambda: parse(p)), 1),
        "external_typed_ingest_us": round(
            t(lambda: NavigationDomainInput.from_external_payload(p)), 1),
        "internal_typed_ingest_us": round(
            t(lambda: NavigationDomainInput.from_trusted_payload(p)), 1),
    }

    sc = SCENARIOS["REGULATOR_FAILURE"]
    engine = build_engine_for(sc)
    typed = NavigationDomainInput.from_trusted_payload(p)
    snaps = [Snapshot(t=s.t, signals=s.signals,
                      v1_1_input=typed.with_timestamp(s.t))
             for s in SC.SnapshotSource(sc, ticks=TICKS)]
    led = V2AssuranceLedger(V2LedgerContext(
        profile="aircraft", software_sha="x", configuration_hash="y",
        plugin_manifest_hash=plugin_manifest_hash(engine)))

    phases = {k: [] for k in ("domains_total", "localization", "functions",
                              "attribution", "ledger", "explanation")}
    from csia.v2 import api as API2
    for snap in snaps:
        t0 = time.perf_counter()
        a = engine.evaluate(snap)
        t1 = time.perf_counter()
        led.observe(a)
        t2 = time.perf_counter()
        explain_all(a, engine.functions)
        t3 = time.perf_counter()
        phases["domains_total"].append((t1 - t0) * 1e6)
        phases["ledger"].append((t2 - t1) * 1e6)
        phases["explanation"].append((t3 - t2) * 1e6)

    # localization alone, over the same records
    recs = engine.evaluate(snaps[-1]).records
    loc_us = t(lambda: localize_all(SIG.SYMPTOMS, recs, SIG.PREDICATES), 100)
    api_us = t(lambda: API2.build(engine.evaluate(snaps[-1]),
                                  profile="aircraft", provenance={}), 20)

    stats = {k: {"median_us": round(statistics.median(v), 3),
                 "max_us": round(max(v), 3)}
             for k, v in phases.items() if v}
    stats["localization_alone"] = {"median_us": round(loc_us, 3),
                                   "max_us": None}
    stats["api_build_and_evaluate"] = {"median_us": round(api_us, 3),
                                       "max_us": None}
    before = ingest["phase_b_uncached_jsonschema_validate_us"]
    after = ingest["internal_typed_ingest_us"]
    return {
        "artifact": "V2_PHASEC_COMPUTE",
        "generation_command": "python engineering/v2/run_phase_c.py",
        "measured_on": f"REGULATOR_FAILURE, {TICKS} ticks, six domains, "
                       f"CPython on a general-purpose host",
        "ingest_us_per_tick": ingest,
        "hot_path_before_us": before,
        "hot_path_after_us": after,
        "hot_path_reduction_factor": round(before / after, 1),
        "phases_us_per_tick": stats,
        "records_per_tick": len(recs),
        "symptoms_evaluated_per_tick": len(SIG.SYMPTOMS),
        "note":
            "TWO INDEPENDENT IMPROVEMENTS, reported separately because they "
            "are different claims. (1) jsonschema.validate re-compiles the "
            "schema on every call; a validator built once does the SAME full "
            "validation for ~1/37th the cost, and validation is not weakened "
            "at all. (2) the internal typed path removes the schema walk "
            "entirely, and is legitimate ONLY between in-process, "
            "version-locked components (§20). NO TARGET-HARDWARE FIGURE "
            "EXISTS AND NONE IS CLAIMED.",
    }


# ======================================================== §§21, 22, 37-E
def plugin_failures():
    rows = []
    for mode in ("raise", "silent"):
        for target in ("POWER", "COMPUTE", "TIMING", "COMMUNICATION",
                       "ACTUATION", "SENSOR"):
            sc = SCENARIOS["NOMINAL"]
            engine = build_engine_for(sc)
            if target not in engine.registry:
                continue
            broken = FailingDomain(engine.registry.get(target), mode=mode,
                                   after_tick=2)
            engine.registry._by_id[target] = broken
            engine.supervisor.statuses[target].state = "AVAILABLE"
            results = SC.run(engine, sc, ticks=8,
                             payload_for=_feed(sc))
            final = results[-1]
            st = final.plugins[target]
            degraded = sorted(n for n, v in final.functions.items()
                              if v.state != "ELIGIBLE")
            healthy_claim = any(
                v.state == "ELIGIBLE" and target in v.domain_states
                and v.domain_states[target] in ("NOMINAL",)
                for v in final.functions.values())
            rows.append({
                "injected": mode, "domain": target,
                "plugin_state": st["state"],
                "consecutive_errors": st["consecutive_errors"],
                "system": final.system,
                "functions_degraded": len(degraded),
                "functions_total": len(final.functions),
                "degraded_functions": "|".join(degraded),
                "claimed_healthy_from_failed_domain": healthy_claim,
                "other_domains_still_reporting": sum(
                    1 for k, v in final.plugins.items()
                    if k != target and v["state"] == "AVAILABLE"),
                "last_error": st["last_error"][:80],
            })
    return rows


# ================================================================ §28 YAML
def function_requirements_yaml():
    import yaml
    from csia.v2.profiles.aircraft import AIRCRAFT_FUNCTIONS
    from csia.v2.profiles.pump_skid import PUMP_SKID_FUNCTIONS
    from csia.v2.profiles.test_stand import TEST_STAND_FUNCTIONS

    def block(fns):
        out = {}
        for f in fns:
            out[f.name] = {
                "summary": f.summary,
                "required_domains": list(f.required_domains),
                "supporting_domains": list(f.supporting_domains),
                "no_degradation_domains": list(f.no_degradation_domains),
                "redundant_groups": [list(g) for g in f.redundant_groups],
                "fallback_requirements": {n: list(d) for n, d
                                          in f.fallback_requirements},
                "optional_domains": list(f.optional_domains),
                "fallback": f.fallback,
                "acceptable_degradation": f.acceptable_degradation,
            }
        return out

    doc = {
        "version": "2.0.0",
        "note": ("GENERATED from the profile tables by "
                 "engineering/v2/run_phase_c.py. The profiles are the source "
                 "of truth; this file exists so the requirements are "
                 "reviewable as data (§28). Thresholds live in the profile "
                 "and NEVER in framework source."),
        "profiles": {
            "aircraft": block(AIRCRAFT_FUNCTIONS),
            "test_stand": block(TEST_STAND_FUNCTIONS),
            "pump_skid": block(PUMP_SKID_FUNCTIONS),
        },
    }
    path = os.path.join(_HERE, "FUNCTION_REQUIREMENTS_V2.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=True, default_flow_style=False,
                       width=78)
    return path


# ================================================================= §3 docs
def domain_evidence_contracts():
    out_dir = os.path.join(_HERE, "DOMAIN_EVIDENCE_CONTRACTS")
    os.makedirs(out_dir, exist_ok=True)
    by_domain: dict = {}
    for spec in SIG.SYMPTOMS:
        for h in spec.hypotheses:
            by_domain.setdefault(h.domain, []).append((spec, h))
    paths = []
    for domain in SIG.DOMAINS:
        entries = by_domain.get(domain, [])
        lines = [f"# {domain} — EVIDENCE CONTRACT (Phase C §3)", "",
                 "Generated by `engineering/v2/run_phase_c.py` from the live "
                 "signature table, so it cannot drift from the code.", "",
                 "For each symptom this domain can explain: the mechanism, "
                 "the alternative explanations, and the evidence that "
                 "distinguishes them.", ""]
        if not entries:
            lines += ["This domain explains no declared symptom in the "
                      "current model.", ""]
        for spec, h in entries:
            others = [x.hypothesis_id for x in spec.hypotheses
                      if x is not h]
            lines += [
                f"## {spec.symptom_id} — `{h.hypothesis_id}`", "",
                f"**Observable symptom.** {spec.description}", "",
                f"**Mechanism.** {h.mechanism}", "",
                "**Alternative explanations (other domains that can produce "
                "the same symptom).**", "",
            ]
            lines += [f"- `{o}`" for o in others] or ["- none"]
            lines += ["", "**Required distinguishing evidence.**", "",
                      "| direction | predicate | reads |", "|---|---|---|"]
            for pid in h.confirmed_by:
                pr = SIG.PREDICATES[pid]
                lines.append(f"| confirms | `{pid}` | {pr.evidence_domain} |")
            for pid in h.refuted_by:
                pr = SIG.PREDICATES[pid]
                lines.append(f"| refutes | `{pid}` | {pr.evidence_domain} |")
            if h.confirm_requires_all:
                lines += ["", "Confirmation requires **all** of the "
                              "confirming predicates, not any."]
            if h.note:
                lines += ["", f"**Note.** {h.note}"]
            lines.append("")
        path = os.path.join(out_dir, f"{domain}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        paths.append(path)
    return paths


# =============================================================== §42 gate
def decision_gate(loc_rows):
    """CROSS_DOMAIN_ASSURANCE_FUNCTIONAL requires at least TWO matched sets
    where several domains could explain the symptom initially AND additional
    cross-domain evidence correctly reduces the set, with no ground truth."""
    qualifying, rejected = [], []
    for set_name in MATCHED_SETS:
        rows = [r for r in loc_rows if r["set"] == set_name and r["detected"]]
        if not rows:
            rejected.append({"set": set_name, "why": "symptom not detected"})
            continue
        # One scenario can exhibit the symptom on several subjects. Those are
        # the same experiment, so the gate counts SCENARIOS, not rows -- and
        # a scenario whose subjects disagree is not counted as reduced.
        by_scenario: dict = {}
        for r in rows:
            by_scenario.setdefault(r["scenario"], []).append(r)
        members = sorted(by_scenario)
        multi = all(len(r["initial_domains"].split("|")) > 1 for r in rows)
        answers = {}
        for name, group in by_scenario.items():
            verdicts = {r["verdict"] for r in group}
            supported = {r["supported"] for r in group}
            if verdicts == {SUPPORTED} and len(supported) == 1:
                answers[name] = supported.pop()
        distinct = set(answers.values())
        # STRICT READING of §42: evidence must reduce EACH member to a
        # DIFFERENT supported hypothesis. Injective, not merely "more than
        # one distinct answer" -- a set where two members land on the same
        # hypothesis has not discriminated between those two, and counting
        # it would let a set pass on the strength of its other members.
        record = {"set": set_name, "members": len(members),
                  "reduced": len(answers), "distinct_answers": len(distinct),
                  "answers": {k: answers[k] for k in sorted(answers)}}
        if multi and len(answers) == len(members) == len(distinct):
            qualifying.append(record)
        else:
            record["why"] = (
                "not every member reduced to a supported hypothesis"
                if len(answers) < len(members) else
                "two members reduced to the SAME hypothesis, so those two "
                "were not discriminated"
                if len(distinct) < len(answers) else
                "the symptom did not start with multiple candidate domains")
            rejected.append(record)
    verdict = ("CROSS_DOMAIN_ASSURANCE_FUNCTIONAL" if len(qualifying) >= 2
               else "CROSS_DOMAIN_ASSURANCE_PARTIALLY_EFFECTIVE"
               if qualifying else "DOMAIN_MONITORS_ONLY")
    return {"verdict": verdict, "qualifying_sets": qualifying,
            "non_qualifying_sets": rejected,
            "criterion": "at least two matched sets where multiple domains "
                         "could explain the symptom initially and evidence "
                         "reduced each member to a DIFFERENT supported "
                         "hypothesis, with no ground-truth access. 'Each' is "
                         "read strictly: the member -> hypothesis map must be "
                         "injective over the whole set."}


# ==================================================================== main
def main() -> int:
    paths = [SIG.write_matrix_csv(
        os.path.join(_HERE, "CROSS_DOMAIN_SIGNATURE_MATRIX.csv"))]

    print("localization over the matched sets...", flush=True)
    loc_rows, ledger_blocks = localization_results()
    paths.append(_write_csv("LOCALIZATION_RESULTS.csv", loc_rows))
    paths.append(_write_json("LOCALIZATION_LEDGER.json", {
        "artifact": "LOCALIZATION_LEDGER", "section": "31",
        "note": "one LOCALIZATION_CHANGED event per decision that changed: "
                "symptom, candidates before, evidence applied, candidates "
                "after, unresolved alternatives, affected functions. "
                "Deterministic and hashable.",
        "scenarios": ledger_blocks}))

    print("minimum resolving evidence...", flush=True)
    paths.append(_write_csv("EVIDENCE_SUBSET_RESULTS.csv",
                            evidence_subsets()))

    print("plugin failure injection...", flush=True)
    paths.append(_write_csv("PLUGIN_FAILURE_RESULTS.csv", plugin_failures()))

    print("compute...", flush=True)
    paths.append(_write_json("V2_PHASEC_COMPUTE.json", compute()))

    paths.append(function_requirements_yaml())
    paths.extend(domain_evidence_contracts())

    print("internal vs external over every real payload...", flush=True)
    equiv = internal_external_equivalence()
    paths.append(_write_json("INTERNAL_EXTERNAL_EQUIVALENCE.json", equiv))

    gate = decision_gate(loc_rows)
    paths.append(_write_json("V2_PHASEC_GATE.json", gate))

    print("=" * 66)
    print("CSIA v2 PHASE C")
    print("=" * 66)
    for set_name in MATCHED_SETS:
        print(f"\n{set_name}")
        for r in loc_rows:
            if r["set"] != set_name:
                continue
            print(f"  {r['scenario']:28s} {r['verdict']:12s} "
                  f"{r['initial_candidates']}->"
                  f"{r['candidate_domains_after']} domains  "
                  f"{r['supported'] or r['unresolved']}")
    print(f"\nGATE: {gate['verdict']}  "
          f"({len(gate['qualifying_sets'])} qualifying sets)")
    print(f"equivalence: {equiv['checked']} ticks, "
          f"identical={equiv.get('identical')}")
    print("\nartifacts:")
    for p in paths:
        print(f"  {os.path.relpath(p, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
