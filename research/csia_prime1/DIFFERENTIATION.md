# Product differentiation, after PRIME-1 (Phase 33)

**2026-10-03. Not a novelty audit, and not restarted.** PRIME's
`DEFENSIBILITY_AND_IP.md` and `COMPETITOR_FUNCTION_MATRIX.md` stand. This
note only updates the commercial statement for what PRIME-1 changed.

## 1. The statement (PRODUCT DIFFERENTIATION, not a novelty claim)

> **CSIA Flight Assurance qualifies the heterogeneous evidence in a PX4 log
> before any cross-system attribution, and shows its work:**
> - which outputs were admitted or refused, and why;
> - which share a source and count once;
> - what was not observed;
> - which explanations remain;
> - which measurement would separate them.
>
> **It decides whether a log is inside its supported boundary before it
> interprets anything.**

**What PRIME-1 adds to that statement:**
- **the boundary decision comes first.** UNSUPPORTED_VEHICLE_CONFIGURATION
  and UNSUPPORTED_SCHEMA withhold interpretation; PARTIAL and
  UNKNOWN_VERSION qualify it;
- **telemetry changes have explicit, separate semantics** (RPM_DEFICIT,
  RPM_EXCESS, ESC_OFFLINE). A telemetry change is never a motor fault on its
  own;
- **a reference that is itself corrupted is never used to certify NOMINAL**
  (TELEMETRY_BASELINE_INCONSISTENT);
- **the blind-pilot workflow is enforced by the tool itself:**
  - intake hashing;
  - a single run;
  - the seal;
  - reveal only after the seal.

## 2. What is NOT claimed as new

Each of these is established on its own: CUSUM and other change-point
detection; FDI; dependency graphs; ambiguity sets; producer health; runtime
assurance; temporal validity windows; integer timebases.

**The combination is close to what aircraft vehicle-level reasoners do**
(PRIME D1). The difference is commercial:
- **it targets the PX4/ULog flight-test engineer;**
- **it needs no reference-model project;**
- **it is honest about simulation-only validation.**

## 3. Where the defensibility really is (unchanged)

**Know-how and validation, not patents:**
- the PX4-specific validity rules and timing traps (now including D-PRIME-1
  and D-PRIME-2);
- the receipts;
- the support contract;
- a real-data corpus with truth, which still does not exist.

**The blind pilots are how that corpus starts.**
