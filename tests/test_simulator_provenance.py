"""The flight log must record WHICH BUILD flew, not the platform's name.

`FlightLog`'s header carries `autopilot_version`, and its own test uses the
shape "4.8.0-dev@01a504b" (tests/test_flight_log.py:39). The SITL harness was
passing `args.platform` -- the literal string "ardupilot" -- so every flight
log in every campaign recorded a constant where its firmware provenance
belonged. A published campaign could not say which build produced it without
an out-of-band note, which is exactly the provenance defect a reader cannot
detect and cannot repair after the fact.
"""

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from csia.simulation.rigs import (                            # noqa: E402
    ROOTS, provenance_string, simulator_provenance)


def test_provenance_is_never_just_the_platform_name():
    for platform in ("ardupilot", "px4"):
        s = provenance_string(platform)
        assert s != platform, (
            f"{platform}: provenance is the platform name again")
        assert s, "provenance string is empty"


def test_a_missing_checkout_degrades_to_not_recorded_rather_than_guessing():
    saved = ROOTS.get("ardupilot")
    try:
        ROOTS["ardupilot"] = "/nonexistent/path/for/this/test"
        p = simulator_provenance("ardupilot")
        assert p["sha"] == "NOT RECORDED"
        assert p["firmware"] == "NOT RECORDED"
        assert provenance_string("ardupilot") == "NOT RECORDED"
    finally:
        ROOTS["ardupilot"] = saved


def test_recorded_sha_matches_the_checkout_that_was_built():
    """The SHA must come from the repository, not from a hand-kept document."""
    for platform in ("ardupilot", "px4"):
        root = ROOTS.get(platform)
        if not root or not os.path.isdir(os.path.join(root, ".git")):
            continue                       # checkout absent in this container
        p = simulator_provenance(platform)
        assert re.fullmatch(r"[0-9a-f]{40}", p["sha"]), p["sha"]
        assert p["sha"].startswith(p["sha_short"])
        assert p["sha_short"] in provenance_string(platform)


def test_px4_does_not_render_its_sha_twice():
    """`describe --always` returns the SHA when no tag is reachable.

    Without a guard that produced "PX4-Autopilot 547e2ca@547e2ca".
    """
    root = ROOTS.get("px4")
    if not root or not os.path.isdir(os.path.join(root, ".git")):
        return
    s = provenance_string("px4")
    short = simulator_provenance("px4")["sha_short"]
    assert s.count(short) == 1, s


def test_the_harness_passes_provenance_not_the_platform():
    """Guard the call site itself, so the fix cannot silently regress."""
    src = open(os.path.join(ROOT, "tools", "deploy", "shadow_sitl_check.py"),
               encoding="utf-8").read()
    assert "autopilot_version=provenance_string(args.platform)" in src
    assert "autopilot_version=args.platform" not in src
