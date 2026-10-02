"""The report of a 2.3 stock analysis (schema 4). OFFBOARD ONLY.

Schema 4 is schema 3 plus five sections, built only for stock runs
(`runs.stock_flight`), so every earlier report stays byte-identical:

| section | phase | content |
|---|---|---|
| `summary` | 21 | the engineer's questions, answered first, from the sections below |
| `events` | 12, 14 | the discovered events and their triggers |
| `evidence_values` | 22 | every stock output with its measured value, unit, threshold and window |
| `coverage_report` | 23 | profile records expected and observed, with what each unobserved one means; producers; topics |
| `diagnosability` | 24 | which explanations the available evidence could ever eliminate, and what is missing |

**The summary computes nothing new.** It reads the other sections and
2.1.1's result. It never upgrades a verdict, and it never states a cause
2.1.1 did not reach.
"""

from __future__ import annotations

SCHEMA_4 = "csia.flight_assurance_report/4"

#: What an unobserved profile record means for an engineer.
MEANING = {
    "actuation.command_path": "whether each motor's ESC received its command (no stock topic shows delivery; actuator_outputs is only what the FMU computed)",
    "actuation.electrical_response": "motor current per command (ESC current absent or zero)",
    "actuation.mechanical_response": "the stall check: current with no rotor speed (needs ESC current)",
    "actuation.physical_response": "each motor's physical effect, from the closed loop's compensation",
    "power.source_health": "battery voltage and current both present (v2: current must be measured)",
    "power.p_equals_vi": "power balance P = V I (needs an independent power measurement)",
    "power.droop_vs_current": "voltage sag under load (needs measured current)",
    "power.cell_balance": "cell balance (needs cell voltages)",
    "compute.process_alive": "process liveness (no stock topic)",
    "compute.process_producing": "process output (no stock topic)",
    "compute.deadline_met": "process deadlines (no stock topic)",
    "compute.stability": "process stability (no stock topic)",
    "compute.resource_headroom": "CPU headroom (cpuload exists, but nothing pairs it with a deadline; in SITL it measures the host)",
}


def _ev_short(eid):
    p = eid.split("|")
    return f"{p[2]} [{p[0]}]" if len(p) == 4 else eid


def _fmt(x, nd=4):
    return "n/a" if x is None else (f"{x:.{nd}g}" if isinstance(x, float) else str(x))


def coverage_report(pc, cov, extras, notices) -> dict:
    observed = set(pc.get("observed", []))
    rows = []
    for k in extras.get("profile_catalog", []):
        rel = k.split(":", 1)[1]
        rows.append({"record": k, "observed": k in observed,
                     "meaning": MEANING.get(rel, "")})
    producers = {}
    for c in cov:
        st = c["ticks_by_state"]
        p = producers.setdefault(c["producer_id"], {"outputs": 0, "states": {}})
        p["outputs"] += 1
        for s, n in st.items():
            p["states"][s] = p["states"].get(s, 0) + n
    topics = extras.get("topic_coverage", {})
    return {"profile_records_expected": len(rows), "profile_records_observed": len(observed),
            "records": rows, "producers": producers, "coverage_notices": notices,
            "topics_absent": sorted(t for t, v in topics.items() if not v.get("present")),
            "fields_without_information": {t: v["fields_without_information"]
                                           for t, v in sorted(topics.items())
                                           if v.get("present") and v.get("fields_without_information")}}


