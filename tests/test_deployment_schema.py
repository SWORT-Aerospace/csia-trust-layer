"""The deployment/profile seam: two files, one vehicle, and what may drift.

THE THREE PROPERTIES THAT MATTER, IN ORDER OF WHAT THEY COST IF THEY BREAK
--------------------------------------------------------------------------
  1. A SCHEMA-1 CONFIG'S HASH NEVER MOVES. The SHA-256 of a deployment config
     is in the header of every flight log it produced. If introducing schema 2
     changed a schema-1 file's hash -- even by adding a key that changes
     nothing -- every committed trial manifest citing it would be orphaned and
     the loss would be silent. Pinned to a literal below.

  2. WHAT REACHES THE FROZEN CORE IS DERIVED, NOT LISTED. The set is read by
     following cli.py -> ShadowConfig -> shadow.py's OnlineTrustLayer(...)
     call. A hand list would say what was true when someone last looked;
     FL-001 is this program's standing evidence about hand lists.

  3. A DISAGREEMENT BETWEEN THE TWO FILES IS REPORTED, NEVER RESOLVED.
     Preferring one silently decodes a PX4 stream with the ArduPilot dialect
     and reports channels missing that were arriving all along.
"""

from __future__ import annotations

import ast
import os

import pytest
import yaml

from csia.aircraft.profile import load as load_profile
from csia.deploy import deployment as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIGS = os.path.join(ROOT, "configs", "vehicle")
SCHEMA_1_EXAMPLE = os.path.join(CONFIGS, "example_quad.yaml")
SCHEMA_2_EXAMPLE = os.path.join(CONFIGS, "reference_quad_ardupilot_v2.yaml")
AP_PROFILE = os.path.join(ROOT, "profiles", "reference_quad_ardupilot.yaml")
PX4_PROFILE = os.path.join(ROOT, "profiles", "reference_quad_px4.yaml")

#: Measured at commit 3533698, BEFORE csia/deploy/deployment.py existed.
#: If this ever needs updating, the flight logs that cite it are already wrong.
SCHEMA_1_EXAMPLE_HASH = "da6321053178df5b"


# ================================================= 1. hashes do not move

def test_the_committed_schema_1_config_hash_is_unchanged():
    dep = D.load(SCHEMA_1_EXAMPLE)
    assert dep.schema == D.SCHEMA_1, (
        "a config with no `schema:` key IS schema 1; inferring anything else "
        "would mean the file's meaning changed without the file changing")
    assert dep.config_hash == SCHEMA_1_EXAMPLE_HASH, (
        f"example_quad.yaml now hashes to {dep.config_hash}, not "
        f"{SCHEMA_1_EXAMPLE_HASH}. Every flight-log header and trial manifest "
        f"citing the old hash is now unresolvable. Schema-1 configs are not "
        f"edited -- see deployment.MIGRATION_POLICY.")


def test_the_hash_matches_what_the_flight_log_header_actually_writes():
    """Two implementations of one fact, deliberately, and pinned together.

    deployment.config_hash duplicates flight_log's computation rather than
    importing it, so a change to either is caught. That is only true if
    something compares them.
    """
    from csia.deploy.flight_log import make_header

    from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
    cfg = yaml.safe_load(open(SCHEMA_1_EXAMPLE, encoding="utf-8"))
    header = make_header(
        adapter=ArduPilotAdapter(), mode="SHADOW",
        autopilot_version="test", command_authority={},
        sensor_availability={}, profile="FIELD_DERIVED_NOISE",
        vehicle_config=cfg)
    assert header.vehicle_config_hash == D.load(SCHEMA_1_EXAMPLE).config_hash


def test_no_schema_1_config_in_the_repository_declares_a_schema():
    """The absence of the key IS the schema. Adding one is the forbidden edit."""
    import glob
    for path in sorted(glob.glob(os.path.join(CONFIGS, "*.yaml"))):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        declared = doc.get("schema")
        assert declared in (None, D.SCHEMA_2), (
            f"{os.path.basename(path)} declares schema {declared!r}. A "
            f"schema-1 file must carry no key at all, and schema 2 is the "
            f"only other implemented value.")


