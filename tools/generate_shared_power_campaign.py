"""Generate and FREEZE the partitioned shared-power generalization campaign.

    python tools/generate_shared_power_campaign.py

Slice 3C Part 2. Run BEFORE any algorithm change. Partition assignment is
derived from a SHA-256 of the scenario id + campaign seed — never from
observed CSIA performance, which is how the previous held-out set was burned.

Scenario families:
  POSITIVE_SHARED_POWER   one resource degrades several sources
  NEGATIVE_INDEPENDENT    several sources degrade without a shared path
  NEGATIVE_SINGLE_SOURCE  one source only
  NEGATIVE_HEALTHY        clean or unusual-but-healthy flight

Partitions: DEVELOPMENT / VALIDATION / ADVERSARIAL / BLIND_SYNTHETIC.
ADVERSARIAL is assigned by construction (deliberately hard cases), the rest by
hash. No exact parameter tuple may appear in two partitions.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.experiments import EvidenceEnvironment, build  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
CAMPAIGN_ID = "shared_power_generalization_v1"
CAMPAIGN_SEED = "csia-3c-2026-08-03"
SCHEMA_VERSION = "1.0.0"

# Hash-share of non-adversarial scenarios per partition.
SPLIT = (("DEVELOPMENT", 0.45), ("VALIDATION", 0.25), ("BLIND_SYNTHETIC", 0.30))


def scenario_hash(sid: str) -> str:
    return hashlib.sha256(f"{CAMPAIGN_SEED}:{sid}".encode()).hexdigest()


def assign_partition(sid: str, adversarial: bool) -> str:
    """Deterministic, metadata-only. Never performance-derived.

    NOTE: superseded by stratify(), which assigns by rank WITHIN each family
    so every partition contains positives, independent negatives, single-source
    negatives and healthy negatives. Kept for the unstratified hash share.
    """
    if adversarial:
        return "ADVERSARIAL"
    x = int(scenario_hash(sid)[:8], 16) / 0xFFFFFFFF
    acc = 0.0
    for name, share in SPLIT:
        acc += share
        if x < acc:
            return name
    return SPLIT[-1][0]


def stratify(rows):
    """Assign partitions by hash RANK within each family.

    Plain hash-share left BLIND_SYNTHETIC with no healthy and no single-source
    negatives, which would make a blind false-positive rate unmeasurable.
    Stratifying keeps assignment deterministic and metadata-only while
    guaranteeing every family appears in every partition.
    """
    fams = {}
    for r in rows:
        if r["adversarial"]:
            r["dataset_partition"] = "ADVERSARIAL"
            continue
        fams.setdefault(r["family"], []).append(r)
    for fam, items in fams.items():
        items.sort(key=lambda r: r["scenario_sha256"])
        n = len(items)
        bounds, acc = [], 0.0
        for name, share in SPLIT:
            acc += share
            bounds.append((name, int(round(acc * n))))
        i = 0
        for name, upto in bounds:
            while i < upto and i < n:
                items[i]["dataset_partition"] = name
                i += 1
        while i < n:
            items[i]["dataset_partition"] = SPLIT[-1][0]
            i += 1
    return rows


def sid(family, **params):
    body = ",".join(f"{k}={params[k]}" for k in sorted(params))
    return f"{family}|{body}"


def scenarios():
    out = []

    def add(family, adversarial=False, **p):
        s = sid(family, **p)
        out.append({
            "scenario_id": s,
            "scenario_sha256": scenario_hash(s),
            "family": family,
            "params": p,
            "adversarial": adversarial,
            "dataset_partition": assign_partition(s, adversarial),
            "expected_shared_resource":
                "MAIN_POWER_PACK" if family == "POSITIVE_SHARED_POWER" else None,
            "expected_affected_sources":
                p.get("_truth", ["battery", "motor_esc"]
                      if family == "POSITIVE_SHARED_POWER" else []),
        })

    # --- POSITIVE: shared power, ratios varied INDEPENDENTLY ---------------
    # Ratio ranges deliberately overlap across partitions so membership
    # cannot be inferred from any single parameter.
    for depth in (0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.1, 2.4):
        for rpm in (100.0, 180.0, 260.0, 350.0, 450.0, 560.0, 650.0):
            add("POSITIVE_SHARED_POWER", depth_v=depth, rpm_loss=rpm,
                onset=30.0, dur=6.0, delay=0.0,
                _truth=["battery", "motor_esc"])
    # onset / duration / propagation delay
    for onset in (18.0, 24.0, 30.0, 36.0, 42.0):
        for delay in (0.0, 0.4, 1.2, 2.5):
            add("POSITIVE_SHARED_POWER", depth_v=1.1, rpm_loss=300.0,
                onset=onset, dur=8.0, delay=delay,
                _truth=["battery", "motor_esc"])
    for dur in (3.0, 5.0, 9.0, 14.0):
        add("POSITIVE_SHARED_POWER", depth_v=1.3, rpm_loss=280.0,
            onset=28.0, dur=dur, delay=0.0, _truth=["battery", "motor_esc"])

    # --- ADVERSARIAL positives: extreme / inverse severity -----------------
    for depth, rpm in ((2.4, 100.0), (0.4, 650.0), (2.4, 650.0), (0.4, 100.0)):
        add("POSITIVE_SHARED_POWER", adversarial=True, depth_v=depth,
            rpm_loss=rpm, onset=31.0, dur=7.0, delay=0.0,
            _truth=["battery", "motor_esc"])
    # late / weak second source
    for delay in (4.0, 6.0):
        add("POSITIVE_SHARED_POWER", adversarial=True, depth_v=1.2,
            rpm_loss=200.0, onset=30.0, dur=10.0, delay=delay,
            _truth=["battery", "motor_esc"])

    # --- NEGATIVE: single source only --------------------------------------
    for depth in (0.8, 1.4, 2.0):
        add("NEGATIVE_SINGLE_SOURCE", depth_v=depth, rpm_loss=0.0,
            onset=30.0, dur=6.0, delay=0.0, _truth=["battery"])
    for rpm in (200.0, 400.0, 600.0):
        add("NEGATIVE_SINGLE_SOURCE", depth_v=0.0, rpm_loss=rpm,
            onset=30.0, dur=6.0, delay=0.0, _truth=["motor_esc"])

    # --- NEGATIVE: independent faults (no shared path) ---------------------
    for o0, o1 in ((25.0, 27.0), (25.0, 25.2), (25.0, 33.0), (20.0, 21.0)):
        add("NEGATIVE_INDEPENDENT", imu0_onset=o0, imu1_onset=o1,
            r0=0.18, r1=-0.15, _truth=["imu0", "imu1"])
    for r0, r1 in ((0.16, -0.16), (0.22, -0.10)):
        add("NEGATIVE_INDEPENDENT", adversarial=True, imu0_onset=26.0,
            imu1_onset=26.1, r0=r0, r1=r1, _truth=["imu0", "imu1"])
    # unrelated single-source faults that must never read as shared power
    add("NEGATIVE_INDEPENDENT", mag_emi=True, _truth=["mag"])
    add("NEGATIVE_INDEPENDENT", gps_spoof=True, _truth=["gps"])

    # --- NEGATIVE: healthy --------------------------------------------------
    add("NEGATIVE_HEALTHY", clean=True, _truth=[])
    add("NEGATIVE_HEALTHY", clean=True, profile="fast_cruise", _truth=[])
    add("NEGATIVE_HEALTHY", adversarial=True, clean=True,
        note="startup+yaw transient window", _truth=[])
    return out


def main() -> int:
    rows = stratify(scenarios())

    seen = {}
    for r in rows:
        key = (r["family"], json.dumps(r["params"], sort_keys=True))
        if key in seen and seen[key] != r["dataset_partition"]:
            raise SystemExit(f"LEAKAGE: {key} in two partitions")
        seen[key] = r["dataset_partition"]

    counts = {}
    for r in rows:
        counts.setdefault(r["dataset_partition"], {}).setdefault(
            r["family"], 0)
        counts[r["dataset_partition"]][r["family"]] += 1

    agg = hashlib.sha256(
        "\n".join(sorted(r["scenario_sha256"] for r in rows)).encode()
    ).hexdigest()

    man = build("shared_power_campaign_generation",
                EvidenceEnvironment.SIMULATION,
                dataset_id=CAMPAIGN_ID, dataset_aggregate_hash=agg,
                output_paths=[f"campaigns/{CAMPAIGN_ID}.json"])

    doc = {
        "campaign_schema_version": SCHEMA_VERSION,
        "campaign_id": CAMPAIGN_ID,
        "campaign_seed": CAMPAIGN_SEED,
        "campaign_aggregate_hash": agg,
        "generated_by": "tools/generate_shared_power_campaign.py",
        "partition_policy": {
            "method": "sha256(campaign_seed:scenario_id) -> uniform share",
            "shares": dict(SPLIT),
            "adversarial": "assigned by construction, never by hash",
            "rule": "partition is derived from metadata ONLY, never from "
                    "observed CSIA performance",
        },
        "blind_rule": "BLIND_SYNTHETIC results must not be inspected until the "
                      "implementation and thresholds are frozen; every access "
                      "is logged in datasets/reports/blind_evaluation_access.json",
        "counts": counts,
        "total": len(rows),
        "experiment_manifest": man.to_dict(),
        "scenarios": rows,
    }
    out = os.path.join(ROOT, "campaigns", f"{CAMPAIGN_ID}.json")
    with open(out, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)

    print(f"campaign {CAMPAIGN_ID}: {len(rows)} scenarios")
    for part in ("DEVELOPMENT", "VALIDATION", "ADVERSARIAL", "BLIND_SYNTHETIC"):
        fam = counts.get(part, {})
        print(f"  {part:16s} {sum(fam.values()):4d}  " +
              " ".join(f"{k.replace('POSITIVE_','+').replace('NEGATIVE_','-')}={v}"
                       for k, v in sorted(fam.items())))
    print(f"aggregate hash: {agg[:16]}…")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