def _summary(m, extras) -> dict:
    f = m["final"] or {}
    locs = f.get("localizations", [])
    ev = extras.get("events", [])
    vals = {v["evidence_id"]: v for v in extras.get("evidence_values", [])}
    km = m["key_moments"]
    corr = (f.get("corroboration") or {}).get("overall", {})
    att = f.get("attribution") or {}
    dg = extras.get("diagnosability", {})
    floors = {(s["symptom"], s.get("subject")): s for s in dg.get("symptoms", []) if s.get("raisable")}
    adverse = (f.get("state") or {}).get("abnormal", {}).get("adverse_evidence", [])
    happened = []
    for e in ev:
        happened.append(f"{e['event_id']} at {e['t0']:.2f} s: {', '.join(e['trigger_kinds'])}"
                        + (f" on motor(s) {', '.join(str(x) for x in e['motors'])}" if e["motors"] else ""))
    if not ev:
        happened.append("no event was discovered")
    for loc in locs:
        happened.append(f"{loc['symptom']} on {loc['subject']}: {loc['outcome']}"
                        + (f" among {len(loc['candidates'])} explanations" if len(loc["candidates"]) > 1 else ""))
    final_keys = {loc["key"] for loc in locs}
    raised: dict = {}
    for c in km.get("candidate_changes", []):
        if c["what"] == "attribution" or c["what"] in final_keys:
            continue
        r = raised.setdefault(c["what"], {"raised": [], "withdrawn": []})
        (r["raised"] if c["to"] else r["withdrawn"]).append(c["t"])
    for key, r in sorted(raised.items()):
        if r["raised"]:
            happened.append(f"{key} was raised {len(r['raised'])} time(s) (first at {r['raised'][0]} s) "
                            "and withdrawn each time when its evidence left its validity window; "
                            "it is not in the final result")
    when = []
    for e in ev:
        when.append(f"{e['event_id']}: onset estimate {e['t0']:.3f} s, first alarm {e['first_alarm_t']:.3f} s"
                    + (f", change complete {e['cleared_t']:.3f} s" if e.get("cleared_t") else ""))
    fa = km.get("first_abnormal")
    if fa:
        when.append(f"first abnormal output: {fa['t']} s ({', '.join(fa['observed_by'])})")
    for c in km.get("candidate_changes", []):
        if c["what"] != "attribution":
            when.append(f"{c['t']} s: {c['what']} -> {c['to'][0] if c['to'] else 'none'}")
    observed = []
    for eid in sorted(set(adverse)):
        v = vals.get(eid)
        if v:
            observed.append(f"{_ev_short(eid)}: {v['state']} {_fmt(v['measured'])} {v['unit']}"
                            f" (threshold {_fmt(v['threshold'])}; window {v['window']})")
        else:
            observed.append(f"{_ev_short(eid)}: adverse")
    pc = m.get("profile_coverage") or {}
    not_obs = []
    if pc.get("enumerable"):
        not_obs.append(f"{len(pc['observed'])} of the profile's {pc['profile_records']} records observed")
    for n in (m.get("coverage_report") or {}).get("coverage_notices", []):
        not_obs.append(f"{n['source']}: {n['why']}")
    seen = set()
    for v in extras.get("evidence_values", []):
        key = (v["record"], tuple(v["reason_codes"]))
        if v["state"] == "UNAVAILABLE" and v["reason_codes"] and key not in seen:
            seen.add(key)
            not_obs.append(f"{v['record']}: {', '.join(v['reason_codes'])} (from {v['t']:.2f} s)")
    remaining = {loc["key"]: loc["candidates"] for loc in locs}
    eliminated = []
    for loc in locs:
        for e in loc["eliminated"]:
            evs = [x for x in loc["refuting_evidence"]]
            mags = "; ".join(f"{_ev_short(x)} = {_fmt(vals[x]['measured'])} {vals[x]['unit']}"
                             for x in evs if x in vals)
            eliminated.append(f"{loc['key']}: {e['hypothesis']} by {', '.join(e['all_refuters'])}"
                              + (f" ({mags})" if mags else ""))
    agreed = {}
    for eid in adverse:
        agreed.setdefault(eid.split("|", 1)[0], []).append(_ev_short(eid))
    resolve = []
    for loc in locs:
        fl = floors.get((loc["symptom"], loc["subject"]))
        if fl:
            for h in fl["hypotheses"]:
                if h["hypothesis"] in loc["candidates"] and h["missing_to_eliminate"]:
                    need = sorted({r for v in h["missing_to_eliminate"].values() for r in v})
                    resolve.append(f"{loc['key']}: {h['hypothesis']} could be eliminated with "
                                   f"{' or '.join(need)}")
        for d in loc.get("would_discriminate", []):
            resolve.append(f"{loc['key']}: {d['predicate']} would discriminate but could not be evaluated")
    attribution = {"verdict": att.get("verdict"), "candidates": att.get("candidates", []),
                   "why": att.get("why"),
                   "justified": att.get("verdict") == "UNIQUE"}
    return {"what_happened": happened, "when": when, "observed": observed,
            "not_observed": not_obs, "explanations_remaining": remaining,
            "eliminated": eliminated,
            "monitors_agreeing": agreed,
            "independence": {"adverse_outputs": corr.get("adverse_evidence"),
                             "lineage_groups": len(corr.get("lineage_groups", [])),
                             "independent_lines": corr.get("independent_lines"),
                             "group_links": corr.get("group_links", [])},
            "would_resolve": resolve, "attribution": attribution}


