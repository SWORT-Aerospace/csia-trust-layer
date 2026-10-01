"""The CSIA Flight Assurance Analyzer: evidence in, auditable assurance out.

OFFBOARD ONLY: SITL, HIL, flight test, post-flight analysis and integration
debugging. Nothing here has, or may be given, flight-control authority.

ONE TICK
--------
1. **Hold.** The latest output of each producer claim is kept. A SNAPSHOT
   producer's output is valid only for the tick it was produced. A
   SAMPLE_AND_HOLD producer's output stands until replaced. That is how
   latched and slow evidence reach a real reasoner, and why staleness has to
   be decided.
2. **Admit** (`admissibility.assess`): every held envelope gets a status;
   rejected evidence is withheld as 2.1.1's R-3 withholds it.
3. **Reason** with Semantic Core 2.1.1 (`Corrections.revised()`, the gated
   successor profile, its pacing map), on the admitted records and the
   current configuration epochs.
4. **Explain** (`AssuranceResult`):
   - what appears abnormal;
   - which explanations remain, and which were eliminated and by what;
   - the evidence used and rejected, and why;
   - producer health and coverage;
   - configuration epochs;
   - lineage groups;
   - profile warnings;
   - the reason trace.

The semantic verdicts are 2.1.1's. The Analyzer never changes one; it can
only decide what evidence reaches the core, and say so.

COVERAGE STATES (pilot, 2.2.1)
------------------------------
`producers.coverage` gives every held output one state, never collapsed:

| state | meaning |
|---|---|
| NOMINAL | admitted; a check with the power to see the condition passed |
| NO_ANOMALY | admitted; a detector stayed silent (the contract's `nominal_means`), which is not an observation of health |
| ANOMALY | admitted and adverse |
| NOT_APPLICABLE | admitted; nothing to look at in this configuration |
| UNAVAILABLE | the producer or the record could not look |
| FAULTED | the producer failed |
| REJECTED:<status> | not admitted for another reason |
| NO_COVERAGE | (from the producers' coverage notices) the producer cannot observe this source at all |
"""

from __future__ import annotations

from dataclasses import dataclass

from . import dependence as D
from .admissibility import ADMISSIBLE, AnalysisContext, assess
from .envelope import record_key
from .health import ProducerHealth

ANALYZER_VERSION = "2.2.1"
PROFILE_REFUSED = "PROFILE_REFUSED"


def _r6(x):
    return None if x is None else round(float(x), 6)


def _headline(locs, verdict) -> str:
    """One line: each localization's outcome and remaining explanations,
    then the cross-domain attribution verdict."""
    parts = [f"{x['symptom']}|{x['subject']} {x['outcome']}: "
             f"{', '.join(x['candidates']) or 'no explanation remains'}" for x in locs]
    return "; ".join(parts + [f"attribution {verdict}"]) if parts else (
        f"no symptom; attribution {verdict}")


@dataclass(frozen=True)
class AssuranceResult:
    """One tick's product-level result. `to_dict()` is the machine form."""

    event_time: float
    semantic_version: str
    analyzer_version: str
    profile: dict
    state: dict
    localizations: tuple
    attribution: dict
    evidence: dict
    producers: dict
    corroboration: dict
    configuration: dict
    profile_warnings: tuple
    reason_trace: dict

    def to_dict(self) -> dict:
        return {"event_time": _r6(self.event_time),
                "semantic_version": self.semantic_version,
                "analyzer_version": self.analyzer_version,
                "profile": self.profile, "state": self.state,
                "localizations": list(self.localizations),
                "attribution": self.attribution, "evidence": self.evidence,
                "producers": self.producers, "corroboration": self.corroboration,
                "configuration": self.configuration,
                "profile_warnings": list(self.profile_warnings),
                "reason_trace": self.reason_trace}


