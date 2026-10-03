"""CSIA Flight Assurance PRIME-1: the first page and the conclusion receipts. OFFBOARD ONLY.

A view over the machine report (`report.json`): it adds no semantics and
changes no conclusion. PRIME's view (`assurance_view.py`) stays as it was for
`assure --release prime`; its helpers (coverage classes, alerts, evidence
descriptions) are reused here unchanged.

FIRST PAGE (for an engineer who has never read the CSIA papers)
---------------------------------------------------------------
1. WHAT HAPPENED
2. WHEN
3. WHAT CSIA CAN JUSTIFY
4. WHAT CSIA CANNOT JUSTIFY
5. WHY
6. KEY EVIDENCE
7. EVIDENCE REJECTED
8. DEPENDENCY / SHARED SOURCES
9. MISSING INSTRUMENTATION
10. NEXT ENGINEERING CHECK
then TECHNICAL DETAIL.

No probability, no confidence figure, no percentage: semantic states only.

RECEIPTS (`receipts.json`): for every conclusion, TYPE, CONCLUSION, STATUS,
SUPPORTING / REFUTING / REJECTED EVIDENCE, REJECTION REASONS, SOURCE LINEAGE,
INDEPENDENT LINE COUNT, PRODUCER HEALTH, CONTENT TIME, CONFIGURATION EPOCH,
COVERAGE, WHAT WOULD RESOLVE THE AMBIGUITY, VERSION. Deterministic JSON
(`report.dumps`).
"""
from __future__ import annotations

from . import assurance_view as AV

VIEW_VERSION = "prime1-view-1"
CLASSES = AV.CLASSES
SEMANTICS_PLAIN = {
    "RPM_DEFICIT_EVENT": "ESC-reported rotor speed dropped below its recent level",
    "RPM_EXCESS_EVENT": "ESC-reported rotor speed rose above its recent level",
    "COMPENSATION_CHANGE_EVENT": "the controller started asking one motor for more than the others",
    "ESC_OFFLINE_EVENT": "an ESC reported itself offline",
}
#: What would separate each remaining explanation (instrumentation), and the engineering check.
MEASURE = {
    "ACTUATION/drive_no_current": "ESC current per motor (esc_status.esc_current)",
    "ACTUATION/mechanical": "ESC current together with RPM (the stall signature)",
    "COMMUNICATION/command_not_delivered": "the command each ESC actually received (ESC-side telemetry of the command)",
    "POWER/path_unavailable": "battery current (battery_status.current_a) and per-ESC supply voltage",
    "SENSOR/response_sensor": "an independent rotor-speed or thrust measurement",
}
CHECK = {
    "ACTUATION/drive_no_current": "inspect {m}'s ESC and motor phase wiring; log ESC current on the next flight",
    "ACTUATION/mechanical": "inspect {m}'s propeller, bearings and mount; run the motor on a bench",
    "COMMUNICATION/command_not_delivered": "check {m}'s signal path (connector, ESC protocol configuration)",
    "POWER/path_unavailable": "check {m}'s power path (connector, distribution board); log battery current",
}


def _versions(m: dict, sup: dict) -> dict:
    return dict(AV._versions(m), view=VIEW_VERSION, release=m.get("inputs", {}).get("release"),
                support_contract=sup.get("contract_version"))


def _coverage_of(cov_rows: list, component: str) -> dict:
    return {f"{r['record']}|{r.get('producer_id') or '-'}": r["class"] + (" (partial)" if r.get("partial") else "")
            for r in cov_rows if r["record"].startswith(component + ":")}


def _times(items: list) -> list:
    return sorted({x["content_time_s"] for x in items if isinstance(x, dict) and x.get("content_time_s") is not None})


