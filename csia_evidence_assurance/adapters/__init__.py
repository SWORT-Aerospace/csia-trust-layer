"""EvidenceProducer adapters: existing monitors, wrapped, not re-implemented.

| adapter | wraps | kind of algorithm |
|---|---|---|
| `v2_domains` | the frozen CSIA v2 domain plugins (power, compute, timing, communication, actuation, and the v1.1 transcription) | the legacy record producers, for historical replay |
| `cusum` | the frozen v1.1 CUSUM bank (`csia/v1_1/sequential.py`) | STATISTICAL change detection |
| `px4_estimator` | PX4 EKF2's own status (`estimator_status`, reset counters, sensor selection; `estimator_selector_status` when logged) | ESTIMATOR integrity, and the configuration epoch |
| `xsys_witness` | the XSYS-001 witnesses (W_RPM, W_DYN, W_CTRL) from the sealed stage-1 features | PHYSICAL cross-domain evidence |

Each adapter emits `EvidenceEnvelope`s that its contract (`contracts/`)
declares. None maps a detection to a cause: attribution is the profile's
and 2.1.1's job.
"""
