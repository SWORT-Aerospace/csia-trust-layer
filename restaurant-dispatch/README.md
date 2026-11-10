# Syncora

Syncora keeps the kitchen and dining room in sync. It assigns food runs, times
course releases, and tells the host when a table is ready, so everyone sees
who owns the next step. It records who owns each handoff, routes missed offers
to backup coverage or a lead, shows when work is physically complete, and
measures each shift so a pilot can be judged on real service.

One Django codebase with one dispatch engine serves two editions:

| Edition | Preset | What changes |
|---|---|---|
| Regular Service | — | Expo taps **Food ready**. The run is offered to one runner, then backup, then the floor lead. |
| Fine Dining | **Captain Release** | Expo **stages** courses at the pass. Runners can't see them until the captain releases to one runner, and missed offers return to the captain. |
| Fine Dining | **Pairing Coordination** | Adds a sommelier readiness check. The captain can mark a course as needing no pairing. |
| Fine Dining | **Coordinated Service** | Also requires the captain's confirmation that the service team is ready. One runner is assigned. |

Table resets work the same in both editions:

1. A server or host confirms the party has physically left.
2. A busser claims and completes the reset.
3. The host sees **Ready to seat**.

Paying the check never marks a table vacant.

> This directory is self-contained. It lives alongside, and doesn't touch, the
> aerospace project at the repository root. Internal identifiers (the
> `dispatch` app, `DISPATCH_*` settings, URLs and database tables) predate the
> Syncora name and are kept stable on purpose.

---

## Quick start (local)

Requirements: Python 3.11+ (tested on 3.12 and 3.13). Local development uses
SQLite and an in-process rate limiter, so no other services are needed.

```bash
cd restaurant-dispatch
```

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
scripts/dev.sh
```

`scripts/dev.sh` migrates, seeds the sample restaurants, and starts the
**timer worker** in the background and the web server on port 8000
(`scripts/dev.sh 8080` for another port).

| What | URL |
|---|---|
| Homepage | http://127.0.0.1:8000/ |
| Demo (isolated sandbox, guided tour) | http://127.0.0.1:8000/demo/ |
| Staff sign in | http://127.0.0.1:8000/signin/ |
| Pair a phone or tablet | http://127.0.0.1:8000/pair/ |
| Set up a venue | http://127.0.0.1:8000/setup/ |
| Liveness | http://127.0.0.1:8000/healthz |

To run the processes separately:

```bash
.venv/bin/python manage.py migrate
```

```bash
.venv/bin/python manage.py seed_demo
```

```bash
.venv/bin/python manage.py run_dispatch_worker
```

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

### The demo, in about a minute

1. Open **/demo/** and pick *Regular Service* or a *Fine Dining* preset. Each
   visitor gets a private sandbox restaurant with demo data and a random,
   passwordless account. It is deleted after `DISPATCH_DEMO_TTL_HOURS`.
2. The **guided tour** on the demo floor runs real server actions as each
   person, and waits for the real timer worker.
   - **Regular Service:** expo fires table 4. Maria's offer expires. The
     worker routes it to Dev (backup), Dev delivers, the host confirms a party
     left, the busser resets the table, and the host sees *Ready to seat*.
   - **Fine Dining:** expo stages a course, which runners can't see. The
     captain's early release is refused by the server until the sommelier
     confirms the pairing (and, in Coordinated Service, the captain confirms
     the team). Then it's released to one runner and delivered.
3. Sandboxes use shorter offer windows (15s first offer, 25s backup), set on
   the sandbox location only. Real locations keep their own windows (Manage →
   Rules).
4. On a phone, the yellow bar has a **Switch person** button. It marks the
   person the tour needs next, and a blue tour bar keeps the next action at
   the top of every screen.
5. Every staff screen is live and permission-checked, so you can explore
   freely after the tour.

### Seeded local accounts

`seed_demo` creates two persistent sample restaurants with password accounts
for trying **Staff sign in** locally. The password is
`DISPATCH_DEMO_STAFF_PASSWORD` (default `service-demo-local`).

| Restaurant | Accounts |
|---|---|
| Juniper & Pine (Regular Service) | `jp-sam` expo · `jp-maria`, `jp-dev` runners · `jp-lee`, `jp-jo` bussers · `jp-ana` host · `jp-theo` server · `jp-rae` floor lead · `jp-kim` manager |
| Marrow Room (Fine Dining, Pairing Coordination) | `mr-noor` expo · `mr-elise` captain · `mr-jordan` sommelier · `mr-mateo`, `mr-priya` runners · `mr-lee` busser · `mr-ana` host · `mr-kim` manager |

These accounts are local only:

- `seed_demo` refuses to run unless `DJANGO_DEBUG=true`.
- Seeded accounts can't sign in when `DISPATCH_ALLOW_DEMO_LOGINS=false`.
- `check --deploy` fails (`dispatch.E001`) if they are allowed on a non-debug
  deployment.

---

## Measuring a pilot

**Manage → Shift report** reports by location and shift, in the location's
time zone. Presets include *Late*, which crosses midnight, and custom start
and end times are allowed. All numbers come from Syncora's own task
timestamps and audit events.

- **Handoff times:** food ready → delivered (Regular Service), and party left
  → reset done. Each shows the median, the 90th percentile and the sample
  count, and is flagged when under 20 completed tasks.
- **Fine Dining:** time intentionally *held at the pass* is reported
  separately from *released → delivered*. Time a missed offer spent back with
  the captain is not counted as held.
- **Resets** can be filtered by whether guests were waiting. The host sets
  *Guests waiting for a table?* on the Tables screen, and each reset records
  that state when the party leaves.
- **Distinct counts:**
  - *missed offers* and *declined offers*: counted per offer
  - *routed to backup* and *escalated*: counted per task
  - *manual interventions*: counted per lead, captain or manager action
    outside normal routing

  Each count's definition is shown next to it.
- **Completed vs unresolved:** only completed work is timed. Open and
  cancelled tasks are listed separately, and a late reset for an earlier
  party is excluded.
- **Also shown:** covers seated in Syncora, interventions per 100 covers, and
  setup duration from the wizard's recorded start and finish.
- **Manually recorded observations:** covers, waitlist, staffing, order
  accuracy, complaints and a stopwatch baseline live in a visibly separate
  panel. They are compared against the **proposed** targets (20% faster at the
  90th percentile, 25% fewer interventions per 100 covers) only when both
  sides were measured.
- **CSV export:** manager only, and scoped to the membership in the URL.
  Spreadsheet formulas are escaped, and the file contains no guest or staff
  names and no notes.
- **Excluded or flagged:** practice tickets are excluded. Demo and sample
  restaurants are flagged as "not pilot evidence".

The one-page pilot runbook is [`docs/pilot-runbook.md`](docs/pilot-runbook.md).

---

## Tests

Backend: 97 tests.

```bash
.venv/bin/python manage.py test dispatch
```

The same suite on PostgreSQL:

```bash
DATABASE_URL=postgres://USER:PASSWORD@127.0.0.1:5432/DBNAME .venv/bin/python manage.py test dispatch
```

The Redis-backed tests use `DISPATCH_TEST_REDIS_URL`, which defaults to
`redis://127.0.0.1:6379/15`. They flush that database, and they're skipped
(and reported as skipped) if Redis isn't reachable. Two of them start two
separate gunicorn processes and prove the pairing and demo-start limits are
shared.

