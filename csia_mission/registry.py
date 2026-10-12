"""Payload modules, sensor transforms, and the self-describing manifest.

WHY THE SENSOR TRANSFORM MODEL HAS FOUR LEVELS AND NOT ONE
------------------------------------------------------------
This requirement came directly out of XR CAD work and it is load-bearing for
any future physical residual analysis.

    MOUNT DATUM          a feature on the AIRFRAME. Known by construction.
    DEVICE PACKAGE       the outside of the physical part. Measurable with
                         calipers, and what CAD usually contains.
    MEASUREMENT ORIGIN   where the SENSING ELEMENT actually is inside the
                         package. NOT the centre of the box.
    MEASUREMENT AXES     the sensing element's axis convention, which is a
                         property of the die and its orientation on the PCB.

**A CAD BOUNDING BOX GIVES YOU THE SECOND AND TELLS YOU NOTHING ABOUT THE
THIRD OR FOURTH.** An IMU die sits somewhere on a board under a package; a
GNSS phase centre is a property of the antenna, not of the module outline.
Inferring the measurement origin from the package centroid produces a lever
arm that is wrong by millimetres to centimetres, and a lever arm that is
wrong by centimetres produces an angular-rate-times-lever-arm acceleration
error that a residual analysis will attribute to something else entirely.

So the model refuses to let a transform be silently promoted. A transform
whose origin came from a bounding box is PROVISIONAL, it says so, and a
future residual analysis can filter on that field rather than discovering the
problem in its results.

    DEFINED      from a drawing or datasheet with the origin stated
    MEASURED     physically measured on the actual article
    PROVISIONAL  inferred, estimated, or taken from a package outline
    UNKNOWN      not established

THE MANIFEST
------------
A machine-readable record of what physical configuration was actually used in
an experiment. Manually populated for now, deliberately: EEPROM identity, QR
codes and 1-wire IDs are all real options and all premature. The requirement
is that the configuration is RECORDABLE AND HASHABLE, not that it is
automatic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from .provenance import content_hash

#: Status vocabulary shared by masses and transforms. Same four words, same
#: meanings, so a reader does not have to learn two.
DEFINED = "DEFINED"
MEASURED = "MEASURED"
GIVEN = "GIVEN"
PROVISIONAL = "PROVISIONAL"
UNKNOWN = "UNKNOWN"

MASS_STATUS = (MEASURED, GIVEN, PROVISIONAL, UNKNOWN)
TRANSFORM_STATUS = (DEFINED, MEASURED, PROVISIONAL, UNKNOWN)

#: Statuses a physical residual analysis may rely on without qualification.
#: Everything else must be reported as qualified, and this tuple is what a
#: downstream filter should use rather than a hand-written list.
TRUSTWORTHY_FOR_RESIDUALS = (DEFINED, MEASURED)


class RegistryError(ValueError):
    """A registry entry that cannot be read as written."""


@dataclass(frozen=True)
class SensorTransform:
    """One sensor's geometry, with every level's provenance separate."""
    transform_id: str
    sensor_id: str
    mount_datum: str
    #: Translation from the MOUNT DATUM to the MEASUREMENT ORIGIN, metres.
    translation_m: tuple = (0.0, 0.0, 0.0)
    #: Rotation from body axes to MEASUREMENT AXES, as a quaternion (w,x,y,z).
    rotation_quat: tuple = (1.0, 0.0, 0.0, 0.0)
    translation_status: str = UNKNOWN
    rotation_status: str = UNKNOWN
    #: Where the numbers came from, in words. Required when PROVISIONAL.
    basis: str = ""
    package_extent_m: tuple | None = None

    def validate(self) -> None:
        for name, status in (("translation_status", self.translation_status),
                             ("rotation_status", self.rotation_status)):
            if status not in TRANSFORM_STATUS:
                raise RegistryError(
                    f"{self.transform_id}: {name}={status!r} is not one of "
                    f"{list(TRANSFORM_STATUS)}")
        if PROVISIONAL in (self.translation_status,
                           self.rotation_status) and not self.basis:
            raise RegistryError(
                f"{self.transform_id}: a PROVISIONAL transform must state its "
                f"`basis`. A provisional number with no stated origin is "
                f"indistinguishable from a measured one six months later.")
        if len(self.translation_m) != 3:
            raise RegistryError(f"{self.transform_id}: translation must be 3D")
        if len(self.rotation_quat) != 4:
            raise RegistryError(
                f"{self.transform_id}: rotation must be a 4-element "
                f"quaternion (w, x, y, z)")

    @property
    def usable_for_residuals(self) -> bool:
        return (self.translation_status in TRUSTWORTHY_FOR_RESIDUALS
                and self.rotation_status in TRUSTWORTHY_FOR_RESIDUALS)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["translation_m"] = list(self.translation_m)
        d["rotation_quat"] = list(self.rotation_quat)
        if self.package_extent_m is not None:
            d["package_extent_m"] = list(self.package_extent_m)
        d["usable_for_residuals"] = self.usable_for_residuals
        return d


@dataclass(frozen=True)
class PayloadModule:
    """A physical module. References the vehicle profile; does not copy it."""
    module_id: str
    module_type: str
    mass_kg: float | None = None
    mass_status: str = UNKNOWN
    mount_id: str = ""
    transform_id: str | None = None
    power_w: float | None = None
    power_status: str = UNKNOWN
    data_interfaces: tuple = ()
    calibration_id: str | None = None
    serial_id: str | None = None
    provides_products: tuple = ()
    provides_evidence: tuple = ()
    #: The vehicle-profile key this module's plumbing lives under, if any.
    #: A REFERENCE, so the two cannot drift; duplicating rates or channel
    #: names here would create a second source of truth for them.
    vehicle_profile_ref: str | None = None
    notes: str = ""

    def validate(self) -> None:
        if self.mass_status not in MASS_STATUS:
            raise RegistryError(
                f"{self.module_id}: mass_status={self.mass_status!r} is not "
                f"one of {list(MASS_STATUS)}")
        if self.mass_kg is None and self.mass_status != UNKNOWN:
            raise RegistryError(
                f"{self.module_id}: no mass but mass_status="
                f"{self.mass_status!r}. A status without a value is a claim "
                f"about a number that is not there.")
        if self.mass_kg is not None and self.mass_status == UNKNOWN:
            raise RegistryError(
                f"{self.module_id}: has a mass but mass_status=UNKNOWN. Say "
                f"where the number came from -- MEASURED, GIVEN or "
                f"PROVISIONAL -- or do not carry the number.")

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("data_interfaces", "provides_products", "provides_evidence"):
            d[k] = list(d[k])
        return d


@dataclass
class ModuleRegistry:
    modules: dict = field(default_factory=dict)
    transforms: dict = field(default_factory=dict)

    def add_module(self, m: PayloadModule) -> None:
        m.validate()
        if m.module_id in self.modules:
            raise RegistryError(f"duplicate module_id {m.module_id!r}")
        if m.transform_id and m.transform_id not in self.transforms:
            raise RegistryError(
                f"{m.module_id} references transform {m.transform_id!r}, "
                f"which is not registered. A dangling transform reference is "
                f"a lever arm nobody can resolve.")
        self.modules[m.module_id] = m

    def add_transform(self, t: SensorTransform) -> None:
        t.validate()
        if t.transform_id in self.transforms:
            raise RegistryError(f"duplicate transform_id {t.transform_id!r}")
        self.transforms[t.transform_id] = t

    def provisional_entries(self) -> dict:
        """Everything a residual analysis must treat as qualified."""
        return {
            "masses": sorted(m.module_id for m in self.modules.values()
                             if m.mass_status in (PROVISIONAL, UNKNOWN)),
            "transforms": sorted(t.transform_id
                                 for t in self.transforms.values()
                                 if not t.usable_for_residuals),
        }

    def to_dict(self) -> dict:
        return {
            "schema": "csia.mission.module_registry/1",
            "modules": {k: v.to_dict()
                        for k, v in sorted(self.modules.items())},
            "transforms": {k: v.to_dict()
                           for k, v in sorted(self.transforms.items())},
            "provisional": self.provisional_entries(),
        }


# ---------------------------------------------------------------------------


@dataclass
class AircraftManifest:
    """What physical article flew, in a form a machine can hash.

    Manually populated. That is the DESIGN, not a shortcoming: hardware
    identity via EEPROM, 1-wire or QR is a real option and a premature one.
    The requirement is that the actual configuration used in an experiment is
    RECORDABLE AND HASHABLE, and a hand-written YAML satisfies it exactly as
    well as an EEPROM read, while costing nothing and delaying nothing.
    """
    airframe_id: str
    fc_module_id: str | None = None
    payload_module_ids: tuple = ()
    gnss_id: str | None = None
    reference_imu_id: str | None = None
    battery_id: str | None = None
    battery_index: str | None = None
    tip_module_left: str | None = None
    tip_module_right: str | None = None
    calibration_set: str | None = None
    software_set: Mapping[str, str] = field(default_factory=dict)
    configuration_status: str = "NON_FLIGHT_DRAFT"
    notes: str = ""

    def body(self) -> dict:
        d = asdict(self)
        d["payload_module_ids"] = sorted(self.payload_module_ids)
        d["software_set"] = dict(sorted(self.software_set.items()))
        return d

    @property
    def config_hash(self) -> str:
        return content_hash(self.body())

    def unresolved(self) -> list:
        """Fields still None. A manifest with holes says which."""
        return sorted(k for k, v in self.body().items() if v is None)

    def to_dict(self) -> dict:
        d = self.body()
        d["schema"] = "csia.mission.aircraft_manifest/1"
        d["config_hash"] = self.config_hash
        d["unresolved_fields"] = self.unresolved()
        return d


def load_registry(doc: Mapping[str, Any]) -> ModuleRegistry:
    """Build a registry from a plain mapping (as parsed from YAML)."""
    reg = ModuleRegistry()
    for tid, t in sorted((doc.get("transforms") or {}).items()):
        reg.add_transform(SensorTransform(
            transform_id=tid,
            sensor_id=t.get("sensor_id", tid),
            mount_datum=t.get("mount_datum", ""),
            translation_m=tuple(t.get("translation_m") or (0.0, 0.0, 0.0)),
            rotation_quat=tuple(t.get("rotation_quat")
                                or (1.0, 0.0, 0.0, 0.0)),
            translation_status=t.get("translation_status", UNKNOWN),
            rotation_status=t.get("rotation_status", UNKNOWN),
            basis=t.get("basis", ""),
            package_extent_m=(tuple(t["package_extent_m"])
                              if t.get("package_extent_m") else None),
        ))
    for mid, m in sorted((doc.get("modules") or {}).items()):
        reg.add_module(PayloadModule(
            module_id=mid,
            module_type=m.get("module_type", ""),
            mass_kg=m.get("mass_kg"),
            mass_status=m.get("mass_status", UNKNOWN),
            mount_id=m.get("mount_id", ""),
            transform_id=m.get("transform_id"),
            power_w=m.get("power_w"),
            power_status=m.get("power_status", UNKNOWN),
            data_interfaces=tuple(m.get("data_interfaces") or ()),
            calibration_id=m.get("calibration_id"),
            serial_id=m.get("serial_id"),
            provides_products=tuple(m.get("provides_products") or ()),
            provides_evidence=tuple(m.get("provides_evidence") or ()),
            vehicle_profile_ref=m.get("vehicle_profile_ref"),
            notes=m.get("notes", ""),
        ))
    return reg


def _iter_ids(items: Iterable) -> list:
    return sorted(getattr(x, "module_id", x) for x in items)
