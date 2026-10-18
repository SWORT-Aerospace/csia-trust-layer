"""csia-edge: the profile-first entry point for plugging CSIA into a vehicle.

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT
---------------------------------------------
It is NOT a second runtime. `csia/deploy/shadow.py` is the runtime, it is
mature, it structurally denies the transmit surface, and building a parallel
one would repeat the mistake this program avoided in P1 -- two stacks and a
silent question about which one flies. `csia-edge run` hands off to it.

What is genuinely missing, and what this module adds, is the step BEFORE
running: answering "can CSIA use this vehicle, and what will it be blind to?"
from a profile, mechanically, before anything is connected.

THE SEAM THIS MODULE EXPOSES RATHER THAN HIDES
-----------------------------------------------
This repository now has two configuration concepts that overlap:

  configs/vehicle/*.yaml   the DEPLOYMENT config. How to connect, which
                           serial port, which CSIA mode, where logs go,
                           which autopilot stream parameters to demand. Its
                           SHA-256 goes into every flight-log header.

  profiles/*.yaml          the VEHICLE PROFILE. What the vehicle provides in
                           CANONICAL terms -- which channels, at what rate,
                           which are structurally absent.

They are different questions and both are needed. They also overlap on
autopilot family and transport, and two files that can disagree about the
same fact will eventually disagree. `validate` CHECKS them against each other
and reports a conflict as a conflict, rather than silently preferring one.

Unifying them is a decision with consequences for the flight-log header hash
and therefore for every committed trial manifest. It is not made here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Optional

from ..aircraft.capability import negotiate
from ..aircraft.profile import ProfileError, load as load_profile
from .deployment import (DeploymentError, conflicts as deployment_conflicts,
                         load as load_deployment)

#: Modes this entry point will start. `control` and anything resembling
#: command authority are absent by construction, not by check.
RUN_MODES = ("validate", "shadow", "record", "replay")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def _adapter_for(family: str):
    """Pick the adapter. Unknown families raise rather than defaulting.

    Defaulting to ArduPilot on an unrecognised family would decode a PX4
    stream with the wrong dialect and report channels missing that were
    arriving all along -- a fault, invented by a fallback.
    """
    if family == "ardupilot":
        from ..aircraft.adapters.ardupilot import ArduPilotAdapter
        return ArduPilotAdapter()
    if family == "px4":
        from ..aircraft.adapters.px4 import PX4Adapter
        return PX4Adapter()
    if family == "synthetic":
        from ..aircraft.adapters.synthetic import SyntheticAdapter
        return SyntheticAdapter(label="edge-validate")
    raise ProfileError(
        f"no adapter for autopilot family {family!r}. Add an adapter rather "
        f"than letting the runner fall back to another platform's dialect.")


def cross_check(profile, deployment_path: Optional[str]) -> list:
    """Compare a profile against a deployment config. Report, do not resolve.

    Returns a list of conflict strings. An empty list means the two agree on
    everything they both state.

    THE COMPARISON LOGIC LIVES IN csia/deploy/deployment.py, not here. It was
    written here first, and a second copy appeared the moment schema 2 needed
    the same rules -- which is the parallel-hierarchy mistake P1 avoided,
    arriving through the back door. A config that will not parse is reported
    as a conflict rather than raised: `validate` must be able to say "these two
    files disagree" without the disagreement becoming a crash.
    """
    if not deployment_path or not os.path.exists(deployment_path):
        return []
    try:
        dep = load_deployment(deployment_path)
    except DeploymentError as exc:
        return [str(exc)]
    return deployment_conflicts(dep, profile)


def do_validate(args) -> int:
    """Answer 'can CSIA use this vehicle?' and print what it will be blind to."""
    try:
        profile = load_profile(args.profile)
    except ProfileError as exc:
        print(f"PROFILE INVALID: {exc}", file=sys.stderr)
        return 2

    adapter = _adapter_for(profile.autopilot)
    report = negotiate(adapter, profile=profile)
    conflicts = cross_check(profile, args.deployment)

    out = {
        "tool": "csia-edge validate",
        "profile_path": args.profile,
        "profile_sha256": _sha256_file(args.profile),
        "profile": profile.to_dict(),
        "adapter": {"platform": adapter.platform,
                    "version": adapter.adapter_version,
                    "contract_version": getattr(adapter.contract, "version",
                                                None)},
        "capability": report.to_dict(),
        "config_conflicts": conflicts,
        # A VALIDATE RUN IS NOT A LIVE CHECK. Nothing was connected, so every
        # declared channel is UNKNOWN rather than confirmed. Saying so here
        # stops a green validate from being read as "the vehicle is wired up".
        "liveness_checked": False,
        "note": ("Static validation from the profile and the frozen relation "
                 "graph. No vehicle was contacted, so channels the profile "
                 "declares are UNKNOWN rather than confirmed present."),
    }

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        _print_human(out)

    if conflicts:
        return 3
    # Structurally absent relations are NOT a failure -- they are the honest
    # answer for that airframe. Only an invalid profile or a config conflict
    # fails.
    return 0


def _print_human(out: dict):
    cap = out["capability"]
    prof = out["profile"]
    print(f"profile            {prof['profile_id']}  "
          f"({out['profile_sha256'][:12]})")
    print(f"autopilot          {prof['autopilot']}")
    print(f"airframe           {prof['airframe']}")
    print(f"adapter            {out['adapter']['platform']} "
          f"v{out['adapter']['version']}, contract "
          f"v{out['adapter']['contract_version']}")
    print(f"declared channels  {len(prof['declared_channels'])}")
    print(f"inapplicable       {len(prof['inapplicable_channels'])}")
    print()
    print("RELATIONS")
    for label, key in (("active           ", "active"),
                       ("inactive         ", "inactive"),
                       ("structurally out ", "structurally_absent"),
                       ("unknown          ", "unknown")):
        names = cap["summary"][key]
        print(f"  {label} {len(names):2d}  {', '.join(names) if names else '-'}")
    print()
    if cap["summary"]["structurally_absent"]:
        print("NOTE: the relations listed as structurally out CANNOT be fed by")
        print("      this airframe. That is a permanent property of the")
        print("      configuration, not a fault, and CSIA will not report")
        print("      health on their behalf.")
        print()
    for c in out["config_conflicts"]:
        print(f"CONFLICT: {c}")
    print(out["note"])


def do_run(args) -> int:
    """Hand off to the mature shadow runtime rather than duplicating it."""
    print("csia-edge run delegates to the shadow runtime.", file=sys.stderr)
    print("", file=sys.stderr)
    print("  csia-shadow --config <deployment-config> --mode SHADOW",
          file=sys.stderr)
    print("", file=sys.stderr)
    print("That runner is the one with the structural transmit-surface "
          "denial, the flight-log header and the watchdog. This entry point "
          "deliberately does not reimplement it.", file=sys.stderr)
    print("Run `csia-edge validate --profile <profile>` first.",
          file=sys.stderr)
    return 4


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="csia-edge",
        description="Profile-first entry point for plugging CSIA into a "
                    "vehicle. Read-only; starts no mode with command "
                    "authority.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate",
                       help="check a vehicle profile and report what CSIA "
                            "will and will not be able to diagnose")
    v.add_argument("--profile", required=True)
    v.add_argument("--deployment", default=None,
                   help="optional configs/vehicle/*.yaml to cross-check")
    v.add_argument("--json", action="store_true")
    v.set_defaults(fn=do_validate)

    r = sub.add_parser("run", help="(delegates to csia-shadow)")
    r.add_argument("--profile", required=True)
    r.add_argument("--mode", default="shadow", choices=RUN_MODES)
    r.set_defaults(fn=do_run)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except ProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":                              # pragma: no cover
    sys.exit(main())
