"""Derive the ArduPilot/PX4 board intersection from the two source trees.

WHY THIS EXISTS
---------------
E2 holds the HARDWARE constant and changes the SOFTWARE STACK. That only works
if one physical board is supported by both autopilots, and "supported" has to
come from each project's own board-support tree, not from a vendor page or a
recollection of which boards are popular. The E2 brief says so explicitly:
do not rely on brand reputation.

WHAT IT READS
  ArduPilot  libraries/AP_HAL_ChibiOS/hwdef/<board>/hwdef.dat
             -- the board exists if the directory does; the MCU is the
             `MCU` line; `env SIM_ENABLED 1` or a `-SimOnHardWare` sibling
             marks the simulation-on-hardware variant.
  PX4        boards/<vendor>/<board>/*.px4board
             -- the board exists if the directory does; SIH is enabled when
             a .px4board sets MODULES_SIMULATION_SIMULATOR_SIH=y.

WHAT IT DOES NOT DO
  It does not decide. It produces the evidence table; the decision and its
  reasoning live in hardware/validation_rig/E2_BOARD_SELECTION.md, where a
  human can disagree with it against the same data.

  It also cannot tell you what is IN STOCK, what a board costs, or whether a
  particular retail listing is the revision the tree describes. Those are
  purchase-time checks and are named as such in the selection document.

    python tools/csia_experiment/e2_board_survey.py \
        --ap-root /tmp/ap-probe --px4-root /tmp/px4 --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

#: Boards the two projects both support but name differently. Each entry is
#: justified by a shared MCU and a shared board lineage, and the survey prints
#: the MCU it read from each tree so a wrong pairing is visible rather than
#: assumed.
ALIASES = {
    # ArduPilot hwdef name -> PX4 boards/<vendor>/<board>
    "CubeOrange": "cubepilot/cubeorange",
    "CubeOrangePlus": "cubepilot/cubeorangeplus",
    "CubeYellow": "cubepilot/cubeyellow",
    "Durandal": "holybro/durandal-v1",
    "Pixhawk6C": "px4/fmu-v6c",
    "Pixhawk6X": "px4/fmu-v6x",
    "Pixhawk5X": "px4/fmu-v5x",
    "MatekH743": "matek/h743",
    "MatekH743-mini": "matek/h743-mini",
    "MatekH743-slim": "matek/h743-slim",
    "KakuteH7": "holybro/kakuteh7",
    "KakuteH7v2": "holybro/kakuteh7v2",
    "KakuteH7-Mini": "holybro/kakuteh7mini",
    # "Pixracer-periph" was here and is REMOVED. It is an STM32F427 board
    # and mro/pixracerpro is an STM32H743; the alias was wrong, and the
    # survey's own MCU cross-check is what showed it -- the row printed
    # "STM32F4xx STM32F427xx" against "STM32H743II". That is the failure mode
    # this table's design is meant to make visible rather than silent.
    "mRoPixracerPro": "mro/pixracerpro",
    "mRoControlZeroH7": "mro/ctrl-zero-h7",
    "mRoControlZeroH7-bdshot": "mro/ctrl-zero-h7",
    "MindPX-v2": "airmind/mindpx-v2",
    "CUAV-Nora": "cuav/nora",
    "CUAV-X7": "cuav/x7pro",
}


def ap_boards(ap_root: str) -> dict:
    base = os.path.join(ap_root, "libraries", "AP_HAL_ChibiOS", "hwdef")
    out = {}
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        hwdef = os.path.join(base, name, "hwdef.dat")
        if not os.path.isfile(hwdef):
            continue
        try:
            text = open(hwdef, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        mcu = None
        m = re.search(r"^\s*MCU\s+(\S+)\s+(\S+)", text, re.M)
        if m:
            mcu = f"{m.group(1)} {m.group(2)}"
        out[name] = {
            "hwdef": os.path.relpath(hwdef, ap_root),
            "mcu": mcu,
            "includes": re.findall(r"^\s*include\s+(\S+)", text, re.M)[:4],
        }
    return out


def px4_boards(px4_root: str) -> dict:
    base = os.path.join(px4_root, "boards")
    out = {}
    if not os.path.isdir(base):
        return out
    for vendor in sorted(os.listdir(base)):
        vdir = os.path.join(base, vendor)
        if not os.path.isdir(vdir):
            continue
        for board in sorted(os.listdir(vdir)):
            bdir = os.path.join(vdir, board)
            if not os.path.isdir(bdir):
                continue
            configs = sorted(f for f in os.listdir(bdir)
                             if f.endswith(".px4board"))
            if not configs:
                continue
            sih = []
            for c in configs:
                try:
                    body = open(os.path.join(bdir, c), encoding="utf-8",
                                errors="replace").read()
                except OSError:
                    continue
                if "MODULES_SIMULATION_SIMULATOR_SIH=y" in body:
                    sih.append(c[:-len(".px4board")])
            out[f"{vendor}/{board}"] = {
                "dir": os.path.relpath(bdir, px4_root),
                "targets": [c[:-len(".px4board")] for c in configs],
                "sih_targets": sih,
                "mcu": _px4_mcu(bdir),
            }
    return out


def _px4_mcu(bdir: str):
    """Read the MCU from the board's NuttX defconfig, where PX4 records it."""
    for sub in ("nuttx-config",):
        cfg = os.path.join(bdir, sub, "nsh", "defconfig")
        if not os.path.isfile(cfg):
            continue
        try:
            body = open(cfg, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = re.search(r"^CONFIG_ARCH_CHIP_(STM32\w+)=y", body, re.M)
        if m:
            return m.group(1)
        m = re.search(r"^CONFIG_ARCH_CHIP=\"(\w+)\"", body, re.M)
        if m:
            return m.group(1)
    return None


def mcu_family(text) -> str | None:
    """STM32H7 / STM32F7 / ... from either project's spelling.

    Compared at FAMILY level on purpose. ArduPilot declares Pixhawk6X as
    STM32H743xx and PX4 declares STM32H753II; the H753 is the H743 die with
    the crypto block, i.e. the same board. A part-number comparison would
    report three false mismatches (CubeOrangePlus H757/H747, Pixhawk5X
    F767/F765, Pixhawk6X H743/H753) and train a reader to ignore the check.
    """
    if not text:
        return None
    m = re.search(r"STM32([A-Z])(\d)", str(text).upper())
    return f"STM32{m.group(1)}{m.group(2)}" if m else None


def _git_head(path):
    proc = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"],
                          capture_output=True, text=True, timeout=60)
    return proc.stdout.strip() if proc.returncode == 0 else None


