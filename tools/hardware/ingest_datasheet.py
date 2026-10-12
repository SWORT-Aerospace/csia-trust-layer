"""Register a datasheet file that is physically in the repository, and hash it.

    python tools/hardware/ingest_datasheet.py \
        --part TCA9548A --manufacturer "Texas Instruments" \
        --file hardware/datasheets/tca9548a/tca9548a.pdf \
        --revision SCPS207K --revision-date 2023-05 \
        --retrieved-from https://www.ti.com/lit/ds/symlink/tca9548a.pdf \
        --retrieved-on 2026-09-20

WHAT THIS DOES AND, MORE IMPORTANTLY, DOES NOT
----------------------------------------------
It records which bytes were present and when. It writes a registration record
with the SHA-256, the stated revision, and the retrieval provenance.

It **does not** flip `csia_bus_provenance.datasheet.DATASHEET_STATUS` to
`VERIFIED`, and there is no flag that makes it. A hash proves which file was
read; it does not prove anybody read it. Flipping that constant means a human
has checked each value in `datasheet.py` against a cited page and table, and
that is a human act this script cannot perform or attest to.

The script prints the exact checklist of constants that still need checking,
so the remaining work is a list rather than a memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "hardware/datasheets/REGISTRY.json"

#: Every constant the owner's gate 6 requires be checked against the document.
CHECKLIST = (
    "supply limits", "logic thresholds", "absolute maximum ratings",
    "slave-address behaviour", "control-register semantics",
    "channel-selection behaviour", "reset / power-on state",
    "maximum clock rate", "timing requirements", "readback behaviour",
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", required=True)
    parser.add_argument("--manufacturer", required=True)
    parser.add_argument("--file", required=True, type=pathlib.Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--revision-date", required=True)
    parser.add_argument("--retrieved-from", required=True)
    parser.add_argument("--retrieved-on", required=True)
    args = parser.parse_args(argv)

    path = args.file if args.file.is_absolute() else ROOT / args.file
    if not path.is_file():
        print(f"no such file: {args.file}\n\n"
              f"The datasheet must be placed in the repository by a human. "
              f"This environment cannot reach ti.com -- the proxy answers 403 "
              f"at CONNECT -- and a file invented here would not be the "
              f"datasheet.", file=sys.stderr)
        return 1
    if path.stat().st_size == 0:
        print(f"{args.file} is empty", file=sys.stderr)
        return 1

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {
        "part_number": args.part,
        "manufacturer": args.manufacturer,
        "original_filename": path.name,
        "repository_path": str(path.relative_to(ROOT)),
        "revision": args.revision,
        "revision_date": args.revision_date,
        "retrieved_from": args.retrieved_from,
        "retrieved_on": args.retrieved_on,
        "sha256": digest,
        "bytes": path.stat().st_size,
        "constants_checked_against_document": False,
        "checked_by": None,
        "page_and_table_references": {},
        "what_this_record_is_not": (
            "not a verification. It records which bytes were present. "
            "DATASHEET_STATUS stays NOT_RETRIEVED until a human checks each "
            "constant against a cited page and table."),
    }

    registry = {}
    if REGISTRY.is_file():
        registry = json.loads(REGISTRY.read_text())
    registry[args.part] = record
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=1, sort_keys=True) + "\n")

    print(f"registered {args.part}")
    print(f"  sha256 {digest}")
    print(f"  wrote  {REGISTRY.relative_to(ROOT)}")
    print("\nDATASHEET_STATUS is still NOT_RETRIEVED and "
          "require_verified_datasheet() still raises.")
    print("Still to be checked by a human, against a cited page and table:")
    for item in CHECKLIST:
        print(f"  [ ] {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
