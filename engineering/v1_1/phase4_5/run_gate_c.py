"""Phase 4.5 Gate C: prove the v1.1 schema can actually be consumed.

The consumer under test is `csia/v1_1/monitor.py`. It imports no producer —
not the trust engine, not the diagnosis, not the eligibility policy, not the
ledger — so anything it can show came out of the payload and nothing else.

Four things are demonstrated, in order:

  §15  the GNSS fix-loss payload is NOT reduced to "GPS healthy"
  §16  six rejection paths, none of them permissive
  §17  a v1 consumer takes the documented projection or refuses the payload
  §18  every control operation is denied through the output firewall

    python engineering/v1_1/phase4_5/run_gate_c.py
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.deploy.guard import CommandAuthorityError                # noqa: E402
from csia.v1_1 import output_api as API                            # noqa: E402
from csia.v1_1.monitor import Monitor, PayloadRejected, parse      # noqa: E402

CLEAN = os.path.join(ENG, "csia_output_example.json")
FIXLOSS = os.path.join(ENG, "csia_output_fixloss_example.json")
STREAM = os.path.join(ENG, "api_consumer_stream.jsonl")

#: §18. Every one must be denied, including an operation nobody has invented.
CONTROL_ATTEMPTS = ("SET_FLIGHT_MODE", "WRITE_PARAMETER", "RTL", "LAND",
                    "SOMETHING_NOBODY_HAS_WRITTEN_YET")


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------- §16
def _negative_cases(good):
    """Six rejection paths. Each perturbs exactly one thing."""
    unknown_version = dict(good, schema_version="2.0.0")

    malformed = "this is not a payload"

    missing = copy.deepcopy(good)
    del missing["diagnosis"]["posterior"]

    kh = copy.deepcopy(good)
    kh["sequential"]["h"] = 5.0            # the textbook value that FAILED

    mode = copy.deepcopy(good)
    mode["trust"]["mode"] = "FLAT_V2_EXPERIMENTAL"

    state = copy.deepcopy(good)
    first = sorted(state["function_eligibility"])[0]
    state["function_eligibility"][first]["state"] = "PROBABLY_FINE"

    return [
        ("unknown_schema_version", unknown_version),
        ("malformed_payload", malformed),
        ("missing_required_field", missing),
        ("sequential_kh_mismatch", kh),
        ("unknown_trust_mode", mode),
        ("unknown_function_state", state),
    ]


# ------------------------------------------------------------------- §17
def _v1_consumer(obj):
    """A pre-Phase-4 consumer, modelled by what it required.

    It knows five fields and their v1 meanings and refuses anything else. It
    is deliberately NOT permissive: that is the behaviour §26 demands of a
    consumer facing a schema it does not understand.
    """
    expected = {"t", "level", "trust", "posterior", "leader"}
    if not isinstance(obj, dict) or not expected <= set(obj):
        raise PayloadRejected(
            "v1 consumer: payload does not carry the v1 field set "
            f"{sorted(expected)}; refusing rather than guessing")
    return {"t": obj["t"], "level": obj["level"], "leader": obj["leader"]}


def main() -> int:
    clean, fixloss = _load(CLEAN), _load(FIXLOSS)

    # ---- a real stream through the real file path -----------------------
    with open(STREAM, "w", encoding="utf-8") as fh:
        for payload in (clean, fixloss):
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
    mon = Monitor()
    mon.consume_jsonl(STREAM)

    # ---- §15: the case the consumer must not flatten --------------------
    view = parse(fixloss)
    rendered = view.render()
    leader_line = view.format_leader()
    fix = {
        "timestamp": view.timestamp,
        "primary_status": view.primary_status,
        "gps_trust_in_payload": view.trust.get("gps"),
        "leader": view.leader, "posterior": view.posterior,
        "support_state": view.support_state,
        "discriminating_evidence_count": view.discriminating_evidence_count,
        "functions_unavailable": list(view.unavailable),
        "recommendations": list(view.recommendations),
        "leader_rendering": leader_line,
        "primary_status_mentions_posterior":
            f"{view.posterior:.4f}" in view.primary_status,
        "primary_status_mentions_healthy":
            any(w in view.primary_status.lower()
                for w in ("healthy", "ok", "nominal", "fine")),
        "posterior_never_rendered_bare":
            view.support_state in leader_line
            and str(view.discriminating_evidence_count) in leader_line,
        "rendered": rendered,
    }

    # ---- §16 -------------------------------------------------------------
    negatives = []
    for name, bad in _negative_cases(clean):
        probe = Monitor()
        try:
            if isinstance(bad, dict):
                accepted = probe.consume(bad) is not None
            else:
                parse(bad)
                accepted = True
        except PayloadRejected as exc:
            negatives.append({"case": name, "rejected": True,
                              "reason": str(exc)[:200]})
            continue
        negatives.append({
            "case": name, "rejected": not accepted,
            "reason": (probe.rejected[0][:200] if probe.rejected
                       else "ACCEPTED — this is a failure")})

    # ---- §17 -------------------------------------------------------------
    projection = API.project_v1(clean)
    compat = {"projection_fields": sorted(projection)}
    try:
        compat["v1_consumer_on_projection"] = _v1_consumer(projection)
        compat["projection_accepted"] = True
    except PayloadRejected as exc:
        compat["projection_accepted"] = False
        compat["projection_error"] = str(exc)
    try:
        _v1_consumer(clean)
        compat["raw_v1_1_accepted_by_v1_consumer"] = True
    except PayloadRejected as exc:
        compat["raw_v1_1_accepted_by_v1_consumer"] = False
        compat["raw_v1_1_refusal"] = str(exc)[:160]
    compat["projection_carries_trust_mode"] = (
        projection.get("trust_mode") == clean["trust"]["mode"])
    try:
        API.project_v1(dict(clean, schema_version="2.0.0"))
        compat["version_mismatch_refused"] = False
    except API.SchemaVersionError:
        compat["version_mismatch_refused"] = True

    # ---- §18 -------------------------------------------------------------
    fw_mon = Monitor()
    denied = []
    for op in CONTROL_ATTEMPTS:
        try:
            fw_mon.act(op)
            denied.append({"operation": op, "denied": False})
        except CommandAuthorityError as exc:
            denied.append({"operation": op, "denied": True,
                           "error": str(exc)[:120]})
    permitted = []
    for op in ("READ_TELEMETRY", "WRITE_LOG", "EMIT_OUTPUT"):
        permitted.append({"operation": op, "allowed": fw_mon.act(op) == op})

    results = {
        "artifact": "API_CONSUMER_RESULTS",
        "generation_command":
            "python engineering/v1_1/phase4_5/run_gate_c.py",
        "csia_sha": _git("rev-parse", "HEAD"),
        "consumer": "csia/v1_1/monitor.py",
        "schema_version_consumed": API.SCHEMA_VERSION,
        "stream": os.path.relpath(STREAM, ROOT),
        "payloads_accepted": mon.accepted,
        "payloads_rejected": len(mon.rejected),
        "fix_loss_interpretation": fix,
        "negative_tests": negatives,
        "all_negative_tests_rejected": all(n["rejected"] for n in negatives),
        "compatibility": compat,
        "firewall": {"denied": denied, "permitted": permitted,
                     "all_control_denied": all(d["denied"] for d in denied),
                     "evidence": fw_mon.firewall.evidence()},
        "gate_E_consumer_pass": bool(
            mon.accepted == 2 and not mon.rejected
            and all(n["rejected"] for n in negatives)
            and not fix["primary_status_mentions_healthy"]
            and not fix["primary_status_mentions_posterior"]
            and fix["posterior_never_rendered_bare"]),
        "gate_F_firewall_pass": bool(
            all(d["denied"] for d in denied)
            and all(p["allowed"] for p in permitted)),
    }
    with open(os.path.join(ENG, "API_CONSUMER_RESULTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"consumed {mon.accepted} payloads, {len(mon.rejected)} rejected")
    print("--- fix-loss, as an external integration sees it ---")
    print(rendered)
    print("--- negative tests ---")
    for n in negatives:
        print(f"  {n['case']:26s} rejected={n['rejected']}")
    print("--- firewall ---")
    for d in denied:
        print(f"  {d['operation']:34s} denied={d['denied']}")
    print(f"gate E (consumer)={results['gate_E_consumer_pass']}  "
          f"gate F (firewall)={results['gate_F_firewall_pass']}")
    return 0 if (results["gate_E_consumer_pass"]
                 and results["gate_F_firewall_pass"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
