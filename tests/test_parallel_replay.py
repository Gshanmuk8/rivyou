import pytest

from rivyou.cache import write_snapshot
from rivyou.config import CrawlConfig
from rivyou.extract import extract
from rivyou.fetch import Fetched, Fetcher
from rivyou.replay import parallel_replay


async def test_offline_fetch_rejects_requests_before_network(tmp_path):
    async with Fetcher(CrawlConfig(offline=True), cache_dir=tmp_path) as fetcher:
        with pytest.raises(RuntimeError, match="disabled"):
            await fetcher.get("https://example.com/")


async def test_spawned_replay_preserves_fields_dates_and_makes_no_requests(
    db, storefront_html, page_factory
):
    db.import_candidates(
        [
            {
                "url": f"https://merchant{i}.example.com",
                "source": "Fixture",
                "source_url": "https://example.com/list",
            }
            for i in range(3)
        ]
    )
    rid, candidates = db.start_run(CrawlConfig().to_dict())
    folder = db.path.parent / "cache"
    folder.mkdir()
    expected = {}
    for candidate in candidates:
        page = page_factory(storefront_html, candidate["url"])
        fetched = Fetched(
            page.url,
            page.url,
            200,
            "ok",
            page.fetched.body,
            "text/html",
            observed_at=page.fetched.observed_at,
        )
        write_snapshot(folder, fetched.body)
        db.save_observation(rid, candidate["id"], fetched.observation("page"))
        store = extract([page], candidate["id"], candidate["url"])
        expected[candidate["id"]] = store.model_dump()
        db.save_result(rid, candidate["id"], store.model_dump())
    db.finish_run(rid, "completed")
    replay_id = await parallel_replay(db, 3, 2)
    run = next(r for r in db.runs() if r["id"] == replay_id)
    assert run["status"] == "completed" and run["completed"] == 3
    assert run["requests"] == run["bytes"] == 0
    for row in db.all_candidates():
        assert row["store"] == expected[row["id"]]
        assert db.cached_pages(replay_id, row["id"])[0]["kind"] == "cached_page"