def receipts(m: dict, sup: dict, cov_rows: list) -> list:
    """Every conclusion with the full receipt (Phase 16)."""
    f = m.get("final", {})
    cfg = f.get("configuration", {})
    epoch = {"epochs": cfg.get("epochs", {}), "changes": cfg.get("changes", []),
             "not_admitted_by_epoch": cfg.get("not_admitted_by_epoch", [])}
    out = []
    for r in AV.receipts(m):
        kind = r["kind"]
        comp = None
        if kind == "symptom":
            comp = "ACTUATION/" + r["conclusion"].split(" on ")[1].split(":")[0]
        elif kind == "unconfirmed":
            comp = r["conclusion"].split("unconfirmed: ")[1].split(":")[0]
        supporting = r.get("supporting_evidence", [])
        refuting = r.get("refuting_evidence", [])
        rejected = r.get("rejected_evidence", [])
        lin = r.get("source_lineage", {})
        rec = {"type": kind.upper(), "conclusion": r["conclusion"], "status": r["semantic_state"],
               "why": r.get("why"),
               "supporting_evidence": supporting, "refuting_evidence": refuting,
               "rejected_evidence": rejected,
               "rejection_reasons": sorted({x for e in rejected for x in e.get("reasons", [])}),
               "source_lineage": lin,
               "independent_line_count": (lin.get("independent_lines") if lin
                                          else (1 if supporting else 0)),
               "producer_health": r.get("producer_health")
               or {e["producer"]: e.get("producer_health") for e in supporting if "producer" in e},
               "content_time_s": _times(supporting + refuting),
               "configuration_epoch": epoch,
               "coverage": _coverage_of(cov_rows, comp) if comp else {},
               "would_resolve": r.get("would_resolve", []),
               "still_possible": r.get("still_possible", r.get("unexcluded_alternatives", [])),
               "version": _versions(m, sup)}
        if kind == "attribution":
            rec.update({"candidates": r.get("candidates", []), "justified": r.get("justified"),
                        "withheld_unique_because": r.get("withheld_unique_because", [])})
        out.append(rec)
    return out


# ------------------------------------------------------------------ the first page
def _times_threshold(v: dict) -> str:
    th, x = v.get("threshold"), v.get("measured")
    if not th or x is None:
        return ""
    return f"; {abs(x) / th:.3g} x its threshold"


def _num(x) -> str:
    return f"{x:.4g}" if isinstance(x, (int, float)) else str(x)


def _plain_value(v: dict) -> str:
    return _plain_value_core(v) + _times_threshold(v)


def _plain_value_core(v: dict) -> str:
    rec, st, codes = v["record"], v["state"], v.get("reason_codes") or []
    motor = rec.split("/")[1].split(":")[0] if "/" in rec else rec
    if rec.endswith("esc.telemetry_response"):
        if "ESC_TELEMETRY_EXCESS" in codes:
            return (f"{motor}'s ESC reports MORE rotor speed than commanded, against the other rotors "
                    f"(telemetry excess, L = {v['measured']:.4g})")
        if "ESC_TELEMETRY_DEFICIT" in codes:
            return (f"{motor}'s ESC reports LESS rotor speed than commanded, against the other rotors "
                    f"(telemetry deficit, L = {v['measured']:.4g})")
    if rec.endswith("actuation.physical_response") and st == "VIOLATED":
        return f"{motor} lost physical effect: the controller compensated (ratio change {v['measured']:.4g})"
    if rec.endswith("vehicle.rate_transient"):
        return f"the vehicle rotated toward {motor}'s side at the event ({v['measured']:.4g} rad/s)"
    return f"{rec}: {st} {v['measured']} {v.get('unit', '')}".strip()


def _ev_line(e: dict) -> str:
    parts = []
    for t in e.get("triggers", []):
        sem = (t.get("detail") or {}).get("semantics")
        who = f" on motor_{t['motor']}" if t.get("motor") is not None else ""
        if sem:
            parts.append(f"{sem}{who} ({SEMANTICS_PLAIN.get(sem, '')})")
        else:
            txt = (t.get("detail") or {}).get("text")
            parts.append(f"{t['kind']}{who}" + (f": {txt}" if txt else ""))
    uniq = list(dict.fromkeys(parts))
    return f"{e['event_id']} at {e['t0']:.2f} s: " + "; ".join(uniq)


def _adverse(m: dict) -> list:
    return [v for v in m.get("evidence_values", []) if v["state"] in ("VIOLATED", "DEGRADED")]


