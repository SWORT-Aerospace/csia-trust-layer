"""Phase 2 demo: Bayesian trust engine + prediction comparator on phase-1 data.

Three scenario runs of the same 60 s flight:
  clean      — no faults; trust must stay high, and the speed-gated
               heading_course edge must NOT false-alarm during the scripted
               90-deg yaw-in-place hover segment (45-49.5 s)
  gps_spoof  — position walks away at ~3 m/s from t=20-35 s while Doppler
               stays clean; GPS trust must drop and recover
  imu_drift  — imu0 accel-z bias ramps 0.05 m/s^2 per s from t=20-40 s;
               imu0 trust must drop while imu1 stays high (trust-weighted
               neighbor evidence keeps the healthy unit protected)

Writes phase2_*.png to data/sample_logs/ and prints per-tick trust-core
latency (desktop Python — not embedded timing).

Usage:  .venv/bin/python phase2_trust_demo.py
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from csia.scenarios import make_sensors
from csia.prediction import PredictionComparator
from csia.sensors import Fault, generate_flight
from csia.trust_engine import TrustEngine
from csia.trust_engine.engine import consistency
from csia.trust_graph import build_trust_graph

OUT = os.path.join(os.path.dirname(__file__), "data", "sample_logs")
DURATION = 60.0


def run_scenario(truth, faults=()):
    streams = {name: s.sample(truth, faults)
               for name, s in make_sensors().items()}
    td = PredictionComparator(tick_hz=25.0).build(streams, DURATION)
    hist = TrustEngine(build_trust_graph()).run(td)
    return td, hist


def fault_bands(ax, faults):
    for f in faults:
        ax.axvspan(f.start, f.start + f.duration, alpha=0.08, color="red")


def report_latency(name, hist):
    lat = hist.latency_us[10:]  # skip warm-up ticks
    print(f"{name:10s} trust-core latency/tick: "
          f"mean {lat.mean():6.1f} us   p95 {np.percentile(lat, 95):6.1f} us"
          f"   max {lat.max():7.1f} us   (desktop Python, 8 nodes/12 edges)")


def main():
    os.makedirs(OUT, exist_ok=True)
    truth = generate_flight(duration=DURATION, dt=0.01)

    td_clean, h_clean = run_scenario(truth)
    report_latency("clean", h_clean)

    spoof = [Fault("gps_spoof", "gps", start=20.0, duration=15.0,
                   params={"drift": (3.0, 1.0, 0.0)})]
    td_spoof, h_spoof = run_scenario(truth, spoof)
    report_latency("gps_spoof", h_spoof)

    drift = [Fault("bias_drift", "imu0", start=20.0, duration=20.0,
                   params={"axis": 2, "rate": 0.05, "channel": "accel"})]
    td_drift, h_drift = run_scenario(truth, drift)
    report_latency("imu_drift", h_drift)

    t = h_clean.t

    # --- figure 1: clean flight + the speed gate at work ----------------------
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    ax = axes[0]
    for n in h_clean.names:
        ax.plot(t, h_clean.trust[:, h_clean.col(n)], lw=1.1, label=n)
    ax.set_ylabel("Trust Coefficient")
    ax.set_ylim(0.4, 1.0)
    ax.legend(fontsize=7, ncol=4)
    ax.set_title("Clean flight — all Trust Coefficients (Beta prior T=0.8 "
                 "converges up as evidence accumulates)")

    ax = axes[1]
    gate = td_clean.aux["speed_gate"]
    ax.plot(t, gate, lw=1.2, color="tab:green", label="speed gate w(v_h)")
    ax.plot(t, td_clean.aux["vh"] / td_clean.aux["vh"].max(), lw=0.8,
            color="gray", alpha=0.6,
            label=f"horiz speed (norm., max {td_clean.aux['vh'].max():.1f} m/s)")
    ax.axvspan(45.0, 49.5, alpha=0.15, color="orange")
    ax.text(47.2, 0.5, "90° yaw-in-place\n(hover)", ha="center", fontsize=8)
    ax.set_ylabel("gate weight")
    ax.legend(fontsize=8)
    ax.set_title("heading_course edge gate: COG constrains heading only when "
                 "translating (full weight ≥3 m/s, zero ≤2 m/s)")

    ax = axes[2]
    lam_hc = td_clean.edges["heading_course"][2]
    ax.plot(t, consistency(lam_hc), lw=0.9, color="tab:red",
            label="raw consistency exp(-max(0, λ-1)/2), UNGATED")
    ax.plot(t, 1.0 - gate * (1.0 - consistency(lam_hc)), lw=1.1,
            color="tab:blue", label="effective (gated) contribution")
    ax.axvspan(45.0, 49.5, alpha=0.15, color="orange")
    ax.set_ylabel("consistency")
    ax.set_xlabel("t [s]")
    ax.legend(fontsize=8)
    ax.set_title("Why the gate is load-bearing: ungated, the yaw-in-place "
                 "segment (heading moves, COG is near-zero-speed noise) would "
                 "read as a mag/GPS fault")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "phase2_clean_speedgate.png"), dpi=130)
    plt.close(fig)

    # --- figure 2: GPS spoof ---------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    ax = axes[0]
    c = h_spoof.col("gps")
    ax.plot(t, h_clean.trust[:, c], "k--", lw=1, label="gps trust, clean run")
    ax.plot(t, h_spoof.trust[:, c], lw=1.4, color="tab:purple",
            label="gps trust, spoofed run")
    fault_bands(ax, spoof)
    ax.set_ylabel("Trust Coefficient")
    ax.legend(fontsize=8)
    ax.set_title("GPS spoof 20-35 s: position walks off at ~3.2 m/s, Doppler "
                 "stays clean — trust drops, then recovers naturally")

    ax = axes[1]
    for comp, color in (("phys", "tab:red"), ("nbr", "tab:blue"),
                        ("temp", "tab:green"), ("stat", "tab:orange")):
        ax.plot(t, h_spoof.components[comp][:, c], lw=0.9, color=color,
                label=f"C_{comp}")
    fault_bands(ax, spoof)
    ax.set_ylabel("evidence sub-score")
    ax.legend(fontsize=8)
    ax.set_title("Evidence anatomy: internal physics (position-derivative vs "
                 "Doppler) collapses; neighbor edges stay high — the signature "
                 "phase 3 turns into P(GPS fault | pattern)")

    ax = axes[2]
    for key, color in (("altitude_baro", "tab:green"),
                       ("velocity_gps_doppler_0", "tab:blue"),
                       ("heading_course", "tab:red")):
        a, b, lam_e, gate_e = td_spoof.edges[key]
        ax.plot(t, consistency(lam_e), lw=0.9, color=color,
                label=f"c({key})")
    fault_bands(ax, spoof)
    ax.set_ylabel("edge consistency")
    ax.set_xlabel("t [s]")
    ax.legend(fontsize=8)
    ax.set_title("GPS-incident edges stay consistent (spoof is x/y position "
                 "only) — graceful degradation, not a binary kill")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "phase2_gps_spoof.png"), dpi=130)
    plt.close(fig)

    # --- figure 3: IMU bias drift ----------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    ax = axes[0]
    for n, color in (("imu0", "tab:blue"), ("imu1", "tab:orange")):
        c = h_drift.col(n)
        ax.plot(t, h_drift.trust[:, c], lw=1.4, color=color, label=f"{n} trust")
        ax.plot(t, h_clean.trust[:, c], "--", lw=0.8, color=color, alpha=0.5,
                label=f"{n} clean")
    fault_bands(ax, drift)
    ax.set_ylabel("Trust Coefficient")
    ax.legend(fontsize=8)
    ax.set_title("imu0 accel-z bias drift 20-40 s (0.05 m/s²/s): faulty unit "
                 "isolated, healthy imu1 keeps its trust")

    ax = axes[1]
    c0 = h_drift.col("imu0")
    for comp, color in (("nbr", "tab:blue"), ("temp", "tab:green"),
                        ("stat", "tab:orange")):
        ax.plot(t, h_drift.components[comp][:, c0], lw=0.9, color=color,
                label=f"imu0 C_{comp}")
    fault_bands(ax, drift)
    ax.set_ylabel("evidence sub-score")
    ax.legend(fontsize=8)
    ax.set_title("Slow ramp is invisible to the historical predictor (Holt "
                 "adapts) — neighbor physics does the catching")

    ax = axes[2]
    for key, color in (("redundant_imu", "tab:blue"),
                       ("accel_motor_current", "tab:red"),
                       ("accel_esc_rpm", "tab:orange")):
        a, b, lam_e, gate_e = td_drift.edges[key]
        ax.plot(t, consistency(lam_e), lw=0.9, color=color,
                label=f"c({key}) [{a}<->{b}]")
    fault_bands(ax, drift)
    ax.set_ylabel("edge consistency")
    ax.set_xlabel("t [s]")
    ax.legend(fontsize=8)
    ax.set_title("Edges implicating imu0 collapse; imu1's independent edges "
                 "hold — trust-weighting turns symmetric edge evidence into "
                 "asymmetric attribution")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "phase2_imu_bias_drift.png"), dpi=130)
    plt.close(fig)

    # --- console summary ---------------------------------------------------------
    print()
    for label, h in (("clean", h_clean), ("gps_spoof", h_spoof),
                     ("imu_drift", h_drift)):
        mins = {n: h.trust[250:, h.col(n)].min() for n in h.names}  # skip prior convergence
        worst = sorted(mins.items(), key=lambda kv: kv[1])[:3]
        print(f"{label:10s} min trust (t>10 s): "
              + "  ".join(f"{n}={v:.2f}" for n, v in worst))
    for f in (os.path.join(OUT, p) for p in
              ("phase2_clean_speedgate.png", "phase2_gps_spoof.png",
               "phase2_imu_bias_drift.png")):
        print(f"wrote {f}")


if __name__ == "__main__":
    main()
