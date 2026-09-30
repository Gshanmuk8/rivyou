import pytest
from fastapi.testclient import TestClient

from rivyou.api import create_app
from rivyou.config import CrawlConfig
from rivyou.db import Database
from rivyou.pipeline import Pipeline

ENTRY = {
    "url": "merchant.in",
    "source": "Fixture",
    "source_url": "https://source.com/list",
}


def test_white_svg_class_rules_get_a_dark_preview_background():
    from rivyou.pipeline import logo_background

    svg = b'<svg><style>.brand { fill: #fff; stroke: white; }</style><path class="brand"/></svg>'
    assert logo_background(svg, "svg") == "dark"


def test_api_pause_reaches_worker_using_another_database_connection(db):
    db.import_candidates([ENTRY])
    rid, candidates = db.start_run(CrawlConfig().to_dict())
    worker = Pipeline(Database(db.path))
    with TestClient(create_app(db)) as client:
        response = client.post(
            f"/api/runs/{rid}/cancel", headers={"X-Rivyou-Request": "1"}
        )
        assert response.status_code == 200
        assert worker.should_pause(rid)
        assert client.get("/api/runs").json()[0]["pause_requested"] == 1
    db.item_started(rid, candidates[0]["id"])
    db.finish_run(rid, "cancelled")
    resumed, pending = db.start_run(CrawlConfig().to_dict(), resume_id=rid)
    assert resumed == rid and len(pending) == 1
    assert not worker.should_pause(rid)


def test_pause_non_running_run_reports_actionable_error(db):
    with TestClient(create_app(db)) as client:
        response = client.post(
            "/api/runs/missing/cancel", headers={"X-Rivyou-Request": "1"}
        )
        assert response.status_code == 400
        assert "no longer running" in response.json()["detail"]


def test_finished_paused_run_cannot_resume_into_empty_job(db):
    db.import_candidates([ENTRY])
    rid, candidates = db.start_run(CrawlConfig().to_dict())
    db.save_result(rid, candidates[0]["id"], {"status": "review"})
    db.finish_run(rid, "cancelled")
    with pytest.raises(ValueError, match="already finished"):
        db.start_run(CrawlConfig().to_dict(), resume_id=rid)
    assert db.runs()[0]["status"] == "cancelled"


@pytest.mark.parametrize("field", ["domains", "source", "source_url"])
def test_whitespace_only_import_fields_are_rejected(db, field):
    body = {
        "domains": "merchant.in",
        "source": "Fixture",
        "source_url": "https://source.com/list",
    }
    body[field] = " " * 12
    with TestClient(create_app(db)) as client:
        response = client.post(
            "/api/import", json=body, headers={"X-Rivyou-Request": "1"}
        )
        assert response.status_code == 422
        assert db.all_candidates() == []


async def test_pause_preserves_page_and_resume_does_not_fetch_it_again(
    db, storefront_html, monkeypatch
):
    import httpx

    from rivyou.fetch import Fetcher

    db.import_candidates([ENTRY])
    config = CrawlConfig(delay_seconds=0, retries=0)
    rid, candidates = db.start_run(config.to_dict())
    visits = []

    def handler(request):
        visits.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/logo.png":
            return httpx.Response(404)
        if request.url.path == "/":
            db.request_pause(rid)
        return httpx.Response(
            200, text=storefront_html, headers={"content-type": "text/html"}
        )

    def fixture_fetcher(config, observer, cache_dir):
        return Fetcher(
            config,
            observer,
            transport=httpx.MockTransport(handler),
            cache_dir=cache_dir,
        )

    monkeypatch.setattr("rivyou.pipeline.Fetcher", fixture_fetcher)
    worker = Pipeline(db, config)
    await worker.execute(rid, candidates)
    assert db.runs()[0]["status"] == "cancelled"
    assert len(db.cached_pages(rid, candidates[0]["id"])) == 1
    assert db.runs()[0]["completed"] == 0
    await worker.run(resume_id=rid)
    assert db.runs()[0]["status"] == "completed"
    assert db.all_candidates()[0]["status"] == "accepted"
    assert visits.count("/") == 1
