"""The cross-domain signature table — Phase C §§3, 4, 7–10.

Generated into `engineering/v2/CROSS_DOMAIN_SIGNATURE_MATRIX.csv` and used by
`csia/v2/localization.py`. **One source of truth**: the CSV a reviewer reads
and the table the engine runs are the same object, so they cannot drift.

WHAT A ROW OF THE MATRIX MEANS — §4
------------------------------------
For symptom S and domain D the cell is

    CAN_EXPLAIN     D has a declared mechanism that produces S, and named
                    evidence that would confirm or refute it
    CANNOT_EXPLAIN  no mechanism in this model
    DEPENDS         D can produce S only on a platform that instruments the
                    stage in question; whether the cell is live is a property
                    of the PROFILE, not of the framework

Every `CAN_EXPLAIN` names its mechanism and its distinguishing evidence,
because §4 requires it and because a matrix of yes/no with no mechanism is an
opinion rather than a model.

THE PREDICATES ARE THE ARGUMENT — §§3, 5
-----------------------------------------
Each predicate is three-valued (True / False / **None = not measurable**) and
reads only evidence the six domains actually emit. §8 is explicit that
evidence which is not modelled must not appear, so a hypothesis the platform
cannot decide is marked `unmodelled` and stays in the candidate set forever
rather than being quietly resolved.

That last point produces the most useful result in the file. On the
multirotor, "the motor did not turn" and "the RPM sensor is lying" are not
separable, because nothing independent observes the shaft. On the motor test
stand, which has a torque channel, they are. **Same framework, same
hypotheses, different resolving power — decided by what the platform
instruments, not by what the code believes.**
"""

from __future__ import annotations

from .evidence import ObservationState
from .localization import (CAN_EXPLAIN, CANNOT_EXPLAIN, DEPENDS, Hypothesis,
                           Predicate, SymptomSpec, _nominal)

# ===================================================================== helpers
_ADVERSE = (ObservationState.DEGRADED, ObservationState.VIOLATED)


def _seg(index, channel, segment):
    """A timing segment record for a channel, or None."""
    return index.one("timing.segment_budget",
                     component=f"{channel}.{segment}")


def _adverse(record):
    return record is not None and record.observation_state in _ADVERSE


def _deps_in(index, component, domain):
    """Declared dependencies of `component` that belong to `domain`."""
    return [d for d in index.dependencies_of(component)
            if d.startswith(f"{domain}/")]


def _any_adverse_id(index, node_ids):
    """True if any named node is adverse, False if all are affirmatively
    fine, None if none of them reported at all."""
    seen = False
    for nid in node_ids:
        rows = index.find_id(nid)
        if not rows:
            continue
        seen = True
        if any(r.observation_state in _ADVERSE for r in rows):
            return True
    return False if seen else None


# =================================================================== predicates
def _p(pid, desc, domain, fn):
    return Predicate(pid, desc, domain, fn)


# -- timing segments -------------------------------------------------------
def _source_interval(index, channel):
    return _nominal(index.one("timing.rate",
                              component=f"{channel}.sensor_slow"))


def _transport(index, channel):
    return _nominal(_seg(index, channel, "transport_delay"))


def _processing(index, channel):
    return _nominal(_seg(index, channel, "processing_delay"))


def _clock(index, channel):
    return _nominal(index.one("timing.clock_consistency", component=channel))


def _producer_processes(index, channel):
    """The COMPUTE components this channel declares it depends on."""
    return [d.split("/", 1)[1] for d in _deps_in(index, channel, "COMPUTE")]


def _producer_health(index, channel):
    """True if a declared producer process is alive AND producing, False if
    one is not, None if the channel declares no process or none reported.

    This is the cross-domain step in the stale-output case: a TIMING symptom
    is separated using COMPUTE evidence, reached through the profile's
    declared dependency structure.
    """
    seen = False
    for proc in _producer_processes(index, channel):
        for rel in ("compute.process_alive", "compute.process_producing"):
            rec = index.one(rel, component=proc)
            if rec is None:
                continue
            seen = True
            if rec.observation_state in _ADVERSE:
                return False
    return True if seen else None


def _producer_deadline(index, channel):
    seen = False
    for proc in _producer_processes(index, channel):
        rec = index.one("compute.deadline_met", component=proc)
        if rec is None:
            continue
        seen = True
        if rec.observation_state in _ADVERSE:
            return False
    return True if seen else None