def test_there_is_no_in_place_upgrade_path():
    """A migration tool that rewrites schema-1 files would be used once, in a
    hurry, on the file whose hash the trial manifests cite."""
    assert "NEVER rewritten in place" in D.MIGRATION_POLICY
    assert "no --upgrade flag" in D.MIGRATION_POLICY
    assert not hasattr(D, "upgrade"), \
        "an upgrade() function is the thing MIGRATION_POLICY forbids"


# ============================================ 2. the surface is derived

def test_what_reaches_the_core_is_read_out_of_the_source():
    reaching = D.core_reachable_keys()
    assert reaching == {"csia.tick_hz": "tick_hz",
                        "csia.field_mode": "field_mode"}, (
        f"the derived core surface is {reaching}. If a value was genuinely "
        f"wired into or out of OnlineTrustLayer this test SHOULD fail -- "
        f"update it deliberately, after checking the new value belongs in a "
        f"deployment config at all.")


def test_the_derivation_agrees_with_the_call_it_claims_to_read():
    """A negative control for the AST scan.

    The scan is the whole basis of the schema-2 requirement, so an independent
    reading of shadow.py must reach the same answer. Done differently on
    purpose: source text, not the same walk.
    """
    path = os.path.join(ROOT, "csia", "deploy", "shadow.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "OnlineTrustLayer"]
    assert len(calls) == 1, (
        f"{len(calls)} OnlineTrustLayer constructions in shadow.py; the "
        f"derivation assumes the runtime has one entry into the frozen core")
    kwargs = {kw.arg for kw in calls[0].keywords}
    assert {"tick_hz", "field_mode"} <= kwargs


def test_a_key_that_reaches_the_core_but_shadows_no_constant_is_still_found():
    """The case a name-based firewall misses, and the reason for two sources.

    `field_mode` collides with no frozen-core constant -- the vehicle-profile
    firewall would let it through -- and it goes straight into
    OnlineTrustLayer.
    """
    from csia.aircraft import firewall
    assert firewall.collision("field_mode") is None, (
        "field_mode now shadows a core constant; this test's premise is gone "
        "and the two-source design needs a different example")
    surface = {e["path"]: e for e in D.science_surface(D.load(SCHEMA_1_EXAMPLE))}
    assert surface["csia.field_mode"]["reaches_core"] == "field_mode"
    assert surface["csia.field_mode"]["shadows"] is None


def test_a_key_that_shadows_a_constant_is_reported_even_when_both_apply():
    surface = {e["path"]: e for e in D.science_surface(D.load(SCHEMA_1_EXAMPLE))}
    assert surface["csia.tick_hz"]["shadows"] == "TICK_HZ"
    assert surface["csia.tick_hz"]["reaches_core"] == "tick_hz"


# ================================================= 3. schema 2 behaviour

def test_the_schema_2_example_loads_and_names_its_profile():
    dep = D.load(SCHEMA_2_EXAMPLE)
    assert dep.schema == D.SCHEMA_2
    assert dep.profile_ref == "profiles/reference_quad_ardupilot.yaml"
    assert os.path.exists(os.path.join(ROOT, dep.profile_ref)), \
        "a schema-2 config must reference a profile that exists"


def test_schema_2_refuses_a_config_that_reaches_the_core_undeclared(tmp_path):
    doc = yaml.safe_load(open(SCHEMA_2_EXAMPLE, encoding="utf-8"))
    doc["science_surface"] = [e for e in doc["science_surface"]
                              if e["key"] != "csia.tick_hz"]
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(D.DeploymentError, match="not declared in "
                                                "science_surface"):
        D.load(str(p))


def test_schema_2_refuses_a_declaration_with_no_reason(tmp_path):
    doc = yaml.safe_load(open(SCHEMA_2_EXAMPLE, encoding="utf-8"))
    doc["science_surface"][0].pop("reason")
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(D.DeploymentError, match="has no reason"):
        D.load(str(p))


def test_schema_2_refuses_a_declaration_for_a_key_that_is_not_set(tmp_path):
    """A reason nobody can check is worse than no reason: it reads as covered."""
    doc = yaml.safe_load(open(SCHEMA_2_EXAMPLE, encoding="utf-8"))
    doc["science_surface"].append(
        {"key": "csia.nonexistent", "reason": "plausible-sounding prose"})
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(D.DeploymentError, match="does not route into the core"):
        D.load(str(p))


def test_schema_2_requires_a_profile_reference(tmp_path):
    doc = yaml.safe_load(open(SCHEMA_2_EXAMPLE, encoding="utf-8"))
    doc.pop("vehicle_profile")
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(D.DeploymentError, match="requires `vehicle_profile"):
        D.load(str(p))


def test_an_unknown_schema_is_refused_rather_than_guessed(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump({"schema": "csia.deployment/9",
                                 "autopilot": {"stack": "ardupilot"}}),
                 encoding="utf-8")
    with pytest.raises(D.DeploymentError, match="unknown schema"):
        D.load(str(p))


# =========================================== the provenance label, honestly

def test_the_noise_profile_label_is_validated_even_though_it_selects_nothing():
    """It lands in the flight-log header. A typo there names nothing, forever.

    The first draft of deployment.py resolved this string through
    csia/profiles.py and raised on the committed config: that is the WRONG
    registry. FIELD_DERIVED_NOISE lives in csia/simulation/profiles.py. Two
    registries, one word.
    """
    from csia.simulation.profiles import PROFILES as NOISE
    from csia.profiles import PROFILES as VEHICLES
    assert "FIELD_DERIVED_NOISE" in NOISE
    assert "FIELD_DERIVED_NOISE" not in VEHICLES, (
        "the two registries have converged; the distinction this test records "
        "no longer holds and deployment.py's docstring needs correcting")


def test_a_misspelled_noise_profile_label_is_refused(tmp_path):
    doc = yaml.safe_load(open(SCHEMA_1_EXAMPLE, encoding="utf-8"))
    doc["csia"]["profile"] = "FIELD_DERIVED_NOIZE"
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(D.DeploymentError, match="not a committed noise"):
        D.load(str(p))


def test_the_label_is_not_claimed_to_reach_the_core():
    """It reaches shadow.py:285, the header, and nothing else."""
    assert "csia.profile" not in D.core_reachable_keys()
    surface = {e["path"] for e in D.science_surface(D.load(SCHEMA_1_EXAMPLE))}
    assert "csia.profile" not in surface


# ============================================ 4. conflicts are reported

def test_the_matching_profile_and_deployment_agree():
    dep = D.load(SCHEMA_2_EXAMPLE)
    assert D.conflicts(dep, load_profile(AP_PROFILE)) == []


def test_the_wrong_profile_against_a_deployment_is_two_conflicts():
    dep = D.load(SCHEMA_2_EXAMPLE)
    found = D.conflicts(dep, load_profile(PX4_PROFILE))
    assert any("autopilot" in c for c in found)
    assert any("profile reference" in c for c in found), (
        "a schema-2 deployment names its profile; validating it against a "
        "different one proves nothing about either and must say so")


def test_a_commanding_mode_is_refused_at_load(tmp_path):
    doc = yaml.safe_load(open(SCHEMA_1_EXAMPLE, encoding="utf-8"))
    doc["csia"]["mode"] = "CONTROL"
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(D.DeploymentError, match="command authority"):
        D.load(str(p))


def test_every_committed_deployment_config_loads():
    import glob
    paths = sorted(glob.glob(os.path.join(CONFIGS, "*.yaml")))
    assert paths, "configs/vehicle/ is empty"
    for path in paths:
        D.load(path)


def test_csia_edge_reports_a_parse_failure_as_a_conflict(tmp_path, capsys):
    """`validate` must be able to say 'these files disagree' without crashing."""
    from csia.deploy import edge
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump({"schema": "csia.deployment/9"}),
                 encoding="utf-8")
    code = edge.main(["validate", "--profile", AP_PROFILE,
                      "--deployment", str(p), "--json"])
    assert code == 3
    import json
    assert any("unknown schema" in c
               for c in json.loads(capsys.readouterr().out)["config_conflicts"])
