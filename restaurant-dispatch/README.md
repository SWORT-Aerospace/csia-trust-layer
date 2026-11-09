# Restaurant Service Dispatch

Restaurant Service Dispatch connects the kitchen pass, runners, servers,
bussers, hosts, captains, sommeliers and floor managers during a live shift.
It records who owns each handoff, routes missed offers to backup coverage or a
lead, and shows when work is physically complete.

It ships as one Django codebase with one dispatch engine and two editions:

| Edition | Preset (public name) | What changes |
|---|---|---|
| Regular Service | — | Expo taps **Food ready** → the run is offered to one runner → backup → floor lead. |
| Fine Dining | **Captain Release** | Expo **stages** courses at the pass; runners can't see them until the captain releases to one runner. Missed offers return to the captain. |
| Fine Dining | **Pairing Coordination** | Adds a sommelier readiness check; the captain can mark a course as needing no pairing. |
| Fine Dining | **Coordinated Service** | Also requires the captain's confirmation that the service team is ready. One runner is assigned. |

Table resets work the same in both editions: a server or host confirms the
party has physically left → a busser claims and completes the reset → the host
sees **Ready to seat**. Paying the check never marks a table vacant.

> This directory is self-contained. It lives alongside, and does not touch,
> the CSIA Trust Layer project at the repository root.

---

## Quick start (local demo)

Requirements: Python 3.11+ (tested on 3.12 and 3.13). No other services are
needed: local development uses SQLite.

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

`scripts/dev.sh` runs migrations, seeds the two sample restaurants, starts the
**timer worker** in the background and the web server on port 8000
(`scripts/dev.sh 8080` for another port). Then open:

| What | URL |
|---|---|
| Homepage | http://127.0.0.1:8000/ |
| Interactive demo (isolated sandbox, no sign-up) | http://127.0.0.1:8000/demo/ |
| Staff sign in | http://127.0.0.1:8000/signin/ |
| Pair a phone or tablet | http://127.0.0.1:8000/pair/ |
| Setup wizard (new location) | http://127.0.0.1:8000/setup/ |
| Health check (worker heartbeat) | http://127.0.0.1:8000/healthz |

To run the two processes yourself instead of `scripts/dev.sh`:

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

### Demonstrating it to an operator

