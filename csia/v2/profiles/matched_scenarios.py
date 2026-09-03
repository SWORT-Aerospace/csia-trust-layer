"""Matched-cause scenario sets — Phase C §§7–10.

Spec: `engineering/v2/MATCHED_SCENARIOS.md`.

WHAT "MATCHED" MEANS AND WHY IT IS THE WHOLE TEST
--------------------------------------------------
Every member of a set produces the **same downstream symptom**. If the four
stale-output causes each produced a visibly different observable, separating
them would be pattern-matching on the injection rather than localization, and
the result would prove nothing about cross-domain reasoning.

So within a set the symptom-level observable is held as close to identical as
the model allows, and only the *distinguishing* evidence differs. §7 is
explicit: **do not allow value shape alone to reveal the condition.**

WHAT THE LOCALIZER IS NOT TOLD
-------------------------------
The scenario name, the injected cause, and every ground-truth label stay in
this module. `localize()` receives evidence records and the declared
signature table, and a test asserts no scenario label reaches it. The
expected result written on each scenario is checked against the output; it is
never an input to it.

SET A — STALE OUTPUT (§7)
--------------------------
The four causes are matched on **end-to-end latency over the channel's
deadline**, all at ~88 ms against a 50 ms deadline. What differs is where the
time went and what the other domains say about it:

    A1  the source itself is slow          interval over period, link healthy
    A2  the link delayed it                interval normal, link queue high
    A3  the process ran long               processing over budget, alive
    A4  the process stopped                processing over budget, heartbeat
                                           stale

A1 and A2 are the interesting pair: **both put the delay in
validity -> arrival, so timestamps alone cannot separate them.** What
separates them is the COMMUNICATION domain's own link evidence — a link
affirmatively reporting healthy rate, loss and queue delay is evidence
against "the link delayed it", and it comes from a different plugin. That is
the Final Rule's test: evidence from one domain changing how a failure in
another is interpreted.

A3 and A4 are the second pair: both show processing over budget, and the
COMPUTE heartbeat separates them in both directions.

SET B — NO ACTUATOR RESPONSE (§8)
----------------------------------
Five causes, matched on "commanded and the shaft is not turning":

    B1  command never delivered            transmitted != requested
    B2  power path unavailable             declared power node adverse
    B3  drive stage passing no current     current absent, power fine
    B4  mechanically stuck                 current present, rpm absent
    B5  the rpm channel is lying           current present, rpm absent

**B4 and B5 produce identical evidence on the multirotor**, because nothing
independent observes the shaft. They are separable on the motor test stand,
which has a torque channel. That is reported as a finding rather than
resolved by assertion — see `EVIDENCE_SUBSET_RESULTS.csv`.
"""

from __future__ import annotations

from dataclasses import replace

from ..scenarios import Scenario
from .aircraft_scenarios import AIRCRAFT_NOMINAL
from .test_stand_scenarios import TEST_STAND_NOMINAL

#: The matched end-to-end latency for set A, in seconds. One number for all
#: four causes, so the symptom cannot betray the cause.
A_TOTAL_LATENCY = 0.088
#: The channel's declared deadline in the aircraft profile is 0.050 s.
A_CHANNEL = "nav_solution"


def _hold(sig, frac, onset=0.30):
    """Matched scenarios are step, not ramp: a ramp would make the four
    causes differ in how fast the observable grows, which is value shape."""
    return frac >= onset


# ================================================================ SET A
def _a_common(sig):
    """Everything the four causes share, so only the split differs."""
    sig["TIMING"][A_CHANNEL]["decision_s"] = 0.002


def _a1_sensor_delay(sig, frac, t):
    _a_common(sig)
    if not _hold(sig, frac):
        return
    ch = sig["TIMING"][A_CHANNEL]
    # The source emits late AND at a reduced rate. The link is untouched.
    ch["transport_s"] = A_TOTAL_LATENCY - 0.006 - 0.002
    ch["processing_s"] = 0.006
    ch["interval_s"] = 0.090


