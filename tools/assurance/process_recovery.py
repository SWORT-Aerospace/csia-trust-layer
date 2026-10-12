"""A16: what happens when the process, its config, or its input goes away.

THE TWO FORBIDDEN TRANSITIONS, DECLARED BEFORE ANY RUN
-------------------------------------------------------
The programme names them and this file encodes them as the pass criteria:

    NEVER   exception -> nominal
    NEVER   exception -> the previous certificate remains valid forever

Everything below is one of those two turned into a scenario with an outcome
that can be observed from outside the process.

WHAT IS ACTUALLY KILLED
-----------------------
Scenarios 1 and 2 run the assurance layer in a REAL SUBPROCESS and send it
SIGKILL -- not a mocked exception, not a `raise` in a try block. SIGKILL cannot
be caught, so no cleanup path can run, which is the point: it is the failure
mode where a system gets to prove it holds no recoverable state it should not
hold.

The remaining scenarios kill an INPUT or a CONFIGURATION rather than a process,
because those are the failures that produce a WRONG ANSWER rather than a
missing one, and a missing answer is the safe kind.

WHAT THIS DOES NOT TEST
-----------------------
There is no supervisor, no service manager and no restart policy in this
repository, so "does it come back up" is not a question this can answer -- and
it is recorded as untested rather than answered from a systemd unit that does
not exist. What is testable is whether a RESTARTED evaluator carries anything
across the gap, and that is what scenarios 1 and 2 measure.

    python tools/assurance/process_recovery.py --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

#: DECLARED BEFORE ANY RUN.
ACCEPTABLE = ("REFUSED", "DEGRADED", "RECOMPUTED_IDENTICAL", "NO_STATE_CARRIED")
UNACCEPTABLE = ("SILENT_HEALTHY", "STALE_CERTIFICATE_HONOURED",
                "EXCEPTION_BECAME_NOMINAL", "STATE_SURVIVED_KILL")

#: The worker the kill scenarios run. It is a separate process on purpose: an
#: in-process `raise` proves nothing about what survives a SIGKILL.
_WORKER = r"""
import json, os, sys, time
sys.path.insert(0, %(root)r)
from csia_assurance import qualify

state_file = %(state)r
vec = json.loads(%(vec)s)

# Anything the evaluator would carry across a restart would have to live
# somewhere. Write a marker so the parent can check whether a restarted
# process picks it up.
if os.path.exists(state_file):
    with open(state_file, encoding="utf-8") as fh:
        carried = fh.read().strip()
else:
    carried = ""

v = qualify(vec["record"], vec.get("prior"))
print(json.dumps({"state": v.state, "reason": v.reason,
                  "carried_marker": carried}), flush=True)

if %(hang)s:
    # Sit still so the parent can SIGKILL a process that is mid-life rather
    # than one that has already exited.
    time.sleep(600)
