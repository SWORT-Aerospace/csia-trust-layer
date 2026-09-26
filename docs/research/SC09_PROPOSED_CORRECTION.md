# SC-09 — proposed correction (NOT APPLIED)

**Status: PROPOSED.** Nothing sealed has been modified. This note specifies a
correction for the owner to accept or reject. The discrepancy is recorded in
`research/physical_validation/FAILURE_LEDGER.yaml` as **FL-053**.

---

## The five statements this note exists to make

1. **The previous dwell subtraction was incorrect.**
2. **The raw trust crossing was already pre-dwell.** It is a crossing of the
   raw trust series, and no failsafe policy ever ran to add a dwell to it.
3. **Correcting this does NOT reverse SC-09.**
4. **The CUSUM remains earlier than the trust threshold in every tested arm.**
5. **Therefore the substantive conclusion survives**, and it survives with a
   *larger* margin than the one currently stated.

---

## 1. What SC-09 says today (`research/systems-paper/CLAIMS.csv`, row SC-09)

> The CUSUM alarms earlier than the trust threshold in every faulted arm and
> never in the clean window.

The claim itself is correct. Its rationale column adds:

> RED TEAM 2.3 was correct that the raw comparison flatters the CUSUM by one
> dwell period; detector-to-detector the figures are 2.96 vs 7.72, 1.16 vs
> 2.36 and 0.72 vs 2.24, so the conclusion survives.

**That sentence is the error.** The raw comparison did not flatter the CUSUM.
It was already detector against detector.

---

## 2. The evidence, from source

| step | file:line | what it shows |
|---|---|---|
| 1 | `research/systems-paper/mechanism_b.py:114` | the trust series comes from `run_pipeline(...)` |
| 2 | `csia/scenarios.py` `run_pipeline` | runs `PredictionComparator` → `TrustEngine` → `CausalDiagnosis`, and **nothing else** — no `FailsafePolicy` anywhere |
| 3 | `research/systems-paper/mechanism_b.py:140` | trust latency = first time that raw series crosses below `nav_caution = 0.75` |
| 4 | `research/systems-paper/mechanism_b.py:152` | the only `.update(` call is on the CUSUM bank; the policy is never stepped |
| 5 | `research/systems-paper/mechanism_b.py:223-227` | nonetheless records `trust_latency_includes_dwell: True` and subtracts `dwell_up` |

`dwell_up` is applied by `FailsafePolicy.update` (`csia/runtime/failsafe.py`)
**after** a trust crossing, between the crossing and the alert. A raw series
crossing cannot contain it.

**Independent confirmation that the dwell sits after the crossing.**
`docs/audit/CSIA_LATENCY_PATH_AUDIT.md` §3, measured by executing repository
code on `gps_spoof`: trust crosses 0.75 at **3.36 s**, the alert fires at
**4.40 s**, and the difference is exactly `dwell_up` + one 25 Hz tick = 1.04 s.
A fresh run of the same catalogue scenario through the online runtime and
`csia/metrics/latency.py`, made for FL-053, reproduced both numbers.

---

## 3. The corrected comparison

Values as committed in `research/systems-paper/results/mechanism_b.json`. No
arm was re-run.

| arm | trust crossing (raw, **pre-dwell**) | CUSUM | CUSUM lead, **corrected** | CUSUM lead, as currently stated |
|---|---|---|---|---|
| `slow_ramp` 1 m/s | 8.72 s | 2.96 s | **5.76 s** | 4.76 s |
| `spoof_3ms` 3 m/s | 3.36 s | 1.16 s | **2.20 s** | 1.20 s |
| `fast_ramp` 6 m/s | 3.24 s | 0.72 s | **2.52 s** | 1.52 s |

Every corrected lead is larger. The direction of every comparison is
unchanged.

---

## 4. Proposed replacement text

**SC-09, rationale column**, replacing the sentence quoted in §1:

> Red-team objection 2.3 does not apply to this measurement. The trust
> latency is a crossing of the raw trust series, taken from run_pipeline,
> which runs no failsafe policy, so it contains no dwell. The raw figures are
> already detector-to-detector: 2.96 vs 8.72, 1.16 vs 3.36 and 0.72 vs 3.24,
> and the conclusion survives with a larger margin than the dwell-subtracted
> figures previously stated. FL-053.

**MECHANISM_B.md §5 and §6**: remove the dwell-subtraction table and the
sentence "The raw comparison flattered the CUSUM by one dwell period"; state
that the raw comparison is detector-to-detector and cite FL-053. The
recommendation "The detector-only figure is the one to quote" inverts: the raw
figure is the one to quote.

**REVIEWER_RED_TEAM.md, objection 2.3**: re-close as *objection examined and
found not to apply to this measurement*, citing FL-053, rather than *closed by
correction*.

**`mechanism_b.json` `policy_dwell` block**: `trust_latency_includes_dwell`
becomes `false`, and `trust_detector_only_latency_s` either equals
`trust_latency_s` or is removed. This requires regenerating the artifact from
a corrected generator, not editing the JSON by hand.

---

## 5. If accepted: what must change together

Applying this is **one coordinated change or none**. The pieces are bound to
each other by guards, and a partial edit fails them.

| piece | why it moves |
|---|---|
| `research/systems-paper/mechanism_b.py` | lines 223-227 are the source of the error |
| `research/systems-paper/results/mechanism_b.json` | regenerated from the corrected generator; its SHA-256 changes |
| `research/systems-paper/MECHANISM_B.md`, `research/systems-paper/REVIEWER_RED_TEAM.md`, `research/systems-paper/CLAIMS.csv` | the prose quoting 7.72 / 2.36 / 2.24 |
| `research/PROSE_NUMERIC_BINDINGS.yaml` PB-26 to PB-29 | PB-26's description asserts the error; PB-27 to PB-29 bind the three net-of-dwell renderings, so the binding guard fails the moment the prose changes |
| `docs/CURRENT_PROGRAM_STATE.md` §3 gate 9 | describes 2.3 as "CLOSED by correction … the objection was right" |

These are systems-paper evidence under the dual-paper evidence freeze, so
applying the correction is the owner's decision. It changes a supporting
figure, not the claim, and the systems-paper manuscript does not quote the
net-of-dwell figures.

**Not proposed here:** a detector-plus-policy comparison, in which the trust
path's alert (crossing + 1.04 s) is compared with a CUSUM given the same
dwell. That is a legitimate second question, but it is not the question SC-09
asks, and answering it would need new runs.

---

## 6. Hashes, preserved

SHA-256 of every file this note concerns, as they stand at the time of writing.
All are unchanged by this note and by FL-053.

| file | SHA-256 | last commit |
|---|---|---|
| `research/systems-paper/results/mechanism_b.json` | `8237458edfb3b55750df99394f17237723d9712ed367975222aac131aa8eb1fc` | `4e3ed38` |
| `research/systems-paper/mechanism_b.py` | `2c254877f7db3e1491710b6de1c68074f5e49de2d3fa544b1f4ef5fa7ad7adc2` | `4e3ed38` |
| `research/systems-paper/MECHANISM_B.md` | `351c04589e92d05c39b1ccb68f28158ed142ecdd783e47fb00f53a23c434aac4` | `4e3ed38` |
| `research/systems-paper/CLAIMS.csv` | `0def29ebd7366f90716f7960573565e07be75f556fe0d2f5be9a4eb5a06ce2ff` | `ea10181` |
| `research/systems-paper/REVIEWER_RED_TEAM.md` | `1090e9d7ec9344f3ec4f2627655755fc1ea9fb83425b80493e870c4db029c790` | `3470cfc` |
