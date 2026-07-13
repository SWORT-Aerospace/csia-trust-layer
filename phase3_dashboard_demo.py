"""Phase 3 demo: causal diagnosis + dashboard (thin wrapper over the csia package).

Equivalent production commands:
  csia build       # rebuild scenario replays
  csia serve       # serve the dashboard at http://127.0.0.1:8017
  csia report      # detection/diagnosis summary table

Usage:
  .venv/bin/python phase3_dashboard_demo.py            # build only
  .venv/bin/python phase3_dashboard_demo.py --serve    # build + serve
  .venv/bin/python phase3_dashboard_demo.py --serve --skip-build --port 8017
"""

import argparse
import logging
import os

import numpy as np

from csia.dashboard import export_replay, render_static_dashboard, serve
from csia.scenarios import SCENARIOS, run_scenario
from csia.sensors import generate_flight
from csia.trust_graph import build_trust_graph

ROOT = os.path.dirname(os.path.abspath(__file__))
REPLAY_DIR = os.path.join(ROOT, "data", "replay")
OUT = os.path.join(ROOT, "data", "sample_logs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8017)
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)

    if not args.skip_build:
        os.makedirs(REPLAY_DIR, exist_ok=True)
        os.makedirs(OUT, exist_ok=True)
        truth = generate_flight()
        graph = build_trust_graph()
        for name in SCENARIOS:
            title, faults, td, hist, diag = run_scenario(name, truth=truth)
            export_replay(name, title, td, hist, diag, graph, faults, REPLAY_DIR)
            nominal = diag.causes.index("nominal")
            non_nom = diag.posterior.copy()
            non_nom[:, nominal] = 0.0
            kk = int(np.argmax(non_nom.max(axis=1)))
            print(f"{name:18s} peak diagnosis @ t={diag.t[kk]:5.1f}s: "
                  f"{diag.callout(kk)}")
            if name == "gps_spoof":
                render_static_dashboard(
                    td, hist, diag, graph, faults,
                    os.path.join(OUT, "phase3_dashboard_gps_spoof.png"),
                    "CSIA phase 3 — static dashboard, GPS spoof scenario")
        print(f"replays -> {REPLAY_DIR}")

    if args.serve:
        serve(args.port, replay_dir=REPLAY_DIR)


if __name__ == "__main__":
    main()