def survey(ap_root: str, px4_root: str) -> dict:
    ap, px = ap_boards(ap_root), px4_boards(px4_root)
    ap_sim = {n for n in ap if n.endswith("-SimOnHardWare")}
    ap_sim_bases = {n[: -len("-SimOnHardWare")] for n in ap_sim}

    both = []
    for ap_name, px_name in sorted(ALIASES.items()):
        if ap_name not in ap or px_name not in px:
            continue
        both.append({
            "ardupilot_hwdef": ap_name,
            "ardupilot_mcu": ap[ap_name]["mcu"],
            "ardupilot_sim_on_hardware": ap_name in ap_sim_bases,
            "px4_board": px_name,
            "px4_mcu": px[px_name]["mcu"],
            "px4_targets": px[px_name]["targets"],
            "px4_sih_targets": px[px_name]["sih_targets"],
            "mcu_family_agrees": (
                mcu_family(ap[ap_name]["mcu"]) is not None
                and mcu_family(ap[ap_name]["mcu"])
                == mcu_family(px[px_name]["mcu"])),
            "both_support_simulation_on_hardware": (
                ap_name in ap_sim_bases
                and bool(px[px_name]["sih_targets"])),
        })

    return {
        "schema": "csia.research.e2_board_survey/1",
        "generated_by": "tools/csia_experiment/e2_board_survey.py",
        "sources": {
            "ardupilot": {"root": ap_root, "head": _git_head(ap_root),
                          "boards_found": len(ap)},
            "px4": {"root": px4_root, "head": _git_head(px4_root),
                    "boards_found": len(px)},
        },
        "method": (
            "Board support is read from each project's OWN tree: ArduPilot "
            "from libraries/AP_HAL_ChibiOS/hwdef/<board>/hwdef.dat, PX4 from "
            "boards/<vendor>/<board>/*.px4board. Nothing here comes from a "
            "vendor page or from reputation."),
        "alias_note": (
            "The two projects name the same board differently, so the "
            "intersection is computed over a hand-written alias table. Each "
            "row prints the MCU read from BOTH trees so a wrong pairing shows "
            "up as an MCU mismatch instead of passing silently."),
        "ardupilot_sim_on_hardware_boards": sorted(ap_sim),
        "px4_sih_board_count": sum(1 for v in px.values()
                                   if v["sih_targets"]),
        "supported_by_both": both,
        "limits": [
            "This says a board is in each project's tree at the surveyed "
            "commit. It does NOT say the firmware is currently built and "
            "published for it, nor that any retail listing is the revision "
            "the tree describes.",
            "It says nothing about availability or price.",
            "The alias table is hand-written. A board supported by both under "
            "names not in the table will be missed -- a false negative, not a "
            "false positive.",
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ap-root", default=os.environ.get("CSIA_AP_ROOT",
                                                        "/tmp/ap-probe"))
    ap.add_argument("--px4-root", default=os.environ.get("CSIA_PX4_ROOT",
                                                         "/tmp/px4"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = survey(args.ap_root, args.px4_root)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
