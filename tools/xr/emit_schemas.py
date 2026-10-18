"""Emit implementation-neutral JSON schemas for the mission-layer records.

WHY THEY ARE IMPLEMENTATION-NEUTRAL
-------------------------------------
A schema that names `csia` in every field describes CSIA, not the idea. These
eight schemas describe records that any diagnostic system could produce:
nothing in them requires a trust coefficient, a Bayesian update, a graph, or
this repository.

Where a CSIA-specific field is genuinely load-bearing it is kept and NAMED as
CSIA-specific rather than disguised. There is exactly one such case, and it is
`semantics_version` -- which identifies the evaluator that issued a record,
and without which a certificate cannot be checked against the evaluator that
would honour it.

WHY THEY ARE GENERATED FROM THE DATACLASSES
---------------------------------------------
So a schema cannot drift from the record it describes. A hand-written schema
says what someone believed the record contained when they last looked, and
this repository already has FL-001 as its standing evidence about hand lists.

    python tools/xr/emit_schemas.py --out-dir csia_mission/schemas
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import typing

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia_mission.capability import (                        # noqa: E402
    CAPABILITY_STATES, CapabilityContract, CapabilitySupportCertificate,
    REASON_CODES)
from csia_mission.compute import (COMPUTE_STATES,            # noqa: E402
                                  ComputeEvidence)
from csia_mission.product import (                           # noqa: E402
    MissionProductCertificate, MissionProductContract, PRODUCT_STATES,
    ProductAssuranceResult, QUALITY_PROPERTIES)
from csia_mission.registry import (MASS_STATUS,              # noqa: E402
                                   PayloadModule, SensorTransform,
                                   TRANSFORM_STATUS)

#: Enumerations attached to specific fields. Kept beside the generator rather
#: than inside the dataclasses, because a dataclass field type cannot carry
#: "one of these strings" without a dependency this package does not want.
ENUMS = {
    "support_status": CAPABILITY_STATES,
    "state": PRODUCT_STATES,
    "reason_codes": REASON_CODES,
    "mass_status": MASS_STATUS,
    "translation_status": TRANSFORM_STATUS,
    "rotation_status": TRANSFORM_STATUS,
    "availability": COMPUTE_STATES,
    "deadline_state": COMPUTE_STATES,
    "scheduler_state": COMPUTE_STATES,
    "memory_state": COMPUTE_STATES,
    "thermal_state": COMPUTE_STATES,
    "execution_state": COMPUTE_STATES,
    "integrity_state": COMPUTE_STATES,
}

#: Fields that are CSIA-specific and are kept anyway, with the reason. Listed
#: so the neutrality claim is checkable rather than asserted.
CSIA_SPECIFIC = {
    "semantics_version": (
        "identifies the evaluator that issued the record. A certificate "
        "carrying a different semantics version than the evaluator asked to "
        "honour it is stale by definition, so the field is load-bearing and "
        "is kept rather than disguised."),
}


def _json_type(annotation) -> dict:
    origin = typing.get_origin(annotation)
    if annotation in (str,):
        return {"type": "string"}
    if annotation in (bool,):
        return {"type": "boolean"}
    if annotation in (int,):
        return {"type": "integer"}
    if annotation in (float,):
        return {"type": "number"}
    if origin in (tuple, list) or annotation in (tuple, list):
        return {"type": "array"}
    if origin is dict or annotation is dict:
        return {"type": "object"}
    text = str(annotation)
    if "Mapping" in text or "dict" in text:
        return {"type": "object"}
    if "tuple" in text or "list" in text:
        return {"type": "array"}
    if "float" in text and "None" in text:
        return {"type": ["number", "null"]}
    if "str" in text and "None" in text:
        return {"type": ["string", "null"]}
    if "bool" in text and "None" in text:
        return {"type": ["boolean", "null"]}
    return {}


def schema_for(cls, title: str, description: str) -> dict:
    props, required = {}, []
    for f in dataclasses.fields(cls):
        entry = _json_type(f.type)
        if f.name in ENUMS:
            entry = {"type": "string", "enum": list(ENUMS[f.name])}
        if f.name == "reason_codes":
            entry = {"type": "array",
                     "items": {"type": "string",
                               "enum": list(ENUMS["reason_codes"])}}
        if f.name in CSIA_SPECIFIC:
            entry["x-csia-specific"] = CSIA_SPECIFIC[f.name]
        props[f.name] = entry
        if (f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING):  # type: ignore
            required.append(f.name)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "description": description,
        "type": "object",
        "properties": props,
        "required": sorted(required),
        "additionalProperties": True,
        "x-generated-from": f"{cls.__module__}.{cls.__qualname__}",
        "x-implementation-neutral": (
            "Nothing here requires a trust coefficient, a Bayesian update, a "
            "graph, or this repository. CSIA-specific fields, where any, "
            "carry x-csia-specific with the reason they are kept."),
    }


SCHEMAS = {
    "CapabilityContract": (
        CapabilityContract,
        "What a capability requires. Says nothing about when to use it."),
    "CapabilitySupportCertificate": (
        CapabilitySupportCertificate,
        "EXPERIMENTAL. Not certified, not certification-grade."),
    "MissionProductContract": (
        MissionProductContract,
        "A deliverable and its independently qualified quality properties."),
    "MissionProductAssuranceResult": (
        ProductAssuranceResult,
        "What a product's data may and may not be used for, right now."),
    "MissionProductCertificate": (
        MissionProductCertificate,
        "EXPERIMENTAL. Supports are reported separately, never as a grade."),
    "ComputeEvidence": (
        ComputeEvidence,
        "Platform-neutral. Unmeasurable fields stay UNKNOWN."),
    "PayloadModule": (
        PayloadModule,
        "A physical module. References the vehicle profile, does not copy "
        "it."),
    "SensorTransform": (
        SensorTransform,
        "Mount datum, device package, measurement origin and measurement "
        "axes, each with its own provenance status."),
}


def build() -> dict:
    out = {}
    for name, (cls, description) in sorted(SCHEMAS.items()):
        out[name] = schema_for(cls, name, description)
    out["_index"] = {
        "schema": "csia.mission.schema_index/1",
        "schemas": sorted(SCHEMAS),
        "quality_properties": list(QUALITY_PROPERTIES),
        "generated_by": "tools/xr/emit_schemas.py",
        "why_generated": ("so a schema cannot drift from the record it "
                          "describes. FL-001 is this repository's standing "
                          "evidence about hand-maintained lists."),
    }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed schemas differ from a "
                         "freshly generated set")
    args = ap.parse_args(argv)

    docs = build()
    if args.check:
        target = args.out_dir or os.path.join(ROOT, "csia_mission", "schemas")
        drift = []
        for name, doc in sorted(docs.items()):
            path = os.path.join(target, f"{name}.json")
            want = json.dumps(doc, indent=2, sort_keys=True) + "\n"
            if not os.path.exists(path):
                drift.append(f"{name}: not committed")
                continue
            with open(path, encoding="utf-8") as fh:
                if fh.read() != want:
                    drift.append(f"{name}: differs from the dataclass")
        if drift:
            print("SCHEMA DRIFT:\n  " + "\n  ".join(drift), file=sys.stderr)
            return 1
        print(f"schemas match their dataclasses ({len(docs)} files)")
        return 0

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        for name, doc in sorted(docs.items()):
            path = os.path.join(args.out_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, sort_keys=True)
                fh.write("\n")
            print(f"wrote {path}")
    else:
        print(json.dumps(docs, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
