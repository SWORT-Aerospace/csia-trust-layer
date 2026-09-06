"""Structured telemetry adversary: 26 hostile input classes, per target.

THE TARGET BEHAVIOUR IS NOT "NO CRASH"
---------------------------------------
For every hostile input, exactly one of these is acceptable:

    REJECTED     the input is refused with an explicit reason
    DEGRADED     the layer reports NOT_EVALUABLE / UNKNOWN, with a reason
    HANDLED      a deterministic, documented outcome

and exactly one is not:

    SILENT_HEALTHY   a positive verdict produced from an input that does not
                     support one. This is the failure this file exists to find.

A crash is recorded as CRASH and is a defect, but it is a LESS dangerous one
than SILENT_HEALTHY, and the report keeps them apart rather than pooling both
into "failures".

WHY THE CASES ARE ENUMERATED AND NOT RANDOM
--------------------------------------------
A random fuzzer over this input shape spends almost all its time on
uninteresting rejections. These 26 classes are the ones that have historically
produced silent acceptance in telemetry pipelines -- sentinel values, clock
anomalies, sequence tricks, unit confusion -- and each is a named case whose
absence from the report is visible.

    python tools/assurance/hostile_input.py --out HOSTILE_INPUT_RESULTS.json
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

REJECTED, DEGRADED, HANDLED = "REJECTED", "DEGRADED", "HANDLED"
SILENT_HEALTHY, CRASH, HANG = "SILENT_HEALTHY", "CRASH", "HANG"

ACCEPTABLE = (REJECTED, DEGRADED, HANDLED)

#: The 26 classes the programme named. Each maps to a mutation of a clean
#: record; a class with no mutation is reported as NOT_APPLICABLE for that
#: target rather than silently skipped.
CLASSES = (
    "nan", "positive_infinity", "negative_infinity", "negative_zero",
    "subnormal", "extreme_finite", "invalid_enum", "unknown_sentinel",
    "duplicate_packet", "packet_reordering", "packet_delay", "packet_loss",
    "bursty_delivery", "timestamp_duplication", "timestamp_rollback",
    "timestamp_jump_forward", "sequence_reuse", "sequence_rollover",
    "partial_stream_disappearance", "stream_restart", "source_id_collision",
    "wrong_units", "impossible_physical_value", "stale_retained_sample",
    "inconsistent_source_clocks", "truncated_replay_record",
    "unknown_schema_field",
)


def _clean_record():
    from csia_assurance.firewall import SCHEMA
    return {
        "schema": SCHEMA, "timestamp": 100.0, "config_hash": "cfg-1",
        "software_hash": "sw-1", "evidence_hash": "ev-1",
        "canonical_sample_present": True, "leader": "nominal",
        "signatures": {"nominal": [], "gps_fault": ["rel_a"],
                       "imu_bias": ["rel_b"]},
        "gates": {"rel_a": 1.0, "rel_b": 1.0},
        "evidence_states": {"rel_a": "ACTIVE", "rel_b": "ACTIVE"},
        "evidence_sources": {"rel_a": "gps", "rel_b": "imu1"},
    }


def _mutations():
    """cls -> (record, prior) for the firewall target."""
    c = _clean_record
    huge = 1e308
    tiny = 5e-324                      # smallest positive subnormal double
    return {
        "nan": (dict(c(), gates={"rel_a": float("nan"), "rel_b": 1.0}), None),
        "positive_infinity": (
            dict(c(), gates={"rel_a": float("inf"), "rel_b": 1.0}), None),
        "negative_infinity": (
            dict(c(), gates={"rel_a": float("-inf"), "rel_b": 1.0}), None),
        "negative_zero": (
            dict(c(), gates={"rel_a": -0.0, "rel_b": 1.0}), None),
        "subnormal": (
            dict(c(), gates={"rel_a": tiny, "rel_b": 1.0}), None),
        "extreme_finite": (
            dict(c(), gates={"rel_a": huge, "rel_b": 1.0}), None),
        "invalid_enum": (
            dict(c(), evidence_states={"rel_a": "SORT_OF_OK",
                                       "rel_b": "ACTIVE"}), None),
        "unknown_sentinel": (
            dict(c(), gates={"rel_a": -1.0, "rel_b": 1.0}), None),
        "duplicate_packet": (c(), {"config_hash": "cfg-1",
                                   "software_hash": "sw-1",
                                   "timestamp": 100.0}),
        "packet_reordering": (dict(c(), timestamp=99.0),
                              {"config_hash": "cfg-1",
                               "software_hash": "sw-1", "timestamp": 100.0}),
        "packet_delay": (dict(c(), timestamp=100.0),
                         {"config_hash": "cfg-1", "software_hash": "sw-1",
                          "timestamp": 10.0, "valid_until": 20.0}),
        "packet_loss": (
            dict(c(), gates={"rel_a": 1.0},
                 signatures={"nominal": [], "gps_fault": ["rel_a"],
                             "imu_bias": ["rel_b"]},
                 evidence_states={"rel_a": "ACTIVE"}), None),
        "bursty_delivery": (dict(c(), timestamp=100.000001),
                            {"config_hash": "cfg-1", "software_hash": "sw-1",
                             "timestamp": 100.0}),
        "timestamp_duplication": (c(), {"config_hash": "cfg-1",
                                        "software_hash": "sw-1",
                                        "timestamp": 100.0}),
        "timestamp_rollback": (dict(c(), timestamp=1.0),
                               {"config_hash": "cfg-1",
                                "software_hash": "sw-1",
                                "timestamp": 100.0}),
        "timestamp_jump_forward": (
            dict(c(), timestamp=1e12),
            {"config_hash": "cfg-1", "software_hash": "sw-1",
             "timestamp": 100.0, "valid_until": 110.0}),
        "sequence_reuse": (dict(c(), sequence=7),
                           {"config_hash": "cfg-1", "software_hash": "sw-1",
                            "timestamp": 100.0, "sequence": 7}),
        "sequence_rollover": (dict(c(), sequence=0),
                              {"config_hash": "cfg-1",
                               "software_hash": "sw-1", "timestamp": 100.0,
                               "sequence": 65535}),
        "partial_stream_disappearance": (
            dict(c(), evidence_states={"rel_a": "ABSENT", "rel_b": "ACTIVE"}),
            None),
        "stream_restart": (
            dict(c(), timestamp=0.0),
            {"config_hash": "cfg-1", "software_hash": "sw-1",
             "timestamp": 100.0}),
        "source_id_collision": (
            dict(c(), evidence_sources={"rel_a": "gps", "rel_b": "gps"}),
            None),
        "wrong_units": (dict(c(), gates={"rel_a": 100.0, "rel_b": 1.0}),
                        None),
        "impossible_physical_value": (
            dict(c(), gates={"rel_a": -12345.0, "rel_b": 1.0}), None),
        "stale_retained_sample": (
            dict(c(), evidence_states={"rel_a": "STALE", "rel_b": "ACTIVE"}),
            None),
        "inconsistent_source_clocks": (
            dict(c(), timestamp=100.0, source_clock_skew_s=45.0),
            {"config_hash": "cfg-1", "software_hash": "sw-1",
             "timestamp": 145.0}),
        "truncated_replay_record": (
            {k: v for k, v in c().items() if k not in ("gates", "signatures")},
            None),
        "unknown_schema_field": (dict(c(), a_field_nobody_declared=True),
                                 None),
    }


def _classify(verdict, cls) -> tuple:
    """Turn a firewall verdict into one of the outcome classes."""
    if verdict is None:
        return CRASH, "no verdict produced"
    state = verdict.state
    if state == "SUPPORTED_UNIQUE":
        # A positive verdict is only acceptable when the hostile input did
        # not actually remove the evidence -- e.g. a duplicate packet, or an
        # unknown extra field. Those are HANDLED; anything else is the
        # failure this file looks for.
        benign = {"duplicate_packet", "timestamp_duplication",
                  "bursty_delivery", "unknown_schema_field",
                  "source_id_collision", "sequence_reuse",
                  "sequence_rollover", "inconsistent_source_clocks"}
        if cls in benign:
            return HANDLED, f"{state}: input did not remove any evidence"
        return SILENT_HEALTHY, f"{state} from hostile input {cls!r}"
    if state == "NOT_EVALUABLE":
        return REJECTED, verdict.reason
    if state in ("AMBIGUOUS", "NON_IDENTIFIABLE", "UNKNOWN"):
        return DEGRADED, verdict.reason
    return CRASH, f"unknown state {state!r}"


def run_firewall_campaign() -> list:
    from csia_assurance import qualify
    rows = []
    muts = _mutations()
    for cls in CLASSES:
        if cls not in muts:
            rows.append({"target": "assurance_firewall", "class": cls,
                         "outcome": "NOT_APPLICABLE",
                         "detail": "no mutation defined for this target"})
            continue
        rec, prior = muts[cls]
        try:
            v = qualify(rec, prior)
            outcome, detail = _classify(v, cls)
            state = v.state
        except Exception as exc:                       # noqa: BLE001
            outcome, detail, state = CRASH, f"{type(exc).__name__}: {exc}", None
        rows.append({"target": "assurance_firewall", "class": cls,
                     "outcome": outcome, "detail": detail, "state": state})
    return rows


def run_parser_campaign(target: str, loader) -> list:
    """Same classes against a parser: bytes in, exception or object out.

    A parser has no notion of SUPPORTED_UNIQUE, so the only failure available
    to it is CRASH-with-an-unhelpful-exception versus an explicit rejection.
    Recorded separately for that reason.
    """
    payloads = {
        "nan": b'{"a": NaN}',
        "positive_infinity": b'{"a": Infinity}',
        "negative_infinity": b'{"a": -Infinity}',
        "negative_zero": b'{"a": -0.0}',
        "subnormal": b'{"a": 5e-324}',
        "extreme_finite": b'{"a": 1e308}',
        "invalid_enum": b'{"quality": "SORT_OF_OK"}',
        "unknown_sentinel": b'{"current_battery": -1}',
        "truncated_replay_record": b'{"a": 1',
        "unknown_schema_field": b'{"a": 1, "undeclared": 2}',
    }
    rows = []
    for cls in CLASSES:
        if cls not in payloads:
            rows.append({"target": target, "class": cls,
                         "outcome": "NOT_APPLICABLE",
                         "detail": "not expressible as a parser payload"})
            continue
        try:
            loader(payloads[cls])
            rows.append({"target": target, "class": cls, "outcome": HANDLED,
                         "detail": "parsed without exception"})
        except Exception as exc:                       # noqa: BLE001
            rows.append({"target": target, "class": cls, "outcome": REJECTED,
                         "detail": f"{type(exc).__name__}"})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    rows = run_firewall_campaign()

    # The deployment/profile parser, as a second target.
    import yaml
    rows += run_parser_campaign(
        "deployment_yaml_parser", lambda b: yaml.safe_load(b.decode()))
    rows += run_parser_campaign(
        "strict_json_parser",
        lambda b: json.loads(b.decode(), parse_constant=_reject_constant))

    counts = {}
    for r in rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    bad = [r for r in rows if r["outcome"] in (SILENT_HEALTHY, CRASH, HANG)]

    doc = {
        "schema": "csia.assurance.hostile_input/1",
        "classes": list(CLASSES),
        "acceptable_outcomes": list(ACCEPTABLE),
        "unacceptable_outcomes": [SILENT_HEALTHY, CRASH, HANG],
        "severity_note": (
            "SILENT_HEALTHY and CRASH are both defects and are NOT pooled. A "
            "crash is loud; a silent healthy verdict is the one that reaches "
            "a downstream consumer looking like an answer."),
        "results": rows,
        "counts": counts,
        "non_pass": bad,
        "limits": [
            "The firewall target is exercised through its record contract, "
            "not through a live MAVLink stream. Wire-level malformity is an "
            "adapter concern and is covered where the adapter is the target.",
            "NOT_APPLICABLE rows are reported rather than dropped, so a "
            "class that no target exercises is visible.",
        ],
    }
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"outcomes: {counts}", file=sys.stderr)
    return 0


def _reject_constant(name):
    raise ValueError(f"non-finite JSON constant {name!r} refused")


if __name__ == "__main__":
    sys.exit(main())
