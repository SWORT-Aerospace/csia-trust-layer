"""Multirotor quad profile, version r1 (CSIA 2.3). OFFBOARD ONLY.

A VERSIONED successor profile for the vehicle the XSYS-001 campaign flew:
PX4 547e2ca SIH quadrotor X, four motors, one battery. The historical
aircraft profile (`csia/v2/profiles/aircraft.py`, one motor) is not touched.
This module builds a new engine from the same frozen v2 library classes,
signatures and predicates, so Semantic Core 2.1.1 reasons over it unchanged
(`SemanticCore21.from_engine`).

WHAT IS MODELLED, AND FROM WHERE
--------------------------------
| component | v2 domain | relationship | source |
|---|---|---|---|
| motor_0 .. motor_3 | ACTUATION | each depends on POWER/battery and COMPUTE/control_allocator | `CA_ROTOR_COUNT` = 4; SIH quad motor order (`CA_ROTORn_PX/PY`); every motor is driven by the allocator's `actuator_motors.control[n]` and powered from the pack |
| battery | POWER | feeds every function | SIH battery (`battery_status`) |
| state_estimator | COMPUTE | depends on COMPUTE/cpu | EKF2 |
| control_allocator | COMPUTE | depends on COMPUTE/state_estimator and COMPUTE/cpu | the rate controller and allocator run on EKF2's attitude |
| cpu | COMPUTE | resource | the flight computer |

WHAT IS NOT MODELLED, AND WHY
-----------------------------
| omitted | why |
|---|---|
| IMU, GNSS, magnetometer, barometer as SENSOR components | v2's SENSOR domain is the v1.1 trust engine's verdict, ingested from its payload; no PX4 log carries one. They appear as lineage roots of the estimator and allocator evidence (`sensor:imu.<id>`, `sensor:gps`, ...) and as the 2.2 EKF2 context claims |
| ESC bus, GNSS serial link, telemetry radio | SIH has none: motors are driven by the simulated PWM output, GNSS is simulated in-process. On hardware these links exist; adding them is a successor revision with a producer for each |
| regulated rails | SIH has none; `system_power` is constant in all 66 logs |
| timing channels | no stock producer of segment latencies |

**Expectation numbers.** `full_current_a` and `full_rpm` are left undeclared:
the stock producers build their own records (`adapters/px4_stock.py`), and
no datasheet number is invented for SIH.
"""

from __future__ import annotations

import hashlib
import inspect

from csia.v2.domain import Snapshot
from csia.v2.domains.actuation import ActuationAssuranceDomain, ActuatorSpec
from csia.v2.domains.compute import ComputeAssuranceDomain, ProcessSpec, ResourceSpec
from csia.v2.domains.power import BatterySpec, PowerAssuranceDomain
from csia.v2.engine import AssuranceEngine
from csia.v2.functions import FunctionGraph, SystemFunction
from csia.v2.registry import DomainRegistry

NAME, VERSION = "multirotor-quad", "r1"
BASE = "csia_evidence_assurance/profiles/multirotor_quad.py"

FUNCTIONS = (
    SystemFunction(
        name="PROPULSION",
        summary="commanded thrust is being produced on every rotor",
        required_domains=("POWER", "ACTUATION"),
        supporting_domains=("COMPUTE",)),
    SystemFunction(
        name="STATE_ESTIMATION",
        summary="EKF2 is producing an estimate",
        required_domains=("COMPUTE", "POWER")),
    SystemFunction(
        name="AUTONOMOUS_MISSION",
        summary="the vehicle can fly a mission without an operator",
        required_domains=("COMPUTE", "POWER", "ACTUATION")),
)
_ALL = tuple(f.name for f in FUNCTIONS)


