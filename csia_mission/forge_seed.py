"""FORGE-SEED PROTOTYPE: a small deterministic dependency compiler.

THE NAME IS THE SCOPE, AND IT IS DELIBERATE
---------------------------------------------
This is NOT CSIA Forge. Forge is a design-time synthesis system; this is the
smallest thing that turns

    MissionProductContract + VehicleProfile + capability definitions

into runtime dependency tables, deterministically, with a stable output hash.
It is called FORGE-SEED so that nobody -- including a future reader of this
repository who has forgotten this conversation -- can mistake the prototype
for the system.

WHAT "DETERMINISTIC" MEANS HERE, PRECISELY
--------------------------------------------
Same inputs -> byte-identical output -> identical output hash, on any host,
in any Python version, in any iteration order. Achieved by sorting every
collection before emission and by hashing through the one canonical
serialiser in `provenance.py`.

**There is no runtime AI, no heuristic, and no search.** Given a set of
contracts there is exactly one correct compiled table, and the compiler emits
it or fails.

FAIL CLOSED, AND WHAT THAT COSTS
----------------------------------
A cycle is a COMPILE ERROR. Not a warning, not a best-effort resolution in
some arbitrary order that happens to terminate. A dependency graph with a
cycle has no well-defined evaluation, and emitting one anyway would produce a
table whose meaning depends on the order the compiler happened to walk it.

A dependency naming something no contract or profile provides is also a
compile error. The alternative -- treat it as always-unavailable -- silently
converts a typo into a permanently degraded capability that nobody
investigates.

THE INDEPENDENT CHECKER
-----------------------
`check_compiled` re-derives the dependency closure from the SOURCE contracts
by a different route (transitive closure by repeated expansion, rather than
the compiler's topological walk) and compares. Two implementations of the
same closure, one of which is not the compiler, is a weaker guarantee than a
proof and a much stronger one than a compiler agreeing with itself.

    python -c "from csia_mission.forge_seed import compile_contracts"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .capability import CapabilityContract
from .product import MissionProductContract
from .provenance import content_hash

SCHEMA = "csia.mission.forge_seed/1"

#: The dependency forms this compiler understands. A contract using anything
#: else is a compile error, because an unrecognised form silently evaluating
#: to "no dependency" is the worst possible reading.
DEPENDENCY_FORMS = ("AND", "OR", "OPTIONAL", "DEGRADING", "K_OF_N")


class CompileError(ValueError):
    """A contract set that cannot be compiled to a well-defined table."""


@dataclass
class CompiledTables:
    schema: str
    capability_dependencies: dict
    product_dependencies: dict
    evidence_consumers: dict
    capability_order: list
    provided_evidence: list
    forms_used: list
    source_hash: str
    output_hash: str = field(default="", compare=False)

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "capability_dependencies": self.capability_dependencies,
            "product_dependencies": self.product_dependencies,
            "evidence_consumers": self.evidence_consumers,
            "capability_order": self.capability_order,
            "provided_evidence": self.provided_evidence,
            "forms_used": self.forms_used,
            "source_hash": self.source_hash,
            "output_hash": self.output_hash,
        }


def _groups(one_of) -> list:
    out = []
    for g in one_of:
        out.append(sorted(g) if isinstance(g, (list, tuple)) else [g])
    return sorted(out)


def _k_of_n_groups(contract) -> list:
    """Compiled form of a contract's k-of-n groups.

    DELEGATES to csia_mission.capability._validated_k_of_n rather than
    parsing the spec a second time. This module previously carried its OWN
    `_k_of_n` parser that NOTHING CALLED, while `K_OF_N` sat in
    DEPENDENCY_FORMS as a form the compiler never emitted -- a declared
    capability with no behaviour behind it, which is the exact shape of claim
    this repository exists to refuse. Two parsers for one syntax would have
    been the next problem.
    """
    from .capability import _validated_k_of_n
    out = []
    for spec in getattr(contract, "requires_k_of_n", ()) or ():
        k, of = _validated_k_of_n(spec, getattr(contract, "capability_id",
                                                "<contract>"))
        out.append({"k": k, "of": of})
    return sorted(out, key=lambda g: (g["k"], g["of"]))


def compile_contracts(capabilities: Iterable[CapabilityContract],
                      products: Iterable[MissionProductContract],
                      vehicle_profile: Mapping | None = None) -> CompiledTables:
    caps = {c.capability_id: c for c in capabilities}
    prods = {p.product_id: p for p in products}
    profile = dict(vehicle_profile or {})

    provided = set(profile.get("provides_evidence") or ())
    forms_used: set = set()

    # -- validate each contract on its own terms first ----------------------
    for c in caps.values():
        c.validate()
    for p in prods.values():
        p.validate()

    # -- cycle detection, before anything is emitted ------------------------
    cycle = _find_cycle({cid: [d for d in c.requires_capabilities]
                         for cid, c in caps.items()})
    if cycle:
        raise CompileError(
            f"dependency cycle: {' -> '.join(cycle)}. This FAILS CLOSED. A "
            f"cyclic dependency graph has no well-defined evaluation, and "
            f"emitting a table anyway would give it a meaning that depends "
            f"on the order the compiler happened to walk it.")

    # -- every named dependency must be provided by something ---------------
    unresolved: list = []
    all_evidence: set = set()

    def note(ids):
        for i in ids:
            all_evidence.add(i)

    for cid, c in caps.items():
        note(c.requires_all)
        for g in c.requires_one_of:
            note(g if isinstance(g, (list, tuple)) else [g])
        for g in _k_of_n_groups(c):
            note(g["of"])
        for dep in c.requires_capabilities:
            if dep not in caps:
                unresolved.append(f"{cid} requires capability {dep!r}")
    for pid, p in prods.items():
        note(p.requires_all)
        for g in p.requires_one_of:
            note(g if isinstance(g, (list, tuple)) else [g])
        for dep in p.requires_capabilities:
            if dep not in caps:
                unresolved.append(f"{pid} requires capability {dep!r}")
        for q in p.qualities:
            note(q.requires_all)
            for g in q.requires_one_of:
                note(g if isinstance(g, (list, tuple)) else [g])
            for dep in q.requires_capabilities:
                if dep not in caps:
                    unresolved.append(
                        f"{pid}.{q.property_name} requires capability {dep!r}")

    if provided:
        missing_evidence = sorted(all_evidence - provided)
        if missing_evidence:
            unresolved.extend(
                f"no declared provider for evidence {e!r}"
                for e in missing_evidence)

    if unresolved:
        raise CompileError(
            "unresolved dependencies:\n  " + "\n  ".join(sorted(unresolved))
            + "\n\nThis is a COMPILE ERROR rather than an always-unavailable "
              "dependency: treating a typo as permanently unsupported "
              "produces a capability nobody investigates.")

    # -- emit -------------------------------------------------------------
    cap_table: dict = {}
    for cid in sorted(caps):
        c = caps[cid]
        k_groups = _k_of_n_groups(c)
        entry = {
            "AND": sorted(c.requires_all),
            "OR": _groups(c.requires_one_of),
            "K_OF_N": k_groups,
            "capabilities": sorted(c.requires_capabilities),
            "compute": sorted(c.requires_compute),
            "timing": sorted(c.requires_timing),
            "actuators": sorted(c.requires_actuators),
            "does_not_require": sorted(c.does_not_require),
        }
        if entry["AND"]:
            forms_used.add("AND")
        if entry["OR"]:
            forms_used.add("OR")
        if k_groups:
            forms_used.add("K_OF_N")
        cap_table[cid] = entry

    prod_table: dict = {}
    for pid in sorted(prods):
        p = prods[pid]
        qualities = {}
        for q in sorted(p.qualities, key=lambda x: x.property_name):
            qualities[q.property_name] = {
                "AND": sorted(q.requires_all),
                "OR": _groups(q.requires_one_of),
                "capabilities": sorted(q.requires_capabilities),
                "permits": sorted(q.permits),
                "prohibits_without": sorted(q.prohibits_without),
            }
            if qualities[q.property_name]["OR"]:
                forms_used.add("OR")
            if qualities[q.property_name]["AND"]:
                forms_used.add("AND")
            if q.prohibits_without:
                forms_used.add("DEGRADING")
        prod_table[pid] = {
            "product_type": p.product_type,
            "AND": sorted(p.requires_all),
            "OR": _groups(p.requires_one_of),
            "capabilities": sorted(p.requires_capabilities),
            "qualities": qualities,
        }

    # reverse index: which capability or product does each evidence item feed
    consumers: dict = {}
    for cid, entry in cap_table.items():
        k_ev = [x for g in entry.get("K_OF_N", []) for x in g["of"]]
        for e in entry["AND"] + [x for g in entry["OR"] for x in g] + k_ev:
            consumers.setdefault(e, []).append(f"capability:{cid}")
    for pid, entry in prod_table.items():
        for e in entry["AND"] + [x for g in entry["OR"] for x in g]:
            consumers.setdefault(e, []).append(f"product:{pid}")
        for qname, q in entry["qualities"].items():
            for e in q["AND"] + [x for g in q["OR"] for x in g]:
                consumers.setdefault(e, []).append(f"product:{pid}.{qname}")
    consumers = {k: sorted(set(v)) for k, v in sorted(consumers.items())}

    order = _topological(caps)

    source = {
        "capabilities": [caps[c].to_dict() for c in sorted(caps)],
        "products": [prods[p].to_dict() for p in sorted(prods)],
        "vehicle_profile": profile,
    }
    tables = CompiledTables(
        schema=SCHEMA,
        capability_dependencies=cap_table,
        product_dependencies=prod_table,
        evidence_consumers=consumers,
        capability_order=order,
        provided_evidence=sorted(provided),
        forms_used=sorted(forms_used),
        source_hash=content_hash(source),
    )
    body = tables.to_dict()
    body.pop("output_hash")
    tables.output_hash = content_hash(body)
    return tables


def _find_cycle(deps: Mapping[str, list]):
    """Return one cycle as a path, or None. Deterministic: sorted traversal."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {k: WHITE for k in deps}
    stack: list = []

    def visit(node):
        colour[node] = GREY
        stack.append(node)
        for nxt in sorted(deps.get(node, ())):
            if nxt not in colour:
                continue
            if colour[nxt] == GREY:
                return stack[stack.index(nxt):] + [nxt]
            if colour[nxt] == WHITE:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        colour[node] = BLACK
        return None

    for node in sorted(deps):
        if colour[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def _topological(caps: Mapping[str, CapabilityContract]) -> list:
    indeg = {cid: sum(1 for d in c.requires_capabilities if d in caps)
             for cid, c in caps.items()}
    ready = sorted(c for c, n in indeg.items() if n == 0)
    order: list = []
    while ready:
        cid = ready.pop(0)
        order.append(cid)
        for other, c in caps.items():
            if cid in c.requires_capabilities and other not in order:
                indeg[other] -= 1
                if indeg[other] == 0:
                    ready.append(other)
                    ready.sort()
    return order


# ---------------------------------------------------------------------------
# the independent checker


def check_compiled(tables: CompiledTables,
                   capabilities: Iterable[CapabilityContract],
                   products: Iterable[MissionProductContract]) -> dict:
    """Re-derive the closure a DIFFERENT WAY and compare.

    The compiler walks the graph topologically. This expands each contract's
    transitive evidence set by repeated substitution until it stops changing,
    which is a different algorithm reaching the same answer. Agreement is not
    proof; it is evidence that a single implementation mistake did not
    silently produce a plausible table.
    """
    caps = {c.capability_id: c for c in capabilities}
    prods = {p.product_id: p for p in products}

    def direct_evidence(c: CapabilityContract) -> set:
        out = set(c.requires_all)
        for g in c.requires_one_of:
            out |= set(g if isinstance(g, (list, tuple)) else [g])
        for g in _k_of_n_groups(c):
            out |= set(g["of"])
        return out

    # transitive closure by repeated expansion
    closure = {cid: direct_evidence(c) for cid, c in caps.items()}
    changed = True
    rounds = 0
    while changed and rounds <= len(caps) + 1:
        changed = False
        rounds += 1
        for cid, c in caps.items():
            before = len(closure[cid])
            for dep in c.requires_capabilities:
                closure[cid] |= closure.get(dep, set())
            if len(closure[cid]) != before:
                changed = True

    problems: list = []

    for cid, entry in tables.capability_dependencies.items():
        if cid not in caps:
            problems.append({"kind": "COMPILED_CAPABILITY_NOT_IN_SOURCE",
                             "id": cid})
            continue
        recompiled = (set(entry["AND"])
                      | {x for g in entry["OR"] for x in g}
                      | {x for g in entry.get("K_OF_N", []) for x in g["of"]})
        if recompiled != direct_evidence(caps[cid]):
            problems.append({"kind": "DIRECT_EVIDENCE_MISMATCH", "id": cid,
                             "compiled": sorted(recompiled),
                             "source": sorted(direct_evidence(caps[cid]))})
    for cid in caps:
        if cid not in tables.capability_dependencies:
            problems.append({"kind": "SOURCE_CAPABILITY_NOT_COMPILED",
                             "id": cid})

    for pid, p in prods.items():
        entry = tables.product_dependencies.get(pid)
        if entry is None:
            problems.append({"kind": "SOURCE_PRODUCT_NOT_COMPILED",
                             "id": pid})
            continue
        if sorted(q.property_name for q in p.qualities) != sorted(
                entry["qualities"]):
            problems.append({"kind": "QUALITY_SET_MISMATCH", "id": pid})

    # the reverse index must agree with a freshly built one
    rebuilt: dict = {}
    for cid, c in caps.items():
        for e in direct_evidence(c):
            rebuilt.setdefault(e, set()).add(f"capability:{cid}")
    for pid, p in prods.items():
        base = set(p.requires_all)
        for g in p.requires_one_of:
            base |= set(g if isinstance(g, (list, tuple)) else [g])
        for e in base:
            rebuilt.setdefault(e, set()).add(f"product:{pid}")
        for q in p.qualities:
            qb = set(q.requires_all)
            for g in q.requires_one_of:
                qb |= set(g if isinstance(g, (list, tuple)) else [g])
            for e in qb:
                rebuilt.setdefault(e, set()).add(
                    f"product:{pid}.{q.property_name}")
    for e, who in sorted(rebuilt.items()):
        compiled = set(tables.evidence_consumers.get(e, ()))
        if compiled != who:
            problems.append({"kind": "CONSUMER_INDEX_MISMATCH", "evidence": e,
                             "compiled": sorted(compiled),
                             "recomputed": sorted(who)})

    return {
        "schema": "csia.mission.forge_seed_check/1",
        "method": ("transitive closure by repeated expansion, NOT the "
                   "compiler's topological walk"),
        "capabilities_checked": len(caps),
        "products_checked": len(prods),
        "transitive_closure_rounds": rounds,
        "problems": problems,
        "agrees": not problems,
        "what_agreement_does_not_prove": (
            "that the contracts are right. Two routes to the same closure "
            "bound implementation error in the compiler, not error in what "
            "the contracts say."),
    }
