"""Dynamic Trust Graph structure.

CSIA role: this IS the architecture's core data structure. Nodes are sensors,
each carrying a Trust Coefficient in [0, 1] (updated by the trust engine in
phase 2). Edges encode the *physical relationships* from the CSIA research
description; each edge will compute a per-sample consistency metric that
feeds the Bayesian trust update of both endpoint nodes.

Edge list below maps the relationships named in the source paper onto the
sensor nodes this prototype models. Two of the paper's relationships have no
sensor pair here yet: Mag-Heading<->Visual-Heading (no visual odometry node
in this prototype; mag heading is instead checked against GPS course) and
Temp<->Bias-Drift (temperature is modeled as a channel on baro/IMU nodes,
so it appears as an edge annotation, not a separate node).
"""

import networkx as nx

# Sensor nodes: (name, human label, kind)
NODES = [
    ("imu0", "IMU 0\n(ICM-42688-P)", "inertial"),
    ("imu1", "IMU 1\n(ICM-42688-P)", "inertial"),
    ("baro", "Barometer\n(MS5611)", "air_data"),
    ("mag", "Magnetometer\n(RM3100)", "magnetic"),
    ("gps", "GPS", "nav"),
    ("motor_esc", "Motor/ESC\ntelemetry", "propulsion"),
    ("battery", "Battery\nV/I", "power"),
    ("vibration", "Vibration\naccel", "structural"),
]

# (node_a, node_b, relation, description) — relation names trace back to the
# CSIA research description's list of physical relationships.
EDGES = [
    ("imu0", "imu1", "redundant_imu",
     "Dual-IMU cross-check: identical quantities, independent noise/bias"),
    ("imu0", "motor_esc", "accel_motor_current",
     "Acceleration <-> Motor Current: thrust that accelerates the airframe must be drawing current"),
    ("imu1", "motor_esc", "accel_esc_rpm",
     "Acceleration <-> ESC RPM: vertical accel tracks total prop speed squared"),
    ("baro", "gps", "altitude_baro",
     "Altitude <-> Barometric Pressure: baro altitude vs GPS vertical channel"),
    ("imu0", "gps", "velocity_gps_doppler",
     "Velocity <-> GPS Doppler: integrated accel vs Doppler velocity (spoof detector)"),
    ("imu1", "gps", "velocity_gps_doppler",
     "Velocity <-> GPS Doppler (redundant pair)"),
    ("imu0", "mag", "attitude_gravity_mag",
     "Attitude <-> Gravity Vector: accel-derived tilt feeds mag tilt compensation"),
    ("mag", "gps", "heading_course",
     "Mag Heading <-> GPS course-over-ground (stand-in for Visual Heading, no VO node yet)"),
    ("motor_esc", "battery", "power_thrust",
     "Power <-> Thrust: summed motor current must match pack current; V sags with I"),
    ("vibration", "motor_esc", "vibration_prop_freq",
     "Vibration <-> Prop Frequency: dominant vibration line tracks RPM/60"),
    ("battery", "baro", "temp_bias_drift",
     "Temp <-> Bias Drift: shared thermal environment drives baro/IMU bias (annotation edge)"),
]


def build_trust_graph() -> nx.Graph:
    g = nx.Graph()
    for name, label, kind in NODES:
        # trust: the CSIA Trust Coefficient, initialized optimistic; the
        # phase-2 engine owns its recursive Bayesian update.
        g.add_node(name, label=label, kind=kind, trust=1.0)
    for a, b, relation, desc in EDGES:
        # consistency: latest per-sample agreement metric in [0,1], stamped
        # by the prediction comparator (phase 2). None until first update.
        g.add_edge(a, b, relation=relation, description=desc, consistency=None)
    return g


def draw_trust_graph(g: nx.Graph, path: str, title: str = "CSIA Dynamic Trust Graph"):
    """Static structure plot; the live version arrives with the phase-3 dashboard."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    kind_colors = {
        "inertial": "#4C72B0", "air_data": "#55A868", "magnetic": "#C44E52",
        "nav": "#8172B2", "propulsion": "#CCB974", "power": "#64B5CD",
        "structural": "#B47CC7",
    }
    pos = nx.spring_layout(g, seed=7, k=1.6)
    fig, ax = plt.subplots(figsize=(11, 8))
    colors = [kind_colors[g.nodes[n]["kind"]] for n in g.nodes]
    trust = [g.nodes[n]["trust"] for n in g.nodes]
    nx.draw_networkx_edges(g, pos, ax=ax, width=1.4, alpha=0.5)
    nx.draw_networkx_nodes(g, pos, ax=ax, node_color=colors,
                           node_size=[2600 * tr for tr in trust],
                           edgecolors="black", linewidths=1.2)
    nx.draw_networkx_labels(
        g, pos, {n: g.nodes[n]["label"] for n in g.nodes}, ax=ax, font_size=8)
    nx.draw_networkx_edge_labels(
        g, pos, {(a, b): d["relation"] for a, b, d in g.edges(data=True)},
        ax=ax, font_size=6.5, alpha=0.8)
    ax.set_title(f"{title}\nnode size = Trust Coefficient (all 1.0 pre-flight)")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
