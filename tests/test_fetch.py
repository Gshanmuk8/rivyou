import httpx
import pytest

from rivyou.config import CrawlConfig
from rivyou.fetch import Fetcher, PublicTransport, retry_after
from rivyou.urls import normalize_url, same_site


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/",
        "http://localhost/",
        "file:///tmp/file",
        "https://user:password@example.com",
        "https://example.com:8080",
    ],
)
def test_unsafe_urls_rejected(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_aliases_require_evidence():
    assert normalize_url("www.Brand.in", homepage=True) == "https://www.brand.in/"
    assert (
        normalize_url("https://brand.in/Case?utm_source=x&variant=123")
        == "https://brand.in/Case?variant=123"
    )
    assert not same_site("https://one.myshopify.com", "https://two.myshopify.com")


async def test_robots_disallow_is_respected(tmp_path):
    visited = []

    def handler(request):
        visited.append(request.url.path)
        return httpx.Response(
            200,
            text="User-agent: *\nDisallow: /private\n",
            headers={"content-type": "text/plain"},
        )

    async with Fetcher(
        CrawlConfig(delay_seconds=0, retries=0),
        transport=httpx.MockTransport(handler),
        cache_dir=tmp_path,
    ) as fetcher:
        result = await fetcher.get("https://example.com/private")
    assert result.outcome == "robots_blocked"
    assert visited == ["/robots.txt"]


async def test_robots_network_error_is_not_permission(tmp_path):
    def handler(request):
        return httpx.Response(503)

    async with Fetcher(
        CrawlConfig(delay_seconds=0, retries=0),
        transport=httpx.MockTransport(handler),
        cache_dir=tmp_path,
    ) as fetcher:
        result = await fetcher.get("https://example.com/")
    assert result.outcome == "robots_blocked"


async def test_allow_end_anchor_and_wildcard(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /*.json$\nAllow: /safe.json\n",
                headers={"content-type": "text/plain"},
            )
        return httpx.Response(200, text="ok", headers={"content-type": "text/html"})

    async with Fetcher(
        CrawlConfig(delay_seconds=0, retries=0),
        transport=httpx.MockTransport(handler),
        cache_dir=tmp_path,
    ) as f:
        assert (
            await f.get("https://example.com/products.json")
        ).outcome == "robots_blocked"
        assert (await f.get("https://example.com/safe.json")).outcome == "ok"


async def test_redirect_destination_checks_own_robots(tmp_path):
    visits = []

    def handler(request):
        visits.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /"
                if request.url.host == "blocked.com"
                else "",
                headers={"content-type": "text/plain"},
            )
        return httpx.Response(302, headers={"location": "https://blocked.com/"})

    async with Fetcher(
        CrawlConfig(delay_seconds=0, retries=0),
        transport=httpx.MockTransport(handler),
        cache_dir=tmp_path,
    ) as f:
        result = await f.get("https://example.com/")
    assert result.outcome == "robots_blocked"
    assert "https://blocked.com/" not in visits


async def test_size_budget_applies_to_decoded_body(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200, content=b"x" * 100, headers={"content-type": "text/html"}
        )

    async with Fetcher(
        CrawlConfig(delay_seconds=0, retries=0, max_bytes=50),
        transport=httpx.MockTransport(handler),
        cache_dir=tmp_path,
    ) as f:
        result = await f.get("https://example.com/")
    assert result.outcome == "too_large"
    assert len(result.body) <= 50


async def test_dns_pinning_preserves_tls_hostname(monkeypatch):
    import rivyou.fetch as module

    async def resolve(host):
        return ["8.8.8.8"]

    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200)

    monkeypatch.setattr(module, "public_addresses", resolve)
    transport = PublicTransport()
    await transport.inner.aclose()
    transport.inner = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await client.get("https://example.com/test")
    assert captured[0].url.host == "8.8.8.8"
    assert captured[0].extensions["sni_hostname"] == "example.com"
    assert captured[0].headers["host"] == "example.com"


async def test_long_retry_after_is_deferred(tmp_path):
    visits = []

    def handler(request):
        visits.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(429, headers={"retry-after": "3600"})

    async with Fetcher(
        CrawlConfig(delay_seconds=0, retries=2),
        transport=httpx.MockTransport(handler),
        cache_dir=tmp_path,
    ) as f:
        result = await f.get("https://example.com/")
    assert result.status_code == 429
    assert visits == ["/robots.txt", "/"]
    assert "Deferred" in result.detail


def test_retry_after_values():
    assert retry_after("10") == 10
    assert retry_after("-1") == 0
    assert retry_after("nonsense") == 0
