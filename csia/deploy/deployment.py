"""Deployment config: the seam between "how to connect" and "what the vehicle is".

THE SEAM, STATED PLAINLY
------------------------
This repository has two configuration files that both describe a vehicle:

  configs/vehicle/*.yaml   the DEPLOYMENT config. Link, port, baud, CSIA mode,
                           log directory, autopilot stream parameters. Its
                           SHA-256 is in every flight-log header, so it is
                           load-bearing for provenance.

  profiles/*.yaml          the VEHICLE PROFILE. What the airframe provides in
                           CANONICAL terms: which channels, at what rate, which
                           are structurally absent.

They answer different questions and both are needed. They also overlap on
autopilot family and transport, and FL-005 recorded that overlap rather than
resolving it, because unifying them changes the flight-log header hash and
therefore every committed trial manifest.

This module formalises the seam without moving it.

THE ASYMMETRY THIS MODULE MAKES VISIBLE -- AND IT IS THE POINT
---------------------------------------------------------------
A vehicle profile MAY NOT set a diagnostic parameter. `csia/aircraft/profile.py`
and `csia/aircraft/firewall.py` refuse one at any nesting depth, under any
spelling, and a fuzz suite proves it.

THE DEPLOYMENT CONFIG HAS NO SUCH FIREWALL. Two of its values are passed
straight into the frozen core, and this was MEASURED by following the call, not
assumed from the key names:

  csia.tick_hz     -> csia/deploy/cli.py builds ShadowConfig.tick_hz from it;
                      csia/deploy/shadow.py:123 passes it to
                      OnlineTrustLayer(tick_hz=...), and shadow.py:307 uses it
                      as the loop dt. The diagnostic smoothing is an EWMA over
                      TICKS (SMOOTH_ALPHA = 0.06, ~15 ticks), so the tick rate
                      sets the smoothing TIME CONSTANT. 25 Hz and 10 Hz are not
                      the same detector.
  csia.field_mode  -> ShadowConfig.field_mode -> OnlineTrustLayer(field_mode=)
                      the real-world tolerance package.

A THIRD KEY LOOKS LIKE IT REACHES THE SCIENCE AND DOES NOT, and getting this
wrong in the first draft of this module is why it is spelled out. `csia.profile`
(`FIELD_DERIVED_NOISE`) is used at exactly ONE place in the shadow runtime --
shadow.py:285, the flight-log header. It selects nothing. It is a PROVENANCE
LABEL, and it must be, because a shadow deployment reads real telemetry and has
no simulated noise to parameterise. Note also that the string names a profile in
`csia/simulation/profiles.py` (IDEAL_SIM / REALISTIC_SIM / FIELD_DERIVED_NOISE),
NOT one in `csia/profiles.py` (sow001_quad, interceptor_seeker); those are two
different registries with one word, and looking it up in the wrong one raises.

So the honest summary is: the deployment config sets two values that reach the
frozen core and one that is recorded beside the evidence. That is a narrower
statement than "the deployment config is unfirewalled", and it is the one the
code supports.

WHAT KEEPS THE TWO REAL ONES FROM BEING A HOLE
-----------------------------------------------
Nothing structural, today. `tick_hz` and `field_mode` are plain values in a YAML
file with no allowlist and no reason field. What exists is provenance: the
config's SHA-256 is in the flight-log header, so which values were used is
recorded rather than reconstructed. That is enough for an audit AFTER a run and
is not enough to stop a run being configured wrong.

Schema 2 closes that gap, opt-in: every key reaching the core must be named in a
`science_surface:` block with a reason, the same discipline `channel_overrides`
already applies. The surface is DERIVED -- `core_reachable_keys()` reads the
ShadowConfig construction in cli.py and the OnlineTrustLayer call in shadow.py
and reports which config keys connect the two. Wire a new value into the core
and the required declaration appears by itself.

WHY SCHEMA 1 IS IMPLICIT AND WILL STAY THAT WAY
------------------------------------------------
`csia/deploy/flight_log.py` hashes the PARSED CONFIG DICT:

    sha256(json.dumps(vehicle_config, sort_keys=True))[:16]

Adding a `schema:` key to an existing deployment config would therefore change
that file's hash and orphan every flight log and trial manifest that cites it.
So a file with NO `schema` key IS schema 1, its dict is untouched, and
`tests/test_deployment_schema.py` pins the committed example's hash to the value
it had before this module existed: da6321053178df5b. Schema 2 is opt-in, in new
files. There is no migration that rewrites a schema-1 file in place, and
`MIGRATION_POLICY` says so in a string the test asserts against.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional

import yaml

from ..aircraft import firewall

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SCHEMA_1 = "csia.deployment/1"
SCHEMA_2 = "csia.deployment/2"
KNOWN_SCHEMAS = (SCHEMA_1, SCHEMA_2)

#: Modes a deployment may declare. Nothing here carries command authority, and
#: the absence is by construction rather than by check.
DEPLOYMENT_MODES = ("SHADOW", "ADVISORY")

#: The frozen-core entry point the shadow runtime constructs. Anything the
#: deployment config can route into THIS call reaches the science.
CORE_ENTRY_POINT = "OnlineTrustLayer"

MIGRATION_POLICY = """\
A schema-1 deployment config is NEVER rewritten in place.

