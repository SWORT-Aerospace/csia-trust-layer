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

KEY MOMENTS (pilot, schema 2)
-----------------------------
The answers to the WHEN questions, computed once over the whole run:
- **first abnormal:** the first symptom or adverse evidence, and which
  producers saw it;
- **first observation by each producer;**
- **candidate changes:** every change of a localization's outcome or
  candidates, and of the attribution;
- **certainty:** when CSIA became certain (UNIQUE, or one explanation left)
  and when that certainty disappeared;
- **evidence invalidated:** the first time each output was STALE,
  CONFIGURATION_MISMATCH, REGIME_INVALID, DUPLICATE, CONTRACT_INVALID or
  PROFILE_MISMATCH;
- **producer health changes;**
- **configuration changes:** key, from, to, event;
- **predicate faults:** the first time each predicate failed.

MANIFEST
--------
`manifest(run, report_bytes)` records what is needed to reproduce a report:
- the input files and their SHA-256;
- the semantic and Analyzer versions;
- the profile;
- every producer's version and contract digest;
- the analysis configuration;
- a digest of the code (`csia_evidence_assurance`, `csia_semantic_core`);
- the report's own SHA-256.

It contains no absolute path and no time.

HUMAN REPORT
------------
Plain text, short, and only what the machine report says. There are no
probabilities or confidence percentages, because nothing in 2.1.1 or 2.2
computes one.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .analyzer import ANALYZER_VERSION

SCHEMA = "csia.flight_assurance_report/2"
MANIFEST_SCHEMA = "csia.analysis_manifest/1"
INVALIDATING = ("STALE", "CONFIGURATION_MISMATCH", "REGIME_INVALID", "DUPLICATE",
                "CONTRACT_INVALID", "PROFILE_MISMATCH")


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
    """Collapse a run of `AssuranceResult`s (or their canonical dicts) into
    intervals of unchanged state."""
    out, prev = [], None
    for res in results:
        r = res if isinstance(res, dict) else _canon(res.to_dict())
        sig = signature(r)
        if prev is not None and sig == prev:
            cur = out[-1]
            cur["to"] = r["event_time"]
            cur["ticks"] += 1
            continue
        changed = (sorted(k for k in sig if prev is None or sig[k] != prev[k])
                   if prev is not None else ["start"])
        out.append({"from": r["event_time"], "to": r["event_time"], "ticks": 1,
                    "changed": changed,
                    "configuration_changes": (r.get("configuration") or {}).get("changes", []),
                    "result": r})
        prev = sig
    return out


def _certain(r):
    """What CSIA is certain of at one tick: a UNIQUE attribution, or a
    localization with exactly one explanation left."""
    out = []
    a = r.get("attribution") or {}
    if a.get("verdict") == "UNIQUE":
        out.append(f"attribution UNIQUE {a.get('unique')}")
    for x in r.get("localizations", []):
        if x["outcome"] == "SUPPORTED" and len(x["candidates"]) == 1:
            out.append(f"{x['key']} SUPPORTED {x['candidates'][0]}")
    return sorted(out)


def key_moments(rs) -> dict:
    """`rs`: canonical result dicts, in order. See the module docstring."""
    first_abnormal, first_by_producer = None, {}
    cand_changes, certainty, invalidated, health, config, faults = [], [], {}, [], [], {}
    prev_loc, prev_attr, prev_cert, prev_health = {}, None, [], {}
    for r in rs:
        t = r["event_time"]
        ab = r["state"].get("abnormal", {})
        adverse = ab.get("adverse_evidence", [])
        for e in adverse:
            first_by_producer.setdefault(e.split("|", 1)[0], t)
        if first_abnormal is None and (ab.get("symptoms") or adverse):
            first_abnormal = {"t": t, "symptoms": ab.get("symptoms", []),
                              "adverse_evidence": adverse,
                              "observed_by": sorted({e.split("|", 1)[0] for e in adverse})}
        locs = {x["key"]: (x["outcome"], x["candidates"]) for x in r.get("localizations", [])}
        for k in sorted(set(locs) | set(prev_loc)):
            if locs.get(k) != prev_loc.get(k):
                cand_changes.append({"t": t, "what": k,
                                     "from": list(prev_loc[k]) if k in prev_loc else None,
                                     "to": list(locs[k]) if k in locs else None})
        a = r.get("attribution") or {}
        attr = [a.get("verdict"), a.get("candidates", [])]
        if prev_attr is not None and attr != prev_attr:
            cand_changes.append({"t": t, "what": "attribution", "from": prev_attr, "to": attr})
        cert = _certain(r)
        for c in cert:
            if c not in prev_cert:
                certainty.append({"t": t, "became_certain": c})
        for c in prev_cert:
            if c not in cert:
                certainty.append({"t": t, "certainty_lost": c})
        for x in r["evidence"].get("rejected", []):
            if x["status"] in INVALIDATING:
                invalidated.setdefault((x["status"], _ekey(x["evidence_id"])),
                                       {"t": t, "status": x["status"],
                                        "evidence": _ekey(x["evidence_id"]),
                                        "reason": x["reasons"][0]})
        hp = {p: v["health"] for p, v in (r.get("producers") or {}).get("by_producer", {}).items()}
        for p in sorted(set(hp) | set(prev_health)):
            if hp.get(p) != prev_health.get(p) and (p in prev_health or hp.get(p) != ["VALID"]):
                health.append({"t": t, "producer": p, "from": prev_health.get(p), "to": hp.get(p)})
        for c in (r.get("configuration") or {}).get("changes", []):
            config.append(dict(c, t=t))
        for x in r.get("localizations", []):
            for f in x["predicate_faults"]:
                faults.setdefault((x["key"], f["predicate"]),
                                  {"t": t, "localization": x["key"], "predicate": f["predicate"],
                                   "error_class": f["error_class"]})
        prev_loc, prev_attr, prev_cert, prev_health = locs, attr, cert, hp
    return {"first_abnormal": first_abnormal,
            "first_observation_by_producer": dict(sorted(first_by_producer.items())),
            "candidate_changes": cand_changes, "certainty": certainty,
            "evidence_invalidated": sorted(invalidated.values(), key=lambda d: (d["t"], d["evidence"])),
            "producer_health_changes": health, "configuration_changes": config,
            "predicate_faults": sorted(faults.values(), key=lambda d: (d["t"], d["localization"]))}


