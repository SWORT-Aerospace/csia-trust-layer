# Mechanism B dwell discrepancy — discrepancy record (proposed ledger entry FL-053)

**Status: RECORDED HERE, NOT IN THE FAILURE LEDGER.** The content below is the
complete entry, ready to append as FL-053. It is held out of
`research/physical_validation/FAILURE_LEDGER.yaml` for a reason stated in §1,
and the proposed correction it refers to is
`docs/research/SC09_PROPOSED_CORRECTION.md`.

---

## 1. Why this is not in the ledger yet

**The failure ledger is pinned by three sealed-phase SHA-256 manifests:**
`research/consequence/phase32/SHA256_MANIFEST32.json`,
`research/phase4/SHA256_MANIFEST4.json` and
`research/phase5/SHA256_MANIFEST5.json`. Appending any entry changes the
ledger's hash, and all three manifest tests fail until the pinned hash is
rewritten.

This repository's established practice rewrites exactly two lines in each
manifest on every append: the ledger's hash and `head_at_build`. FL-048 through
FL-052 were all appended that way, in commits `b7f1816`, `d69919d`, `c2aac29`
and `39dc509`.

The owner's instruction for this work was to **not modify sealed artifacts and
to preserve the original hashes.** Rewriting a pinned hash in three
sealed-phase manifests is a modification of sealed hash records, even when the
file it pins is an append-only log. So the entry is held here, and promoting
it is the owner's decision.

**What happened, stated plainly.** The entry was first appended to the ledger
in commit `ec9f8ed` without updating the manifests. The full suite then failed
three manifest checks (`tests/test_consequence_phase32.py`,
`tests/test_phase4_pipeline.py`, `tests/test_phase5_pipeline.py`, each
`test_the_manifest_matches_every_file_it_lists`). The ledger was restored to
its pinned bytes, SHA-256 `6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f`,
matching all three manifests again, and the entry moved here. No manifest was
edited at any point.

---

## 2. To promote it into the ledger (owner decision)

1. Append the block in §3 to `research/physical_validation/FAILURE_LEDGER.yaml`.
2. In each of the three manifests, rewrite the ledger's hash and
   `head_at_build`, and nothing else, as the precedent commits did.
3. Change "ledger has 124 entries" to 125 in
   `docs/FIELD_INTEGRATION_RUNBOOK.md`, which `tests/test_runbook_numbers.py`
   couples to the ledger.
4. Run the three manifest tests and the runbook test.

---

## 3. The entry, verbatim, ready to append

```yaml
  - id: FL-053
    date: 2026-09-26
    phase: Cross-system research reconnaissance (read-only audit of sealed evidence)
    kind: MEASUREMENT_DEFECT
    what_happened: >-
      Mechanism B's CUSUM-versus-trust comparison subtracted the failsafe's
      1.0 s dwell_up from a trust latency that never contained it. The
      generator research/systems-paper/mechanism_b.py takes its trust series
      from run_pipeline (line 114), which is PredictionComparator ->
      TrustEngine -> CausalDiagnosis and runs no FailsafePolicy at all
      (csia/scenarios.py run_pipeline). The trust latency is the first
      crossing of that raw series below nav_caution = 0.75 (line 140). A
      raw series crossing cannot contain a dwell: the dwell is applied by
      FailsafePolicy.update AFTER the crossing, between the crossing and the
      alert. Yet lines 223-227 record trust_latency_includes_dwell: True and
      compute trust_detector_only_latency_s = trust_latency - dwell_up. The
      committed values are therefore 1.0 s too favourable to the trust path:
      raw (correct, pre-dwell) 8.72 / 3.36 / 3.24 s against CUSUM 2.96 /
      1.16 / 0.72 s, reported instead as "detector only" 7.72 / 2.36 /
      2.24 s. The raw comparison was ALREADY detector-to-detector. Red-team
      objection 2.3's premise does not hold for this measurement, and the
      "correction" that closed it introduced the error rather than removing
      one.
    found_by: >-
      Cross-checking three independent sources during reconnaissance for the
      cross-system research direction, not by inspecting Mechanism B for
      defects. (1) docs/audit/CSIA_LATENCY_PATH_AUDIT.md section 3, measured
      by executing repository code: gps_spoof trust crosses the production
      threshold 0.75 at 3.36 s after onset and the alert fires at 4.40 s,
      the 1.04 s difference being exactly dwell_up plus one 25 Hz tick. (2) A
      fresh run of the gps_spoof catalogue scenario through the online
      runtime (TrustLayerRuntime + csia/metrics/latency.py) reproduced
      3.36 s and 4.40 s. (3) Reading the generator and run_pipeline, which
      shows no policy is ever run. The dwell sits after 3.36 s, so 3.36 s is
      pre-dwell.
    honest_limit: >-
      The corroborating runs use the default and hover_circle profiles; the
      three Mechanism B arms were not re-run for this entry, and their
      values are taken as committed. The claim this affects is narrower than
      the error: SC-09's statement ("the CUSUM alarms earlier than the trust
      threshold in every faulted arm and never in the clean window") is
      unaffected, and correcting the figures WIDENS the CUSUM's lead (5.76 s
      on the 1 m/s ramp, not 4.76 s). What is wrong is the rationale column
      of SC-09, the policy_dwell block of mechanism_b.json, section 5 of
      MECHANISM_B.md and the closure text of red-team 2.3. The systems-paper
      manuscript does not quote the net-of-dwell figures. Whether a separate
      detector-plus-policy comparison is wanted is a separate question this
      entry does not answer; the trust-path alert times it would use (9.76 /
      4.40 / 4.28 s) are DERIVED here as crossing + 1.04 s, and only the
      4.40 s figure has a measured equivalent (the gps_spoof run above).
    verdict: RECORDED_FIX_SPECIFIED_NOT_APPLIED
    consequence: >-
      No sealed artifact was modified. SHA-256 at the time of this entry, all
      unchanged: results/mechanism_b.json 8237458edfb3b557...,
      mechanism_b.py 2c254877f7db3e14..., MECHANISM_B.md 351c04589e92d05c...,
      CLAIMS.csv 0def29ebd7366f90..., REVIEWER_RED_TEAM.md
      1090e9d7ec9344f3... A proposed correction for SC-09 is written as a
      separate note for the owner to accept or reject. Correcting does NOT
      reverse SC-09: the CUSUM remains earlier in every tested arm, so the
      substantive conclusion survives, and survives with a larger margin.
    artifact: >-
      docs/research/SC09_PROPOSED_CORRECTION.md;
      research/systems-paper/mechanism_b.py;
      research/systems-paper/results/mechanism_b.json;
      csia/scenarios.py;
      docs/audit/CSIA_LATENCY_PATH_AUDIT.md
```
