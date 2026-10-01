"""Dependence: which admitted evidence is NOT independent.

**What 2.1.1 already does.** Semantic Core 2.1.1 never counts confirmations.
A confirmer is True or not, whatever number of records made it so, and
attribution works per component (`DEPENDENCY_METADATA_PREVIEW.md` §1). So
three alarms on one IMU cannot be multiplied into certainty inside the
core, and 2.2 must not add any counting that would.

**What was missing** is the knowledge that apparently separate evidence is
one line, and the use of that knowledge wherever CSIA states corroboration.
2.2's policy, the simplest compatible with 2.1.1:

1. **Logical use is unchanged.** Every admitted record reaches the core.
2. **Republished duplicates are collapsed before the core.** That is the
   DUPLICATE status in `admissibility.py`.
3. **Corroboration is stated by lineage, never by count.** For every
   component with adverse admitted evidence, the result lists that evidence,
   its independence groups (the connected components of "shares a root"),
   and the number of independent lines (the largest set of that evidence no
   two of which share a root). A report never says "three monitors agree"
   when the three share a source.
4. **Independence-based strengthening is not introduced.** When a UNIQUE
   rests on cross-domain exclusion evidence that shares a root with the
   candidate's own adverse evidence, the result says so (INFO). The verdict
   is 2.1.1's, unchanged.
"""

from __future__ import annotations

from .lineage import independence_groups, independent_lines


def corroboration(envelopes) -> list:
    """`envelopes`: admitted envelopes. One entry per component with adverse
    evidence: the evidence, its lineage groups and independent lines."""
    by_comp: dict = {}
    for e in envelopes:
        if e.record.is_adverse:
            cid = f"{e.record.domain}/{e.record.component}"
            by_comp.setdefault(cid, []).append(e)
    out = []
    for cid in sorted(by_comp):
        es = sorted(by_comp[cid], key=lambda e: e.evidence_id)
        items = [(e.evidence_id, e.lineage) for e in es]
        n, exact = independent_lines(items)
        out.append({"component": cid,
                    "adverse_evidence": [e.evidence_id for e in es],
                    "producers": sorted({e.producer_id for e in es}),
                    "lineage_groups": independence_groups(items),
                    "independent_lines": n, "independent_lines_exact": exact})
    return out


def shared_roots(group, lineages) -> list:
    """The roots that tie a lineage group together: those held by at least
    two of its members. This is what an engineer needs to see to know why
    the members are not independent."""
    count: dict = {}
    for k in group:
        for r in lineages[k].roots:
            count[r] = count.get(r, 0) + 1
    return sorted(r for r, n in count.items() if n >= 2)


def overall(envelopes) -> dict:
    """Every adverse admitted envelope of the tick, grouped by lineage."""
    adverse = sorted((e for e in envelopes if e.record.is_adverse),
                     key=lambda e: e.evidence_id)
    items = [(e.evidence_id, e.lineage) for e in adverse]
    n, exact = independent_lines(items)
    groups = independence_groups(items)
    lins = dict(items)
    return {"adverse_evidence": len(adverse), "independent_lines": n,
            "independent_lines_exact": exact,
            "lineage_groups": groups,
            "group_shared_roots": [shared_roots(g, lins) for g in groups]}


def exclusion_independence(candidate_ids, discriminator_records, envelopes_by_record) -> list:
    """For a UNIQUE: the relevant cross-domain discriminators whose lineage
    shares a root with the candidate's own adverse evidence. Trace only."""
    cand = [e for e in envelopes_by_record.values()
            if f"{e.record.domain}/{e.record.component}" in candidate_ids
            and e.record.is_adverse]
    notes = []
    for rid in sorted(discriminator_records):
        d = envelopes_by_record.get(rid)
        if d is None:
            continue
        shared = sorted({r for c in cand for r in d.lineage.shared_with(c.lineage)})
        if shared:
            notes.append({"discriminator": rid, "shares_roots_with_candidate": shared})
    return notes