def _a2_communication_delay(sig, frac, t):
    _a_common(sig)
    if not _hold(sig, frac):
        return
    ch = sig["TIMING"][A_CHANNEL]
    # Same arrival lateness as A1. The source's rate is normal, and the LINK
    # reports the queue delay that A1's link does not.
    ch["transport_s"] = A_TOTAL_LATENCY - 0.006 - 0.002
    ch["processing_s"] = 0.006
    sig["COMMUNICATION"]["telemetry_radio"]["queue_delay_s"] = 1.20
    sig["COMMUNICATION"]["gnss_serial"]["queue_delay_s"] = 0.90


def _a3_compute_delay(sig, frac, t):
    _a_common(sig)
    if not _hold(sig, frac):
        return
    ch = sig["TIMING"][A_CHANNEL]
    ch["transport_s"] = 0.004
    ch["processing_s"] = A_TOTAL_LATENCY - 0.004 - 0.002
    # The process is alive and producing, and it is over its deadline.
    sig["COMPUTE"]["state_estimator"]["runtime_s"] = 0.045


def _a4_process_stall(sig, frac, t):
    _a_common(sig)
    if not _hold(sig, frac):
        return
    ch = sig["TIMING"][A_CHANNEL]
    ch["transport_s"] = 0.004
    ch["processing_s"] = A_TOTAL_LATENCY - 0.004 - 0.002
    # Identical timing split to A3. The heartbeat is what differs.
    sig["COMPUTE"]["state_estimator"]["heartbeat_age_s"] = 1.40
    sig["COMPUTE"]["state_estimator"]["output_age_s"] = 1.40


# ================================================================ SET B
def _b_command(sig, actuator="motor_0"):
    sig["ACTUATION"][actuator]["command"] = 0.60
    sig["ACTUATION"][actuator]["command_transmitted"] = 0.60


def _b1_command_lost(sig, frac, t):
    _b_command(sig)
    if not _hold(sig, frac):
        return
    sig["ACTUATION"]["motor_0"]["command_transmitted"] = 0.0
    sig["ACTUATION"]["motor_0"]["current_a"] = 0.2
    sig["ACTUATION"]["motor_0"]["rpm"] = 0.0
    sig["COMMUNICATION"]["esc_can"]["link_up"] = False


def _b2_power_path(sig, frac, t):
    _b_command(sig)
    if not _hold(sig, frac):
        return
    sig["ACTUATION"]["motor_0"]["current_a"] = 0.2
    sig["ACTUATION"]["motor_0"]["rpm"] = 0.0
    # The actuator declares POWER/battery; drop it past its droop limit.
    sig["POWER"]["battery"]["voltage_v"] = 21.0
    sig["POWER"]["battery"]["power_w"] = 21.0 * 15.0


def _b3_drive_no_current(sig, frac, t):
    _b_command(sig)
    if not _hold(sig, frac):
        return
    sig["ACTUATION"]["motor_0"]["current_a"] = 0.2
    sig["ACTUATION"]["motor_0"]["rpm"] = 0.0


def _b4_mechanical(sig, frac, t):
    _b_command(sig)
    if not _hold(sig, frac):
        return
    sig["ACTUATION"]["motor_0"]["current_a"] = 20.0
    sig["ACTUATION"]["motor_0"]["rpm"] = 200.0


def _b5_response_sensor(sig, frac, t):
    """The actuator is fine; the channel measuring it is not.

    On the multirotor this is BYTE-IDENTICAL to B4, and that is the point.
    """
    _b_command(sig)
    if not _hold(sig, frac):
        return
    sig["ACTUATION"]["motor_0"]["current_a"] = 20.0
    sig["ACTUATION"]["motor_0"]["rpm"] = 200.0


# -- the same five on the bench, which HAS an independent torque channel --
def _ts_b_command(sig):
    sig["ACTUATION"]["dyno_motor"]["command"] = 0.60
    sig["ACTUATION"]["dyno_motor"]["command_transmitted"] = 0.60