def _process_alive(index, process):
    """Subject IS the process here, not a channel.

    `PRODUCER_PROCESS_HEALTHY` walks a channel's declared dependencies; the
    process-level symptoms name the process directly and would get None from
    it. Two predicates rather than one overloaded one, so a reader can see
    which subject each expects.
    """
    rows = [index.one("compute.process_alive", component=process),
            index.one("compute.process_producing", component=process)]
    rows = [r for r in rows if r is not None]
    if not rows:
        return None
    return not any(r.observation_state in _ADVERSE for r in rows)


def _cpu_headroom_ok(index, _subject):
    rows = index.by_relation("compute.resource_headroom")
    if not rows:
        return None
    return not any(r.observation_state in _ADVERSE for r in rows)


def _channel_link_ok(index, channel):
    ids = _deps_in(index, channel, "COMMUNICATION")
    got = _any_adverse_id(index, ids)
    return None if got is None else (not got)


# -- actuation -------------------------------------------------------------
def _command_delivered(index, actuator):
    return _nominal(index.one("actuation.command_path", component=actuator))


def _actuator_link_ok(index, actuator):
    ids = _deps_in(index, actuator, "COMMUNICATION")
    got = _any_adverse_id(index, ids)
    return None if got is None else (not got)


def _actuator_power_ok(index, actuator):
    ids = _deps_in(index, actuator, "POWER")
    got = _any_adverse_id(index, ids)
    return None if got is None else (not got)


def _current_present(index, actuator):
    """True if the actuator is drawing roughly what it was commanded to."""
    rec = index.one("actuation.electrical_response", component=actuator)
    if rec is None or rec.observation_state is ObservationState.NOT_APPLICABLE:
        return None
    return "ACT_NO_ELECTRICAL_RESPONSE" not in rec.reason_codes


def _stall_signature(index, actuator):
    rec = index.one("actuation.mechanical_response", component=actuator)
    if rec is None or rec.observation_state is ObservationState.NOT_APPLICABLE:
        return None
    return "ACT_STALLED" in rec.reason_codes


def _physical_response_ok(index, actuator):
    """Independent confirmation that the shaft actually moved.

    None where the platform has no independent physical channel — which is
    the multirotor, and which is exactly why the response-sensor hypothesis
    is unresolvable there.
    """
    rec = index.one("actuation.physical_response", component=actuator)
    if rec is None or rec.observation_state is ObservationState.NOT_APPLICABLE:
        return None
    return rec.observation_state is ObservationState.NOMINAL


# -- shared dependencies ---------------------------------------------------
def _adverse_sources(index):
    return [r for r in index.by_relation("v1_1.source_health")
            if r.observation_state in _ADVERSE]


def _shared_adverse_dependency(index, domain):
    """A node in `domain` that two or more adverse sources depend on AND
    that is itself adverse. §13's common cause, per domain."""
    counts: dict = {}
    for rec in _adverse_sources(index):
        for dep in set(rec.dependencies):
            if dep.startswith(f"{domain}/"):
                counts[dep] = counts.get(dep, 0) + 1
    shared = sorted(k for k, n in counts.items() if n >= 2)
    if not shared:
        # Also walk one level up: a rail feeds a converter feeds the sources.
        reach: dict = {}
        for rec in _adverse_sources(index):
            for dep in set(rec.dependencies):
                for up in index.dependencies_of(dep.split("/", 1)[1]):
                    if up.startswith(f"{domain}/"):
                        reach[up] = reach.get(up, 0) + 1
        shared = sorted(k for k, n in reach.items() if n >= 2)
    if not shared:
        return False, None
    adverse = [s for s in shared if _any_adverse_id(index, [s]) is True]
    return (bool(adverse), adverse[0] if adverse else None)


def _shared_power(index, _subject):
    if len(_adverse_sources(index)) < 2:
        return None
    return _shared_adverse_dependency(index, "POWER")[0]


def _shared_comm(index, _subject):
    if len(_adverse_sources(index)) < 2:
        return None
    return _shared_adverse_dependency(index, "COMMUNICATION")[0]


def _shared_compute(index, _subject):
    if len(_adverse_sources(index)) < 2:
        return None
    return _shared_adverse_dependency(index, "COMPUTE")[0]


