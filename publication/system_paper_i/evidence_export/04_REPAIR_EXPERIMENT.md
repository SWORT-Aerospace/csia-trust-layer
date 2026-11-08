# 04 — The repair experiment, and the fix-preserving contrast

Two distinct experiments live here because the paper needs both: a **contrast**
showing the mechanism does not fire when the fix survives, and a **candidate
table** showing what would repair it.

---

## PART 1 — Fix-preserving contrast

Same artifact, same script, same onset, three arms.
**Artifact:** `research/wp_c4/results/self_occlusion.json`

| quantity | arm A `A_spoof_only` | arm B `B_denial_only` |
|---|---|---|
| description | fix stays VALID — control, evidence survives | fix INVALID — the self-occlusion case |
| **`gvalid_min_after_onset`** | **1.0** (gate never closes) | **0.0** (gate fully closes) |
| `gvalid_frac_closed_after_onset` | 0.0 | 0.625 |
| top-cause occupancy | `{"gps_fault": 0.665, "nominal": 0.335}` | `{"nominal": 1.0}` |
| time to first `gps_fault` lead | **1.44 s** | **None** (never) |
| GPS trust minimum | 0.5905 | 0.9767 |
| seconds nominal-on-top while faulted | 13.4 | 40.0 |
| max failsafe level | 1 | 1 |

**Third arm, for completeness.** `C_spoof_then_denial`
(spoof for 5 s, then denial): gate closes
0.5 of the
window, `gps_fault` leads
0.156
of it, first lead at
1.44 s,
trust minimum 0.7003.

### What this licenses

> **SELF-OCCLUSION OBSERVED FOR TESTED FIX-LOSS FAULTS.**

and **not**:

> ~~GNSS FAULTS SELF-OCCLUDE.~~

Arm A is a GNSS fault. It keeps the fix, the gate stays open, the evidence
survives, and the diagnosis names `gps_fault` in
1.44 s. A general claim over GNSS faults is
refuted by a run inside the same artifact as the positive result.

---

## PART 2 — The candidate relation table

**Artifact:** `research/wp_c6/results/minimum_repair.json`
**SHA256:** `d2eb52f02d2a7d2e17c95c0d52942828fa200596606b385a66a2a6d4587c4657`
**Script:** `research/wp_c6/minimum_repair.py` · **Commit:** `1ee0662acffb84472aad3f19f49b6b259c855747`
**Implements nothing:** `implements_nothing = True`
**Reachable configurations quantified over:** 1232

| candidate | channels | gated by | survives `gvalid` | crit. exposed k=8 before | after | kappa_max k=8 before | after | crit. exposed k=7 before | after | repairs target at k=8 | telemetry |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `gps_cn0_stats` | gps | **none** | **yes** | 1 | 0 | 0.142857 | 0.0 | 11 | 7 | yes | needs plumbing: noise_per_ms |
| `gps_sat_geometry` | gps | **none** | **yes** | 1 | 0 | 0.142857 | 0.0 | 11 | 7 | yes | needs plumbing: satellites_used, hdop |
| `gps_jamming_flag` | gps | **none** | **yes** | 1 | 0 | 0.142857 | 0.0 | 11 | 7 | yes | needs plumbing: jamming_indicator |
| `gps_accuracy_report` | gps | **none** | **yes** | 1 | 0 | 0.142857 | 0.0 | 11 | 7 | yes | needs plumbing: eph, epv, s_variance_m_s |
| `phys_gps_inertial` | gps, imu0 | **none** | **yes** | 1 | 0 | 0.142857 | 0.0 | 11 | 9 | yes | no new fields: position derivative vs inertial |
| `CONTROL_gated_cn0` | gps | `gvalid` | **no** | 1 | 1 | 0.142857 | 0.142857 | 11 | 11 | **NO** | control: same relation, gated by gvalid |