def _ts_b4_mechanical(sig, frac, t):
    _ts_b_command(sig)
    if not _hold(sig, frac):
        return
    m = sig["ACTUATION"]["dyno_motor"]
    m["current_a"] = 60.0
    m["rpm"] = 200.0
    m["torque_nm"] = 1.0          # the shaft really is not turning


def _ts_b5_response_sensor(sig, frac, t):
    _ts_b_command(sig)
    if not _hold(sig, frac):
        return
    m = sig["ACTUATION"]["dyno_motor"]
    m["current_a"] = 60.0
    m["rpm"] = 200.0
    m["torque_nm"] = 27.0         # torque says the shaft IS turning


# ================================================================ SET C
def _c1_independent(sig, frac, t):
    """Two sources adverse with nothing adverse shared.

    Uses the real v1.1 SHARED_SOURCE payload, whose two alarming sources are
    `battery` and `motor_esc`. Here nothing they depend on is adverse, so the
    honest answer is independent faults.
    """
    return


def _c2_shared_power(sig, frac, t):
    if not _hold(sig, frac):
        return
    sig["POWER"]["battery"]["voltage_v"] = 21.3
    sig["POWER"]["battery"]["power_w"] = 21.3 * 15.0


def _c3_shared_comm(sig, frac, t):
    if not _hold(sig, frac):
        return
    sig["COMMUNICATION"]["esc_can"]["link_up"] = False
    sig["COMMUNICATION"]["gnss_serial"]["link_up"] = False


def _c4_shared_compute(sig, frac, t):
    if not _hold(sig, frac):
        return
    sig["COMPUTE"]["cpu"]["cpu_load"] = 0.995
    sig["COMPUTE"]["state_estimator"]["runtime_s"] = 0.045


# ================================================================ SET D
def _d1_navigation_source(sig, frac, t):
    """The v1.1 fix-loss payload carries this one; nothing is injected."""
    return


def _d2_estimator_stale(sig, frac, t):
    if not _hold(sig, frac):
        return
    sig["COMPUTE"]["state_estimator"]["heartbeat_age_s"] = 1.20
    sig["COMPUTE"]["state_estimator"]["output_age_s"] = 1.20


def _d3_communication_starvation(sig, frac, t):
    if not _hold(sig, frac):
        return
    sig["COMMUNICATION"]["gnss_serial"]["link_up"] = False


def _d4_compute_deadline(sig, frac, t):
    if not _hold(sig, frac):
        return
    sig["TIMING"][A_CHANNEL]["processing_s"] = 0.060
    sig["COMPUTE"]["state_estimator"]["runtime_s"] = 0.045


# ================================================================== table
def _air(name, section, desc, expect, inject, variant="clean", tags=()):
    return Scenario(name=name, system="aircraft", section=section,
                    description=desc, expectation=expect, inject=inject,
                    v1_1_variant=variant, tags=("matched",) + tags,
                    nominal=AIRCRAFT_NOMINAL)


def _bench(name, section, desc, expect, inject, tags=()):
    return Scenario(name=name, system="test_stand", section=section,
                    description=desc, expectation=expect, inject=inject,
                    tags=("matched",) + tags, nominal=TEST_STAND_NOMINAL)