def machine_report_4(rs, tl, final, cov, inputs, gate, contracts, extras, km, pc) -> dict:
    from .report import ANALYZER_VERSION
    notices = sorted({(n["producer_id"], n["source"], n["why"])
                      for r in rs for n in (r.get("producers") or {}).get("coverage_gaps", [])})
    notices = [{"producer_id": p, "source": s, "why": w} for p, s, w in notices]
    m = {
        "schema": SCHEMA_4,
        "analyzer_version": ANALYZER_VERSION,
        "semantic_version": final["semantic_version"] if final else None,
        "inputs": inputs,
        "profile_gate": gate.to_dict(),
        "contracts": {pid: {"producer_version": c.producer_version,
                            "contract_version": c.contract_version,
                            "digest": c.digest()} for pid, c in sorted(contracts.items())},
        "ticks": len(rs),
        "intervals": len(tl),
        "key_moments": km,
        "coverage": cov,
        "profile_coverage": pc,
        "timeline": tl,
        "final": final,
        "events": extras.get("events", []),
        "evidence_values": extras.get("evidence_values", []),
        "checkpoints_skipped": extras.get("checkpoints_skipped", []),
        "stock_parameters": extras.get("stock_parameters", {}),
        "diagnosability": extras.get("diagnosability", {}),
    }
    m["coverage_report"] = coverage_report(pc, cov, extras, notices)
    m["summary"] = _summary(m, extras)
    return m


def _links(groups) -> list:
    """Shared sources, grouped by the outputs that share them."""
    out = []
    for g in groups:
        by: dict = {}
        for x in g:
            by.setdefault(tuple(_ev_short(e) for e in x["evidence"]), []).append(x["root"])
        for holders, roots in sorted(by.items()):
            out.append(f"  {' and '.join(holders)} share {', '.join(sorted(roots))}")
    return out


