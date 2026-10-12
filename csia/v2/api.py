"""CSIA SYSTEM ASSURANCE API v2 — §24.

    Design CSIA SYSTEM ASSURANCE API v2 without breaking v1.1.
    v2 may ingest v1.1 output. **Do not change schema 1.1.0.**

THE RELATIONSHIP BETWEEN THE TWO SCHEMAS, STATED ONCE
-----------------------------------------------------
    v1.1 output (schema 1.1.0)  --INGESTED BY-->  v2 (schema 2.0.0)

One direction only. v2 reads v1.1 payloads through `csia.v1_1.monitor.parse`,
the same strict parser the external monitor uses, and produces its own
document. **Nothing in v2 writes, extends, reinterprets or re-versions schema
1.1.0.** A v1.1 consumer pointed at a v1.1 producer sees byte-identical output
whether or not v2 exists anywhere in the system, because v2 is downstream of
the payload and has no path back to the producer.

That is not a convention to be careful about — it is structural. `csia/v2/`
imports exactly one thing from `csia/v1_1/`: the payload parser. It imports no
producer, and a test asserts that by parsing the import graph.

WHAT THE v2 DOCUMENT PROMISES
-----------------------------
The §16/§17 answer and nothing more:

    system              NORMAL / DEGRADED / RESTRICTED / UNAVAILABLE
    domains             per-domain observation state
    functions           per-function ELIGIBLE / DEGRADED / INELIGIBLE /
                        UNKNOWN, each with the DOMAIN THAT LIMITED IT
    attribution         UNIQUE / AMBIGUOUS / UNSUPPORTED / NO_EVIDENCE, with
                        candidates, discriminators and any common cause
    evidence            every record, with its provenance and dependencies
    unevaluated         what could not be looked at, and why

AND WHAT IT DOES NOT
--------------------
There is no system-level score, index, percentage or grade anywhere in this
document, and adding one later would be a breaking change in meaning even if
it were an additive change in schema. §3's rule — categorical evidence stays
categorical — is not only about the record type; a "system health: 82%" field
would re-import exactly the false comparability the record type exists to
prevent.

There is also no command, no recommendation to switch, and no mode. §33: the
autopilot asks "is precision navigation eligible?", CSIA answers, and the
**autopilot owns the switching action**. `fallback` is reported because the
host declared it, and reporting a host's own declaration back to it is not
CSIA choosing anything.
"""

from __future__ import annotations

SCHEMA_VERSION = "2.0.0"
INGESTS_V1_1_SCHEMA = "1.1.0"

SYSTEM_STATES = ("NORMAL", "DEGRADED", "RESTRICTED", "UNAVAILABLE")
FUNCTION_STATES = ("ELIGIBLE", "DEGRADED", "INELIGIBLE", "UNKNOWN")
OBSERVATION_STATES = ("NOMINAL", "DEGRADED", "VIOLATED", "UNAVAILABLE",
                      "NOT_APPLICABLE")
ATTRIBUTION_VERDICTS = ("UNIQUE", "AMBIGUOUS", "UNSUPPORTED", "NO_EVIDENCE")


class SchemaVersionError(ValueError):
    """A version mismatch, raised rather than coerced. A consumer that kept
    reading a document whose fields had been redefined is the failure this
    exists to prevent."""


def build(assurance, *, profile: str, provenance: dict,
          declarations: dict | None = None,
          ledger_events=()) -> dict:
    """One tick, as the product's answer.

    `assurance` is a `SystemAssurance`; everything else is context the engine
    does not hold. Deterministic: the same tick and the same provenance
    produce the same document, byte for byte, so it can be hashed.
    """
    doc = assurance.to_dict()
    doc = {
        "schema_version": SCHEMA_VERSION,
        "ingests": {"csia_output_v1_1": INGESTS_V1_1_SCHEMA},
        "profile": profile,
        "provenance": dict(sorted(provenance.items())),
        **doc,
        "ledger_events": [dict(e) for e in ledger_events],
    }
    if declarations is not None:
        doc["declarations"] = declarations
    return doc


