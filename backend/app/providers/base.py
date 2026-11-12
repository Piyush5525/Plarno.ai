"""Shared provider plumbing: persistent cache (stale-if-error), per-provider rate limiting, daily quota guard, retries.
No secret is ever logged or returned: callers pass keys in headers/params only."""
import json
import logging
import threading
import time
from datetime import date
from typing import Callable

import httpx

from .. import config, db
from ..provenance import now_iso

log = logging.getLogger("plarno.providers")
class QuotaGuard(RuntimeError):
    """Our own daily call cap was reached. Not a provider outage: must not open the circuit breaker."""


_locks: dict[str, threading.Lock] = {}
_last: dict[str, float] = {}


def throttle(provider: str, min_interval: float):
    lock = _locks.setdefault(provider, threading.Lock())
    with lock:
        wait = _last.get(provider, 0) + min_interval - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[provider] = time.time()


_broken_until: dict[str, float] = {}
last_outcome: dict[str, dict] = {}  # provider -> {ok, at}: what the most recent real network attempt did


def breaker_open(provider: str) -> bool:
    """Circuit breaker: after repeated failures skip the provider for a cool-down so user requests never stall."""
    return time.time() < _broken_until.get(provider, 0)


def trip_breaker(provider: str, seconds: float = 300):
    _broken_until[provider] = time.time() + seconds
    log.warning("circuit opened for %s (%ss)", provider, int(seconds))


def reset_breakers():
    _broken_until.clear()


def quota_ok(provider: str, per_day: int) -> bool:
    row = db.one("SELECT calls FROM api_usage WHERE provider=? AND day=?", (provider, date.today().isoformat()))
    return (row["calls"] if row else 0) < per_day


def quota_use(provider: str):
    db.run("INSERT INTO api_usage(provider,day,calls) VALUES(?,?,1) ON CONFLICT(provider,day) DO UPDATE SET calls=calls+1", (provider, date.today().isoformat()))


def prov(source: str, kind: str, fetched_at: str | None = None, note: str | None = None, confidence: float = 0.8) -> dict:
    return {"source": source, "kind": kind, "fetched_at": fetched_at or now_iso(), "confidence": confidence, "note": note}


def cached_fetch(key: str, ttl: int, fetch: Callable[[], dict | list | None]) -> tuple[object | None, str, str | None]:
    """Returns (data, kind, fetched_at_iso). kind: 'live' fresh from network, 'cached' from cache (fresh or stale after a failure), None data on total failure.
    Offline mode serves cache only."""
    row = db.one("SELECT value, fetched_at FROM api_cache WHERE key=?", (key,))
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(t))  # noqa: E731
    if row and time.time() - row["fetched_at"] < ttl:
        return json.loads(row["value"]), "cached", iso(row["fetched_at"])
    if not config.OFFLINE and not breaker_open(key.split(':')[0]):
        try:
            data = fetch()
            if data is not None:
                db.run("INSERT INTO api_cache(key,value,fetched_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, fetched_at=excluded.fetched_at",
                       (key, json.dumps(data), time.time()))
                last_outcome[key.split(":")[0]] = {"ok": True, "at": now_iso()}
                return data, "live", now_iso()
        except QuotaGuard:
            last_outcome[key.split(":")[0]] = {"ok": False, "at": now_iso(), "error": "daily cap reached"}
            if row:
                return json.loads(row["value"]), "cached", iso(row["fetched_at"])
            return None, "quota", None
        except Exception as e:  # noqa: BLE001
            log.warning("provider fetch failed key=%s err=%s", key.split(":")[0], type(e).__name__)
            last_outcome[key.split(":")[0]] = {"ok": False, "at": now_iso(), "error": type(e).__name__}
            trip_breaker(key.split(":")[0])
    if row:  # stale-if-error
        return json.loads(row["value"]), "cached", iso(row["fetched_at"])
    return None, "none", None


def http_json(method: str, url: str, retries: int = 1, timeout: float = 20, **kw) -> dict:
    last: Exception | None = None
    for i in range(retries + 1):
        try:
            r = httpx.request(method, url, timeout=timeout, **kw)
            if r.status_code in (429, 502, 503, 504) and i < retries:
                time.sleep(1.5 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            last = e
            if i < retries:
                time.sleep(1.0)
    raise last or RuntimeError("request failed")