1. Open **/demo/**, pick *Regular Service* or a *Fine Dining* preset, and
   press **Start the demo**. Every visitor gets a private sandbox restaurant
   with sample data and a random account (no password). It is deleted after
   `DISPATCH_DEMO_TTL_HOURS` (default 6).
2. The **demo floor** shows six real staff screens side by side on a desktop
   (Expo, Runner, Backup runner, Host, Busser, Floor lead — or Expo, Captain,
   Sommelier, Runner, Host, Busser for Fine Dining). On a phone, open one
   person at a time; the yellow bar at the top switches person.
3. Each person's permissions are enforced by the server. Acting as a runner,
   the captain's and manager's actions are refused.
4. Demo offers expire after 30 seconds so you can watch a run move to backup
   and then to the floor lead (or back to the captain) without touching it.
5. On a Fine Dining demo, the **Switch preset** control changes Captain
   Release / Pairing Coordination / Coordinated Service live.

### Seeded local accounts

`seed_demo` creates two persistent sample restaurants with password accounts
for trying **Staff sign in** locally. The password for every account is the
value of `DISPATCH_DEMO_STAFF_PASSWORD`, or `service-demo-local` if unset.

| Restaurant | Accounts |
|---|---|
| Juniper & Pine (Regular Service) | `jp-sam` expo · `jp-maria`, `jp-dev` runners · `jp-lee`, `jp-jo` bussers · `jp-ana` host · `jp-theo` server · `jp-rae` floor lead · `jp-kim` manager |
| Marrow Room (Fine Dining, Pairing Coordination) | `mr-noor` expo · `mr-elise` captain · `mr-jordan` sommelier · `mr-mateo`, `mr-priya` runners · `mr-lee` busser · `mr-ana` host · `mr-kim` manager |

These are local-only: `seed_demo` refuses to run unless `DJANGO_DEBUG=true`,
seeded accounts can't sign in when `DISPATCH_ALLOW_DEMO_LOGINS=false`, and
`manage.py check --deploy` fails (`dispatch.E001`) if they are allowed on a
non-debug deployment.

---

## The timer worker

Offer expiry (primary → backup → floor lead / captain) is driven by a separate
process, never by a browser tab:

```bash
.venv/bin/python manage.py run_dispatch_worker
```

It sweeps every second (`--interval`), writes a heartbeat, and deletes expired
demo sandboxes every five minutes. `--once` runs a single sweep (useful from
cron). Leads, captains and managers see a red warning if the heartbeat is more
than 15 seconds old, and `/healthz` reports `worker_online`. Running two
workers is safe (every transition is a guarded conditional update), but one is
enough.

---

## Tests

```bash
.venv/bin/python manage.py test dispatch
```

58 tests covering the engine, HTTP enforcement, the site, the wizard and the
worker. The same suite runs on PostgreSQL:

```bash
DATABASE_URL=postgres://USER:PASSWORD@127.0.0.1:5432/DBNAME .venv/bin/python manage.py test dispatch
```

Browser checks (Playwright + Chromium) against a running server and worker:

```bash
NODE_PATH=$(npm root -g) node e2e/run_flows.cjs http://127.0.0.1:8000
```

They need the `playwright` npm package and a Chromium it can launch. Each run
writes screenshots and `report.json` to `e2e/artifacts/` (git-ignored). The
expiry check waits about 25 seconds and lowers that demo sandbox's timeouts
to 10 seconds.

### Acceptance tests and where they're covered

| Acceptance test | Automated coverage |
|---|---|
| Homepage renders at mobile and desktop widths; demo action leads to a usable workflow | `e2e` homepage checks (390 px and 1440 px, no overflow, no console errors); `test_site.PublicSiteTests` |
| Regular run Expo → Runner → Delivered; expired offer → Backup → escalates | `test_regular` (`…expo_to_runner_to_delivered`, `…backup_then_escalates_to_floor_lead`); `e2e` regular flow |
| Reset Vacated → Busser → Ready to seat; a previous visit's reset can't change a newly occupied table | `test_resets` (`…vacated_to_busser_to_ready_to_seat`, `…previous_visits_reset_cannot_release…`, `…engine_guard_ignores_stale_visit…`); `e2e` reset flow |
| Captain holds and releases; Pairing Coordination rejects early release until pairing resolved; Coordinated Service also requires team readiness | `test_fine_dining` (all classes); `e2e` fine-dining checks, including a direct POST that the server refuses with 409 |
| Two simultaneous claims → one winner; replaying a creation request doesn't duplicate | `test_concurrency` (real threads, separate DB connections, on SQLite and PostgreSQL); `test_regular…replaying…`; `test_http…full_regular_flow_over_http` (double tap) |
| No access to another location's tasks; no captain or manager action without permission | `test_http` (404 across tenants, 403 for roles, CSRF required); `e2e` roles check |
| Offer expiration progresses with every browser tab closed | `test_worker.IndependentWorkerProcessTests` (worker as a separate OS process, no client); `e2e` closes every tab, waits, reopens and finds the run with the floor lead |
| Clean checkout starts from this README | Verified by cloning the branch into an empty directory and following *Quick start* |

---

## Architecture

A Django modular monolith with server-rendered pages and a small amount of
JavaScript. The dispatch rules don't depend on page rendering.

```
restaurant-dispatch/
  config/            settings (env-driven), urls, wsgi
  dispatch/          domain core — no views or templates
    states.py        explicit task / table / visit states
    profiles.py      edition + preset rules (data, not branches)
    permissions.py   role capabilities, profile-aware
    engine.py        every state transition (transaction-safe, audited)
    config_ops.py    manager configuration + device pairing
    selectors.py     read-side board queries, tenant-scoped
    seeding.py       sample restaurants, demo sandboxes, setup parsing
    integrations/pos.py   POS adapter interface + fake adapter (shadow mode)
    management/commands/  run_dispatch_worker, seed_demo, cleanup_demos
  web/               rendering: views, templates, static (CSS/JS), CSP middleware
  e2e/               Playwright browser checks
```

**Separate records for tables, visits and tasks.** A *Table* is furniture with
an explicit state (`ready`, `occupied`, `needs_reset`, `resetting`). A *Visit*
is one party's stay (party size only). A *Task* is one run, course or reset
(`staged`, `offered`, `escalated`, `claimed`, `completed`, `cancelled`) with
timestamps for ready, staged, released, offered, claimed, escalated and
completed. A reset only frees its table if the table still belongs to that
reset's visit. A late completion from an earlier party is logged as
`reset.stale` and changes nothing.

**One engine, profile rules.** `ServiceProfile` decides whether expo stages or
fires, which readiness checks block release, who receives escalations (floor
lead or captain), and whether escalated work is open for any runner to claim.
Switching preset is a data change. There are no per-edition code paths.

**Concurrency and idempotency.** Every transition is a conditional `UPDATE …
WHERE version = ? AND state IN (…)` inside a transaction. On PostgreSQL the row
is also locked first: the bare row with `SELECT … FOR UPDATE`, then related data
read in a fresh statement, so the losing claimant is told who actually won.
SQLite runs WAL with `IMMEDIATE` transactions. Creation requests carry a client
token with a per-location unique constraint, and a partial unique constraint
allows one live reset per visit, so a double tap or replay returns the original
task.

**Live boards.** Each screen short-polls an HTML partial every 2.5 seconds.
Actions post with `fetch` and also work as plain form posts. If a request
times out or the connection drops, the screen shows **Not confirmed**, locks
action buttons, and re-reads the board from the server before anyone retries.
A half-filled pass form keeps its token, so a retry is deduplicated.

---

## Security and privacy

- **Sign-in:** Django sessions with username and password for managers and
  leads, plus single-use device pairing codes for floor staff. Codes are
  HMAC-hashed at rest, expire after 15 minutes, and failed attempts are
  throttled.
- **Scope:** every staff URL names a membership that must belong to the
  signed-in user. Every engine lookup filters by the actor's location, so
  another tenant's objects return 404. Role capabilities are checked again in
  the engine for every action.
- **Web protections:** framework CSRF on every POST; a strict
  Content-Security-Policy (no inline script or style); a permissions policy
  that denies geolocation, camera and microphone; secure, HTTP-only cookies
  when `DJANGO_DEBUG=false`; HSTS and SSL redirect through environment
  variables.
- **Secrets:** secrets come only from environment variables. The settings
  refuse to start without `DJANGO_SECRET_KEY` when debug is off. See
  `.env.example` and `deploy/staging.env.example`; both contain placeholders
  only.
- **Data minimization:** no guest names (party size only), no payment details,
  no payroll, no staff location tracking.
- **Authorized staff:** allergy alerts can be set only by expo, the captain or
  a manager, and runners see the alert without being able to change it.
  Refunds and guest recovery are deliberately not in the product.
- **Demo isolation:** each demo visitor gets their own restaurant and a
  random, passwordless account, deleted after the TTL. There are no shared
  demo credentials.

---

## Setup wizard

`/setup/` creates a location in the browser, in this order:

1. create the location
2. choose the edition and preset
3. paste table labels (`Main: 1-12`, `Patio: P1-P6`)
4. add staff with roles and assign section coverage
5. pair devices
6. complete a practice run and reset with the real engine

Start and finish are recorded on `SetupSession` and in the activity log
(`setup.started` / `setup.finished` with `duration_seconds`). Managers see
the setup time on **Manage → Now**. The design target is under 10 minutes.
`DISPATCH_SETUP_OPEN=false` makes setup invite-only: create a user with
`manage.py createsuperuser`, sign in, then open `/setup/`.

## POS integrations

The first release runs on manual Expo and table events.
`dispatch/integrations/pos.py` defines a small `POSAdapter` interface and a
`FakePOSAdapter` used by the tests. `ingest()` records events in **shadow
mode**: it stores what dispatch *would* do and never changes floor state. A
`check_closed` event explicitly never frees a table. Toast (first) and Square
appear under **Manage → Integrations** as *planned, not connected*, with the
Connect button disabled. No vendor access is simulated or required. An
adapter should leave shadow mode only after the site proves that its event
means the full course is ready at the pass.

---

## Configuration

| Variable | Default (local) | Notes |
|---|---|---|
| `DJANGO_DEBUG` | `true` | `false` for any hosted deployment |
| `DJANGO_SECRET_KEY` | dev key | **required** when debug is off |
| `DJANGO_ALLOWED_HOSTS` | localhost | comma-separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | e.g. `https://staging.example.com` |
| `DATABASE_URL` | SQLite `db.sqlite3` | `postgres://…` for the hosted pilot |
| `DISPATCH_DEMO_ENABLED` | `true` | isolated demo sandboxes |
| `DISPATCH_DEMO_TTL_HOURS` | `6` | sandbox lifetime |
| `DISPATCH_ALLOW_DEMO_LOGINS` | = debug | seeded password accounts; must be `false` when public |
| `DISPATCH_DEMO_STAFF_PASSWORD` | `service-demo-local` | local seeded accounts only |
| `DISPATCH_SETUP_OPEN` | = debug | open self-serve setup |
| `DISPATCH_DEFAULT_TIME_ZONE` | `America/New_York` | per-location override in Manage → Rules |
| `DISPATCH_SECURE_SSL_REDIRECT`, `DISPATCH_HSTS_SECONDS` | off | enable behind HTTPS |

---

## Hosted pilot: staging configuration and remaining steps

Included and validated locally with `DJANGO_DEBUG=false`, PostgreSQL 16,
gunicorn (3 workers), WhiteNoise and the full browser suite (10/10):

- `Dockerfile`: one image for both the web and worker processes
- `docker-compose.staging.yml`: PostgreSQL, a one-shot migration, web and worker
- `Procfile`: release, web and worker for platforms that use one
- `deploy/staging.env.example`: placeholders only

The Docker image itself has not been built here (no Docker engine was
available). Publishing and paid infrastructure need separate authorization.
The remaining steps are:

1. Choose a host that runs two long-lived processes (web and worker) plus
   managed PostgreSQL.
2. Copy `deploy/staging.env.example` to the host's secret store. Generate
   `DJANGO_SECRET_KEY`, set the real domain in `DJANGO_ALLOWED_HOSTS` and
   `DJANGO_CSRF_TRUSTED_ORIGINS`, and keep `DISPATCH_ALLOW_DEMO_LOGINS=false`.
3. Build and deploy the image. Run `python manage.py migrate --noinput` as the
   release step, then run `gunicorn …` (web) and `python manage.py
   run_dispatch_worker` (worker).
4. Terminate HTTPS at the platform and set `DISPATCH_SECURE_SSL_REDIRECT=true`
   and `DISPATCH_HSTS_SECONDS`. Run `python manage.py check --deploy`; it
   should report only HSTS preload, which is an operator decision.
5. Switch `CACHES` to a shared backend (Redis or Django's database cache) so
   the pairing-code and demo-start throttles apply across all web workers.
   Today they are per process.
6. Create the pilot manager with `python manage.py createsuperuser`, sign in,
   and run `/setup/` (or keep `DISPATCH_SETUP_OPEN=true` for self-serve).
7. Add uptime monitoring on `/healthz` (alert when `worker_online` is false)
   and back up the database.

## Not in this release

Shown as disabled in the interface, or left out of it:

- Individual server acknowledgments and seat-level placement for
  Coordinated Service. The MVP records the captain's team-ready confirmation
  and assigns one runner.
- Live POS integrations (Toast, then Square). These are planned, will start in
  shadow mode, and show a disabled Connect button.
- Push notifications. Boards poll every 2.5 seconds.
- Performance metrics, testimonials, customer logos and pricing on the public
  site. These wait until they are supported and approved.
