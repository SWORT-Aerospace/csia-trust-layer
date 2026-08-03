"""Trust Contract v0.1 conformance validator (ACEG slice 2, Part 11).

Verdicts:
  CSIA_CONTRACT_VALID       schema-valid AND semantically complete
  CSIA_CONTRACT_INCOMPLETE  schema-valid, but assurance-critical semantics
                            missing (UNKNOWN uncertainty, no missing-data
                            semantics, undeclared dependencies...)
  CSIA_CONTRACT_INVALID     schema violation or a prohibited authorization

"CSIA-COMPATIBLE" is NOT public marketing language yet (directive).
"""

import json
import os
from enum import Enum

SCHEMA = os.path.join(os.path.dirname(__file__), "..", "..",
                      "specifications", "csia_trust_contract_schema_v0.1.json")


class ContractVerdict(str, Enum):
    VALID = "CSIA_CONTRACT_VALID"
    INCOMPLETE = "CSIA_CONTRACT_INCOMPLETE"
    INVALID = "CSIA_CONTRACT_INVALID"


def validate_contract(doc: dict) -> dict:
    import jsonschema
    with open(SCHEMA) as fh:
        schema = json.load(fh)
    problems, gaps = [], []
    v = jsonschema.Draft202012Validator(schema)
    for err in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
        problems.append(f"{'/'.join(map(str, err.path)) or '<root>'}: "
                        f"{err.message[:120]}")
    if problems:
        return {"verdict": ContractVerdict.INVALID.value,
                "problems": problems, "gaps": []}

    auth = doc["authorization"]
    if auth.get("active_action_prohibited") is not True:
        return {"verdict": ContractVerdict.INVALID.value,
                "problems": ["authorization: active action must be "
                             "prohibited in v0.1"], "gaps": []}

    for i, fn in enumerate(doc["functions"]):
        if fn["uncertainty"]["semantics"] == "UNKNOWN":
            gaps.append(f"functions[{i}] '{fn['name']}': uncertainty "
                        "semantics UNKNOWN — evidence weighting impossible")
        if fn.get("missing_data_semantics", "UNKNOWN") == "UNKNOWN":
            gaps.append(f"functions[{i}] '{fn['name']}': missing-data "
                        "semantics undeclared")
    deps = doc.get("dependencies", {})
    if not deps.get("power_rails"):
        gaps.append("dependencies: no power rail declared — shared-power "
                    "reasoning disabled for this component")
    if doc.get("restart_semantics", {}).get("state_after_restart",
                                            "UNKNOWN") == "UNKNOWN":
        gaps.append("restart_semantics: undeclared — e-process restart "
                    "handling cannot be configured (T-2)")
    ids = doc["identity"]
    if not ids.get("configuration_hash"):
        gaps.append("identity: configuration_hash missing")

    verdict = (ContractVerdict.INCOMPLETE if gaps else ContractVerdict.VALID)
    return {"verdict": verdict.value, "problems": [], "gaps": gaps}
