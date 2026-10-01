"""Source lineage: which root information sources a piece of evidence
ultimately depends on.

The one failure this exists to prevent is FALSE INDEPENDENCE: three monitors
that all read IMU1 (a threshold, a CUSUM, a Kalman residual) presented as
three confirmations, when they are one. The shadow study's preview
(`research/csia_semantic_core_2_1_shadow/DEPENDENCY_METADATA_PREVIEW.md`)
showed that a set of root sources per output, and a disjointness test,
removed every false corroboration in its seven cases and kept the genuine
one.

A lineage is a small, sorted, hashable tuple of root ids, each
`kind:name`:

| kind | what it names | example |
|---|---|---|
| `sensor` | a physical sensor | `sensor:imu1` |
| `channel` | a telemetry or command channel that is its own source | `channel:esc_rpm.motor_0` |
| `model` | a model whose error would be shared by every output computed with it | `model:ekf2` |
| `calibration` | a calibration whose error would be shared | `calibration:imu1_bias` |

Nothing else is represented: no transformation chain, no parent ids, no
graph database. Two outputs are DEPENDENT when their lineages share a root.

Two numbers come out of a set of lineages:
- **independence groups**, the connected components of "shares a root",
  for display: everything that is tied together, directly or through a
  third output;
- **independent lines**, the largest number of outputs no two of which
  share a root: the shadow preview's `max_disjoint`, the definition that
  removed every false corroboration there and kept the genuine one. It is
  exact up to `EXACT_LIMIT` outputs; above that the group count, which can
  only under-count, is returned and marked as a lower bound.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

KINDS = ("sensor", "channel", "model", "calibration")
#: Bounded on purpose: lineage is a coarse dependence statement, not a
#: provenance record.
MAX_ROOTS = 16
#: Outputs above which `independent_lines` stops being exact.
EXACT_LIMIT = 16


class LineageError(ValueError):
    """A lineage that is empty, too large, or names an unknown kind."""


@dataclass(frozen=True)
class Lineage:
    roots: tuple

    @classmethod
    def of(cls, *roots) -> "Lineage":
        flat = []
        for r in roots:
            flat.extend(r if isinstance(r, (list, tuple, set, frozenset)) else [r])
        if not flat:
            raise LineageError("a lineage must name at least one root")
        out = set()
        for r in flat:
            if not isinstance(r, str) or ":" not in r:
                raise LineageError(f"root {r!r} is not kind:name")
            kind, _, name = r.partition(":")
            if kind not in KINDS or not name:
                raise LineageError(f"root {r!r}: kind must be one of {KINDS}")
            out.add(r)
        if len(out) > MAX_ROOTS:
            raise LineageError(f"more than {MAX_ROOTS} roots")
        return cls(tuple(sorted(out)))

    def overlaps(self, other: "Lineage") -> bool:
        return not set(self.roots).isdisjoint(other.roots)

    def shared_with(self, other: "Lineage") -> tuple:
        return tuple(sorted(set(self.roots) & set(other.roots)))

    def digest(self) -> str:
        return hashlib.sha256("|".join(self.roots).encode()).hexdigest()[:16]

    def to_list(self) -> list:
        return list(self.roots)


def independence_groups(items) -> list:
    """`items`: iterable of (key, Lineage). Returns the groups (lists of
    keys, sorted) of the connected components of "shares a root". Each group
    is one independent line of evidence at most."""
    items = sorted(items, key=lambda kv: kv[0])
    parent = {k: k for k, _ in items}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    by_root: dict = {}
    for k, lin in items:
        for r in lin.roots:
            if r in by_root:
                a, b = find(k), find(by_root[r])
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                by_root[r] = k
    groups: dict = {}
    for k, _ in items:
        groups.setdefault(find(k), []).append(k)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


def independent_lines(items) -> tuple:
    """`items`: iterable of (key, Lineage). -> (n, exact): the largest number
    of outputs no two of which share a root, and whether n is exact.

    Outputs with an identical lineage count once; the rest is a maximum
    independent set of the overlap graph, by branching on the output with
    the most overlaps (small inputs only, hence `EXACT_LIMIT`)."""
    lins = sorted({lin.roots for _k, lin in items})
    if len(lins) > EXACT_LIMIT:
        return len(independence_groups((i, Lineage(r)) for i, r in enumerate(lins))), False
    sets = [set(r) for r in lins]
    adj = {i: {j for j in range(len(sets)) if j != i and not sets[i].isdisjoint(sets[j])}
           for i in range(len(sets))}

    def mis(nodes: frozenset) -> int:
        if not nodes:
            return 0
        v = max(sorted(nodes), key=lambda i: len(adj[i] & nodes))
        if not adj[v] & nodes:
            return len(nodes)
        return max(mis(nodes - {v}), 1 + mis(nodes - {v} - adj[v]))

    return mis(frozenset(adj)), True
