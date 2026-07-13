"""Phase 1 demo: synthetic sensor streams for a short simulated flight.

Runs the scripted 60 s flight, samples every sensor node of the trust graph
(clean pass + a fault-injected pass to prove the injection machinery), and
writes three figures to data/sample_logs/:

  phase1_raw_sensors.png     — raw output of all 8 sensor models, clean flight
  phase1_fault_injection.png — same flight with GPS spoof + mag EMI + power sag
  phase1_trust_graph.png     — static structure of the Dynamic Trust Graph

Usage:  .venv/bin/python phase1_raw_sensors.py
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from csia.scenarios import make_sensors
from csia.sensors import Fault, generate_flight
from csia.trust_graph import build_trust_graph, draw_trust_graph

OUT = os.path.join(os.path.dirname(__file__), "data", "sample_logs")


def sample_all(truth, faults=()):
    return {name: s.sample(truth, faults) for name, s in make_sensors().items()}


def plot_flight(truth, data, path, title, faults=()):
    fig, axes = plt.subplots(4, 2, figsize=(15, 13))
    fig.suptitle(title, fontsize=13)

    ax = axes[0, 0]
    ax.plot(data["baro"]["t"], data["baro"]["altitude"], lw=0.7,
            label="baro alt (MS5611)", color="tab:green")
    g = data["gps"]
    ax.plot(g["t"][g["valid"]], g["pos"][g["valid"], 2], ".", ms=2,
            label="GPS alt", color="tab:purple")
    ax.plot(truth.t, truth.pos[:, 2], "k--", lw=1, label="truth")
    ax.set_ylabel("altitude [m]"); ax.legend(fontsize=7); ax.set_title("Altitude <-> Baro edge")

    ax = axes[0, 1]
    ax.plot(truth.pos[:, 0], truth.pos[:, 1], "k--", lw=1, label="truth path")
    ax.plot(g["pos"][g["valid"], 0], g["pos"][g["valid"], 1], ".", ms=2.5,
            color="tab:purple", label="GPS fix")
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.axis("equal")
    ax.legend(fontsize=7); ax.set_title("GPS ground track")

    ax = axes[1, 0]
    for name, c in (("imu0", "tab:blue"), ("imu1", "tab:orange")):
        d = data[name]
        ax.plot(d["t"], d["accel"][:, 2], lw=0.4, alpha=0.8, color=c,
                label=f"{name} accel z")
    ax.set_ylabel("specific force z [m/s$^2$]"); ax.legend(fontsize=7)
    ax.set_title("Dual ICM-42688-P (redundant_imu edge)")

    ax = axes[1, 1]
    d = data["imu0"]
    ax.plot(d["t"], np.rad2deg(d["gyro"][:, 2]), lw=0.4, color="tab:blue",
            label="imu0 gyro z")
    ax.plot(data["mag"]["t"], np.rad2deg(np.gradient(
        data["mag"]["heading"], data["mag"]["t"])), lw=0.4, alpha=0.6,
        color="tab:red", label="d(mag heading)/dt")
    ax.set_ylabel("yaw rate [deg/s]"); ax.legend(fontsize=7)
    ax.set_title("Gyro vs mag-derived heading rate")

    ax = axes[2, 0]
    d = data["motor_esc"]
    for m in range(4):
        ax.plot(d["t"], d["rpm"][:, m], lw=0.5, label=f"motor {m}")
    ax.set_ylabel("RPM"); ax.legend(fontsize=6, ncol=4)
    ax.set_title("ESC telemetry RPM (accel_esc_rpm edge)")

    ax = axes[2, 1]
    b = data["battery"]
    ax.plot(b["t"], b["voltage"], color="tab:cyan", lw=0.9, label="pack V")
    ax2 = ax.twinx()
    ax2.plot(b["t"], b["current"], color="tab:olive", lw=0.7, label="pack I")
    ax2.plot(d["t"], d["current"].sum(axis=1), color="tab:brown", lw=0.5,
             alpha=0.6, label="sum ESC I")
    ax.set_ylabel("V"); ax2.set_ylabel("A")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7)
    ax.set_title("Battery (power_thrust / batt V<->I edges)")

    ax = axes[3, 0]
    v = data["vibration"]
    ax.plot(v["t_rms"], v["rms"], lw=0.8, color="tab:pink", label="vib RMS (10 Hz)")
    ax2 = ax.twinx()
    ax2.plot(v["t"][::100], v["prop_freq_hz"][::100], lw=0.7, color="gray",
             alpha=0.7, label="prop freq")
    ax.set_ylabel("RMS [m/s$^2$]"); ax2.set_ylabel("Hz"); ax.set_xlabel("t [s]")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7)
    ax.set_title("Vibration (vibration_prop_freq edge)")

    ax = axes[3, 1]
    m = data["mag"]
    ax.plot(m["t"], np.rad2deg(m["heading"]), lw=0.6, color="tab:red",
            label="mag heading")
    ax.plot(truth.t, np.rad2deg(np.unwrap(truth.att[:, 2])), "k--", lw=1,
            label="true yaw")
    ax.set_ylabel("heading [deg]"); ax.set_xlabel("t [s]"); ax.legend(fontsize=7)
    ax.set_title("RM3100 heading (heading_course edge)")

    for f in faults:
        for ax in axes.flat:
            if ax is axes[0, 1]:  # ground track: x-axis is meters, not time
                continue
            ax.axvspan(f.start, f.start + f.duration, alpha=0.08, color="red")

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"wrote {path}")


def main():
    os.makedirs(OUT, exist_ok=True)
    truth = generate_flight(duration=60.0, dt=0.01)

    # --- clean pass -----------------------------------------------------------
    clean = sample_all(truth)
    for name, d in clean.items():
        keys = [k for k in d if k not in ("t", "valid")]
        print(f"{name:10s} {len(d['t']):6d} samples @ "
              f"{1.0 / np.mean(np.diff(d['t'])):7.1f} Hz  channels: {keys}")
    plot_flight(truth, clean, os.path.join(OUT, "phase1_raw_sensors.png"),
                "CSIA phase 1 — raw synthetic sensor streams, clean 60 s flight")

    # --- fault-injected pass (proves the injection machinery; detection is
    #     phase 2's job) --------------------------------------------------------
    faults = [
        Fault("gps_spoof", "gps", start=20.0, duration=15.0,
              params={"drift": (3.0, 1.0, 0.0)}),
        Fault("emi_spike", "mag", start=40.0, duration=6.0,
              params={"amplitude": 10.0, "rate_hz": 12.0}),
        Fault("power_sag", "battery", start=48.0, duration=4.0,
              params={"depth_v": 1.2}),
        Fault("power_sag", "motor_esc", start=48.0, duration=4.0,
              params={"rpm_loss": 350.0}),
    ]
    faulty = sample_all(truth)
    faulty.update({k: make_sensors()[k].sample(truth, faults)
                   for k in ("gps", "mag", "battery", "motor_esc")})
    plot_flight(truth, faulty, os.path.join(OUT, "phase1_fault_injection.png"),
                "CSIA phase 1 — same flight with injected faults "
                "(red bands): GPS spoof 20-35 s, mag EMI 40-46 s, power sag 48-52 s",
                faults=faults)

    # --- trust graph structure -------------------------------------------------
    g = build_trust_graph()
    print(f"\ntrust graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    for a, b, d in g.edges(data=True):
        print(f"  {a:10s} <-> {b:10s}  [{d['relation']}]")
    draw_trust_graph(g, os.path.join(OUT, "phase1_trust_graph.png"))
    print(f"wrote {os.path.join(OUT, 'phase1_trust_graph.png')}")


if __name__ == "__main__":
    main()
