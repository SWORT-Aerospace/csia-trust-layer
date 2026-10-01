"""The XSYS-001 witnesses as evidence producers: physical cross-domain evidence.

**Wrapped, not re-implemented.** The frozen pipeline
(`research/xsys_confirmatory_001/pipeline`) decides everything:
- `stage1_evidence.plan` decides which witness a variant consults at a
  checkpoint, and from which window;
- `xsys_v2_adapter.records_for` builds the records;
- the sealed stage-1 features (`STAGE1.json`) supply the values.

The adapter adds only what admissibility needs: the producer, its lineage,
the content time and the validated window.

| witness | producer | record | lineage | validated window (relative to onset) |
|---|---|---|---|---|
| W_RPM | `xsys:w_rpm` | ACTUATION/motor_m `xsys.rpm_response` | `channel:esc_rpm.motor_m`, `channel:motor_command.motor_m` | T1 and T3: [0, 15] s |
| W_DYN | `xsys:w_dyn` | NAVIGATION/motor_m `xsys.dynamics_T1` | `sensor:gyro.<id>`, `calibration:rotor_geometry` | T1 only: [0, 0.2] s |
| W_CTRL | `xsys:w_ctrl` | CONTROL/motor_m `xsys.compensation_T3` | `channel:motor_command.motor_m`, `model:px4_rate_controller`, `model:ekf2`, `sensor:gyro.<id>` | T3 only: [10, 15] s |

**Where the lineage comes from** (`xsys_extract.load_full`):
- W_RPM compares `esc_status` RPM with `actuator_outputs_sim`, the motor
  command;
- W_DYN projects `sensor_combined` gyro rates on the loss axis given by the
  `CA_ROTOR*` geometry;
- W_CTRL reads the allocator's `actuator_motors`, the same command, which the
  rate controller computes from the gyro rates, with EKF2's bias estimate and
  attitude.

So W_CTRL shares a root with each of the other two, and W_DYN and W_RPM share
none. This is structure, not a measured correlation (amendment A1 studied
the statistics).

**THE VALIDITY LESSON.** XSYS-001 validated each witness in a fixed window.
The contract states exactly that rule (`validity.event_window_s`); it does
not replace it with a compensation-state rule that was never validated.
- A T1 dynamics result held to C3 is still valid: content in [0, 0.2] s,
  although 14.8 s old.
- The same statistic over T3 (the V4_INVALID_WINDOW variant) is
  REGIME_INVALID and never reaches the core.

**Content time** is the end of the window the statistic covers: T1 → 0.2 s,
T3 → 15 s. Produced time is the checkpoint: C1 → 0.2 s, C3 → 15 s.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..envelope import EvidenceEnvelope
from ..health import ProducerHealth
from ..lineage import Lineage

REPO = Path(__file__).resolve().parents[2]
PIPELINE = REPO / "research/xsys_confirmatory_001/pipeline"
CAMPAIGN = REPO / "research/xsys_001_confirmatory_campaign"
ONSET = "xsys.onset"
CONTRACT_VERSION = "xsys-witness-1"
CHECKPOINT_T = {"C1": 0.2, "C3": 15.0}
#: The SIH gyro the XSYS-001 vehicle used (`sensor_selection.gyro_device_id`,
#: identical in every campaign flight; checked by the dataset H script).
XSYS_GYRO_DEVICE_ID = 1310988

WITNESSES = {
    # name: (producer id, claim, record domain, relation attribute in xsys_v2_adapter)
    "rpm": ("xsys:w_rpm", "RPM_DEFICIT", "ACTUATION", "REL_RPM"),
    "dyn": ("xsys:w_dyn", "DYN_RESPONSE", "NAVIGATION", "REL_DYN"),
    "ctrl": ("xsys:w_ctrl", "CTRL_COMPENSATION", "CONTROL", "REL_CTRL"),
}
CONTRACT_FILES = ("xsys_w_rpm", "xsys_w_dyn", "xsys_w_ctrl")


def pipeline():
    """The frozen pipeline modules (stage1_evidence, xsys_v2_adapter, xsys_features)."""
    if str(PIPELINE) not in sys.path:
        sys.path.insert(0, str(PIPELINE))
    import stage1_evidence as S1
    import xsys_features as XF
    import xsys_v2_adapter as XA
    return S1, XA, XF


def frozen_version() -> str:
    """The A2 freeze the confirmatory run was executed under (KEY.json)."""
    key = json.loads((CAMPAIGN / "stage0/KEY.json").read_text())
    return "xsys001-a2-" + key["freeze_manifest_sha256"][:12]


def lineage(witness: str, subject: str, gyro_id=XSYS_GYRO_DEVICE_ID) -> Lineage:
    gyro = f"sensor:gyro.{int(gyro_id)}"
    if witness == "rpm":
        return Lineage.of(f"channel:esc_rpm.{subject}", f"channel:motor_command.{subject}")
    if witness == "dyn":
        return Lineage.of(gyro, "calibration:rotor_geometry")
    return Lineage.of(f"channel:motor_command.{subject}", "model:px4_rate_controller",
                      "model:ekf2", gyro)


def content_time(window_label: str) -> float | None:
    """End of the window a statistic covers; None for a witness not consulted."""
    _S1, _XA, XF = pipeline()
    if window_label.startswith("T1"):
        return float(XF.WINDOWS["T1"][1])
    if window_label.startswith("T3"):
        return float(XF.WINDOWS["T3"][1])
    return None


def envelopes(subject: str, features: dict, variant: str, checkpoint: str,
              gyro_id=XSYS_GYRO_DEVICE_ID, version: str | None = None) -> list:
    """The witness outputs a variant consults at a checkpoint, for one
    subject, exactly as the frozen harness builds them."""
    S1, XA, _XF = pipeline()
    version = version or frozen_version()
    f = features
    rpm, dyn, ctrl, w = S1.plan(variant, checkpoint, f)
    stats = {"L": f["L_T1"] if checkpoint == "C1" else f["L_T3"],
             "D": f["D_T3"] if variant == "V4_INVALID_WINDOW" else f["D_T1"],
             "C": f["C_T3"]}
    recs = XA.records_for(subject, rpm, dyn, ctrl, stats, w)
    by_rel = {r.relation: r for r in recs}
    out = []
    for name, (pid, claim, _dom, rel_attr) in WITNESSES.items():
        ct = content_time(w[name])
        if ct is None:
            continue
        out.append(EvidenceEnvelope(
            producer_id=pid, producer_version=version, contract_version=CONTRACT_VERSION,
            claim=claim, record=by_rel[getattr(XA, rel_attr)],
            lineage=lineage(name, subject, gyro_id), content_time=ct,
            producer_health=ProducerHealth.VALID, produced_time=CHECKPOINT_T[checkpoint],
            detail={"window": w[name]}))
    return out


def contracts_dict(version: str | None = None) -> dict:
    """The three witness contracts, as written to `contracts/`."""
    _S1, XA, XF = pipeline()
    version = version or frozen_version()
    t1, t3 = XF.WINDOWS["T1"], XF.WINDOWS["T3"]
    spec = {
        "rpm": ("the RPM telemetry implies less thrust than the command (VIOLATED), or not "
                "(NOMINAL): the local ESC-monitor symptom. It does not say whether the rotor or "
                "the RPM channel is at fault", "ACTUATION", XA.REL_RPM, [t1[0], t3[1]],
                ["channel:esc_rpm.<motor>", "channel:motor_command.<motor>"]),
        "dyn": ("in T1 the body rates show no response along the motor's thrust-loss axis "
                "(NOMINAL) or show one (VIOLATED), when the local symptom implies a genuine loss "
                "would be detectable", "NAVIGATION", XA.REL_DYN, list(t1),
                ["sensor:gyro.<id>", "calibration:rotor_geometry"]),
        "ctrl": ("in T3 the controller shows no compensation on the motor (NOMINAL) or shows "
                 "it (VIOLATED), when the local symptom implies a genuine loss would be "
                 "detectable", "CONTROL", XA.REL_CTRL, list(t3),
                 ["channel:motor_command.<motor>", "model:px4_rate_controller", "model:ekf2",
                  "sensor:gyro.<id>"]),
    }
    out = {}
    for name, (pid, claim, _dom, _rel) in WITNESSES.items():
        meaning, dom, rel, window, lin = spec[name]
        out[name] = {
            "schema": "csia.evidence_contract/1",
            "producer_id": pid, "producer_version": version,
            "contract_version": CONTRACT_VERSION,
            "claims": {claim: {"meaning": meaning, "domain": dom, "relation": rel,
                               "attributable": False}},
            "lineage": "PER_OUTPUT", "lineage_rule": lin,
            "update": {"mode": "SAMPLE_AND_HOLD", "period_s": None},
            "validity": {"event_window_s": window, "relative_to": ONSET},
            "validity_rule": "the window XSYS-001 validated this witness in "
                             "(xsys_features.WINDOWS); content time is the window's end",
            "health_reporting": "IN_PROCESS",
            "profile_compatibility": [
                "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py"],
            "expected_inputs": ["the sealed stage-1 features (STAGE1.json)",
                                "stage1_evidence.plan for the variant and checkpoint"],
            "fault_behavior": "a statistic that cannot be computed is NOT_APPLICABLE "
                              "(xsys_v2_adapter._state_from)",
        }
    return out
