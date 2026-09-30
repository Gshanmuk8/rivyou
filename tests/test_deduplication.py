import json

from rivyou.config import CrawlConfig
from rivyou.extract import extract
from rivyou.report import project, snapshot_files


def test_shop_identity_prefers_custom_domain_merges_contacts_and_explains_alias(
    db, page_factory, storefront_html
):
    db.import_candidates(
        [
            {"url": url, "source": "Fixture", "source_url": "https://example.com/list"}
            for url in (
                "https://merchant.in/",
                "https://brand.myshopify.com/",
                "https://other.in/",
            )
        ]
    )
    rid, candidates = db.start_run(CrawlConfig().to_dict())
    for candidate in candidates:
        html = storefront_html
        if "myshopify" in candidate["url"]:
            html = html.replace("hello@merchant.in", "extra@merchant.in")
        if "other.in" in candidate["url"]:
            html = html.replace("brand.myshopify.com", "different.myshopify.com")
        store = extract(
            [page_factory(html, candidate["url"])], candidate["id"], candidate["url"]
        )
        db.save_result(rid, candidate["id"], store.model_dump())
    db.finish_run(rid, "completed")
    rows = project(db.all_candidates())
    accepted = [r for r in rows if r["status"] == "accepted"]
    assert len(accepted) == 2
    winner = next(r for r in accepted if r["url"] == "https://merchant.in/")
    assert winner["store"]["emails"] == ["extra@merchant.in", "hello@merchant.in"]
    assert "https://brand.myshopify.com/" in winner["store"]["aliases"]
    duplicate = json.loads(snapshot_files(rows, db.runs())["unresolved.json"])[0]
    assert duplicate["duplicate_of"] == winner["id"]
    assert duplicate["reason"] == f"Duplicate of accepted store {winner['id']}."
