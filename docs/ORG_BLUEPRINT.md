# SWORT Aerospace — 10-Year Engineering Blueprint

> **Scope note:** this is an *organization-level* document. It is placed in
> the CSIA repo for now because that is the only engineering repo that
> exists. When the org structure is built out, it should migrate to a
> dedicated `SWORT-Aerospace/engineering-handbook` repo (see Part 1). It
> deliberately does **not** belong in the public website repo.

Designed for the SWORT that competes with Anduril / Shield AI / SpaceX, not
today's size. Five tenets everything derives from:

1. **Interfaces over integration** — contracts (IDL/API/ICD) are the unit of
   coupling, not shared source. This is what lets 500 engineers not collide.
2. **Artifacts cross boundaries, never source** — repos consume each other's
   published, versioned outputs (packages, images, docs, spec files).
3. **Private and classified are physical boundaries, decided day one** —
   ITAR/classified is a separate enclave, not a folder or a permission.
4. **The flight-code path is certifiable from the first commit; everything
   else is fast** — two engineering cultures, deliberately separated.
5. **Automate the boring safety** (signing, SBOM, provenance, traceability)
   so humans spend judgment on design.

## Part 1 — Organization structure

Three trust-boundary tiers:
- `SWORT-Aerospace` — private-by-default, commercial + ITAR-controlled by access.
- `SWORT-Public` — deliberately published: website, open docs, OSS.
- `SWORT-Secure` — **not GitHub cloud**; GitHub Enterprise Server / AWS
  GovCloud enclave, air-gapped for classified/ITAR-restricted work.
  Designed now, populated later.

Repositories by domain (create just-in-time from a template, not all at once):

- **Platform (shared spine):** `.github` (reusable workflows/templates),
  `engineering-handbook`, `proto` (the contract repo — all cross-service
  IDL/ICD), `platform-libs-{cpp,rust,py}`, `infra` (IaC), `devops-tooling`.
- **Flight & autonomy:** `csia-trust-layer` ✅, `flight-software`,
  `flight-controller-fw`, `autopilot-integration`, `perception`.
- **Ground & apps:** `ground-station`, `fleet-backend`, `mobile-app`,
  `web-console`.
- **Hardware (LFS/PLM):** `hardware-pcb`, `hardware-mech`, `manufacturing`.
- **AI / data / research:** `ai-models`, `datasets`, `simulation`,
  `benchmarks`, `research-papers`.
- **Public:** `swort-web`, `docs-portal`, `oss-*`.
- **Security & compliance:** `security-policies`, `certification`.

## Part 2 — Software architecture (strictly acyclic, downward-only)

```
apps → services → platform-libs + proto/(contract) → pinned 3rd-party
```
No repo imports another's source; it consumes the published package or calls
the versioned API from `proto/`. Contract changes are PRs to `proto/` →
regenerate stubs → publish new SemVer artifact → consumers upgrade
deliberately. Interfaces carry their own SemVer with an N-1 deprecation
window. Circular dependencies are blocked in CI.

## Part 3 — Engineering standards (two profiles)

| Aspect | General software | Flight/embedded (certifiable path) |
|---|---|---|
| Language rules | linters + format-on-CI | MISRA C/C++, no dynamic alloc post-init, bounded loops |
| Branching | trunk-based, short branches | trunk + protected release branches, cherry-pick fixes |
| Review | ≥1 + CODEOWNERS | ≥2 incl. one independent; requirement link mandatory |
| Testing | unit/property/integration, coverage gate | + MC/DC, requirements-based tests, HIL |
| Perf | benchmark regression gate | + WCET, stack-depth analysis |
| Static analysis | CodeQL, type-check | + Polyspace/Astrée, no UB |
| Docs | README + ADRs | + traceability matrix, ICD, FMEA |

Universal: every repo from a template with README, LICENSE, CODEOWNERS,
CONTRIBUTING, ADRs in `docs/adr/`, issue/PR templates, CI gate. ADRs
mandatory for expensive-to-reverse decisions.

## Part 4 — Technology stack (rationale in one line each)

