"""The assurance view: the CSIA Flight Assurance summary, receipts and coverage states. OFFBOARD ONLY.

A view over the machine report (`report.machine_report`). It adds no
semantics: every statement it makes is read from the report that
Semantic Core 2.1.1 and the 2.2 evidence model produced. The report itself is
unchanged (`analyze` writes exactly what it always wrote); the view is
written only by the `assure` sub-command.

WHY IT EXISTS (CSIA PRIME, Track A; research/csia_prime/TRACK_A_MVP.md)
-------------------------------------------------------------------
- **A1, the first page:** the report answered most of the engineer's
  questions, but "what evidence was rejected, and why" was not in its
  summary.
- **A3, receipts:** there was no per-conclusion receipt.
- **A4, coverage states:** coverage was a per-producer tick count, not
  stated per record in the brief's terms.
- **Alert grouping:** measured on a real FMUv5 log, one persistent PX4
  condition became 9 events (REAL_DATA_ACQUISITION.md).

CONFIDENCE DISCIPLINE (A2)
--------------------------
No percentage, probability or confidence figure appears. The states are
2.1.1's (UNIQUE, AMBIGUOUS, SUPPORTED, NO_CONSISTENT, NO_EVIDENCE) and the
coverage classes below.

COVERAGE CLASSES (A4)
---------------------
Per profile record, from the report's per-tick states:

| report state | class |
|---|---|
| ANOMALY (also VIOLATED, DEGRADED) | OBSERVED (an adverse value was observed) |
| NO_ANOMALY, NOMINAL | NO_ANOMALY |
| NO_COVERAGE, or a profile record no producer emitted | NO_COVERAGE |
| UNAVAILABLE | UNAVAILABLE |
| REJECTED:STALE | STALE |
| REJECTED:PRODUCER_INVALID, a producer fault, a predicate fault | FAULTED |
| REJECTED:<any other gate reason, e.g. REGIME_INVALID> | UNAVAILABLE (the reason is kept) |
| NOT_APPLICABLE | NOT_APPLICABLE |
| anything else | UNKNOWN |

**A record's class** is the first, in this order, that any of its ticks
has: OBSERVED, FAULTED, STALE, NO_ANOMALY, NOT_APPLICABLE, UNAVAILABLE,
NO_COVERAGE, UNKNOWN.

**NO_ANOMALY is marked `partial`** whenever any tick was in another class.

**The invariant (tested):** nothing unavailable, stale, faulted, unknown or
uncovered is ever reported as NO_ANOMALY.
"""

from __future__ import annotations

VIEW_VERSION = "prime-view-1"
CLASSES = ("OBSERVED", "FAULTED", "STALE", "NO_ANOMALY", "NOT_APPLICABLE", "UNAVAILABLE",
           "NO_COVERAGE", "UNKNOWN")
#: E1's merge rule (EVENT_DISCOVERY_STUDY.md): a re-raised identical PX4 condition within this joins one alert.
ALERT_MERGE_S = 60.0
#: EKF2 aiding and reset changes in the first seconds of a log happen in every flight (2.2 pilot:
#: 64 of 66); they are summarised in one line, not listed.
START_UP_S = 10.0


# ------------------------------------------------------------------ A4 coverage states
def state_class(state: str) -> str:
    s = str(state)
    if s in ("ANOMALY", "VIOLATED", "DEGRADED"):
        return "OBSERVED"
    if s in ("NO_ANOMALY", "NOMINAL"):
        return "NO_ANOMALY"
    if s == "NO_COVERAGE":
        return "NO_COVERAGE"
    if s == "UNAVAILABLE":
        return "UNAVAILABLE"
    if s == "NOT_APPLICABLE":
        return "NOT_APPLICABLE"
    if s.startswith("REJECTED:"):
        reason = s.split(":", 1)[1]
        if reason == "STALE":
            return "STALE"
        if reason in ("PRODUCER_INVALID", "FAULTED", "PREDICATE_FAULT"):
            return "FAULTED"
        return "UNAVAILABLE"
    if s in ("FAULTED", "PRODUCER_FAULT", "PREDICATE_FAULT"):
        return "FAULTED"
    return "UNKNOWN"