def build(m: dict, sup: dict) -> dict:
    cov = AV.coverage_states(m)
    rc = receipts(m, sup, cov)
    alerts = AV.alerts(m)
    s = m.get("summary", {})
    f = m.get("final", {})
    att = s.get("attribution", {})
    locs = f.get("localizations", [])
    symptoms = [x for x in locs]
    adverse = _adverse(m)
    confirmed_comps = {"ACTUATION/" + x["subject"] for x in locs}
    unconfirmed = [v for v in adverse if v["record"].split(":")[0] not in confirmed_comps]
    # one line per record (its largest output), largest first relative to its threshold
    best = {}
    for v in unconfirmed:
        k = v["record"]
        r = abs(v["measured"] or 0) / (v.get("threshold") or 1)
        if k not in best or r > best[k][0]:
            best[k] = (r, v)
    unconfirmed = [v for _r, v in sorted(best.values(), key=lambda x: (-x[0], x[1]["record"]))]
    baseline = [v for v in m.get("evidence_values", [])
                if "TELEMETRY_BASELINE_INCONSISTENT" in (v.get("reason_codes") or [])]
    L = []
    L.append("CSIA FLIGHT ASSURANCE (PRIME-1): ASSURANCE SUMMARY (offboard; no flight-control authority)")
    p = f.get("profile", {})
    L.append(f"log: {m.get('inputs', {}).get('ulog', {}).get('file')}   release {m.get('inputs', {}).get('release')}, "
             f"analyzer {m.get('analyzer_version')}, semantics {m.get('semantic_version')}, profile "
             f"{p.get('name')} {p.get('version')}, view {VIEW_VERSION}, support contract {sup.get('contract_version')}")
    L.append(f"SUPPORT: {sup['status']} (configuration {sup.get('configuration')}; validation level "
             f"{sup.get('validation_level')})")
    for r in sup.get("reasons", []):
        L.append(f"  - {r}")
    L.append("")
    # 1
    L.append("1. WHAT HAPPENED")
    if symptoms:
        for x in symptoms:
            n = len(x.get("unresolved", []))
            L.append(f"  - {x['symptom']} on {x['subject']}: {x['outcome']}"
                     + (f" (explanations remaining: {n})" if n else ""))
    for v in unconfirmed:
        L.append(f"  - observed, not confirmed: {_plain_value(v)}")
    if not symptoms and not unconfirmed:
        L.append("  - nothing adverse was observed in the records CSIA could judge")
    if baseline:
        motors = sorted({v["record"].split("/")[1].split(":")[0] for v in baseline})
        L.append(f"  - telemetry of {', '.join(motors)} had no valid reference at some events: no change "
                 "statement is made there (TELEMETRY_BASELINE_INCONSISTENT)")
    # 2
    L.append("2. WHEN")
    evs = m.get("events", [])
    if evs:
        for e in evs[:8]:
            L.append(f"  - {_ev_line(e)}")
        if len(evs) > 8:
            L.append(f"  - ... {len(evs) - 8} more (alerts.json)")
    else:
        L.append("  - no event was discovered")
    # 3
    L.append("3. WHAT CSIA CAN JUSTIFY")
    can = []
    for x in symptoms:
        can.append(f"{x['symptom']} on {x['subject']} is supported by admitted evidence")
        for el in x.get("eliminated", []):
            can.append(f"{x['subject']}: {el['hypothesis']} is eliminated ({el['by']})")
    for v in unconfirmed:
        if v["record"].endswith("esc.telemetry_response"):
            can.append(f"{v['record'].split('/')[1].split(':')[0]}'s ESC telemetry changed at an event "
                       "(a telemetry observation, not a motor fault)")
    if att.get("verdict") == "UNIQUE" and att.get("justified"):
        can.append(f"a single cause: {', '.join(att.get('candidates', []))}")
    if not can:
        can.append("no propulsion fault in the records that were observed (see 9 for what was not)")
    L += [f"  - {c}" for c in can]
    # 4
    L.append("4. WHAT CSIA CANNOT JUSTIFY")
    cannot = []
    if symptoms and (att.get("verdict") != "UNIQUE" or not att.get("justified")):
        cannot.append(f"a single root cause (attribution {att.get('verdict')}: {att.get('why')})")
    for x in symptoms:
        if x.get("unresolved"):
            cannot.append(f"which of {len(x['unresolved'])} explanations caused {x['symptom']} on {x['subject']}")
    for v in unconfirmed:
        comp = v["record"].split(":")[0]
        cannot.append(f"that {comp} has a physical fault: its observation was not confirmed by an independent witness")
    cr = m.get("coverage_report", {})
    exp, obs = cr.get("profile_records_expected"), cr.get("profile_records_observed")
    if exp is not None and obs is not None and obs < exp:
        cannot.append(f"anything about the {exp - obs} of {exp} profile records that were not observed "
                      "(silence is not health)")
    L += [f"  - {c}" for c in cannot] or ["  - nothing withheld"]
    # 5
    L.append("5. WHY")
    L.append(f"  - attribution {att.get('verdict')}: {att.get('why')}")
    for x in symptoms:
        L.append(f"  - {x['symptom']} on {x['subject']}: {x.get('why')}")
    # 6
    L.append("6. KEY EVIDENCE")
    key = sorted(adverse, key=lambda v: (v["record"], v["t"]))[:6]
    for v in key:
        L.append(f"  - {v['record']} [{v['producer_id']}]: {v['state']} {_num(v['measured'])} {v.get('unit', '')} "
                 f"(threshold {_num(v.get('threshold'))}; {v.get('window')}; at {v['t']} s)")
    if not key:
        L.append("  - no adverse evidence")
    # 7
    L.append("7. EVIDENCE REJECTED")
    rej = []
    for x in f.get("evidence", {}).get("rejected", []):
        rej.append(f"{x['evidence_id']}: {x['status']} ({'; '.join(AV._plain(r) for r in x['reasons'])})")
    grouped = {}
    for v in m.get("evidence_values", []):
        if v["state"] == "UNAVAILABLE" and v.get("reason_codes"):
            k = (v["record"], v["producer_id"], tuple(v["reason_codes"]))
            grouped.setdefault(k, []).append(v["t"])
    for (rec_, pid, codes), ts in sorted(grouped.items(), key=lambda x: (min(x[1]), x[0])):
        when = f"at {ts[0]} s" if len(ts) == 1 else f"{len(ts)} times from {min(ts)} s"
        rej.append(f"{rec_} [{pid}] {when}: {'; '.join(AV._plain(r) for r in codes)}")
    rej = list(dict.fromkeys(rej))
    L += [f"  - {r}" for r in rej[:8]] or ["  - none"]
    if len(rej) > 8:
        L.append(f"  - ... {len(rej) - 8} more (receipts.json)")
    # 8
    L.append("8. DEPENDENCY / SHARED SOURCES")
    ind = s.get("independence", {})
    L.append(f"  - {ind.get('adverse_outputs', 0)} adverse output(s) amount to {ind.get('independent_lines', 0)} "
             f"independent line(s) of evidence ({ind.get('lineage_groups', 0)} lineage group(s))")
    for grp in ind.get("group_links", [])[:1]:
        roots = [g["root"] for g in grp]
        if roots:
            L.append(f"  - shared sources: {', '.join(roots[:5])}" + (" ..." if len(roots) > 5 else ""))
    # 9
    L.append("9. MISSING INSTRUMENTATION")
    miss = []
    for n in cr.get("coverage_notices", []):
        if n.get("producer_id") == "cusum:v1_1_sequential":
            continue
        miss.append(f"{n.get('source')}: {n.get('why')}")
    for x in symptoms:
        for h in x.get("unresolved", []):
            if h in MEASURE:
                miss.append(f"to separate {h} for {x['subject']}: {MEASURE[h]}")
    miss = list(dict.fromkeys(miss))
    L += [f"  - {x}" for x in miss] or ["  - none identified"]
    # 10
    L.append("10. NEXT ENGINEERING CHECK")
    nxt = []
    for x in symptoms:
        for h in x.get("unresolved", []):
            if h in CHECK:
                nxt.append(CHECK[h].format(m=x["subject"]))
    for v in unconfirmed:
        if v["record"].endswith("esc.telemetry_response"):
            mot = v["record"].split("/")[1].split(":")[0]
            nxt.append(f"verify {mot}'s ESC telemetry (pole-count and scaling configuration, connector) against "
                       "an independent tachometer before trusting its RPM")
    if not nxt:
        nxt.append("none required by this log; the records not observed (9) are where a fault could hide")
    L += [f"  - {x}" for x in dict.fromkeys(nxt)]
    # technical detail
    L.append("")
    L.append("TECHNICAL DETAIL")
    for k, v in s.get("explanations_remaining", {}).items():
        L.append(f"  - remaining for {k}: {', '.join(v)}")
    for e in s.get("eliminated", []):
        L.append(f"  - eliminated: {e}")
    counts = {c: sum(1 for r in cov if r["class"] == c) for c in CLASSES}
    L.append("  - coverage rows (record x producer) by class: "
             + ", ".join(f"{c} {n}" for c, n in counts.items() if n))
    for ch in f.get("configuration", {}).get("changes", [])[:6]:
        L.append(f"  - configuration change: {ch}")
    for a in alerts[:8]:
        L.append(f"  - alert {a['first_t']:.2f}-{a['last_t']:.2f} s {a['kind']}"
                 + (f": {a['text']}" if a.get("text") else "") + f" (raised {a['raised']}x)")
    text = "\n".join(L) + "\n"
    return {"summary_text": text, "receipts": rc, "coverage_states": cov, "support": sup, "alerts": alerts}


