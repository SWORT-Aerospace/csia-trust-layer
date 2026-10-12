"""The governed hardware constants, and what may be believed about each.

WHY A REGISTRY RATHER THAN CONSTANTS IN CODE
--------------------------------------------
A number in a source file carries no record of where it came from. Read six
months later, ``ADDRESS_MIN = 0x70`` is indistinguishable from a value somebody
checked against a datasheet page and a value somebody remembered. The two have
very different consequences when they reach silicon, so this module makes the
difference a data field that code can refuse to proceed on.

THE RULE THAT MAKES ``VERIFIED`` MEAN SOMETHING
-----------------------------------------------
``VERIFIED`` is not a label anybody can write. :func:`load_registry` recomputes
it: an entry claiming VERIFIED is rejected unless it names a document, that
document is listed, its file exists in this repository, its SHA-256 matches the
digest recorded for it, and a page or section is cited. A registry that claims
VERIFIED without those is malformed, not verified -- and malformed is treated
as blocking, never as passing.

The asymmetry is deliberate. Every way of getting this wrong resolves toward
refusing hardware.

UNVERIFIED ENTRIES DO NOT RESTATE THEIR VALUE
---------------------------------------------
Where a value exists in code from general knowledge, the registry cites the
symbol rather than copying the number. A copy would be a second place for the
value to live and a second place for it to drift, and it would put a guessed
constant into a file whose whole purpose is to say which constants are guessed.
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
from typing import Dict, List, Optional, Tuple

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

DEFAULT_REGISTRY = ROOT / "hardware/constants/E2M_HARDWARE_CONSTANTS.yaml"

#: A human checked this value against the cited page of a hashed document.
VERIFIED = "VERIFIED"
#: A value exists in code, but from general knowledge rather than a source.
UNVERIFIED = "UNVERIFIED"
#: No value exists anywhere.
MISSING = "MISSING"

DECLARED_STATUSES = (VERIFIED, UNVERIFIED, MISSING)

#: Only VERIFIED permits live hardware. Both of the others block it, and they
#: are kept distinct because they call for different work: UNVERIFIED needs a
#: document checked against an existing number, MISSING needs a number at all.
BLOCKING_STATUSES = (UNVERIFIED, MISSING)

#: The kinds of constant this policy governs, named so that adding a new one
#: is a deliberate act rather than a field nobody classified.
GOVERNED_KINDS = ("i2c_address", "register_value", "register_semantics",
                  "voltage", "electrical_limit", "timing_limit")

REQUIRED_FIELDS = ("name", "kind", "units", "status")


@dataclasses.dataclass(frozen=True)
class HardwareConstant:
    """One governed constant and the evidence behind it.

    ``value`` is populated only for VERIFIED entries, because a value is a
    claim about the device and this registry only makes that claim when it can
    say which page of which hashed document it came from.
    """

    name: str
    kind: str
    units: str
    status: str
    value: Optional[object] = None
    source_document: Optional[str] = None
    source_page_section: Optional[str] = None
    declared_in: Optional[str] = None
    #: Why this entry is not VERIFIED, when it is not. Empty when it is.
    problems: Tuple[str, ...] = ()

    @property
    def blocks_live_hardware(self) -> bool:
        return self.status != VERIFIED

    def as_dict(self) -> dict:
        out = dataclasses.asdict(self)
        out["problems"] = list(self.problems)
        out["blocks_live_hardware"] = self.blocks_live_hardware
        return out


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RegistryMalformed(ValueError):
    """The registry itself cannot be read.

    Separate from :class:`~csia_hardware_gate.gate.HardwareConfigurationBlocked`
    because the two are different failures: one says the hardware may not be
    driven, the other says the file that decides that is unreadable. Both stop
    a live run; conflating them would hide a broken registry behind a routine
    refusal.
    """


def _check_document(entry: dict, documents: Dict[str, dict],
                    root: pathlib.Path) -> List[str]:
    """Problems with the primary source an entry cites. Never raises."""
    problems: List[str] = []
    doc_id = entry.get("source_document")
    if not doc_id:
        return ["claims VERIFIED but names no source document"]

    document = documents.get(doc_id)
    if document is None:
        return [f"cites document {doc_id!r}, which the registry does not list"]

    recorded = document.get("sha256")
    declared_path = document.get("path")
    if not declared_path:
        problems.append(f"document {doc_id!r} records no path")
    if not recorded:
        problems.append(f"document {doc_id!r} records no sha256")
    if problems:
        return problems

    path = root / declared_path
    if not path.is_file():
        return [f"document {doc_id!r} is not in the repository at "
                f"{declared_path}; a digest recorded for a file nobody can "
                f"open is not evidence"]

    actual = sha256(path)
    if actual != recorded:
        problems.append(
            f"document {doc_id!r} hashes to {actual[:16]}... but the registry "
            f"records {str(recorded)[:16]}...")

    if not entry.get("source_page_section"):
        problems.append(
            "claims VERIFIED but cites no page or section; a whole document "
            "is not a citation for one number")
    if entry.get("value") is None:
        problems.append("claims VERIFIED but carries no value")
    return problems


def _load_entry(raw: dict, documents: Dict[str, dict],
                root: pathlib.Path) -> HardwareConstant:
    """One entry, with its claimed status re-derived rather than trusted."""
    missing = [f for f in REQUIRED_FIELDS if raw.get(f) in (None, "")]
    if missing:
        raise RegistryMalformed(
            f"constant {raw.get('name')!r} is missing required field(s): "
            f"{missing}")

    name = raw["name"]
    kind = raw["kind"]
    if kind not in GOVERNED_KINDS:
        raise RegistryMalformed(
            f"constant {name!r} has kind {kind!r}, which is not one of "
            f"{GOVERNED_KINDS}. A constant nobody classified is not governed, "
            f"and an ungoverned electrical value is the thing this file "
            f"exists to prevent.")

    claimed = raw["status"]
    if claimed not in DECLARED_STATUSES:
        raise RegistryMalformed(
            f"constant {name!r} has status {claimed!r}, not one of "
            f"{DECLARED_STATUSES}")

    problems: Tuple[str, ...] = ()
    status = claimed
    if claimed == VERIFIED:
        found = _check_document(raw, documents, root)
        if found:
            # A VERIFIED claim that does not hold up is DOWNGRADED, not
            # accepted and not raised. Downgrading keeps the run blocked while
            # naming precisely what is wrong.
            status = UNVERIFIED
            problems = tuple(found)

    return HardwareConstant(
        name=name,
        kind=kind,
        units=raw["units"],
        status=status,
        value=raw.get("value") if status == VERIFIED else None,
        source_document=raw.get("source_document"),
        source_page_section=raw.get("source_page_section"),
        declared_in=raw.get("declared_in"),
        problems=problems,
    )


def load_registry(path: os.PathLike | str = DEFAULT_REGISTRY,
                  root: pathlib.Path = ROOT) -> Tuple[HardwareConstant, ...]:
    """Read the registry. Never writes, and never upgrades a status."""
    path = pathlib.Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RegistryMalformed(f"cannot read {path}: {error}") from error

    if not isinstance(document, dict):
        raise RegistryMalformed(f"{path} is not a mapping")

    entries = document.get("constants")
    if not isinstance(entries, list) or not entries:
        raise RegistryMalformed(
            f"{path} declares no constants. An empty registry would let every "
            f"live run through on the grounds that nothing was governed.")

    documents = {d.get("document_id"): d
                 for d in (document.get("documents") or [])
                 if isinstance(d, dict)}

    return tuple(_load_entry(e, documents, root) for e in entries)


def blocking(constants=None) -> Tuple[HardwareConstant, ...]:
    """Every constant that is not VERIFIED, in declaration order."""
    if constants is None:
        constants = load_registry()
    return tuple(c for c in constants if c.blocks_live_hardware)


def summarise(constants=None) -> dict:
    """Counts by status, for a report that is not a pass/fail alone."""
    if constants is None:
        constants = load_registry()
    counts: Dict[str, int] = {}
    for c in constants:
        counts[c.status] = counts.get(c.status, 0) + 1
    return {"total": len(constants), "by_status": counts,
            "blocking": [c.name for c in constants if c.blocks_live_hardware]}
