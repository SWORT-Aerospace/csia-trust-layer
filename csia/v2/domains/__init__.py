"""The domain plugins built in the first v2 scope — §§26, 35.

    1. SENSOR / NAVIGATION   via the existing v1.1 wrapper   (§20)
    2. POWER                                                 (§4)
    3. COMPUTE                                               (§5)
    4. TIMING                                                (§6)
    5. COMMUNICATION                                         (§7)
    6. ACTUATION                                             (§8, the sixth)

The remaining domains named in §1 — FIRMWARE_CONFIGURATION, THERMAL,
ESTIMATOR, STORAGE, SECURITY_INTEGRITY — are **specified and not built**.
They have ids reserved in `csia.v2.domain.DOMAIN_IDS` and specs in
`engineering/v2/`, and each would be a new module here implementing the same
contract. Nothing in the framework needs to change to add one; that is the
claim the six built domains are here to test.

Each module is importable on its own and imports no other domain. A domain
that reached into another domain's module would be a cross-domain relation
written in the wrong place — those live in the relation table
(`csia.v2.attribution.CrossDomainRelation`) where they can be declared,
listed and reviewed.

WHY THE RE-EXPORTS ARE LAZY
---------------------------
They used to be plain imports, and a test that runs §37's motor test stand in
a fresh interpreter caught what that cost: importing ANY domain executed
`navigation.py`, which imports the v1.1 payload parser, which pulls in the
whole v1.1 stack. A bench with no sensors, no GNSS and no v1.1 was loading all
of it, purely for the convenience of a flat namespace here.

`__getattr__` (PEP 562) keeps `from csia.v2.domains import PowerAssuranceDomain`
working exactly as before while making `from csia.v2.domains.power import
PowerAssuranceDomain` genuinely standalone. Modularity that only holds at the
level of the source tree is not modularity.
"""

import importlib

#: Public name -> the module that defines it.
_EXPORTS = {
    "ActuationAssuranceDomain": "actuation",
    "ActuatorSpec": "actuation",
    "CommunicationAssuranceDomain": "communication",
    "LinkSpec": "communication",
    "ComputeAssuranceDomain": "compute",
    "ProcessSpec": "compute",
    "ResourceSpec": "compute",
    "NavigationAssuranceDomain": "navigation",
    "PowerAssuranceDomain": "power",
    "BatterySpec": "power",
    "RailSpec": "power",
    "LoadSpec": "power",
    "TimingAssuranceDomain": "timing",
    "ChannelSpec": "timing",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(f".{module}", __name__), name)


def __dir__():
    return sorted(set(__all__) | set(globals()))