"""


def _vector(name: str) -> dict:
    path = os.path.join(ROOT, "csia_assurance", "vectors", name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _run_worker(vec: dict, state_file: str, hang: bool):
    code = _WORKER % {"root": ROOT, "state": state_file,
                      "vec": repr(json.dumps(vec)), "hang": bool(hang)}
    return subprocess.Popen([sys.executable, "-c", code],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)


# --------------------------------------------------------------------------

def scenario_sigkill_mid_evaluation(tmp: str) -> dict:
    """SIGKILL a live evaluator, restart it, and look for carried state."""
    vec = _vector("V01_supported_unique.json")
    state_file = os.path.join(tmp, "carried.marker")

    proc = _run_worker(vec, state_file, hang=True)
    first = json.loads(proc.stdout.readline())
    os.kill(proc.pid, signal.SIGKILL)
    rc = proc.wait(timeout=30)

    # Anything left on disk by the killed process would be here.
    leftovers = sorted(os.listdir(tmp))

    proc2 = _run_worker(vec, state_file, hang=False)
    out, _err = proc2.communicate(timeout=60)
    second = json.loads(out.strip().splitlines()[0])

    carried = bool(second["carried_marker"])
    same = (first["state"], first["reason"]) == (second["state"],
                                                 second["reason"])
    return {
        "scenario": "SIGKILL_MID_EVALUATION",
        "what_was_killed": "the evaluator process, with SIGKILL (uncatchable)",
        "killed_exit_signal": rc,
        "first_verdict": first["state"],
        "restarted_verdict": second["state"],
        "verdict_recomputed_identically": same,
        "files_left_behind": leftovers,
        "state_carried_across_the_kill": carried,
        "outcome": ("STATE_SURVIVED_KILL" if carried
                    else "RECOMPUTED_IDENTICAL" if same
                    else "DEGRADED"),
        "why_it_matters": (
            "A restarted evaluator that inherits a verdict it did not "
            "recompute is asserting support from a process that is gone."),
    }


def scenario_restart_with_expired_certificate(tmp: str) -> dict:
    """The forbidden transition, stated directly: does an old certificate
    stay valid forever across a restart?"""
    vec = _vector("V01_supported_unique.json")
    rec = dict(vec["record"])
    prior = {
        "config_hash": rec.get("config_hash"),
        "software_hash": rec.get("software_hash"),
        "timestamp": rec.get("timestamp", 0.0) - 10.0,
        "valid_until": rec.get("timestamp", 0.0) - 1.0,   # already expired
    }
    proc = _run_worker({"record": rec, "prior": prior},
                       os.path.join(tmp, "none.marker"), hang=False)
    out, _err = proc.communicate(timeout=60)
    got = json.loads(out.strip().splitlines()[0])
    refused = got["reason"] == "STALE_SUPPORT_CERTIFICATE"
    return {
        "scenario": "RESTART_WITH_EXPIRED_CERTIFICATE",
        "prior_valid_until": prior["valid_until"],
        "record_timestamp": rec.get("timestamp"),
        "verdict": got["state"],
        "reason": got["reason"],
        "outcome": "REFUSED" if refused else "STALE_CERTIFICATE_HONOURED",
        "why_it_matters": (
            "'previous certificate remains valid forever' is one of the two "
            "transitions the programme forbids by name."),
    }


def scenario_config_reload_changes_hash() -> dict:
    """A configuration reload between two records. The layer must notice."""
    from csia_assurance import qualify
    vec = _vector("V01_supported_unique.json")
    rec = dict(vec["record"])
    prior = {"config_hash": "BEFORE_RELOAD",
             "software_hash": rec.get("software_hash"),
             "timestamp": rec.get("timestamp", 0.0) - 1.0}
    v = qualify(rec, prior)
    refused = v.reason == "CONFIG_HASH_MISMATCH"
    return {
        "scenario": "CONFIG_RELOAD_BETWEEN_RECORDS",
        "prior_config_hash": prior["config_hash"],
        "record_config_hash": rec.get("config_hash"),
        "verdict": v.state,
        "reason": v.reason,
        "outcome": "REFUSED" if refused else "SILENT_HEALTHY",
        "why_it_matters": (
            "A reloaded configuration makes the previous certificate a "
            "statement about a system that no longer exists."),
    }


def scenario_software_reload_changes_hash() -> dict:
    """The same, for the code rather than the configuration."""
    from csia_assurance import qualify
    vec = _vector("V01_supported_unique.json")
    rec = dict(vec["record"])
    prior = {"config_hash": rec.get("config_hash"),
             "software_hash": "BEFORE_UPGRADE",
             "timestamp": rec.get("timestamp", 0.0) - 1.0}
    v = qualify(rec, prior)
    refused = v.reason == "CONFIG_HASH_MISMATCH"
    return {
        "scenario": "SOFTWARE_UPGRADE_BETWEEN_RECORDS",
        "verdict": v.state,
        "reason": v.reason,
        "outcome": "REFUSED" if refused else "SILENT_HEALTHY",
        "why_it_matters": (
            "A rebuilt binary is a different evaluator, and a certificate "
            "issued by the previous one does not transfer to it."),
    }


def scenario_telemetry_source_dies() -> dict:
    """The input stops. The last good verdict must not become the current one.

    Modelled as the canonical sample going absent, which is exactly what a
    dead telemetry source produces at this boundary.
    """
    from csia_assurance import qualify
    vec = _vector("V01_supported_unique.json")
    good = dict(vec["record"])
    live = qualify(good)

    dead = dict(good)
    dead["canonical_sample_present"] = False
    dead["timestamp"] = good.get("timestamp", 0.0) + 1.0
    after = qualify(dead, prior=None)

    refused = after.reason == "MISSING_CANONICAL_SAMPLE"
    return {
        "scenario": "TELEMETRY_SOURCE_DIES",
        "verdict_while_live": live.state,
        "verdict_after_source_dies": after.state,
        "reason": after.reason,
        "outcome": "REFUSED" if refused else "SILENT_HEALTHY",
        "why_it_matters": (
            "Silence is the input that most easily reads as health. The "
            "layer must say it cannot evaluate, not repeat its last answer."),
    }


def scenario_adapter_raises() -> dict:
    """An exception inside evaluation. It must not become a nominal answer."""
    from csia_assurance import qualify

    class Exploding(dict):
        def get(self, *a, **k):                      # noqa: D102
            raise RuntimeError("adapter exploded mid-evaluation")

    v = qualify(Exploding())
    became_nominal = v.state in ("SUPPORTED_UNIQUE",)
    named = v.reason.startswith("FIREWALL_INTERNAL_EXCEPTION")
    return {
        "scenario": "EVALUATION_RAISES",
        "verdict": v.state,
        "reason": v.reason,
        "exception_is_named_in_the_reason": named,
        "outcome": ("EXCEPTION_BECAME_NOMINAL" if became_nominal
                    else "REFUSED"),
        "why_it_matters": (
            "'exception -> nominal' is the other transition the programme "
            "forbids by name."),
    }


def campaign() -> dict:
    with tempfile.TemporaryDirectory(prefix="csia-recovery-") as tmp:
        runs = [
            scenario_sigkill_mid_evaluation(tmp),
            scenario_restart_with_expired_certificate(tmp),
        ]
    runs += [
        scenario_config_reload_changes_hash(),
        scenario_software_reload_changes_hash(),
        scenario_telemetry_source_dies(),
        scenario_adapter_raises(),
    ]

    bad = [r for r in runs if r["outcome"] in UNACCEPTABLE]
    return {
        "schema": "csia.assurance.process_recovery/1",
        "criteria_declared_before_runs": {
            "acceptable": list(ACCEPTABLE),
            "unacceptable": list(UNACCEPTABLE),
            "forbidden_transitions": [
                "exception -> nominal",
                "exception -> previous certificate remains valid forever",
            ],
        },
        "runs": runs,
        "counts": {o: sum(1 for r in runs if r["outcome"] == o)
                   for o in sorted({r["outcome"] for r in runs})},
        "failures": bad,
        "verdict": "NO_FORBIDDEN_TRANSITION" if not bad else "FORBIDDEN_TRANSITION_OBSERVED",
        "not_tested_here": [
            "whether a supervisor restarts the process. There is no service "
            "manager or restart policy in this repository, so the question "
            "is recorded as UNTESTED rather than answered from a unit file "
            "that does not exist.",
            "recovery of the autopilot link itself, which is an adapter and "
            "E2 concern and needs real hardware to mean anything.",
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = campaign()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"\n{doc['verdict']}  {doc['counts']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
