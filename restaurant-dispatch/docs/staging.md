# Syncora staging: deploy, migrate, roll back, monitor

This covers a hosted staging or pilot deployment. Publishing it and paying for
infrastructure are separate decisions; nothing here does either.

## Processes

| Process | Command | Instances |
|---|---|---|
| Web | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3` | 1 or more |
| Timer worker | `python manage.py run_dispatch_worker` | exactly 1 (a second is safe but unnecessary) |
| Release step | `python manage.py migrate --noinput` | once per deploy, before new web processes take traffic |

Required services: PostgreSQL (`DATABASE_URL`) and Redis
(`DISPATCH_REDIS_URL`). Redis holds only short-lived rate-limit counters, so
it needs no persistence or backups.

## Startup guarantees

- With `DJANGO_DEBUG=false`, every entry point (gunicorn, worker,
  `manage.py`) refuses to start without `DJANGO_SECRET_KEY` and
  `DISPATCH_REDIS_URL`. Rate limits can't silently become per-process.
- `python manage.py check --deploy` fails on:
  - `dispatch.E001`: seeded demo logins are allowed
  - `dispatch.E002`: the rate-limit cache is process-local
  - `dispatch.E003`: Redis is configured but unreachable

  With HTTPS settings on, the only expected warning is `security.W021` (HSTS
  preload), which is an operator decision.
- If Redis goes down while running, `/pair/` and `/demo/start/` answer 503
  with a friendly message (fail closed). Signed-in staff boards and actions
  keep working because they never touch Redis.

## Safe deploy

1. Back up PostgreSQL (snapshot or `pg_dump`).
2. Build the image. Behind a TLS-inspecting proxy, add
   `--secret id=build_ca,src=<ca-bundle>`.

   ```bash
   docker build -t syncora:<version> .
   ```

3. Run the release step with the new image:
   `python manage.py migrate --noinput`.
4. Run `python manage.py check --deploy` with the production environment. It
   must report no `dispatch.E*` errors.
5. Replace the web processes, then the worker.
6. Smoke-test:
   - `GET /healthz` returns `{"ok": true}`
   - `GET /healthz/worker` with `Authorization: Bearer $DISPATCH_HEALTH_TOKEN`
     returns `{"worker": "ok"}`
   - one sign-in works

Migrations in this release (`0002_pilot_measurement`) only add nullable or
defaulted columns, one new table and one partial unique index. The previous
release keeps running against the migrated schema, so migrating before
switching code is safe.

## Rollback

1. Redeploy the previous image for the web and worker processes. Leave the
   database as it is: the old code ignores the new columns and table.
2. Reverse the schema only if you must, and only after a backup:

   ```bash
   python manage.py migrate dispatch 0001
   ```

   This drops the shift observations, waitlist snapshots and POS shadow
   fields recorded since the upgrade.

## Detecting a stalled timer worker

Any one of these is enough:

- **Command** (cron or platform health check): `python manage.py check_worker
  --max-age 30` exits 1 when the last heartbeat is older than 30 seconds.
  `docker-compose.staging.yml` wires it as the worker's health check.
- **HTTP** (uptime monitor): `GET /healthz/worker` with the bearer token
  returns 200 `{"worker":"ok"}` or 503 `{"worker":"stalled"}`. It returns 404
  when `DISPATCH_HEALTH_TOKEN` is unset.
- **In the app:** floor leads, captains and managers see a red banner, and
  **Manage → Now** shows the heartbeat.

The public `/healthz` reports only liveness (`{"ok": true}`, or 503 if the
database is unreachable). It never includes tenant data, versions or worker
details.

## Environment variables (no values here; see `deploy/staging.env.example`)

| Variable | Notes |
|---|---|
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | 50+ random characters |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins |
| `DATABASE_URL` | PostgreSQL |
| `DISPATCH_REDIS_URL` | Shared Redis for atomic rate limits |
| `DISPATCH_TRUSTED_PROXY_COUNT` | Proxies appending `X-Forwarded-For` (1 behind one load balancer) |
| `DISPATCH_HEALTH_TOKEN` | Bearer token for `/healthz/worker` |
| `DISPATCH_ALLOW_DEMO_LOGINS` | Must be `false` |
| `DISPATCH_DEMO_ENABLED` | Whether visitors can start isolated demo sandboxes |
| `DISPATCH_DEMO_TTL_HOURS` | Lifetime of a demo sandbox |
| `DISPATCH_SETUP_OPEN` | `false` keeps setup invite-only: first manager via `createsuperuser` |
| `DISPATCH_SECURE_SSL_REDIRECT` | `true` behind HTTPS |
| `DISPATCH_HSTS_SECONDS` | HSTS max-age behind HTTPS |
| `DISPATCH_PAIR_ATTEMPT_LIMIT` | Optional tuning (default 10 per 10 minutes) |
| `DISPATCH_DEMO_PER_CLIENT_LIMIT` | Optional tuning (default 30 per hour) |
| `DISPATCH_DEMO_GLOBAL_LIMIT` | Optional tuning (default 600 per hour) |
| `DISPATCH_DEFAULT_TIME_ZONE` | Default time zone for new locations |