def record_class(ticks_by_state: dict) -> dict:
    counts: dict = {}
    for st, n in ticks_by_state.items():
        c = state_class(st)
        counts[c] = counts.get(c, 0) + int(n)
    primary = next((c for c in CLASSES if counts.get(c)), "UNKNOWN")
    return {"class": primary,
            "partial": primary == "NO_ANOMALY" and any(c != "NO_ANOMALY" for c in counts),
            "classes": dict(sorted(counts.items())), "states": dict(sorted(ticks_by_state.items()))}


def coverage_states(m: dict) -> list:
    rows = []
    seen = set()
    for c in m.get("coverage", []):
        r = record_class(c["ticks_by_state"])
        rows.append(dict(r, record=c["record"], producer_id=c["producer_id"]))
        seen.add(c["record"])
    for rec in m.get("coverage_report", {}).get("records", []):
        if rec["record"] not in seen and not rec.get("observed"):
            rows.append({"record": rec["record"], "producer_id": None, "class": "NO_COVERAGE",
                         "partial": False, "classes": {"NO_COVERAGE": 1}, "states": {},
                         "meaning": rec.get("meaning", "")})
    for p, s in m.get("final", {}).get("producers", {}).get("by_producer", {}).items():
        if s.get("faults"):
            for r in rows:
                if r.get("producer_id") == p:
                    r["class"], r["partial"] = "FAULTED", False
                    r["producer_faults"] = s["faults"]
    return sorted(rows, key=lambda r: (CLASSES.index(r["class"]), r["record"], r.get("producer_id") or ""))


# ------------------------------------------------------------------ alerts (grouped events)
def alerts(m: dict) -> list:
    groups, out = {}, []
    for e in m.get("events", []):
        kinds = [t["kind"] for t in e["triggers"]]
        if kinds and all(k.startswith("px4.") for k in kinds):
            for t in e["triggers"]:
                key = (t["kind"], (t.get("detail") or {}).get("text"))
                g = groups.get(key)
                if g is not None and t["onset_t"] - g["last_t"] <= ALERT_MERGE_S:
                    g["last_t"] = t["onset_t"]
                    g["raised"] += 1
                    if e["event_id"] not in g["events"]:
                        g["events"].append(e["event_id"])
                else:
                    g = {"kind": t["kind"], "text": key[1], "first_t": t["onset_t"], "last_t": t["onset_t"],
                         "raised": 1, "events": [e["event_id"]]}
                    groups[key] = g
                    out.append(g)
        else:
            out.append({"kind": "+".join(sorted(set(kinds))), "text": None, "first_t": e["t0"],
                        "last_t": e["t0"], "raised": 1, "events": [e["event_id"]],
                        "motors": e.get("motors", [])})
    return sorted(out, key=lambda a: (a["first_t"], a["kind"]))


# ------------------------------------------------------------------ A3 receipts
def _value(m: dict, evidence_id: str):
    for v in m.get("evidence_values", []):
        if v["evidence_id"] == evidence_id:
            return v
    rec, t = None, None
    parts = evidence_id.split("|")
    if len(parts) >= 4:
        rec, t = parts[2], parts[3]
    for v in m.get("evidence_values", []):
        if v["record"] == rec and t is not None and abs(float(v["t"]) - float(t)) < 1e-6:
            return v
    return None


def _describe(m: dict, evidence_id: str) -> dict:
    v = _value(m, evidence_id)
    if v is None:
        return {"evidence": evidence_id}
    return {"evidence": evidence_id, "record": v["record"], "producer": v["producer_id"],
            "state": v["state"], "measured": v["measured"], "unit": v["unit"],
            "threshold": v["threshold"], "window": v["window"], "content_time_s": v["t"],
            "producer_health": v["producer_health"], "reason_codes": v["reason_codes"]}


