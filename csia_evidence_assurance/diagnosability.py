"""Structural diagnosability for one analysis (CSIA 2.3, Phase 24). OFFBOARD.

**The question.** Given the evidence a log can actually supply, which of a
symptom's explanations could ever be confirmed or eliminated, and which
evidence is missing for the rest?

**The method** is the fault-signature (isolability) analysis of structural
diagnosis. It is computed on Semantic Core 2.1.1's OWN symptom
specifications and predicate table, which are read and never changed:

1. **Observable evidence.** Build a probe index holding only the records the
   log's producers can emit, with the profile's declarations, once all
   NOMINAL and once all adverse.
2. **Raisable symptoms.** A symptom can be raised on a subject if its
   detector fires on the adverse probe.
3. **Evaluable predicates.** A predicate can be evaluated if it returns
   True or False (not None) on either probe.
4. **Each hypothesis:**
   - can be eliminated if one of its refuting predicates is evaluable;
   - can be confirmed if one of its confirming predicates is.
5. **Missing evidence.** For each predicate that cannot be evaluated, the
   single catalog records whose addition (NOMINAL) makes it evaluable.

**The floor.** The hypotheses that can never be eliminated form the honest
floor of the candidate set. With this evidence, no analysis can be more
specific than that.

This is a property of the evidence set, not of a flight. It holds for every
tick of the analysis.
"""

from __future__ import annotations

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState
from csia_semantic_core.index import SuccessorIndex

#: The adverse reason code a producer of each relation would report.
_ADVERSE_CODE = {"actuation.physical_response": "ACT_NO_PHYSICAL_RESPONSE",
                 "actuation.electrical_response": "ACT_NO_ELECTRICAL_RESPONSE",
                 "actuation.mechanical_response": "ACT_RESPONSE_LOW",
                 "actuation.command_path": "ACT_COMMAND_NOT_TRANSMITTED"}


def _split(key):
    comp, rel = key.split(":", 1)
    dom, cpt = comp.split("/", 1)
    return dom, cpt, rel


def _records(keys, decl, adverse):
    out = []
    for k in sorted(keys):
        dom, cpt, rel = _split(k)
        deps, fns = decl.get(f"{dom}/{cpt}", ((), ()))
        st = ObservationState.VIOLATED if adverse else ObservationState.NOMINAL
        codes = (_ADVERSE_CODE.get(rel, "PROBE_ADVERSE"),) if adverse else ()
        out.append(EvidenceRecord(domain=dom, component=cpt, relation=rel, source="probe",
                                  observation_state=st, applicability=Applicability.APPLICABLE,
                                  affected_functions=tuple(fns), reason_codes=codes,
                                  dependencies=tuple(deps)))
    return out


def _eval(pred, records, subject):
    try:
        v = pred(SuccessorIndex(records, tracing=False), subject)
    except Exception:          # noqa: BLE001 - a probe that raises is "not evaluable"
        return None
    return v if isinstance(v, bool) else None


def _evaluable(pred, keys, decl, subject):
    return any(_eval(pred, _records(keys, decl, adv), subject) is not None for adv in (False, True))


def analyze(core, sample_records, observable_keys, catalog_keys) -> dict:
    """`sample_records`: the profile's declaration tick (dependencies and
    functions per component). `observable_keys`: the record keys this log's
    producers can emit with a usable state. `catalog_keys`: every record the
    profile defines."""
    decl = {f"{r.domain}/{r.component}": (r.dependencies, r.affected_functions)
            for r in sample_records}
    obs = sorted(set(observable_keys) & set(catalog_keys))
    preds = core.predicates
    adverse = SuccessorIndex(_records(obs, decl, True), tracing=False)
    out = []
    for spec in core.symptoms:
        try:
            subjects = spec.detect(adverse)
        except Exception:      # noqa: BLE001
            subjects = ()
        if not subjects:
            out.append({"symptom": spec.symptom_id, "raisable": False,
                        "why": f"no observable record can raise it (reads {spec.evidence_relation})"})
            continue
        for subject in sorted(subjects):
            hyps = []
            for h in spec.hypotheses:
                row = {"hypothesis": h.hypothesis_id, "can_be_eliminated_by": [],
                       "can_be_confirmed_by": [], "missing_to_eliminate": {}}
                for pid in h.refuted_by:
                    if pid in preds and _evaluable(preds[pid], obs, decl, subject):
                        row["can_be_eliminated_by"].append(pid)
                    elif pid in preds:
                        need = [k for k in sorted(set(catalog_keys) - set(obs))
                                if _evaluable(preds[pid], obs + [k], decl, subject)]
                        row["missing_to_eliminate"][pid] = need or ["no single profile record"]
                for pid in h.confirmed_by:
                    if pid in preds and _evaluable(preds[pid], obs, decl, subject):
                        row["can_be_confirmed_by"].append(pid)
                hyps.append(row)
            floor = sorted(r["hypothesis"] for r in hyps if not r["can_be_eliminated_by"])
            out.append({"symptom": spec.symptom_id, "subject": subject, "raisable": True,
                        "hypotheses": hyps, "never_eliminable": floor,
                        "distinguishable": [r["hypothesis"] for r in hyps if r["can_be_eliminated_by"]]})
    return {"observable_profile_records": obs, "symptoms": out}
