# PHASE 3C FEASIBILITY NOTE

§28 and §33. **Nothing is implemented here.** §28 forbids adding an IMU
sequential residual during Phase 3B, and none was added.

---

## OPEN_ENGINEERING_QUESTION

> The v1.1 architecture retains the trust recursion **solely** because the
> sequential bank has no IMU residual. Would an established IMU change
> detector permit removing or simplifying trust?

## Why the question is live

Trust's unique contribution reduces to exactly two mechanisms:

| mechanism | trust | sequential |
|---|---:|---|
| `GNSS_FIX_LOSS` | 26.00 s | censored |
| `DUAL_IMU_FAILURE` | 34.12 s | censored |

If a standard detector covered both, trust would have no unique coverage left
in this catalogue and the architecture could shrink further.

## Short source audit — what would be needed

**For `DUAL_IMU_FAILURE`.** The `redundant_imu` relation already exists and
already produces a per-tick λ (`td.edges["redundant_imu"]`). A CUSUM on that
standardised residual is the same established statistic already in use, on a
stream the layer already computes. **No new sensor, no new message, no new
mathematics** — this looks cheap and standard.

**For `GNSS_FIX_LOSS`.** Structurally different, and a detector is the wrong
tool. Fix loss is **absence of evidence**: the gate goes to zero and the
residual stops existing. A CUSUM on a stream that has stopped cannot fire, and
should not — §13's distinction between sensor-fault evidence and
evidence-unavailable-through-staleness applies directly. This is a **freshness
and support** question, which Phase 1 and Phase 2 already handle, and it is
not a candidate for sequential coverage at all.

## Consequence

**Trust cannot be removed even if Phase 3C succeeds**, because `GNSS_FIX_LOSS`
is not a detector problem. The realistic upside of Phase 3C is *simplification*
of the trust recursion's role, not deletion.

That materially lowers the value of Phase 3C and it is better to say so now
than after building it.

## Recommendation

**Do not start Phase 3C. Proceed to Phase 4, then Phase 5.**

Reasons, in order:

1. Trust survives regardless (`GNSS_FIX_LOSS` above), so the best case is a
   smaller simplification than it first appears.
2. The architecture is already decided and stable enough to freeze for the
   function-eligibility, ledger and output-API work.
3. Adding a detector now would change the architecture that Phase 5 is meant
   to port, which is exactly what §33 warns against.

If Phase 3C is wanted anyway, its scope should be **one** CUSUM on the
existing `redundant_imu` residual with the same `k = 0.5` and the same
zero-clean-alarm `h` selection rule — and it should be measured against the
same nine mechanisms before anything is retained.
