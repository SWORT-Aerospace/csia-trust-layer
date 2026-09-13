# Counterexample and Failure Log — RCEC Independent Validation

Every entry is something that was believed, tested, and found wrong, or an
instrument that was found not to measure what it claimed. Entries are appended,
never edited away. `IV-n` numbering continues independently of the prior
phase's `RC-n` log, which is frozen.

---

## IV-1 — "Zero false certificates in 8640 runs" could not have failed

**Believed:** the locked campaign demonstrated empirical soundness of the
certificate: 8640 runs, zero false certificates.

**Found:** `tools/research/rcec_locked_campaign.py::false_certificates`
selects rows where `state == CERTIFIED and M_R < 0`. In
`csia_active_evidence/rcec.py::certify`, the `CERTIFIED` return is reached only
after the guard `if achieved >= margin: return <not certified>`, and
`M_R = margin - achieved`. So `CERTIFIED` implies `M_R > 0` on every code path.
The selected set is empty by construction.

**Status:** the claim "zero false certificates" is **withdrawn as evidence of
soundness**. It is a true statement about a code invariant and says nothing
about whether any certificate was correct about the world. Detecting a genuine
false certificate requires comparing the estimate to simulator truth, which the
locked campaign never did.

**Consequence:** `RESULTS_LOCKED.md` §7's sentence "Separating plants requires
scoring the estimate against plant truth, which only the false-certificate
check does here" is false in its second clause. Not edited; recorded.

**Test:** `tests/test_iv_provenance.py::test_certify_only_returns_certified_when_the_margin_is_positive`,
`::test_no_locked_row_can_be_certified_with_a_negative_margin`,
`::test_the_locked_campaign_never_scored_against_plant_truth`.

---

## IV-2 — The "90% resolution frontier" does not require a certificate

**Believed:** the headline frontier numbers (P2 at 0.006 ohm, and so on)
describe how small a resistance change each probe can *certify*.

**Found:** the stored `resolvable_fraction` counts rows with `M_R > 0`,
irrespective of state. Requiring `CERTIFIED_IN_MODEL` as well moves every
frontier one grid step worse, and removes the old P7 from the table entirely:

| arm | published (`M_R > 0`) | requiring a certificate |
|---|---|---|
| P1 palindromic | 0.020 | 0.040 |
| P2 compensated | 0.006 | 0.010 |
| P3 shaped | 0.010 | 0.020 |
| P4 feedback | 0.010 | 0.020 |
| P5 random-safe | 0.020 | 0.040 |
| P7 (old) | 0.040 | **never** |

**Status:** the published numbers are arithmetically correct for the predicate
used. The *label* was wrong. Both predicates are computed and reported from
here on, and the predicate is stated with the number.

**Test:** `tests/test_iv_provenance.py::test_published_frontier_reproduces_under_margin_positive`,
`::test_frontier_is_strictly_worse_when_certification_is_required`,
`::test_the_old_p7_never_certifies_anywhere_on_the_grid`.

---

## IV-3 — The paired-win denominators were a single-plant slice

**Believed:** "P2 beat P6 on 140 of 140 matched triples and P1 on 240 of 240"
described the campaign.

**Found:** those are the `one_rc` slice. Campaign-wide the same comparisons are
420/420 and 726/726. The `simple` plant yields 246, not 240, against P1,
because P1 produced a margin in six more cells there.

**Status:** the win *rate* and the median differences reproduce exactly
(+0.0391840889243677 and +0.006057004416076926 ohm on the one-RC slice). The
denominators were under-reported by a factor of three and the scope was not
stated. Reported correctly from here on. Not a falsification of the direction
of the result.

**Test:** `tests/test_iv_provenance.py::test_published_paired_wins_are_the_one_rc_slice`,
`::test_campaign_wide_denominators_are_larger_and_still_unanimous`.

---

## IV-4 — The certificate margin is bit-identical across plants, not merely equal to 12 dp

**Believed:** "median certificate margin was identical to twelve decimal places
across the three plant arms in 2012 cells", which reads like a numerical
coincidence worth investigating.

**Found:** in all 2012 cells where all three plants produced a margin, the
values are **bit-identical**. `M_R^cert` is computed from the realized current
and the declared envelope; it never reads the plant's voltage response. There
was nothing to investigate: the quantity is plant-independent by construction.

**Status:** strengthens rather than contradicts the prior withdrawal of the
simple-versus-one-RC comparison. It also fixes the target for H5: an outcome
metric that is *also* plant-independent would be a failed instrument, not a
finding.

**Test:** `tests/test_iv_provenance.py::test_certificate_margin_is_bit_identical_across_plants`.

---

## IV-5 — `RAW_CHECKSUMS.sha256` pins files that are supposed to change

**Found:** the prior phase's checksum manifest lists nine living source and
document files (`rcec.py`, `test_rcec.py`, `DERIVATION.md`, `CLAIM_LEDGER.md`
and others) alongside the immutable raw campaign JSON. Those nine legitimately
changed in MX-040 and MX-042, so the manifest fails on 9 of 18 entries today.
The immutable raw JSON still verifies.

**Status:** a checksum file that mixes immutable artifacts with files expected
to evolve produces a permanent red that everybody learns to ignore, which is
worse than no manifest. Not repaired in place — the old file is evidence of
what was true at MX-039. This phase checksums **immutable raw outputs only**.

---

## IV-6 — The frozen-core digest had no committed derivation

**Found:** `b0b011c6…915ba5a8` appears exactly once in the repository, in
prose, with no code that produces it. A number nobody can recompute is not a
verification.

**Status:** the derivation is
`sha256(json.dumps(FROZEN_BASELINE.json["files"], sort_keys=True))`. Recovered
by enumerating ten plausible formulations and testing each; nine did not match.
Now pinned in `tools/research/iv_base_provenance.py` and asserted in
`tests/test_iv_provenance.py::test_frozen_core_digest_and_its_derivation`. All
12 files match their recorded digests.