def build_quad_engine(n_motors: int = 4) -> AssuranceEngine:
    """The quad profile. `n_motors` exists for the Phase 11 scale test only
    (1 against 4); the profile is r1 with 4."""
    reg = DomainRegistry()
    reg.register(ActuationAssuranceDomain(actuators=tuple(
        ActuatorSpec(f"motor_{m}", affected_functions=("PROPULSION", "AUTONOMOUS_MISSION"),
                     depends_on=("POWER/battery", "COMPUTE/control_allocator"))
        for m in range(n_motors)), affected_functions=("PROPULSION",)))
    reg.register(PowerAssuranceDomain(
        rails=(), battery=BatterySpec(affected_functions=_ALL), affected_functions=_ALL))
    reg.register(ComputeAssuranceDomain(
        processes=(
            ProcessSpec("state_estimator", affected_functions=("STATE_ESTIMATION",
                                                               "AUTONOMOUS_MISSION"),
                        depends_on=("COMPUTE/cpu",)),
            ProcessSpec("control_allocator", affected_functions=("PROPULSION",
                                                                 "AUTONOMOUS_MISSION"),
                        depends_on=("COMPUTE/state_estimator", "COMPUTE/cpu")),
        ),
        resource=ResourceSpec(name="cpu", affected_functions=_ALL),
        affected_functions=("STATE_ESTIMATION",)))
    from csia.v2.signatures import PREDICATES, SYMPTOMS
    return AssuranceEngine(reg, FunctionGraph(FUNCTIONS), (), symptoms=SYMPTOMS,
                           predicates=PREDICATES)


def sample_records(engine) -> tuple:
    """One tick with every input missing: each declared component reports
    UNAVAILABLE with its declarations, which is all the validator reads."""
    return engine.evaluate(Snapshot(t=0.0, signals={})).records


def digest() -> str:
    src = inspect.getsource(build_quad_engine) + repr(FUNCTIONS)
    return hashlib.sha256(src.encode()).hexdigest()


def profile_info() -> dict:
    return {"name": NAME, "version": VERSION, "base_profile": BASE, "digest": digest()}


#: Every record the profile defines: each domain's relations for each of its
#: components (the sample tick shows only what a domain emits with no inputs).
RELATIONS = {
    "ACTUATION": ("actuation.command_path", "actuation.electrical_response",
                  "actuation.mechanical_response", "actuation.physical_response"),
    "POWER/battery": ("power.source_health", "power.p_equals_vi", "power.droop_vs_current",
                      "power.cell_balance"),
    "COMPUTE/process": ("compute.process_alive", "compute.process_producing",
                        "compute.deadline_met", "compute.stability"),
    "COMPUTE/cpu": ("compute.resource_headroom",),
}


def record_catalog(n_motors: int = 4) -> tuple:
    keys = [f"ACTUATION/motor_{m}:{r}" for m in range(n_motors) for r in RELATIONS["ACTUATION"]]
    keys += [f"POWER/battery:{r}" for r in RELATIONS["POWER/battery"]]
    keys += [f"COMPUTE/{p}:{r}" for p in ("state_estimator", "control_allocator")
             for r in RELATIONS["COMPUTE/process"]]
    keys += [f"COMPUTE/cpu:{r}" for r in RELATIONS["COMPUTE/cpu"]]
    return tuple(sorted(keys))


def gate(engine=None, n_motors: int = 4):
    """The 2.2 profile gate for this profile: PV1-PV9 on the declarations
    (no pacing overlay, so PG1 has nothing to check). Records: the full
    catalog."""
    from csia_semantic_core.profile_validator import ERROR, GAP, WARNING, validate_profile

    from ..profile_gate import OK, REFUSED, GateResult
    engine = engine or build_quad_engine(n_motors)
    sev = {ERROR: "ERROR", WARNING: "WARNING", GAP: "INFO"}
    found = tuple(sorted(((sev[f.severity], f.rule, f.subject, f.detail)
                          for f in validate_profile(sample_records(engine), engine.functions)),
                         key=lambda f: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[f[0]], f[1], f[2])))
    status = REFUSED if any(f[0] == "ERROR" for f in found) else OK
    return GateResult(status, profile_info(), found, record_catalog(n_motors))
