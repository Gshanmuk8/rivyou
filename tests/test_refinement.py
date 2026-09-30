import pytest

from rivyou.cache import write_snapshot
from rivyou.config import CrawlConfig
from rivyou.extract import extract, logo_candidates, social_link, valid_email
from rivyou.refine import refine_store


def test_paused_migration_cannot_be_resumed_as_network_collection(
    db, page_factory, storefront_html
):
    db.import_candidates(
        [
            {
                "url": "https://merchant.in",
                "source": "Fixture",
                "source_url": "https://source.org/",
            }
        ]
    )
    rid, candidates = db.start_run(CrawlConfig().to_dict(), 1)
    store = extract(
        [page_factory(storefront_html)], candidates[0]["id"], candidates[0]["url"]
    ).model_dump()
    store["rule_version"] = "2026-09-30.7"
    db.save_result(rid, candidates[0]["id"], store)
    db.finish_run(rid, "completed")
    migration, _ = db.start_run(
        CrawlConfig(operation="refine", offline=True).to_dict(), 1
    )
    db.finish_run(migration, "cancelled")
    with pytest.raises(ValueError, match="Repeat the offline refine command"):
        db.start_run(CrawlConfig().to_dict(), 1, migration)
    assert next(r for r in db.runs() if r["id"] == migration)["status"] == "cancelled"


def test_foreign_parent_logo_in_footer_is_not_the_store_logo(
    page_factory, storefront_html, tmp_path
):
    body = storefront_html.replace(
        "</body>",
        '<footer><div class="footer-logo"><a href="https://parentbrand.com/"><img src="/parent-logo.png" alt="Parent logo"></a></div></footer></body>',
    )
    page = page_factory(body)
    assert all("/parent-logo.png" not in choice[1] for choice in logo_candidates(page))
    store = extract([page], "brand", page.url).model_dump()
    store["rule_version"] = "2026-09-30.7"
    store["logo_url"] = "https://merchant.in/parent-logo.png"
    store["logo_path"] = "old.png"
    store["evidence"].append(
        page.evidence("logo_url", store["logo_url"], "header_brand_image").model_dump()
    )
    write_snapshot(tmp_path, page.fetched.body)
    result = refine_store(store, [page.fetched.observation("page")], tmp_path)
    assert result["logo_url"] is None and result["logo_path"] is None
    assert result["status"] == "accepted"
    assert not any(e["field"] == "logo_url" for e in result["evidence"])


def test_displayed_email_wins_over_copied_mailto(
    page_factory, storefront_html, tmp_path
):
    body = storefront_html.replace(
        "</body>",
        '<a href="mailto:info@anotherbrand.in">support@merchant.in</a></body>',
    )
    page = page_factory(body)
    store = extract([page], "brand", page.url).model_dump()
    assert "support@merchant.in" in store["emails"]
    assert "info@anotherbrand.in" not in store["emails"]
    store["rule_version"] = "2026-09-30.7"
    store["emails"].append("info@anotherbrand.in")
    store["evidence"].append(
        page.evidence(
            "emails", "info@anotherbrand.in", "mailto_link", "info@anotherbrand.in"
        ).model_dump()
    )
    write_snapshot(tmp_path, page.fetched.body)
    refined = refine_store(store, [page.fetched.observation("page")], tmp_path)
    assert "info@anotherbrand.in" not in refined["emails"]
    assert "support@merchant.in" in refined["emails"]


def test_post_links_and_concatenated_profiles_are_not_accounts():
    for value in (
        "https://x.com/MediaInfoline/status/2074748971562717404",
        "https://linkedin.com/posts/media-mohalla_lavie-123",
        "https://facebook.com/brand/posts/123",
        "https://facebook.com/settings",
        "https://youtube.com/@brandhttps://www.youtube.com/@brand",
    ):
        assert social_link(value) is None
    assert social_link("https://linkedin.com/company/the-artment/mycompany") == (
        "LinkedIn",
        "https://linkedin.com/company/the-artment",
    )
    assert valid_email("sales@voganow.com")
    assert not valid_email("sales@voganow.com.the")
    assert not valid_email("unsubscribe@emarsys.com")
    assert not valid_email("support@yourcompany.com")
    assert social_link("https://youtube.com/c/RicoHomeKitchenAppliances/videos") == (
        "YouTube",
        "https://youtube.com/c/RicoHomeKitchenAppliances",
    )


def test_theme_favicon_cannot_supply_runtime_family(page_factory, storefront_html):
    body = storefront_html.replace(
        '<script src="/cdn/shopifycloud/storefront/assets/runtime.js"></script>',
        '<link rel="icon" href="/cdn/shop/t/20/assets/favicon.png">',
    )
    assert (
        extract([page_factory(body)], "brand", "https://merchant.in/").shopify
        == "unconfirmed"
    )


def test_narrow_migration_matches_full_extraction_and_preserves_dates(
    tmp_path, page_factory, storefront_html
):
    page = page_factory(storefront_html)
    expected = extract([page], "brand", page.url).model_dump()
    old = extract([page], "brand", page.url).model_dump()
    old["rule_version"] = "2026-09-30.7"
    old["emails"].append("sales@voganow.com.the")
    old["socials"]["X"] = ["https://x.com/brand/status/123"]
    for proof in old["evidence"]:
        if proof["field"] == "shopify" and proof["family"] == "delivery":
            proof["value"] = "https://merchant.in/cdn/shop/t/1/assets/favicon.png"
    write_snapshot(tmp_path, page.fetched.body)
    observation = page.fetched.observation("page")
    result = refine_store(old, [observation], tmp_path)
    assert result["observed_at"] == old["observed_at"]
    assert result["status"] == expected["status"] == "accepted"
    assert result["emails"] == expected["emails"]
    assert result["socials"] == expected["socials"]
    assert next(e for e in result["evidence"] if e["family"] == "delivery") == next(
        e for e in expected["evidence"] if e["family"] == "delivery"
    )
    assert refine_store(result, [], tmp_path) == result
    old["shopify"] = "verified"
    assert refine_store(old, [], tmp_path)["status"] == "review"