MATCHED_SCENARIOS = (
    # -- SET A: stale output, four causes, one symptom ------------------
    _air("MS_A1_SENSOR_DELAY", "7",
         "source emits late and at a reduced rate; link healthy",
         "OUTPUT_STALE localizes to SENSOR/source_slow; the link's own "
         "healthy evidence is what rules out the transport explanation",
         _a1_sensor_delay, tags=("set_a", "stale_output")),
    _air("MS_A2_COMMUNICATION_DELAY", "7",
         "identical arrival lateness to A1; source rate normal; link "
         "reports a large queue delay",
         "OUTPUT_STALE localizes to COMMUNICATION/transport_delay",
         _a2_communication_delay, tags=("set_a", "stale_output")),
    _air("MS_A3_COMPUTE_DELAY", "7",
         "processing over budget; process alive, producing, past deadline",
         "OUTPUT_STALE localizes to COMPUTE/processing_delay, not stall",
         _a3_compute_delay, tags=("set_a", "stale_output")),
    _air("MS_A4_PROCESS_STALL", "7",
         "identical timing split to A3; heartbeat and output age stale",
         "OUTPUT_STALE localizes to COMPUTE/process_stall, not delay",
         _a4_process_stall, tags=("set_a", "stale_output")),

    # -- SET B: no actuator response, five causes ----------------------
    _air("MS_B1_COMMAND_LOST", "8",
         "command requested but not transmitted; ESC link down",
         "COMMAND_NO_RESPONSE localizes to "
         "COMMUNICATION/command_not_delivered",
         _b1_command_lost, tags=("set_b", "actuator")),
    _air("MS_B2_POWER_PATH", "8",
         "command delivered; the actuator's declared power node is adverse",
         "COMMAND_NO_RESPONSE keeps POWER/path_unavailable; the drive "
         "hypothesis is not separable from it without a bus-voltage "
         "measurement at the actuator",
         _b2_power_path, tags=("set_b", "actuator")),
    _air("MS_B3_DRIVE_NO_CURRENT", "8",
         "command delivered, power healthy, no current drawn",
         "COMMAND_NO_RESPONSE localizes to ACTUATION/drive_no_current",
         _b3_drive_no_current, tags=("set_b", "actuator")),
    _air("MS_B4_MECHANICAL", "8",
         "current present, shaft not turning",
         "AMBIGUOUS between ACTUATION/mechanical and SENSOR/response_sensor: "
         "the multirotor has no independent physical channel",
         _b4_mechanical, tags=("set_b", "actuator", "irreducible")),
    _air("MS_B5_RESPONSE_SENSOR", "8",
         "byte-identical evidence to B4 on this platform",
         "the SAME ambiguous result as B4, which is the honest answer",
         _b5_response_sensor, tags=("set_b", "actuator", "irreducible")),
    _bench("MS_TS_B4_MECHANICAL", "8",
           "bench: current present, shaft not turning, torque absent",
           "SUPPORTED ACTUATION/mechanical -- the torque channel refutes the "
           "response-sensor alternative",
           _ts_b4_mechanical, tags=("set_b", "actuator")),
    _bench("MS_TS_B5_RESPONSE_SENSOR", "8",
           "bench: current present, rpm absent, torque NORMAL",
           "SUPPORTED SENSOR/response_sensor -- the same framework resolves "
           "what the multirotor cannot, because the bench instruments it",
           _ts_b5_response_sensor, tags=("set_b", "actuator")),

    # -- SET C: multiple sensors degraded ------------------------------
    _air("MS_C1_INDEPENDENT", "9",
         "two sources adverse; nothing they depend on is adverse",
         "SENSOR/independent_faults supported; no common cause claimed",
         _c1_independent, variant="shared_source",
         tags=("set_c", "multi_sensor")),
    _air("MS_C2_SHARED_POWER", "9",
         "the same two sources, and the power node they share is adverse",
         "POWER/shared_node supported; the independent explanation is "
         "refuted by the shared dependency",
         _c2_shared_power, variant="shared_source",
         tags=("set_c", "multi_sensor")),
    # C3 and C4 are NEGATIVE controls, and their expectations say so. The
    # only real v1.1 payload with two adverse sources has `battery` and
    # `motor_esc`, which share a POWER node and nothing else. A shared-link
    # or shared-compute common cause is therefore NOT CONSTRUCTIBLE from the
    # available real data, and the honest thing is to check that the model
    # declines to claim one rather than to fabricate a payload that would.
    _air("MS_C3_SHARED_COMM", "9",
         "both links are down, but the two adverse sources do not share a "
         "link: only motor_esc rides one",
         "SENSOR/independent_faults stays supported and NO shared-link "
         "common cause is claimed -- a negative control on §13",
         _c3_shared_comm, variant="shared_source",
         tags=("set_c", "multi_sensor", "negative_control")),
    _air("MS_C4_SHARED_COMPUTE", "9",
         "the CPU is saturated, and neither adverse source declares a "
         "compute dependency",
         "SENSOR/independent_faults stays supported. This is what the "
         "dependency model OMITS: v1.1 sources are raw and declare no "
         "compute node, so a shared-compute cause cannot be reached",
         _c4_shared_compute, variant="shared_source",
         tags=("set_c", "multi_sensor", "negative_control", "model_gap")),

    # -- SET D: position function failure ------------------------------
    _air("MS_D1_NAV_SOURCE", "10",
         "GNSS fix lost; compute, timing and communication healthy",
         "POSITION_UNAVAILABLE localizes to "
         "SENSOR/navigation_source_invalid",
         _d1_navigation_source, variant="fixloss",
         tags=("set_d", "position")),
    _air("MS_D2_ESTIMATOR_STALE", "10",
         "sources fresh; the estimating process stopped",
         "POSITION_UNAVAILABLE localizes to COMPUTE/estimator_stale",
         _d2_estimator_stale, tags=("set_d", "position")),
    _air("MS_D3_COMM_STARVATION", "10",
         "sources fresh; the GNSS link is down",
         "POSITION_UNAVAILABLE implicates COMMUNICATION/starvation",
         _d3_communication_starvation, tags=("set_d", "position")),
    _air("MS_D4_COMPUTE_DEADLINE", "10",
         "sources fresh; the nav channel misses its end-to-end deadline",
         "POSITION_UNAVAILABLE implicates TIMING/deadline_violation and "
         "COMPUTE, which are one event seen twice (§27)",
         _d4_compute_deadline, tags=("set_d", "position")),
)

