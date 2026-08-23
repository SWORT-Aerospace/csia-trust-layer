"""Bake the live web dashboard into a single self-contained HTML file.

Takes csia/dashboard/web/index.html (the real dashboard) and the generated
data/replay/*.json, inlines the replay data, and rewrites the three fetch()
calls to read from the embedded object — producing ONE HTML file that runs
the actual dashboard code against the actual generated data with zero server
and zero network. The "live" streaming tab (which needs the running runtime)
is omitted; all replay scenarios are fully interactive (play/scrub/inspect).

  python tools/build_standalone_dashboard.py [out.html]

This is not a mock — it is the shipping dashboard, packaged for offline view.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "csia", "dashboard", "web", "index.html")
REPLAY = os.path.join(ROOT, "data", "replay")


def main(argv=None):
    argv = argv or sys.argv[1:]
    out = argv[0] if argv else os.path.join(ROOT, "dashboard_standalone.html")

    src = open(HTML).read()

    names = sorted(f[:-5] for f in os.listdir(REPLAY) if f.endswith(".json"))
    embedded = {"index": names, "data": {}}
    for n in names:
        with open(os.path.join(REPLAY, f"{n}.json")) as fh:
            embedded["data"][n] = json.load(fh)
    blob = json.dumps(embedded, separators=(",", ":"))
    blob = blob.replace("</", "<\\/")  # never break out of <script>

    # 1) index fetch -> embedded list
    src = src.replace(
        'scenarios = await (await fetch("/data/index.json")).json();',
        "scenarios = EMBEDDED.index;")
    # 2) load() data fetch (+ 503 live-warmup branch) -> embedded lookup
    src = re.sub(
        r'const resp = await fetch\(`/data/\$\{name\}\.json`\);.*?'
        r'data = await resp\.json\(\);',
        "data = EMBEDDED.data[name];",
        src, count=1, flags=re.DOTALL)
    # 3) inject the embedded blob just after the opening <script>
    src = src.replace('<script>\n"use strict";',
                      '<script>\n"use strict";\nconst EMBEDDED = '
                      + blob + ";", 1)

    with open(out, "w") as fh:
        fh.write(src)
    mb = os.path.getsize(out) / 1048576
    print(f"wrote {out} ({mb:.1f} MB, {len(names)} scenarios)")
    # sanity: the three network calls to /data/ must be gone (live.json in
    # refreshLive is fine — it never runs without the 'live' tab)
    remaining = [ln for ln in open(out) if "/data/index.json" in ln
                 or "/data/${name}" in ln]
    assert not remaining, f"unpatched fetch remains: {remaining}"
    print("verified: no index/replay network fetches remain")


if __name__ == "__main__":
    main()
