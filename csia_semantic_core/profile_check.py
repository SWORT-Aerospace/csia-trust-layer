"""Declared-scope report: the profile gaps C3 makes visible.

C3 reads, for a function, only what the profile declares serves it. Where a
profile declares nothing, a scoped predicate is None. That is a gap in the
profile's declarations, not something the reasoning created. This module
lists those gaps from one tick of records. It changes no profile and no
outcome.

The three kinds of gap the semantic correctness audit named (SC-18):

| id | what it detects |
|---|---|
| G-1 | a function that no timing channel, process or link declares it serves |
| G-2 | a process with no declared COMMUNICATION dependency, so no input link |
| G-3 | a link or source a function's serving closure reaches through `dependencies`, whose own records do not name that function in `affected_functions` |
"""

from __future__ import annotations

from .index import SuccessorIndex
from .predicates import SERVING_RELATIONS, declared_scope

_FAMILIES = {"timing.end_to_end": "timing_channels",
             "compute.process_alive": "processes",
             "compute.process_producing": "processes",
             "compute.deadline_met": "processes",
             "comm.link_state": "links"}


def scope_report(records, functions) -> dict:
    index = SuccessorIndex(records, tracing=False)
    per_function = {}
    for fn in sorted(functions):
        serving: dict = {"timing_channels": set(), "processes": set(),
                         "links": set()}
        for r in index.records:
            if r.relation in SERVING_RELATIONS and fn in r.affected_functions:
                serving[_FAMILIES[r.relation]].add(r.component)
        closure = sorted(declared_scope(index, fn) - {fn})
        gaps = []
        if not any(serving.values()):
            gaps.append("G-1")
        g3 = sorted({r.component for r in index.records
                     if r.component in closure
                     and r.domain in ("COMMUNICATION", "SENSOR")
                     and r.affected_functions
                     and fn not in r.affected_functions})
        if g3:
            gaps.append("G-3")
        per_function[fn] = {
            **{k: sorted(v) for k, v in serving.items()},
            "closure": closure, "gaps": gaps,
            "g3_components": g3}
    procs = sorted({r.component for r in index.records
                    if r.relation.startswith("compute.process_")})
    no_link = [p for p in procs
               if not any(d.startswith("COMMUNICATION/")
                          for d in index.dependencies_of(p))]
    return {"functions": per_function,
            "processes_without_declared_input_link": no_link,
            "gap_summary": {
                "G-1": [f for f, v in per_function.items() if "G-1" in v["gaps"]],
                "G-2": no_link,
                "G-3": [f for f, v in per_function.items() if "G-3" in v["gaps"]]}}
