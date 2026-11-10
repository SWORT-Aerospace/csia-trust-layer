"""Hosted-pilot safeguards: shared atomic limits across processes, fail-closed
public endpoints, startup refusal, pairing restrictions, health endpoints."""

import http.client
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dispatch import config_ops, engine
from dispatch.models import PairingCode, StaffMember, WorkerHeartbeat
from dispatch.selectors import WORKER_NAME
from web import ratelimit

from .helpers import sample, subprocess_db_env, table

TEST_REDIS = os.environ.get("DISPATCH_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")


def redis_available():
    try:
        import redis

        return bool(redis.Redis.from_url(TEST_REDIS, socket_connect_timeout=0.5).ping())
    except Exception:
        return False


def flush_test_redis():
    import redis

    redis.Redis.from_url(TEST_REDIS).flushdb()


class LimiterTests(TestCase):
    def test_local_limiter_counts_and_refunds(self):
        limiter = ratelimit.LocalLimiter()
        counts = [limiter.add("k", 1, 60) for _ in range(3)]
        self.assertEqual(counts, [1, 2, 3])
        self.assertEqual(limiter.add("k", -1, 60), 2)
        self.assertFalse(limiter.shared)

    def test_client_ip_honours_only_trusted_proxies(self):
        rf = RequestFactory()
        request = rf.get("/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7")
        with override_settings(DISPATCH_TRUSTED_PROXY_COUNT=0):
            self.assertEqual(ratelimit.client_ip(request), "10.0.0.9")  # spoofable header ignored
        with override_settings(DISPATCH_TRUSTED_PROXY_COUNT=1):
            self.assertEqual(ratelimit.client_ip(request), "203.0.113.7")  # appended by our proxy
        with override_settings(DISPATCH_TRUSTED_PROXY_COUNT=3):
            self.assertEqual(ratelimit.client_ip(request), "10.0.0.9")  # chain shorter than trusted hops

    def test_redis_counter_is_atomic_and_always_expires(self):
        if not redis_available():
            self.skipTest(f"Redis not reachable at {TEST_REDIS}")
        flush_test_redis()
        limiter = ratelimit.RedisLimiter(TEST_REDIS)
        results = []
        lock = threading.Lock()

        def worker():
            for _ in range(25):
                n = limiter.add("atomic", 1, 60)
                with lock:
                    results.append(n)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), list(range(1, 201)))  # no lost or duplicate increments
        ttl = limiter.client.ttl(limiter.prefix + "atomic")
        self.assertTrue(0 < ttl <= 60, ttl)