def _rejected_for(m: dict, component: str) -> list:
    out = []
    for x in m.get("final", {}).get("evidence", {}).get("rejected", []):
        if component in x["evidence_id"]:
            out.append({"evidence": x["evidence_id"], "status": x["status"], "reasons": x["reasons"]})
    for x in m.get("key_moments", {}).get("evidence_invalidated", []):
        if component in x["evidence"]:
            out.append({"evidence": x["evidence"], "status": x["status"], "reasons": [x["reason"]],
                        "at_s": x["t"]})
    for v in m.get("evidence_values", []):
        if v["record"].startswith(component + ":") and v["state"] == "UNAVAILABLE":
            out.append({"evidence": v["evidence_id"], "status": "UNAVAILABLE",
                        "reasons": v["reason_codes"] or ["UNAVAILABLE"], "at_s": v["t"]})
    seen, uniq = set(), []
    for r in out:
        k = (r["evidence"], r["status"], tuple(r["reasons"]))
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def _versions(m: dict) -> dict:
    f = m.get("final", {})
    p = f.get("profile", {})
    return {"analyzer": m.get("analyzer_version"), "semantics": m.get("semantic_version"),
            "profile": f"{p.get('name')} {p.get('version')}", "profile_digest": p.get("digest"),
            "view": VIEW_VERSION}


def receipts(m: dict) -> list:
    f = m.get("final", {})
    corr = {c["component"]: c for c in f.get("corroboration", {}).get("by_component", [])}
    cfg = f.get("configuration", {})
    by_prod = f.get("producers", {}).get("by_producer", {})
    out = []
    for loc in f.get("localizations", []):
        comp = f"ACTUATION/{loc['subject']}" if loc.get("subject", "").startswith("motor_") else loc.get("subject")
        c = corr.get(comp, {})
        producers = sorted(set(c.get("producers", [])))
        out.append({
            "kind": "symptom",
            "conclusion": f"{loc['symptom']} on {loc['subject']}: {loc['outcome']}",
            "semantic_state": loc["outcome"], "why": loc["why"],
            "supporting_evidence": [_describe(m, e) for e in c.get("adverse_evidence", [])],
            "refuting_evidence": [dict(_describe(m, e), eliminates=[x["hypothesis"] for x in loc["eliminated"]])
                                  for e in loc.get("refuting_evidence", [])],
            "eliminated": loc["eliminated"],
            "still_possible": loc["unresolved"],
            "rejected_evidence": _rejected_for(m, comp),
            "evidence_that_could_not_be_evaluated": loc.get("evidence_unavailable", []),
            "would_resolve": loc.get("would_discriminate", []),
            "source_lineage": {"roots": loc.get("evidence_basis", {}),
                               "lineage_groups": c.get("lineage_groups", []),
                               "independent_lines": c.get("independent_lines")},
            "producer_health": {p: by_prod.get(p, {}).get("health") for p in producers},
            "configuration": {"changes": cfg.get("changes", []),
                              "not_admitted_by_epoch": cfg.get("not_admitted_by_epoch", [])},
            "versions": _versions(m)})
    att = f.get("attribution", {})
    out.append({
        "kind": "attribution",
        "conclusion": f"attribution: {att.get('verdict')}", "semantic_state": att.get("verdict"),
        "why": att.get("why"), "candidates": att.get("candidates", []), "unique": att.get("unique"),
        "unexcluded_alternatives": att.get("unexcluded_alternatives", []),
        "withheld_unique_because": att.get("withheld_unique_because", []),
        "justified": bool(m.get("summary", {}).get("attribution", {}).get("justified")),
        "versions": _versions(m)})
    with_symptom = {f"ACTUATION/{loc['subject']}" for loc in f.get("localizations", [])}
    for v in m.get("evidence_values", []):
        comp = v["record"].split(":", 1)[0]
        if v["state"] in ("VIOLATED", "DEGRADED") and comp not in with_symptom:
            out.append({
                "kind": "unconfirmed",
                "conclusion": f"unconfirmed: {v['record']} {v['state']}",
                "semantic_state": "UNCONFIRMED_OBSERVATION",
                "why": "an adverse output that no symptom reads (context), or whose confirmation was refused",
                "supporting_evidence": [_describe(m, v["evidence_id"])],
                "rejected_evidence": _rejected_for(m, comp),
                "versions": _versions(m)})
    return out


# ------------------------------------------------------------------ A1 summary
#: Plain-language meaning of the reason codes an engineer meets most (the code is always shown too).
PLAIN = {
    "NOT_STEADY_FLIGHT": "vehicle maneuvering: the compensation statistic is valid only in near-steady flight",
    "CONTENT_OUTSIDE_VALIDATED_WINDOW": "outside the time window this evidence is valid for (e.g. held from an earlier event)",
    "ESC_TELEMETRY_OFFLINE": "the ESC reported itself offline",
    "BATTERY_CURRENT_NOT_MEASURED": "battery current is not measured",
    "NOT_MEASURABLE_IN_FLIGHT_WINDOWS": "too few in-flight samples in the window",
    "IN_PROCESS_PRODUCER_NOT_VALID": "the producer's input had a log gap",
    "NO_LOCAL_DEFICIT_TO_TEST": "no local deficit on this motor, so nothing to test",
    "STALE": "too old to use at this time",
}


