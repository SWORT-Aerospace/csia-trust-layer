# Version boundary — pre- and post-promotion

**The boundary commit is `081cca3`**, "promote the IMU repair to default",
which added `attitude_gravity_mag` to `imu0_bias_drift`'s LOW signature in
`csia/diagnosis/bayes.py`.

Everything written before it was written against a system with a different
diagnostic partition. This page says, for every external-facing claim and
research artifact, which side of the boundary it applies to.

**What changed, precisely:**

| | Pre (`≤ 5b67a39`…`95e9502`) | Post (`≥ 081cca3`) |
|---|---|---|
| `imu0_bias_drift` LOW set | `{redundant_imu, accel_motor_current}` | `+ attitude_gravity_mag` |
| κ_max at full instrumentation | 0.2857 | **0.1429** |
| Irreducible critical exposure | 0.0741 (2 pairs) | **0.0370 (1 pair)** |
| Pairs with an order-one cut set | 7 | **6** |
| Components in any order-one cut set | 9 | **7** (`armed_gate`, `channel:motor_esc` drop out) |
| Peak `P(imu0_bias_drift)` | 0.9861 | **0.9203** |
| WP1 finding F-D1 | open counterexample | **repaired** |
| `gps_fault ≡ nominal` | exposed | **still exposed — unchanged** |

**What did NOT change:** κ(S) = 0.000 either side (the design-time partition
was already fully separated); every WP-A2 external-claim finding; the GPS
exposure; `campaigns/bench.json` (bit-identical); all five scenario
latencies and minimum trusts.

---

## Artifact-by-artifact

| Artifact | Applies | Notes |
|---|---|---|
| **WP-A2 correction package** (`WP_A2_CORRECTION_PACKAGE.md`) | **BOTH** | Concerns external claims about test counts, exposure, framing and the seeker campaign. None depends on the signature matrix. **Safe to send as written.** |
| **WP-A2 evidence table** (§D3) | **BOTH** | Artifact hashes cited are of committed corpus and campaign files, none of which the promotion touched. |
| **WP-A2 report** (`WP_A2_REPORT.md`) | **BOTH** | E2 channel-coverage κ values are computed with all gates open, so the promotion does not move them. E1/E4/E5 are pre-promotion measurements of unchanged code paths. |
| **WP-A2 E1 inert-gates result** | **PRE** (still valid, now understated) | Measured before the promotion. `attitude_gravity_mag` is now *more* load-bearing than the E1 numbers show, since it carries an additional hypothesis. **Re-running would strengthen, not weaken, the finding.** |
| **Paper 1 empirical section** | **BOTH, with one caveat** | The corpus κ table (2/3/4/5 channels) is gate-open and unaffected. **The gate ceiling quoted as 0.286 is PRE-promotion; post-promotion it is 0.143.** The section's argument is unchanged — the ceiling still sits far below the corpus's 1.000 — but the number must be updated before submission. **Flagged, not yet edited.** |
| **WP-C1 certificate** (`WP_C1_CERTIFICATE.md`) | **PRE** | Its headline "2 exposed critical pairs" is now **1**. The method, the reachability reduction (4096 → 1232), `D_critical` = 27, and the sub-additivity verdict are all unchanged. **Read as the pre-promotion baseline the repair was measured against.** |
| **WP-C1 design inverse** | **PRE** | "No minimal sufficient channel set exists" still holds post-promotion — the surviving exposure is still gate-caused. The cheapest-repair table is historical: its recommended repair has been executed. |
| **WP-C2 repair record** (`repair_experiment.json`) | **THE BOUNDARY ITSELF** | This is the before/after evidence. Its "before" arm is pre-promotion and its "after" arm is what production now is. **Do not re-run and overwrite it** — the flag is now a no-op, so a re-run collapses both arms to the post state. It was restored from git once already for exactly this reason. |
| **WP-C2 report** | **PRE→POST transition** | Written when the repair was behind a flag. Its recommendation ("promote") has been acted on. |
| **WP-C2 GPS integrity study** | **BOTH** | Concerns `gps_fault` only; untouched by the promotion. Its candidate rankings and the gated-control result stand. |
| **WP-C3 effective signature** | **POST** | Computed against the post-promotion matrix. `SOI(imu0_bias_drift) = 0` is *because of* the promotion. |
| **WP-C3 reliability structure** | **POST** | Birnbaum ranking is post-promotion, which is why `mag` ranks first. |
| **WP-C3 report §4.2 remark** | **SUPERSEDED** | It said the promotion "traded an IMU collision for increased reliance on `mag`." WP-C4 2.5 tested this directly: **no new order-one cut set at `channel:mag`**, and the order-one component set *shrank* from 9 to 7. The trade framing was too pessimistic. |
| **WP-C4, all parts** | **POST** | Except 2.5, which computes both sides explicitly. |
| **`tests/test_formalization_lock.py`** | **POST** | The F-D1 counterexample test became a repair regression test in the same commit. |
| **`research/formalization/diagnostic_signature_matrix.yaml`** | **POST (v1.1.0)** | Regenerated. Also carries the D-3 correction (`temp_gps` ungated), which is independent of the promotion. |
| **README validation table** | **BOTH** | Makes no signature-matrix claim. |
| **`SWORT_CSIA.pdf`** (submitted) | **PRE, and pre-everything** | Predates all of this. The correction package applies regardless. |

---

## Actions this boundary creates

| # | Action | Owner |
|---|---|---|
| 1 | Update the gate ceiling in the paper empirical section from 0.286 to 0.143 before submission | Author |
| 2 | Strike the "traded for reliance on `mag`" remark from WP-C3 §4.2, citing WP-C4 2.5 | Done here; the report retains the original with a correction note |
| 3 | Do not re-run `repair_experiment.py` expecting a before/after — the flag is a no-op now | Anyone |
| 4 | When quoting "2 exposed critical pairs", say which side of `081cca3` | Anyone |
