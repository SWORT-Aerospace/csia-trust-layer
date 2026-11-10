"""Shared, atomic rate limits for the public pairing and demo-start endpoints.

Hosted (DJANGO_DEBUG=false) deployments must set DISPATCH_REDIS_URL: every web
process then counts against the same Redis key, incremented atomically with
a server-side script (INCRBY + EXPIRE in one step, so no key is ever left
without an expiry). Local development without Redis uses an in-process
counter; settings refuse to start a non-debug deployment without Redis.

If Redis is unreachable the limiter raises ``LimiterUnavailable`` and the
public endpoints fail closed. Staff boards never touch the limiter.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass

from django.conf import settings

log = logging.getLogger("dispatch")

_SCRIPT = """
local n = redis.call('INCRBY', KEYS[1], ARGV[1])
if redis.call('TTL', KEYS[1]) < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return n
"""


class LimiterUnavailable(Exception):
    """The shared limiter can't be reached. Callers must fail closed."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    count: int
    limit: int


class RedisLimiter:
    shared = True

    def __init__(self, url: str, prefix: str = "syncora:rl:"):
        import redis

        self._errors = (redis.RedisError, OSError)
        self.client = redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        self.script = self.client.register_script(_SCRIPT)
        self.prefix = prefix

    def add(self, key: str, amount: int, window: int) -> int:
        try:
            return int(self.script(keys=[self.prefix + key], args=[amount, window]))
        except self._errors as error:
            raise LimiterUnavailable(str(error)) from error

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except self._errors:
            return False


class LocalLimiter:
    """Development only: counts inside this one process."""

    shared = False

    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[str, tuple[int, float]] = {}

    def add(self, key: str, amount: int, window: int) -> int:
        now = time.monotonic()
        with self._lock:
            count, expires = self._data.get(key, (0, now + window))
            if expires <= now:
                count, expires = 0, now + window
            count += amount
            self._data[key] = (count, expires)
            return count

    def ping(self) -> bool:
        return True


_instances: dict[str, object] = {}
_instances_lock = threading.Lock()


def get_limiter():
    url = getattr(settings, "DISPATCH_REDIS_URL", "") or ""
    with _instances_lock:
        if url not in _instances:
            _instances[url] = RedisLimiter(url) if url else LocalLimiter()
        return _instances[url]


def _key(scope: str, ident: str) -> str:
    # Hash identifiers (client IPs) so Redis never stores them in the clear.
    return f"{scope}:{hashlib.sha256(ident.encode()).hexdigest()[:32]}"


def hit(scope: str, ident: str, limit: int, window: int) -> Decision:
    """Count one attempt atomically and say whether it is within the limit."""
    count = get_limiter().add(_key(scope, ident), 1, window)
    return Decision(allowed=count <= limit, count=count, limit=limit)


def refund(scope: str, ident: str, window: int) -> None:
    """Give back one attempt (for example, after a successful pairing)."""
    try:
        get_limiter().add(_key(scope, ident), -1, window)
    except LimiterUnavailable:
        log.warning("rate limiter unavailable while refunding %s", scope)


def client_ip(request) -> str:
    """The client address, honouring exactly DISPATCH_TRUSTED_PROXY_COUNT
    proxies in X-Forwarded-For (0 = use the socket address)."""
    trusted = getattr(settings, "DISPATCH_TRUSTED_PROXY_COUNT", 0)
    remote = request.META.get("REMOTE_ADDR", "unknown")
    if trusted <= 0:
        return remote
    chain = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    if len(chain) < trusted:
        return remote
    return chain[-trusted]