def human_summary(m) -> list:
    s = m["summary"]
    L = ["CSIA FLIGHT ASSURANCE ANALYZER (offboard; no flight-control authority)",
         f"analyzer {m['analyzer_version']}, semantics {m['semantic_version']}, "
         f"profile {m['profile_gate']['profile'].get('name')} {m['profile_gate']['profile'].get('version')}",
         f"input: {m['inputs'].get('ulog', {}).get('file')} "
         f"({m['inputs'].get('configuration', '')}; {m['inputs'].get('rates', '')})", ""]

    def sec(title, items):
        L.append(title)
        if not items:
            L.append("  nothing")
        for x in items:
            L.append(f"  - {x}")
        L.append("")

    sec("WHAT HAPPENED?", s["what_happened"])
    sec("WHEN?", s["when"])
    sec("WHAT DID CSIA OBSERVE? (adverse outputs, with their magnitudes)", s["observed"])
    sec("WHAT COULD CSIA NOT OBSERVE?", s["not_observed"])
    sec("WHAT EXPLANATIONS REMAIN?", [f"{k}: {', '.join(v)}" for k, v in s["explanations_remaining"].items()])
    sec("WHAT WAS ELIMINATED, AND WHY?", s["eliminated"])
    sec("WHICH MONITORS AGREED?", [f"{p}: {', '.join(v)}" for p, v in sorted(s["monitors_agreeing"].items())])
    ind = s["independence"]
    sec("WERE THEY INDEPENDENT?",
        [] if not ind["adverse_outputs"] else
        [f"{ind['adverse_outputs']} adverse outputs in {ind['lineage_groups']} lineage group(s): "
         f"{ind['independent_lines']} independent line(s)"]
        + _links(ind["group_links"]))
    sec("WHAT WOULD RESOLVE THE REMAINING AMBIGUITY?", s["would_resolve"])
    a = s["attribution"]
    sec("IS ATTRIBUTION JUSTIFIED?",
        [f"{'yes' if a['justified'] else 'no'}: {a['verdict']}"
         + (f" ({', '.join(a['candidates'])})" if a["candidates"] else "")
         + (f"; {a['why']}" if a.get("why") else "")])
    L.append("=" * 72)
    L.append("DETAIL")
    L.append("")
    L.append("EVENTS (discovered; a trigger says something may have started, not what failed)")
    for e in m["events"]:
        L.append(f"  {e['event_id']}: t0 {e['t0']:.3f} s, first alarm {e['first_alarm_t']:.3f} s")
        for t in e["triggers"]:
            L.append(f"    {t['kind']}" + (f" motor {t['motor']}" if t["motor"] is not None else "")
                     + f": onset {t['onset_t']:.3f} s, alarm {t['alarm_t']:.3f} s"
                     + (f", magnitude {_fmt(t['magnitude'])} ({t['unit']})" if t.get("magnitude") is not None else ""))
    if not m["events"]:
        L.append("  none")
    for x in m.get("checkpoints_skipped", []):
        L.append(f"  {x['event_id']} {x['checkpoint']} not evaluated: {x['why']}")
    L += ["", "EVIDENCE VALUES (every stock output)"]
    for v in m["evidence_values"]:
        L.append(f"  {v['t']:.3f}s {_ev_short(v['evidence_id'])}: {v['state']} {_fmt(v['measured'])} "
                 f"{v['unit']} (threshold {_fmt(v['threshold'])}; {v['window']})"
                 + (f" {', '.join(v['reason_codes'])}" if v["state"] != "NOMINAL" and v["reason_codes"] else "")
                 + (f" [producer {v['producer_health']}: {v['log_gap'] or 'not admitted'}; not used]"
                    if v.get("producer_health", "VALID") != "VALID" else ""))
    cr = m["coverage_report"]
    L += ["", f"COVERAGE ({cr['profile_records_observed']} of {cr['profile_records_expected']} profile "
              "records observed; unobserved is not healthy)"]
    for r in cr["records"]:
        if not r["observed"]:
            L.append(f"  NOT OBSERVED {r['record']}: {r['meaning']}")
    for t, flds in cr["fields_without_information"].items():
        L.append(f"  topic {t}: fields that never vary: {', '.join(f'{k} ({v})' for k, v in sorted(flds.items()))}")
    if cr["topics_absent"]:
        L.append(f"  topics absent: {', '.join(cr['topics_absent'])}")
    dg = m.get("diagnosability") or {}
    L += ["", "DIAGNOSABILITY (with the evidence this log can supply)"]
    for sym in dg.get("symptoms", []):
        if not sym.get("raisable"):
            L.append(f"  {sym['symptom']}: cannot be raised ({sym['why']})")
        elif sym.get("subject") in ("motor_0",) or len([x for x in dg["symptoms"] if x.get("raisable")]) <= 4:
            L.append(f"  {sym['symptom']} on {sym['subject']}: could be eliminated "
                     f"{', '.join(sym['distinguishable']) or 'none'}; never eliminable "
                     f"{', '.join(sym['never_eliminable']) or 'none'}")
    L += ["", "=" * 72, ""]
    return L
