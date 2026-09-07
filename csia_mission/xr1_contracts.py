"""The XR-1 capability and product contract set, as data.

WHAT THIS IS
------------
A concrete, committed set of contracts for the assured infrastructure damage
assessment mission. It is the input the benchmark, the compiler and the
formal properties all run against, so it lives in one place rather than being
rebuilt in each.

WHAT IT IS NOT
--------------
It is not a claim that XR-1 has these capabilities. It is a claim about what
each capability WOULD REQUIRE. Nothing here has been demonstrated on hardware;
the vehicle does not exist yet.

THE DESIGN DECISION WORTH READING
-----------------------------------
`global_rgb_orthomosaic` and `relative_rgb_inspection` are SEPARATE products
that share evidence, rather than one product with a quality flag. And within
`bridge_rgb_inspection`, `imagery_quality` and `absolute_geolocation` have
DISJOINT requirement sets.

That is what makes losing GNSS remove the geolocation qualification and leave
the photograph. If the two properties shared a requirement list -- even
partially, even through a shared capability -- the loss would propagate and
the imagery would go with it. The independence is the mechanism, and it only
works because it was written down deliberately.
"""

from __future__ import annotations

from .capability import CapabilityContract
from .product import MissionProductContract, QualityRequirement

# ---------------------------------------------------------------------------
# evidence identifiers this contract set names.
#
# These are CANONICAL EVIDENCE IDS, not CSIA internal names. The mapping from
# a CSIA relation to one of these belongs in an adapter, so that the frozen
# core's vocabulary and the mission layer's vocabulary can each change without
# forcing the other.

EVIDENCE = (
    "attitude.supported",
    "imu.primary.supported",
    "imu.reference.supported",
    "airspeed.supported",
    "baro.altitude.supported",
    "gnss.position.supported",
    "gnss.velocity.supported",
    "mag.field.supported",
    "camera.rgb.available",
    "camera.rgb.calibration_valid",
    "camera.thermal.available",
    "camera.thermal.calibration_valid",
    "visual_odometry.supported",
    "camera_navigation_timing.supported",
    "timebase.supported",
    "power.telemetry.supported",
    "comms.telemetry_link.supported",
    "actuator.elevon.command_echo",
)


# ---------------------------------------------------------------------------
# capabilities

CAPABILITIES = (
    CapabilityContract(
        capability_id="timing",
        requires_all=("timebase.supported",),
        description="A shared timebase. Everything that correlates two "
                    "sensors rests on it, which is why it is a capability "
                    "rather than an assumption.",
    ),
    CapabilityContract(
        capability_id="attitude_hold",
        requires_all=("attitude.supported",),
        requires_one_of=(("imu.primary.supported",
                          "imu.reference.supported"),),
        requires_capabilities=("timing",),
        does_not_require=("gnss.position.supported",),
        description="Attitude does not need position, and saying so "
                    "explicitly is what stops a later edit adding it.",
    ),
    CapabilityContract(
        capability_id="altitude_hold",
        requires_all=("baro.altitude.supported",),
        requires_capabilities=("attitude_hold",),
        does_not_require=("gnss.position.supported",),
    ),
    CapabilityContract(
        capability_id="airspeed_regulation",
        requires_all=("airspeed.supported",),
        requires_capabilities=("attitude_hold",),
    ),
    CapabilityContract(
        capability_id="stable_flight",
        requires_capabilities=("attitude_hold", "altitude_hold"),
        requires_actuators=("elevon_left", "elevon_right"),
        description="The floor. Nothing else in this set means anything "
                    "without it.",
    ),
    CapabilityContract(
        capability_id="relative_navigation",
        requires_capabilities=("attitude_hold", "timing"),
        requires_one_of=(("visual_odometry.supported",
                          "imu.reference.supported"),),
        does_not_require=("gnss.position.supported",),
        description="The example from the brief, written as given: relative "
                    "navigation needs attitude and timing, one of two "
                    "sensing paths, and NOT global position.",
    ),
    CapabilityContract(
        capability_id="absolute_navigation",
        requires_all=("gnss.position.supported",),
        requires_capabilities=("attitude_hold", "timing"),
        description="The one capability that does need GNSS. Isolating it "
                    "here is what keeps the loss from spreading.",
    ),
    CapabilityContract(
        capability_id="controlled_glide",
        requires_capabilities=("attitude_hold",),
        requires_actuators=("elevon_left", "elevon_right"),
        degradation="UNPOWERED",
        description="DEPENDENCY SEMANTICS ONLY. This says what a controlled "
                    "glide would REQUIRE. It says nothing about whether XR-1 "
                    "can glide, which is an aerodynamic question no evidence "
                    "in this repository addresses.",
    ),
    CapabilityContract(
        capability_id="RGB_capture",
        requires_all=("camera.rgb.available",),
        requires_capabilities=("timing",),
    ),
    CapabilityContract(
        capability_id="thermal_capture",
        requires_all=("camera.thermal.available",),
        requires_capabilities=("timing",),
        does_not_require=("camera.rgb.available",),
        description="Independent of RGB by construction. An RGB payload "
                    "failure must not take thermal with it.",
    ),
    CapabilityContract(
        capability_id="local_mapping",
        requires_capabilities=("relative_navigation", "RGB_capture"),
        requires_compute=("mapping",),
        does_not_require=("gnss.position.supported",),
    ),
    CapabilityContract(
        capability_id="global_mapping",
        requires_capabilities=("absolute_navigation", "RGB_capture"),
        requires_compute=("mapping",),
    ),
    CapabilityContract(
        capability_id="telemetry_downlink",
        requires_all=("comms.telemetry_link.supported",),
        description="Named so that its LOSS can be shown to invalidate "
                    "nothing that does not depend on it.",
    ),
)


