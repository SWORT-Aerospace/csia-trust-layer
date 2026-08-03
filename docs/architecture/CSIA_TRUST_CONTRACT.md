# CSIA Trust Contract v0.1

A Trust Contract is a machine-readable declaration a component makes BEFORE
CSIA consumes its output: what it provides (functions with units, uncertainty
semantics, rates, latency, time source), what it depends on (power rails,
timing, bus, mounting), where it is valid, how it degrades, how it fails,
how it restarts, and what responses are authorized (v0.1: everything
shadow-only, `active_action_prohibited: true` is REQUIRED by schema).

Files: `specifications/csia_trust_contract_v0.1.yaml` (reference instance —
the simulation GPS, the one component we fully know),
`specifications/csia_trust_contract_schema_v0.1.json`,
validator `csia/contracts/validate.py` with verdicts
CSIA_CONTRACT_VALID / INCOMPLETE / INVALID.

Why it exists commercially: slice 3E showed CSIA cannot reason about causal
structure that is not DECLARED (no rail topology → no rail hypothesis). The
contract is where OEMs and vendors declare it. The conformance suite is the
seed of the eventual "CSIA-COMPATIBLE" program — **that phrase is not yet
public marketing language**.

The reference instance validates as CSIA_CONTRACT_INCOMPLETE — its timing
function's uncertainty is genuinely uncharacterized. That is the validator
working, not a defect to hide: gaps are the product's conversation with the
vendor.