def _no_shared_adverse_dependency(index, _subject):
    if len(_adverse_sources(index)) < 2:
        return None
    return not any(_shared_adverse_dependency(index, d)[0]
                   for d in ("POWER", "COMMUNICATION", "COMPUTE", "TIMING"))


# -- function-level --------------------------------------------------------
def _v1_1_function_ok(index, function):
    return _nominal(index.one("v1_1.function_eligibility",
                              component=f"v1_1.{function}"))


def _estimator_ok(index, _function):
    rows = [r for r in index.records
            if r.domain == "COMPUTE"
            and r.relation in ("compute.process_alive",
                               "compute.process_producing",
                               "compute.deadline_met")]
    if not rows:
        return None
    return not any(r.observation_state in _ADVERSE for r in rows)


def _nav_timing_ok(index, _function):
    rows = index.by_relation("timing.end_to_end")
    rows = [r for r in rows if r.applicability.value == "APPLICABLE"]
    if not rows:
        return None
    return not any(r.observation_state in _ADVERSE for r in rows)


def _no_segment_over_budget(index, _function):
    """Function-subject form: is EVERY judged timing segment inside its own
    budget, anywhere in the system?

    The segment predicates above take a CHANNEL as their subject. A
    function-level symptom names a function, so it needs this form -- and
    without it §27's "do not double-count" refutation is unmeasurable and
    silently does nothing, which is how it read before this was added.
    """
    rows = [r for r in index.by_relation("timing.segment_budget")
            if r.applicability.value == "APPLICABLE"]
    rows += [r for r in index.by_relation("timing.rate")]
    if not rows:
        return None
    return not any(r.observation_state in _ADVERSE for r in rows)


def _nav_link_ok(index, _function):
    rows = index.by_relation("comm.link_state")
    if not rows:
        return None
    return not any(r.observation_state in _ADVERSE for r in rows)


def _rail_low(index, rail):
    return _nominal(index.one("power.rail_tolerance", component=rail))


def _source_ok(index, source):
    return _nominal(index.one("power.source_health", component=source))


PREDICATES = {p.predicate_id: p for p in (
    _p("SOURCE_INTERVAL_NOMINAL",
       "the source's own sampling interval is within its declared period",
       "TIMING", _source_interval),
    _p("TRANSPORT_WITHIN_BUDGET",
       "arrival - validity is within the channel's transport budget",
       "TIMING", _transport),
    _p("PROCESSING_WITHIN_BUDGET",
       "processed - arrival is within the channel's processing budget",
       "TIMING", _processing),
    _p("CLOCK_CONSISTENT",
       "the four timestamps are in a physically possible order",
       "TIMING", _clock),
    _p("PRODUCER_PROCESS_HEALTHY",
       "every COMPUTE process this channel declares is alive and producing",
       "COMPUTE", _producer_health),
    _p("PRODUCER_DEADLINE_MET",
       "every COMPUTE process this channel declares met its deadline",
       "COMPUTE", _producer_deadline),
    _p("PROCESS_ALIVE_AND_PRODUCING",
       "this process is alive and has produced output recently",
       "COMPUTE", _process_alive),
    _p("CPU_HEADROOM_NOMINAL",
       "the machine has CPU and memory headroom left",
       "COMPUTE", _cpu_headroom_ok),
    _p("CHANNEL_LINK_NOMINAL",
       "every COMMUNICATION link this channel declares is up and healthy",
       "COMMUNICATION", _channel_link_ok),
    _p("COMMAND_DELIVERED",
       "the transmitted command matches the requested command",
       "ACTUATION", _command_delivered),
    _p("ACTUATOR_LINK_NOMINAL",
       "every COMMUNICATION link the actuator declares is healthy",
       "COMMUNICATION", _actuator_link_ok),
    _p("ACTUATOR_POWER_NOMINAL",
       "every POWER node the actuator declares is within tolerance",
       "POWER", _actuator_power_ok),
    _p("CURRENT_PRESENT",
       "the actuator draws roughly the current its command implies",
       "ACTUATION", _current_present),
    _p("STALL_SIGNATURE",
       "current present AND shaft speed absent",
       "ACTUATION", _stall_signature),
    _p("PHYSICAL_RESPONSE_NOMINAL",
       "an INDEPENDENT physical channel confirms the actuator moved",
       "ACTUATION", _physical_response_ok),
    _p("SHARED_ADVERSE_POWER_DEPENDENCY",
       "two or more adverse sources reach one adverse POWER node",
       "POWER", _shared_power),
    _p("SHARED_ADVERSE_COMM_DEPENDENCY",
       "two or more adverse sources reach one adverse COMMUNICATION node",
       "COMMUNICATION", _shared_comm),
    _p("SHARED_ADVERSE_COMPUTE_DEPENDENCY",
       "two or more adverse sources reach one adverse COMPUTE node",
       "COMPUTE", _shared_compute),
    _p("NO_SHARED_ADVERSE_DEPENDENCY",
       "the adverse sources share no adverse declared dependency",
       "SENSOR", _no_shared_adverse_dependency),
    _p("V1_1_FUNCTION_ELIGIBLE",
       "v1.1 still calls this function eligible on its own evidence",
       "SENSOR", _v1_1_function_ok),
    _p("ESTIMATOR_PROCESS_HEALTHY",
       "no COMPUTE process is dead, silent or past its deadline",
       "COMPUTE", _estimator_ok),
    _p("FUNCTION_TIMING_WITHIN_DEADLINE",
       "every judged channel met its end-to-end deadline",
       "TIMING", _nav_timing_ok),
    _p("NO_TIMING_SEGMENT_OVER_BUDGET",
       "every judged timing segment is inside its own budget",
       "TIMING", _no_segment_over_budget),
    _p("FUNCTION_LINKS_NOMINAL",
       "every communication link is up",
       "COMMUNICATION", _nav_link_ok),
    _p("RAIL_WITHIN_TOLERANCE",
       "the rail is inside its declared band", "POWER", _rail_low),
    _p("SOURCE_WITHIN_TOLERANCE",
       "the power source is healthy", "POWER", _source_ok),
)}