MATCHED_BY_NAME = {s.name: s for s in MATCHED_SCENARIOS}

#: The sets §42's gate is evaluated over.
MATCHED_SETS = {
    "A_STALE_OUTPUT": ("MS_A1_SENSOR_DELAY", "MS_A2_COMMUNICATION_DELAY",
                       "MS_A3_COMPUTE_DELAY", "MS_A4_PROCESS_STALL"),
    "B_ACTUATOR_RESPONSE": ("MS_B1_COMMAND_LOST", "MS_B2_POWER_PATH",
                            "MS_B3_DRIVE_NO_CURRENT", "MS_B4_MECHANICAL",
                            "MS_B5_RESPONSE_SENSOR"),
    "B_ACTUATOR_RESPONSE_BENCH": ("MS_TS_B4_MECHANICAL",
                                  "MS_TS_B5_RESPONSE_SENSOR"),
    "C_MULTI_SENSOR": ("MS_C1_INDEPENDENT", "MS_C2_SHARED_POWER",
                       "MS_C3_SHARED_COMM", "MS_C4_SHARED_COMPUTE"),
    "D_POSITION_FUNCTION": ("MS_D1_NAV_SOURCE", "MS_D2_ESTIMATOR_STALE",
                            "MS_D3_COMM_STARVATION",
                            "MS_D4_COMPUTE_DEADLINE"),
}

#: The symptom each set is matched on. Every member must exhibit it.
SET_SYMPTOM = {
    "A_STALE_OUTPUT": "OUTPUT_STALE",
    "B_ACTUATOR_RESPONSE": "COMMAND_NO_RESPONSE",
    "B_ACTUATOR_RESPONSE_BENCH": "COMMAND_NO_RESPONSE",
    "C_MULTI_SENSOR": "MULTIPLE_SENSORS_DEGRADED",
    "D_POSITION_FUNCTION": "POSITION_UNAVAILABLE",
}

__all__ = ["MATCHED_SCENARIOS", "MATCHED_BY_NAME", "MATCHED_SETS",
           "SET_SYMPTOM", "A_TOTAL_LATENCY", "A_CHANNEL"]
