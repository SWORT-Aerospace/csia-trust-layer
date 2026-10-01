# Source lineage and dependence (Phases 4, 13 and 14)

**2026-10-01. Code:** `csia_evidence_assurance/lineage.py`,
`dependence.py`. **Tests:** `test_lineage_*`, `test_independence_*`,
`test_three_monitor_imu_regression`, `test_dependence_never_strengthens_a_verdict`.

## 1. Representation

**A lineage is a sorted tuple of at most 16 root ids, each `kind:name`.**

| kind | names | example |
|---|---|---|
| `sensor` | a physical sensor | `sensor:imu1`, `sensor:gyro.1310988` |
| `channel` | a telemetry or command channel that is its own source | `channel:esc_rpm.motor_0`, `channel:motor_command.motor_0` |
| `model` | a model whose error every output computed with it shares | `model:ekf2` |
| `calibration` | a calibration whose error is shared | `calibration:rotor_geometry` |

**Properties:**
- small: at most 16 roots;
- hashable;
- serialisable: a list of strings;
- cheap to compare: a set intersection;
- a 16-hex digest for keys.

**Not represented:**
- transformation chains;
- parent ids;
- a provenance database.

**Two outputs are DEPENDENT when their lineages share a root.**

## 2. The distinctions the brief asked for

| outputs | lineages | independent lines |
|---|---|---|
| threshold(IMU1), CUSUM(IMU1), EKF residual(IMU1) | all contain `sensor:imu1` | **1** |
| monitor(IMU1), monitor(IMU2), an independent physical witness | disjoint | **3** |
| EKF residual(IMU1), EKF residual(IMU2) | share `model:ekf2` | **1** |
| CUSUM(battery), CUSUM(motor_esc), CUSUM(vibration) (frozen v1 relation table) | all contain `sensor:motor_esc` | **1** |
| W_RPM, W_DYN, W_CTRL (XSYS-001) | W_CTRL shares `channel:motor_command` with W_RPM and `sensor:gyro` with W_DYN; W_RPM and W_DYN share nothing | **2** (one group) |

## 3. Groups and independent lines

| quantity | definition | why |
|---|---|---|
| lineage groups | connected components of "shares a root" | display: everything tied together, directly or through a third output |
| independent lines | the largest set of outputs no two of which share a root | the shadow preview's `max_disjoint`, the definition that removed every false corroboration in its seven cases and kept the genuine one |

**Why both.** Connected components alone would under-count: in XSYS,
W_DYN and W_RPM are joined only through W_CTRL, so one group, yet two
independent lines.

**Computation:**
- identical lineages count once;
- then a maximum independent set of the overlap graph, by branching on the
  output with the most overlaps;
- exact up to 16 outputs, then the group count, marked as a lower bound.

**Checked** against the preview's own `max_disjoint` on 300 random cases (all
agree). 16 outputs take 0.2 ms.

## 4. Dependence policy (Phase 13)

**The constraint.** Semantic Core 2.1.1 never counts confirmations: a
confirmer is True or not, whatever number of records made it so. So 2.2 must
not add any counting.

**The policy, the simplest compatible with that:**
1. **Logical use is unchanged.** Every admitted record reaches 2.1.1.
2. **Republished duplicates are collapsed before the core.** DUPLICATE: the
   same claim, record, content time, lineage and state under another
   producer identity.
3. **Corroboration is stated by lineage, never by count.** Per component and
   overall: the adverse evidence, its producers, its groups and its
   independent lines.
4. **No independence-based strengthening.** When a UNIQUE rests on exclusion
   evidence that shares a root with the candidate's own adverse evidence,
   the result says so (INFO). The verdict is 2.1.1's.

**Options not taken:**
- **Collapsing by lineage group before the core.** It would hide evidence
  from 2.1.1, change its logical inputs, and need a rule for which member
  survives.
- **Bayesian fusion.** Excluded by the brief, and 2.1.1 has no probabilities
  to fuse.

**Pinned.** `test_dependence_never_strengthens_a_verdict`: one alarm and three
alarms on one source give the same localizations and attribution, with one
independent line.

## 5. The permanent three-monitor IMU regression (Phase 14)

`test_three_monitor_imu_regression`:

| case | pinned result |
|---|---|
| shared source | threshold, CUSUM and EKF residual of IMU1: 3 producers, 1 independent line |
| shared model | two IMUs through one estimator: 1 line |
| duplicate producer | a relay of the threshold output: one ADMISSIBLE, one DUPLICATE, and the core receives one copy |
| stale producer | content 0.6 s old against a 0.5 s limit: STALE |
| faulted producer | a NOMINAL from a FAULTED monitor reaches the core as UNAVAILABLE |
| different content times | separate evidence ids, each judged on its own age (STALE and ADMISSIBLE) |

Dataset G runs the same set over a whole scenario (`DATASETS.md`).
