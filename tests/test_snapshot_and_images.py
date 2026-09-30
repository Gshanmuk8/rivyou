import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from test_storage_api import saved_store

from rivyou.api import create_app
from rivyou.pipeline import safe_logo
from rivyou.report import project, snapshot_files


def test_cli_export_hashes_match_files_on_disk(
    db, page_factory, storefront_html, tmp_path, monkeypatch
):
    from rivyou.cli import main

    saved_store(db, page_factory, storefront_html)
    output = tmp_path / "export"
    monkeypatch.setattr("rivyou.cli.Database", lambda: db)
    monkeypatch.setattr("sys.argv", ["rivyou", "export", "--output", str(output)])
    main()
    manifest = json.loads((output / "manifest.json").read_bytes())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    csv_bytes = (output / "stores.csv").read_bytes()
    assert b"\r\r\n" not in csv_bytes
    csv_records = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    json_records = json.loads((output / "stores.json").read_bytes())
    assert len(csv_records) == len(json_records) == manifest["records"] == 1
    assert csv_records[0]["domain_url"] == json_records[0]["domain_url"]


def test_snapshot_hashes_match_exact_download_bytes(db, page_factory, storefront_html):
    saved_store(db, page_factory, storefront_html)
    with TestClient(create_app(db)) as client:
        response = client.get("/api/export/bundle")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["records"] == 1
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        assert len(json.loads(archive.read("stores.json"))) == 1
        assert (
            json.loads(archive.read("audit-sample.json"))["snapshot_id"]
            == manifest["snapshot_id"]
        )


def test_changed_evidence_changes_snapshot_identity(db, page_factory, storefront_html):
    saved_store(db, page_factory, storefront_html)
    rows = project(db.all_candidates())
    first = json.loads(snapshot_files(rows, [])["manifest.json"])
    rows[0]["store"]["evidence"][0]["excerpt"] += " changed"
    second = json.loads(snapshot_files(rows, [])["manifest.json"])
    assert first["snapshot_id"] != second["snapshot_id"]


def test_replay_does_not_make_old_platform_evidence_fresh(
    db, page_factory, storefront_html
):
    saved_store(db, page_factory, storefront_html)
    rows = db.all_candidates()
    old = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    for evidence in rows[0]["store"]["evidence"]:
        if evidence["field"] == "shopify":
            evidence["observed_at"] = old
    assert project(rows)[0]["status"] == "stale"


def test_svg_retains_internal_brand_shapes_and_removes_external_content():
    body = b"""<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">
    <style>.brand{fill:white}</style><defs><path id="brand" d="M0 0h10v10z"/></defs>
    <use href="#brand"/><use href="https://bad.test/shape.svg"/>
    <script>alert(1)</script><image href="https://bad.test/image.png"/>
    </svg>"""
    clean, extension = safe_logo(body, "image/svg+xml")
    assert extension == "svg"
    assert b'href="#brand"' in clean
    assert b".brand{fill:white}" in clean
    assert b"bad.test" not in clean
    assert b"script" not in clean
    assert b"onload" not in clean


def test_invalid_logo_is_not_published():
    assert safe_logo(b"<html>Access denied</html>", "image/png") is None
    assert safe_logo(b"<svg", "image/svg+xml") is None
