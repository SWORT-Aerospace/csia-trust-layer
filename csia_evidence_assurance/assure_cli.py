"""`csia-assure`: the one-command CSIA Flight Assurance entry point. OFFBOARD ONLY.

    csia-assure flight.ulg [--out DIR]
    csia-assure analyze flight.ulg [--out DIR]      (the same)

It is `python -m csia_evidence_assurance assure`: the analysis plus the
assurance view. The frozen v2 `csia` command is a different program and is
not touched.
"""

from __future__ import annotations

import sys

from .__main__ import main as _main


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "analyze":
        args = args[1:]
    return _main(["assure", *args])


if __name__ == "__main__":
    sys.exit(main())
