"""The firewall between a vehicle profile and the frozen science, fuzzed.

WHY THIS FILE IS SEPARATE FROM `test_vehicle_profile.py`
--------------------------------------------------------
That file checks the hand-written blacklist does what it says. This one checks
the thing the blacklist cannot: that a parameter name nobody wrote down is
still refused, and that refusal survives the spellings a person would reach for
without thinking of themselves as evading anything.

The generated namespace is derived from the frozen core by
`csia/aircraft/firewall.py`. Every test below drives it from the SOURCE rather
than from a fixture, so a constant added to the core tomorrow is covered
tonight -- which is precisely what FL-001 proves a hand list does not do.

WHAT A PASS HERE DOES AND DOES NOT MEAN
---------------------------------------
It means: no key spelling reaching `validate()` can name a frozen-core tuning
parameter. It does NOT mean the core is un-tunable -- editing the core's own
source still changes the core, and that is what the freeze tags and
`test_vehicle_profile_no_core_change.py` are for. The firewall closes the
CONFIGURATION route only, and that is the route the pluggable architecture
opens.
"""

from __future__ import annotations

import itertools
import os
import re

import pytest

from csia.aircraft import firewall
from csia.aircraft.profile import ProfileError, validate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _base():
    """A profile that is valid, so any failure is the injected key's."""
    return {
        "vehicle_profile": {"id": "fuzz"},
        "autopilot": {"family": "ardupilot"},
        "streams": {"gnss.position": {"nominal_rate_hz": 5}},
    }


# ============================================================ the namespace

def test_the_protected_namespace_is_derived_and_not_empty():
    names = firewall.protected_names()
    assert len(names) >= 40, (
        f"only {len(names)} protected names derived from the frozen core; "
        f"the AST scan has probably stopped matching and is now protecting "
        f"nothing while appearing to work")
    # The five the paper's numbers actually depend on.
    for required in ("EPS", "SMOOTH_ALPHA", "EVIDENCE_MULT", "PRIOR_NOMINAL",
                     "nav_caution"):
        assert required in names, f"{required} is not protected"


