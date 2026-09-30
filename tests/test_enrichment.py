import asyncio

import pytest

from rivyou.cache import write_snapshot
from rivyou.config import CrawlConfig
from rivyou.db import EmptyQueueError
from rivyou.fetch import Fetched
from rivyou.models import Store
from rivyou.pipeline import Pipeline


def test_enrichment_is_one_follow_up_and_does_not_requeue_accepted_records(db):
    db.import_candidates(
        [
            {"url": "one.in", "source": "Test", "source_url": "https://source.com/"},
            {"url": "two.in", "source": "Test", "source_url": "https://source.com/"},
            {"url": "three.in", "source": "Test", "source_url": "https://source.com/"},
        ]
    )
    rid, candidates = db.start_run(CrawlConfig().to_dict())
    for i, candidate in enumerate(candidates):
        store = Store(
            store_id=candidate["id"],
            domain_url=candidate["url"],
            status="accepted" if i == 1 else "review",
            shopify="verified" if i == 0 else "unconfirmed",
        )
        db.save_result(rid, candidate["id"], store.model_dump())
    db.finish_run(rid, "completed")
    rid, selected = db.start_run(CrawlConfig(operation="enrich").to_dict())
    assert len(selected) == 1
    store = Store(
        store_id=selected[0]["id"],
        domain_url=selected[0]["url"],
        status="review",
        shopify="verified",
    )
    db.save_result(rid, selected[0]["id"], store.model_dump())
    db.finish_run(rid, "completed")
    with pytest.raises(EmptyQueueError):
        db.start_run(CrawlConfig(operation="enrich").to_dict())


def test_enrichment_reuses_homepage_adds_address_and_keeps_replay_evidence(
    db, storefront_html
):
    db.import_candidates(
        [{"url": "merchant.in", "source": "Test", "source_url": "https://source.com/"}]
    )
    rid, candidates = db.start_run(CrawlConfig().to_dict())
    candidate = candidates[0]
    cid = candidate["id"]
    html = storefront_html.replace(
        "Registered office: Brand Private Limited, 12 MG Road, Bengaluru, Karnataka 560001, India.",
        "We sell skincare.",
    ).replace('<img alt="Test brand logo" src="/logo.png">', "")
    home = Fetched(
        candidate["url"], candidate["url"], 200, "ok", html.encode(), "text/html"
    )
    folder = db.path.parent / "cache"
    folder.mkdir()
    write_snapshot(folder, home.body)
    db.save_observation(rid, cid, home.observation("page"))
    db.save_result(
        rid,
        cid,
        Store(
            store_id=cid,
            domain_url=candidate["url"],
            status="review",
            shopify="verified",
        ).model_dump(),
    )
    db.finish_run(rid, "completed")
    config = CrawlConfig(operation="enrich", max_pages=11)
    new_rid, selected = db.start_run(config.to_dict())

    class FakeFetcher:
        cache_dir = folder
        requested = []

        async def get(self, url, **kwargs):
            self.requested.append(url)
            body = b"<p>Registered office: Brand Private Limited, 12 MG Road, Bengaluru, Karnataka 560001, India.</p>"
            result = Fetched(url, url, 200, "ok", body, "text/html")
            write_snapshot(folder, body)
            db.save_observation(new_rid, cid, result.observation("page"))
            return result

    fetcher = FakeFetcher()
    asyncio.run(Pipeline(db, config).collect_one(new_rid, selected[0], fetcher))
    assert candidate["url"] not in fetcher.requested
    assert len(fetcher.requested) == 4
    row = db.all_candidates()[0]
    assert row["store"]["status"] == "accepted"
    assert row["store"]["state"] == "Karnataka"
    saved = db.cached_pages(db.latest_page_run(cid), cid)
    assert saved[0]["content_hash"] == home.digest
    assert saved[0]["observed_at"] == home.observed_at
    assert len(saved) == 5