# ==================================================================== symptoms
def _stale_channels(index):
    out = []
    for rec in index.by_relation("timing.end_to_end"):
        ch = rec.component
        if (_adverse(rec)
                or _adverse(index.one("timing.clock_consistency",
                                      component=ch))
                or _adverse(index.one("timing.rate",
                                      component=f"{ch}.sensor_slow"))):
            out.append(ch)
    # A channel whose clock was refused emits no end_to_end record at all.
    for rec in index.by_relation("timing.clock_consistency"):
        if _adverse(rec) and rec.component not in out:
            out.append(rec.component)
    return tuple(sorted(set(out)))


def _unresponsive_actuators(index):
    out = set()
    for rel in ("actuation.command_path", "actuation.electrical_response",
                "actuation.mechanical_response",
                "actuation.physical_response"):
        for rec in index.by_relation(rel):
            if _adverse(rec):
                out.add(rec.component)
    return tuple(sorted(out))


def _multi_sensor(index):
    return ("sources",) if len(_adverse_sources(index)) >= 2 else ()


def _degraded_position_functions(index):
    """Functions v1.1 names that are not fully available somewhere."""
    out = set()
    for rec in index.by_relation("v1_1.function_eligibility"):
        name = rec.component.split(".", 1)[1]
        if "NAVIGATION" not in name and "POSITION" not in name:
            continue
        if (_adverse(rec) or _estimator_ok(index, name) is False
                or _nav_timing_ok(index, name) is False
                or _nav_link_ok(index, name) is False):
            out.add(name)
    return tuple(sorted(out))


def _low_rails(index):
    return tuple(sorted(r.component for r in
                        index.by_relation("power.rail_tolerance")
                        if _adverse(r)))


def _late_processes(index):
    return tuple(sorted(r.component for r in
                        index.by_relation("compute.deadline_met")
                        if _adverse(r)))


def _high_current_low_rpm(index):
    return tuple(sorted(r.component for r in
                        index.by_relation("actuation.mechanical_response")
                        if "ACT_STALLED" in r.reason_codes))


def _missing_outputs(index):
    return tuple(sorted(r.component for r in
                        index.by_relation("compute.process_producing")
                        if _adverse(r)))