**Candidates that repair cleanly:** `gps_cn0_stats`, `gps_sat_geometry`, `gps_jamming_flag`, `gps_accuracy_report`, `phys_gps_inertial`
**Recommended:** `gps_cn0_stats`
**Basis:** repairs the target at full instrumentation, creates no new collision anywhere in the lattice, and leaves the fewest critical pairs exposed at k=7 (one channel already lost)
**Why size one:** The partial-containment sweep shows a knife edge: a single feature outside C_h removes absorption entirely at every density. So the minimum repair is one relation, and the question is only which.

### The control that carries the argument

`CONTROL_gated_cn0` is deliberately the **same relation** as `gps_cn0_stats`,
placed **behind `gvalid`**. Its row is the comparison the design rule rests on:

| | `gps_cn0_stats` (ungated) | `CONTROL_gated_cn0` (behind `gvalid`) |
|---|---|---|
| repairs target at k=8 | **yes** | **NO** |
| critical exposed k=8 after | 0 | 1 |
| kappa_max k=8 after | 0.0 | 0.142857 |
| critical exposed k=7 after | 7 | 11 |

An otherwise comparable relation gated by the same gate the fault closes
repairs nothing. Adding evidence does not help; adding evidence **outside the
fault's own gate** does.

**Runtime behaviour:** not tested for these six candidates.
`implements_nothing = true`; the table is computed over the declared structure.
Runtime column: **UNRECOVERABLE** for all six, by design.

---

## PART 3 — The IMU repair, which was implemented and measured

Distinct from part 2: this one was executed behind a flag and measured at
runtime.

**Artifact:** `research/wp_c2/results/repair_experiment.json`
**SHA256:** `f97b201887ebecc854a0c49ae12f28fe2d351eebc76e6533feb2f361d5417c43`
**Script:** `research/wp_c2/repair_experiment.py` · **Commit:** `cf58075e46cfda421e738cd0a0e1e69aec0a0bbe`

| item | value |
|---|---|
| feature added | `attitude_gravity_mag` |
| into hypothesis | `imu0_bias_drift` |
| channels spanned | imu0, mag |
| gated by | **none** |
| new hardware | False |
| physical justification | attitude_gravity_mag compares mag heading against imu0-integrated yaw. An imu0 bias corrupts that comparison; an imu1 bias does not. The asymmetry is what breaks the tie. |
| research flag | `CSIA_WP_C2_IMU_REPAIR` |
| default | OFF — production behaviour unchanged; asserted by tests/test_wp_c2_repair_flag.py |

**Certificate diff:** exposed pairs
28 before, 28 after, over
1232 reachable configurations;
`no_new_collisions = True`.
Whole-lattice caveat, verbatim: *the union over ALL configurations includes the zero-channel case, where every pair merges; use diff_by_min_channels*

**The GPS case and the IMU case are different problems.** The IMU repair
breaks a **tie between two hypotheses** by adding an asymmetric feature; both
IMU hypotheses keep their evidence. The GPS case is a hypothesis **destroying
its own evidence**. A repair for one is not a repair for the other, and the
paper must not present them as instances of one fix.

**CI/build guard:** the flag defaults OFF and that is asserted by
`tests/test_wp_c2_repair_flag.py`. The IMU repair was later promoted to
default in commit `081cca3b83fe098385648b9a0b7e26a0f5bd11c3`.

---

## PART 4 — The design rule

> **DESIGN RULE.** For a hypothesis `h` whose evidence set is entirely gated
> by gates that `h` itself closes, effective undetectability is removed by
> adding at least one relation for `h` that is **not** behind any gate `h`
> closes. Adding a relation behind such a gate does not remove it.

**Scope, exactly.** Computed over the 1232
reachable channel configurations of the declared eight-node structure, for the
target `gps_fault`, at full instrumentation (k=8) and at one-channel-loss
(k=7). It is a statement about the declared structure, verified by
enumeration.

**It is not a theorem and is not labelled one.** No proof of a general claim
over arbitrary structures is offered, and none should be written.
