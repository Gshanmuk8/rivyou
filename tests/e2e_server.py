"""Isolated browser QA server. No merchant network requests or production data.

Run: python tests/e2e_server.py --port 8766
Each invocation uses a fresh temporary workspace. HTTP is replaced only here;
the real fetcher, robots checks, pipeline, SQLite, API and UI remain in use.
"""

import argparse
import asyncio
import tempfile
from dataclasses import replace
from pathlib import Path

import httpx
import uvicorn

import rivyou.pipeline as pipeline_module
from rivyou.api import create_app
from rivyou.config import ROOT, CrawlConfig
from rivyou.db import Database
from rivyou.fetch import Fetcher


async def fixture_response(request):
    host, path = request.url.host, request.url.path
    if not (host.startswith("fixture-") and host.endswith(".in")):
        raise httpx.ConnectError(
            "This test server only serves fixture domains.", request=request
        )
    await asyncio.sleep(0.2)
    if path == "/robots.txt":
        rule = "Disallow: /" if host == "fixture-blocked.in" else "Allow: /"
        return httpx.Response(
            200, text=f"User-agent: *\n{rule}\n", headers={"content-type": "text/plain"}
        )
    if path == "/logo.svg":
        return httpx.Response(
            200,
            text='<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="#157d6d"/></svg>',
            headers={"content-type": "image/svg+xml"},
        )
    name = host.removesuffix(".in").replace("-", " ").title()
    address = (
        ""
        if host == "fixture-review.in"
        else "Registered office: Example Private Limited, 12 MG Road, Bengaluru, Karnataka 560001, India."
    )
    html = f'''<html><head><title>{name}</title>
      <meta name="description" content="Small-batch skincare with sunscreen and face serum.">
      <script>var Shopify = Shopify || {{}}; Shopify.shop = '{host.split(".")[0]}.myshopify.com';</script>
      <script src="/cdn/shopifycloud/storefront/assets/runtime.js"></script></head>
      <body><header><a href="/"><img alt="{name} logo" src="/logo.svg"></a></header>
      <nav><a href="/products/serum">Shop skincare</a><a href="/pages/contact">Contact</a></nav>
      <p>{address}</p><a href="mailto:hello@{host}">Email</a><a href="tel:+919876543210">Call</a>
      <a href="https://instagram.com/fixturebrand">Instagram</a></body></html>'''
    return httpx.Response(200, text=html, headers={"content-type": "text/html"})


class FixtureFetcher(Fetcher):
    def __init__(self, config: CrawlConfig, observer=None, cache_dir=None):
        super().__init__(
            replace(config, delay_seconds=0.05),
            observer,
            transport=httpx.MockTransport(fixture_response),
            cache_dir=cache_dir,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    pipeline_module.Fetcher = FixtureFetcher
    with tempfile.TemporaryDirectory(prefix="e2e-", dir=ROOT / "work") as directory:
        app = create_app(Database(Path(directory) / "fixture.sqlite"))
        uvicorn.run(app, host="127.0.0.1", port=args.port)
