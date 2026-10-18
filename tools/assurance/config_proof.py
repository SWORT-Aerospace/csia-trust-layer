"""A17: six ways to sneak a value into a configuration, tried against both gates.

THE SIX FORMS, DECLARED BEFORE ANY RUN
---------------------------------------
Each mutates the committed reference deployment config, and each is a real way
an operator or an attacker gets a value into a running system:

    UNKNOWN_KEY          a key nobody defined
    ALIAS                a plausible other spelling of a real key
    CASE_VARIANT         the real key, shouted
    SEPARATOR_TRICK      the real key, hyphenated
    ENV_VAR              no file change at all; an environment variable
    NESTED_OVERRIDE      an `overrides:` block that re-states a real key

WHAT IS MEASURED, AND WHY IT IS TWO THINGS
-------------------------------------------
For each form and each gate:

    ACCEPTED / REFUSED   did the gate read the config at all
    REACHES_CORE         did the value change what is handed to
                         OnlineTrustLayer

They are separate because they fail differently. A gate that ACCEPTS a stray
key which reaches NOTHING has a documentation problem. A gate that ACCEPTS a
key which REACHES THE CORE has a science problem: the evidence record would
name a configuration that is not the one that ran.

TWO GATES, AND THE EXISTING ONE IS NOT BEING FAILED FOR ITS DESIGN
-------------------------------------------------------------------
    EXISTING   csia/deploy/deployment.py validate() -- SEMANTIC validation.
               It checks that what it recognises MEANS something. It was never
               written to be exact-key, and reporting what it does is a
               finding about coverage, not an accusation of a bug.

    STRICT     csia_assurance/config_gate.py -- EXACT-KEY. Written for this,
               sits outside the frozen core, and is NOT wired into the loader.

NOTHING IS MODIFIED AUTOMATICALLY. The programme says so directly, and the
adoption decision -- whether the strict gate runs in front of `validate()` in
production -- is left to a human with this table in front of them.

    python tools/assurance/config_proof.py --out <json>
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

REFERENCE = os.path.join(ROOT, "configs", "vehicle",
                         "reference_quad_ardupilot_v2.yaml")

#: The key every mutation targets. Chosen because it is the one deployment key
#: that is BOTH declared in science_surface and routed into the frozen core, so
#: a successful smuggle would change the detector itself.
TARGET_PATH = ("csia", "tick_hz")
TARGET_VALUE = 50.0


def _load():
    with open(REFERENCE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _mutations(base: dict) -> list:
    def m(label, why, fn, env=None):
        doc = copy.deepcopy(base)
        fn(doc)
        return {"form": label, "why_an_operator_would_do_this": why,
                "doc": doc, "env": env or {}}

    return [
        m("UNKNOWN_KEY",
          "a key from a newer build, a blog post, or a typo nobody noticed",
          lambda d: d["csia"].__setitem__("tick_hz_override", TARGET_VALUE)),
        m("ALIAS",
          "the same setting under the spelling another project uses",
          lambda d: d["csia"].__setitem__("tickHz", TARGET_VALUE)),
        m("CASE_VARIANT",
          "copied from documentation that shouts its key names",
          lambda d: d["csia"].__setitem__("TICK_HZ", TARGET_VALUE)),
        m("SEPARATOR_TRICK",
          "hyphen instead of underscore, which most YAML readers accept",
          lambda d: d["csia"].__setitem__("tick-hz", TARGET_VALUE)),
        m("ENV_VAR",
          "no file edit at all -- an environment variable in a unit file",
          lambda d: None,
          env={"CSIA_TICK_HZ": str(TARGET_VALUE)}),
        m("NESTED_OVERRIDE",
          "a late-binding overrides block, the shape most config systems grow",
          lambda d: d.__setitem__(
              "overrides", {"csia": {"tick_hz": TARGET_VALUE}})),
    ]


def _existing_gate(doc, env):
    """What csia/deploy/deployment.py does with it."""
    from csia.deploy import deployment as dep_mod
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        dep = dep_mod.validate(doc, source_path=REFERENCE)
        # Does the smuggled value actually reach the core?
        reaching = dep_mod.core_reachable_keys()
        core_values = {}
        for path in sorted(reaching):
            node = doc
            for part in path.split("."):
                node = (node or {}).get(part) if isinstance(node, dict) else None
            core_values[path] = node
        return {"accepted": True, "error": None,
                "core_values": core_values,
                "tick_hz_seen_by_loader": dep.tick_hz}
    except Exception as exc:                                 # noqa: BLE001
        return {"accepted": False, "error": f"{type(exc).__name__}: {exc}",
                "core_values": None, "tick_hz_seen_by_loader": None}
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _strict_gate(doc, env):
    from csia_assurance import config_gate
    refusals = config_gate.check(doc, environ=env)
    return {"accepted": not refusals,
            "refusals": refusals,
            "reasons": sorted({r["reason"] for r in refusals})}


def _environment_paths() -> dict:
    """Every environment variable this codebase actually reads, found by
    scanning rather than asserted.

    The ENV_VAR row above proves that `CSIA_TICK_HZ` changes nothing. That is
    not the same as "there is no environment path at all", and claiming the
    stronger thing from the weaker evidence is exactly the move this
    programme exists to refuse. So the scan is here, and what it finds is
    reported whether or not it is convenient.
    """
    import ast

    found = {}
    for sub in ("csia",):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, sub)):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    try:
                        tree = ast.parse(fh.read(), filename=path)
                    except SyntaxError:                      # pragma: no cover
                        continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    fn = node.func
                    is_env = (
                        (isinstance(fn, ast.Attribute) and fn.attr == "get"
                         and isinstance(fn.value, ast.Attribute)
                         and fn.value.attr == "environ")
                        or (isinstance(fn, ast.Attribute)
                            and fn.attr == "getenv"))
                    if not is_env or not node.args:
                        continue
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(
                            arg.value, str):
                        found.setdefault(arg.value, []).append(
                            f"{os.path.relpath(path, ROOT)}:{node.lineno}")

    from csia.deploy import deployment as dep_mod
    reaching = set(dep_mod.core_reachable_keys())

    # Which files construct the frozen core's entry point at all. An env read
    # in a file that never calls OnlineTrustLayer cannot reach it from there.
    core_call_files = set()
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "csia")):
        if "__pycache__" in dirpath:
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if dep_mod.CORE_ENTRY_POINT + "(" in src:
                core_call_files.add(os.path.relpath(path, ROOT))

    env_files = {site.rsplit(":", 1)[0]
                 for sites in found.values() for site in sites}
    return {
        "variables_read_by_csia": {k: sorted(v) for k, v in
                                   sorted(found.items())},
        "files_constructing_the_core_entry_point": sorted(core_call_files),
        "files_reading_an_environment_variable": sorted(env_files),
        "files_doing_both": sorted(env_files & core_call_files),
        "check_performed": (
            "NAME-LEVEL AND READ-SITE, NOT DATAFLOW. Two things are checked: "
            "that no environment variable name is a core-reachable "
            "deployment key, and which files both read the environment and "
            "construct the core entry point. A file in neither set cannot "
            "route the environment into the core. This is weaker than a "
            "dataflow proof and is labelled as such rather than reported as "
            "one."),
        "core_reachable_deployment_keys": sorted(reaching),
        "note": (
            "CSIA_MODE is read, and it is reported here rather than omitted "
            "because the ENV_VAR row only proves that CSIA_TICK_HZ is inert. "
            "CSIA_MODE selects a deployment MODE, no mode carries command "
            "authority, an unrecognised value RAISES rather than falling "
            "back, and the value is not among the keys routed into "
            "OnlineTrustLayer. It is therefore an environment path that does "
            "not reach the science -- which is a different statement from "
            "'there is no environment path', and the weaker one is the true "
            "one."),
    }


def run() -> dict:
    base = _load()
    baseline_tick = (base.get("csia") or {}).get("tick_hz")

    rows = []
    for mut in _mutations(base):
        existing = _existing_gate(mut["doc"], mut["env"])
        strict = _strict_gate(mut["doc"], mut["env"])

        reached = (existing["accepted"]
                   and existing["tick_hz_seen_by_loader"] not in
                   (None, baseline_tick))
        rows.append({
            "form": mut["form"],
            "why_an_operator_would_do_this":
                mut["why_an_operator_would_do_this"],
            "existing_gate": {
                "accepted": existing["accepted"],
                "error": existing["error"],
                "tick_hz_the_core_would_receive":
                    existing["tick_hz_seen_by_loader"],
            },
            "strict_gate": {
                "accepted": strict["accepted"],
                "reasons": strict["reasons"],
            },
            "value_reached_the_frozen_core": reached,
            "assessment": (
                "SMUGGLED_INTO_CORE" if reached
                else "REFUSED_BY_BOTH" if not existing["accepted"]
                and not strict["accepted"]
                else "ACCEPTED_BUT_INERT" if existing["accepted"]
                and not strict["accepted"]
                else "ACCEPTED_BY_BOTH"),
        })

    # The control: the UNMODIFIED reference config must pass BOTH gates. A
    # strict gate that rejects the committed configuration is not strict, it
    # is broken, and without this row the six refusals above prove nothing.
    control_existing = _existing_gate(copy.deepcopy(base), {})
    control_strict = _strict_gate(copy.deepcopy(base), {})
    control_ok = control_existing["accepted"] and control_strict["accepted"]

    smuggled = [r for r in rows if r["value_reached_the_frozen_core"]]
    strict_missed = [r for r in rows if r["strict_gate"]["accepted"]]
    existing_missed = [r for r in rows if r["existing_gate"]["accepted"]]

    return {
        "schema": "csia.assurance.config_proof/1",
        "reference_config": os.path.relpath(REFERENCE, ROOT),
        "baseline_tick_hz": baseline_tick,
        "target": {"path": ".".join(TARGET_PATH), "value": TARGET_VALUE,
                   "why_this_key": ("the one deployment key that is both "
                                    "declared in science_surface and routed "
                                    "into OnlineTrustLayer, so a successful "
                                    "smuggle would change the detector")},
        "gates": {
            "EXISTING": ("csia/deploy/deployment.py validate() -- SEMANTIC. "
                         "Not exact-key by design; this table reports its "
                         "coverage, it does not accuse it of a bug."),
            "STRICT": ("csia_assurance/config_gate.py -- EXACT-KEY. Outside "
                       "the frozen core and NOT wired into the loader."),
        },
        "control": {
            "unmodified_reference_passes_existing": control_existing["accepted"],
            "unmodified_reference_passes_strict": control_strict["accepted"],
            "strict_refusals_on_the_control": control_strict["refusals"],
            "control_holds": control_ok,
            "why": ("A gate that rejects the committed configuration would "
                    "refuse everything, and six refusals would mean nothing."),
        },
        "forms": rows,
        "environment_paths": _environment_paths(),
        "totals": {
            "forms_tried": len(rows),
            "reached_the_frozen_core": len(smuggled),
            "accepted_by_the_existing_gate": len(existing_missed),
            "accepted_by_the_strict_gate": len(strict_missed),
        },
        "verdict": ("NOTHING_SMUGGLED_INTO_THE_CORE" if not smuggled
                    else "VALUE_REACHED_THE_CORE"),
        "strict_gate_verdict": ("ALL_SIX_REFUSED" if not strict_missed
                                else "STRICT_GATE_ACCEPTED_A_FORM"),
        "nothing_was_modified_automatically": (
            "The strict gate is written and evidenced here. Wiring it in "
            "front of csia/deploy/deployment.py validate() is a deliberate "
            "later decision by a human reading this table, not a side effect "
            "of running this tool."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = run()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"\n{doc['verdict']}  strict: {doc['strict_gate_verdict']}  "
          f"{doc['totals']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