def _plain(reason: str) -> str:
    code = reason.split(":", 1)[0]
    return f"{reason}: {PLAIN[code]}" if code in PLAIN else reason


def _fmt(x):
    if x is None:
        return "n/a"
    return f"{x:.4g}" if isinstance(x, float) else str(x)


def summary_text(m: dict, support: dict, view: dict) -> str:
    s = m.get("summary", {})
    f = m.get("final", {})
    L = ["CSIA FLIGHT ASSURANCE: ASSURANCE SUMMARY (offboard; no flight-control authority)"]
    v = _versions(m)
    L.append(f"log: {m.get('inputs', {}).get('ulog', {}).get('file', '?')}   analyzer {v['analyzer']}, "
             f"semantics {v['semantics']}, profile {v['profile']}, view {v['view']}")
    L.append(f"SUPPORT: {support.get('status')}" +
             (": " + "; ".join(support.get("reasons", [])) if support.get("reasons") else ""))
    L.append("")
    L.append("WHAT HAPPENED?")
    happened = [r["conclusion"] for r in view["receipts"] if r["kind"] == "symptom"]
    best = {}
    for r in view["receipts"]:
        if r["kind"] != "unconfirmed":
            continue
        e = r["supporting_evidence"][0]
        thr = e.get("threshold") or 0.0
        score = abs(e.get("measured") or 0.0) / thr if thr else 0.0
        if e.get("record") not in best or score > best[e["record"]][0]:
            best[e["record"]] = (score, r, e)
    ranked = sorted(best.values(), key=lambda x: -x[0])
    for score, r, e in ranked[:3]:
        comp = e["record"].split(":", 1)[0]
        refused = sorted({x for v in m.get("evidence_values", []) if v["record"] == f"{comp}:actuation.physical_response"
                          and v["state"] == "UNAVAILABLE" for x in v["reason_codes"]})
        why = (f"its physical confirmation was refused ({_plain(refused[0])})" if refused
               else "context only: no symptom reads this output")
        happened.append(f"UNCONFIRMED: {e['record']} {e['state']} {_fmt(e.get('measured'))} {e.get('unit') or ''} "
                        f"(threshold {_fmt(e.get('threshold'))}; {e.get('window')}); {why}")
    if len(ranked) > 3:
        happened.append(f"(+{len(ranked) - 3} smaller unconfirmed context outputs: receipts.json)")
    L += [f"  - {x}" for x in (happened or ["nothing adverse was observed"])]
    L.append(f"  - attribution: {s.get('attribution', {}).get('verdict')} "
             f"({'justified' if s.get('attribution', {}).get('justified') else 'not justified'}: "
             f"{s.get('attribution', {}).get('why')})")
    L.append("WHEN DID IT START?")
    L += [f"  - {x}" for x in (s.get("when") or ["no event"])][:4]
    L.append("WHICH SUBSYSTEM IS AFFECTED?")
    confirmed = sorted({f"ACTUATION/{loc['subject']}" for loc in f.get("localizations", [])})
    unconf = sorted({e["record"].split(":", 1)[0] for _sc, _r, e in ranked[:3]})
    L.append("  - " + (", ".join(confirmed) if confirmed else
                       "none confirmed" + (f" (unconfirmed observations on {', '.join(unconf)})" if unconf else "")))
    L.append("WHAT CAUSES REMAIN POSSIBLE?")
    rem = s.get("explanations_remaining", {})
    L += [f"  - {k}: {', '.join(vv)}" for k, vv in rem.items()] or ["  - none (no symptom)"]
    L.append("WHAT WAS ELIMINATED, AND WHY?")
    L += [f"  - {x}" for x in (s.get("eliminated") or ["nothing"])]
    L.append("WHAT EVIDENCE SUPPORTS THIS?")
    sup = [e for r in view["receipts"] if r["kind"] == "symptom" for e in r.get("supporting_evidence", [])]
    L += [f"  - {e.get('record')} [{e.get('producer')}]: {e.get('state')} {_fmt(e.get('measured'))} "
          f"{e.get('unit') or ''} (threshold {_fmt(e.get('threshold'))}; {e.get('window')})" for e in sup[:6]] \
        or ["  - no confirmed conclusion"]
    L.append("WHAT EVIDENCE WAS REJECTED, AND WHY?")
    rej = {}
    for r in view["receipts"]:
        for x in r.get("rejected_evidence", []):
            rec = x["evidence"].split("|")[2] if x["evidence"].count("|") >= 2 else x["evidence"]
            rej.setdefault((rec, x["status"], ", ".join(x["reasons"])), 0)
            rej[(rec, x["status"], ", ".join(x["reasons"]))] += 1
    L += [f"  - {rec}: {st} ({_plain(why)}){' x' + str(n) if n > 1 else ''}" for (rec, st, why), n in
          sorted(rej.items(), key=lambda kv: (-kv[1], kv[0]))][:6] or ["  - none"]
    if len(rej) > 6:
        L.append(f"  - (+{len(rej) - 6} more: receipts.json)")
    L.append("WHICH MONITORS SHARE THE SAME SOURCE?")
    ind = s.get("independence", {})
    L.append(f"  - {ind.get('adverse_outputs', 0)} adverse output(s) in {ind.get('lineage_groups', 0)} "
             f"lineage group(s): {ind.get('independent_lines', 0)} independent line(s)")
    for grp in ind.get("group_links", [])[:3]:
        roots = sorted({link["root"] for link in grp if isinstance(link, dict) and link.get("root")})
        outs = sorted({e.split("|")[2] + " [" + e.split("|")[0] + "]"
                       for link in grp if isinstance(link, dict) for e in link.get("evidence", [])
                       if e.count("|") >= 2})
        if roots:
            L.append(f"  - {' and '.join(outs)} share {', '.join(roots[:4])}"
                     f"{' (+' + str(len(roots) - 4) + ' more)' if len(roots) > 4 else ''}")
    L.append("WHAT WAS NOT OBSERVABLE?")
    counts = {}
    for r in view["coverage_states"]:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    L.append("  - coverage rows (record x producer) by class: " + ", ".join(f"{c} {counts[c]}" for c in CLASSES if c in counts))
    L += [f"  - {x}" for x in (s.get("not_observed") or [])[:5]]
    L.append("WHAT ADDITIONAL MEASUREMENT WOULD RESOLVE THE AMBIGUITY?")
    L += [f"  - {x}" for x in (s.get("would_resolve") or ["nothing is ambiguous"])[:5]]
    L.append("WHAT CHANGED IN THE CONFIGURATION? (EKF2 aiding, resets, sensor selection)")
    cc = m.get("key_moments", {}).get("configuration_changes", [])
    first_event = min((e["t0"] for e in m.get("events", [])), default=None)
    t_start = min((c["t"] for c in cc), default=0.0)
    startup = [c for c in cc if c["t"] <= t_start + START_UP_S]
    later = [c for c in cc if c["t"] > t_start + START_UP_S]
    if startup:
        L.append(f"  - start-up ({t_start:.0f}-{t_start + START_UP_S:.0f} s): {len(startup)} aiding/reset changes, "
                 "as in every flight (context, not a finding)")
    for c in later[:6]:
        near = (f" (event at {first_event:.1f} s)" if first_event is not None and abs(c["t"] - first_event) < 5.0
                else "")
        L.append(f"  - {c['t']:.1f} s: {c['event']}{near}")
    if not cc:
        L.append("  - none recorded (or no estimator evidence in this log)")
    L.append("ALERTS (re-raised identical PX4 conditions grouped)")
    L += [f"  - {a['first_t']:.2f}-{a['last_t']:.2f} s {a['kind']}"
          f"{(': ' + a['text']) if a.get('text') else ''} (raised {a['raised']}x; {', '.join(a['events'])})"
          for a in view["alerts"]][:10] or ["  - none"]
    return "\n".join(L) + "\n"


def build(m: dict, support: dict) -> dict:
    view = {"view_version": VIEW_VERSION, "coverage_states": coverage_states(m),
            "receipts": receipts(m), "alerts": alerts(m), "support": support}
    view["summary_text"] = summary_text(m, support, view)
    return view
