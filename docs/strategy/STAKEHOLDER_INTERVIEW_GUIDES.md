# Stakeholder Interview Guides — v1

**Rule:** every answer lands in the assumption register (strategy step 4) as
`untested → weakly supported → partner supported → contract validated →
disproved`. **No stakeholder input exists yet; nothing below is evidence.**

## Guide A — UAV OEM (autonomy / avionics lead)

1. Walk me through what happens today when a sensor degrades in flight — who
   detects it, in which module, and what the vehicle does. *(architecture)*
2. How many engineer-months went into your current fault-monitoring and
   sensor-voting logic? How much is re-done per airframe variant? *(cost baseline
   for ROI model)*
3. What was your worst in-service diagnosis failure — wrong sensor blamed,
   missed common cause, false RTL? What did it cost? *(pain, quantified)*
4. Would you run a third-party assurance runtime on the companion computer in
   shadow mode? What would it take to let it advise? To let it act? *(authority
   boundary — the product's hardest constraint)*
5. What evidence would your certification lead need before shadow → advisory?
   *(maps to assurance ledger requirements)*
6. If this saved you X integration months per platform, what is that worth —
   per program, per year? Who owns that budget line? *(pricing anchor)*
7. What flight data could you share, under what restrictions? *(data pipeline)*

## Guide B — Certification / safety expert (DER, consultant, or authority-adjacent)

1. Under ASTM F3269-style RTA, what would you classify a shadow-only
   diagnosis layer as — and what changes the classification? *(assurance class)*
2. What independence must the monitor have from the monitored autonomy?
   *(architecture requirement)*
3. Is a statistically controlled alert rate (anytime-valid bound, declared
   dependence domain) something you could cite in a safety case, or is it
   noise to you? *(tests whether the math is a certifiable asset — the
   program's central commercial bet)*
4. What would you require of the evidence ledger: content, retention,
   signatures, configuration control? *(F3201 / ARP4754B mapping)*
5. Which tool-qualification path applies if CSIA output informs pilot or
   operator decisions? *(DO-330 exposure)*
6. Who carries liability when an advisory system is wrong — and what wording
   have you seen survive that question? *(contract structure)*

## Guide C — Defense integrator

1. In GPS-denied or jammed operations, what does your current stack report to
   the operator, and how often is it wrong? 2. Which degraded-operation
   requirements in your programs are currently unmet? 3. What cyber/export
   constraints apply to a third-party inference layer (ITAR/EAR class,
   on-airframe code provenance)? 4. What data rights would the government
   claim over an assurance ledger? 5. Procurement route: SBIR phase III,
   OTA, sub to prime — which is realistic for a component like this?

## Guide D — Sensor / avionics vendor

1. Would you publish a machine-readable Trust Contract (units, uncertainty,
   latency, failure modes) for your product? What stops you today?
2. Are your health/status flags actually used by integrators? Semantics
   documented anywhere machine-readable? 3. Would "CSIA-COMPATIBLE"
   conformance help you sell — and what would you pay or contribute?
   4. What failure-mode data can you share without exposing IP?