def coverage_summary(rs) -> list:
    """Every (producer, claim, record) seen, with how many ticks it spent in
    each coverage state over the run."""
    out: dict = {}
    for r in rs:
        for c in (r.get("producers") or {}).get("coverage", []):
            k = (c["producer_id"], c["claim"] or "", c["record"])
            d = out.setdefault(k, {})
            d[c["state"]] = d.get(c["state"], 0) + 1
    return [{"producer_id": p, "claim": c or None, "record": rec, "ticks_by_state": dict(sorted(v.items()))}
            for (p, c, rec), v in sorted(out.items())]


def machine_report(results, inputs: dict, gate, contracts: dict) -> dict:
    rs = [_canon(x.to_dict()) for x in results]
    tl = timeline(rs)
    final = rs[-1] if rs else None
    return {
        "schema": SCHEMA,
        "analyzer_version": ANALYZER_VERSION,
        "semantic_version": final["semantic_version"] if final else None,
        "inputs": inputs,
        "profile_gate": gate.to_dict(),
        "contracts": {pid: {"producer_version": c.producer_version,
                            "contract_version": c.contract_version,
                            "digest": c.digest()} for pid, c in sorted(contracts.items())},
        "ticks": len(rs),
        "intervals": len(tl),
        "key_moments": key_moments(rs),
        "coverage": coverage_summary(rs),
        "timeline": tl,
        "final": final,
    }


def _tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in (".py", ".json") and "__pycache__" not in p.parts:
            h.update(p.relative_to(root).as_posix().encode())
            h.update(hashlib.sha256(p.read_bytes()).hexdigest().encode())
    return h.hexdigest()


def code_digests() -> dict:
    pkg = Path(__file__).resolve().parent
    return {"csia_evidence_assurance": _tree_digest(pkg),
            "csia_semantic_core": _tree_digest(pkg.parent / "csia_semantic_core")}


def _files(x, out):
    if isinstance(x, dict):
        if "sha256" in x and ("file" in x or "name" in x):
            out.append({k: x[k] for k in ("file", "name", "extract", "sha256") if k in x})
        for v in x.values():
            _files(v, out)
    elif isinstance(x, list):
        for v in x:
            _files(v, out)
    return out


def manifest(m: dict, report_bytes: bytes, config: dict | None = None) -> dict:
    """The reproduction record for one machine report `m`."""
    inputs = m["inputs"]
    files = _files(inputs, [])
    for k, v in inputs.items():
        if k.endswith("sha256") and isinstance(v, str):
            files.append({"name": k[:-len("_sha256")], "sha256": v})
    return {"schema": MANIFEST_SCHEMA,
            "inputs": files,
            "semantic_version": m["semantic_version"],
            "analyzer_version": m["analyzer_version"],
            "report_schema": m["schema"],
            "profile": dict(m["profile_gate"]["profile"], gate=m["profile_gate"]["status"]),
            "producers": m["contracts"],
            "analysis_config": dict({k: v for k, v in inputs.items()
                                     if not isinstance(v, dict) and not k.endswith("sha256")},
                                    **(config or {})),
            "code": code_digests(),
            "report_sha256": hashlib.sha256(report_bytes).hexdigest()}


# ------------------------------------------------------------------ human
def _fmt_t(x):
    return f"{x:.3f}s" if isinstance(x, (int, float)) else str(x)


