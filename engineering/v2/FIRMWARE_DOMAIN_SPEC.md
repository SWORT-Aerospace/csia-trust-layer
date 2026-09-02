# FIRMWARE / CONFIGURATION DOMAIN — v2 §9 — **SPECIFIED, NOT BUILT**

No implementation exists. `FIRMWARE_CONFIGURATION` is reserved in
`csia/v2/domain.py:DOMAIN_IDS`, and this document is what a module would
implement. §26 scoped the first build to five domains plus actuation as a
sixth; this is not among them, and nothing in the repository pretends it is.

---

## 1. WHAT IT WOULD MONITOR

Firmware SHA and version, hardware ID, parameter/configuration hash, boot
count, reset reason, calibration versions, message-rate configuration,
unexpected parameter changes, sensor identity changes.

## 2. THE THREE STATES — §9

    QUALIFIED_CONFIGURATION   matches a configuration that was qualified
    CONFIGURATION_MISMATCH    differs from it, and the record says how
    CONFIGURATION_UNKNOWN     no qualified reference to compare against

These map onto the common evidence schema without extension:
`NOMINAL` / `VIOLATED` / `UNAVAILABLE`, with the engineering state in
`detail`. **No new evidence field is required**, which is one of the things
this spec exists to establish.

`CONFIGURATION_UNKNOWN` is `UNAVAILABLE`, never `NOMINAL`. A system with no
qualified reference has not been shown to be running qualified software; it
has been shown that nobody looked.

## 3. WHY IT NEEDS NOTHING NEW FROM THE FRAMEWORK

- Its evidence is **categorical** — a hash matches or it does not. That is
  precisely the case §18 says must not be forced into a likelihood, and the
  common record already carries a categorical verdict with optional numbers.
- Its relations are per component (`fmu`, `gps_receiver`, `esc_0`), which the
  existing `component` field covers.
- It affects functions through the same `affected_functions` mechanism.

The cost of building it is one module implementing `evaluate` plus a
`FirmwareSpec` per component in a profile. That claim is untested — this
domain is the test — and the report says so rather than assuming it passes.

## 4. THE CROSS-DOMAIN RELATION IT UNLOCKS — §14

> FIRMWARE + TIMING: a message-rate parameter changed → freshness behaviour
> changes.

This is the relation that catches a class of incident where nothing is broken
and everything looks wrong: someone lowers a publication rate, the staleness
watchdog starts firing, and the investigation goes to the sensor.

It is deliberately **not declared** in either profile today. A relation whose
firmware side can only ever be `UNSUPPORTED` would add an entry to every
timing fault and teach an operator to ignore the field. It gets declared when
the domain exists.

## 5. RELATIONSHIP TO SECURITY — §13

Unexpected firmware and unexpected device identity are also security signals.
They belong here as **configuration** findings and are surfaced to the
security domain as evidence, not re-derived there. §13's instruction to keep
security findings separate from physical fault attribution is served by the
domain boundary: this domain says "the parameter hash changed"; whether that
was an engineer or an intruder is not a question this domain can answer.
