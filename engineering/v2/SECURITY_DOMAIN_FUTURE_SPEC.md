# SECURITY / INTEGRITY DOMAIN — v2 §§13, 30 — **SPECIFIED, NOT BUILT**

No implementation exists. `SECURITY_INTEGRITY` is reserved in `DOMAIN_IDS`.

> Start small. No ML intrusion detector. (§13)
> Security-ready, not security-centric. (§30)

---

## 1. WHAT IT WOULD MONITOR

Unexpected firmware or configuration, unexpected device ID, unauthorised write
attempts, **output-firewall denials**, unexpected processes, unexpected command
origin, message-rate anomalies, configuration changes.

All of these are events the platform can already report. None requires a
model, a baseline learned from traffic, or a classifier.

## 2. THE INTEGRATION THAT ALREADY EXISTS

`csia/v1_1/firewall.py` is a default-deny output firewall: every operation a
consumer might take goes through `request()`, and everything outside a closed
permitted set is denied. Those denials are **already** the highest-quality
security evidence in the system — an attempt to take an action the design
forbids — and they are currently counted and not surfaced as assurance
evidence.

The first thing this domain should do is emit them. That is a small, concrete,
useful piece of work with no research content.

## 3. FINDINGS STAY SEPARATE FROM PHYSICAL FAULT ATTRIBUTION — §13

A security finding must not become a candidate in the physical cause
attribution, and a physical fault must not be reported as a security event.
The two questions have different evidence, different response paths and
different consequences for being wrong.

The mechanism already exists: `EvidenceRecord.attributable`. A security record
would set it `False` for the physical attribution, and a security-specific
view would read those records directly. No new field is needed.

## 4. WHAT WOULD MAKE THIS DANGEROUS TO BUILD BADLY

- **A learned baseline.** "Unusual message rate" from a model trained on
  normal operation is an anomaly detector with a false-positive rate nobody
  has characterised, and §13 says not to build one.
- **Attribution to an actor.** This domain can report that a parameter hash
  changed. It cannot report who changed it, and a field that implied
  otherwise would be worse than no field.
- **Coupling the system's availability to it.** §30: do not make the system
  depend on security research yet. A security domain that could make a
  function INELIGIBLE on a heuristic would be a new way to ground a vehicle.

The conservative build is: emit the events, attach them to no function, and
let a human or a later policy decide what they mean.

## 5. THE API SURFACE THAT IS ALREADY READY — §30

The four event kinds §30 names — integrity event, unauthorised command,
firmware mismatch, identity mismatch — all fit the common evidence record
without extension, and all reach the ledger through the existing
`domain`/`component`/`reason_codes` fields. The plug is ready; nothing is
plugged into it.
