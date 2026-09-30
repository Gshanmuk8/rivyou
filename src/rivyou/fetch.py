"""Robots-aware, bounded fetcher with DNS pinning and auditable outcomes."""

import asyncio
import hashlib
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from protego import Protego

from .cache import write_snapshot
from .config import WORK, CrawlConfig
from .models import now
from .urls import host_of, normalize_url, origin_of, public_addresses


class PublicTransport(httpx.AsyncBaseTransport):
    """Pin each connection to validated public DNS; keep original TLS SNI/Host.

    Disable keepalive so two hostnames sharing a CDN IP cannot reuse each
    other's TLS connection. No environment proxy or second hostname lookup.
    """

    def __init__(self):
        self.inner = httpx.AsyncHTTPTransport(
            retries=0,
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=0),
        )

    async def handle_async_request(self, request):
        original_host = request.url.host
        addresses = await public_addresses(original_host)
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=addresses[0]),
            headers=request.headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": original_host},
        )
        return await self.inner.handle_async_request(pinned)

    async def aclose(self):
        await self.inner.aclose()


@dataclass
class Fetched:
    url: str
    final_url: str
    status_code: int | None = None
    outcome: str = "error"
    body: bytes = b""
    content_type: str = ""
    detail: str = ""
    observed_at: str = field(default_factory=now)
    elapsed_ms: int = 0
    chain: list[str] = field(default_factory=list)

    @property
    def digest(self):
        return hashlib.sha256(self.body).hexdigest() if self.body else ""

    @property
    def text(self):
        return self.body.decode("utf-8", errors="replace")

    def observation(self, kind: str):
        return {
            "url": self.url,
            "final_url": self.final_url,
            "kind": kind,
            "status_code": self.status_code,
            "outcome": self.outcome,
            "observed_at": self.observed_at,
            "content_hash": self.digest,
            "bytes": len(self.body),
            "elapsed_ms": self.elapsed_ms,
            "detail": self.detail,
            "content_type": self.content_type,
        }