Its SHA-256 is in the header of every flight log it produced, so editing it --
even to add a `schema:` key that changes nothing else -- breaks the link
between a log and the configuration that produced it. Schema 1 files stay
exactly as they are, and are read as schema 1 by the ABSENCE of a `schema` key.

To adopt schema 2, write a NEW file. The new file has a new hash, which is
correct: it is a different configuration. Logs produced under the old file
still resolve against the old file, and nothing has to be re-derived.

There is deliberately no --upgrade flag. A tool that rewrites schema-1 files
would be used once, in a hurry, on the file whose hash is cited by the trial
manifests.
"""


class DeploymentError(ValueError):
    """A deployment config that cannot be trusted to mean what it says."""


# ---------------------------------------------------------------------------
# WHAT REACHES THE CORE, DERIVED BY FOLLOWING THE CALL
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def core_reachable_fields(root: Optional[str] = None) -> frozenset:
    """ShadowConfig fields passed into the frozen core's entry point.

    Read out of csia/deploy/shadow.py rather than listed here. A hand list
    would say what was true when someone last looked; FL-001 is this program's
    standing evidence about hand lists.
    """
    root = root or ROOT
    path = os.path.join(root, "csia", "deploy", "shadow.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    fields = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == CORE_ENTRY_POINT):
            continue
        for kw in node.keywords:
            for sub in ast.walk(kw.value):
                # cfg.tick_hz / self.cfg.tick_hz -> "tick_hz"
                if (isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Name)
                        and sub.value.id == "cfg"):
                    fields.add(sub.attr)
                elif (isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Attribute)
                        and sub.value.attr == "cfg"):
                    fields.add(sub.attr)
    return frozenset(fields)


@functools.lru_cache(maxsize=4)
def config_key_to_field(root: Optional[str] = None) -> dict:
    """deployment `csia.<key>` -> the ShadowConfig field it becomes.

    Read out of csia/deploy/cli.py's ShadowConfig(...) construction, so a new
    wiring line is picked up without anyone remembering to edit this module.
    """
    root = root or ROOT
    path = os.path.join(root, "csia", "deploy", "cli.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    mapping = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ShadowConfig"):
            continue
        for kw in node.keywords:
            for sub in ast.walk(kw.value):
                # csia_cfg.get("tick_hz", 25.0)
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "get"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "csia_cfg"
                        and sub.args
                        and isinstance(sub.args[0], ast.Constant)
                        and isinstance(sub.args[0].value, str)):
                    mapping[sub.args[0].value] = kw.arg
    return mapping


def core_reachable_keys(root: Optional[str] = None) -> dict:
    """deployment path -> the frozen-core parameter it feeds.

    The composition of the two scans above: a `csia.<key>` that becomes a
    ShadowConfig field that is handed to OnlineTrustLayer.
    """
    fields = core_reachable_fields(root)
    return {f"csia.{key}": field_name
            for key, field_name in config_key_to_field(root).items()
            if field_name in fields}


@dataclass
class Deployment:
    schema: str
    path: Optional[str]
    raw: dict = field(default_factory=dict)
    profile_ref: Optional[str] = None

    @property
    def autopilot_stack(self) -> Optional[str]:
        return ((self.raw.get("autopilot") or {}).get("stack")
                or "").lower() or None

    @property
    def mode(self) -> Optional[str]:
        return ((self.raw.get("csia") or {}).get("mode") or "").upper() or None

    @property
    def tick_hz(self):
        return (self.raw.get("csia") or {}).get("tick_hz")

    @property
    def noise_profile_label(self) -> Optional[str]:
        """The flight-log header's `profile` field.

        Named `_label` because that is what it is: shadow.py uses it at one
        place, the header, and it selects nothing. See the module docstring.
        """
        return (self.raw.get("csia") or {}).get("profile")

    @property
    def link(self) -> dict:
        return self.raw.get("link") or {}

    @property
    def config_hash(self) -> str:
        """The flight-log header's `vehicle_config_hash`, recomputed here.

        DELIBERATELY DUPLICATED from csia/deploy/flight_log.py rather than
        imported: a test asserts the two agree, so a change to either is
        caught, where a shared helper would let both drift together silently.
        """
        blob = json.dumps(self.raw, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "path": self.path,
            "profile_ref": self.profile_ref,
            "autopilot_stack": self.autopilot_stack,
            "mode": self.mode,
            "config_hash": self.config_hash,
            "science_surface": science_surface(self),
        }


def science_surface(dep: Deployment, root: Optional[str] = None) -> list:
    """Every deployment key that touches the frozen core, and how.

    TWO SOURCES, because neither finds the other's cases:

      reaches_core     the key is routed into OnlineTrustLayer. Derived by
                       following cli.py -> ShadowConfig -> shadow.py. This is
                       the one that matters and the one a name-based check
                       misses: `field_mode` shadows no frozen constant and
                       goes straight into the core.
      shadows_constant the key's NAME collides with a frozen-core parameter,
                       via the same generated namespace the vehicle-profile
                       firewall uses. Catches a key that does not reach the
                       core today but would be read as setting one.

    REPORTS; does not reject. The deployment config legitimately selects a tick
    rate, and refusing it would break `csia-shadow` on the only committed
    configuration in the repository. What must not happen is the selection
    being invisible.
    """
    reaches = core_reachable_keys(root)
    found = {}
    for path, key in _walk(dep.raw):
        entry = None
        if path in reaches:
            entry = {"path": path, "key": key, "reaches_core": reaches[path],
                     "shadows": None, "value": _at(dep.raw, path)}
        hit = firewall.collision(key)
        if hit:
            entry = entry or {"path": path, "key": key, "reaches_core": None,
                              "value": _at(dep.raw, path)}
            entry["shadows"] = hit
        if entry:
            found[path] = entry
    return [found[k] for k in sorted(found)]


def _walk(node, prefix=""):
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{prefix}.{k}".lstrip(".")
            yield here, k
            yield from _walk(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{prefix}[{i}]")


def _at(root_obj, path):
    node = root_obj
    for part in path.split("."):
        if "[" in part:
            name, _, rest = part.partition("[")
            node = node[name][int(rest.rstrip("]"))]
        else:
            node = node[part]
    return node


def validate(doc: dict, source_path: Optional[str] = None) -> Deployment:
    """Parse a deployment config under whichever schema it declares."""
    where = source_path or "<dict>"
    if not isinstance(doc, dict):
        raise DeploymentError(f"{where}: deployment config is not a mapping")

    declared = doc.get("schema")
    if declared is None:
        schema = SCHEMA_1
    elif declared in KNOWN_SCHEMAS:
        schema = declared
    else:
        raise DeploymentError(
            f"{where}: unknown schema {declared!r}; expected one of "
            f"{list(KNOWN_SCHEMAS)}. A config claiming a schema this build "
            f"does not implement must not be read under a guessed one.")

    dep = Deployment(schema=schema, path=source_path, raw=doc)

    mode = dep.mode
    if mode and mode not in DEPLOYMENT_MODES:
        raise DeploymentError(
            f"{where}: csia.mode {mode!r} is not one of "
            f"{list(DEPLOYMENT_MODES)}. No deployment mode carries command "
            f"authority, and an unrecognised one must not be silently "
            f"replaced by a mode nobody wrote.")

    label = dep.noise_profile_label
    if label is not None:
        # RESOLVED HERE EVEN THOUGH IT SELECTS NOTHING. The string lands in the
        # flight-log header, so a typo puts a profile name in the permanent
        # evidence record that names nothing -- and the reader of that record
        # cannot tell a typo from a profile that was later renamed.
        from ..simulation.profiles import PROFILES as NOISE_PROFILES
        if str(label).strip().upper() not in NOISE_PROFILES:
            raise DeploymentError(
                f"{where}: csia.profile {label!r} is not a committed noise "
                f"profile ({sorted(NOISE_PROFILES)}). It selects nothing at "
                f"runtime -- it is the provenance label in the flight-log "
                f"header -- which is exactly why it must name something real.")

    if schema == SCHEMA_1:
        return dep

    # ---------------------------------------------------------------- v2
    ref = doc.get("vehicle_profile")
    if not isinstance(ref, str) or not ref:
        raise DeploymentError(
            f"{where}: {SCHEMA_2} requires `vehicle_profile: <path>`. That "
            f"reference is the point of the schema bump -- it is what lets a "
            f"deployment be cross-checked against what the airframe actually "
            f"provides, instead of the two files drifting apart.")
    dep.profile_ref = ref

    declared_surface = doc.get("science_surface") or []
    if not isinstance(declared_surface, list):
        raise DeploymentError(
            f"{where}: science_surface must be a list of {{key, reason}} "
            f"entries")
    for entry in declared_surface:
        if not (entry or {}).get("reason"):
            raise DeploymentError(
                f"{where}: science_surface entry {entry!r} has no reason. An "
                f"undeclared reason is how a stub gets quietly re-admitted -- "
                f"the same rule channel_overrides already applies.")
    declared_keys = {(e or {}).get("key") for e in declared_surface}

    surface = science_surface(dep)
    reaching = {e["path"] for e in surface if e["reaches_core"]}
    undeclared = sorted(reaching - declared_keys)
    if undeclared:
        detail = ", ".join(f"{e['path']} -> OnlineTrustLayer({e['reaches_core']})"
                           for e in surface if e["path"] in undeclared)
        raise DeploymentError(
            f"{where}: these keys are routed into the frozen core and are not "
            f"declared in science_surface: {undeclared}. Under {SCHEMA_2} "
            f"every value that touches the diagnostic mathematics is named "
            f"with a reason, so a reviewer reads one block instead of the "
            f"whole file.\nThey reach: {detail}")

    stale = sorted(k for k in declared_keys if k not in reaching)
    if stale:
        raise DeploymentError(
            f"{where}: science_surface declares {stale}, which this config "
            f"does not route into the core. A declaration for a key that is "
            f"not there is a reason nobody can check.")
    return dep


def load(path: str) -> Deployment:
    if not os.path.exists(path):
        raise DeploymentError(f"{path}: no such deployment config")
    with open(path, encoding="utf-8") as fh:
        return validate(yaml.safe_load(fh), source_path=path)


def conflicts(dep: Deployment, profile) -> list:
    """Every disagreement between a deployment and a vehicle profile.

    REPORTS, never resolves. Preferring one silently would decode a PX4 stream
    with the ArduPilot dialect and report channels missing that were arriving
    all along -- a fault invented by a fallback.
    """
    out = []
    if dep.autopilot_stack and dep.autopilot_stack != profile.autopilot:
        out.append(
            f"autopilot: profile says {profile.autopilot!r}, deployment "
            f"config says {dep.autopilot_stack!r}. These select different "
            f"message dialects; running with the wrong one reports channels "
            f"missing that were arriving.")

    prof_conn = (profile.transport.get("mavlink") or {}).get("port")
    dep_conn = dep.link.get("connection") or dep.link.get("device")
    if dep_conn and prof_conn and dep_conn != prof_conn:
        out.append(
            f"transport: profile says {prof_conn!r}, deployment config says "
            f"{dep_conn!r}. Not necessarily an error -- the deployment config "
            f"is authoritative for the link -- but the profile should not "
            f"state a different one.")

    if dep.mode and dep.mode not in DEPLOYMENT_MODES:
        out.append(
            f"mode: deployment config declares {dep.mode!r}. csia-edge starts "
            f"no mode with command authority.")

    if dep.profile_ref and profile.source_path:
        ref = os.path.normpath(dep.profile_ref)
        got = os.path.normpath(profile.source_path)
        if not got.endswith(ref):
            out.append(
                f"profile reference: deployment names {dep.profile_ref!r}, "
                f"but the profile being validated is {profile.source_path!r}. "
                f"Validating one profile against another's deployment proves "
                f"nothing about either.")
    return out