# ---------------------------------------------------------------------------
# products

PRODUCTS = (
    MissionProductContract(
        product_id="bridge_rgb_inspection",
        product_type="rgb_visual_inspection",
        requires_capabilities=("RGB_capture",),
        qualities=(
            QualityRequirement(
                property_name="imagery_quality",
                requires_all=("camera.rgb.calibration_valid",),
                requires_capabilities=("RGB_capture",),
                permits=("visual_damage_assessment",),
                prohibits_without=("any_use_of_this_imagery",),
            ),
            QualityRequirement(
                property_name="relative_geometry",
                requires_capabilities=("relative_navigation",),
                permits=("relative_crack_width_estimate",),
                prohibits_without=("relative_dimensional_measurement",),
            ),
            QualityRequirement(
                property_name="absolute_geolocation",
                requires_capabilities=("absolute_navigation",),
                permits=("georeferenced_defect_logging",),
                prohibits_without=("survey_grade_absolute_measurement",),
            ),
        ),
        description="The worked example. Losing GNSS removes ONLY "
                    "absolute_geolocation; the photograph and its relative "
                    "geometry survive, because their requirement sets do not "
                    "mention GNSS.",
    ),
    MissionProductContract(
        product_id="bridge_thermal_inspection",
        product_type="thermal_inspection",
        requires_capabilities=("thermal_capture",),
        qualities=(
            QualityRequirement(
                property_name="imagery_quality",
                requires_all=("camera.thermal.available",),
                permits=("thermal_anomaly_screening",),
                prohibits_without=("any_use_of_this_imagery",),
            ),
            QualityRequirement(
                property_name="radiometric_calibration",
                requires_all=("camera.thermal.calibration_valid",),
                permits=("absolute_temperature_estimate",),
                prohibits_without=("absolute_temperature_estimate",),
            ),
            QualityRequirement(
                property_name="thermal_alignment",
                requires_capabilities=("relative_navigation",),
                requires_all=("camera_navigation_timing.supported",),
                permits=("thermal_to_structure_registration",),
                prohibits_without=("thermal_to_structure_registration",),
            ),
        ),
        description="Shares no evidence with the RGB product except the "
                    "timebase. An RGB payload failure leaves it intact.",
    ),
    MissionProductContract(
        product_id="relative_reconstruction",
        product_type="relative_3d_reconstruction",
        requires_capabilities=("local_mapping",),
        qualities=(
            QualityRequirement(
                property_name="relative_geometry",
                requires_capabilities=("local_mapping",),
                permits=("relative_structural_comparison",),
                prohibits_without=("relative_structural_comparison",),
            ),
            QualityRequirement(
                property_name="temporal_consistency",
                requires_capabilities=("timing",),
                permits=("change_detection_between_passes",),
                prohibits_without=("change_detection_between_passes",),
            ),
        ),
    ),
    MissionProductContract(
        product_id="global_rgb_orthomosaic",
        product_type="absolute_georeferenced_map",
        requires_capabilities=("global_mapping",),
        requires_all=("camera.rgb.calibration_valid",
                      "camera_navigation_timing.supported"),
        qualities=(
            QualityRequirement(
                property_name="absolute_geolocation",
                requires_capabilities=("absolute_navigation",),
                permits=("georeferenced_asset_mapping",),
                prohibits_without=("georeferenced_asset_mapping",),
            ),
            QualityRequirement(
                property_name="survey_grade",
                requires_capabilities=("absolute_navigation",),
                requires_all=("gnss.velocity.supported",),
                permits=("survey_grade_absolute_measurement",),
                prohibits_without=("survey_grade_absolute_measurement",),
            ),
        ),
        description="The product that SHOULD collapse when GNSS support "
                    "goes. Its base requirements name the mapping capability "
                    "that needs absolute navigation, so the collapse is "
                    "structural rather than a special case.",
    ),
    MissionProductContract(
        product_id="raw_evidence_package",
        product_type="raw_evidence_archive",
        qualities=(
            QualityRequirement(
                property_name="temporal_consistency",
                requires_capabilities=("timing",),
                permits=("post_flight_analysis",),
                prohibits_without=("cross_sensor_correlation",),
            ),
        ),
        description="DEPENDS ON ALMOST NOTHING, ON PURPOSE. Raw evidence is "
                    "preserved even when every qualification is gone -- the "
                    "programme's rule is that raw evidence is archived "
                    "before reduction, and a product layer that could "
                    "invalidate the archive would contradict it.",
    ),
)


def vehicle_profile() -> dict:
    """What the XR-1 draft configuration declares it provides.

    Used by the compiler to reject a dependency nothing provides. It is a
    DECLARATION, not a measurement: no hardware exists.
    """
    return {
        "profile_id": "xr1_draft_non_flight",
        "status": "NON_FLIGHT_DRAFT",
        "provides_evidence": sorted(EVIDENCE),
        "provides_compute": ["mapping", "logging"],
        "provides_actuators": ["elevon_left", "elevon_right",
                               "elevon_outer_left", "elevon_outer_right"],
    }