Website: Astro/11ty + Cloudflare Pages (edge, zero ops). GCS: TS/React UI +
Rust core (Tauri) (native perf + memory safety + web skills). Backend: Go
services (+Rust hot paths). Embedded: C/C++ MISRA for the cert path, Rust for
new non-certified modules. AI: Python/PyTorch → ONNX → TensorRT on Jetson.
Sim: PX4/ArduPilot SITL, Gazebo, NVIDIA Isaac Sim. IaC: Terraform. Orchestr.:
Kubernetes (EKS) + distroless. Registry: GitHub Packages/Artifactory
(private). Secrets: Vault + OIDC (no long-lived creds). Auth: SSO + mandatory
hardware MFA. Observability: Prometheus/Grafana/OpenTelemetry, Loki. DBs:
Postgres, TimescaleDB (telemetry), S3 (artifacts), DVC (datasets). Messaging:
NATS/Kafka services, MQTT/MAVLink edge. Cloud: AWS commercial + GovCloud
enclave. Principle: boring proven tech for infra; innovation budget only on
the trust/autonomy core.

## Part 5 — Development workflow

Issue (templated, linked to requirement) → ADR if load-bearing → short branch
→ pre-commit hooks → PR (template: what/why/testing/risk) → CI gates (build,
test, coverage, static analysis, SBOM, perf) → CODEOWNERS review (flight code
= 2 incl. independent) → squash to trunk → auto-deploy staging → tag →
automated changelog + signed artifacts → progressive/canary deploy →
OTel-observed → LTS branches for firmware. Flight software adds requirement↔
test traceability at the PR gate.

## Part 6 — CI/CD

Reusable workflows in `.github`; self-hosted runners for embedded/HIL/GPU.
Per repo type: website (build→Lighthouse→Pages), Python (pytest+native+
latency gate; nightly campaign artifact), C++/Rust (matrix→CodeQL→signed
container), firmware (cross-compile→MISRA→HIL smoke→HSM-signed binary),
docs (build→link-check→portal), research (LaTeX→PDF), sim/bench (nightly
sweeps→ROC artifacts). Cross-cutting in every pipeline: Dependabot/Renovate,
CodeQL, Trivy, **Syft SBOM + cosign signing + SLSA provenance**, acyclicity
check.

## Part 7 — Security (day one)

Private-by-default; `SWORT-Secure` enclave physically separate. SSO +
mandatory hardware MFA; least-privilege teams; CODEOWNERS as access map.
Vault + short-lived OIDC in CI — zero long-lived secrets. Supply chain:
pinned+verified deps, SBOM per artifact, signed artifacts, SLSA-L3 provenance
(a growing DoD contract requirement). Protected trunk + release branches;
signed commits for flight code. Firmware: HSM signing keys; secure-boot
roadmap = hardware root of trust → signed bootloader → signed application.
`security-policies` owns threat models, runbooks, pen-test cadence.

## Part 8 — Documentation ecosystem

Docs-as-code, versioned with the code they describe; `docs-portal`
aggregates. Requirements/ICD/FMEA/validation in the owning repo's `docs/`;
ADRs per repo; certification planning in `certification` (controlled);
research in LaTeX; API docs auto-generated. Graduate requirements to a real
tool (Jama/DOORS or a traceability linter) at ~100 engineers.

## Part 9 — Growth roadmap

- **1 eng (now):** polyrepo by domain; CSIA independent; `.github` +
  templates; nightly benchmark; website separate.
- **5:** reusable workflows; `proto/` contract repo; `docs-portal`; ADR habit.
- **20:** platform team forms; `flight-software` consolidates into a software
  **monorepo** (Bazel/Nx) while hardware/CAD/firmware stay polyrepo;
  self-hosted HIL; Vault.
- **100:** dedicated DevOps + Security + Release + Cert orgs; GovCloud enclave
  populated; requirements tool; SLSA-L3.
- **500+:** multiple product lines; internal platform-as-a-product; classified
  enclave active; per-product monorepos + shared platform; formal DO-178C
  programs per certifiable product.

The interface discipline is the only thing that scales unchanged from 1 to
500. The mature state is **hybrid** — a software monorepo for cohesive
autonomy code, independent repos for hardware/firmware (different tooling,
LFS, cadence, certification), and a physically separate classified enclave.
Monorepo is a software-cohesion tool, never a company-wide mandate.

## Part 10 — Assumptions challenged

1. *"Private is enough for defense"* → no: design the ITAR/classified enclave
   day one, even if empty for years; retrofitting is a compliance nightmare.
2. *"Polyrepo scales forever"* → no: the 500-person end-state is a governed
   hybrid, and the enabler (`proto/`) should exist at 5 engineers.
3. *"CI/CD is per-repo config"* → no: at scale it's a product (reusable
   workflows + templates + scaffolding CLI) owned by a platform team.

Immediate real actions that begin this blueprint: rename `swort` →
`swort-web`; create `SWORT-Aerospace/.github` (reusable workflows) and
`engineering-handbook` (this document as ADR-0001).
