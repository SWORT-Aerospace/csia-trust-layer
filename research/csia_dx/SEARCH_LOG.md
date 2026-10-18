# CSIA-DX search log

Searches run on 2026-09-28 for the CSIA-DX adversarial prior-art review. The
tool was a web-search tool returning titles, URLs and a summary. Full text
was not reachable (see `research/csia_dx/BIBLIOGRAPHY.md`). The XSYS-001
record was not opened for this review, apart from what the brief allows:
XSYS-001 as an existing empirical primitive.

Every query targeted a field the brief lists. The aim was to **kill** a
claim, not to support it.

| # | exact query | kept | what it showed |
|---|---|---|---|
| DXQ1 | `online diagnosability assessment runtime "diagnosability" changes after sensor failure fault isolability reevaluation` | D43, D13 | quantitative diagnosability under missing measurements; runtime reconfiguration to gain observations under safety constraints |
| DXQ2 | `"robust diagnosability" OR "reliable diagnosability" sensor failures discrete event systems diagnosability under loss of sensors` | D04, D05 | robust diagnosability under permanent and intermittent sensor failures is an established family |
| DXQ3 | `Krysander Frisk "sensor placement for fault diagnosis" isolability structural analysis minimal sensor sets` | D07, D08, D12 | structural isolability and minimal sensor sets |
| DXQ4 | `mode-dependent diagnosability hybrid systems "diagnosability" depends on operating mode fault isolability varies with operating point` | D42, D14 | isolability evaluated per operating mode; mode signatures |
| DXQ5 | `"Sensor Placement for Online Fault Diagnosis" arXiv 2211.11741 runtime reconfiguration switches safety constraints active diagnosis` | D13 | joint sensor placement and active diagnosis |
| DXQ6 | `safe active fault diagnosis state constraints input design "active fault diagnosis" safety constraints Punčochář OR Škach OR Šimandl` | D17 | constrained active fault detection and control |
| DXQ7 | `"Improving diagnosability of hybrid systems through active diagnosis" authors Bayoudh Travé-Massuyès input sequence diagnosability` | D14, D15 | active diagnosis guided by diagnosability; on-board procedures for space systems |
| DXQ8 | `constrained active fault isolation model predictive control input design fault isolation guaranteed state constraints set-based Raimondo Scott Braatz` | D18 | active input guaranteeing isolability under input and state constraints |
| DXQ9 | `QSI TEAMS Designer TEAMS-RT same model design-time testability analysis runtime diagnosis reasoner multi-signal model` | D27 | design-time testability and on-board runtime reasoning from one model |
| DXQ10 | `testability analysis diagnosability matrix design time reused onboard runtime diagnostic reasoner IVHM "D-matrix" same model aircraft` | D29 | on-board model-based reasoners; designing for IVHM |
| DXQ11 | `"Applying Active Diagnosis to Space Systems by On-Board Control Procedures" arXiv 1903.01710 authors` | D15 | authors confirmed |
| DXQ12 | `dynamic observers fault diagnosis Cassez Tripakis minimal sensor activation diagnosability runtime sensor activation policy` | D06 | runtime sensor activation minimal for diagnosability |
| DXQ13 | `test sequencing AO* Pattipati minimum expected cost fault isolation test selection ambiguity group resolution optimal` | D26 | minimum-cost test selection; NP-complete optimal tree |
| DXQ14 | `fault-tolerant control under isolation ambiguity controller robust to set of candidate faults uncertain fault isolation decision under ambiguity` | D38 | supervisory switching over candidate controllers; passive FTC robust to unknown faults |
| DXQ15 | `explaining non-diagnosability why faults cannot be distinguished explanation indistinguishable pair counterexample sensor that restores diagnosability` | D01 | non-diagnosability witnessed by critical pairs of indistinguishable traces |
| DXQ16 | `belief-space planning fault diagnosis POMDP autonomous aircraft contingency actions under diagnostic uncertainty health-aware mission planning` | D20, D32 | belief-space planning that discriminates simultaneous actuator and sensor faults |
| DXQ17 | `active sequential hypothesis testing Chernoff Naghshvar Javidi controlled sensing information utility fault isolation` | D24 | information-optimal, cost-aware active sensing |
| DXQ18 | `control barrier function active fault diagnosis safe excitation input design probing signal safety filter fault isolation UAV` | D22 | quadrotor fault separation with a safety controller |
| DXQ19 | `active fault diagnosis quadrotor multirotor excitation maneuver distinguish actuator fault sensor fault probing input flight test` | D22, D23 | multirotor probing: excitation maneuvers; null-space excitation |
| DXQ20 | `"Online tree-based planning for active spacecraft fault estimation and collision avoidance" Science Robotics authors fault ambiguity actuator sensor` | D20 | s-FEAST details |
| DXQ21 | `"Dynamic vehicle assessment" intelligent contingency management NASA aircraft capability assessment uncertain fault diagnosis flight envelope` | D30 | real-time capability assessment for UAM contingency management |
| DXQ22 | `no fault found aviation cost unscheduled removals diagnostic ambiguity group size maintenance cost percentage NFF avionics` | D34 | NFF 20–50% of avionics removals; testability-driven ambiguity |
| DXQ23 | `diagnosis system reconfiguration after sensor fault structural analysis residual generator reselection online isolability sensor loss` | D12 | residual-generator reselection; diagnosability indices |
| DXQ24 | `fault isolability depends on input excitation operating point "input-dependent" distinguishability of fault models persistence of excitation fault isolation linear systems` | D11 | excitation conditions for distinguishing dynamic models; conditional and unconditional fault distinguishability |
| DXQ25 | `patent determining at runtime which faults remain distinguishable after sensor failure diagnostic coverage degraded sensor set vehicle health` | D35 | sensor diagnostic-coverage patent (design-time metric) |
| DXQ26 | `compiled model-based diagnosis embedded real-time OBDD knowledge compilation diagnosis onboard spacecraft aircraft memory complexity` | D33 | onboard compiled diagnosis |
| DXQ27 | `ambiguity group remaining after isolation conservative action selection maintenance or flight action robust to all candidate failures decision under diagnostic ambiguity avionics` (and a follow-up on avionics diagnostic ambiguity) | D34 | at-wing reasoners for ambiguity reduction; NFF |
| DXQ28 | `"conditional" "unconditional" fault distinguishability Kościelny fault isolability multiple-valued evaluation fault symptoms relation` | D11 | **the term "conditional isolability" is already defined** (different conditioning) |
| DXQ29 | `Eriksson Frisk Krysander quantitative fault diagnosability analysis distinguishability Kullback-Leibler stochastic linear descriptor models fault pairs` | D09, D10 | quantitative pairwise distinguishability; probabilistic sensor faults |
| DXQ30 | `US12151689 "determining diagnostic coverage of sensors to prevent goal violations of autonomous vehicles" assignee` | D35 | assignee and dates |
| DXQ31 | `MADe PHM Technology sensor set optimization diagnostic coverage design time fault isolation DSI eXpress diagnostic design IVHM tools comparison` | D28 | a commercial design-time tool that flags failures not uniquely identifiable |
| DXQ32 | `online diagnosability checking at runtime discrete event systems "on-line" verification diagnosability current state "diagnosability" runtime monitor` | D01 | online diagnosers; diagnosability verification offline |
| DXQ33 | `aircraft loss of monitoring capability annunciation latent failure monitor unavailable crew alert integrity unavailable degraded monitoring CS-25.1309` | D40 | certification basis for annunciating unsafe conditions and latent failures |
| DXQ34 | `Sampath Lafortune Teneketzis "active diagnosis of discrete-event systems" 1998 controller for diagnosability "safe diagnosability" Paoli active diagnosis safety constraints` | D02, D03, D36, D21 | active diagnosis and active safe diagnosis in DES; safe real-time active diagnosis via reachability |
| DXQ35 | `"active fault diagnosis" aircraft OR UAV "safety constraints" OR "flight envelope" auxiliary input design fault isolation reachability constraints survey 2023 2024` | D19 | AFD with chance constraints; maneuvering-envelope reachability |

**Direct fetch attempts (raw.githubusercontent.com).**

| source | result |
|---|---|
| `treyra/s-FEAST` README (paths `main`, `master`, `HEAD`, several file names) | 404: not reachable. D20 stays V0 |
| `faultdiagnosistoolbox/pyfaultdiagnosistoolbox` README | 200: read. D12 at V2 |

**What was not searched well.**

- IEEE Xplore, AIAA ARC and SAE full text, and patent claims: all blocked.
- Theses: only titles surfaced.
- Customer-need evidence beyond the NFF literature and NASA's ICM program:
  no product-demand data was reachable.
