import pytest

from rivyou.db import Database
from rivyou.extract import Page
from rivyou.fetch import Fetched


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "rivyou.sqlite")


@pytest.fixture
def page_factory():
    def create(html, url="https://merchant.in/"):
        return Page.from_fetch(
            Fetched(
                url,
                url,
                status_code=200,
                outcome="ok",
                body=html.encode(),
                content_type="text/html",
            )
        )

    return create


@pytest.fixture
def storefront_html():
    return """<html><head><title>Test brand</title><meta name="description"
       content="Small-batch skincare with sunscreen and face serum.">
       <script>var Shopify = Shopify || {}; Shopify.shop = 'brand.myshopify.com';</script>
       <script src="/cdn/shopifycloud/storefront/assets/runtime.js"></script></head>
       <body><header><a href="/"><img alt="Test brand logo" src="/logo.png"></a></header>
       <nav><a href="/products/serum">Shop skincare</a><a href="/pages/contact">Contact</a></nav>
       <p>Registered office: Brand Private Limited, 12 MG Road, Bengaluru, Karnataka 560001, India.</p>
       <a href="mailto:hello@merchant.in">Email us</a><a href="tel:+919876543210">Call</a>
       <a href="https://instagram.com/testbrand?utm_source=footer">Instagram</a>
       <a href="https://facebook.com/sharer.php?u=merchant.in">Share</a></body></html>"""
