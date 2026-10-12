"""Preflight: prove the rig is what you think it is, BEFORE anything flies.

WHAT THIS IS FOR
----------------
Every number a hardware trial produces is worthless if the thing that
produced it was not what the notebook says. This tool checks the claims a
trial depends on and writes them down, so a log can be attributed to a
build rather than to a memory of one.

It answers, in order:

    1. is the FROZEN CORE the frozen core?          identity
    2. can this process transmit to the vehicle?    safety
    3. does the adapter/contract exist for this platform?
    4. are the staleness timeouts derived, not guessed?
    5. which failsafe policy will be in force?
    6. can the log actually be written?
    7. is the software self-consistent right now?

EVERY CHECK HAS THREE OUTCOMES, AND ONLY ONE IS GREEN
-----------------------------------------------------
    PASS          the claim was checked and holds
    FAIL          the claim was checked and does not hold
    INCONCLUSIVE  the check could not be performed

INCONCLUSIVE IS NOT PASS. A check that could not run tells you nothing,
and this repository has already been bitten once by a skip that read as a
success. A preflight with any INCONCLUSIVE is not a green preflight.

WHAT IT DOES NOT DO
-------------------
It does not touch the vehicle, arm anything, or command anything. It
cannot: the connection it opens is the same read-only object the shadow
runner uses, and one of the checks is that the transmit surface is absent.

    python tools/deploy/preflight.py --platform ardupilot \
        --out preflight.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform as _platform
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"

FROZEN_PATHS = ("csia/trust_engine", "csia/diagnosis", "csia/runtime/online.py",
                "csia/runtime/failsafe.py", "csia/scenarios.py",
                "csia/profiles.py")

FREEZE_TAG = "csia-v1.0-research-final"


def _check(name, status, detail, **extra):
    row = {"check": name, "status": status, "detail": detail}
    row.update(extra)
    return row


# ---------------------------------------------------------------------------
# 1. identity
# ---------------------------------------------------------------------------

def check_frozen_core() -> list:
    """The frozen core must be byte-identical to what the evidence describes.

    Two independent ways, because each fails differently: the freeze TAG is
    the strongest check but is local-only on a fresh clone, and the recorded
    SOURCE DIGESTS are reproducible anywhere.
    """
    out = []

    tag_present = subprocess.run(
        ["git", "rev-parse", "--verify", FREEZE_TAG], cwd=ROOT,
        capture_output=True, text=True).returncode == 0
    if not tag_present:
        out.append(_check(
            "frozen_core_vs_tag", INCONCLUSIVE,
            f"tag {FREEZE_TAG} is not present in this clone (it is "
            f"local-only; push was refused 403). The source-digest check "
            f"below is the reproducible one."))
    else:
        diff = subprocess.run(
            ["git", "diff", "--stat", FREEZE_TAG, "--", *FROZEN_PATHS],
            cwd=ROOT, capture_output=True, text=True).stdout.strip()
        out.append(_check(
            "frozen_core_vs_tag", PASS if not diff else FAIL,
            "byte-identical to the freeze tag" if not diff
            else f"THE FROZEN CORE DIFFERS FROM {FREEZE_TAG}:\n{diff}"))

    digests = os.path.join(ROOT, "research", "physical_validation", "results",
                           "FROZEN_SOURCE_DIGESTS.json")
    if not os.path.exists(digests):
        out.append(_check("frozen_core_vs_source_digests", INCONCLUSIVE,
                          "FROZEN_SOURCE_DIGESTS.json is absent"))
        return out
    try:
        from tools.csia_experiment.build_e1_freeze_manifest import (sha256_file,
                                                                    sha256_tree)
        with open(digests, encoding="utf-8") as fh:
            recorded = json.load(fh)["digests"]
        wrong = []
        for rel, expected in sorted(recorded.items()):
            full = os.path.join(ROOT, rel)
            got = (sha256_tree(rel, source_only=True) if os.path.isdir(full)
                   else {"files": 1,
                         "sha256_of_file_manifest": sha256_file(full)})
            if got != expected:
                wrong.append(rel)
        out.append(_check(
            "frozen_core_vs_source_digests", PASS if not wrong else FAIL,
            f"{len(recorded)} paths match" if not wrong
            else f"CHANGED: {wrong}"))
    except Exception as exc:                                # noqa: BLE001
        out.append(_check("frozen_core_vs_source_digests", INCONCLUSIVE,
                          f"could not verify: {exc!r}"))
    return out


def check_version_provenance() -> list:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return [_check(
        "working_tree_clean", PASS if not dirty else FAIL,
        f"commit {commit[:12]}" if not dirty
        else ("the working tree is DIRTY. A trial run from an uncommitted "
              "tree cannot be attributed to a commit, and its log will "
              "name one that does not describe it."),
        commit=commit, dirty_files=len(dirty.splitlines()) if dirty else 0)]


# ---------------------------------------------------------------------------
# 2. safety
# ---------------------------------------------------------------------------

def check_no_command_authority() -> list:
    """The single property everything else rests on.

    CSIA is advisory. The guard makes transmission structurally impossible
    rather than merely absent, and this proves it on THIS build rather than
    trusting the design note.
    """
    out = []
    try:
        from csia.deploy.guard import (CommandAuthorityError,
                                       ReadOnlyMavlinkConnection,
                                       assert_no_command_capability)
    except Exception as exc:                                # noqa: BLE001
        return [_check("no_command_authority", INCONCLUSIVE,
                       f"the guard could not be imported: {exc!r}")]

    try:
        from csia.deploy.shadow import Mode
        modes = {m.name: m.may_command for m in Mode}
        bad = [k for k, v in modes.items() if v]
        out.append(_check(
            "no_mode_claims_command", PASS if not bad else FAIL,
            f"modes {sorted(modes)} all report may_command=False"
            if not bad else f"MODES CLAIMING COMMAND AUTHORITY: {bad}",
            modes=modes))
    except Exception as exc:                                # noqa: BLE001
        out.append(_check("no_mode_claims_command", INCONCLUSIVE, repr(exc)))

    # A read-only connection must not expose a transmit surface.
    #
    # USE THE GUARD'S OWN INTERFACE. A first version of this check probed
    # with `hasattr(conn, "write")`, which RAISES CommandAuthorityError
    # rather than returning False -- `hasattr` only swallows AttributeError.
    # So the probe tripped the very denial it was verifying and reported
    # DO_NOT_FLY on a healthy build. A preflight that cries wolf is worse
    # than none: it trains the operator to skip it.
    #
    # `assert_no_command_capability` returns the evidence dict that goes
    # into the flight-log header. Every send-capable name must come back
    # DENIED or ABSENT.
    try:
        class _Fake:
            def recv_match(self, *a, **k):
                return None

        conn = ReadOnlyMavlinkConnection(_Fake())
        evidence = assert_no_command_capability(conn)
        probes = evidence.get("probes", evidence)
        reachable = [n for n, verdict in probes.items()
                     if verdict not in ("DENIED", "ABSENT")]
        out.append(_check(
            "read_only_connection_has_no_transmit_surface",
            PASS if not reachable else FAIL,
            f"{len(probes)} send-capable names, all DENIED or ABSENT"
            if not reachable else f"REACHABLE TRANSMIT SURFACE: {reachable}",
            probes=probes))
    except CommandAuthorityError as exc:
        out.append(_check("read_only_connection_has_no_transmit_surface",
                          FAIL, f"the guard refused the connection: {exc}"))
    except Exception as exc:                                # noqa: BLE001
        out.append(_check("read_only_connection_has_no_transmit_surface",
                          INCONCLUSIVE, repr(exc)))
    return out


# ---------------------------------------------------------------------------
# 3-5. configuration
# ---------------------------------------------------------------------------

def check_platform(platform_name: str) -> list:
    out = []
    try:
        from csia.aircraft.adapters import get_adapter
        adapter = get_adapter(platform_name)
        out.append(_check("adapter_present", PASS,
                          f"{platform_name} -> {adapter.adapter_version}",
                          contract_version=getattr(
                              getattr(adapter, "contract", None),
                              "version", None)))
    except Exception as exc:                                # noqa: BLE001
        return [_check("adapter_present", FAIL,
                       f"no adapter for {platform_name!r}: {exc!r}")]

    try:
        from csia.v1_1.staleness import build_runtime_stale_timeouts
        timeouts = build_runtime_stale_timeouts(platform_name)
        ok = timeouts and all(v > 0 for v in timeouts.values())
        out.append(_check(
            "staleness_timeouts_derived", PASS if ok else FAIL,
            f"{len(timeouts)} nodes, derived from the channel contract "
            f"(no constant is introduced)" if ok
            else f"implausible timeouts: {timeouts}",
            timeouts={k: round(v, 4) for k, v in sorted(timeouts.items())}))
    except Exception as exc:                                # noqa: BLE001
        out.append(_check("staleness_timeouts_derived", INCONCLUSIVE,
                          repr(exc)))
    return out


def check_failsafe_policy(supervision: bool) -> list:
    """WHICH policy will run, stated before the flight rather than inferred
    from the log afterwards."""
    out = []
    try:
        from csia.runtime.failsafe import FailsafeConfig
        cfg = FailsafeConfig()
        out.append(_check(
            "failsafe_policy", PASS,
            "FROZEN_PLUS_DATA_LOSS_SUPERVISION" if supervision
            else "FROZEN_ONLY",
            policy=("FROZEN_PLUS_DATA_LOSS_SUPERVISION" if supervision
                    else "FROZEN_ONLY"),
            arm_time_s=cfg.arm_time, dwell_up_s=cfg.dwell_up,
            dwell_down_s=cfg.dwell_down))
    except Exception as exc:                                # noqa: BLE001
        return [_check("failsafe_policy", INCONCLUSIVE, repr(exc))]

    if supervision:
        try:
            from csia_supervision import (ALREADY_COVERED, DERIVED_FROM,
                                          UNANCHORED)
            unanchored = sorted(s for s, (_, p, _) in DERIVED_FROM.items()
                                if p == UNANCHORED)
            out.append(_check(
                "data_loss_rule_coverage", PASS,
                f"{len(DERIVED_FROM)} sensors covered; {sorted(ALREADY_COVERED)}"
                f" left to the frozen rule",
                sensors_covered=sorted(DERIVED_FROM),
                levels_that_are_a_choice=unanchored,
                note=("the levels for these two are NOT derived from "
                      "FailsafeConfig -- it has no threshold for them. "
                      "They are a judgement and are labelled as one.")))
        except Exception as exc:                            # noqa: BLE001
            out.append(_check("data_loss_rule_coverage", FAIL,
                              f"supervision requested but unavailable: {exc!r}"))
    return out


# ---------------------------------------------------------------------------
# 6-7. the boring ones that ruin trials
# ---------------------------------------------------------------------------

def check_log_destination(log_dir: str) -> list:
    path = os.path.join(ROOT, log_dir) if not os.path.isabs(log_dir) else log_dir
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".preflight_write_probe")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
    except Exception as exc:                                # noqa: BLE001
        return [_check("log_dir_writable", FAIL,
                       f"{path} is not writable: {exc!r}")]

    try:
        import shutil
        free_mb = shutil.disk_usage(path).free / (1024 * 1024)
    except Exception:                                       # noqa: BLE001
        return [_check("log_dir_writable", PASS, f"{path} is writable"),
                _check("log_dir_free_space", INCONCLUSIVE, "unknown")]

    # A 25 Hz flight log runs a few MB per minute; 200 MB is a long trial.
    enough = free_mb >= 200
    return [_check("log_dir_writable", PASS, f"{path} is writable"),
            _check("log_dir_free_space", PASS if enough else FAIL,
                   f"{free_mb:.0f} MB free"
                   + ("" if enough else " -- under 200 MB, a long trial will "
                                        "run out and the log is the trial"),
                   free_mb=round(free_mb, 1))]


def check_self_consistency() -> list:
    """A fast subset of the suite. Not the whole thing -- this runs in a
    field tent, and a preflight nobody waits for is a preflight nobody
    runs."""
    tests = ["tests/test_shadow_mode.py", "tests/test_shadow_transport.py",
             "tests/test_shadow_supervision_wiring.py",
             "tests/test_supervision_dataloss.py"]
    present = [t for t in tests if os.path.exists(os.path.join(ROOT, t))]
    missing = [t for t in tests if t not in present]
    if missing:
        # A named test that is not there is not "fewer tests", it is a
        # preflight checking something other than what it claims.
        return [_check("self_test", INCONCLUSIVE,
                       f"named test files are absent: {missing}")]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *present, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, timeout=900)
    return [_check("self_test", PASS if proc.returncode == 0 else FAIL,
                   proc.stdout.strip().splitlines()[-1] if proc.stdout
                   else "no output",
                   tests=present)]


# ---------------------------------------------------------------------------

def run(platform_name: str = "ardupilot", supervision: bool = False,
        log_dir: str = "logs/shadow", quick: bool = False) -> dict:
    checks = []
    checks += check_frozen_core()
    checks += check_version_provenance()
    checks += check_no_command_authority()
    checks += check_platform(platform_name)
    checks += check_failsafe_policy(supervision)
    checks += check_log_destination(log_dir)
    if not quick:
        checks += check_self_consistency()

    counts = {PASS: 0, FAIL: 0, INCONCLUSIVE: 0}
    for row in checks:
        counts[row["status"]] += 1
    if counts[FAIL]:
        verdict = "DO_NOT_FLY"
    elif counts[INCONCLUSIVE]:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "READY"

    return {
        "schema": "csia.deploy.preflight/1",
        "t_unix": time.time(),
        "platform": platform_name,
        "data_loss_supervision": supervision,
        "host": {"python": _platform.python_version(),
                 "system": _platform.system(),
                 "release": _platform.release(),
                 "machine": _platform.machine()},
        "checks": checks,
        "counts": counts,
        "verdict": verdict,
        "inconclusive_is_not_pass": (
            "a check that could not be performed tells you nothing. A "
            "preflight with any INCONCLUSIVE is not a green preflight, and "
            "this repository has already been bitten once by a skip that "
            "read as a success."),
        "what_this_does_not_establish": (
            "that the vehicle is airworthy, that the sensors are calibrated, "
            "or that any hypothesis is true. It establishes that the "
            "SOFTWARE is the software you think it is and cannot transmit."),
    }


INSTRUMENT = "tools.deploy.preflight"


def _controls():
    """Preflight must still be able to say NO.

    A preflight stuck on PASS is the most dangerous instrument in the
    repository: it is the last check before a flight. The pair uses the
    platform check, which depends on neither the working tree nor the host,
    so a dirty tree cannot make the control ambiguous.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _adapter(platform):
        rows = {r["check"]: r for r in check_platform(platform)}
        return rows["adapter_present"]["status"]

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="an unknown platform is refused",
            kind=POSITIVE,
            run=lambda: _adapter("not_a_real_autopilot"),
            expect=lambda st: st == FAIL,
            basis=("no adapter is registered under that name; FAIL follows "
                   "from the adapter registry, not from this tool"),
        ),
        negative=Control(
            name="a real platform is not refused",
            kind=NEGATIVE,
            run=lambda: _adapter("ardupilot"),
            expect=lambda st: st == PASS,
            basis=("the ardupilot adapter is registered and imported by the "
                   "runtime; a preflight that rejects it is broken"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", default="ardupilot")
    ap.add_argument("--data-loss-supervision", action="store_true")
    ap.add_argument("--log-dir", default="logs/shadow")
    ap.add_argument("--quick", action="store_true",
                    help="skip the self-test subset")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE. An instrument that cannot
    # demonstrate it still works may not emit an artifact (MX-025).
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    _control_report = guard(INSTRUMENT)

    report = run(args.platform, args.data_loss_supervision, args.log_dir,
                 args.quick)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".",
                    exist_ok=True)
        report = stamp(report, _control_report)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")

    width = max(len(c["check"]) for c in report["checks"])
    for row in report["checks"]:
        print(f"  {row['status']:13} {row['check']:{width}}  {row['detail']}")
    print(f"\n  PASS={report['counts'][PASS]}  "
          f"FAIL={report['counts'][FAIL]}  "
          f"INCONCLUSIVE={report['counts'][INCONCLUSIVE]}")
    print(f"\nPREFLIGHT: {report['verdict']}", file=sys.stderr)
    return 0 if report["verdict"] == "READY" else 1


if __name__ == "__main__":
    sys.exit(main())
