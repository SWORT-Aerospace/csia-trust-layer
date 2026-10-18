"""Decode with the VEHICLE's message definitions, not the library's.

WHY THIS EXISTS -- a measured defect, not a precaution.

The PX4 qualification run of 2026-08-24 reported this, and it was published:

    esc.current   declared STUB_OR_NONINFORMATIVE   observed UNAVAILABLE
    esc.rpm       declared STUB_OR_NONINFORMATIVE   observed UNAVAILABLE
    -> "No ESC telemetry. ESC_STATUS never arrives on PX4 SIH."

PX4 sent ESC_STATUS 38 times in that 40 s window. The frames arrived, were
well-formed, and were counted -- as `UNKNOWN_291`, because the pymavlink
installed here carries a reduced `common.xml` (205 messages) that has no
message 291. `pymavlink.dialects.v20.common.decode()` returns
`MAVLink_unknown` for any id it does not know, whose type name is
`UNKNOWN_<id>`, and the probe binned that under "unmapped" alongside the
genuinely irrelevant traffic.

So the instrument could not read the message, and reported the PLATFORM as
not sending it. That is the same error as calling a channel a stub because
the aircraft never moved: a property of the measuring apparatus written down
as a property of the thing measured. It survived because "never arrived" and
"I cannot decode this" produce identical evidence at the layer that was
looking -- an empty list either way.

THE FIX HAS TWO HALVES, and the second one matters more:

  1. Decode with the definitions the vehicle was BUILT from. PX4 ships its
     own `message_definitions/v1.0`, ArduPilot ships its own. Those are
     authoritative for what that binary emits; the library's bundled copy is
     a third party's snapshot of a moving standard.

  2. Never let an undecodable frame become a claim about the platform. Even
     with (1), a vehicle can emit something outside its own XML (a vendor
     dialect, a newer build). `qualify_platform.py` therefore resolves every
     surviving `UNKNOWN_<id>` against the vehicle's XML and, if the id names
     a message the contract depends on, marks that channel UNDECODABLE and
     voids the run rather than reporting the channel absent.

(1) can fail -- no checkout, no XML, a generator error. When it does, this
module returns a report saying so and the caller keeps the stock dialect.
It never silently proceeds, because a silent fallback here reintroduces
exactly the defect it was written to remove.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Where each vehicle keeps the XML its own MAVLink code was generated from,
# relative to the checkout root, and which file is the top of the include
# graph. PX4's `development.xml` includes `common.xml`; ArduPilot's
# `ardupilotmega.xml` includes `common.xml` too and adds its own messages.
DEFS_SUBPATH = {
    "px4": os.path.join("src", "modules", "mavlink", "mavlink",
                        "message_definitions", "v1.0"),
    "ardupilot": os.path.join("modules", "mavlink", "message_definitions",
                              "v1.0"),
}
TOP_XML = {"px4": "development.xml", "ardupilot": "ardupilotmega.xml"}

_MESSAGE_RE = re.compile(r'<message\s+id="(\d+)"\s+name="([A-Za-z0-9_]+)"')
_INCLUDE_RE = re.compile(r"<include>([^<]+)</include>")

_LOADED: dict = {}


class DialectReport:
    """What decoder actually ran, and whether it was the vehicle's own.

    Recorded in every qualification result. A reader who wants to know
    whether an "observed UNAVAILABLE" row is a platform fact or a decoder
    limitation must be able to answer that from the result file alone.
    """

    __slots__ = ("platform", "active", "name", "xml", "message_count",
                 "generated", "reason")

    def __init__(self, platform, active, name=None, xml=None,
                 message_count=0, generated=False, reason=""):
        self.platform = platform
        self.active = active
        self.name = name
        self.xml = xml
        self.message_count = message_count
        self.generated = generated
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "vehicle_dialect_active": self.active,
            "dialect": self.name,
            "xml": self.xml,
            "message_count": self.message_count,
            "regenerated_this_run": self.generated,
            "reason": self.reason,
        }

    def __repr__(self):
        return (f"<DialectReport {self.platform} active={self.active} "
                f"{self.name} n={self.message_count}>")


def defs_dir(platform: str, root: str) -> str:
    return os.path.join(root, DEFS_SUBPATH[platform])


def message_names(platform: str, root: str) -> dict:
    """id -> name, read from the vehicle's OWN definitions.

    Deliberately a regex over the XML rather than a dialect import: this has
    to work in exactly the case where the dialect could NOT be built, since
    that is when an unknown id most needs a name. Follows `<include>` so a
    message defined in common.xml resolves when the top file is
    development.xml.
    """
    top = os.path.join(defs_dir(platform, root), TOP_XML[platform])
    names: dict = {}
    seen = set()
    stack = [top]
    while stack:
        path = stack.pop()
        real = os.path.realpath(path)
        if real in seen or not os.path.exists(real):
            continue
        seen.add(real)
        with open(real, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for mid, name in _MESSAGE_RE.findall(text):
            names.setdefault(int(mid), name)
        for inc in _INCLUDE_RE.findall(text):
            stack.append(os.path.join(os.path.dirname(real), inc.strip()))
    return names


def _newest_xml_mtime(directory: str) -> float:
    newest = 0.0
    for entry in os.listdir(directory):
        if entry.endswith(".xml"):
            newest = max(newest, os.path.getmtime(
                os.path.join(directory, entry)))
    return newest


def _generate(platform: str, root: str, out_py: str, log_path: str) -> None:
    from pymavlink.generator import mavgen
    xml = os.path.join(defs_dir(platform, root), TOP_XML[platform])
    opts = mavgen.Opts(output=out_py, wire_protocol="2.0", language="Python",
                      validate=False)
    os.makedirs(os.path.dirname(out_py), exist_ok=True)
    # mavgen is chatty and prints one line per parsed file. That output is
    # evidence (it names every XML that went in) but it is not console
    # material, so it goes to a log next to the generated module.
    with open(log_path, "w", encoding="utf-8") as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            mavgen.mavgen(opts, [xml])


def use_vehicle_dialect(platform: str, root: str,
                        build_dir: str = None) -> DialectReport:
    """Make pymavlink decode with the vehicle's own definitions.

    Returns a report either way. Never raises: a qualification run with an
    incomplete decoder is still worth having as long as the result says the
    decoder was incomplete.
    """
    cached = _LOADED.get(platform)
    if cached is not None:
        # RE-ACTIVATE on a cache hit. `set_dialect` mutates a module-level
        # global in mavutil, so in a process that qualifies two platforms the
        # second call would return this report while the FIRST platform's
        # dialect stayed active -- a cache that silently decodes PX4 with
        # ArduPilot's definitions. Nothing does that today; the next thing
        # that loops over platforms would have, silently.
        if cached.active:
            from pymavlink import mavutil
            mavutil.set_dialect(cached.name)
        return cached

    if platform not in DEFS_SUBPATH:
        return DialectReport(platform, False,
                             reason=f"no definitions path known for "
                                    f"{platform!r}")
    d = defs_dir(platform, root)
    xml = os.path.join(d, TOP_XML[platform])
    if not os.path.exists(xml):
        rep = DialectReport(platform, False, xml=xml,
                            reason=f"vehicle definitions not found at {xml}; "
                                   f"decoding with the library's bundled "
                                   f"dialect, which may not cover every "
                                   f"message this vehicle emits")
        _LOADED[platform] = rep
        return rep

    build_dir = build_dir or os.path.join(ROOT, "build", "mavdialect")
    name = f"csia_{platform}"
    out_py = os.path.join(build_dir, f"{name}.py")
    log_path = os.path.join(build_dir, f"{name}.mavgen.log")
    generated = False
    try:
        if (not os.path.exists(out_py)
                or os.path.getmtime(out_py) < _newest_xml_mtime(d)):
            _generate(platform, root, out_py, log_path)
            generated = True

        modname = f"pymavlink.dialects.v20.{name}"
        mod = sys.modules.get(modname)
        if mod is None:
            spec = importlib.util.spec_from_file_location(modname, out_py)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[modname] = mod
            spec.loader.exec_module(mod)
        # set_dialect resolves the module by attribute traversal from the
        # package, so registering in sys.modules alone is not enough.
        import pymavlink.dialects.v20 as v20
        setattr(v20, name, mod)
        # set_dialect picks the v20 package only when MAVLINK20 is set; without
        # it the name would be looked for under dialects.v10 and the import
        # would fall through to pymavlink's own auto-generation.
        os.environ["MAVLINK20"] = "1"
        from pymavlink import mavutil
        mavutil.set_dialect(name)
        rep = DialectReport(platform, True, name=name, xml=xml,
                            message_count=len(mod.mavlink_map),
                            generated=generated,
                            reason="decoding with the vehicle's own message "
                                   "definitions")
    except Exception as exc:                       # pragma: no cover - env
        rep = DialectReport(platform, False, name=name, xml=xml,
                            generated=generated,
                            reason=f"{type(exc).__name__}: {exc}; decoding "
                                   f"with the library's bundled dialect")
    _LOADED[platform] = rep
    return rep


def undecodable_frames(unmapped_types: dict) -> dict:
    """Pull the `UNKNOWN_<id>` entries out of an adapter's unmapped counter.

    These are NOT "messages we chose not to map". They are messages the
    decoder could not parse at all, and the distinction is the whole point:
    an unmapped ATTITUDE is a decision, an UNKNOWN_291 is a blind spot.
    """
    out = {}
    for key, count in unmapped_types.items():
        if key.startswith("UNKNOWN_"):
            try:
                out[int(key.split("_", 1)[1])] = count
            except ValueError:
                continue
    return out


def producer_messages(contract, platform: str) -> dict:
    """message name -> [channels that depend on it] for this platform.

    `producer_<platform>.message` is either a name or a list of alternatives
    (ArduPilot publishes imu0 as RAW_IMU *or* SCALED_IMU depending on the
    link), so both shapes are accepted.
    """
    key = f"producer_{platform}"
    out: dict = {}
    for channel, row in contract.channels.items():
        spec = row.raw.get(key) or {}
        message = spec.get("message")
        if not message:
            continue
        names = message if isinstance(message, list) else [message]
        for n in names:
            out.setdefault(str(n), []).append(channel)
    return out


def blind_channels(contract, platform: str, undecodable: dict,
                   names: dict) -> dict:
    """channel -> the message name it needed that the decoder could not read.

    This is the guard that makes the ESC_STATUS class of error impossible to
    repeat: any channel whose producer arrived as an undecodable frame is
    UNDECODABLE, never UNAVAILABLE.
    """
    producers = producer_messages(contract, platform)
    blind = {}
    for mid, count in undecodable.items():
        name = names.get(mid)
        if not name:
            continue
        for channel in producers.get(name, []):
            blind[channel] = {"message": name, "id": mid, "frames": count}
    return blind