# ------------------------------------------------------------------ withheld interpretation
def generic_text(file: str, sup: dict, generic: dict) -> str:
    L = ["CSIA FLIGHT ASSURANCE (PRIME-1): ASSURANCE SUMMARY (offboard; no flight-control authority)",
         f"log: {file}   view {VIEW_VERSION}, support contract {sup.get('contract_version')}",
         f"SUPPORT: {sup['status']}"]
    veh = sup.get("vehicle") or {}
    if sup["status"] == "UNSUPPORTED_VEHICLE_CONFIGURATION":
        L += [f"  - detected vehicle: {veh.get('detected')} (airframe {veh.get('sys_autostart')}, "
              f"CA_ROTOR_COUNT {veh.get('ca_rotor_count')})",
              f"  - requested profile: {veh.get('requested_profile')}",
              f"  - supported vehicle classes: {'; '.join(veh.get('supported_vehicle_classes', []))}"]
    for r in sup.get("reasons", []):
        L.append(f"  - {r}")
    L += ["", "INTERPRETATION WITHHELD",
          "  - no diagnostic conclusion is drawn for this log. This is a statement about the Analyzer's",
          "    scope, not about the log or the vehicle: the log is not judged broken.", "",
          "GENERIC ANALYSIS (safe for any PX4 log)"]
    px = sup.get("px4") or {}
    L.append(f"  - PX4 {px.get('release') or 'version not recorded'} ({px.get('git') or '-'}), hardware "
             f"{px.get('hardware') or '-'}")
    li = generic.get("log_integrity", {})
    if li:
        L.append(f"  - log integrity: {li.get('topics', 0)} topics; {li.get('dropouts', 0)} logger dropout(s); "
                 f"largest gaps: " + (", ".join(f"{k} {v} ms" for k, v in li.get("largest_gap_ms", {}).items())
                                      or "-"))
    al = generic.get("alerts", [])
    if al:
        L.append("  - PX4's own warnings and failsafes (identical re-raised conditions grouped):")
        for a in al[:12]:
            L.append(f"    {a['first_t']:.2f}-{a['last_t']:.2f} s {a['kind']}"
                     + (f": {a['text']}" if a.get("text") else "") + f" (raised {a['raised']}x)")
    else:
        L.append("  - PX4 raised no warning, failsafe or failure-detector flag in flight")
    return "\n".join(L) + "\n"
