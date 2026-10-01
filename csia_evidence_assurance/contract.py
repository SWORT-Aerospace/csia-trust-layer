"""Producer contracts: what CSIA must know to interpret a producer safely.

A contract is a small versioned JSON file in `contracts/`. It is not a
formal-verification language and not a general schema framework: it states
only what admissibility and the report need.

| field | needed for |
|---|---|
| `producer_id`, `producer_version`, `contract_version` | refusing output of another version (L9) |
| `claims` | the claims the producer may make, each with its meaning and the 2.1.1 record it maps to (domain, relation, attributable). An undeclared claim is refused (L6) |
| `lineage` | the declared root sources, or `PER_OUTPUT` when each output names its own |
| `update` | `SNAPSHOT` (valid only for the tick it was produced) or `SAMPLE_AND_HOLD` (the latest output stands until replaced), and the period |
| `validity` | how long or where its content is valid: `max_content_age_s`, or an `event_window_s` relative to a named event. Only the rule actually validated for this producer is declared (XSYS: the fixed T1 window, not a compensation-state rule) |
| `config_dependency` | per claim (or a contract default): the configuration-epoch keys the claim depends on. An output without them is refused |
| `health_reporting` | `REPORTED` (health is part of each output) or `IN_PROCESS` (a frozen in-process plugin) |
| `profile_compatibility` | the base profiles the claims were declared against |
| `expected_inputs`, `fault_behavior` | documentation for the engineer; not read by the runtime |

**Deferred:** `operating_regimes` (hover, cruise, ...). No producer in this
phase has a validated regime restriction other than an event window, which
`validity` already expresses.

A malformed contract is refused when it is loaded, never at a tick.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .lineage import Lineage

CONTRACT_DIR = Path(__file__).resolve().parent / "contracts"
SCHEMA = "csia.evidence_contract/1"
UPDATE_MODES = ("SNAPSHOT", "SAMPLE_AND_HOLD")
HEALTH_REPORTING = ("REPORTED", "IN_PROCESS")


class ContractError(ValueError):
    """A contract that cannot be used."""


@dataclass(frozen=True)
class ClaimSpec:
    claim: str
    meaning: str
    domain: str
    relation: str
    attributable: bool
    config_dependency: tuple = ()


@dataclass(frozen=True)
class ProducerContract:
    producer_id: str
    producer_version: str
    contract_version: str
    claims: dict
    lineage: object                 # Lineage, or "PER_OUTPUT"
    update_mode: str
    update_period_s: float | None
    max_content_age_s: float | None
    event_window: tuple | None      # (event name, lo, hi)
    health_reporting: str
    profile_compatibility: tuple
    raw: dict

    @classmethod
    def from_dict(cls, d: dict) -> "ProducerContract":
        try:
            if d.get("schema") != SCHEMA:
                raise ContractError(f"schema must be {SCHEMA}")
            default_dep = tuple(d.get("config_dependency", ()))
            claims = {}
            for name, c in d["claims"].items():
                claims[name] = ClaimSpec(name, c["meaning"], c["domain"], c["relation"],
                                         bool(c.get("attributable", True)),
                                         tuple(c.get("config_dependency", default_dep)))
            if not claims:
                raise ContractError("a contract must declare at least one claim")
            lin = d["lineage"]
            lineage = "PER_OUTPUT" if lin == "PER_OUTPUT" else Lineage.of(*lin)
            upd = d["update"]
            if upd["mode"] not in UPDATE_MODES:
                raise ContractError(f"update.mode must be one of {UPDATE_MODES}")
            val = d.get("validity") or {}
            window = None
            if "event_window_s" in val:
                lo, hi = val["event_window_s"]
                window = (val["relative_to"], float(lo), float(hi))
                if not window[1] <= window[2]:
                    raise ContractError("event window lo > hi")
            age = val.get("max_content_age_s")
            if d["health_reporting"] not in HEALTH_REPORTING:
                raise ContractError(f"health_reporting must be one of {HEALTH_REPORTING}")
            if not d["profile_compatibility"]:
                raise ContractError("profile_compatibility must name at least one profile")
            return cls(d["producer_id"], str(d["producer_version"]),
                       str(d["contract_version"]), claims, lineage, upd["mode"],
                       upd.get("period_s"), None if age is None else float(age), window,
                       d["health_reporting"], tuple(d["profile_compatibility"]), d)
        except ContractError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError(f"malformed contract: {type(exc).__name__}: {exc}") from exc

    @classmethod
    def load(cls, name: str) -> "ProducerContract":
        return cls.from_dict(json.loads((CONTRACT_DIR / f"{name}.json").read_text()))

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.raw, sort_keys=True).encode()).hexdigest()


def load_contracts(*names) -> dict:
    """`{producer_id: contract}` for the named contract files."""
    out = {}
    for n in names:
        c = ProducerContract.load(n)
        if c.producer_id in out:
            raise ContractError(f"two contracts for {c.producer_id}")
        out[c.producer_id] = c
    return out
