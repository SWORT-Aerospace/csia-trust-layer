"""Reports: the deterministic machine report, the event timeline, and the
human report.

MACHINE REPORT
--------------
`machine_report(results, inputs, gate, contracts)` returns a dict, and
`dumps()` turns it into bytes that are identical for identical inputs:
- keys sorted;
- floats rounded to 6 decimals;
- no wall-clock time, host name or absolute path;
- every list either ordered by the analysis or sorted.

The timeline holds the full `AssuranceResult` at the first tick of each
interval. The last tick's result is kept in full as `final`.

EVENT TIMELINE
--------------
A new interval starts when any of these changes:
- the verdict or the candidate set;
- a localization's outcome, candidates or eliminations;
- producer health;
- the profile state;
- a configuration epoch;
- the admissibility status of any held evidence (by producer, claim and
  record, not by content time);
- the predicate faults;
- the adverse evidence.

Ticks with none of these changes are collapsed into the interval: its
first and last tick and its tick count.

HUMAN REPORT
------------
Plain text, short, and only what the machine report says. There are no
probabilities or confidence percentages, because nothing in 2.1.1 or 2.2
computes one.
"""

from __future__ import annotations

import json
import math

from .analyzer import ANALYZER_VERSION

SCHEMA = "csia.flight_assurance_report/1"


def _canon(x):
    if isinstance(x, float):
        if not math.isfinite(x):
            return str(x)
        r = round(x, 6)
        return 0.0 if r == 0 else r
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(_canon(v) for v in x)
    if hasattr(x, "value") and not isinstance(x, (int, str, bool)):
        return _canon(x.value)
    return x


def dumps(obj) -> bytes:
    """Byte-stable JSON."""
    return (json.dumps(_canon(obj), sort_keys=True, indent=1, ensure_ascii=True,
                       allow_nan=False) + "\n").encode()


def _ekey(evidence_id: str) -> str:
    """Evidence id without its content time: producer|claim|record."""
    return evidence_id.rsplit("|", 1)[0]


def signature(r: dict) -> dict:
    """The parts of one result whose change starts a new interval."""
    adm = {_ekey(e): "ADMISSIBLE" for e in r["evidence"].get("used", [])}
    for x in r["evidence"].get("rejected", []):
        adm[_ekey(x["evidence_id"])] = x["status"]
    att = r.get("attribution") or {}
    return {
        "verdict": r["state"].get("attribution"),
        "candidates": list(att.get("candidates", [])),
        "localizations": sorted(
            [x["key"], x["outcome"], x["candidates"],
             sorted(e["hypothesis"] for e in x["eliminated"])]
            for x in r.get("localizations", [])),
        "producer_health": {p: v["health"] for p, v in
                            (r.get("producers") or {}).get("by_producer", {}).items()},
        "profile": (r.get("profile") or {}).get("gate"),
        "epochs": (r.get("configuration") or {}).get("epochs", {}),
        "admissibility": dict(sorted(adm.items())),
        "predicate_faults": sorted([x["key"], f["predicate"], f["error_class"]]
                                   for x in r.get("localizations", [])
                                   for f in x["predicate_faults"]),
        "abnormal": sorted(_ekey(e) for e in r["state"].get("abnormal", {})
                           .get("adverse_evidence", [])),
    }


def timeline(results) -> list:
    """Collapse a run of `AssuranceResult`s into intervals of unchanged state."""
    out, prev = [], None
    for res in results:
        r = _canon(res.to_dict())
        sig = signature(r)
        if prev is not None and sig == prev:
            cur = out[-1]
            cur["to"] = r["event_time"]
            cur["ticks"] += 1
            continue
        changed = (sorted(k for k in sig if prev is None or sig[k] != prev[k])
                   if prev is not None else ["start"])
        out.append({"from": r["event_time"], "to": r["event_time"], "ticks": 1,
                    "changed": changed, "result": r})
        prev = sig
    return out


def machine_report(results, inputs: dict, gate, contracts: dict) -> dict:
    results = list(results)
    tl = timeline(results)
    final = _canon(results[-1].to_dict()) if results else None
    return {
        "schema": SCHEMA,
        "analyzer_version": ANALYZER_VERSION,
        "semantic_version": final["semantic_version"] if final else None,
        "inputs": inputs,
        "profile_gate": gate.to_dict(),
        "contracts": {pid: {"producer_version": c.producer_version,
                            "contract_version": c.contract_version,
                            "digest": c.digest()} for pid, c in sorted(contracts.items())},
        "ticks": len(results),
        "intervals": len(tl),
        "timeline": tl,
        "final": final,
    }


# ------------------------------------------------------------------ human
def _fmt_t(x):
    return f"{x:.3f}s" if isinstance(x, (int, float)) else str(x)


def _short(evidence_id: str) -> str:
    """For the human report: `record@content time`. The producer is listed
    under PRODUCERS; the machine report keeps the full id."""
    parts = evidence_id.split("|")
    if len(parts) != 4:
        return evidence_id
    return f"{parts[2]}@{parts[3].rstrip('0').rstrip('.')}s"


def _ids(ids) -> str:
    return ", ".join(_short(i) for i in ids)


def _epoch(v):
    if isinstance(v, (list, tuple)) and len(v) == 1:
        return v[0]
    return v


