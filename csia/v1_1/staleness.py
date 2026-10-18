"""Runtime stale-timeout derivation — Phase 4.5 §§5–7.

Phase 4's audit found the deployment defect this module closes: the frozen
core's `STALE_TIMEOUT_S` table has a producer rate baked into a constant,
while the adapter derives its `MaxAge` per platform from the channel contract.
Six of eight nodes disagree, and on PX4 the `motor_esc` disagreement is large
enough to withdraw the node's evidence for most of every publish period.

THE RULE, AND WHY IT INTRODUCES NO NEW NUMBER
---------------------------------------------
A node's evidence reaches the frozen core through `to_core_samples`, which
emits a sensor **only when every one of its required channels is usable**
(`csia/aircraft/adapters/base.py:300`). A channel is usable while its age is
within the adapter's `MaxAge`. So the node stops being emitted exactly when
its **slowest-permitted** required channel stops being usable:

    runtime_stale_timeout[node] = max over required channels of max_age[channel]

and `max_age` is the adapter's own derived table,
`MAX_AGE_MARGIN / declared_rate_hz` per platform, falling back to the hand
table and then to `DEFAULT_MAX_AGE`.

**There is no constant in this file.** `MAX_AGE_MARGIN = 5.0` is imported from
`csia/aircraft/adapters/base.py`, where it was already declared and already
justified ("a channel that has missed five consecutive publications is not
slightly old, it is gone"). §9 forbids inventing a multiplier after seeing a
result, and the way to make that impossible is to have no multiplier to
invent.

WHAT THE RULE ACTUALLY SAYS
---------------------------
"The runtime watchdog agrees with the adapter." A node's evidence is withdrawn
by the trust layer at the same moment the ingestion layer withdraws the
channel it depends on — instead of up to 4.9 s earlier, which is the bug.

DIRECTION OF RISK, STATED PLAINLY (§7)
--------------------------------------
Every derived timeout is **longer** than the frozen default on the six nodes
that disagree. A longer timeout cannot cause a false stale; it can delay
detection of a genuinely dead source. That is the direction that needs
controls, so `validation/v1_1/deployment/` measures both a NOMINAL-RATE
control and a HARD-DROPOUT control for every node, and this module is not
adopted anywhere on the strength of argument alone.

THE FROZEN CORE IS NOT TOUCHED. `OnlineTrustLayer` already accepts
`stale_timeout_s`; this module computes what to pass it.
"""

from __future__ import annotations

from ..aircraft.adapters.base import (DEFAULT_MAX_AGE, MAX_AGE_MARGIN,
                                      MaxAge, PlatformAdapter)
from ..aircraft.qualification import default_contract

#: Node -> the channels `to_core_samples` requires for it to be emitted.
#: Derived from `PlatformAdapter.CORE_MAP` rather than restated, so a change
#: to the map cannot leave this table behind.
#:
#: `baro.temp_c` is OPTIONAL to the core -- `to_core_samples` skips it rather
#: than withholding the sensor -- so it is excluded from the required set. A
#: node whose timeout was set by an optional channel would be tolerating a
#: gap that never actually blocks it.
OPTIONAL_CHANNELS = frozenset({"baro.temp_c"})

#: Nodes the frozen core scores. `vehicle_status` is carried through the
#: adapter but is not a trust node and has no watchdog entry.
_NON_SENSOR = frozenset({"vehicle_status"})


def required_channels(node: str) -> tuple:
    """The channels a node needs before the core sees it at all."""
    mapping = PlatformAdapter.CORE_MAP.get(node, {})
    return tuple(sorted(ch for ch in mapping.values()
                        if ch not in OPTIONAL_CHANNELS))


def channel_max_age(platform: str, contract=None) -> dict:
    """The adapter's own per-channel max age, without building an adapter.

    Mirrors `PlatformAdapter._derive_max_age` exactly: contract rate for this
    platform first, then the hand table, then `DEFAULT_MAX_AGE`. A test
    asserts this function and a live adapter agree on every channel, so the
    two cannot drift.
    """
    contract = contract or default_contract(platform)
    derived = dict(MaxAge)
    key = f"producer_{platform}"
    for channel, row in contract.channels.items():
        rate = (row.raw.get(key) or {}).get("rate_hz")
        if rate:
            derived[channel] = MAX_AGE_MARGIN / float(rate)
    return derived


def build_runtime_stale_timeouts(platform: str, contract=None) -> dict:
    """`{node: seconds}` for `OnlineTrustLayer(stale_timeout_s=...)`.

    Deterministic, source-grounded, and the single rule used by shadow
    deployment, deployment-equivalent replay and any future HIL runner.
    Callers pass the result in; nobody copies a number into a constructor.
    """
    ages = channel_max_age(platform, contract)
    out = {}
    for node in PlatformAdapter.CORE_MAP:
        if node in _NON_SENSOR:
            continue
        needed = required_channels(node)
        if not needed:
            continue
        out[node] = max(ages.get(ch, DEFAULT_MAX_AGE) for ch in needed)
    return out


def explain(platform: str, contract=None) -> list:
    """Per-node derivation, for the audit artifacts and the flight-log header.

    Returns the driving channel and its declared rate alongside the result, so
    a timeout in a flight record can be traced to the contract row that
    produced it rather than taken on trust.
    """
    contract = contract or default_contract(platform)
    ages = channel_max_age(platform, contract)
    key = f"producer_{platform}"
    rows = []
    for node, timeout in sorted(build_runtime_stale_timeouts(
            platform, contract).items()):
        needed = required_channels(node)
        driver = max(needed, key=lambda ch: ages.get(ch, DEFAULT_MAX_AGE))
        row = contract.channels.get(driver)
        rate = ((row.raw.get(key) or {}).get("rate_hz")
                if row is not None else None)
        rows.append({
            "node": node,
            "required_channels": list(needed),
            "driving_channel": driver,
            "declared_rate_hz": rate,
            "source": ("contract" if rate else
                       "MaxAge table" if driver in MaxAge else "DEFAULT"),
            "margin_periods": MAX_AGE_MARGIN,
            "runtime_stale_timeout_s": round(float(timeout), 6),
        })
    return rows