def validate(doc: dict) -> dict:
    """Structural validation, strict, with no permissive path.

    Deliberately hand-written rather than JSON Schema: v1.1 ships a schema
    file because it is frozen and externally consumed, while v2 is still
    moving, and a schema file that drifts from the code it describes is worse
    than none. When v2 freezes it gets a schema file the same way v1.1 did.
    """
    if not isinstance(doc, dict):
        raise SchemaVersionError(f"document is {type(doc).__name__}")
    version = doc.get("schema_version")
    if not isinstance(version, str):
        raise SchemaVersionError("schema_version missing or not a string")
    if version.split(".")[0] != SCHEMA_VERSION.split(".")[0]:
        raise SchemaVersionError(
            f"unsupported schema_version {version!r}; this consumer "
            f"understands major {SCHEMA_VERSION.split('.')[0]}. Refusing "
            f"rather than reinterpreting fields whose meaning may have "
            f"changed.")

    for key in ("profile", "system", "domains", "functions", "attribution",
                "evidence", "provenance"):
        if key not in doc:
            raise SchemaVersionError(f"missing required field: {key}")

    if doc["system"] not in SYSTEM_STATES:
        raise SchemaVersionError(f"unknown system state {doc['system']!r}")
    for name, state in doc["domains"].items():
        if state not in OBSERVATION_STATES:
            raise SchemaVersionError(
                f"unknown observation state {state!r} for domain {name}")
    for name, row in doc["functions"].items():
        if row.get("state") not in FUNCTION_STATES:
            raise SchemaVersionError(
                f"unknown function state {row.get('state')!r} for {name}")
        if "limiting_domain" not in row:
            raise SchemaVersionError(f"{name}: no limiting_domain field")
    if doc["attribution"].get("verdict") not in ATTRIBUTION_VERDICTS:
        raise SchemaVersionError(
            f"unknown attribution verdict "
            f"{doc['attribution'].get('verdict')!r}")

    # §3, enforced rather than asserted: no scalar health anywhere at the top
    # level. A document that acquired one would have changed what it means.
    for banned in ("score", "health", "health_score", "confidence", "index",
                   "grade", "percentage"):
        if banned in doc:
            raise SchemaVersionError(
                f"forbidden top-level field {banned!r}: v2 reports "
                f"categorical states and the evidence behind them, never a "
                f"scalar system health")
    return doc


def assert_schema_version(doc: dict, expected: str = SCHEMA_VERSION) -> None:
    got = doc.get("schema_version")
    if got != expected:
        raise SchemaVersionError(
            f"expected schema_version {expected!r}, got {got!r}")


# ------------------------------------------------------- the §33 interface
def function_eligible(doc: dict, function: str) -> dict:
    """§33's worked example, as an actual call.

        autopilot asks:  precision_navigation eligible?
        CSIA returns:    NO
        the autopilot owns the switching action.

    Returns the answer AND why, because an integration that only got a
    boolean would have no way to log what it acted on. It returns no command,
    and there is no function in this module that does.
    """
    row = doc.get("functions", {}).get(function)
    if row is None:
        return {"function": function, "eligible": None,
                "state": "UNKNOWN",
                "why": "this profile does not declare that function",
                "limiting_domain": None, "reason_codes": [],
                "fallback": None}
    return {
        "function": function,
        "eligible": row["state"] == "ELIGIBLE",
        "state": row["state"],
        "limiting_domain": row.get("limiting_domain"),
        "reason_codes": list(row.get("reason_codes", ())),
        "domain_states": dict(row.get("domain_states", {})),
        #: The host's own declared fallback, reported back. CSIA does not
        #: select it, command it, or recommend it (§33).
        "fallback": row.get("fallback"),
        "why": _why(row),
    }


def _why(row: dict) -> str:
    if row["state"] == "ELIGIBLE":
        return "every required domain met its requirement"
    lim = row.get("limiting_domain") or "an unidentified domain"
    codes = ", ".join(row.get("reason_codes", ())) or "no reason code"
    return f"limited by {lim}: {codes}"


def limiting_report(doc: dict) -> dict:
    """Which domain is holding back what — §17's central column."""
    out: dict = {}
    for name, row in sorted(doc.get("functions", {}).items()):
        lim = row.get("limiting_domain")
        if lim and row["state"] != "ELIGIBLE":
            out.setdefault(lim, []).append(name)
    return {"limiting": {k: sorted(v) for k, v in sorted(out.items())},
            "unlimited": sorted(n for n, r in doc.get("functions", {}).items()
                                if r["state"] == "ELIGIBLE")}
