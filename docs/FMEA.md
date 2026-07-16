# FMEA — CSIA Trust Layer as a system component (v0.7)

Failure modes OF THE MONITOR ITSELF (advisory role; severity assumes the
operator/autopilot acts on advisories). Sev/Occ/Det: 1 low – 5 high.

| # | Failure mode | Cause | Effect | Sev | Occ | Det | Mitigation (status) |
|---|---|---|---|---|---|---|---|
| F1 | False alarm cascade | mis-tuned σ, regime change | unnecessary RTL/land; operator trust erosion | 3 | 3 | 4 | field_mode adaptive baseline + dwell (DONE); held-out campaign (OPEN) |
| F2 | Missed fast fault | check gated during fault regime | no advisory during real fault | 4 | 2 | 3 | multi-edge redundancy per sensor (DONE); Monte Carlo TPR bounds (campaigns/) |
| F3 | **Missed slow drift in field config** | adaptive normalizer absorbs < τ=90 s ramps | slow bias never flagged | 4 | 3 | 5 | **MEASURED GAP (campaigns/bench.json). Planned: dual-timescale CUSUM on pre-normalization residuals — issue #tracked** |
| F4 | Monitor process death | crash, OOM, CPU starvation | silent loss of monitoring | 4 | 2 | 5 | systemd restart (doc); heartbeat to GCS (OPEN); self-watchdog (OPEN) |
| F5 | Stale-data confidence | sensor silent, values held | checks pass on frozen data | 4 | 2 | 1 | freshness watchdog + fresh-aware rules (DONE, tested) |
| F6 | Wrong-unit ingestion | dialect/frame error in adapter | systematically wrong trust | 4 | 2 | 2 | SITL validation of mapping (DONE); per-FC bench validation required before ops (doc) |
| F7 | Unauthorized actuation | unauthenticated MAVLink link | adversary triggers LAND | 5 | 2 | 5 | advisory-by-default (DONE); MAVLink signing (OPEN — required before any command use) |
| F8 | Trust deadlock/bistability | feedback in trust-weighted evidence | healthy pair mutually distrusted | 3 | 1 | 4 | not analyzed — stability study OPEN (top research item) |
| F9 | Clock skew between sensors | transport jitter, no common clock | phantom residuals during dynamics | 3 | 3 | 3 | tick sample-and-hold tolerates ~40 ms; interpolation + offset estimation OPEN |
| F10 | Diagnosis wrong under multi-fault | naive Bayes single-fault assumption | confident wrong attribution | 3 | 2 | 4 | disclosed limitation; per-cause detectors OPEN |