class FlightAssuranceAnalyzer:
    """Configured once for one platform: a Semantic Core 2.1.1 instance, the
    producers' contracts, and the gated profile."""

    def __init__(self, core, contracts: dict, gate_result, profile_base: str):
        self.core = core
        self.contracts = dict(contracts)
        self.gate = gate_result
        self.profile_base = profile_base
        self.store: dict = {}
        #: The raw 2.1.1 TickResult of the latest step, for harnesses that
        #: grade it with the historical graders.
        self.last_tick = None
        self._last_epochs: dict = {}
        self.specs = {s.symptom_id: s for s in core.symptoms}

    # ------------------------------------------------------------- hold
    def _hold(self, envelopes):
        for k in [k for k, e in self.store.items()
                  if self._mode(e.producer_id) == "SNAPSHOT"]:
            del self.store[k]
        for e in envelopes:
            self.store[e.key] = e
        return list(self.store.values())

    def _mode(self, producer_id):
        c = self.contracts.get(producer_id)
        return c.update_mode if c is not None else "SNAPSHOT"

    # ------------------------------------------------------------- step
    def step(self, t, envelopes, epochs=None, events=None, coverage=()):
        held = self._hold(envelopes)
        profile = dict(self.gate.profile, gate=self.gate.status)
        warnings = tuple(f"{s}:{r}:{sub}" for s, r, sub, _d in self.gate.warnings())
        if not self.gate.accepted:
            return AssuranceResult(
                t, "none", ANALYZER_VERSION, profile,
                {"headline": PROFILE_REFUSED, "attribution": PROFILE_REFUSED},
                (), {}, {"used": [], "rejected": []}, {}, {}, {}, warnings,
                {"why": "the profile failed its load gate; nothing was reasoned"})
        ctx = AnalysisContext(t, self.profile_base, epochs, dict(events or {}))
        a = assess(held, self.contracts, ctx)
        tr = self.core.reason(a.records, a.epochs)
        self.last_tick = tr
        envs = {e.evidence_id: e for e in held}
        admitted = [envs[x.evidence_id] for x in a.admissions if x.status == ADMISSIBLE]
        by_record: dict = {}
        for e in admitted:
            by_record.setdefault(record_key(e.record), []).append(e.evidence_id)
        lineage = {e.evidence_id: e.lineage.to_list() for e in admitted}
        locs = tuple(self._loc(x, by_record, lineage) for x in tr.localizations)
        attr = self._attr(tr.attribution, admitted)
        rejected = [x.to_dict() for x in a.admissions if x.status != ADMISSIBLE]
        warned = [x.to_dict() for x in a.admissions
                  if x.status == ADMISSIBLE and x.warnings]
        producers = self._producers(held, a, coverage)
        producers["coverage"] = self._coverage(held, a, coverage)
        outcomes: dict = {}
        for x in locs:
            outcomes[x["outcome"]] = outcomes.get(x["outcome"], 0) + 1
        adverse = sorted(e.evidence_id for e in admitted if e.record.is_adverse)
        state = {"headline": _headline(locs, attr["verdict"]),
                 "attribution": attr["verdict"],
                 "abnormal": {"symptoms": [f"{x['symptom']}|{x['subject']}" for x in locs],
                              "adverse_evidence": adverse},
                 "localization_outcomes": dict(sorted(outcomes.items()))}
        adm = tr.admission or {}
        now = {k: list(v) if isinstance(v, (list, tuple)) else v
               for k, v in (adm.get("context_epochs") or {}).items()}
        changes = [{"key": k, "from": self._last_epochs.get(k), "to": v,
                    "event": (adm.get("transition_events") or {}).get(k)}
                   for k, v in sorted(now.items())
                   if k in self._last_epochs and self._last_epochs[k] != v]
        self._last_epochs = now
        configuration = {"epochs": adm.get("context_epochs", {}),
                         "changes": changes,
                         "transition_events": adm.get("transition_events", {}),
                         "keys_with_context_behind": adm.get("keys_with_context_behind", []),
                         "not_admitted_by_epoch": [
                             {k: e[k] for k in ("record", "source", "key", "evidence_epoch",
                                                "current_epoch", "reason", "action")}
                             for e in adm.get("inadmissible", [])]}
        trace = {"localizations": {x["key"]: x["why"] for x in locs},
                 "attribution": attr["why"]}
        return AssuranceResult(
            t, tr.semantics_version, ANALYZER_VERSION,
            dict(profile, pacing_digest=tr.pacing_digest), state, locs, attr,
            {"used": sorted(e.evidence_id for e in admitted), "rejected": rejected,
             "admitted_with_warnings": warned},
            producers,
            {"by_component": D.corroboration(admitted), "overall": D.overall(admitted)},
            configuration, warnings, trace)

    # ------------------------------------------------------------- parts
    def _evidence_of(self, pred_trace, by_record):
        ids = []
        for rid in sorted((pred_trace or {}).get("read", {})):
            ids.extend(by_record.get(rid, []))
        return sorted(set(ids))

    def _loc(self, x, by_record, lineage):
        spec = self.specs.get(x.symptom)
        preds = x.trace.get("predicates", {})
        vals = x.v2.detail.get("predicate_values", {})
        supporting, refuting = set(), set()
        refuters = {}
        if spec is not None:
            hyps = {h.hypothesis_id: h for h in spec.hypotheses}
            for h in spec.hypotheses:
                if h.hypothesis_id in x.supported:
                    for p in h.confirmed_by:
                        if vals.get(p) is True:
                            supporting.update(self._evidence_of(preds.get(p), by_record))
            for hid, by in x.v2.rejected:
                # every refuter that held, not only the one 2.1.1 names first
                h = hyps.get(hid)
                true = [p for p in (h.refuted_by if h else (by,)) if vals.get(p) is True] or [by]
                refuters[hid] = true
                for p in true:
                    refuting.update(self._evidence_of(preds.get(p), by_record))
        return {"key": x.key, "symptom": x.symptom, "subject": x.subject,
                "outcome": x.outcome, "outcome_reason": x.outcome_reason,
                "evaluation": x.evaluation,
                "candidates": sorted(set(x.supported) | set(x.unresolved)),
                "supported": list(x.supported), "unresolved": list(x.unresolved),
                "eliminated": [{"hypothesis": h, "by": p, "all_refuters": refuters.get(h, [p])}
                               for h, p in x.v2.rejected],
                "supporting_evidence": sorted(supporting),
                "refuting_evidence": sorted(refuting),
                "evidence_unavailable": list(x.evidence_unavailable),
                "evidence_basis": {eid: lineage.get(eid, []) for eid in sorted(supporting | refuting)},
                "would_discriminate": self._discriminators(x),
                "scope_gaps": list(x.trace.get("scope_gaps", [])),
                "predicate_faults": [{"predicate": e.predicate, "error_class": e.error_class}
                                     for e in x.predicate_errors],
                "fault_impact": [e for e in x.fault_impact if e["dependency"] == "MATERIAL"],
                "withheld_because": list(x.trace.get("withheld_because", [])),
                "why": x.trace.get("why")}

    def _discriminators(self, x):
        """For a localization with more than one explanation left: the
        predicates that could not be evaluated, i.e. the evidence that would
        have discriminated, with 2.1.1's own description of each."""
        if len(set(x.supported) | set(x.unresolved)) < 2:
            return []
        table = self.core.predicates
        ids = set(x.evidence_unavailable)
        base = sorted(p for p in ids if not (p.endswith("_FALSE") and p[:-6] in ids))
        return [{"predicate": p, "description": getattr(table.get(p), "description", "")}
                for p in base]

    def _coverage(self, held, a, notices):
        stat = {x.evidence_id: x for x in a.admissions}
        out = []
        for e in sorted(held, key=lambda e: e.evidence_id):
            x = stat[e.evidence_id]
            st = e.record.observation_state.value
            if x.status == ADMISSIBLE:
                if e.record.is_adverse:
                    state = "ANOMALY"
                elif st == "NOMINAL":
                    c = self.contracts.get(e.producer_id)
                    spec = c.claims.get(e.claim) if c else None
                    state = spec.nominal_means if spec else "NOMINAL"
                else:
                    state = st            # NOT_APPLICABLE or UNAVAILABLE
            elif e.producer_health in (ProducerHealth.FAULTED,) or any(
                    "FAULTED" in r for r in x.reasons):
                state = "FAULTED"
            elif e.producer_health is ProducerHealth.UNAVAILABLE:
                state = "UNAVAILABLE"
            else:
                state = f"REJECTED:{x.status}"
            out.append({"producer_id": e.producer_id, "claim": e.claim,
                        "record": record_key(e.record), "state": state})
        for c in sorted(notices, key=lambda c: (c["producer_id"], c["source"])):
            out.append({"producer_id": c["producer_id"], "claim": None,
                        "record": c["source"], "state": "NO_COVERAGE"})
        return out

    def _attr(self, at, admitted):
        t = at.trace
        unique = at.candidates[0] if at.verdict == "UNIQUE" else None
        out = {"verdict": at.verdict, "candidates": list(at.candidates),
               "unique": unique,
               "withheld_unique_because": list(at.withheld_unique_because),
               "retained_by_localization": t.get("localization_disagreement", []),
               "unexcluded_alternatives": t.get("unexcluded_alternatives", []),
               "relevant_discriminators": t.get("relevant_discriminators", []),
               "why": t.get("why")}
        if unique is not None:
            by_rec = {record_key(e.record): e for e in admitted}
            disc = set(t.get("relevant_discriminators", []))
            out["exclusion_shares_lineage_with_candidate"] = D.exclusion_independence(
                {unique}, disc, by_rec)
        return out

    def _producers(self, held, a, coverage):
        out: dict = {}
        stat = {x.evidence_id: x.status for x in a.admissions}
        for e in sorted(held, key=lambda e: e.evidence_id):
            p = out.setdefault(e.producer_id, {"health": set(), "evidence": 0,
                                               "admitted": 0, "rejected": {},
                                               "faults": []})
            p["health"].add(e.producer_health.value)
            p["evidence"] += 1
            s = stat[e.evidence_id]
            if s == ADMISSIBLE:
                p["admitted"] += 1
            else:
                p["rejected"][s] = p["rejected"].get(s, 0) + 1
        for pid, f in a.producer_faults.items():
            out.setdefault(pid, {"health": set(), "evidence": 0, "admitted": 0,
                                 "rejected": {}, "faults": []})["faults"].extend(f)
            out[pid]["health"].add(ProducerHealth.FAULTED.value)
        for p in out.values():
            p["health"] = sorted(p["health"])
            p["rejected"] = dict(sorted(p["rejected"].items()))
            p["faults"] = sorted(set(p["faults"]))
        cov = [dict(c) for c in sorted(coverage, key=lambda c: (c["producer_id"], c["source"]))]
        return {"by_producer": dict(sorted(out.items())), "coverage_gaps": cov}