def _short(evidence_id: str) -> str:
    """For the human report: `record@content time [producer]`. The machine
    report keeps the full id."""
    parts = evidence_id.split("|")
    if len(parts) != 4:
        return evidence_id
    return f"{parts[2]}@{parts[3].rstrip('0').rstrip('.')}s [{parts[0]}]"


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
        refs = e.get("all_refuters") or [e["by"]]
        lines.append(f"    eliminated: {e['hypothesis']} by {', '.join(refs)}")
    basis = loc.get("evidence_basis", {})
    if loc["supporting_evidence"]:
        lines.append(f"    supporting evidence: {_ids(loc['supporting_evidence'])}")
        lines += [f"      rests on: {', '.join(basis.get(e, []))}" for e in loc["supporting_evidence"]
                  if basis.get(e)]
    if loc["refuting_evidence"]:
        lines.append(f"    refuting evidence: {_ids(loc['refuting_evidence'])}")
        lines += [f"      rests on: {', '.join(basis.get(e, []))}" for e in loc["refuting_evidence"]
                  if basis.get(e)]
    for kind in ("supporting_evidence", "refuting_evidence"):
        ev = [e for e in loc[kind] if basis.get(e)]
        if len(ev) > 1:
            shared = set(basis[ev[0]]).intersection(*(set(basis[e]) for e in ev[1:]))
            if shared:
                lines.append(f"    the {kind.split('_')[0]} evidence shares {', '.join(sorted(shared))}: "
                             f"it is not independent corroboration")
    for d in loc.get("would_discriminate", []):
        lines.append(f"    would discriminate, but could not be evaluated: {d['predicate']}"
                     + (f" ({d['description']})" if d.get("description") else ""))
    for f in loc["predicate_faults"]:
        lines.append(f"    predicate fault: {f['predicate']} ({f['error_class']})")
    for e in loc["fault_impact"]:
        lines.append(f"    fault impact: {e['hypothesis']} may rest on the failed "
                     f"{e['role'].lower()} {e['predicate']}")
    for w in loc["withheld_because"]:
        lines.append(f"    withheld: {w}")
    return lines


def _state_words(v) -> str:
    if v is None:
        return "none"
    verdict, cands = v
    return f"{verdict} [{', '.join(cands) or 'no candidate'}]"


def _key_moment_lines(k: dict) -> list:
    """Every key moment, in time order."""
    if not k:
        return []
    items = []
    fa = k.get("first_abnormal")
    if fa:
        items.append((fa["t"], 0, "FIRST ABNORMAL: " + (", ".join(fa["symptoms"]) or "adverse evidence only")
                      + (f"; observed by {', '.join(fa['observed_by'])}" if fa["observed_by"] else "")))
    for p, t in k.get("first_observation_by_producer", {}).items():
        items.append((t, 1, f"first adverse output from {p}"))
    for c in k.get("certainty", []):
        if "became_certain" in c:
            items.append((c["t"], 2, f"CERTAIN: {c['became_certain']}"))
        else:
            items.append((c["t"], 2, f"CERTAINTY LOST: {c['certainty_lost']}"))
    for c in k.get("candidate_changes", []):
        items.append((c["t"], 3, f"{c['what']}: {_state_words(c['from'])} -> {_state_words(c['to'])}"))
    for e in k.get("evidence_invalidated", []):
        items.append((e["t"], 4, f"first {e['status']}: {e['evidence']} ({e['reason']})"))
    for h in k.get("producer_health_changes", []):
        items.append((h["t"], 5, f"producer {h['producer']} health {h['from']} -> {h['to']}"))
    for c in k.get("configuration_changes", []):
        items.append((c["t"], 6, f"configuration: {c.get('event') or c['key']}"
                      + ("" if c.get("event") else f" {_epoch(c['from'])} -> {_epoch(c['to'])}")))
    for f in k.get("predicate_faults", []):
        items.append((f["t"], 7, f"predicate {f['predicate']} failed ({f['error_class']}) "
                                 f"in {f['localization']}"))
    L = ["", "KEY MOMENTS (in time order)"]
    if not fa:
        L.append("  nothing abnormal at any tick")
    for t, _o, text in sorted(items, key=lambda x: (x[0], x[1])):
        L.append(f"  {_fmt_t(t)}  {text}")
    return L


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
        for c in iv.get("configuration_changes", []):
            L.append(f"      configuration: {c['key']} {_epoch(c['from'])} -> {_epoch(c['to'])}"
                     + (f" ({c['event']})" if c.get("event") else ""))
    L += _key_moment_lines(m.get("key_moments") or {})
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
                 + (f"; candidates {', '.join(a['candidates'])}" if a.get("candidates") else "")
                 + (f" ({a['why']})" if a.get("why") else ""))
        if a.get("verdict") == "NO_EVIDENCE" and f["localizations"]:
            L.append("    (cross-domain attribution reads only attributable evidence; the "
                     "localizations above are the diagnosis)")
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
    L += ["", "COVERAGE OVER THE RUN (ticks in each state; NO_ANOMALY is a silent detector, "
              "not an observation of health)"]
    for c in m.get("coverage", []):
        states = ", ".join(f"{k} {v}" for k, v in c["ticks_by_state"].items())
        what = f"{c['record']}" + (f" [{c['claim']}]" if c["claim"] else "")
        L.append(f"  {c['producer_id']}: {what}: {states}")
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
