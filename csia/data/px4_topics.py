"""PX4 assurance-topic registry (ACEG slice 2, Part 6).

Declares every ULog topic CSIA ingests for assurance, what evidence it
carries, and how absence is handled. ABSENCE IS NEVER ZERO: a topic or field
that is not present is recorded as unavailable, and every consumer must
handle that state explicitly.

PX4 version differences are recorded per topic in `since`/`notes` — these are
from the PUBLISHED PX4 message definitions, not locally verified against
every firmware (no real corpus is locally available; see acquisition status).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TopicSpec:
    name: str
    multi_instance: bool
    assurance_role: str
    key_fields: tuple
    device_id_fields: tuple = ()
    flag_fields: tuple = ()
    reset_fields: tuple = ()
    since: str = "UNKNOWN"
    notes: str = ""


#: The Part-6 registry. `key_fields` are ingested when present; missing
#: fields yield nulls with a missingness mask, never zeros.
PX4_ASSURANCE_TOPICS = (
    TopicSpec("estimator_innovations", True, "estimator-vs-sensor residuals",
              ("gps_hvel[0]", "gps_hvel[1]", "gps_vvel",
               "gps_hpos[0]", "gps_hpos[1]", "gps_vpos")),
    TopicSpec("estimator_innovation_variances", True,
              "innovation scale for normalized residuals",
              ("gps_hvel[0]", "gps_hvel[1]", "gps_vpos")),
    TopicSpec("estimator_innovation_test_ratios", True,
              "PX4's own gate ratios — independent estimator consistency",
              ("gps_hvel[0]", "gps_vpos", "mag_field[0]")),
    TopicSpec("estimator_status", True, "estimator health",
              ("test_ratio[0]", "test_ratio[1]", "test_ratio[2]",
               "pos_horiz_accuracy", "pos_vert_accuracy"),
              flag_fields=("filter_fault_flags", "innovation_check_flags"),
              reset_fields=("reset_count_vel_ne", "reset_count_pos_ne")),
    TopicSpec("estimator_status_flags", True, "decomposed estimator flags",
              (), flag_fields=("cs_gps", "cs_baro_hgt", "cs_mag_hdg"),
              since="v1.12"),
    TopicSpec("estimator_event_flags", True, "estimator warning/info events",
              (), flag_fields=("warning_event_changes",), since="v1.12"),
    TopicSpec("estimator_selector_status", False,
              "which estimator instance is primary",
              ("primary_instance",), since="v1.12",
              notes="multi-EKF selector; absent on single-EKF builds"),
    TopicSpec("vehicle_local_position", False, "fused local state",
              ("x", "y", "z", "vx", "vy", "vz", "eph", "epv"),
              flag_fields=("xy_valid", "v_xy_valid")),
    TopicSpec("vehicle_global_position", False, "fused global state",
              ("lat", "lon", "alt", "eph", "epv")),
    TopicSpec("vehicle_attitude", False, "fused attitude", ("q[0]", "q[1]",
              "q[2]", "q[3]")),
    TopicSpec("sensor_combined", False, "legacy combined IMU",
              ("accelerometer_m_s2[0]", "accelerometer_m_s2[1]",
               "accelerometer_m_s2[2]", "gyro_rad[0]", "gyro_rad[1]",
               "gyro_rad[2]"),
              notes="superseded by vehicle_imu instances on newer firmware"),
    TopicSpec("vehicle_imu", True, "per-instrument IMU",
              ("delta_velocity[0]", "delta_velocity[1]", "delta_velocity[2]",
               "delta_angle[0]", "delta_angle[1]", "delta_angle[2]"),
              device_id_fields=("accel_device_id", "gyro_device_id"),
              flag_fields=("delta_velocity_clipping",), since="v1.11"),
    TopicSpec("sensor_gps", True, "raw GNSS",
              ("lat", "lon", "alt", "vel_n_m_s", "vel_e_m_s", "vel_d_m_s",
               "eph", "epv", "satellites_used", "fix_type"),
              device_id_fields=("device_id",)),
    TopicSpec("sensor_mag", True, "raw magnetometer",
              ("x", "y", "z"), device_id_fields=("device_id",)),
    TopicSpec("sensor_baro", True, "raw barometer",
              ("pressure", "temperature"), device_id_fields=("device_id",)),
    TopicSpec("battery_status", True, "pack electrical state",
              ("voltage_v", "current_a", "remaining"),
              flag_fields=("warning",)),
    TopicSpec("system_power", False, "RAIL voltages — the signal whose "
              "absence blocked slice 3E's sensor-rail hypothesis",
              ("voltage5v_v",), flag_fields=("brick_valid", "usb_connected"),
              notes="v1.14 adds sensors3v3; older logs may lack the topic "
                    "entirely"),
    TopicSpec("power_monitor", True, "external power monitor", ("voltage_v",
              "current_a"), since="v1.13", notes="rarely logged"),
    TopicSpec("failure_detector_status", False, "PX4 failure detector",
              (), flag_fields=("fd_roll", "fd_pitch", "fd_ext")),
    TopicSpec("sensors_status_imu", False, "per-IMU inconsistency scores",
              ("accel_inconsistency_m_s_s[0]",), since="v1.12"),
    TopicSpec("sensor_correction", False, "thermal corrections applied",
              ()),
    TopicSpec("vehicle_status", False, "arming/nav state",
              ("arming_state", "nav_state"),
              notes="armed-state gating source; absence disables exposure "
                    "accounting for the flight"),
    TopicSpec("actuator_outputs", True, "commanded outputs", ("output[0]",)),
    TopicSpec("actuator_motors", False, "motor setpoints", ("control[0]",),
              since="v1.13"),
    TopicSpec("control_allocator_status", True, "allocation saturation",
              (), flag_fields=("torque_setpoint_achieved",), since="v1.13"),
)

TOPIC_INDEX = {t.name: t for t in PX4_ASSURANCE_TOPICS}


@dataclass
class TopicAvailability:
    """What a specific log actually provided. Absence != zero, ever."""
    present: dict = field(default_factory=dict)    # name -> [instances]
    absent: list = field(default_factory=list)
    fields_missing: dict = field(default_factory=dict)  # (name,inst) -> [fields]

    def to_dict(self):
        return {"present": self.present, "absent": self.absent,
                "fields_missing": {f"{k[0]}#{k[1]}": v
                                   for k, v in self.fields_missing.items()}}


def survey_ulog(ulog) -> TopicAvailability:
    """Inventory a pyulog.ULog against the assurance registry."""
    av = TopicAvailability()
    have = {}
    for d in ulog.data_list:
        have.setdefault(d.name, []).append(d.multi_id)
    for spec in PX4_ASSURANCE_TOPICS:
        if spec.name in have:
            av.present[spec.name] = sorted(have[spec.name])
            for d in ulog.data_list:
                if d.name != spec.name:
                    continue
                missing = [f for f in spec.key_fields if f not in d.data]
                if missing:
                    av.fields_missing[(spec.name, d.multi_id)] = missing
        else:
            av.absent.append(spec.name)
    return av