class FailClosedTests(TestCase):
    def setUp(self):
        ratelimit._instances.clear()  # fresh in-process counters for this test
        self.loc, self.s = sample("regular", prefix="fc-")

    @override_settings(DISPATCH_REDIS_URL="redis://127.0.0.1:1/0")
    def test_public_endpoints_fail_closed_but_staff_boards_keep_working(self):
        response = self.client.post(reverse("web:pair"), {"code": "ABCD-EFGH"})
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "temporarily unavailable", status_code=503)
        response = self.client.post(reverse("web:demo_start"), {"profile": "regular"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(StaffMember.objects.filter(user__username__startswith="demo_").exists())
        staff = Client()
        staff.force_login(self.s["Sam"].user)
        self.assertEqual(staff.get(reverse("web:screen", args=[self.s["Sam"].pk, "pass"])).status_code, 200)
        done = staff.post(
            reverse("web:act", args=[self.s["Sam"].pk, "food_ready"]),
            {"table": table(self.loc, "4").pk},
            HTTP_X_DISPATCH_FETCH="1",
        )
        self.assertEqual(done.status_code, 200)

    @override_settings(DISPATCH_PAIR_ATTEMPT_LIMIT=3)
    def test_pairing_attempts_are_limited(self):
        for _ in range(3):
            self.assertEqual(self.client.post(reverse("web:pair"), {"code": "WRONG-CODE"}).status_code, 200)
        self.assertEqual(self.client.post(reverse("web:pair"), {"code": "WRONG-CODE"}).status_code, 429)


class StartupRefusalTests(TestCase):
    def run_check(self, extra_env, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DISPATCH_", "DJANGO_", "DATABASE_URL"))}
        env.update({"DJANGO_DEBUG": "false", "DJANGO_SECRET_KEY": "x" * 60, "DISPATCH_ALLOW_DEMO_LOGINS": "false"})
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, "manage.py", "check", *args],
            cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=60,
        )

    def test_staging_refuses_to_start_without_shared_cache(self):
        result = self.run_check({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DISPATCH_REDIS_URL must point to a shared Redis", result.stderr)

    def test_deploy_check_flags_unreachable_redis(self):
        result = self.run_check({"DISPATCH_REDIS_URL": "redis://127.0.0.1:1/0"}, "--deploy")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dispatch.E003", result.stderr + result.stdout)

    def test_deploy_check_passes_with_shared_redis(self):
        if not redis_available():
            self.skipTest(f"Redis not reachable at {TEST_REDIS}")
        result = self.run_check(
            {"DISPATCH_REDIS_URL": TEST_REDIS, "DISPATCH_SECURE_SSL_REDIRECT": "true", "DISPATCH_HSTS_SECONDS": "3600"},
            "--deploy",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("dispatch.E", result.stderr + result.stdout)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Http:
    """Tiny client that keeps cookies itself (no Secure-cookie filtering)."""

    def __init__(self, port):
        self.port, self.cookies = port, {}

    def call(self, method, path, form=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {"Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        body = None
        if form is not None:
            body = urlencode(form)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        text = response.read().decode()
        for header in response.msg.get_all("Set-Cookie") or []:
            name, _, rest = header.partition("=")
            self.cookies[name.strip()] = rest.split(";", 1)[0]
        return response.status, response.getheader("Location") or "", text

    def form_token(self, path):
        _, _, html = self.call("GET", path)
        return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)


class TwoProcessLimitTests(TransactionTestCase):
    """Two separate gunicorn processes, one shared Redis: limits are global."""

    def setUp(self):
        if not redis_available():
            self.skipTest(f"Redis not reachable at {TEST_REDIS}")
        env = subprocess_db_env(connection)
        if env is None:
            self.skipTest("needs a file-backed SQLite or PostgreSQL test DB")
        flush_test_redis()
        env.update(
            {
                "DISPATCH_REDIS_URL": TEST_REDIS,
                "DISPATCH_PAIR_ATTEMPT_LIMIT": "4",
                "DISPATCH_DEMO_PER_CLIENT_LIMIT": "3",
                "DJANGO_DEBUG": "true",
            }
        )
        self.procs, self.ports = [], []
        for _ in range(2):
            port = _free_port()
            proc = subprocess.Popen(
                [sys.executable, "-m", "gunicorn", "config.wsgi:application", "--bind", f"127.0.0.1:{port}", "--workers", "1"],
                cwd=settings.BASE_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.procs.append(proc)
            self.ports.append(port)
        for port in self.ports:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    if Http(port).call("GET", "/healthz")[0] == 200:
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                self.fail(f"gunicorn on {port} never became healthy")

    def tearDown(self):
        for proc in getattr(self, "procs", []):
            proc.terminate()
            proc.wait(10)

    def test_pairing_attempts_are_shared_across_processes(self):
        a, b = Http(self.ports[0]), Http(self.ports[1])
        statuses = []
        for client in (a, b, a, b):
            token = client.form_token("/pair/")
            statuses.append(client.call("POST", "/pair/", {"code": "WRONG-CODE", "csrfmiddlewaretoken": token})[0])
        self.assertEqual(statuses, [200, 200, 200, 200])  # 4 wrong codes, split across processes
        for client in (b, a):
            token = client.form_token("/pair/")
            status, _, html = client.call("POST", "/pair/", {"code": "WRONG-CODE", "csrfmiddlewaretoken": token})
            self.assertEqual(status, 429)
            self.assertIn("Too many attempts", html)

    def test_demo_starts_are_shared_across_processes(self):
        a, b = Http(self.ports[0]), Http(self.ports[1])
        locations = []
        for client in (a, b, a, b):
            token = client.form_token("/demo/")
            _, location, _ = client.call("POST", "/demo/start/", {"profile": "regular", "csrfmiddlewaretoken": token})
            locations.append(location)
        self.assertEqual(locations[:3], ["/demo/floor/"] * 3)
        self.assertEqual(locations[3], "/demo/")  # the 4th start, on the other process, is refused


class PairingRulesTests(TestCase):
    def setUp(self):
        self.loc, self.s = sample("regular", prefix="pr-")
        self.other_loc, self.o = sample("captain_release", prefix="po-")

    def test_codes_are_only_for_single_location_floor_accounts(self):
        with self.assertRaises(engine.Forbidden):
            config_ops.create_pairing_code(self.s["Kim"], self.s["Kim"].pk)  # a manager
        maria_user = self.s["Maria"].user
        maria_user.set_password("a-long-password-1")
        maria_user.save()
        with self.assertRaises(engine.Forbidden):
            config_ops.create_pairing_code(self.s["Kim"], self.s["Maria"].pk)  # has a password
        StaffMember.objects.filter(pk=self.o["Mateo"].pk).update(user=self.s["Dev"].user)
        with self.assertRaises(engine.Forbidden):
            config_ops.create_pairing_code(self.s["Kim"], self.s["Dev"].pk)  # account reaches another location

    def test_code_is_refused_if_the_account_changed_after_issue(self):
        code, _ = config_ops.create_pairing_code(self.s["Kim"], self.s["Lee"].pk)
        StaffMember.objects.filter(pk=self.o["Lee"].pk).update(user=self.s["Lee"].user)
        self.assertIsNone(config_ops.redeem_pairing_code(code))
        self.assertIsNone(config_ops.redeem_pairing_code(code))  # burned, not reusable

    def test_codes_expire_supersede_and_cannot_be_replayed(self):
        first, _ = config_ops.create_pairing_code(self.s["Kim"], self.s["Lee"].pk)
        second, record = config_ops.create_pairing_code(self.s["Kim"], self.s["Lee"].pk)
        self.assertIsNone(config_ops.redeem_pairing_code(first))  # superseded by the newer code
        PairingCode.objects.filter(pk=record.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(config_ops.redeem_pairing_code(second))  # expired
        third, _ = config_ops.create_pairing_code(self.s["Kim"], self.s["Lee"].pk)
        self.assertEqual(config_ops.redeem_pairing_code(third), self.s["Lee"])
        self.assertIsNone(config_ops.redeem_pairing_code(third))  # single use


class PairingRaceTests(TransactionTestCase):
    def test_simultaneous_redemptions_produce_one_device(self):
        if connection.vendor == "sqlite" and ":memory:" in str(connection.settings_dict["NAME"]):
            self.skipTest("needs a file-backed SQLite test DB")
        from .test_concurrency import race

        loc, s = sample("regular", prefix="rr-")
        code, _ = config_ops.create_pairing_code(s["Kim"], s["Lee"].pk)
        results = race(*(lambda: config_ops.redeem_pairing_code(code) for _ in range(3)))
        winners = [r for r in results if r[0] == "ok" and r[1] is not None]
        self.assertEqual(len(winners), 1, results)


class HealthTests(TestCase):
    def test_public_health_reveals_nothing_internal(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_worker_health_needs_the_operator_token(self):
        self.assertEqual(self.client.get("/healthz/worker").status_code, 404)  # disabled without a token
        with override_settings(DISPATCH_HEALTH_TOKEN="operator-token-for-tests"):
            self.assertEqual(self.client.get("/healthz/worker").status_code, 401)
            auth = {"HTTP_AUTHORIZATION": "Bearer operator-token-for-tests"}
            response = self.client.get("/healthz/worker", **auth)
            self.assertEqual((response.status_code, response.json()), (503, {"worker": "stalled"}))
            WorkerHeartbeat.objects.create(name=WORKER_NAME, beat_at=timezone.now())
            response = self.client.get("/healthz/worker", **auth)
            self.assertEqual((response.status_code, response.json()), (200, {"worker": "ok"}))

    def test_check_worker_command(self):
        with self.assertRaises(CommandError):
            call_command("check_worker")
        WorkerHeartbeat.objects.create(name=WORKER_NAME, beat_at=timezone.now() - timedelta(seconds=90))
        with self.assertRaises(CommandError):
            call_command("check_worker", "--max-age", "30")
        call_command("check_worker", "--max-age", "120")
