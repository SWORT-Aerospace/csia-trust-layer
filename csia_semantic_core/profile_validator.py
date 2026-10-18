"""Static profile validation: the checks the shadow study showed are worth
having, and no others.

2.1 reasons only as well as the dependency model it is given. The shadow
study found real gaps in the frozen profiles (G-1, G-2), and the adversarial
mutations in `research/csia_semantic_core_2_1_shadow/adversarial_profiles.py`
showed which profile mistakes change conclusions silently. Each rule below
exists because one of those produced a wrong, missing or silently dead
result. The study records which (`PROFILE_VALIDATOR_SPEC.md`), and
`tests/test_semantic_core_2_1_shadow.py` holds one failing profile per rule.

Input: one tick of evidence records, which carry the profile's declarations
(`domain`, `component`, `affected_functions`, `dependencies`), and the frozen
`FunctionGraph` whose table the declarations must agree with. The records'
observation states are not read, so any tick of a profile, nominal or not,
gives the same findings.

| rule | severity | what it catches |
|---|---|---|
| PV1 SUBJECT_WITHOUT_SERVING_COMPONENT | GAP | a function a scoped symptom can be raised on that nothing is declared to serve (G-1) |
| PV2 DEAD_SUPPORTING_DOMAIN | WARNING | a supporting or optional domain of a function that no record of that domain names, so the declaration can never act |
| PV3 UNWATCHED_DECLARATION | WARNING | a record naming a function whose table entry does not watch the record's domain: the function graph ignores it, while 2.1's subject scope may use it |
| PV4 DANGLING_DEPENDENCY | ERROR | a dependency on a component no record describes |
| PV5 DEPENDENCY_DOMAIN_MISMATCH | ERROR | a dependency naming a real component under the wrong domain |
| PV6 DEPENDENCY_CYCLE | ERROR | a dependency cycle; common-cause reasoning assumes the depends-on graph is acyclic |
| PV7 UNKNOWN_FUNCTION | ERROR | a record naming a function the function table does not define (a typo) |
| PV8 INCONSISTENT_COMPONENT_DEPENDENCIES | ERROR | records of one component declaring different dependency sets |
| PV9 PACING_INPUT_NOT_A_DEPENDENCY | ERROR | (2.1.1, R-2) a pacing input that is not a declared dependency of its component, or a pacing mode other than ALL or ANY. A pacing declaration says which EXISTING edge paces the output; it may not add an edge |

`severity` says how a deployment should treat a finding:
- ERROR: refuse the profile;
- WARNING: accept it with the finding recorded;
- GAP: accept it, knowing that 2.1 will report `scope_gaps` for that subject.

Nothing here edits a profile or changes a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from .predicates import SERVING_RELATIONS

ERROR, WARNING, GAP = "ERROR", "WARNING", "GAP"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    subject: str
    detail: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "severity": self.severity,
                "subject": self.subject, "detail": self.detail}


def _cid(r) -> str:
    return f"{r.domain}/{r.component}"


def watched_domains(fn) -> tuple:
    """The domains `FunctionGraph._one` looks at for this function. A
    redundant group lists `DOMAIN/component` members; their domains count."""
    return tuple(dict.fromkeys(
        tuple(fn.required_domains) + tuple(fn.supporting_domains)
        + tuple(m.partition("/")[0] for g in fn.redundant_groups for m in g)
        + tuple(fn.optional_domains)
        + tuple(d for _n, ds in fn.fallback_requirements for d in ds)))


def scoped_subjects(records) -> tuple:
    """The functions the 2.1 scoped POSITION_UNAVAILABLE detector can raise
    a symptom on: the v1.1 eligibility records of navigation and position
    functions (`predicates.position_detector`)."""
    out = set()
    for r in records:
        if r.relation != "v1_1.function_eligibility":
            continue
        _, _, name = r.component.partition(".")
        if name and ("NAVIGATION" in name or "POSITION" in name):
            out.add(name)
    return tuple(sorted(out))


def _cycles(graph) -> list:
    seen, stack, out = set(), [], []
    on = set()

    def visit(n):
        seen.add(n)
        stack.append(n)
        on.add(n)
        for m in sorted(graph.get(n, ())):
            if m in on:
                out.append(stack[stack.index(m):] + [m])
            elif m not in seen:
                visit(m)
        stack.pop()
        on.discard(n)

    for n in sorted(graph):
        if n not in seen:
            visit(n)
    return out


def validate_profile(records, functions, subjects=None, pacing=None) -> list:
    """-> a sorted list of `Finding`. `functions` is a frozen
    `FunctionGraph` (or anything with a `.functions` name -> SystemFunction
    mapping). `pacing` is a successor profile's `pacing_map()` (PV9)."""
    table = getattr(functions, "functions", functions)
    records = tuple(records)
    found: set = set()
    comps = {_cid(r) for r in records}
    by_name: dict = {}
    for r in records:
        by_name.setdefault(r.component, set()).add(r.domain)

    # PV7, PV3 -- what records say they serve
    naming: dict = {}
    unwatched: dict = {}
    for r in records:
        for f in r.affected_functions or ():
            naming.setdefault(f, set()).add(r.domain)
            if f not in table:
                found.add(Finding("PV7_UNKNOWN_FUNCTION", ERROR, _cid(r),
                                  f"names function {f!r}, which the function table "
                                  "does not define"))
                continue
            if r.domain not in watched_domains(table[f]):
                unwatched.setdefault(f"{_cid(r)} -> {f}", set()).add(r.relation)

    for subj, rels in sorted(unwatched.items()):
        serving = sorted(rels & set(SERVING_RELATIONS))
        dom, f = subj.split("/", 1)[0], subj.rsplit(" -> ", 1)[1]
        found.add(Finding(
            "PV3_UNWATCHED_DECLARATION", WARNING, subj,
            f"{dom} is not a domain {f} watches, so the function graph ignores "
            "this declaration"
            + (f"; {', '.join(serving)} is a serving relation, so 2.1's subject "
               "scope does use it" if serving else "")))

    # PV2 -- supporting / optional domains nobody names
    for name, fn in sorted(table.items()):
        silent = tuple(fn.supporting_domains) + tuple(fn.optional_domains)
        for d in dict.fromkeys(silent):
            if d not in naming.get(name, set()):
                found.add(Finding(
                    "PV2_DEAD_SUPPORTING_DOMAIN", WARNING, f"{name}:{d}",
                    f"{name} declares {d} a supporting/optional domain, but no {d} "
                    "record names it, so the declaration can never act"))

    # PV1 -- scoped subjects nothing serves
    serving: dict = {}
    for r in records:
        if r.relation in SERVING_RELATIONS:
            for f in r.affected_functions or ():
                serving.setdefault(f, set()).add(_cid(r))
    for s in (scoped_subjects(records) if subjects is None else subjects):
        if not serving.get(s):
            found.add(Finding(
                "PV1_SUBJECT_WITHOUT_SERVING_COMPONENT", GAP, s,
                f"no {'/'.join(SERVING_RELATIONS)} record names {s}; scoped "
                "predicates on it can only be UNKNOWN"))

    # PV4, PV5, PV8 -- dependency endpoints and consistency
    deps_by_comp: dict = {}
    for r in records:
        deps = tuple(r.dependencies or ())
        deps_by_comp.setdefault(_cid(r), set()).add(tuple(sorted(set(deps))))
        for d in deps:
            if d in comps:
                continue
            dom, _, name = d.partition("/")
            if name in by_name:
                found.add(Finding(
                    "PV5_DEPENDENCY_DOMAIN_MISMATCH", ERROR, f"{_cid(r)} -> {d}",
                    f"{name} exists, but as {sorted(by_name[name])}, not {dom}"))
            else:
                found.add(Finding("PV4_DANGLING_DEPENDENCY", ERROR, f"{_cid(r)} -> {d}",
                                  f"no record describes {d}"))
    for c, sets in sorted(deps_by_comp.items()):
        if len(sets) > 1:
            found.add(Finding(
                "PV8_INCONSISTENT_COMPONENT_DEPENDENCIES", ERROR, c,
                "its records declare different dependency sets: "
                + " | ".join(",".join(s) or "-" for s in sorted(sets))))

    # PV6 -- cycles
    graph: dict = {}
    for r in records:
        graph.setdefault(_cid(r), set()).update(r.dependencies or ())
    for cyc in _cycles(graph):
        found.add(Finding("PV6_DEPENDENCY_CYCLE", ERROR, " -> ".join(cyc),
                          "dependency cycle"))

    # PV9 -- pacing inputs must be existing edges
    deps_of: dict = {}
    for r in records:
        deps_of.setdefault(r.component, set()).update(r.dependencies or ())
    for comp, (mode, inputs) in sorted((pacing or {}).items()):
        if mode not in ("ALL", "ANY"):
            found.add(Finding("PV9_PACING_INPUT_NOT_A_DEPENDENCY", ERROR, comp,
                              f"pacing mode {mode!r} is not ALL or ANY"))
        for i in inputs:
            if i not in deps_of.get(comp, set()):
                found.add(Finding(
                    "PV9_PACING_INPUT_NOT_A_DEPENDENCY", ERROR, f"{comp} <- {i}",
                    f"{i} is declared to pace {comp}, but it is not a declared "
                    f"dependency of {comp}"
                    + ("" if comp in deps_of else "; no record describes " + comp)))
    return sorted(found, key=lambda f: (f.rule, f.subject))