Browser checks (Playwright + Chromium) against a running server and worker:

```bash
NODE_PATH=$(npm root -g) node e2e/run_flows.cjs http://127.0.0.1:8000
```

The browser suite (15 checks) covers:

- the homepage at 390 px and 1440 px
- the original Regular and Fine Dining journeys
- offer expiry with every tab closed
- the unconfirmed-action banner
- both guided tours (desktop, and iPhone 13 emulation)
- mobile role switching
- the host waitlist toggle
- the shift report and CSV download

Screenshots and `report.json` are written to `e2e/artifacts/` (git-ignored).

| Requirement | Automated coverage |
|---|---|
| Regular run Expo → Runner → Delivered; expired offer → backup → lead | `test_regular`, e2e |
| Reset Vacated → Busser → Ready to seat; a stale reset can't free a new party's table | `test_resets`, e2e |
| Captain hold and release; pairing and team readiness block early release | `test_fine_dining`, e2e, `test_demo_tour` |
| One winner for simultaneous claims; replays don't duplicate | `test_concurrency` (real threads, both databases) |
| Tenant and role scope, CSRF | `test_http`, `test_reporting` (export), `test_demo_tour` |
| Expiry with every tab closed | `test_worker` (separate OS process), e2e |
| Shift report math, overnight shifts, waitlist filter, demo and practice exclusion, CSV safety | `test_reporting` |
| Shared limits across processes, fail closed, startup refusal, health endpoints | `test_hosting` |
| Pairing: single use, expiry, supersede, replay, races, single-location accounts only | `test_hosting`, `test_site` |
| POS shadow mode: dedupe, identity checks, no side effects | `test_pos_shadow`, `test_resets` |

---

## Architecture