SYMPTOMS = (
    # -- §7 -----------------------------------------------------------
    SymptomSpec(
        symptom_id="OUTPUT_STALE",
        description="a timed channel's output is later than its function "
                    "requires, or its timestamps are inconsistent",
        detect=_stale_channels,
        evidence_relation="timing.end_to_end",
        hypotheses=(
            Hypothesis("SENSOR/source_slow", "SENSOR",
                       "the source sampled later than its declared period, so "
                       "the value was already old when it left",
                       confirmed_by=("SOURCE_INTERVAL_NOMINAL_FALSE",),
                       refuted_by=("SOURCE_INTERVAL_NOMINAL",)),
            Hypothesis("COMMUNICATION/transport_delay", "COMMUNICATION",
                       "the value was delayed between leaving the source and "
                       "arriving",
                       confirmed_by=("TRANSPORT_WITHIN_BUDGET_FALSE",),
                       # THE CROSS-DOMAIN STEP. A late arrival alone cannot
                       # separate "the source was slow to emit" from "the link
                       # was slow to carry": both live in validity->arrival.
                       # A link that affirmatively reports healthy rate, loss
                       # and queue delay is evidence against the second, and
                       # it comes from a different domain's plugin.
                       refuted_by=("TRANSPORT_WITHIN_BUDGET",
                                   "CHANNEL_LINK_NOMINAL")),
            Hypothesis("COMPUTE/processing_delay", "COMPUTE",
                       "the process was running but took too long",
                       confirmed_by=("PROCESSING_WITHIN_BUDGET_FALSE",),
                       # A process that is not alive is not "slow": the
                       # heartbeat is what separates the two COMPUTE causes,
                       # and it separates them in BOTH directions.
                       refuted_by=("PROCESSING_WITHIN_BUDGET",
                                   "PRODUCER_PROCESS_HEALTHY_FALSE")),
            Hypothesis("COMPUTE/process_stall", "COMPUTE",
                       "the process stopped producing altogether",
                       confirmed_by=("PRODUCER_PROCESS_HEALTHY_FALSE",),
                       refuted_by=("PRODUCER_PROCESS_HEALTHY",)),
            Hypothesis("TIMING/clock_inconsistent", "TIMING",
                       "the timebase itself is wrong, so no latency computed "
                       "from these stamps means anything",
                       confirmed_by=("CLOCK_CONSISTENT_FALSE",),
                       refuted_by=("CLOCK_CONSISTENT",)),
        )),
    # -- §8 -----------------------------------------------------------
    SymptomSpec(
        symptom_id="COMMAND_NO_RESPONSE",
        description="an actuator was commanded and the measured response is "
                    "weak or absent",
        detect=_unresponsive_actuators,
        evidence_relation="actuation.electrical_response",
        hypotheses=(
            Hypothesis("COMMUNICATION/command_not_delivered", "COMMUNICATION",
                       "the command never reached the controller",
                       confirmed_by=("COMMAND_DELIVERED_FALSE",
                                     "ACTUATOR_LINK_NOMINAL_FALSE"),
                       refuted_by=("COMMAND_DELIVERED",)),
            Hypothesis("POWER/path_unavailable", "POWER",
                       "the actuator's declared power node is out of "
                       "tolerance, so nothing could drive it",
                       confirmed_by=("ACTUATOR_POWER_NOMINAL_FALSE",),
                       refuted_by=("ACTUATOR_POWER_NOMINAL",)),
            Hypothesis("ACTUATION/drive_no_current", "ACTUATION",
                       "the drive stage is not passing current despite a "
                       "delivered command and healthy power",
                       confirmed_by=("CURRENT_PRESENT_FALSE",),
                       # "despite" is doing the work. A stage that was never
                       # commanded, or that has no power, is not drawing no
                       # current because IT failed -- and both refutations
                       # come from other domains.
                       refuted_by=("CURRENT_PRESENT",
                                   "COMMAND_DELIVERED_FALSE",
                                   "ACTUATOR_POWER_NOMINAL_FALSE")),
            Hypothesis("ACTUATION/mechanical", "ACTUATION",
                       "current is flowing and the shaft is not turning",
                       confirmed_by=("STALL_SIGNATURE",),
                       # An independent channel saying the shaft DID move
                       # rules out "mechanically stuck" -- and is the only
                       # thing that can. Where no such channel exists this
                       # predicate is None and the pair stays ambiguous.
                       refuted_by=("STALL_SIGNATURE_FALSE",
                                   "PHYSICAL_RESPONSE_NOMINAL")),
            Hypothesis("SENSOR/response_sensor", "SENSOR",
                       "the actuator is fine and the channel measuring its "
                       "response is not",
                       confirmed_by=("PHYSICAL_RESPONSE_NOMINAL",),
                       refuted_by=("PHYSICAL_RESPONSE_NOMINAL_FALSE",),
                       note="resolvable ONLY where an independent physical "
                            "channel exists. On a platform without one this "
                            "hypothesis can never be eliminated, and the "
                            "candidate set has an honest floor of two."),
        )),
    # -- §9 -----------------------------------------------------------
    SymptomSpec(
        symptom_id="MULTIPLE_SENSORS_DEGRADED",
        description="two or more sensor-derived sources are adverse at once",
        detect=_multi_sensor,
        evidence_relation="v1_1.source_health",
        hypotheses=(
            Hypothesis("SENSOR/independent_faults", "SENSOR",
                       "the sources failed separately and share nothing "
                       "adverse",
                       confirmed_by=("NO_SHARED_ADVERSE_DEPENDENCY",),
                       refuted_by=("SHARED_ADVERSE_POWER_DEPENDENCY",
                                   "SHARED_ADVERSE_COMM_DEPENDENCY",
                                   "SHARED_ADVERSE_COMPUTE_DEPENDENCY")),
            Hypothesis("POWER/shared_node", "POWER",
                       "the sources share one adverse power node",
                       confirmed_by=("SHARED_ADVERSE_POWER_DEPENDENCY",),
                       refuted_by=("SHARED_ADVERSE_POWER_DEPENDENCY_FALSE",)),
            Hypothesis("COMMUNICATION/shared_link", "COMMUNICATION",
                       "the sources share one adverse link",
                       confirmed_by=("SHARED_ADVERSE_COMM_DEPENDENCY",),
                       refuted_by=("SHARED_ADVERSE_COMM_DEPENDENCY_FALSE",)),
            Hypothesis("COMPUTE/shared_process", "COMPUTE",
                       "the sources share one adverse compute node",
                       confirmed_by=("SHARED_ADVERSE_COMPUTE_DEPENDENCY",),
                       refuted_by=(
                           "SHARED_ADVERSE_COMPUTE_DEPENDENCY_FALSE",)),
        )),
    # -- §10 ----------------------------------------------------------
    SymptomSpec(
        symptom_id="POSITION_UNAVAILABLE",
        description="a position or navigation function is not fully "
                    "available",
        detect=_degraded_position_functions,
        evidence_relation="v1_1.function_eligibility",
        hypotheses=(
            Hypothesis("SENSOR/navigation_source_invalid", "SENSOR",
                       "v1.1's own evidence says the function is not "
                       "eligible",
                       confirmed_by=("V1_1_FUNCTION_ELIGIBLE_FALSE",),
                       refuted_by=("V1_1_FUNCTION_ELIGIBLE",)),
            Hypothesis("COMPUTE/estimator_stale", "COMPUTE",
                       "the estimating process is dead, silent or late",
                       confirmed_by=("ESTIMATOR_PROCESS_HEALTHY_FALSE",),
                       refuted_by=("ESTIMATOR_PROCESS_HEALTHY",)),
            Hypothesis("TIMING/deadline_violation", "TIMING",
                       "the deadline was missed with no segment over its own "
                       "budget -- a timing fault in its own right",
                       confirmed_by=("FUNCTION_TIMING_WITHIN_DEADLINE_FALSE",),
                       # §27: transport latency belongs to COMMUNICATION and
                       # processing latency to COMPUTE. When a segment IS over
                       # budget the deadline miss is that segment's, and
                       # counting it again here would turn one event into two
                       # independent faults.
                       refuted_by=("FUNCTION_TIMING_WITHIN_DEADLINE",
                                   "NO_TIMING_SEGMENT_OVER_BUDGET_FALSE")),
            Hypothesis("COMMUNICATION/starvation", "COMMUNICATION",
                       "the link carrying position evidence is down or "
                       "starved",
                       confirmed_by=("FUNCTION_LINKS_NOMINAL_FALSE",),
                       refuted_by=("FUNCTION_LINKS_NOMINAL",)),
        )),
    # -- the remaining §4 symptoms ------------------------------------
    SymptomSpec(
        symptom_id="VOLTAGE_RAIL_LOW",
        description="a regulated rail is outside its declared band",
        detect=_low_rails, evidence_relation="power.rail_tolerance",
        hypotheses=(
            Hypothesis("POWER/source", "POWER",
                       "the source feeding the rail is itself sagging",
                       confirmed_by=("SOURCE_WITHIN_TOLERANCE_FALSE",),
                       refuted_by=("SOURCE_WITHIN_TOLERANCE",)),
            Hypothesis("POWER/distribution", "POWER",
                       "the source is healthy and the regulator or "
                       "distribution path is not",
                       confirmed_by=("SOURCE_WITHIN_TOLERANCE",),
                       refuted_by=("SOURCE_WITHIN_TOLERANCE_FALSE",)),
        )),
    SymptomSpec(
        symptom_id="PROCESS_OUTPUT_LATE",
        description="a process exceeded its declared deadline",
        detect=_late_processes, evidence_relation="compute.deadline_met",
        hypotheses=(
            Hypothesis("COMPUTE/resource_exhaustion", "COMPUTE",
                       "the machine ran out of CPU or memory headroom",
                       confirmed_by=("CPU_HEADROOM_NOMINAL_FALSE",),
                       refuted_by=("CPU_HEADROOM_NOMINAL",),
                       note="CPU saturation CAN explain processing delay; "
                            "processing delay does NOT imply CPU saturation "
                            "(§26), so this is confirmed by resource evidence "
                            "and never inferred from lateness alone"),
            Hypothesis("COMPUTE/process_stall", "COMPUTE",
                       "the process stopped rather than slowed",
                       confirmed_by=("PROCESS_ALIVE_AND_PRODUCING_FALSE",),
                       refuted_by=("PROCESS_ALIVE_AND_PRODUCING",)),
        )),
    SymptomSpec(
        symptom_id="HIGH_CURRENT_LOW_RPM",
        description="an actuator draws its expected current and does not turn",
        detect=_high_current_low_rpm,
        evidence_relation="actuation.mechanical_response",
        hypotheses=(
            Hypothesis("ACTUATION/mechanical", "ACTUATION",
                       "the load is obstructed or the drivetrain has failed",
                       confirmed_by=("STALL_SIGNATURE",),
                       refuted_by=("PHYSICAL_RESPONSE_NOMINAL",)),
            Hypothesis("SENSOR/response_sensor", "SENSOR",
                       "the shaft is turning and the speed channel is not "
                       "reporting it",
                       confirmed_by=("PHYSICAL_RESPONSE_NOMINAL",),
                       refuted_by=("PHYSICAL_RESPONSE_NOMINAL_FALSE",),
                       note="same irreducible pair as COMMAND_NO_RESPONSE"),
        )),
    SymptomSpec(
        symptom_id="OUTPUT_MISSING",
        description="a process is alive but has produced nothing recently",
        detect=_missing_outputs,
        evidence_relation="compute.process_producing",
        hypotheses=(
            Hypothesis("COMPUTE/process_stall", "COMPUTE",
                       "the process is not producing output",
                       confirmed_by=("PROCESS_ALIVE_AND_PRODUCING_FALSE",),
                       refuted_by=("PROCESS_ALIVE_AND_PRODUCING",)),
            Hypothesis("COMMUNICATION/input_starvation", "COMMUNICATION",
                       "the process has nothing to work on because its input "
                       "link is down",
                       confirmed_by=("FUNCTION_LINKS_NOMINAL_FALSE",),
                       refuted_by=("FUNCTION_LINKS_NOMINAL",)),
        )),
    SymptomSpec(
        symptom_id="FUNCTION_DEADLINE_MISS",
        description="a function's end-to-end deadline was missed",
        detect=lambda ix: tuple(sorted(
            r.component for r in ix.by_relation("timing.end_to_end")
            if "TIMING_DEADLINE_MISSED" in r.reason_codes)),
        evidence_relation="timing.end_to_end",
        hypotheses=(
            Hypothesis("COMMUNICATION/transport_delay", "COMMUNICATION",
                       "transport consumed the budget",
                       confirmed_by=("TRANSPORT_WITHIN_BUDGET_FALSE",),
                       refuted_by=("TRANSPORT_WITHIN_BUDGET",)),
            Hypothesis("COMPUTE/processing_delay", "COMPUTE",
                       "processing consumed the budget",
                       confirmed_by=("PROCESSING_WITHIN_BUDGET_FALSE",),
                       refuted_by=("PROCESSING_WITHIN_BUDGET",)),
            Hypothesis("SENSOR/source_slow", "SENSOR",
                       "the source was already old",
                       confirmed_by=("SOURCE_INTERVAL_NOMINAL_FALSE",),
                       refuted_by=("SOURCE_INTERVAL_NOMINAL",)),
            Hypothesis("TIMING/budget_exceeded_without_segment", "TIMING",
                       "every segment was inside its own budget and the "
                       "total was not: the budgets do not sum to the "
                       "deadline",
                       confirmed_by=("TRANSPORT_WITHIN_BUDGET",
                                     "PROCESSING_WITHIN_BUDGET",
                                     "SOURCE_INTERVAL_NOMINAL"),
                       # A CONJUNCTION: "no segment was over" is only true
                       # when none of them was. ANY-of would confirm this
                       # whenever a single segment happened to be fine, which
                       # is exactly the case where another segment is the
                       # answer.
                       confirm_requires_all=True,
                       refuted_by=("TRANSPORT_WITHIN_BUDGET_FALSE",
                                   "PROCESSING_WITHIN_BUDGET_FALSE",
                                   "SOURCE_INTERVAL_NOMINAL_FALSE")),
        )),
)