def test_the_firewalls_frozen_path_list_matches_the_programs():
    """Two copies of the same list is one copy too many, so pin them.

    EVIDENCE_EXTENSION.yaml's `forbidden_paths` is what the append-only guard
    enforces; firewall.FROZEN_PATHS is what the namespace is generated from.
    If they drift, a file could be frozen against edits while its constants
    were settable from a profile, or the reverse.
    """
    import yaml
    with open(os.path.join(ROOT, "research", "physical_validation",
                           "EVIDENCE_EXTENSION.yaml"), encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    declared = doc["forbidden_paths"]
    paths = declared["paths"] if isinstance(declared, dict) else declared
    assert sorted(paths) == sorted(firewall.FROZEN_PATHS), (
        f"EVIDENCE_EXTENSION.yaml forbidden_paths {sorted(paths)} != "
        f"firewall.FROZEN_PATHS {sorted(firewall.FROZEN_PATHS)}")


def test_every_protected_name_is_rejected_verbatim():
    """The floor. Before any fuzzing: the exact source spelling is refused."""
    survivors = []
    for name in sorted(firewall.protected_names()):
        doc = _base()
        doc["experiment"] = {name: 0.5}
        try:
            validate(doc)
        except ProfileError:
            continue
        survivors.append(name)
    assert not survivors, (
        f"these frozen-core parameters are settable from a profile in their "
        f"own source spelling: {survivors}")


# ================================================================== fuzzing
#
# Six transforms, each one something a person would write while believing they
# were writing the same word.

def _spelling_variants(name: str):
    lower = name.lower()
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", lower) if p]
    camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
    yield "case", name.upper() if name.islower() else name.lower()
    yield "camel", camel
    yield "pascal", camel[:1].upper() + camel[1:]
    yield "hyphen", "-".join(parts)
    yield "space", " ".join(parts)
    yield "plural", lower + ("" if lower.endswith("s") else "s")


@pytest.mark.parametrize("transform", [
    "case", "camel", "pascal", "hyphen", "space", "plural"])
def test_a_respelled_protected_name_is_still_rejected(transform):
    """`navCaution` is `nav_caution` to every reader except a string compare."""
    survivors = []
    for name in sorted(firewall.protected_names()):
        variant = dict(_spelling_variants(name))[transform]
        if variant == name:
            continue
        doc = _base()
        doc["experiment"] = {variant: 0.5}
        try:
            validate(doc)
        except ProfileError:
            continue
        survivors.append(f"{name} -> {variant}")
    assert not survivors, (
        f"{transform} respellings slipped past the firewall: {survivors}")


@pytest.mark.parametrize("prefix", sorted(firewall.STRIPPABLE_PREFIXES))
def test_a_framed_protected_name_is_still_rejected(prefix):
    """`CSIA_NAV_CAUTION`, `override_rho_max`, `tuning_eps`.

    Wrapping a parameter in a word that describes what you are doing to it
    does not make it a different parameter.
    """
    survivors = []
    for name in sorted(firewall.protected_names()):
        for variant in (f"{prefix}_{name.lower()}", f"{prefix}_{name}",
                        f"{prefix.upper()}_{name.upper()}"):
            doc = _base()
            doc["experiment"] = {variant: 0.5}
            try:
                validate(doc)
            except ProfileError:
                continue
            survivors.append(variant)
    assert not survivors, (
        f"prefixed protected names slipped past the firewall: {survivors}")


@pytest.mark.parametrize("depth", [1, 2, 5, 12])
def test_nesting_does_not_hide_a_protected_name(depth):
    """A key twelve levels down is still a key. Lists count as levels too."""
    for name in ("nav_caution", "SMOOTH_ALPHA", "rho_max"):
        node = {name: 0.5}
        for i in range(depth):
            node = {f"level{i}": [node] if i % 2 else node}
        doc = _base()
        doc["experiment"] = node
        with pytest.raises(ProfileError, match="may not set diagnostic"):
            validate(doc)


@pytest.mark.parametrize("template", [
    "${%s}", "$%s", "%%%s%%", "env:%s", "port-${%s}-suffix"])
def test_an_environment_reference_to_a_protected_name_is_rejected(template):
    """The route a key-only check cannot see.

    Nothing in the frozen core reads the environment today -- the test below
    keeps it that way -- so this is defence in depth, closing the door before
    anyone opens it rather than after.
    """
    for name in ("CSIA_NAV_CAUTION", "SMOOTH_ALPHA", "rho_max"):
        doc = _base()
        doc["transport"] = {"mavlink": {"port": template % name}}
        with pytest.raises(ProfileError, match="may not set diagnostic"):
            validate(doc)


def test_the_frozen_core_reads_no_environment_variable():
    """The premise the env check is defence in depth FOR.

    If a frozen-core module ever reads os.environ, the profile firewall stops
    being the only configuration route and this whole file guards a door in an
    open wall. Measured, not assumed.
    """
    offenders = []
    for path in firewall.frozen_source_files():
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if line.lstrip().startswith("#"):
                    continue
                if "os.environ" in line or "getenv" in line:
                    offenders.append(
                        f"{os.path.relpath(path, ROOT)}:{lineno}")
    assert not offenders, (
        f"the frozen core now reads the environment at {offenders}. That is a "
        f"second configuration route, outside the profile firewall entirely, "
        f"and it must be closed or explicitly justified before it ships.")


# ============================================================== fail closed

def test_an_unrecognised_top_level_section_is_refused_not_ignored():
    """The difference between 'ignored' and 'honoured' is invisible to a user.

    A `tuning:` block that is silently dropped looks exactly like a `tuning:`
    block that worked, and the operator finds out which from flight data.
    """
    doc = _base()
    doc["tuning"] = {"unremarkable_name": 1.0}
    with pytest.raises(ProfileError, match="unknown top-level section"):
        validate(doc)


def test_an_invented_stream_key_is_refused():
    """`sigma` and `scale` read as plumbing and are diagnostic parameters.

    Neither is in the frozen core's namespace today, which is exactly why the
    blacklist cannot catch them and why this one place fails closed.
    """
    for invented in ("sigma", "scale", "gain", "residual_limit"):
        doc = _base()
        doc["streams"]["gnss.position"] = {"nominal_rate_hz": 5,
                                           invented: 0.1}
        with pytest.raises(ProfileError, match="unrecognised key"):
            validate(doc)


def test_the_allowlists_do_not_reject_anything_the_repository_ships():
    """A fail-closed rule that breaks the shipped profiles gets widened under
    deadline pressure, and a widened allowlist protects nothing. Check both
    directions."""
    import glob

    from csia.aircraft.profile import load
    paths = sorted(glob.glob(os.path.join(ROOT, "profiles", "*.yaml")))
    assert paths, "no profiles to check"
    for path in paths:
        load(path)      # raises if either allowlist is too tight


# ========================================================= no false positives

def test_the_firewall_does_not_fire_on_ordinary_plumbing():
    """An over-eager firewall is routed around, so it must be quiet.

    Every key here is real plumbing from a shipped profile or an obvious near
    neighbour. If normalisation ever becomes broad enough to catch one of
    these, it has stopped being a firewall and become an obstacle.
    """
    innocuous = [
        "nominal_rate_hz", "status", "note", "port", "baud", "sysid",
        "transmit", "family", "airframe", "description", "id", "enabled",
        "channels", "shadow_only", "props_removed_for_bench",
        "independent_pilot_authority_required", "position_hold",
        "precision_navigation", "inertial_continuation", "mavlink",
        "version_observed_at_runtime", "fault_injector", "serial_device",
        "connection_string", "vehicle_id", "operator", "site", "notes",
    ]
    caught = [k for k in innocuous if firewall.collision(k)]
    assert not caught, (
        f"the firewall fires on ordinary plumbing keys {caught}; each maps to "
        f"{[firewall.collision(k) for k in caught]}. Narrow the normalisation "
        f"-- a guard that blocks legitimate configuration gets disabled.")


def test_folding_is_the_property_it_claims_to_be():
    """One spelling of one word must fold to one comparison form."""
    forms = ["nav_caution", "navCaution", "NavCaution", "NAV_CAUTION",
             "nav-caution", "nav caution", "NAV CAUTION"]
    folded = {firewall.fold(f) for f in forms}
    assert folded == {"navcaution"}, (
        f"these all name one parameter and folded to {folded}")
    # And distinct parameters must NOT collapse together.
    distinct = ["rho_min", "rho_max", "dwell_up", "dwell_down",
                "att_caution", "nav_caution", "w_phys", "w_stat"]
    assert len({firewall.fold(d) for d in distinct}) == len(distinct), \
        "folding has become lossy enough to merge distinct core parameters"


def test_collision_reports_the_source_spelling_not_the_folded_form():
    """An error message naming `navcaution` sends the reader looking for a
    constant that does not exist under that name anywhere."""
    assert firewall.collision("navCaution") == "nav_caution"
    assert firewall.collision("CSIA_SMOOTH_ALPHA") == "SMOOTH_ALPHA"


def test_the_error_message_names_the_frozen_constant():
    doc = _base()
    doc["experiment"] = {"csiaSmoothAlpha": 0.1}
    with pytest.raises(ProfileError) as exc:
        validate(doc)
    assert "SMOOTH_ALPHA" in str(exc.value), (
        "the rejection must say WHICH core parameter was shadowed; "
        "'invalid key' sends the author to guess")


# ============================================== the guard cannot go vacuous

def test_the_fuzzer_would_catch_a_real_hole():
    """A negative control for this file.

    Every test above passes trivially if `collision()` starts returning a
    truthy value for everything, or if the transforms produce nothing. Assert
    the machinery discriminates: an unrelated key of similar shape must NOT
    collide, and the transform set must be non-empty for a real name.
    """
    assert firewall.collision("nominal_rate_hz") is None
    variants = dict(_spelling_variants("nav_caution"))
    assert len(variants) == 6 and all(variants.values())
    # A key that differs from a protected name by more than framing is free.
    assert firewall.collision("caution_nav") is None
    assert firewall.collision("nav_caution_reason_code") is None


def test_every_transform_in_this_file_actually_changes_the_name():
    """A transform that is the identity tests nothing and looks like coverage."""
    inert = []
    for name in ("nav_caution", "SMOOTH_ALPHA", "rho_max", "w_phys"):
        for label, variant in _spelling_variants(name):
            if variant == name:
                inert.append(f"{label}:{name}")
    # `case` on an already-lowercase name and `plural` on a name ending in s
    # legitimately no-op for SOME names; no transform may no-op for ALL.
    by_label = {}
    for entry in inert:
        by_label.setdefault(entry.split(":")[0], 0)
        by_label[entry.split(":")[0]] += 1
    dead = [k for k, v in by_label.items() if v == 4]
    assert not dead, f"transform(s) {dead} are the identity on every name"


def test_no_two_protected_names_fold_together():
    """If two core parameters share a folded form, one of them is unprotected
    in every error message and the index silently keeps only the first."""
    index = {}
    for name in firewall.protected_names():
        index.setdefault(firewall.fold(name), []).append(name)
    clashes = {k: sorted(v) for k, v in index.items() if len(v) > 1}
    assert not clashes, (
        f"distinct frozen-core parameters fold to one comparison form: "
        f"{clashes}. Both are still rejected, but the error names only one.")


def test_the_hand_list_and_the_generated_set_are_both_load_bearing():
    """Neither may be deleted as redundant, and this says why in a test.

    If the generated set ever covers the hand list entirely, someone will
    delete the hand list -- and lose the concept-level entries (`signature`,
    `priors`, `cusum_h`) that no single core constant is named after.
    """
    from csia.aircraft.profile import FORBIDDEN_KEYS
    generated = {firewall.fold(n) for n in firewall.protected_names()}
    hand_only = sorted(k for k in FORBIDDEN_KEYS
                       if firewall.fold(k) not in generated)
    assert hand_only, (
        "every hand-written forbidden key is now covered by the generated "
        "namespace. Before deleting FORBIDDEN_KEYS, check the concept-level "
        "entries are genuinely redundant rather than merely unmatched.")

    gen_only = sorted(n for n in firewall.protected_names()
                      if n.lower() not in FORBIDDEN_KEYS)
    assert gen_only, (
        "the generated namespace adds nothing the hand list did not already "
        "have, which would mean the AST scan has stopped finding constants")