```
restaurant-dispatch/
  config/              settings (environment-driven), urls, wsgi
  dispatch/            domain core: no views or templates
    states.py          explicit task, table and visit states
    profiles.py        edition and preset rules (data, not branches)
    permissions.py     role capabilities, profile-aware
    engine.py          every state transition (transaction-safe, audited)
    reporting.py       shift report and CSV, derived from tasks and audit events
    config_ops.py      manager configuration and device pairing
    selectors.py       read-side board queries, tenant-scoped
    seeding.py         sample restaurants, demo sandboxes, setup parsing
    integrations/pos.py  POS adapter interface (shadow mode only)
  web/                 rendering: views, templates, static, CSP middleware
    ratelimit.py       shared atomic limits (Redis) for pairing and demo starts
    demo_tour.py       guided demo tour (real engine actions)
    showcase.py        homepage storyboards rendered with the real staff templates
  docs/                pilot runbook, staging runbook
  e2e/                 Playwright browser checks
```

Key design points (unchanged from the first release):

- Tables, visits and tasks have separate, explicit states.
- Every transition is a version-guarded conditional UPDATE inside a
  transaction, with row locks on PostgreSQL.
- Creation requests carry idempotency tokens.
- Boards short-poll, and a dropped connection shows the action as
  "Not confirmed" until the board is re-read.

## Security and privacy

- **Scope:** every staff URL names a membership owned by the signed-in user,
  and every engine lookup is scoped to the actor's location. Role
  capabilities are re-checked in the engine. New views follow the same rules:
  the shift report, CSV export, observations, waitlist toggle and tour
  endpoints.
- **Pairing codes** are for floor staff devices:
  - HMAC-hashed, single use (enforced by a conditional update), expire after
    15 minutes, and superseded by a newer code
  - refused for managers, accounts with a password, and accounts linked to
    another location, both when issued and when redeemed
  - attempts are rate-limited per client address, and a successful pairing
    gives its attempt back
- **Rate limits:** pairing and demo starts are counted atomically in Redis
  (one Lua script: INCRBY plus EXPIRE), with client addresses hashed. If
  Redis is down, both endpoints fail closed. Client IPs honor exactly
  `DISPATCH_TRUSTED_PROXY_COUNT` proxies.
- **Web protections:** CSRF on every POST; a strict Content-Security-Policy
  (no inline script or style); secure, HTTP-only cookies when debug is off;
  HSTS and SSL redirect through environment variables.
- **Data minimization:** party size only, never guest names, payment data,
  payroll or staff location. The shift CSV has no names or notes.

## Setup wizard

`/setup/` takes a new venue through six steps:

1. Create the location.
2. Choose the edition and preset.
3. Paste table labels.
4. Add roles and sections.
5. Pair devices.
6. Run a practice ticket and reset.

Start and finish are recorded and shown in the shift report and on
**Manage → Now**. With `DISPATCH_SETUP_OPEN=false`, setup is invite-only:
`createsuperuser`, sign in, then open `/setup/`.

## POS integrations

Manual Expo and table events run service. `dispatch/integrations/pos.py` keeps
the adapter boundary, and shadow-mode `ingest()` does three things:

1. **Dedupes vendor retries** by event ID.
2. **Checks identity:** the location (`Location.pos_ref`), the table, and the
   course number against the course the party is on.
3. **Records** what Syncora *would* do.

It never creates tasks, changes tables, writes to the staff activity log or
alerts anyone. A closed check never frees a table. Toast (first) and Square
show as *planned, not connected*. See
`dispatch/tests/fixtures/pos_shadow_ready_events.json`.

---

## Hosted pilot (staging)

[`docs/staging.md`](docs/staging.md) has the deploy, migrate, rollback and
monitoring steps and the full environment-variable list. Included:

- **`Dockerfile`:** one image for web and worker. Behind a TLS-inspecting
  proxy, pass its CA as a build secret (`--secret id=build_ca,src=…`); it is
  never stored in the image.
- **`docker-compose.staging.yml`:** PostgreSQL, Redis, a migration job, two
  web processes and the worker. The worker's health check is
  `check_worker`.
- **`Procfile`** for platforms that use one, and
  **`deploy/staging.env.example`** with placeholders only.

Remaining steps need inputs from outside this repository: a host, managed
PostgreSQL and Redis, a domain with HTTPS, and generated secrets. Publishing
and paid infrastructure are a separately authorized step.

## Not in this release

- Individual server acknowledgments and seat-level placement for Coordinated
  Service.
- Live POS automation (shadow mode only).
- Guest-request workflows, custom hardware and payments.
- Push notifications (boards poll every 2.5 seconds).
- Performance claims, testimonials, customer logos and pricing on the public
  site.