SYMPTOMS_BY_ID = {s.symptom_id: s for s in SYMPTOMS}


# ------------------------------------------------ negated predicate support
class _Negated(Predicate):
    """`X_FALSE` is True exactly when `X` is False, and None when X is None.

    Refutation and confirmation are not each other's negation when a
    predicate can be unmeasurable, so both directions have to be nameable.
    Deriving the negation rather than writing it keeps the pair in step.
    """


def _negate(pred):
    def test(index, subject):
        got = pred(index, subject)
        return None if got is None else (not got)
    return _Negated(pred.predicate_id + "_FALSE",
                    "NOT (" + pred.description + ")",
                    pred.evidence_domain, test)


for _pid in list(PREDICATES):
    PREDICATES[_pid + "_FALSE"] = _negate(PREDICATES[_pid])

# ================================================================== the matrix
DOMAINS = ("SENSOR", "POWER", "COMPUTE", "TIMING", "COMMUNICATION",
           "ACTUATION")

#: §4's third cell value. A domain that can explain a symptom only where the
#: platform instruments the relevant stage.
PROFILE_DEPENDENT = {
    ("COMMAND_NO_RESPONSE", "SENSOR"):
        "needs an independent physical response channel; the multirotor has "
        "none and the motor test stand has torque",
    ("HIGH_CURRENT_LOW_RPM", "SENSOR"):
        "same independent channel",
    ("OUTPUT_STALE", "COMMUNICATION"):
        "needs an arrival timestamp distinct from the validity timestamp",
    ("OUTPUT_STALE", "COMPUTE"):
        "needs a processed timestamp and a declared producer process",
}


