"""Build the canonical dataset manifest, dedup report and exposure account.

    python tools/build_dataset_manifest.py

Slice 3A. Source of record is whichever exists:
  * ``data/real_logs/*.ulg`` if the corpus has been fetched (hashes computed
    from file content), otherwise
  * ``data/real_logs_report.json``, the committed campaign artifact, which
    carries per-flight duration, sensor inventory and alert transitions but
    NO file content — so ``content_sha256`` is recorded as null rather than
    invented, and every such log is flagged as not-yet-acquired.

Classification is deliberately conservative. Every log in the public PX4
Flight Review corpus is UNANNOTATED: nobody has certified those flights
healthy, and "CSIA raised no alert" cannot be used as evidence of health —
that is the hypothesis under test.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.datasets import (AnnotationStatus, Confidentiality,  # noqa: E402
                           HealthClassification, LogManifest, Partition,
                           Redistribution, SourceType, check_split_leakage,
                           check_tuning_not_heldout, dataset_aggregate_hash,
                           find_exact_duplicates,
                           find_suspected_near_duplicates, save_manifests,
                           sha256_file, stable_log_id, verify_files)
from csia.experiments import EvidenceEnvironment, build  # noqa: E402
from csia.metrics import alert_episodes  # noqa: E402
from csia.metrics.exposure import account, rate_report  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
REPORT = os.path.join(ROOT, "data", "real_logs_report.json")
LOGDIR = os.path.join(ROOT, "data", "real_logs")
DATASET_ID = "px4_public_v1"
SOURCE_URL = "https://review.px4.io/download_log?log={uuid}"

# Offline-validation posture used by `csia analyze-logs` (cli.py).
ARM_TIME_S = 20.0
REQUIRED_FOR_FULL_GRAPH = 8


def build_manifests():
    with open(REPORT) as fh:
        report = json.load(fh)

    manifests = []
    for f in report["flights"]:
        log_id = stable_log_id(f["log"])
        path = os.path.join(LOGDIR, f["log"])
        present = os.path.exists(path)

        sensors = list(f.get("sensors", []))
        excluded_ch = list(f.get("excluded_channels", {}))
        duration = float(f["duration_s"])
        episodes = len(alert_episodes(f.get("transitions", [])))

        m = LogManifest(
            log_id=log_id,
            dataset_id=DATASET_ID,
            content_sha256=sha256_file(path) if present else None,
            byte_size=os.path.getsize(path) if present else None,
            source_type=SourceType.REAL_FLIGHT.value,
            source_reference=SOURCE_URL.format(uuid=log_id),
            autopilot="PX4",
            # Not present in the campaign artifact and NOT inferable.
            firmware_version=None,
            airframe_type=None,
            vehicle_id=None,
            flight_duration_s=duration,
            monitored_duration_s=max(0.0, duration - ARM_TIME_S),
            sensor_inventory=sensors,
            available_channels=sensors,
            missing_channels=excluded_ch,
            annotation_status=AnnotationStatus.UNANNOTATED.value,
            # The core correction of this slice.
            health_classification=HealthClassification.UNANNOTATED.value,
            confidentiality=Confidentiality.PUBLIC.value,
            # Public to VIEW is not permission to REDISTRIBUTE. Unverified.
            redistribution_permission=Redistribution.UNKNOWN.value,
            license=None,
            file_present=present,
            parse_status="PARSED_IN_COMMITTED_CAMPAIGN" if not present
                         else "PRESENT_UNVERIFIED",
            alert_episodes=episodes,
        )

        # Every one of these logs was inspected while CSIA's field-mode
        # tolerances and offline failsafe posture were being developed, so
        # none of them is blind, and none may be held out.
        m.used_for_threshold_tuning = True
        m.used_for_architecture_design = True
        m.eligible_for_blind_evaluation = False
        m.dataset_partition = Partition.DEVELOPMENT.value
        m.split_group_id = f"px4_public_v1_all"   # one campaign, one group
        m.notes.append(
            "seen during field_mode / offline-posture development (C2 "
            "train-test contamination): not eligible for held-out or blind use")
        if not present:
            m.notes.append("file not acquired in this environment; "
                           "content hash unknown")
        if len(sensors) < REQUIRED_FOR_FULL_GRAPH:
            m.notes.append(
                f"{len(sensors)}/8 trust-graph nodes carried usable data; "
                "the graph ran degraded")
        manifests.append(m)
    return manifests, report


def main() -> int:
    manifests, report = build_manifests()

    exact = find_exact_duplicates(manifests)
    for ids in exact.values():                     # keep first, mark the rest
        for dup in ids[1:]:
            for m in manifests:
                if m.log_id == dup:
                    m.duplicate_of = ids[0]
                    m.notes.append(f"exact content duplicate of {ids[0]}")
    near = find_suspected_near_duplicates(manifests)
    for pair in near:
        for m in manifests:
            if m.log_id == pair["log_a"]:
                m.suspected_near_duplicate_of.append(pair["log_b"])
            elif m.log_id == pair["log_b"]:
                m.suspected_near_duplicate_of.append(pair["log_a"])

    leakage = check_split_leakage(manifests)
    contamination = check_tuning_not_heldout(manifests)
    integrity = verify_files(manifests, LOGDIR)
    acc = account(manifests, ARM_TIME_S)

    agg = dataset_aggregate_hash(manifests)
    man = build("dataset_manifest",
                EvidenceEnvironment.REAL_LOG_REPLAY,
                dataset_id=DATASET_ID,
                dataset_aggregate_hash=agg,
                dataset_partition=Partition.DEVELOPMENT.value,
                input_logs=[{"log_id": m.log_id, "sha256": m.content_sha256}
                            for m in manifests],
                output_paths=["datasets/manifests/px4_public_v1.json",
                              "datasets/reports/deduplication_report.json",
                              "datasets/reports/exposure_v2.json"])

    save_manifests(manifests, os.path.join(ROOT, "datasets", "manifests",
                                           f"{DATASET_ID}.json"),
                   DATASET_ID,
                   notes=["health_classification is UNANNOTATED for every log: "
                          "no annotation exists and absence of an alert is not "
                          "evidence of health",
                          "content hashes are null where the corpus has not "
                          "been acquired in this environment"])

    dedup = {"dataset_id": DATASET_ID, "dataset_aggregate_hash": agg,
             "exact_duplicates": exact,
             "exact_duplicate_log_count": sum(len(v) - 1 for v in exact.values()),
             "suspected_near_duplicates": near,
             "integrity": integrity,
             "note": "nothing is deleted or auto-excluded; near-duplicates are "
                     "review candidates only"}
    with open(os.path.join(ROOT, "datasets", "reports",
                           "deduplication_report.json"), "w") as fh:
        json.dump(dedup, fh, indent=1, sort_keys=True)

    rates = {c: rate_report(manifests, c, ARM_TIME_S)
             for c in (HealthClassification.UNANNOTATED.value,
                       HealthClassification.VERIFIED_HEALTHY.value)}
    exposure = {
        "result_schema_version": "1.0.0",
        "result_type": "EXPOSURE",
        "evidence_environment": EvidenceEnvironment.REAL_LOG_REPLAY.value,
        "experiment_manifest": man.to_dict(),
        "payload": {
            "dataset_id": DATASET_ID, "dataset_aggregate_hash": agg,
            "arm_time_s": ARM_TIME_S,
            "exposure": acc.to_dict(),
            "rates_by_health_category": rates,
            "leakage": leakage, "contamination": contamination,
            "historical_result_preserved": {
                "source": "data/real_logs_report.json",
                "logs": len(report["flights"]),
                "raw_hours": report["total_hours"],
                "note": "historical artifact retained unmodified"},
        }}
    with open(os.path.join(ROOT, "datasets", "reports",
                           "exposure_v2.json"), "w") as fh:
        json.dump(exposure, fh, indent=1, sort_keys=True)

    print(f"logs                    : {len(manifests)}")
    print(f"exact duplicates        : {dedup['exact_duplicate_log_count']}")
    print(f"near-dup candidates     : {len(near)}")
    print(f"not yet acquired        : {len(integrity['not_yet_acquired'])}")
    print(f"raw hours               : {acc.total_raw_hours:.4f}")
    print(f"monitored hours         : {acc.total_monitored_hours:.4f}")
    print(f"unmonitored (arm gate)  : {acc.unmonitored_hours:.4f}")
    print(f"VERIFIED_HEALTHY hours  : "
          f"{acc.by_health.get('VERIFIED_HEALTHY', 0.0):.4f}")
    print(f"UNANNOTATED hours       : "
          f"{acc.by_health.get('UNANNOTATED', 0.0):.4f}")
    print(f"leakage findings        : {len(leakage)}")
    print(f"contamination findings  : {len(contamination)}")
    print(f"dataset aggregate hash  : {agg[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
