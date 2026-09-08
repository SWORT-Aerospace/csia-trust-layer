# Unblocking the four things this environment cannot do

Four pieces of work are blocked here and **not** blocked on your machine. This
document is the exact procedure for each, what to expect, and how to feed the
result back so it lands in the evidence chain rather than in a chat window.

**Why they are blocked here, verified rather than assumed** — every outbound
host needed goes through an agent proxy that refuses the CONNECT:

```
$ curl -sS -o /dev/null -w "%{http_code}\n" https://firmware.ardupilot.org/
curl: (56) CONNECT tunnel failed, response 403
$ curl -sS -o /dev/null -w "%{http_code}\n" https://api.crossref.org/works?query=test
curl: (56) CONNECT tunnel failed, response 403
```

and there is no Docker daemon (`/var/run/docker.sock` absent) and no hardware.

---

## 1. ArduPilot SITL

Ubuntu 22.04/24.04, Debian 12, or WSL2. ~4 GB disk, ~20 min for the first
build.

```bash
git clone --recursive https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y   # asks for sudo
. ~/.profile                                              # picks up the PATH
```

If the clone predates the submodules, `git submodule update --init --recursive`.

Then launch a copter and **publish a second MAVLink stream for CSIA**, so
CSIA is not competing with the ground station for the primary link:

```bash
cd ArduCopter
sim_vehicle.py -v ArduCopter -f quad \
    --console --map \
    --out=udp:127.0.0.1:14550 \
    --out=udp:127.0.0.1:14551
```

The first `sim_vehicle.py` run compiles; later runs start in seconds.

**Point CSIA at the second stream, never the first:**

```bash
.venv/bin/python tools/deploy/preflight.py --platform ardupilot \
    --out logs/preflight-sitl.json
.venv/bin/csia-shadow \
    --platform ardupilot \
    --connection udp:127.0.0.1:14551 \
    --log-dir logs/sitl \
    --context SIMULATOR \
    --max-seconds 300
```

`--context SIMULATOR` matters: it keeps the log honest about what produced
it, and simulator logs must never be compared against hardware logs for
timing (portability contract, level 4).

### What to expect

The runbook's Stage 1–3 table applies unchanged: 25 Hz ticks, trust climbing
off the 0.8 prior toward ≥ 0.88, `NORMAL` throughout, no failsafe action
before `arm_time = 10.0 s`. In `STABILIZE` on the ground with no
`vehicle_status`, expect the motor-coupled edges gated **out**.

### PX4 instead

```bash
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot && bash ./Tools/setup/ubuntu.sh
make px4_sitl jmavsim          # or gz_x500 on newer trees
```

PX4 SITL publishes MAVLink on `udp:14550`. Use `--platform px4`; the
staleness timeouts differ per platform and CSIA derives them from the
adapter, so do not override them.

### Feeding it back — and the one experiment worth running first

**Run the HF-014 experiment.** The PX4 decision-replay divergence is
attributed to a per-sensor freshness disagreement and stops there, because
the committed logs never recorded the layer's own `fresh` map. Logs written
after that fix do. So:

```bash
.venv/bin/csia-shadow --platform px4 --connection udp:127.0.0.1:14550 \
    --log-dir logs/sitl-px4 --context SIMULATOR --max-seconds 120
.venv/bin/python tools/assurance/attribute_replay_divergence.py \
    --platform px4 --out /tmp/divergence-new.json
```

A log from this build carries `fresh` per tick and `stale_timeout_s` in the
header. Compare the replay's freshness against the recorded map directly:
that is the measurement that closes HF-004, and it cannot be taken here.

---

## 2. The Docker daemon, and the portability matrix

The portability matrix in `docs/OPTIPLEX_VALIDATION_NODE.md` §5 has **one
measured row and four unmeasured ones**. Filling it needs containers.

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # log out and back in
docker run --rm hello-world       # must print, or nothing below works
```

Rootless `podman` works too and needs no daemon:
`sudo apt install podman`, then substitute `podman` for `docker`.

Then measure each environment and compare:

```bash
for image in ubuntu:22.04 debian:12; do
  docker run --rm -v "$PWD":/w -w /w "$image" bash -c '
    apt-get update -qq && apt-get install -y -qq python3-venv git >/dev/null
    python3 -m venv /tmp/v && /tmp/v/bin/pip install -q -e ".[dev]"
    /tmp/v/bin/python tools/assurance/portability_probe.py \
        --out "/w/research/physical_validation/results/PORTABILITY_${image//[:.]/_}.json"
  '
done
.venv/bin/python tools/assurance/portability_probe.py --compare \
    research/physical_validation/results/PORTABILITY_HOST_current.json \
    research/physical_validation/results/PORTABILITY_ubuntu_22_04.json
```

**What a difference means, and what it does not.** A differing dependency
hash is expected across distributions and is not a failure. A differing
*decision* is a finding. Timing is never compared across hosts — the
contract's level 4 forbids it, and an emulated ARM64 row is not a physical
ARM64 row.

---

## 3. Prior-art search

Three APIs are free and need no key. Run them from a machine with open
egress; none of them are reachable here.

```bash
# OpenAlex -- the broadest; the mailto puts you in the faster pool
curl -sS 'https://api.openalex.org/works?search=sensor+trust+cross-validation+UAV&mailto=YOU@example.com' \
  | jq -r '.results[] | "\(.publication_year)\t\(.title)\t\(.doi)"'

# Crossref
curl -sS 'https://api.crossref.org/works?query=sensor+consistency+trust+propagation+autopilot&rows=20' \
  | jq -r '.message.items[] | "\(.issued.\"date-parts\"[0][0])\t\(.title[0])"'

# arXiv
curl -sS 'http://export.arxiv.org/api/query?search_query=all:%22sensor%20trust%22%20AND%20all:UAV&max_results=25'
```

Semantic Scholar (`https://api.semanticscholar.org/graph/v1/paper/search?query=...`)
also works, and is heavily rate-limited without a key.

### The queries that actually matter

The open question is **novelty of the specific mechanism**, not of the words.
Search for each of these separately and record what you find, including
nothing:

1. cross-sensor consistency as *evidence for a trust value*, rather than as a
   fault detector — Beta/Dirichlet trust updated from pairwise physical
   residuals
2. graph-structured sensor trust where edges are *physics checks* between
   sensor pairs (`altitude_baro`, `velocity_gps_doppler`, …)
3. advisory-only avionics monitors with a *technically enforced* absence of
   command authority
4. evidence-gated *capability* declaration — "which functions does the
   surviving evidence support" — as opposed to conventional FDIR

Put the result in `research/FUTURE_RESEARCH_FRONTIER.md` and the ledger,
**including a negative**: "searched, found the mechanism already published in
X" is a first-class result and more valuable than silence. Under the standing
rule, an unsupported novelty claim is not acceptable — so until this search
runs, the papers must not claim novelty of mechanism.

---

## 4. Hardware: E2 and HITL

Not a network problem — it needs the boards. The build is specified in
`hardware/validation_rig/E2_BUILD_PACKET.md`, the fault injector in
`FAULT_INJECTOR_PROTOCOL.md`, and the gate sequence in
`docs/hardware_validation.md`. `docs/FIELD_INTEGRATION_RUNBOOK.md` §8 is the
minimum first session.

**Fly with props off until Gate D says otherwise**, and run
`tools/deploy/preflight.py` before every session — `INCONCLUSIVE` is not a
pass.

---

## What none of this changes

CSIA remains advisory in every mode. SITL, containers and a literature search
add evidence; they add no command authority, and no result from any of them
promotes a stage on its own.