def retry_after(value: str | None) -> float:
    if not value:
        return 0
    try:
        return max(0, float(value))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return max(0, (dt - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0


class Fetcher:
    def __init__(
        self,
        config: CrawlConfig,
        observer=None,
        transport=None,
        cache_dir: Path | None = None,
    ):
        self.config, self.observer = config, observer
        self.cache_dir = cache_dir or WORK / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            transport=transport or PublicTransport(),
            follow_redirects=False,
            timeout=httpx.Timeout(config.timeout_seconds, connect=8),
            trust_env=False,
            headers={
                "User-Agent": config.user_agent,
                "Accept": "text/html,application/xhtml+xml,image/*;q=0.8,*/*;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "close",
            },
        )
        self.slots = asyncio.Semaphore(config.concurrency)
        self.locks, self.next_at, self.robots, self.robots_locks = {}, {}, {}, {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    def record(self, result: Fetched, kind: str, context):
        if result.body:
            write_snapshot(self.cache_dir, result.body)
        if self.observer:
            self.observer(context, result.observation(kind))

    async def _request(self, url: str, kind: str, context) -> tuple[Fetched, dict]:
        host = host_of(url)
        lock = self.locks.setdefault(host, asyncio.Lock())
        async with lock:
            delay = max(0, self.next_at.get(host, 0) - time.monotonic())
            if delay > 30:
                result = Fetched(
                    url,
                    url,
                    outcome="deferred",
                    detail=f"Host deferred for {delay:.0f}s; no request sent",
                )
                self.record(result, kind, context)
                return result, {}
            await asyncio.sleep(delay)
            self.next_at[host] = time.monotonic() + self.config.delay_seconds
            start = time.monotonic()
            data, headers = bytearray(), {}
            result = Fetched(url=url, final_url=url)
            try:
                async with self.slots:
                    async with asyncio.timeout(self.config.timeout_seconds):
                        async with self.client.stream("GET", url) as response:
                            result.status_code = response.status_code
                            headers = dict(response.headers)
                            result.content_type = (
                                response.headers.get("content-type", "")
                                .split(";")[0]
                                .strip()
                                .lower()
                            )
                            async for chunk in response.aiter_bytes(chunk_size=65536):
                                if len(data) + len(chunk) > self.config.max_bytes:
                                    result.outcome, result.detail = (
                                        "too_large",
                                        "Decompressed response exceeded configured byte limit",
                                    )
                                    break
                                data.extend(chunk)
                            else:
                                result.outcome = (
                                    "ok"
                                    if response.status_code == 200
                                    else "http_error"
                                )
                            result.body = bytes(data)
            except (httpx.HTTPError, ValueError, TimeoutError, OSError) as exc:
                result.outcome, result.detail = (
                    "fetch_failed",
                    f"{type(exc).__name__}: {str(exc)[:220]}",
                )
            result.elapsed_ms = int((time.monotonic() - start) * 1000)
            if result.status_code in {429, 503}:
                wait = max(retry_after(headers.get("retry-after")), 5)
                self.next_at[host] = max(self.next_at[host], time.monotonic() + wait)
                result.detail = f"Rate limited; retry after {wait:.0f}s"
            self.record(result, kind, context)
            return result, headers

    async def _get(
        self, url: str, kind: str, context, *, robots_check: bool
    ) -> Fetched:
        original, chain = url, []
        for hop in range(self.config.max_redirects + 1):
            try:
                url = normalize_url(url)
                if robots_check:
                    allowed, reason = await self.allowed(url, context)
                    if not allowed:
                        result = Fetched(
                            original,
                            url,
                            outcome="robots_blocked",
                            detail=reason,
                            chain=chain,
                        )
                        self.record(result, kind, context)
                        return result
            except ValueError as exc:
                result = Fetched(
                    original, url, outcome="unsafe_url", detail=str(exc), chain=chain
                )
                self.record(result, kind, context)
                return result
            for attempt in range(self.config.retries + 1):
                result, headers = await self._request(url, kind, context)
                transient = result.outcome == "fetch_failed" or result.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }
                if not transient or attempt == self.config.retries:
                    break
                wait = max(
                    retry_after(headers.get("retry-after")),
                    2 ** (attempt + 1) + random.random(),
                )
                if wait > 30:
                    result.detail = "Deferred: server requested a longer retry delay"
                    break
                await asyncio.sleep(wait)
            chain.append(url)
            if result.status_code in {301, 302, 303, 307, 308} and headers.get(
                "location"
            ):
                if hop == self.config.max_redirects:
                    result.outcome, result.detail = (
                        "redirect_limit",
                        "Too many redirects",
                    )
                else:
                    next_url = urljoin(url, headers["location"])
                    if next_url in chain:
                        result.outcome, result.detail = (
                            "redirect_loop",
                            "Redirect cycle",
                        )
                    else:
                        url = next_url
                        continue
            result.url, result.chain = original, chain
            return result
        raise AssertionError("Unreachable redirect state")

    async def allowed(self, url: str, context) -> tuple[bool, str]:
        origin = origin_of(url)
        lock = self.robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            entry = self.robots.get(origin)
            if entry is None or time.monotonic() - entry[0] > 86400:
                result = await self._get(
                    origin + "/robots.txt", "robots", context, robots_check=False
                )
                if result.outcome == "ok" and result.content_type in {
                    "text/plain",
                    "",
                    "application/octet-stream",
                }:
                    policy = Protego.parse(result.text)
                    entry = (time.monotonic(), policy, "")
                elif result.status_code in {404, 410}:
                    entry = (time.monotonic(), Protego.parse(""), "")
                else:
                    entry = (
                        time.monotonic(),
                        None,
                        f"Robots unavailable ({result.status_code or result.outcome}); deferred",
                    )
                self.robots[origin] = entry
            policy = entry[1]
            if policy is None:
                return False, entry[2]
            delay = policy.crawl_delay(self.config.user_agent)
            if delay:
                self.next_at[host_of(url)] = max(
                    self.next_at.get(host_of(url), 0), time.monotonic() + float(delay)
                )
            return policy.can_fetch(
                url, self.config.user_agent
            ), "Disallowed by robots.txt"

    async def get(self, url: str, *, kind: str = "page", context=None) -> Fetched:
        if self.config.offline:
            raise RuntimeError("Network requests are disabled for offline replay.")
        return await self._get(url, kind, context, robots_check=True)
