"""Deterministic plugin registry — §21.

Rejects duplicate ids and unsupported schema versions, and keeps registration
order out of the answer: `domains()` returns them sorted by `domain_id`, so
two hosts that registered the same plugins in different orders produce the
same evidence sequence and the same ledger.
"""

from __future__ import annotations

from .domain import DOMAIN_IDS, AssuranceDomain

#: Core contract version. A plugin declaring a different MAJOR is refused —
#: §21 says unsupported versions are rejected, and a plugin written against a
#: different contract is exactly what "unsupported" means.
CORE_SCHEMA_MAJOR = "2"


class PluginRejected(ValueError):
    """A plugin the registry will not accept. Never downgraded to a warning:
    a silently dropped domain is a domain whose evidence stops appearing
    while everything still looks like it is working."""


class DomainRegistry:
    def __init__(self):
        self._by_id: dict = {}

    def register(self, domain: AssuranceDomain) -> AssuranceDomain:
        did = getattr(domain, "domain_id", "")
        if not did:
            raise PluginRejected(f"{type(domain).__name__} declares no "
                                 f"domain_id")
        if did not in DOMAIN_IDS:
            raise PluginRejected(
                f"unknown domain_id {did!r}; the core knows {DOMAIN_IDS}. "
                f"Adding a domain is a deliberate change to the core "
                f"contract, not a plugin-side decision.")
        if did in self._by_id:
            raise PluginRejected(
                f"duplicate domain_id {did!r}: already registered by "
                f"{type(self._by_id[did]).__name__}")
        version = str(getattr(domain, "schema_version", ""))
        if version.split(".")[0] != CORE_SCHEMA_MAJOR:
            raise PluginRejected(
                f"{did} declares schema_version {version!r}; this core "
                f"supports major {CORE_SCHEMA_MAJOR}. Refusing rather than "
                f"interpreting evidence written against another contract.")
        if not domain.relations:
            raise PluginRejected(f"{did} declares no relations")
        if not domain.affected_functions:
            raise PluginRejected(f"{did} declares no affected_functions")
        self._by_id[did] = domain
        return domain

    def domains(self) -> tuple:
        """Sorted by id, so registration order cannot change the answer."""
        return tuple(self._by_id[k] for k in sorted(self._by_id))

    def get(self, domain_id: str):
        return self._by_id.get(domain_id)

    def __contains__(self, domain_id) -> bool:
        return domain_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)

    def declarations(self) -> list:
        return [d.declaration() for d in self.domains()]

    def functions_covered(self) -> tuple:
        """Every function some registered domain can bear on.

        Read from `declaration()` rather than from the attribute, because a
        domain whose per-component specs name their own functions (compute
        processes do) covers more than its domain-wide default names.
        """
        out = set()
        for d in self.domains():
            out.update(d.declaration().get("affected_functions", ()))
        return tuple(sorted(out))