def matrix_rows() -> list:
    """The signature matrix, one row per (symptom, domain)."""
    rows = []
    for spec in SYMPTOMS:
        by_domain: dict = {}
        for h in spec.hypotheses:
            by_domain.setdefault(h.domain, []).append(h)
        for domain in DOMAINS:
            hyps = by_domain.get(domain, [])
            key = (spec.symptom_id, domain)
            if not hyps:
                rows.append({
                    "symptom": spec.symptom_id, "domain": domain,
                    "cell": CANNOT_EXPLAIN, "mechanism": "",
                    "confirming_evidence": "", "refuting_evidence": "",
                    "note": "no mechanism in this model"})
                continue
            cell = DEPENDS if key in PROFILE_DEPENDENT else CAN_EXPLAIN
            rows.append({
                "symptom": spec.symptom_id, "domain": domain, "cell": cell,
                "mechanism": " | ".join(h.mechanism for h in hyps),
                "confirming_evidence": " | ".join(
                    ";".join(h.confirmed_by) for h in hyps),
                "refuting_evidence": " | ".join(
                    ";".join(h.refuted_by) for h in hyps),
                "note": PROFILE_DEPENDENT.get(key, "") or
                " | ".join(h.note for h in hyps if h.note)})
    return rows


def write_matrix_csv(path: str) -> str:
    import csv
    rows = matrix_rows()
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path
