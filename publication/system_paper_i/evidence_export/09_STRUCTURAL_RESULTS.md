# 09 — Structural results

**Every number in this file is COMPUTED FROM THE DECLARED STRUCTURE by
enumeration.** None of it is a runtime measurement. The separation is stated
per row.

---

## 1. Reachable configuration count

| quantity | value | source |
|---|---|---|
| hypotheses | 8 | `wp_c1/results/certificate.json` |
| hypothesis pairs | 28 | same |
| **reachable channel configurations** | **1232** | `wp_c6/results/minimum_repair.json`, `wp_c2/results/repair_experiment.json` |
| naive 2^12 = 4096 | **UNRECOVERABLE as a committed field** | no artifact states 4096; see below |

**On "4096 naive to 1232 admissible".** The value **1232**
is committed and appears in two independent artifacts. The figure 4096 does
**not** appear in any committed artifact. If the paper wants the contrast it
must state the enumeration basis explicitly and derive it; otherwise cite
1232 alone. Marked **UNRECOVERABLE**.

**Evidence class: COMPUTED FROM DECLARED STRUCTURE.**

---

## 2. Coarsening index, final values

| reading of the 3 UNKNOWN cells | classes under S | kappa(S) | classes under S_eff | kappa(S_eff) | gap |
|---|---|---|---|---|---|
| unknown as open | 8 | 0.0 | 7 | **0.142857** | 0.142857 |
| unknown as closed | 8 | 0.0 | 7 | **0.142857** | 0.142857 |

Pairs merged only in S_eff: `['gps_fault+nominal']` (open),
`['gps_fault+nominal']` (closed).
Monotonicity holds in both readings:
`theorem_holds = True / True`.
**It is monotonicity, not a theorem, and the artifact's key name should not be
copied into the paper as a claim.**

**Stale kappa values.** The figure 0.286 does not appear in this artifact.
Any kappa other than those in the table above is **stale** and must not be
used; the reason is the WP-C3 promotion, which changed the signature matrix
(`computed against the POST-PROMOTION signature matrix, i.e. with attitude_gravity_mag already in imu0_bias_drift (WP-C3 promotion)`).

**Post-promotion gate-closure ceiling.** The maximum kappa reachable under
gate closure at full instrumentation is
0.142857 before any repair and
0.0 after the recommended addition
(`wp_c6/results/minimum_repair.json`).

**Evidence class: COMPUTED FROM DECLARED STRUCTURE.**

---

## 3. Exposed pairs and the certificate

| quantity | value | source |
|---|---|---|
| exposure-set critical pairs enumerated | 27 | `certificate.json.exposure_set_critical_pairs` |
| critical pairs in D_critical | 27 | `d_critical` |
| response-equivalent pairs | 1 | `d_critical` |
| certificate curve points | 8 | `certificate_curve_min_channels` |
| corpus-admissible configurations | 19 | `corpus_admissible_set` |
| corpus logs behind that set | 26 | `corpus_admissible_set` |
| guaranteed pairs | 0 | `corpus_admissible_set` |
| critical exposed in that set | 27 | `corpus_admissible_set` |

**Additivity.** `certificate.json.subadditivity` carries three levels:
`{
 "feature_level": {
  "examples": [],
  "superadditive_configurations": 0,
  "verdict": "ADDITIVE BY CONSTRUCTION \u2014 a feature dies if its channel is absent OR a controlling gate is closed, so joint feature loss is exactly the union of the marginals. No configuration can exceed it."
 },
 "pair_level_raw_union": {
  "caveat": "THIS TEST IS WRONG and is retained only to document the error. It compares joint merges against the raw union of marginal merges, ignoring that merging is an equivalence relation. It reports interaction wherever transitivity alone links two classes.",
  "examples": [
   {
    "channels": [
     "gps"
    ],
    "gates_closed": [
     "gps_warmup"
    ],
    "novel_merges": [
     "gps_fault+imu0_bias_drift",
     "gps_fault+imu1_bias_drift",
     "gps_fault+mag_interference",
     "gps_fault+power_fault",
     "gps_fault+vibration_anomaly"
    ]
   },
   {
    "channels": [
     "gps"
    ],
    "gates_closed": [
     "gvalid"
    ],
    "novel_merges": [
     "gps_fault+imu0_bias_drift",
     "gps_fault+imu1_bias_drift",
     "gps_fault+mag_interference",
     "gps_fault+power_fault",
     "gps_fault+vibration_anomaly"
    ]
   },
   {
    "channels": [
     "gps"
    ],
    "gates_closed": [
     "armed_gate",
     "gps_warmup"
    ],
    "novel_merges": [
     "gps_fault+imu0_bias_drift",
     "gps_fault+imu1_bias_drift",
     "gps_fault+mag_interference",
     "gps_fault+power_fault",
     "gps_fault+vibration_anomaly"
    ]
   }
  ],
  "superadditive_configurations": 1784
 },
 "pair_level_transitive_closure": {
  "examples": [],
  "superadditive_configurations": 0,
  "verdict": "SUB-ADDITIVE \u2014 no configuration merges a pair beyond the transitive closure of the two marginal merge relations. Gate closure and channel absence destroy OVERLAPPING feature sets; their effects compose by union and transitivity, not by interaction."
 }
}`

**Super-additive interaction was REFUTED**; see `10_CORRECTIONS_LEDGER.md`.
The artifact reports sub-additivity, and the paper must use that word.

`not_novel` field, verbatim: *see research/wp_c1/NOVELTY_ATTACK.md*

---

## 4. Cut sets, before and after the IMU promotion

| quantity | pre-promotion | post-promotion |
|---|---|---|
| pairs with an order-one cut set | **7** | **6** |
| components in any order-one cut | 9 | 7 |
| new mag order-one pairs | — | `none` |

Question asked: *did promoting the IMU repair create a new order-one cut set at channel:mag?* Answer: **NO**

Pairs losing their order-one cut: `imu0_bias_drift+imu1_bias_drift` is present
pre and absent post, which is the promotion working.

**Evidence class: COMPUTED FROM DECLARED STRUCTURE.**

---

## 5. Channel absence and the field-set universe

`research/wp_c6/results/field_set_universe.json` bounds the universe of
GPS-spanning relations over the currently ingested field set.

| key | value |
|---|---|
| `containment_complete_over_ingested_field_set` | false |
| `escape_route` | "Every GPS-spanning relation buildable from the CURRENTLY INGESTED fields depends on position, velocity or altitude, all |
| `n_inside` | 5 |
| `n_outside` | 1 |
| `purpose` | "bound the admissible evidence universe for gps_fault over the FINITE, ENUMERABLE set of telemetry fields the ingestion  |
| `why_this_is_not_the_universal_claim` | "U_h subset C_h over ALL physically admissible relations is not established and is not claimed. This enumerates U_h rest |

Full lists are in the artifact; the paper's Table 6 is built from it.

---

## 6. "One in seven effective collision"

**Not located as a committed field.** No artifact in `research/wp_c*/results/`
contains a field expressing a one-in-seven ratio. Marked **UNRECOVERABLE**. If the
paper wants it, derive it explicitly from `kappa_S_eff` = 0.142857
(= 1/7 to four places) and say so; do not cite it as a separate measurement.

---

## 7. "5 of 11 edges inert"

**REFUTED.** See `10_CORRECTIONS_LEDGER.md`. Do not use.
