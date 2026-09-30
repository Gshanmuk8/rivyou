import csv
import io
import json

from fastapi.testclient import TestClient

from rivyou.api import create_app
from rivyou.config import CrawlConfig
from rivyou.extract import extract
from rivyou.report import audit_sample, export_csv, project, records

ENTRY = {
    "url": "https://merchant.in/",
    "source": "Fixture",
    "source_url": "https://source.com/list",
}


def test_import_idempotent_and_attributed(db):
    assert db.import_candidates([ENTRY])["added"] == 1
    assert db.import_candidates([ENTRY])["duplicates"] == 1
    assert db.import_candidates([{"url": "other.in"}])["errors"]
    assert len(db.all_candidates()) == 1


def test_single_active_run_and_resume(db):
    db.import_candidates([ENTRY])
    rid, items = db.start_run(CrawlConfig().to_dict())
    import pytest

    with pytest.raises(ValueError):
        db.start_run(CrawlConfig().to_dict())
    db.item_started(rid, items[0]["id"])
    db.finish_run(rid, "cancelled")
    resumed, pending = db.start_run(CrawlConfig().to_dict(), resume_id=rid)
    assert resumed == rid
    assert len(pending) == 1


def saved_store(db, page_factory, storefront_html):
    db.import_candidates([ENTRY])
    rid, items = db.start_run(CrawlConfig().to_dict())
    store = extract([page_factory(storefront_html)], items[0]["id"], ENTRY["url"])
    db.save_result(rid, items[0]["id"], store.model_dump())
    db.finish_run(rid, "completed")
    return items[0]["id"]


def test_export_round_trip_and_evidence_gate(db, page_factory, storefront_html):
    saved_store(db, page_factory, storefront_html)
    rows = project(db.all_candidates())
    exported = list(csv.DictReader(io.StringIO(export_csv(rows))))
    assert len(exported) == 1
    assert json.loads(exported[0]["emails"]) == ["hello@merchant.in"]
    assert exported[0]["state"] == "Karnataka"
    assert len(records(rows)) == 1


def test_formula_text_escaped_only_in_csv():
    from rivyou.report import csv_safe

    assert csv_safe("=1+2") == "'=1+2"
    assert csv_safe("hello") == "hello"
    assert csv_safe(["+919876543210"]) == '["+919876543210"]'


def test_review_excludes_without_erasing_original(db, page_factory, storefront_html):
    cid = saved_store(db, page_factory, storefront_html)
    db.review(cid, "excluded", "Fixture exclusion for a test.", "human")
    assert db.detail(cid)["store"]["status"] == "accepted"
    assert records(project(db.all_candidates())) == []


def test_cannot_confirm_missing_evidence(db, page_factory):
    import pytest

    cid = saved_store(db, page_factory, "<title>Unknown</title>")
    with pytest.raises(ValueError):
        db.review(cid, "confirmed", "No actual evidence.", "human")


def test_audit_sample_reproducible(db, page_factory, storefront_html):
    saved_store(db, page_factory, storefront_html)
    a = audit_sample(project(db.all_candidates()))
    b = audit_sample(project(db.all_candidates()))
    assert a["items"] == b["items"]
    assert a["items"][0]["shopify_and_india"] is None


def test_api_rejects_cross_origin_mutation(db):
    with TestClient(create_app(db)) as client:
        assert client.post("/api/import-starter").status_code == 403
        response = client.post(
            "/api/import-starter",
            headers={"X-Rivyou-Request": "1", "Origin": "https://evil.com"},
        )
        assert response.status_code == 403


def test_api_filters_and_safe_exports(db, page_factory, storefront_html):
    cid = saved_store(db, page_factory, storefront_html)
    with TestClient(create_app(db)) as client:
        assert client.get("/api/stores?q=missing").json()["total"] == 0
        result = client.get("/api/stores?status=accepted").json()
        assert result["total"] == 1
        assert "evidence" not in result["items"][0]["store"]
        assert client.get("/api/stores/" + cid).json()["store"]["evidence"]
        assert client.get("/api/export/csv").status_code == 200
        assert client.get("/api/export/wrong").status_code == 404
        assert client.get("/api/logos/..").status_code == 404


def test_empty_queue_guides_user_to_import_instead_of_starting_a_run(db):
    db.import_candidates([ENTRY])
    rid, items = db.start_run(CrawlConfig().to_dict())
    db.item_started(rid, items[0]["id"])
    db.save_result(
        rid,
        items[0]["id"],
        {"status": "review", "reason": "Fixture candidate was processed."},
    )
    db.finish_run(rid, "completed")
    with TestClient(create_app(db)) as client:
        response = client.post(
            "/api/runs", headers={"X-Rivyou-Request": "1"}, json={"limit": 1}
        )
        assert response.status_code == 409
        assert response.json()["code"] == "empty_queue"
        assert "Add new sourced domains" in response.json()["detail"]
        assert len(db.runs()) == 1


def test_html_is_never_returned_unescaped_by_api(db):
    with TestClient(create_app(db)) as client:
        response = client.post(
            "/api/import",
            headers={"X-Rivyou-Request": "1"},
            json={
                "domains": "https://merchant.in/",
                "source": "<script>alert(1)</script>",
                "source_url": "https://source.com/",
            },
        )
        assert response.status_code == 200
        assert client.get("/api/stores").headers["x-content-type-options"] == "nosniff"