def _loc_lines(loc) -> list:
    lines = [f"  {loc['symptom']} on {loc['subject']}: {loc['outcome']}"
             + (f" ({loc['outcome_reason']})" if loc.get("outcome_reason") else "")]
    if loc["candidates"]:
        lines.append(f"    remaining explanations: {', '.join(loc['candidates'])}")
    for e in loc["eliminated"]:
        lines.append(f"    eliminated: {e['hypothesis']} by {e['by']}")
    if loc["supporting_evidence"]:
        lines.append(f"    supporting evidence: {_ids(loc['supporting_evidence'])}")
    if loc["refuting_evidence"]:
        lines.append(f"    refuting evidence: {_ids(loc['refuting_evidence'])}")
    for f in loc["predicate_faults"]:
        lines.append(f"    predicate fault: {f['predicate']} ({f['error_class']})")
    for w in loc["withheld_because"]:
        lines.append(f"    withheld: {w}")
    return lines


def human_report(m: dict) -> str:
    """The short text report for an engineer."""
    L = ["CSIA FLIGHT ASSURANCE ANALYZER (offboard; no flight-control authority)",
         f"analyzer {m['analyzer_version']}, semantics {m['semantic_version']}", ""]
    L.append("INPUTS")
    for k, v in sorted(m["inputs"].items()):
        L.append(f"  {k}: {v}")
    g = m["profile_gate"]
    L += ["", f"PROFILE  {g['profile'].get('name')} ({g['status']})"]
    for f in g["findings"]:
        L.append(f"  {f['severity']} {f['rule']} {f['subject']}: {f['detail']}")
    L += ["", f"TIMELINE  {m['ticks']} ticks in {m['intervals']} intervals"]
    for iv in m["timeline"]:
        r = iv["result"]
        span = (_fmt_t(iv["from"]) if iv["ticks"] == 1
                else f"{_fmt_t(iv['from'])} .. {_fmt_t(iv['to'])} ({iv['ticks']} ticks)")
        rej = len(r["evidence"]["rejected"])
        L.append(f"  {span}: {r['state']['headline']}; "
                 f"{len(r['evidence']['used'])} used, {rej} rejected"
                 f"; changed: {', '.join(iv['changed'])}")
    f = m["final"]
    if f is None:
        return "\n".join(L) + "\n"
    L += ["", f"FINAL STATE at {_fmt_t(f['event_time'])}: {f['state']['headline']}"]
    ab = f["state"].get("abnormal", {})
    L.append("  what appears abnormal: "
             + (", ".join(ab.get("symptoms", [])) or "no symptom detected"))
    if ab.get("adverse_evidence"):
        L.append(f"  adverse evidence: {_ids(ab['adverse_evidence'])}")
    for loc in f["localizations"]:
        L += _loc_lines(loc)
    a = f.get("attribution") or {}
    if a:
        L.append(f"  attribution: {a.get('verdict')}"
                 + (f" -> {a['unique']}" if a.get("unique") else "")
                 + (f"; candidates {', '.join(a['candidates'])}" if a.get("candidates") else ""))
        for w in a.get("withheld_unique_because", []):
            L.append(f"    UNIQUE withheld: {w}")
        for n in a.get("exclusion_shares_lineage_with_candidate", []):
            L.append(f"    INFO exclusion evidence {n['discriminator']} shares "
                     f"{', '.join(n['shares_roots_with_candidate'])} with the candidate")
    L += ["", "EVIDENCE REJECTED (not reasoned with)"]
    rej = f["evidence"]["rejected"]
    if not rej:
        L.append("  none")
    for x in rej:
        L.append(f"  {x['evidence_id']}: {x['status']} ({'; '.join(x['reasons'])})")
    for x in f["evidence"].get("admitted_with_warnings", []):
        L.append(f"  admitted with warning: {x['evidence_id']} ({'; '.join(x['warnings'])})")
    L += ["", "PRODUCERS"]
    for pid, p in f["producers"]["by_producer"].items():
        L.append(f"  {pid}: health {'/'.join(p['health'])}; {p['admitted']} of "
                 f"{p['evidence']} admitted"
                 + (f"; faults {', '.join(p['faults'])}" if p["faults"] else ""))
    for c in f["producers"]["coverage_gaps"]:
        L.append(f"  coverage: {c['producer_id']} has no evidence for {c['source']}: {c['why']}")
    L += ["", "DEPENDENCE (adverse evidence, by lineage)"]
    comp = f["corroboration"]["by_component"]
    ov = f["corroboration"]["overall"]
    if not comp:
        L.append("  no adverse evidence admitted")
    else:
        L.append(f"  all adverse evidence: {ov['adverse_evidence']} outputs in "
                 f"{len(ov['lineage_groups'])} lineage group(s), {ov['independent_lines']} "
                 f"independent line(s)" + ("" if ov["independent_lines_exact"]
                                           else " (lower bound)"))
        for g in ov["lineage_groups"]:
            if len(g) > 1:
                L.append(f"    one group: {_ids(g)}")
    for c in comp:
        L.append(f"  {c['component']}: {len(c['adverse_evidence'])} adverse outputs from "
                 f"{len(c['producers'])} producer(s), {c['independent_lines']} independent "
                 f"line(s)")
    cfg = f["configuration"]
    L += ["", "CONFIGURATION"]
    L.append("  epochs: " + (", ".join(f"{k}={_epoch(v)}" for k, v in sorted(cfg["epochs"].items()))
                             or "none given"))
    for k, ev in sorted(cfg.get("transition_events", {}).items()):
        L.append(f"  transition: {ev}")
    for e in cfg.get("not_admitted_by_epoch", []):
        L.append(f"  not admitted: {e['record']} from {e['source']} ({e['reason']} on "
                 f"{e['key']}: evidence {e['evidence_epoch']}, current {e['current_epoch']})")
    if f["profile_warnings"]:
        L += ["", "PROFILE WARNINGS"]
        L += [f"  {w}" for w in f["profile_warnings"]]
    return "\n".join(L) + "\n"
