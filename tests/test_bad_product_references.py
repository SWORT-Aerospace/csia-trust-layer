"""The conformance suite must reject the seven, and only for behaviour.

The most important test in this file is the LAST one: a correct
implementation named `BAD_PRODUCT_08_actually_fine` must PASS. Without it, a
checker that greps for "BAD_" in a class name would satisfy every other test
here and detect nothing real.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_mission.bad_references import (ALL_REFERENCES,     # noqa: E402
                                         GOOD_REFERENCE)
from csia_mission.conformance import (FAIL, INCONCLUSIVE,    # noqa: E402
                                      PASS, PROBES, run, run_all)


def test_the_good_reference_passes_every_probe():
    report = run(GOOD_REFERENCE)
    assert report["conforms"], report["probes"]
    assert report["counts"][FAIL] == 0
    assert report["counts"][INCONCLUSIVE] == 0
    assert report["counts"][PASS] == len(PROBES)


@pytest.mark.parametrize("impl,must_reject", ALL_REFERENCES,
                         ids=[getattr(i, "name", "?")
                              for i, _ in ALL_REFERENCES])
def test_each_reference_is_judged_correctly(impl, must_reject):
    report = run(impl)
    assert report["rejected"] == must_reject, (
        f"{report['implementation_label']}: expected rejected="
        f"{must_reject}, got {report['rejected']}. "
        f"Failing probes: "
        f"{[p['probe'] for p in report['probes'] if p['verdict'] == FAIL]}")


@pytest.mark.parametrize("impl,_must", [(i, m) for i, m in ALL_REFERENCES
                                        if m],
                         ids=[getattr(i, "name", "?")
                              for i, m in ALL_REFERENCES if m])
def test_each_bad_reference_fails_only_its_own_probe(impl, _must):
    """A bad reference that fails several probes is testing several things at
    once, and the suite cannot then say which defect it detected."""
    report = run(impl)
    failing = [p["probe"] for p in report["probes"] if p["verdict"] == FAIL]
    assert len(failing) == 1, (
        f"{report['implementation_label']} fails {failing}. Each reference "
        f"is wrong in exactly ONE named way; more than one failing probe "
        f"means the reference or a probe is over-broad.")
    # The probe id is the reference's own number: BAD_PRODUCT_03 must fail
    # probe BAD_PRODUCT_03 and no other. Compared on the NUMBER, so the check
    # is about which defect was detected rather than about a label.
    assert failing[0] == impl.name[:len(failing[0])], (
        f"{impl.name} fails {failing[0]}, which is not its own probe. The "
        f"suite detected a different defect from the one this reference "
        f"contains.")


def test_no_probe_inspects_the_implementation_object():
    """Static check, complementing the behavioural control below.

    THE FIRST VERSION OF THIS GUARD WAS OVER-BROAD and fired on
    `probe_04`'s `isinstance(got, (tuple, list))` -- which inspects the
    RETURN VALUE to tolerate two result shapes, and is exactly the kind of
    behavioural check the suite is supposed to make.

    A guard that cannot tell "inspecting the implementation" from
    "inspecting its answer" has one cheap fix -- stop tolerating two return
    shapes -- and that fix makes the suite worse. So the check now tracks the
    probe's `impl` PARAMETER and flags only uses OF IT in an inspection
    position.
    """
    import ast
    src_path = os.path.join(ROOT, "csia_mission", "conformance.py")
    tree = ast.parse(open(src_path, encoding="utf-8").read())

    INSPECTING = {"name", "__name__", "__class__", "__module__", "__doc__",
                  "defect", "__qualname__"}
    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef)
                and node.name.startswith("probe_")):
            continue
        args = [a.arg for a in node.args.args]
        if not args:
            continue
        impl_name = args[0]

        for sub in ast.walk(node):
            # impl.<inspecting attribute>
            if (isinstance(sub, ast.Attribute)
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id == impl_name
                    and sub.attr in INSPECTING):
                offenders.append(f"{node.name} reads {impl_name}.{sub.attr}")
            # type(impl) / isinstance(impl, ...) / getattr(impl, "name")
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                if sub.func.id in ("type", "isinstance") and sub.args and \
                        isinstance(sub.args[0], ast.Name) and \
                        sub.args[0].id == impl_name:
                    offenders.append(
                        f"{node.name} calls {sub.func.id}({impl_name})")
                if (sub.func.id == "getattr" and len(sub.args) >= 2
                        and isinstance(sub.args[0], ast.Name)
                        and sub.args[0].id == impl_name
                        and isinstance(sub.args[1], ast.Constant)
                        and sub.args[1].value in INSPECTING):
                    offenders.append(
                        f"{node.name} getattr({impl_name}, "
                        f"{sub.args[1].value!r})")
    assert not offenders, (
        "a conformance probe inspects the implementation rather than its "
        "behaviour:\n  " + "\n  ".join(offenders))


def test_a_correct_implementation_named_like_a_bad_one_still_passes():
    """THE CONTROL. This is the test that makes the rest mean anything."""
    control = [i for i, _ in ALL_REFERENCES
               if getattr(i, "name", "") == "BAD_PRODUCT_08_actually_fine"]
    assert control, "the name-trap control has been removed"
    report = run(control[0])
    assert not report["rejected"], (
        "a CORRECT implementation was rejected. The suite is judging names "
        "rather than behaviour, which means every other test in this file "
        "is passing for the wrong reason.")
    assert report["conforms"]


def test_the_campaign_reports_the_control_explicitly():
    doc = run_all(ALL_REFERENCES)
    assert doc["suite_correct"], doc["misjudged"]
    assert "BAD_PRODUCT_08_actually_fine" in doc["control"]


def test_inconclusive_is_never_counted_as_pass():
    class _Empty:
        """Exposes none of the five methods."""

    report = run(_Empty())
    assert report["counts"][INCONCLUSIVE] == len(PROBES)
    assert report["counts"][PASS] == 0
    assert not report["conforms"], (
        "an implementation that could not be judged on a single probe was "
        "reported as conforming; a skipped check reading as green is a "
        "failure mode this repository has already hit")
    assert not report["rejected"], (
        "and it must not be reported as REJECTED either -- it was not "
        "judged, which is a third answer")
