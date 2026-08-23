# Public Dataset Survey (v1)

Machine-readable source of truth: `datasets/registry/public_datasets_v1.yaml`.
Everything below is PUBLISHED_SPECIFICATION — **0/7 datasets are locally
verified** (all hosts blocked by network policy; verbatim errors in
`datasets/reports/acquisition_status_v1.json`).

| Dataset | Role for CSIA | Labels | Key restriction |
|---|---|---|---|
| UAV-SEAD | Primary PX4 anomaly benchmark; false-alert characterization | Anomaly REGIONS — **no ms-latency claims** | license to verify |
| ALFA | Fixed-wing transfer; **onset-accurate** latency; actuator faults | Exact onset + type | CC BY (confirm) |
| INSANE | Multi-IMU, dual-RTK; estimator research | Trajectory GT, no fault labels | **RESEARCH-ONLY — commercial artifacts prohibited pending license review** |
| Blackbird | Aggressive-flight FALSE-POSITIVE testing | Nominal only | no fault claims possible |
| EuRoC MAV | VI estimator divergence, timing skew | Trajectory GT | CC BY-SA share-alike |
| TUM VI | Calibration faults, estimator divergence | Partial GT | confirm |
| px4_flightreview_v1 | v1 development corpus ONLY | none | 100% contaminated; never blind |

Claim eligibility (once acquired): detection (UAV-SEAD, ALFA), exact latency
(ALFA only), false-alert (UAV-SEAD nominal segments, Blackbird), source
isolation (limited; ALFA actuator classes), transfer (PX4→fixed-wing via
ALFA), estimator evaluation (INSANE/EuRoC/TUM-VI, research track).
